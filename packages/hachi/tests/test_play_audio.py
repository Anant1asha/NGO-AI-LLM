"""Offline tests for the play_audio voice tool and AudioPlayer backend.

All tests use an injectable ``Player`` callable — no real audio player binary
is ever invoked, so the suite runs on any CI machine regardless of installed
system audio packages.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hachi.core.loop import ToolRegistry
from hachi.core.voice import AudioPlayer
from hachi.tools.voice_tools import (
    PLAY_AUDIO_SCHEMA,
    _make_play_audio,
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


def _fake_player(returncode: int = 0, stderr: str = "") -> AudioPlayer:
    """Return an AudioPlayer that reports a fixed (returncode, stderr) pair."""

    def _play(path: Path) -> tuple[int, str]:
        return returncode, stderr

    ap = AudioPlayer(player=_play)
    return ap


def _wav(tmp_path: Path, name: str = "speech.wav") -> Path:
    """Write a minimal WAV stub and return its path."""
    import struct
    import wave

    p = tmp_path / name
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(struct.pack("<h", 0) * 160)  # 10 ms of silence
    return p


# ---------------------------------------------------------------------------
# AudioPlayer unit tests
# ---------------------------------------------------------------------------


def test_audio_player_happy_path(tmp_path: Path) -> None:
    """AudioPlayer with a fake player that returns 0 succeeds."""
    p = _wav(tmp_path)
    ap = _fake_player(returncode=0)
    code, err = ap.play(p)
    assert code == 0
    assert err == ""


def test_audio_player_failure_propagates(tmp_path: Path) -> None:
    """AudioPlayer propagates the non-zero exit code from the player."""
    p = _wav(tmp_path)
    ap = _fake_player(returncode=1, stderr="device not found")
    code, err = ap.play(p)
    assert code == 1
    assert "device not found" in err


def test_audio_player_is_available_when_injected() -> None:
    """is_available() is based on detect_player_binary, not on the injected fn."""
    # Patch _detect_player_binary to return a fake binary name
    with patch("hachi.core.voice._detect_player_binary", return_value="fake-player"):
        ap = AudioPlayer(player=lambda p: (0, ""))
        assert ap.is_available() is True


def test_audio_player_not_available_when_no_binary() -> None:
    with patch("hachi.core.voice._detect_player_binary", return_value=None):
        ap = AudioPlayer()
        assert ap.is_available() is False


# ---------------------------------------------------------------------------
# play_audio tool — permission gating
# ---------------------------------------------------------------------------


def test_play_audio_sandbox_tier_blocked(tmp_path: Path) -> None:
    p = _wav(tmp_path)
    gate = _Gate(tier="sandbox")
    fn = _make_play_audio(gate, _fake_player())
    result = fn(str(p))
    assert "Permission Denied" in result
    assert "sandbox" in result


def test_play_audio_path_denied(tmp_path: Path) -> None:
    p = _wav(tmp_path)
    gate = _Gate(tier="guided", allowed=False)
    fn = _make_play_audio(gate, _fake_player())
    result = fn(str(p))
    assert "Permission Denied" in result


# ---------------------------------------------------------------------------
# play_audio tool — file validation
# ---------------------------------------------------------------------------


def test_play_audio_missing_file(tmp_path: Path) -> None:
    fn = _make_play_audio(None, _fake_player())
    result = fn(str(tmp_path / "nonexistent.wav"))
    assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# play_audio tool — player availability
# ---------------------------------------------------------------------------


def test_play_audio_no_player_available(tmp_path: Path) -> None:
    p = _wav(tmp_path)
    with patch("hachi.core.voice._detect_player_binary", return_value=None):
        fn = _make_play_audio(None, None)  # no injected player → uses AudioPlayer()
        result = fn(str(p))
    assert "No audio player" in result or "not available" in result.lower()


# ---------------------------------------------------------------------------
# play_audio tool — happy path and failure
# ---------------------------------------------------------------------------


def test_play_audio_happy_path(tmp_path: Path) -> None:
    p = _wav(tmp_path)
    fn = _make_play_audio(None, _fake_player(returncode=0))
    result = fn(str(p))
    assert "Played" in result
    assert p.name in result


def test_play_audio_player_failure(tmp_path: Path) -> None:
    p = _wav(tmp_path)
    fn = _make_play_audio(None, _fake_player(returncode=1, stderr="no sound card"))
    result = fn(str(p))
    assert "failed" in result.lower()
    assert "no sound card" in result


def test_play_audio_player_exception(tmp_path: Path) -> None:
    """If player raises unexpectedly, the tool returns a friendly message."""

    def _boom(path: Path) -> tuple[int, str]:
        raise OSError("device busy")

    p = _wav(tmp_path)
    ap = AudioPlayer(player=_boom)
    fn = _make_play_audio(None, ap)
    result = fn(str(p))
    assert "failed" in result.lower()
    assert "device busy" in result


# ---------------------------------------------------------------------------
# Registration: 5 voice tools present
# ---------------------------------------------------------------------------


def test_register_voice_tools_includes_play_audio() -> None:
    registry = ToolRegistry()
    register_voice_tools(registry, gate=None, player=_fake_player())
    names = {s["name"] for s in registry.get_schemas()}
    assert "play_audio" in names
    assert "transcribe_audio" in names
    assert "transcribe_and_summarize" in names
    assert "speak_text" in names
    assert "get_audio_info" in names
    assert len(names) == 5


def test_play_audio_schema_shape() -> None:
    assert PLAY_AUDIO_SCHEMA["name"] == "play_audio"
    assert "path" in PLAY_AUDIO_SCHEMA["input_schema"]["properties"]
    assert PLAY_AUDIO_SCHEMA["input_schema"]["required"] == ["path"]
