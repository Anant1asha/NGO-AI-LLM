"""Tests for the voice gateway endpoints.

All tests run fully offline: speech providers are mocked via monkeypatching so no
real API calls are made.  The ElevenLabs provider is verified by intercepting the
httpx.Client call via monkeypatching.

Coverage:
  - transcribe(): returns text, raises VoiceConfigError when unconfigured
  - speak():      returns bytes + media_type, respects format parameter
  - voice_config(): reports stt_provider / tts_provider / configured flag
  - set_voice_config(): round-trips config through write_global_config
  - ElevenLabsSpeechProvider.from_config(): builds from env + synthesize() call
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_stt_provider(transcript: str = "hello world") -> MagicMock:
    """Return a mock STT provider whose transcribe() returns *transcript*."""
    provider = MagicMock()
    provider.transcribe.return_value = transcript
    return provider


def _make_fake_tts_provider(audio: bytes = b"AUDIO") -> MagicMock:
    """Return a mock TTS provider whose synthesize() returns *audio*."""
    provider = MagicMock()
    provider.synthesize.return_value = audio
    return provider


# ---------------------------------------------------------------------------
# transcribe()
# ---------------------------------------------------------------------------


def test_transcribe_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """transcribe() should delegate to the STT provider and return text."""
    from hachi.gateway import voice_endpoints

    fake_provider = _make_fake_stt_provider("the quick brown fox")

    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: True)

    with patch("hachi.gateway.voice_endpoints.build_stt_provider", return_value=fake_provider):
        result = voice_endpoints.transcribe(
            b"\x00\x01\x02",
            filename="audio.wav",
            content_type="audio/wav",
        )

    assert result["text"] == "the quick brown fox"
    fake_provider.transcribe.assert_called_once()


def test_transcribe_raises_voice_config_error_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """transcribe() must raise VoiceConfigError when STT is not configured."""
    from hachi.gateway import voice_endpoints

    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: False)

    with pytest.raises(voice_endpoints.VoiceConfigError, match="not configured"):
        voice_endpoints.transcribe(
            b"\x00",
            filename="test.wav",
            content_type="audio/wav",
        )


def test_transcribe_passes_language_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """transcribe() should include the language hint in its return dict."""
    from hachi.gateway import voice_endpoints

    fake_provider = _make_fake_stt_provider("bonjour")
    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: True)

    with patch("hachi.gateway.voice_endpoints.build_stt_provider", return_value=fake_provider):
        result = voice_endpoints.transcribe(
            b"\x00",
            filename="audio.webm",
            content_type="audio/webm",
            language="fr",
        )

    assert result["text"] == "bonjour"
    assert result.get("language") == "fr"


# ---------------------------------------------------------------------------
# speak()
# ---------------------------------------------------------------------------


def test_speak_returns_bytes_and_media_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """speak() should return (bytes, media_type) from the TTS provider."""
    from hachi.gateway import voice_endpoints

    fake_provider = _make_fake_tts_provider(b"MP3DATA")
    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: True)

    with patch("hachi.gateway.voice_endpoints.build_tts_provider", return_value=fake_provider):
        audio, media_type = voice_endpoints.speak("hello hachi")

    assert audio == b"MP3DATA"
    assert "audio" in media_type
    fake_provider.synthesize.assert_called_once()


def test_speak_wav_format_returns_wav_mime(monkeypatch: pytest.MonkeyPatch) -> None:
    """speak() should return audio/wav media_type for fmt='wav'."""
    from hachi.gateway import voice_endpoints

    fake_provider = _make_fake_tts_provider(b"WAVDATA")
    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: True)

    with patch("hachi.gateway.voice_endpoints.build_tts_provider", return_value=fake_provider):
        audio, media_type = voice_endpoints.speak("test", fmt="wav")

    assert audio == b"WAVDATA"
    assert media_type == "audio/wav"


def test_speak_raises_voice_config_error_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """speak() must raise VoiceConfigError when TTS is not configured."""
    from hachi.gateway import voice_endpoints

    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: False)

    with pytest.raises(voice_endpoints.VoiceConfigError, match="not configured"):
        voice_endpoints.speak("anything")


# ---------------------------------------------------------------------------
# voice_config()
# ---------------------------------------------------------------------------


def test_voice_config_reports_defaults_when_no_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """voice_config() should return sane defaults when no [voice] section exists."""
    from hachi.gateway import voice_endpoints

    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: False)

    cfg = voice_endpoints.voice_config()

    assert cfg["stt_provider"] == "openai"
    assert cfg["tts_provider"] == "openai"
    assert "configured" in cfg
    assert cfg["configured"] is False
    assert "available" in cfg
    assert "tts_providers" in cfg["available"]
    assert "voices" in cfg["available"]


def test_voice_config_reports_configured_true_when_key_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """voice_config() should report configured=True when a key resolves."""
    from hachi.gateway import voice_endpoints

    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: None)
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: True)

    cfg = voice_endpoints.voice_config()
    assert cfg["configured"] is True


def test_voice_config_reads_elevenlabs_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """voice_config() should surface elevenlabs fields from VoiceSettings."""
    from hachi.gateway import voice_endpoints

    class _FakeCfg:
        stt_provider = "openai"
        tts_provider = "elevenlabs"
        tts_voice = None
        stt_model = None
        tts_model = None
        elevenlabs_voice_id = "some_voice"
        elevenlabs_api_key_env = "MY_EL_KEY"

    monkeypatch.setattr(voice_endpoints, "_load_voice_cfg", lambda: _FakeCfg())
    monkeypatch.setattr(voice_endpoints, "_is_voice_configured", lambda _cfg: True)

    cfg = voice_endpoints.voice_config()

    assert cfg["tts_provider"] == "elevenlabs"
    assert cfg["elevenlabs_voice_id"] == "some_voice"
    assert cfg["configured"] is True


# ---------------------------------------------------------------------------
# ElevenLabsSpeechProvider
# ---------------------------------------------------------------------------


def test_elevenlabs_provider_from_config_resolves_env_key() -> None:
    """ElevenLabsSpeechProvider.from_config() should read the API key via env."""
    from hachi.core.providers.speech import ElevenLabsSpeechProvider

    class _Cfg:
        elevenlabs_api_key_env = "MY_EL_KEY"
        elevenlabs_voice_id = "abc123"

    with patch.dict(os.environ, {"MY_EL_KEY": "sk-fake-el-key"}, clear=False):
        provider = ElevenLabsSpeechProvider.from_config(_Cfg())

    assert provider._api_key == "sk-fake-el-key"
    assert provider._voice_id == "abc123"


def test_elevenlabs_provider_transcribe_raises_not_implemented() -> None:
    """ElevenLabsSpeechProvider.transcribe() must raise NotImplementedError."""
    from hachi.core.providers.speech import ElevenLabsSpeechProvider

    provider = ElevenLabsSpeechProvider(api_key="sk-test")
    with pytest.raises(NotImplementedError):
        provider.transcribe(b"\x00")


def test_elevenlabs_provider_synthesize_hits_correct_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ElevenLabsSpeechProvider.synthesize() should POST to the ElevenLabs endpoint."""
    from hachi.core.providers.speech import ElevenLabsSpeechProvider

    captured: dict[str, Any] = {}

    class _FakeResponse:
        status_code = 200
        content = b"EL_AUDIO"
        text = ""

    class _FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def post(self, url: str, *, json: Any, headers: Any) -> _FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr("httpx.Client", _FakeClient)

    provider = ElevenLabsSpeechProvider(api_key="sk-el-test", voice_id="myvoice")
    audio = provider.synthesize("Hello world")

    assert audio == b"EL_AUDIO"
    assert "xi-api-key" in captured.get("headers", {})
    assert captured["headers"]["xi-api-key"] == "sk-el-test"
    assert "myvoice" in captured.get("url", "")


def test_elevenlabs_provider_no_key_raises_runtime_error() -> None:
    """ElevenLabsSpeechProvider.synthesize() must raise RuntimeError when no key."""
    from hachi.core.providers.speech import ElevenLabsSpeechProvider

    provider = ElevenLabsSpeechProvider(api_key=None)
    with pytest.raises(RuntimeError, match="not configured"):
        provider.synthesize("hello")


# ---------------------------------------------------------------------------
# build_stt_provider / build_tts_provider factories
# ---------------------------------------------------------------------------


def test_build_stt_provider_returns_openai_compat() -> None:
    """build_stt_provider() should always return an OpenAICompatibleSpeechProvider."""
    from hachi.core.providers.speech import OpenAICompatibleSpeechProvider, build_stt_provider

    provider = build_stt_provider(None)
    assert isinstance(provider, OpenAICompatibleSpeechProvider)


def test_build_tts_provider_openai_returns_openai_compat() -> None:
    """build_tts_provider() with tts_provider='openai' returns OpenAICompatibleSpeechProvider."""
    from hachi.core.providers.speech import OpenAICompatibleSpeechProvider, build_tts_provider

    class _Cfg:
        tts_provider = "openai"
        tts_api_key_env = None
        tts_base_url = None
        tts_model = None
        tts_voice = None

    provider = build_tts_provider(_Cfg())
    assert isinstance(provider, OpenAICompatibleSpeechProvider)


# ---------------------------------------------------------------------------
# Gateway route — streaming headers (B1)
# ---------------------------------------------------------------------------


def test_voice_speak_route_carries_proxy_buffering_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /voice/speak StreamingResponse must disable proxy buffering (B1)."""
    from fastapi.testclient import TestClient

    from hachi.gateway import voice_endpoints
    from hachi.gateway.control_plane import GatewayControlPlane
    from hachi.gateway.fastapi_app import create_gateway_app

    # Patch speak_stream before app creation so the lazy import inside
    # create_gateway_app picks up the stub.
    def _fake_speak_stream(text: str, **_kwargs: Any) -> tuple[Any, str]:
        def _gen():  # type: ignore[return]
            yield b"AUDIO"

        return _gen(), "audio/mpeg"

    monkeypatch.setattr(voice_endpoints, "speak_stream", _fake_speak_stream)

    cp = GatewayControlPlane()
    app = create_gateway_app(cp)
    with TestClient(app) as client:
        resp = client.post("/voice/speak", json={"text": "hello hachi"})

    assert resp.status_code == 200
    assert resp.headers.get("x-accel-buffering") == "no"
    assert resp.headers.get("cache-control") == "no-cache"


def test_build_tts_provider_elevenlabs_returns_elevenlabs() -> None:
    """build_tts_provider() with tts_provider='elevenlabs' returns ElevenLabsSpeechProvider."""
    from hachi.core.providers.speech import ElevenLabsSpeechProvider, build_tts_provider

    class _Cfg:
        tts_provider = "elevenlabs"
        elevenlabs_api_key_env = None
        elevenlabs_voice_id = None

        def model_dump(self) -> dict[str, Any]:
            return {
                "tts_provider": "elevenlabs",
                "elevenlabs_api_key_env": None,
                "elevenlabs_voice_id": None,
            }

    provider = build_tts_provider(_Cfg())
    assert isinstance(provider, ElevenLabsSpeechProvider)
