"""Speech provider contract and OpenAI-compatible adapter (Initiative F).

Design doc 19 §2-3.  ``SpeechProvider`` is the protocol for speech-to-text and
text-to-speech providers.  ``OpenAICompatibleSpeechProvider`` **wraps** the
existing :class:`~hachi.core.voice.SpeechToText` /
:class:`~hachi.core.voice.TextToSpeech` implementations — no rewrite — so
Deepgram, Groq, and any other OpenAI-compatible Whisper/TTS endpoint continues
to work via env config.

``ElevenLabsSpeechProvider`` is a TTS-only adapter for the ElevenLabs REST API
(``POST /v1/text-to-speech/{voice_id}``).  It follows the same resilient-call
pattern as :class:`OpenAICompatibleSpeechProvider`.

Use :func:`build_stt_provider` / :func:`build_tts_provider` to get the right
provider from a :class:`~hachi.core.settings.VoiceSettings` object without
knowing which backend is configured.

Calls are wrapped by :func:`~hachi.core.resilience.resilient_call` so
transcription and synthesis both gain timeout + bounded retry + circuit-breaker
for free without touching :mod:`~hachi.core.voice`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from hachi.core.resilience import HealthRecorder, RetryPolicy, resilient_call
from hachi.core.routing.capability import Capability

logger = logging.getLogger(__name__)


class OpenAICompatibleSpeechProvider:
    """Adapter that wraps :class:`~hachi.core.voice.SpeechToText` /
    :class:`~hachi.core.voice.TextToSpeech` under the :class:`SpeechProvider`
    protocol.

    This is the *only* class that may import from :mod:`hachi.core.voice` for
    the purpose of speech provider registration.  Keyless playback
    (:class:`~hachi.core.voice.AudioPlayer`) is not part of this adapter — it
    stays directly in the tool layer.

    Args:
        stt: Optional :class:`~hachi.core.voice.SpeechToText` instance.
            When ``None`` the provider advertises no STT capability.
        tts: Optional :class:`~hachi.core.voice.TextToSpeech` instance.
            When ``None`` the provider advertises no TTS capability.
        retry_policy: Retry/circuit-breaker policy for all calls.
            Defaults to the global :class:`~hachi.core.resilience.RetryPolicy`.
        provider_name: Registry key.  Defaults to ``"openai-compat-speech"``.
    """

    def __init__(
        self,
        *,
        stt: Any | None = None,
        tts: Any | None = None,
        retry_policy: RetryPolicy | None = None,
        provider_name: str = "openai-compat-speech",
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._policy = retry_policy or RetryPolicy()
        self._recorder = HealthRecorder(provider_name, self._policy)
        self.name = provider_name

    # ------------------------------------------------------------------
    # SpeechProvider protocol
    # ------------------------------------------------------------------

    def capabilities(self) -> set[Capability]:
        """Return capabilities based on which backends are configured."""
        caps: set[Capability] = set()
        if self._stt is not None and self._stt.is_configured():
            caps.add(Capability.SPEECH_TO_TEXT)
        if self._tts is not None and self._tts.is_configured():
            caps.add(Capability.TEXT_TO_SPEECH)
        return caps

    def transcribe(self, audio: bytes, **opts: Any) -> str:
        """Transcribe raw audio bytes to text via the STT backend.

        Wraps :meth:`~hachi.core.voice.SpeechToText.transcribe` with
        :func:`~hachi.core.resilience.resilient_call`.

        Args:
            audio: Raw audio bytes to transcribe.
            **opts: Unused; reserved for future ``media_type`` / ``language`` kwargs.

        Returns:
            The transcript string.

        Raises:
            RuntimeError: When no STT backend is configured.
            :class:`~hachi.core.voice.VoiceError`: On transcription failure.
        """
        if self._stt is None:
            raise RuntimeError("No STT backend configured on this SpeechProvider")

        import tempfile
        from pathlib import Path

        # SpeechToText.transcribe takes a file path; write bytes to a temp file.
        media_type: str = opts.get("media_type", "audio/wav")
        ext = _media_type_to_ext(media_type)
        _stt = self._stt  # narrowed local for closure

        def _call() -> str:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio)
                tmp_path = Path(tmp.name)
            try:
                result: str = str(_stt.transcribe(tmp_path))
                return result
            finally:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        result_str: str = resilient_call(_call, self._policy, self._recorder)
        return result_str

    def synthesize(self, text: str, **opts: Any) -> bytes:
        """Synthesize *text* to audio bytes via the TTS backend.

        Wraps :meth:`~hachi.core.voice.TextToSpeech.synthesize` with
        :func:`~hachi.core.resilience.resilient_call`.

        Args:
            text: The text to convert to speech.
            **opts: Accepted kwargs: ``voice`` (str), ``fmt`` (str, default ``"mp3"``).

        Returns:
            Raw audio bytes.

        Raises:
            RuntimeError: When no TTS backend is configured.
            :class:`~hachi.core.voice.VoiceError`: On synthesis failure.
        """
        if self._tts is None:
            raise RuntimeError("No TTS backend configured on this SpeechProvider")

        import tempfile
        from pathlib import Path

        voice: str | None = opts.get("voice")
        fmt: str = opts.get("fmt", "mp3")
        _tts = self._tts  # narrowed local for closure

        # NOTE: TextToSpeech.synthesize (core/voice.py) infers the output format
        # from the file extension of ``out_path`` via ``path.suffix.lstrip(".")``,
        # and passes it as ``response_format`` in the OpenAI API payload.
        # Using ``suffix=f".{fmt}"`` here therefore propagates the requested format
        # all the way to the provider so the returned bytes ARE encoded in the
        # requested format — no media_type mismatch occurs.
        def _call() -> bytes:
            with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                _tts.synthesize(text, tmp_path, voice=voice)
                return bytes(tmp_path.read_bytes())
            finally:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        result_bytes: bytes = resilient_call(_call, self._policy, self._recorder)
        return result_bytes

    # ------------------------------------------------------------------
    # Health (used by ProviderRegistry.health())
    # ------------------------------------------------------------------

    def health(self) -> Any:
        """Return health snapshot from the underlying HealthRecorder."""
        return self._recorder.snapshot()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        voice_cfg: Any | None = None,
        *,
        retry_policy: RetryPolicy | None = None,
    ) -> OpenAICompatibleSpeechProvider:
        """Build from a ``VoiceSettings`` object or plain dict.

        Precedence (matching established HACHI_* env-key pattern):
          1. ``voice_cfg`` fields (``stt_api_key``, ``stt_base_url``, etc.)
          2. ``HACHI_STT_*`` / ``HACHI_TTS_*`` env vars
          3. ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` fallback

        This matches exactly the logic inside
        :meth:`~hachi.core.voice.SpeechToText.from_env` and
        :meth:`~hachi.core.voice.TextToSpeech.from_env`, so the fallback is
        identical regardless of code path.

        Args:
            voice_cfg: A :class:`~hachi.core.settings.VoiceSettings` (or dict)
                from the ``[voice]`` config section, or ``None`` to fall back
                fully to env vars.
            retry_policy: Optional retry/circuit-breaker policy.

        Returns:
            A configured :class:`OpenAICompatibleSpeechProvider`.
        """
        from hachi.core.voice import SpeechToText, TextToSpeech

        cfg: dict[str, Any] = {}
        if voice_cfg is not None:
            if isinstance(voice_cfg, dict):
                cfg = voice_cfg
            else:
                try:
                    cfg = voice_cfg.model_dump()
                except AttributeError:
                    # Fallback for plain objects.
                    for attr in (
                        "stt_api_key",
                        "stt_base_url",
                        "stt_model",
                        "stt_api_key_env",
                        "tts_api_key",
                        "tts_base_url",
                        "tts_model",
                        "tts_voice",
                        "tts_api_key_env",
                    ):
                        val = getattr(voice_cfg, attr, None)
                        if val is not None:
                            cfg[attr] = val

        def _resolve_key(cfg_key: str, env_key: str, fallback_env: str) -> str | None:
            """Return value from config, then env_key, then fallback_env."""
            # Also handle api_key_env indirection: if cfg has stt_api_key_env, read that env.
            key_env_field = cfg_key.replace("_api_key", "_api_key_env")
            key_env_name = cfg.get(key_env_field)
            if key_env_name:
                val = os.environ.get(key_env_name)
                if val:
                    return val
            if cfg.get(cfg_key):
                return str(cfg[cfg_key])
            env_val = os.environ.get(env_key)
            if env_val:
                return env_val
            return os.environ.get(fallback_env)

        stt_api_key = _resolve_key("stt_api_key", "HACHI_STT_API_KEY", "OPENAI_API_KEY")
        stt_base_url = (
            cfg.get("stt_base_url")
            or os.environ.get("HACHI_STT_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
        )
        stt_model = cfg.get("stt_model") or os.environ.get("HACHI_STT_MODEL")

        tts_api_key = _resolve_key("tts_api_key", "HACHI_TTS_API_KEY", "OPENAI_API_KEY")
        tts_base_url = (
            cfg.get("tts_base_url")
            or os.environ.get("HACHI_TTS_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
        )
        tts_model = cfg.get("tts_model") or os.environ.get("HACHI_TTS_MODEL")
        tts_voice = cfg.get("tts_voice") or os.environ.get("HACHI_TTS_VOICE")

        stt = SpeechToText(
            api_key=stt_api_key,
            base_url=stt_base_url,
            model=stt_model,
        )
        tts = TextToSpeech(
            api_key=tts_api_key,
            base_url=tts_base_url,
            model=tts_model,
            voice=tts_voice,
        )

        return cls(stt=stt, tts=tts, retry_policy=retry_policy)


# ---------------------------------------------------------------------------
# ElevenLabs TTS-only provider
# ---------------------------------------------------------------------------

_ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
_ELEVENLABS_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" — always present
_ELEVENLABS_DEFAULT_MODEL = "eleven_turbo_v2_5"

# Shared httpx client for ElevenLabs — lazily created, reuses TCP/TLS connections.
# Never opened at import time; no eager sockets.
_el_shared_client: Any = None


def _get_el_http_client() -> Any:
    """Return (or create) the shared ElevenLabs httpx.Client."""
    import httpx

    global _el_shared_client  # noqa: PLW0603
    if _el_shared_client is None:
        _el_shared_client = httpx.Client(
            timeout=60.0,
            follow_redirects=False,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _el_shared_client


class ElevenLabsSpeechProvider:
    """TTS-only provider that calls the ElevenLabs ``/v1/text-to-speech`` API.

    Args:
        api_key: ElevenLabs API key.  When ``None`` the provider is considered
            not configured and :meth:`synthesize` raises :class:`RuntimeError`.
        voice_id: The ElevenLabs voice ID to use.  Defaults to "Rachel".
        retry_policy: Retry/circuit-breaker policy.
        provider_name: Registry key.  Defaults to ``"elevenlabs-speech"``.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice_id: str | None = None,
        model_id: str | None = None,
        retry_policy: RetryPolicy | None = None,
        provider_name: str = "elevenlabs-speech",
    ) -> None:
        self._api_key = api_key or None
        self._voice_id = voice_id or _ELEVENLABS_DEFAULT_VOICE
        self._model_id = model_id or _ELEVENLABS_DEFAULT_MODEL
        self._policy = retry_policy or RetryPolicy()
        self._recorder = HealthRecorder(provider_name, self._policy)
        self.name = provider_name

    # ------------------------------------------------------------------
    # SpeechProvider protocol
    # ------------------------------------------------------------------

    def capabilities(self) -> set[Capability]:
        """Return TTS capability when an API key is configured."""
        if self._api_key:
            return {Capability.TEXT_TO_SPEECH}
        return set()

    def transcribe(self, audio: bytes, **opts: Any) -> str:
        """Not implemented — ElevenLabs is TTS-only.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ElevenLabsSpeechProvider does not support transcription")

    def synthesize(self, text: str, *, voice: str | None = None, fmt: str = "mp3") -> bytes:
        """Synthesize *text* to audio bytes via the ElevenLabs TTS API.

        Args:
            text: The text to convert to speech.
            voice: ElevenLabs voice ID override.  Falls back to the configured
                ``voice_id``.
            fmt: Output format — one of ``"mp3"`` (default), ``"pcm"``  or
                ``"ulaw"``.  ElevenLabs uses ``mp3_44100_128`` internally; we
                normalise the common aliases here.

        Returns:
            Raw audio bytes in the requested format.

        Raises:
            RuntimeError: When no API key is configured.
        """
        if not self._api_key:
            raise RuntimeError(
                "ElevenLabs TTS is not configured — set elevenlabs_api_key_env "
                "in [voice] or HACHI_TTS_API_KEY in the environment"
            )

        resolved_voice = voice or self._voice_id
        api_key = self._api_key  # local for closure capture
        model_id = self._model_id  # local for closure capture

        # Map common format names to ElevenLabs output_format values.
        _fmt_map = {
            "mp3": "mp3_44100_128",
            "mp3_44100_128": "mp3_44100_128",
            "pcm": "pcm_44100",
            "pcm_44100": "pcm_44100",
            "ulaw": "ulaw_8000",
        }
        el_fmt = _fmt_map.get(fmt.lower(), "mp3_44100_128")

        def _call() -> bytes:
            url = f"{_ELEVENLABS_API_BASE}/text-to-speech/{resolved_voice}"
            payload = {
                "text": text,
                "model_id": model_id,
                "output_format": el_fmt,
            }
            headers = {
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            }
            client = _get_el_http_client()
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                detail = resp.text[:200] if resp.text else ""
                raise RuntimeError(f"ElevenLabs TTS returned HTTP {resp.status_code}: {detail}")
            if not resp.content:
                raise RuntimeError("ElevenLabs TTS returned no audio")
            return bytes(resp.content)

        return resilient_call(_call, self._policy, self._recorder)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> Any:
        """Return health snapshot from the underlying HealthRecorder."""
        return self._recorder.snapshot()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        voice_cfg: Any | None = None,
        *,
        retry_policy: RetryPolicy | None = None,
    ) -> ElevenLabsSpeechProvider:
        """Build from a :class:`~hachi.core.settings.VoiceSettings` object.

        Precedence for the API key:
          1. ``voice_cfg.elevenlabs_api_key_env`` → read that env var
          2. ``HACHI_TTS_API_KEY``
          3. ``ELEVENLABS_API_KEY``

        The voice ID comes from ``voice_cfg.elevenlabs_voice_id`` or
        ``HACHI_ELEVENLABS_VOICE_ID``.

        Args:
            voice_cfg: A :class:`~hachi.core.settings.VoiceSettings` (or dict),
                or ``None`` to fall back fully to env vars.
            retry_policy: Optional retry/circuit-breaker policy.

        Returns:
            A configured :class:`ElevenLabsSpeechProvider`.
        """
        cfg: dict[str, Any] = {}
        if voice_cfg is not None:
            if isinstance(voice_cfg, dict):
                cfg = voice_cfg
            else:
                try:
                    cfg = voice_cfg.model_dump()
                except AttributeError:
                    for attr in ("elevenlabs_api_key_env", "elevenlabs_voice_id",
                                 "elevenlabs_model"):
                        val = getattr(voice_cfg, attr, None)
                        if val is not None:
                            cfg[attr] = val

        # Resolve API key via indirection env var, then direct env fallbacks.
        key_env_name: str | None = cfg.get("elevenlabs_api_key_env")
        api_key: str | None = None
        if key_env_name:
            api_key = os.environ.get(key_env_name)
        if not api_key:
            api_key = os.environ.get("HACHI_TTS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY")

        voice_id: str | None = cfg.get("elevenlabs_voice_id") or os.environ.get(
            "HACHI_ELEVENLABS_VOICE_ID"
        )
        # Model: read from config field (contract C-VOICECFG), fallback to default.
        model_id: str | None = (
            cfg.get("elevenlabs_model")
            or getattr(voice_cfg, "elevenlabs_model", None)
            or os.environ.get("HACHI_ELEVENLABS_MODEL")
        )

        return cls(api_key=api_key, voice_id=voice_id, model_id=model_id, retry_policy=retry_policy)


# ---------------------------------------------------------------------------
# Provider factory helpers
# ---------------------------------------------------------------------------


def build_stt_provider(
    voice_cfg: Any | None = None,
    *,
    retry_policy: RetryPolicy | None = None,
) -> OpenAICompatibleSpeechProvider:
    """Return the configured STT provider (currently always OpenAI-compatible).

    Args:
        voice_cfg: A :class:`~hachi.core.settings.VoiceSettings` or ``None``.
        retry_policy: Optional retry/circuit-breaker policy.

    Returns:
        A :class:`OpenAICompatibleSpeechProvider` wired for STT only.
    """
    # STT is always OpenAI-compatible (Whisper).  Build STT side only; TTS=None
    # keeps capabilities() from advertising TTS on this instance.
    from hachi.core.voice import SpeechToText

    cfg: dict[str, Any] = {}
    if voice_cfg is not None:
        if isinstance(voice_cfg, dict):
            cfg = voice_cfg
        else:
            try:
                cfg = voice_cfg.model_dump()
            except AttributeError:
                for attr in ("stt_api_key", "stt_base_url", "stt_model", "stt_api_key_env"):
                    val = getattr(voice_cfg, attr, None)
                    if val is not None:
                        cfg[attr] = val

    def _resolve_key(cfg_key: str, env_key: str, fallback_env: str) -> str | None:
        key_env_field = cfg_key.replace("_api_key", "_api_key_env")
        key_env_name = cfg.get(key_env_field)
        if key_env_name:
            val = os.environ.get(key_env_name)
            if val:
                return val
        if cfg.get(cfg_key):
            return str(cfg[cfg_key])
        env_val = os.environ.get(env_key)
        if env_val:
            return env_val
        return os.environ.get(fallback_env)

    stt_api_key = _resolve_key("stt_api_key", "HACHI_STT_API_KEY", "OPENAI_API_KEY")
    stt_base_url = (
        cfg.get("stt_base_url")
        or os.environ.get("HACHI_STT_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
    )
    stt_model = cfg.get("stt_model") or os.environ.get("HACHI_STT_MODEL")
    stt = SpeechToText(api_key=stt_api_key, base_url=stt_base_url, model=stt_model)
    return OpenAICompatibleSpeechProvider(stt=stt, tts=None, retry_policy=retry_policy)


def build_tts_provider(
    voice_cfg: Any | None = None,
    *,
    retry_policy: RetryPolicy | None = None,
) -> OpenAICompatibleSpeechProvider | ElevenLabsSpeechProvider:
    """Return the configured TTS provider (OpenAI or ElevenLabs).

    Selects the backend from ``voice_cfg.tts_provider`` (defaulting to
    ``"openai"`` when absent).

    Args:
        voice_cfg: A :class:`~hachi.core.settings.VoiceSettings` or ``None``.
        retry_policy: Optional retry/circuit-breaker policy.

    Returns:
        Either an :class:`OpenAICompatibleSpeechProvider` or an
        :class:`ElevenLabsSpeechProvider` configured for TTS.
    """
    tts_provider_name: str = "openai"
    if voice_cfg is not None:
        try:
            tts_provider_name = str(voice_cfg.tts_provider or "openai")
        except AttributeError:
            if isinstance(voice_cfg, dict):
                tts_provider_name = str(voice_cfg.get("tts_provider", "openai"))

    if tts_provider_name == "elevenlabs":
        return ElevenLabsSpeechProvider.from_config(voice_cfg, retry_policy=retry_policy)

    # Default: OpenAI-compatible TTS.  Build TTS side only; STT=None so
    # capabilities() does not advertise STT on this TTS-only instance.
    from hachi.core.voice import TextToSpeech

    cfg: dict[str, Any] = {}
    if voice_cfg is not None:
        if isinstance(voice_cfg, dict):
            cfg = voice_cfg
        else:
            try:
                cfg = voice_cfg.model_dump()
            except AttributeError:
                for attr in (
                    "tts_api_key",
                    "tts_base_url",
                    "tts_model",
                    "tts_voice",
                    "tts_api_key_env",
                ):
                    val = getattr(voice_cfg, attr, None)
                    if val is not None:
                        cfg[attr] = val

    def _resolve_key(cfg_key: str, env_key: str, fallback_env: str) -> str | None:
        key_env_field = cfg_key.replace("_api_key", "_api_key_env")
        key_env_name = cfg.get(key_env_field)
        if key_env_name:
            val = os.environ.get(key_env_name)
            if val:
                return val
        if cfg.get(cfg_key):
            return str(cfg[cfg_key])
        env_val = os.environ.get(env_key)
        if env_val:
            return env_val
        return os.environ.get(fallback_env)

    tts_api_key = _resolve_key("tts_api_key", "HACHI_TTS_API_KEY", "OPENAI_API_KEY")
    tts_base_url = (
        cfg.get("tts_base_url")
        or os.environ.get("HACHI_TTS_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
    )
    tts_model = cfg.get("tts_model") or os.environ.get("HACHI_TTS_MODEL")
    tts_voice = cfg.get("tts_voice") or os.environ.get("HACHI_TTS_VOICE")
    tts = TextToSpeech(api_key=tts_api_key, base_url=tts_base_url, model=tts_model, voice=tts_voice)
    return OpenAICompatibleSpeechProvider(stt=None, tts=tts, retry_policy=retry_policy)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _media_type_to_ext(media_type: str) -> str:
    """Map a MIME media type to a file extension for temp files."""
    _map = {
        "audio/wav": ".wav",
        "audio/wave": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/m4a": ".m4a",
        "audio/webm": ".webm",
        "audio/flac": ".flac",
        "audio/ogg": ".ogg",
    }
    return _map.get(media_type.lower(), ".wav")
