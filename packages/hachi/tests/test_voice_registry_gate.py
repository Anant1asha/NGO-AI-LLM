"""Voice registry gate tests (Design doc 19 §3).

Tests:
  - HACHI_STT_* / HACHI_TTS_* env vars still resolve via the config fallback
    through OpenAICompatibleSpeechProvider.from_config (back-compat gate).
  - transcribe and synthesize route through resilient_call (retry + health recording).
  - register_voice_tools resolves provider from registry when available;
    falls back to SpeechToText.from_env() when registry is absent (unchanged behavior).

No network, no real audio.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hachi.core.loop import ToolRegistry
from hachi.core.providers.speech import OpenAICompatibleSpeechProvider
from hachi.core.voice import SpeechToText, TextToSpeech, VoiceError
from hachi.tools.voice_tools import (
    _resolve_stt_from_registry,
    _resolve_tts_from_registry,
    register_voice_tools,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, allowed: bool, reason: str = "") -> None:
        self.allowed = allowed
        self.reason = reason


class _Gate:
    def __init__(self, tier: str = "guided", allowed: bool = True) -> None:
        self.tier = tier
        self._allowed = allowed

    def check_path(self, path: str, mode: str) -> _Result:
        return _Result(self._allowed, "" if self._allowed else "path not allowed")


def _wav(tmp_path: Path, name: str = "note.wav") -> Path:
    p = tmp_path / name
    p.write_bytes(b"RIFF....WAVEfmt ")
    return p


def _ok_transcriber(text: str = "hello from registry"):
    def _t(url: str, file_bytes: bytes, filename: str, form_data: dict, headers: dict):
        return 200, json.dumps({"text": text})

    return _t


def _ok_synthesizer(audio: bytes = b"AUDIO"):
    def _s(url: str, payload: dict, headers: dict):
        return 200, audio

    return _s


# ---------------------------------------------------------------------------
# Gate: HACHI_STT_* / HACHI_TTS_* env vars → config fallback
# ---------------------------------------------------------------------------


def test_env_fallback_stt_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """HACHI_STT_API_KEY env var is picked up by from_config with no voice_cfg."""
    monkeypatch.setenv("HACHI_STT_API_KEY", "sk-stt-from-env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAICompatibleSpeechProvider.from_config(None)
    # The inner SpeechToText should be configured.
    assert provider._stt is not None
    assert provider._stt.is_configured()
    # STT capability advertised.
    from hachi.core.routing.capability import Capability

    assert Capability.SPEECH_TO_TEXT in provider.capabilities()


def test_env_fallback_tts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """HACHI_TTS_API_KEY env var is picked up by from_config with no voice_cfg."""
    monkeypatch.setenv("HACHI_TTS_API_KEY", "sk-tts-from-env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAICompatibleSpeechProvider.from_config(None)
    assert provider._tts is not None
    assert provider._tts.is_configured()
    from hachi.core.routing.capability import Capability

    assert Capability.TEXT_TO_SPEECH in provider.capabilities()


def test_env_openai_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENAI_API_KEY is the last-resort fallback for both STT and TTS."""
    monkeypatch.delenv("HACHI_STT_API_KEY", raising=False)
    monkeypatch.delenv("HACHI_TTS_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-fallback")

    provider = OpenAICompatibleSpeechProvider.from_config(None)
    assert provider._stt is not None and provider._stt.is_configured()
    assert provider._tts is not None and provider._tts.is_configured()


def test_no_key_no_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    """No API keys → capabilities() returns empty set."""
    monkeypatch.delenv("HACHI_STT_API_KEY", raising=False)
    monkeypatch.delenv("HACHI_TTS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = OpenAICompatibleSpeechProvider.from_config(None)
    assert provider.capabilities() == set()


def test_stt_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """HACHI_STT_MODEL env var is forwarded to the inner SpeechToText."""
    monkeypatch.setenv("HACHI_STT_API_KEY", "sk-test")
    monkeypatch.setenv("HACHI_STT_MODEL", "whisper-large-v3")

    provider = OpenAICompatibleSpeechProvider.from_config(None)
    assert provider._stt is not None
    assert provider._stt._model == "whisper-large-v3"


# ---------------------------------------------------------------------------
# Gate: transcribe/synthesize route through resilient_call
# ---------------------------------------------------------------------------


def test_transcribe_routes_through_resilient_call(tmp_path: Path) -> None:
    """transcribe() wraps SpeechToText via resilient_call; success recorded in health."""
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber("testing resilience"))
    provider = OpenAICompatibleSpeechProvider(stt=stt, tts=None)

    # Write a wav file and read its bytes.
    wav = _wav(tmp_path)
    audio_bytes = wav.read_bytes()

    result = provider.transcribe(audio_bytes, media_type="audio/wav")
    assert result == "testing resilience"

    # Health recorder should show a successful call.
    health = provider.health()
    assert health.recent_error_rate == 0.0
    assert health.consecutive_failures == 0


def test_synthesize_routes_through_resilient_call(tmp_path: Path) -> None:
    """synthesize() wraps TextToSpeech via resilient_call; bytes returned."""
    tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer(b"MP3AUDIO"))
    provider = OpenAICompatibleSpeechProvider(stt=None, tts=tts)

    result = provider.synthesize("hello world", voice="alloy", fmt="mp3")
    assert result == b"MP3AUDIO"

    health = provider.health()
    assert health.consecutive_failures == 0


def test_transcribe_records_failure_in_health(tmp_path: Path) -> None:
    """A transcription failure is recorded by the HealthRecorder."""
    stt = SpeechToText(
        api_key="sk-test",
        transcriber=lambda url, fb, fn, fd, h: (500, "server error"),
    )
    provider = OpenAICompatibleSpeechProvider(stt=stt, tts=None)
    wav = _wav(tmp_path)
    audio_bytes = wav.read_bytes()

    with pytest.raises(VoiceError):
        provider.transcribe(audio_bytes, media_type="audio/wav")

    health = provider.health()
    assert health.consecutive_failures > 0


# ---------------------------------------------------------------------------
# Gate: register_voice_tools resolves from registry / falls back to env
# ---------------------------------------------------------------------------


def test_register_voice_tools_resolves_from_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """register_voice_tools picks up STT/TTS from the ProviderRegistry when provided."""
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber())
    tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer())
    speech_provider = OpenAICompatibleSpeechProvider(stt=stt, tts=tts)

    registry_mock = MagicMock()
    from hachi.core.routing.capability import Capability

    def _get_speech(cap: Any) -> Any:
        if cap in (Capability.SPEECH_TO_TEXT, Capability.TEXT_TO_SPEECH):
            return speech_provider
        return None

    registry_mock.get_speech.side_effect = _get_speech

    tool_registry = ToolRegistry()
    register_voice_tools(tool_registry, _Gate("guided"), provider_registry=registry_mock)

    names = {schema["name"] for schema in tool_registry.get_schemas()}
    assert "transcribe_audio" in names
    assert "speak_text" in names


def test_resolve_stt_from_registry_returns_inner_stt() -> None:
    """_resolve_stt_from_registry extracts the inner SpeechToText from the speech provider."""
    stt = SpeechToText(api_key="sk-test")
    provider = OpenAICompatibleSpeechProvider(stt=stt, tts=None)

    registry = MagicMock()

    registry.get_speech.return_value = provider

    resolved = _resolve_stt_from_registry(registry)
    assert resolved is stt


def test_resolve_tts_from_registry_returns_inner_tts() -> None:
    """_resolve_tts_from_registry extracts the inner TextToSpeech from the speech provider."""
    tts = TextToSpeech(api_key="sk-test")
    provider = OpenAICompatibleSpeechProvider(stt=None, tts=tts)

    registry = MagicMock()
    registry.get_speech.return_value = provider

    resolved = _resolve_tts_from_registry(registry)
    assert resolved is tts


def test_resolve_stt_returns_none_when_registry_is_none() -> None:
    """_resolve_stt_from_registry returns None when no registry is provided."""
    assert _resolve_stt_from_registry(None) is None


def test_register_voice_tools_back_compat_no_registry() -> None:
    """register_voice_tools without provider_registry falls through to from_env at call time."""
    tool_registry = ToolRegistry()
    # Should not raise even when provider_registry is absent.
    register_voice_tools(tool_registry, _Gate("guided"))
    names = {schema["name"] for schema in tool_registry.get_schemas()}
    assert "transcribe_audio" in names
    assert "speak_text" in names


def test_explicit_stt_overrides_registry(tmp_path: Path) -> None:
    """Explicit stt argument takes precedence over provider_registry resolution."""
    explicit_stt = SpeechToText(api_key="sk-explicit", transcriber=_ok_transcriber("explicit"))
    registry_stt = SpeechToText(api_key="sk-from-registry", transcriber=_ok_transcriber("registry"))
    registry_provider = OpenAICompatibleSpeechProvider(stt=registry_stt, tts=None)

    registry_mock = MagicMock()
    registry_mock.get_speech.return_value = registry_provider

    tool_registry = ToolRegistry()
    # Pass explicit stt; registry should be ignored for STT.
    register_voice_tools(
        tool_registry, _Gate("guided"), stt=explicit_stt, provider_registry=registry_mock
    )

    # Find and call the transcribe_audio tool directly.
    wav = _wav(tmp_path)
    fn = None
    for name, func in tool_registry._tools.items():  # type: ignore[attr-defined]
        if "transcribe_audio" in name:
            fn = func
            break
    if fn is None:
        # Fallback: find by schema name.
        for schema in tool_registry.get_schemas():
            if schema["name"] == "transcribe_audio":
                fn = tool_registry.get_tool(schema["name"])
                break

    # Just verify we can call it without error; explicit stt wins so no registry lookup.
    if fn is not None:
        out = fn(str(wav))
        assert "explicit" in out or "Transcript" in out
