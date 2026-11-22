"""Tests for voice pipeline fixes (P1, P4, P6, cost tracking).

All tests run fully offline: no real HTTP calls, no real audio files.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import (
    MagicMock,
    patch,
)

# ---------------------------------------------------------------------------
# FIX P4 — shared httpx.Client reuse across calls (voice.py)
# ---------------------------------------------------------------------------


def test_shared_http_client_created_once() -> None:
    """The module-level shared httpx client must be constructed only once across
    multiple calls (TCP connection reuse).  We verify by resetting the singleton
    and counting how many distinct object identities are returned."""
    import hachi.core.voice as voice_mod

    # Reset the module-level singleton so we start from a clean state.
    original = voice_mod._shared_http_client  # type: ignore[attr-defined]
    voice_mod._shared_http_client = None  # type: ignore[attr-defined]

    try:
        # Patch httpx.Client at the source so the lazy import inside
        # _get_shared_http_client() gets our fake.
        with patch("httpx.Client") as mock_client_cls, patch("httpx.Limits"):
            fake_instance = MagicMock()
            mock_client_cls.return_value = fake_instance

            c1 = voice_mod._get_shared_http_client()
            c2 = voice_mod._get_shared_http_client()
            c3 = voice_mod._get_shared_http_client()

        assert c1 is c2 is c3, "Expected the same client instance on every call"
        assert mock_client_cls.call_count == 1, (
            f"httpx.Client constructed {mock_client_cls.call_count} times; expected 1"
        )
    finally:
        # Restore previous singleton.
        voice_mod._shared_http_client = original  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# FIX P4 — ElevenLabs shared client (speech.py)
# ---------------------------------------------------------------------------


def test_elevenlabs_shared_http_client_reused() -> None:
    """ElevenLabs provider reuses the module-level client across calls."""
    import hachi.core.providers.speech as speech_mod

    original = speech_mod._el_shared_client  # type: ignore[attr-defined]
    speech_mod._el_shared_client = None  # type: ignore[attr-defined]

    try:
        with patch("httpx.Client") as mock_client_cls, patch("httpx.Limits"):
            fake_instance = MagicMock()
            mock_client_cls.return_value = fake_instance

            c1 = speech_mod._get_el_http_client()
            c2 = speech_mod._get_el_http_client()
            c3 = speech_mod._get_el_http_client()

        assert c1 is c2 is c3
        assert mock_client_cls.call_count == 1
    finally:
        speech_mod._el_shared_client = original  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# FIX P6 — ElevenLabs model from config (speech.py)
# ---------------------------------------------------------------------------


def test_elevenlabs_model_from_config() -> None:
    """ElevenLabs provider reads model_id from config (contract C-VOICECFG)."""
    from hachi.core.providers.speech import ElevenLabsSpeechProvider

    provider = ElevenLabsSpeechProvider(api_key="fake-key", model_id="eleven_turbo_v2_5")
    assert provider._model_id == "eleven_turbo_v2_5"


def test_elevenlabs_model_default() -> None:
    """When model_id is omitted, the default is eleven_turbo_v2_5."""
    from hachi.core.providers.speech import _ELEVENLABS_DEFAULT_MODEL, ElevenLabsSpeechProvider

    provider = ElevenLabsSpeechProvider(api_key="fake-key")
    assert provider._model_id == _ELEVENLABS_DEFAULT_MODEL
    assert _ELEVENLABS_DEFAULT_MODEL == "eleven_turbo_v2_5"


def test_elevenlabs_model_sent_in_payload() -> None:
    """synthesize() must include the configured model_id in the ElevenLabs payload."""
    import hachi.core.providers.speech as speech_mod

    speech_mod._el_shared_client = None  # type: ignore[attr-defined]

    from hachi.core.providers.speech import ElevenLabsSpeechProvider

    provider = ElevenLabsSpeechProvider(api_key="fake-key", model_id="eleven_turbo_v2_5")

    captured_payloads: list[dict[str, Any]] = []

    with patch("hachi.core.providers.speech._get_el_http_client") as mock_get_client:
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.content = b"AUDIO"
        fake_resp.text = ""
        fake_client = MagicMock()
        fake_client.post.return_value = fake_resp
        mock_get_client.return_value = fake_client

        def _capturing_post(url: str, *, json: dict[str, Any], headers: dict[str, str]) -> Any:
            captured_payloads.append(json)
            return fake_resp

        fake_client.post.side_effect = _capturing_post

        provider.synthesize("Hello world")

    assert len(captured_payloads) == 1
    assert captured_payloads[0]["model_id"] == "eleven_turbo_v2_5"

    speech_mod._el_shared_client = None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# FIX — Cost tracking after transcribe (voice_endpoints.py)
# ---------------------------------------------------------------------------


def test_transcribe_records_voice_cost() -> None:
    """transcribe() must invoke record_voice_usage with 'stt' + minutes."""
    from unittest.mock import patch as _patch

    from hachi.gateway import voice_endpoints

    fake_provider = MagicMock()
    fake_provider.transcribe.return_value = "hello"

    recorded: list[tuple[str, str, float]] = []

    def _fake_record(modality: str, model: str, units: float) -> float:
        recorded.append((modality, model, units))
        return 0.0

    with (
        _patch.object(voice_endpoints, "_load_voice_cfg", return_value=None),
        _patch.object(voice_endpoints, "_is_voice_configured", return_value=True),
        _patch("hachi.gateway.voice_endpoints.build_stt_provider", return_value=fake_provider),
        _patch("hachi.core.cost.record_voice_usage", _fake_record),
    ):
        # Provide ~1 second of fake webm audio at 32kbps → ~4000 bytes.
        voice_endpoints.transcribe(
            b"\x00" * 4000,
            filename="test.webm",
            content_type="audio/webm",
        )

    assert len(recorded) == 1
    modality, model, minutes = recorded[0]
    assert modality == "stt"
    assert minutes > 0  # must be a positive duration estimate


# ---------------------------------------------------------------------------
# FIX — Cost tracking after speak (voice_endpoints.py)
# ---------------------------------------------------------------------------


def test_speak_records_voice_cost() -> None:
    """speak() must invoke record_voice_usage with 'tts' + char count."""
    from unittest.mock import patch as _patch

    from hachi.gateway import voice_endpoints

    fake_provider = MagicMock()
    fake_provider.synthesize.return_value = b"AUDIODATA"

    recorded: list[tuple[str, str, float]] = []

    def _fake_record(modality: str, model: str, units: float) -> float:
        recorded.append((modality, model, units))
        return 0.0

    test_text = "Hello, this is a test."

    with (
        _patch.object(voice_endpoints, "_load_voice_cfg", return_value=None),
        _patch.object(voice_endpoints, "_is_voice_configured", return_value=True),
        _patch("hachi.gateway.voice_endpoints.build_tts_provider", return_value=fake_provider),
        _patch("hachi.core.cost.record_voice_usage", _fake_record),
    ):
        voice_endpoints.speak(test_text)

    assert len(recorded) == 1
    modality, model, units = recorded[0]
    assert modality == "tts"
    assert units == float(len(test_text))


# ---------------------------------------------------------------------------
# FIX — Cost tracking is non-fatal (voice_endpoints.py)
# ---------------------------------------------------------------------------


def test_speak_cost_tracking_failure_is_non_fatal() -> None:
    """If record_voice_usage raises, speak() must still return normally."""
    from unittest.mock import patch as _patch

    from hachi.gateway import voice_endpoints

    fake_provider = MagicMock()
    fake_provider.synthesize.return_value = b"AUDIODATA"

    def _exploding_record(*a: Any, **kw: Any) -> float:
        raise RuntimeError("cost DB unavailable")

    with (
        _patch.object(voice_endpoints, "_load_voice_cfg", return_value=None),
        _patch.object(voice_endpoints, "_is_voice_configured", return_value=True),
        _patch("hachi.gateway.voice_endpoints.build_tts_provider", return_value=fake_provider),
        _patch("hachi.core.cost.record_voice_usage", _exploding_record),
    ):
        audio, media_type = voice_endpoints.speak("Hello")

    assert audio == b"AUDIODATA"
    assert "audio" in media_type


# ---------------------------------------------------------------------------
# FIX P1 — speak_stream falls back to buffered path for non-streaming providers
# ---------------------------------------------------------------------------


def test_speak_stream_falls_back_to_buffered() -> None:
    """speak_stream() must return chunked bytes even when the provider has no
    synthesize_stream method (i.e. the buffered fallback path)."""
    from unittest.mock import patch as _patch

    from hachi.gateway import voice_endpoints

    fake_provider = MagicMock(spec=["synthesize", "health"])
    fake_provider.synthesize.return_value = b"A" * 20_000

    with (
        _patch.object(voice_endpoints, "_load_voice_cfg", return_value=None),
        _patch.object(voice_endpoints, "_is_voice_configured", return_value=True),
        _patch("hachi.gateway.voice_endpoints.build_tts_provider", return_value=fake_provider),
        _patch("hachi.core.cost.record_voice_usage", lambda *a, **k: 0.0),
    ):
        chunk_iter, media_type = voice_endpoints.speak_stream("Hello", chunk_size=4096)
        chunks = list(chunk_iter)

    # All chunks together should equal the original audio.
    total = b"".join(chunks)
    assert total == b"A" * 20_000
    assert len(chunks) > 1, "Expected multiple chunks for streaming behaviour"
