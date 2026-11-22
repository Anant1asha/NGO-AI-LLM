"""Offline tests for speech-to-text: the SpeechToText backend (faked transcriber,
no network) and the transcribe_audio tool (gating + graceful degradation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hachi.core.loop import ToolRegistry
from hachi.core.voice import SpeechToText, TextToSpeech, VoiceError, probe_audio_info
from hachi.tools.voice_tools import (
    _make_get_audio_info,
    _make_speak_text,
    _make_transcribe_audio,
    register_voice_tools,
)


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
    p.write_bytes(b"RIFF....WAVEfmt ")  # bytes don't matter — transcriber is faked
    return p


def _ok_transcriber(text: str = "hello world"):
    def _t(url, file_bytes, filename, form_data, headers):
        assert url.endswith("/audio/transcriptions")
        assert headers.get("Authorization", "").startswith("Bearer ")
        return 200, json.dumps({"text": text})

    return _t


# --------------------------------------------------------------------------- #
# SpeechToText backend
# --------------------------------------------------------------------------- #
def test_stt_not_configured_without_key() -> None:
    stt = SpeechToText()  # no api_key
    assert stt.is_configured() is False


def test_stt_transcribe_happy_path(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber("the meeting is at noon"))
    assert stt.transcribe(audio) == "the meeting is at noon"


def test_stt_transcribe_raises_when_unconfigured(tmp_path: Path) -> None:
    with pytest.raises(VoiceError):
        SpeechToText().transcribe(_wav(tmp_path))


def test_stt_missing_file(tmp_path: Path) -> None:
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber())
    with pytest.raises(VoiceError, match="not found"):
        stt.transcribe(tmp_path / "nope.wav")


def test_stt_unsupported_extension(tmp_path: Path) -> None:
    bad = tmp_path / "note.txt"
    bad.write_bytes(b"not audio")
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber())
    with pytest.raises(VoiceError, match="unsupported audio format"):
        stt.transcribe(bad)


def test_stt_ssrf_blocks_private_endpoint(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    stt = SpeechToText(
        api_key="sk-test",
        base_url="http://127.0.0.1:1234/v1",
        transcriber=_ok_transcriber(),
        allow_private=False,
    )
    with pytest.raises(VoiceError, match="blocked transcription endpoint"):
        stt.transcribe(audio)


def test_stt_http_error_status(tmp_path: Path) -> None:
    def _t(url, file_bytes, filename, form_data, headers):
        return 401, "unauthorized"

    stt = SpeechToText(api_key="sk-test", transcriber=_t)
    with pytest.raises(VoiceError, match="HTTP 401"):
        stt.transcribe(_wav(tmp_path))


def test_stt_missing_text_field(tmp_path: Path) -> None:
    def _t(url, file_bytes, filename, form_data, headers):
        return 200, json.dumps({"not_text": "x"})

    stt = SpeechToText(api_key="sk-test", transcriber=_t)
    with pytest.raises(VoiceError, match="text"):
        stt.transcribe(_wav(tmp_path))


def test_stt_from_env_reads_keys(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("HACHI_STT_API_KEY", "sk-env")
    monkeypatch.setenv("HACHI_STT_MODEL", "whisper-large")
    stt = SpeechToText.from_env(transcriber=_ok_transcriber())
    assert stt.is_configured() is True
    assert stt._model == "whisper-large"


# --------------------------------------------------------------------------- #
# transcribe_audio tool
# --------------------------------------------------------------------------- #
def test_register_voice_tools_registers_in_voice_group() -> None:
    registry = ToolRegistry()
    register_voice_tools(registry, _Gate("guided"))
    names = {schema["name"] for schema in registry.get_schemas()}
    assert "transcribe_audio" in names
    assert "speak_text" in names
    assert "get_audio_info" in names
    assert "voice" in registry.available_groups()


def test_tool_blocked_in_sandbox(tmp_path: Path) -> None:
    tool = _make_transcribe_audio(_Gate("sandbox"), SpeechToText(api_key="sk-test"))
    out = tool(str(_wav(tmp_path)))
    assert "disabled in 'sandbox'" in out


def test_tool_path_denied(tmp_path: Path) -> None:
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber())
    tool = _make_transcribe_audio(_Gate("guided", allowed=False), stt)
    out = tool(str(_wav(tmp_path)))
    assert "Permission Denied" in out


def test_tool_not_configured_is_friendly(tmp_path: Path) -> None:
    tool = _make_transcribe_audio(_Gate("guided"), SpeechToText())  # no key
    out = tool(str(_wav(tmp_path)))
    assert "not configured" in out
    assert "OPENAI_API_KEY" in out


def test_tool_happy_path(tmp_path: Path) -> None:
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber("call me back"))
    tool = _make_transcribe_audio(_Gate("guided"), stt)
    out = tool(str(_wav(tmp_path, "vm.wav")))
    assert "Transcript of vm.wav" in out
    assert "call me back" in out


def test_tool_failure_is_friendly(tmp_path: Path) -> None:
    def _t(url, file_bytes, filename, form_data, headers):
        return 500, "server error"

    stt = SpeechToText(api_key="sk-test", transcriber=_t)
    tool = _make_transcribe_audio(_Gate("guided"), stt)
    out = tool(str(_wav(tmp_path)))
    assert "Transcription failed" in out


# --------------------------------------------------------------------------- #
# TextToSpeech backend
# --------------------------------------------------------------------------- #
def _ok_synthesizer(audio: bytes = b"ID3fakeaudio"):
    def _s(url, payload, headers):
        assert url.endswith("/audio/speech")
        assert headers.get("Authorization", "").startswith("Bearer ")
        assert payload["input"]
        return 200, audio

    return _s


def test_tts_not_configured_without_key() -> None:
    assert TextToSpeech().is_configured() is False


def test_tts_synthesize_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "reply.mp3"
    tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer(b"AUDIO"))
    result = tts.synthesize("hello there", out)
    assert result == out
    assert out.read_bytes() == b"AUDIO"


def test_tts_format_inferred_from_extension(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def _s(url, payload, headers):
        captured.update(payload)
        return 200, b"AUDIO"

    tts = TextToSpeech(api_key="sk-test", synthesizer=_s)
    tts.synthesize("hi", tmp_path / "note.wav", voice="nova")
    assert captured["response_format"] == "wav"
    assert captured["voice"] == "nova"


def test_tts_unconfigured_raises(tmp_path: Path) -> None:
    with pytest.raises(VoiceError):
        TextToSpeech().synthesize("hi", tmp_path / "x.mp3")


def test_tts_empty_text_raises(tmp_path: Path) -> None:
    tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer())
    with pytest.raises(VoiceError, match="empty"):
        tts.synthesize("   ", tmp_path / "x.mp3")


def test_tts_unsupported_format_raises(tmp_path: Path) -> None:
    tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer())
    with pytest.raises(VoiceError, match="unsupported audio format"):
        tts.synthesize("hi", tmp_path / "x.txt")


def test_tts_ssrf_blocks_private_endpoint(tmp_path: Path) -> None:
    tts = TextToSpeech(
        api_key="sk-test",
        base_url="http://127.0.0.1:9/v1",
        synthesizer=_ok_synthesizer(),
        allow_private=False,
    )
    with pytest.raises(VoiceError, match="blocked speech endpoint"):
        tts.synthesize("hi", tmp_path / "x.mp3")


def test_tts_http_error_raises(tmp_path: Path) -> None:
    def _s(url, payload, headers):
        return 401, b"unauthorized"

    tts = TextToSpeech(api_key="sk-test", synthesizer=_s)
    with pytest.raises(VoiceError, match="HTTP 401"):
        tts.synthesize("hi", tmp_path / "x.mp3")


def test_tts_empty_audio_raises(tmp_path: Path) -> None:
    tts = TextToSpeech(api_key="sk-test", synthesizer=lambda u, p, h: (200, b""))
    with pytest.raises(VoiceError, match="no audio"):
        tts.synthesize("hi", tmp_path / "x.mp3")


# --------------------------------------------------------------------------- #
# speak_text tool
# --------------------------------------------------------------------------- #
def test_speak_tool_blocked_in_sandbox(tmp_path: Path) -> None:
    tool = _make_speak_text(_Gate("sandbox"), TextToSpeech(api_key="sk-test"))
    out = tool("hi", str(tmp_path / "x.mp3"))
    assert "disabled in 'sandbox'" in out


def test_speak_tool_path_denied(tmp_path: Path) -> None:
    tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer())
    tool = _make_speak_text(_Gate("guided", allowed=False), tts)
    out = tool("hi", str(tmp_path / "x.mp3"))
    assert "Permission Denied" in out


def test_speak_tool_not_configured_is_friendly(tmp_path: Path) -> None:
    tool = _make_speak_text(_Gate("guided"), TextToSpeech())  # no key
    out = tool("hi", str(tmp_path / "x.mp3"))
    assert "not configured" in out
    assert "OPENAI_API_KEY" in out


def test_speak_tool_happy_path(tmp_path: Path) -> None:
    out_file = tmp_path / "reply.mp3"
    tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer(b"AUDIO"))
    tool = _make_speak_text(_Gate("guided"), tts)
    out = tool("hello", str(out_file))
    assert "Saved spoken audio to" in out
    assert out_file.read_bytes() == b"AUDIO"


def test_speak_tool_failure_is_friendly(tmp_path: Path) -> None:
    tts = TextToSpeech(api_key="sk-test", synthesizer=lambda u, p, h: (500, b"err"))
    tool = _make_speak_text(_Gate("guided"), tts)
    out = tool("hi", str(tmp_path / "x.mp3"))
    assert "Speech synthesis failed" in out


# --------------------------------------------------------------------------- #
# probe_audio_info (backend, keyless)
# --------------------------------------------------------------------------- #


def _write_wav(
    path: Path, sample_rate: int = 16000, n_channels: int = 1, n_frames: int = 16000
) -> Path:
    """Write a minimal PCM WAV file suitable for testing.

    ``n_frames`` is the number of multi-channel frames.  Each frame contains
    ``n_channels`` samples, so the total number of 16-bit values written is
    ``n_frames * n_channels``.
    """
    import struct
    import wave

    total_samples = n_frames * n_channels
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{total_samples}h", *([0] * total_samples)))
    return path


def test_probe_wav_returns_full_metadata(tmp_path: Path) -> None:
    p = _write_wav(tmp_path / "clip.wav", sample_rate=44100, n_channels=2, n_frames=44100)
    info = probe_audio_info(p)
    assert info["probeable"] is True
    assert info["format"] == "wav"
    assert info["sample_rate"] == 44100
    assert info["channels"] == 2
    assert abs(info["duration_seconds"] - 1.0) < 0.01
    assert info["size_bytes"] > 0


def test_probe_non_wav_returns_size_only(tmp_path: Path) -> None:
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"\xff\xfb" + b"\x00" * 100)
    info = probe_audio_info(mp3)
    assert info["probeable"] is False
    assert info["format"] == "mp3"
    assert info["size_bytes"] == 102
    assert "duration_seconds" not in info


def test_probe_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(VoiceError, match="not found"):
        probe_audio_info(tmp_path / "ghost.wav")


def test_probe_corrupt_wav_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"RIFF garbage not a real wav")
    with pytest.raises(VoiceError, match="could not read WAV header"):
        probe_audio_info(bad)


# --------------------------------------------------------------------------- #
# get_audio_info tool
# --------------------------------------------------------------------------- #


def test_audio_info_tool_blocked_in_sandbox(tmp_path: Path) -> None:
    p = _write_wav(tmp_path / "clip.wav")
    tool = _make_get_audio_info(_Gate("sandbox"))
    out = tool(str(p))
    assert "disabled in 'sandbox'" in out


def test_audio_info_tool_path_denied(tmp_path: Path) -> None:
    p = _write_wav(tmp_path / "clip.wav")
    tool = _make_get_audio_info(_Gate("guided", allowed=False))
    out = tool(str(p))
    assert "Permission Denied" in out


def test_audio_info_tool_happy_wav(tmp_path: Path) -> None:
    p = _write_wav(tmp_path / "mono.wav", sample_rate=22050, n_channels=1, n_frames=22050)
    tool = _make_get_audio_info(_Gate("guided"))
    out = tool(str(p))
    assert "WAV" in out
    assert "22,050 Hz" in out
    assert "mono" in out
    assert "duration_seconds" in out  # JSON block present


def test_audio_info_tool_non_wav_friendly(tmp_path: Path) -> None:
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"\xff\xfb" + b"\x00" * 50)
    tool = _make_get_audio_info(_Gate("guided"))
    out = tool(str(mp3))
    assert "MP3" in out
    assert "not available" in out  # graceful non-WAV message


def test_audio_info_tool_missing_file_friendly(tmp_path: Path) -> None:
    tool = _make_get_audio_info(_Gate("guided"))
    out = tool(str(tmp_path / "nope.wav"))
    assert "Audio info failed" in out
