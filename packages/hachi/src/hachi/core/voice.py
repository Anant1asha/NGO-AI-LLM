"""Voice backends (speech-to-text, text-to-speech, audio playback) with graceful degradation.

:class:`SpeechToText` transcribes a local audio file via an OpenAI-compatible
``/audio/transcriptions`` endpoint; :class:`TextToSpeech` synthesizes speech to a
file via ``/audio/speech`` (OpenAI, Groq, or any compatible server);
:class:`AudioPlayer` plays a local audio file through the system's speakers using
a platform-native binary — no API key required.  All three follow the same
test-complete pattern as the browser controller and the Slack/Discord senders:

- credentials resolve **lazily from the environment** at call time (never at
  import/boot), so this constructs cleanly even with nothing configured;
- the actual HTTP POST goes through an injectable ``transcriber`` so tests run
  fully offline;
- the endpoint URL is **SSRF-validated** via ``net_guard`` before any request;
- it raises :class:`VoiceError` (a readable message) rather than leaking a raw
  HTTP/parse error — callers check :meth:`is_configured` first and surface
  failures as friendly tool results.

:class:`AudioPlayer` is **keyless** — it uses ``afplay`` on macOS, the stdlib
``winsound`` module (WAV) or ``mpv``/``ffplay`` on Windows, and ``paplay`` /
``aplay`` / ``mpv`` on Linux.  When no player is found it returns a friendly
install hint rather than raising.

:func:`probe_audio_info` is a **keyless** helper that uses only the Python
standard library to inspect a local audio file.  Full metadata (duration,
sample rate, channels) is available for WAV files.  For other formats only
the file size and extension are reported — "format not probeable" is the
friendly response rather than an error.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hachi.core.net_guard import validate_outbound_url

# (url, file_bytes, filename, form_data, headers) -> (status_code, response_text)
Transcriber = Callable[[str, bytes, str, dict[str, str], dict[str, str]], tuple[int, str]]

# (url, json_payload, headers) -> (status_code, audio_bytes)
Synthesizer = Callable[[str, dict[str, object], dict[str, str]], tuple[int, bytes]]

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "whisper-1"

_DEFAULT_TTS_MODEL = "tts-1"
_DEFAULT_TTS_VOICE = "alloy"
# Output formats an OpenAI-compatible /audio/speech endpoint produces, keyed by
# the file extension we map them from.  ``pcm`` is intentionally excluded:
# raw PCM has no container, no duration metadata, and no agreed sample-rate
# encoding — writing it to disk silently produces an unplayable file.  Callers
# who need raw PCM should request ``wav`` (same codec, playable container) or
# post-process the WAV output themselves.
_TTS_FORMATS = frozenset({"mp3", "opus", "aac", "flac", "wav"})

# Extension that would previously have been accepted by _TTS_FORMATS but is
# explicitly blocked for the reasons above.  Used to produce an actionable
# rejection message instead of a silent dead-end.
_PCM_REJECTION_MESSAGE = (
    "'.pcm' output is not supported: raw PCM has no container format and no "
    "embedded sample-rate, making the resulting file unplayable by most tools. "
    "Use '.wav' instead — it encodes the same PCM audio in a standard container "
    "that includes all required metadata. If you specifically need headerless PCM, "
    "request '.wav' and strip the 44-byte RIFF header yourself."
)

# Extensions the common Whisper endpoints accept; checked up front for a friendly
# error instead of an opaque API rejection.
_SUPPORTED_EXTENSIONS = frozenset(
    {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".flac", ".ogg", ".opus", ".aac"}
)

# Hard ceiling on audio bytes (the OpenAI endpoint caps at ~25 MB); fail fast.
_MAX_AUDIO_BYTES = 25 * 1024 * 1024


_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "i",
        "you",
        "we",
        "he",
        "she",
        "it",
        "they",
        "that",
        "this",
        "so",
        "as",
        "if",
        "not",
        "do",
        "did",
        "have",
        "has",
        "had",
        "will",
        "would",
        "can",
        "could",
        "my",
        "your",
        "our",
        "his",
        "her",
        "its",
        "their",
        "what",
        "which",
        "who",
        "how",
        "when",
        "where",
        "then",
        "than",
    }
)


def summarize_transcript(text: str, *, top_sentences: int = 3) -> dict[str, Any]:
    """Extract key sentences from a transcript using word-frequency scoring.

    Pure Python — no third-party dependencies, no LLM call, no network I/O.
    Sentences are selected by the average frequency of their non-stop-word
    tokens, then re-ordered by their original position in the transcript so the
    summary preserves narrative flow.

    Args:
        text: The raw transcript string.
        top_sentences: How many key sentences to extract (default 3).

    Returns:
        A dict with:
          - ``word_count``               — total words in the transcript
          - ``sentence_count``           — total sentences detected
          - ``key_sentences``            — list of up to *top_sentences* strings
          - ``estimated_reading_seconds`` — rough read-time at 200 wpm
    """
    if not text.strip():
        return {
            "word_count": 0,
            "sentence_count": 0,
            "key_sentences": [],
            "estimated_reading_seconds": 0,
        }

    # --- split into sentences (handles ., !, ?) ---
    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    word_count = len(text.split())

    # --- word-frequency table (non-stop content words, len > 2) ---
    freq: dict[str, int] = {}
    for tok in re.findall(r"[a-z]+", text.lower()):
        if tok not in _STOPWORDS and len(tok) > 2:
            freq[tok] = freq.get(tok, 0) + 1

    # --- score: mean frequency of content words per sentence ---
    def _score(s: str) -> float:
        words = [w for w in re.findall(r"[a-z]+", s.lower()) if w not in _STOPWORDS and len(w) > 2]
        if not words:
            return 0.0
        return sum(freq.get(w, 0) for w in words) / len(words)

    scored = sorted(
        ((i, s) for i, s in enumerate(raw_sentences)),
        key=lambda pair: _score(pair[1]),
        reverse=True,
    )
    top = scored[: max(top_sentences, 1)]
    # restore original order for narrative coherence
    key_sentences = [s for _, s in sorted(top, key=lambda pair: pair[0])]

    # ~200 words/min reading speed
    estimated_reading_seconds = round((word_count / 200) * 60)

    return {
        "word_count": word_count,
        "sentence_count": len(raw_sentences),
        "key_sentences": key_sentences,
        "estimated_reading_seconds": estimated_reading_seconds,
    }


def probe_audio_info(path: str | Path) -> dict[str, Any]:
    """Probe a local audio file for metadata without any API key or network call.

    Uses only the Python standard library.  Full metadata (duration in seconds,
    sample rate in Hz, channel count) is available for PCM-WAV files.  For all
    other formats only the file size and format hint (derived from the extension)
    are returned — the ``probeable`` flag tells the caller whether the richer
    fields are present.

    Args:
        path: Absolute or relative path to the audio file.

    Returns:
        A dict with at least:
          - ``file`` — resolved absolute path (str)
          - ``format`` — extension without leading dot, lower-case (e.g. ``"wav"``)
          - ``size_bytes`` — file size in bytes
          - ``probeable`` — ``True`` when duration/sample_rate/channels are present

        When ``probeable`` is ``True`` the dict additionally contains:
          - ``duration_seconds`` — float, e.g. ``3.71``
          - ``sample_rate`` — int, e.g. ``44100``
          - ``channels`` — int, e.g. ``1`` (mono) or ``2`` (stereo)

    Raises:
        VoiceError: If the file does not exist, is not a regular file, or the
            WAV header is corrupt.
    """
    p = Path(path).resolve()
    if not p.exists() or not p.is_file():
        raise VoiceError(f"audio file not found: {p}")

    fmt = p.suffix.lstrip(".").lower() or "unknown"
    size = p.stat().st_size

    info: dict[str, Any] = {
        "file": str(p),
        "format": fmt,
        "size_bytes": size,
        "probeable": False,
    }

    if fmt == "wav":
        try:
            with wave.open(str(p), "rb") as wf:
                n_channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                sampwidth = wf.getsampwidth()
            # OpenAI tts-1 (and other streaming encoders) write 0xFFFFFFFF as the
            # RIFF/data-chunk length sentinel, which wave reads as 0x7FFFFFFF frames.
            # Clamp to what the actual file size allows (44-byte header lower bound).
            frame_size = n_channels * sampwidth
            if frame_size > 0:
                max_frames = max(0, (size - 44) // frame_size)
                n_frames = min(n_frames, max_frames)
            duration = n_frames / sample_rate if sample_rate > 0 else 0.0
            info["probeable"] = True
            info["duration_seconds"] = round(duration, 3)
            info["sample_rate"] = sample_rate
            info["channels"] = n_channels
        except wave.Error as exc:
            raise VoiceError(f"could not read WAV header: {exc}") from exc

    return info


class VoiceError(RuntimeError):
    """Raised when a voice backend is misconfigured or rejects the request."""


def _get_shared_http_client() -> Any:
    """Return a lazily-created module-level httpx.Client (reuses TCP/TLS connections).

    Never called at import time — only on the first actual request.  The 60-second
    per-request timeout replaces the old 120-second one; the circuit-breaker in
    :mod:`hachi.core.resilience` provides the outer retry/abort boundary.
    """
    import httpx

    global _shared_http_client  # noqa: PLW0603
    if _shared_http_client is None:
        _shared_http_client = httpx.Client(
            timeout=60.0,
            follow_redirects=False,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _shared_http_client


# Module-level shared client — None until the first voice call.
_shared_http_client: Any = None


def _default_transcriber(
    url: str, file_bytes: bytes, filename: str, form_data: dict[str, str], headers: dict[str, str]
) -> tuple[int, str]:
    client = _get_shared_http_client()
    files = {"file": (filename, file_bytes)}
    resp = client.post(url, files=files, data=form_data, headers=headers)
    return resp.status_code, resp.text


class SpeechToText:
    """Transcribe audio via an OpenAI-compatible transcription endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        transcriber: Transcriber | None = None,
        allow_private: bool = False,
    ) -> None:
        self._api_key = api_key or None
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._model = model or _DEFAULT_MODEL
        self._transcriber = transcriber or _default_transcriber
        self._allow_private = allow_private

    @classmethod
    def from_env(cls, transcriber: Transcriber | None = None) -> SpeechToText:
        """Build from environment: HACHI_STT_* overrides, else OpenAI defaults."""
        return cls(
            api_key=os.environ.get("HACHI_STT_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("HACHI_STT_BASE_URL") or os.environ.get("OPENAI_BASE_URL"),
            model=os.environ.get("HACHI_STT_MODEL"),
            transcriber=transcriber,
            allow_private=os.environ.get("HACHI_REST_ALLOW_PRIVATE", "").strip().lower()
            in {"1", "true", "yes"},
        )

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def transcribe(self, audio_path: str | Path) -> str:
        """Transcribe a local audio file to text. Raises VoiceError on any failure."""
        if not self._api_key:
            raise VoiceError(
                "speech-to-text is not configured (set OPENAI_API_KEY or HACHI_STT_API_KEY)"
            )
        path = Path(audio_path)
        if not path.exists() or not path.is_file():
            raise VoiceError(f"audio file not found: {path}")
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise VoiceError(
                f"unsupported audio format '{path.suffix or '(none)'}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            )

        url = f"{self._base_url}/audio/transcriptions"
        ok, reason = validate_outbound_url(url, allow_private=self._allow_private)
        if not ok:
            raise VoiceError(f"blocked transcription endpoint: {reason}")

        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise VoiceError(f"could not read audio: {exc}") from exc
        if len(raw) > _MAX_AUDIO_BYTES:
            raise VoiceError(
                f"audio is {len(raw) // (1024 * 1024)} MB, exceeding the "
                f"{_MAX_AUDIO_BYTES // (1024 * 1024)} MB limit"
            )

        headers = {"Authorization": f"Bearer {self._api_key}"}
        status, body = self._transcriber(url, raw, path.name, {"model": self._model}, headers)
        if status != 200:
            raise VoiceError(f"transcription API returned HTTP {status}: {body[:200]}")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise VoiceError(f"could not parse transcription response: {exc}") from exc
        text = parsed.get("text")
        if not isinstance(text, str):
            raise VoiceError("transcription response did not include a 'text' field")
        return text.strip()


def _default_synthesizer(
    url: str, payload: dict[str, object], headers: dict[str, str]
) -> tuple[int, bytes]:
    client = _get_shared_http_client()
    resp = client.post(url, json=payload, headers=headers)
    return resp.status_code, resp.content


class TextToSpeech:
    """Synthesize speech from text via an OpenAI-compatible /audio/speech endpoint.

    Mirrors :class:`SpeechToText`: lazy env credentials, an injectable
    ``synthesizer`` for offline tests, SSRF-validated endpoint, readable
    :class:`VoiceError` on failure. The output audio format is inferred from the
    target file's extension (defaulting to mp3).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        voice: str | None = None,
        synthesizer: Synthesizer | None = None,
        allow_private: bool = False,
    ) -> None:
        self._api_key = api_key or None
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._model = model or _DEFAULT_TTS_MODEL
        self._voice = voice or _DEFAULT_TTS_VOICE
        self._synthesizer = synthesizer or _default_synthesizer
        self._allow_private = allow_private

    @classmethod
    def from_env(cls, synthesizer: Synthesizer | None = None) -> TextToSpeech:
        """Build from environment: HACHI_TTS_* overrides, else OpenAI defaults."""
        return cls(
            api_key=os.environ.get("HACHI_TTS_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("HACHI_TTS_BASE_URL") or os.environ.get("OPENAI_BASE_URL"),
            model=os.environ.get("HACHI_TTS_MODEL"),
            voice=os.environ.get("HACHI_TTS_VOICE"),
            synthesizer=synthesizer,
            allow_private=os.environ.get("HACHI_REST_ALLOW_PRIVATE", "").strip().lower()
            in {"1", "true", "yes"},
        )

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def synthesize(self, text: str, out_path: str | Path, voice: str | None = None) -> Path:
        """Synthesize ``text`` to an audio file at ``out_path``. Raises VoiceError on failure."""
        if not self._api_key:
            raise VoiceError(
                "text-to-speech is not configured (set OPENAI_API_KEY or HACHI_TTS_API_KEY)"
            )
        if not text.strip():
            raise VoiceError("nothing to speak: text is empty")

        path = Path(out_path)
        fmt = path.suffix.lstrip(".").lower() or "mp3"
        if fmt == "pcm":
            raise VoiceError(_PCM_REJECTION_MESSAGE)
        if fmt not in _TTS_FORMATS:
            raise VoiceError(
                f"unsupported audio format '{path.suffix or '(none)'}'. "
                f"Supported: {', '.join(sorted(_TTS_FORMATS))}"
            )

        url = f"{self._base_url}/audio/speech"
        ok, reason = validate_outbound_url(url, allow_private=self._allow_private)
        if not ok:
            raise VoiceError(f"blocked speech endpoint: {reason}")

        payload: dict[str, object] = {
            "model": self._model,
            "input": text,
            "voice": voice or self._voice,
            "response_format": fmt,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        status, audio = self._synthesizer(url, payload, headers)
        if status != 200:
            detail = audio[:200].decode("utf-8", "replace") if audio else ""
            raise VoiceError(f"speech API returned HTTP {status}: {detail}")
        if not audio:
            raise VoiceError("speech API returned no audio")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
        except OSError as exc:
            raise VoiceError(f"could not write audio file: {exc}") from exc
        return path


# ==========================================
# AudioPlayer — platform-native playback
# ==========================================

# (path) -> (exit_code, stderr_text)
Player = Callable[[Path], tuple[int, str]]

# Linux players tried in order (first found wins).
_LINUX_PLAYERS = ("paplay", "aplay", "mpv", "ffplay", "mplayer", "vlc")
# Cross-platform fallbacks (Windows + Linux when primary isn't available).
_FALLBACK_PLAYERS = ("mpv", "ffplay", "vlc")


def _detect_player_binary() -> str | None:
    """Return the name/path of the first available audio-player binary, or None.

    On macOS ``afplay`` is always present (bundled OS utility) so this rarely
    returns None there.  On Linux the first binary from ``_LINUX_PLAYERS`` that
    is on ``$PATH`` wins.  On Windows the ``winsound`` stdlib module covers WAV;
    for other formats this falls back to the same ``_FALLBACK_PLAYERS`` list.
    """
    if sys.platform == "darwin":
        return shutil.which("afplay")
    if sys.platform == "win32":
        # winsound is always available in CPython on Windows; treat as a virtual
        # "player" name so is_available() returns True for WAV.
        try:
            import winsound as _ws  # noqa: F401

            return "winsound"
        except ImportError:
            pass
        for name in _FALLBACK_PLAYERS:
            found = shutil.which(name)
            if found:
                return found
        return None
    # Linux / other POSIX
    for name in _LINUX_PLAYERS:
        found = shutil.which(name)
        if found:
            return found
    return None


def _default_player(path: Path) -> tuple[int, str]:
    """Play *path* using the first available system player.

    Returns ``(exit_code, stderr_text)``.  ``exit_code == 0`` means success;
    non-zero means the player reported an error or no suitable player was found.
    Uses ``subprocess.run`` with a list-form command — never ``shell=True``.
    """
    ext = path.suffix.lower()

    if sys.platform == "darwin":
        afplay = shutil.which("afplay")
        if not afplay:
            return 1, "afplay not found (should be built into macOS)"
        result = subprocess.run(  # noqa: S603
            [afplay, str(path)], capture_output=True, timeout=300
        )
        return result.returncode, result.stderr.decode("utf-8", "replace")

    if sys.platform == "win32":
        # WAV: use the stdlib winsound module — no subprocess needed.
        if ext == ".wav":
            try:
                import winsound

                winsound.PlaySound(str(path), winsound.SND_FILENAME)
                return 0, ""
            except Exception as exc:
                return 1, str(exc)
        # Non-WAV: try installed third-party players.
        for name in _FALLBACK_PLAYERS:
            binary = shutil.which(name)
            if binary:
                result = subprocess.run(  # noqa: S603
                    [binary, str(path)], capture_output=True, timeout=300
                )
                return result.returncode, result.stderr.decode("utf-8", "replace")
        return (
            1,
            "No audio player found for non-WAV files on Windows. "
            "Install mpv (https://mpv.io) or VLC and add it to PATH.",
        )

    # Linux / other POSIX
    for name in _LINUX_PLAYERS:
        binary = shutil.which(name)
        if binary:
            result = subprocess.run(  # noqa: S603
                [binary, str(path)], capture_output=True, timeout=300
            )
            return result.returncode, result.stderr.decode("utf-8", "replace")
    return (
        1,
        "No audio player found. Install paplay (PulseAudio), aplay (ALSA), "
        "mpv, or ffplay and ensure the binary is in PATH.",
    )


class AudioPlayer:
    """Play a local audio file through the system speakers.

    Mirrors the ``SpeechToText`` / ``TextToSpeech`` pattern:

    - An **injectable** ``player`` callable lets tests run fully offline without
      actually invoking a system binary.
    - :meth:`is_available` reflects whether a real player is found on the current
      machine (always True in tests that inject a fake player).
    - Never raises — all failures come back as a ``(non-zero, message)`` tuple.

    Usage::

        ap = AudioPlayer()
        if ap.is_available():
            code, err = ap.play(Path("hello.mp3"))
    """

    def __init__(self, player: Player | None = None) -> None:
        self._player: Player = player or _default_player

    @staticmethod
    def is_available() -> bool:
        """Return True when a suitable audio-player binary (or stdlib module) is found."""
        return _detect_player_binary() is not None

    def play(self, path: Path) -> tuple[int, str]:
        """Play *path* and return ``(exit_code, stderr_text)``.

        A ``0`` exit code indicates success.  The caller is responsible for
        validating the path before calling this method.
        """
        return self._player(path)
