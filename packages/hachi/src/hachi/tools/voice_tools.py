"""Voice tools — transcribe audio (STT), speak text (TTS), audio playback, and metadata.

``transcribe_audio`` reads a local audio file and returns its transcript;
``transcribe_and_summarize`` transcribes AND extracts the most information-dense
sentences using pure-Python word-frequency scoring (no LLM, no extra deps);
``speak_text`` synthesizes speech to a local audio file; ``play_audio`` plays
a local audio file through the system's speakers (no API key required);
``get_audio_info`` probes a local audio file for metadata (duration, sample rate,
channels for WAV; size + format hint for all others) **without any API key**.

The STT/TTS tools go through the OpenAI-compatible voice backends
(:class:`SpeechToText` / :class:`TextToSpeech`), are permission-gated (read/write
path checks; disabled in the ``sandbox`` tier), and gracefully degrade — if no
API key is configured they return a friendly hint rather than failing.

``play_audio`` uses :class:`AudioPlayer` (platform-native binary — ``afplay`` /
``winsound`` / ``paplay`` / ``mpv``) and is keyless; it too degrades gracefully
when no suitable player is installed.

All five tools are registered under the lazy ``voice`` tool group.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from hachi.core.voice import (
    AudioPlayer,
    SpeechToText,
    TextToSpeech,
    VoiceError,
    probe_audio_info,
    summarize_transcript,
)
from hachi.tools.os_tools import _normalize_user_path

_BLOCKED_TIERS = {"sandbox"}

TRANSCRIBE_AUDIO_SCHEMA: dict[str, Any] = {
    "name": "transcribe_audio",
    "description": (
        "Transcribe a local audio file (voice note, recording, voicemail) to text so "
        "you can read, summarize, or act on what was said. Supports mp3, m4a, wav, webm, "
        "flac, ogg, and more. Provide the path to the audio file."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local audio file path (absolute, ~, or relative).",
            },
        },
        "required": ["path"],
    },
}


def _tier_blocked(gate: Any | None) -> str | None:
    if gate is None:
        return None
    tier = getattr(gate, "tier", None)
    return tier if tier in _BLOCKED_TIERS else None


def _make_transcribe_audio(gate: Any | None, stt: SpeechToText | None) -> Callable[[str], str]:
    def transcribe_audio(path: str) -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: audio transcription is disabled in '{tier}' tier."

        target = _normalize_user_path(path)
        if gate is not None:
            check = gate.check_path(str(target), "read")
            if not getattr(check, "allowed", True):
                return f"Permission Denied: {getattr(check, 'reason', 'path not allowed')}"

        active = stt or SpeechToText.from_env()
        if not active.is_configured():
            return (
                "Speech-to-text is not configured. Set OPENAI_API_KEY (or "
                "HACHI_STT_API_KEY) — optionally HACHI_STT_BASE_URL / "
                "HACHI_STT_MODEL for a non-OpenAI Whisper endpoint — then try again."
            )
        try:
            text = active.transcribe(target)
        except VoiceError as exc:
            return f"Transcription failed: {exc}"
        except Exception as exc:  # never propagate; the agent should recover/report
            return f"Transcription failed: {exc}"
        return f"Transcript of {target.name}:\n\n{text}"

    return transcribe_audio


SPEAK_TEXT_SCHEMA: dict[str, Any] = {
    "name": "speak_text",
    "description": (
        "Convert text to spoken audio and save it to a local file (a voice reply, a "
        "narrated note). Provide the text and an output path ending in .mp3 / .wav / "
        ".flac / .opus / .aac. Optionally choose a voice (e.g. alloy, echo, nova)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to speak."},
            "path": {
                "type": "string",
                "description": "Output audio file path (extension sets the format; default mp3).",
            },
            "voice": {
                "type": "string",
                "description": "Optional voice name (provider-specific; default alloy).",
            },
        },
        "required": ["text", "path"],
    },
}


def _make_speak_text(gate: Any | None, tts: TextToSpeech | None) -> Callable[..., str]:
    def speak_text(text: str, path: str, voice: str = "") -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: text-to-speech is disabled in '{tier}' tier."

        target = _normalize_user_path(path)
        if gate is not None:
            check = gate.check_path(str(target), "write")
            if not getattr(check, "allowed", True):
                return f"Permission Denied: {getattr(check, 'reason', 'path not allowed')}"

        active = tts or TextToSpeech.from_env()
        if not active.is_configured():
            return (
                "Text-to-speech is not configured. Set OPENAI_API_KEY (or "
                "HACHI_TTS_API_KEY) — optionally HACHI_TTS_BASE_URL / "
                "HACHI_TTS_MODEL / HACHI_TTS_VOICE — then try again."
            )
        try:
            out = active.synthesize(text, target, voice=voice or None)
        except VoiceError as exc:
            return f"Speech synthesis failed: {exc}"
        except Exception as exc:  # never propagate; the agent should recover/report
            return f"Speech synthesis failed: {exc}"
        return f"Saved spoken audio to {out}"

    return speak_text


GET_AUDIO_INFO_SCHEMA: dict[str, Any] = {
    "name": "get_audio_info",
    "description": (
        "Inspect a local audio file and return its metadata — format, file size, and "
        "(for WAV files) duration in seconds, sample rate in Hz, and channel count. "
        "No API key required. Useful before transcribing to check if a file is the "
        "right length, or to report audio properties to the user."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local audio file path (absolute, ~, or relative).",
            },
        },
        "required": ["path"],
    },
}


def _make_get_audio_info(gate: Any | None) -> Callable[[str], str]:
    def get_audio_info(path: str) -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: audio info is disabled in '{tier}' tier."

        target = _normalize_user_path(path)
        if gate is not None:
            check = gate.check_path(str(target), "read")
            if not getattr(check, "allowed", True):
                return f"Permission Denied: {getattr(check, 'reason', 'path not allowed')}"

        try:
            info = probe_audio_info(target)
        except VoiceError as exc:
            return f"Audio info failed: {exc}"
        except Exception as exc:
            return f"Audio info failed: {exc}"

        # Human-friendly summary + full JSON for programmatic use.
        lines = [f"Audio file: {info['file']}"]
        lines.append(f"Format: {info['format'].upper()}  |  Size: {info['size_bytes']:,} bytes")
        if info.get("probeable"):
            dur = info.get("duration_seconds", 0.0)
            sr = info.get("sample_rate", 0)
            ch = info.get("channels", 0)
            ch_label = {1: "mono", 2: "stereo"}.get(ch, f"{ch}-channel")
            lines.append(f"Duration: {dur:.3f}s  |  Sample rate: {sr:,} Hz  |  {ch_label}")
        else:
            lines.append(
                "Duration/sample-rate: not available "
                "(only WAV files are fully probed without an API key)"
            )
        lines.append("")
        lines.append(json.dumps(info, indent=2))
        return "\n".join(lines)

    return get_audio_info


PLAY_AUDIO_SCHEMA: dict[str, Any] = {
    "name": "play_audio",
    "description": (
        "Play a local audio file through the system's speakers. "
        "Uses the platform's built-in player — afplay on macOS, winsound (WAV) "
        "or mpv/ffplay on Windows, paplay/aplay/mpv on Linux. "
        "No API key required. Blocks until playback finishes. "
        "Most useful after speak_text to immediately hear the generated voice output."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local audio file path to play (absolute, ~, or relative).",
            },
        },
        "required": ["path"],
    },
}


def _make_play_audio(gate: Any | None, player: AudioPlayer | None) -> Callable[[str], str]:
    def play_audio(path: str) -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: audio playback is disabled in '{tier}' tier."

        target = _normalize_user_path(path)
        if gate is not None:
            check = gate.check_path(str(target), "read")
            if not getattr(check, "allowed", True):
                return f"Permission Denied: {getattr(check, 'reason', 'path not allowed')}"

        if not target.exists() or not target.is_file():
            return f"Audio file not found: {target}"

        active = player or AudioPlayer()
        if not active.is_available():
            return (
                "No audio player available on this system. "
                "Install paplay (Linux/PulseAudio), mpv, or ffplay and add it to PATH. "
                "macOS afplay is built-in; Windows WAV uses the stdlib winsound module."
            )

        try:
            returncode, stderr = active.play(target)
        except Exception as exc:  # never propagate
            return f"Playback failed: {exc}"

        if returncode != 0:
            detail = stderr.strip() or "(no details)"
            return f"Playback failed (exit {returncode}): {detail}"
        return f"Played: {target.name}"

    return play_audio


TRANSCRIBE_AND_SUMMARIZE_SCHEMA: dict[str, Any] = {
    "name": "transcribe_and_summarize",
    "description": (
        "Transcribe a local audio file and return both the full transcript and an "
        "extractive summary (the most information-dense sentences, re-ordered by "
        "original position). Useful for meeting recordings, voice notes, or any audio "
        "where you want the key points without reading the whole transcript. Includes "
        "word count and estimated reading time. Requires the same STT API key as "
        "transcribe_audio. Supports mp3, m4a, wav, webm, flac, ogg, and more."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local audio file path (absolute, ~, or relative).",
            },
            "top_sentences": {
                "type": "integer",
                "description": "Number of key sentences to extract for the summary (default 3).",
                "default": 3,
            },
        },
        "required": ["path"],
    },
}


def _make_transcribe_and_summarize(
    gate: Any | None, stt: SpeechToText | None
) -> Callable[..., str]:
    def transcribe_and_summarize(path: str, top_sentences: int = 3) -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: audio transcription is disabled in '{tier}' tier."

        target = _normalize_user_path(path)
        if gate is not None:
            check = gate.check_path(str(target), "read")
            if not getattr(check, "allowed", True):
                return f"Permission Denied: {getattr(check, 'reason', 'path not allowed')}"

        active = stt or SpeechToText.from_env()
        if not active.is_configured():
            return (
                "Speech-to-text is not configured. Set OPENAI_API_KEY (or "
                "HACHI_STT_API_KEY) — optionally HACHI_STT_BASE_URL / "
                "HACHI_STT_MODEL for a non-OpenAI Whisper endpoint — then try again."
            )
        try:
            transcript = active.transcribe(target)
        except VoiceError as exc:
            return f"Transcription failed: {exc}"
        except Exception as exc:  # never propagate
            return f"Transcription failed: {exc}"

        n = max(int(top_sentences), 1)
        stats = summarize_transcript(transcript, top_sentences=n)

        lines = [
            f"Transcript of {target.name} "
            f"({stats['word_count']} words, ~{stats['estimated_reading_seconds']}s to read):",
            "",
            "## Summary (key sentences)",
        ]
        if stats["key_sentences"]:
            for sent in stats["key_sentences"]:
                lines.append(f"- {sent}")
        else:
            lines.append("(transcript too short to summarize)")
        lines.append("")
        lines.append("## Full transcript")
        lines.append(transcript)
        return "\n".join(lines)

    return transcribe_and_summarize


def _resolve_stt_from_registry(provider_registry: Any | None) -> SpeechToText | None:
    """Resolve an STT backend from the ProviderRegistry, or ``None`` to fall back to env."""
    if provider_registry is None:
        return None
    try:
        from hachi.core.routing.capability import Capability

        speech = provider_registry.get_speech(Capability.SPEECH_TO_TEXT)
        if speech is None:
            return None
        # The OpenAICompatibleSpeechProvider wraps a SpeechToText; extract it.
        inner_stt = getattr(speech, "_stt", None)
        if isinstance(inner_stt, SpeechToText):
            return inner_stt
    except Exception:
        pass
    return None


def _resolve_tts_from_registry(provider_registry: Any | None) -> TextToSpeech | None:
    """Resolve a TTS backend from the ProviderRegistry, or ``None`` to fall back to env."""
    if provider_registry is None:
        return None
    try:
        from hachi.core.routing.capability import Capability

        speech = provider_registry.get_speech(Capability.TEXT_TO_SPEECH)
        if speech is None:
            return None
        inner_tts = getattr(speech, "_tts", None)
        if isinstance(inner_tts, TextToSpeech):
            return inner_tts
    except Exception:
        pass
    return None


def register_voice_tools(
    registry: Any,
    gate: Any | None = None,
    stt: SpeechToText | None = None,
    tts: TextToSpeech | None = None,
    player: AudioPlayer | None = None,
    *,
    provider_registry: Any | None = None,
) -> None:
    """Register the voice tools under the ``voice`` lazy tool group.

    When *provider_registry* is provided, STT/TTS backends are resolved via
    :meth:`~hachi.core.providers.registry.ProviderRegistry.get_speech`, gaining
    resilience and capability-routing for free.  Explicit *stt* / *tts* arguments
    take precedence (back-compat: existing callers that pre-build the backends are
    unchanged).  When neither is provided, the tools fall back to
    :meth:`~hachi.core.voice.SpeechToText.from_env` / ``TextToSpeech.from_env``
    at call time (today's behaviour — unchanged).

    Registers:
    - ``transcribe_audio``         — STT, requires an API key
    - ``transcribe_and_summarize`` — STT + extractive summary, requires an API key
    - ``speak_text``               — TTS, requires an API key
    - ``play_audio``               — keyless playback via platform-native binary
    - ``get_audio_info``           — keyless metadata probe (stdlib ``wave`` for WAV)
    """
    # Prefer explicit args; fall back to registry resolution.
    resolved_stt = stt or _resolve_stt_from_registry(provider_registry)
    resolved_tts = tts or _resolve_tts_from_registry(provider_registry)

    registry.register(
        TRANSCRIBE_AUDIO_SCHEMA,
        _make_transcribe_audio(gate, resolved_stt),
        group="voice",
    )
    registry.register(
        TRANSCRIBE_AND_SUMMARIZE_SCHEMA,
        _make_transcribe_and_summarize(gate, resolved_stt),
        group="voice",
    )
    registry.register(
        SPEAK_TEXT_SCHEMA,
        _make_speak_text(gate, resolved_tts),
        group="voice",
    )
    registry.register(
        PLAY_AUDIO_SCHEMA,
        _make_play_audio(gate, player),
        group="voice",
    )
    registry.register(
        GET_AUDIO_INFO_SCHEMA,
        _make_get_audio_info(gate),
        group="voice",
    )
