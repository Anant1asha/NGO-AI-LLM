"""Tests for UC-INT-005 (.pcm dead-end) and ADV-015 (empty allowlist fail-open).

UC-INT-005 — `.pcm` output from TextToSpeech must be rejected early with an
  actionable message rather than silently writing an unplayable raw-PCM file.

ADV-015 — An empty channel sender allowlist must be FAIL-CLOSED (deny all),
  not fail-open (admit all).  A non-empty allowlist must still admit listed
  senders and deny others.  Open access requires an explicit opt-in flag.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hachi.channels import ChannelRouter, InboundMessage
from hachi.core.voice import TextToSpeech, VoiceError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_synthesizer(url: str, payload: dict, headers: dict) -> tuple[int, bytes]:
    """Fake synthesizer that returns a minimal WAV stub."""
    # Return a tiny but structurally valid WAV header so write succeeds for
    # supported formats; the content doesn't matter for these tests.
    return 200, b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"


def _echo_runner(session_key: str, text: str) -> str:
    return f"[{session_key}] {text}"


# ---------------------------------------------------------------------------
# UC-INT-005: .pcm clean rejection
# ---------------------------------------------------------------------------


class TestPcmRejection:
    """TextToSpeech must reject .pcm early with an actionable error."""

    def test_pcm_raises_voice_error(self, tmp_path: Path) -> None:
        """Synthesizing to a .pcm path raises VoiceError before any API call."""
        tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer)
        out = tmp_path / "output.pcm"
        with pytest.raises(VoiceError) as exc_info:
            tts.synthesize("hello world", out)
        assert ".pcm" in str(exc_info.value).lower() or "pcm" in str(exc_info.value).lower()

    def test_pcm_error_mentions_wav_alternative(self, tmp_path: Path) -> None:
        """The rejection message must name .wav as the recommended alternative."""
        tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer)
        out = tmp_path / "output.pcm"
        with pytest.raises(VoiceError) as exc_info:
            tts.synthesize("hello world", out)
        msg = str(exc_info.value).lower()
        assert "wav" in msg, f"Expected '.wav' alternative in message, got: {exc_info.value}"

    def test_pcm_error_is_actionable_not_opaque(self, tmp_path: Path) -> None:
        """The error must explain WHY .pcm is rejected (not just 'unsupported format')."""
        tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer)
        out = tmp_path / "output.pcm"
        with pytest.raises(VoiceError) as exc_info:
            tts.synthesize("hello world", out)
        msg = str(exc_info.value)
        # Must give a reason, not just a list of supported formats.
        assert len(msg) > 60, f"Error too terse to be actionable: {msg!r}"

    def test_pcm_file_is_not_written_to_disk(self, tmp_path: Path) -> None:
        """No partial file must be left on disk after a .pcm rejection."""
        tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer)
        out = tmp_path / "output.pcm"
        with pytest.raises(VoiceError):
            tts.synthesize("hello world", out)
        assert not out.exists(), "Rejected .pcm path must not exist after early rejection"

    def test_synthesizer_not_called_for_pcm(self, tmp_path: Path) -> None:
        """The API synthesizer callable must not be invoked for a .pcm path."""
        calls: list[str] = []

        def _tracking_synthesizer(url, payload, headers):
            calls.append(url)
            return 200, b"fake audio"

        tts = TextToSpeech(api_key="sk-test", synthesizer=_tracking_synthesizer)
        out = tmp_path / "output.pcm"
        with pytest.raises(VoiceError):
            tts.synthesize("hello world", out)
        assert calls == [], "Synthesizer must not be called when .pcm is rejected early"

    def test_wav_output_still_works(self, tmp_path: Path) -> None:
        """.wav output must still succeed (not caught by the .pcm guard)."""

        def _wav_synthesizer(url, payload, headers):
            import io
            import struct
            import wave

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(struct.pack("<h", 0) * 24)  # 1 ms silence
            return 200, buf.getvalue()

        tts = TextToSpeech(api_key="sk-test", synthesizer=_wav_synthesizer)
        out = tmp_path / "output.wav"
        result = tts.synthesize("hello", out)
        assert result == out
        assert out.exists()

    def test_mp3_output_still_works(self, tmp_path: Path) -> None:
        """.mp3 output must still succeed."""

        def _mp3_synthesizer(url, payload, headers):
            return 200, b"\xff\xfb\x90\x00" + b"\x00" * 100  # fake MP3 frame

        tts = TextToSpeech(api_key="sk-test", synthesizer=_mp3_synthesizer)
        out = tmp_path / "output.mp3"
        result = tts.synthesize("hello", out)
        assert result == out
        assert out.exists()

    def test_pcm_voice_error_is_catchable_as_friendly_string(self, tmp_path: Path) -> None:
        """The VoiceError raised for .pcm must be catch-able and produce a friendly message.

        The speak_text tool wrapper catches VoiceError and returns
        ``f"Speech synthesis failed: {exc}"``.  This test verifies the error
        message surfaced to that wrapper contains the expected content, without
        importing voice_tools (which has a heavy transitive dep chain).
        """
        tts = TextToSpeech(api_key="sk-test", synthesizer=_ok_synthesizer)
        out = tmp_path / "output.pcm"
        try:
            tts.synthesize("hello world", out)
            pytest.fail("Expected VoiceError was not raised for .pcm")
        except VoiceError as exc:
            friendly = f"Speech synthesis failed: {exc}"
            assert "Speech synthesis failed" in friendly
            # The actionable message forwarded to the caller mentions the fix.
            assert "pcm" in friendly.lower() or "wav" in friendly.lower()


# ---------------------------------------------------------------------------
# ADV-015: sender allowlist fail-closed
# ---------------------------------------------------------------------------


class TestAllowlistFailClosed:
    """ChannelRouter sender allowlist must default to fail-closed."""

    # --- empty allowlist → deny all ---

    def test_empty_allowlist_denies_any_sender(self) -> None:
        """An empty allowlist (fail-closed) denies every sender_id."""
        router = ChannelRouter(_echo_runner, allowlist=[])
        out = router.dispatch(InboundMessage(channel="test", sender_id="anyone", text="hi"))
        assert "not authorized" in out.text

    def test_empty_allowlist_is_allowed_returns_false(self) -> None:
        """is_allowed() must return False for any sender when allowlist is empty."""
        router = ChannelRouter(_echo_runner, allowlist=[])
        assert router.is_allowed("alice") is False
        assert router.is_allowed("") is False
        assert router.is_allowed("admin") is False

    def test_empty_allowlist_denies_multiple_different_senders(self) -> None:
        """All senders are denied when the allowlist is empty."""
        router = ChannelRouter(_echo_runner, allowlist=[])
        for sender_id in ("alice", "bob", "charlie", "42", "root"):
            out = router.dispatch(InboundMessage(channel="test", sender_id=sender_id, text="x"))
            assert "not authorized" in out.text, f"Expected denial for sender {sender_id!r}"

    # --- no allowlist + default flag → deny all (fail-closed) ---

    def test_no_allowlist_default_denies_all(self) -> None:
        """Without an allowlist and without the opt-in flag, all senders are denied."""
        router = ChannelRouter(_echo_runner)  # no allowlist, no opt-in
        out = router.dispatch(InboundMessage(channel="test", sender_id="anyone", text="hi"))
        assert "not authorized" in out.text

    def test_no_allowlist_is_allowed_false_by_default(self) -> None:
        """is_allowed() must return False when no allowlist and no opt-in flag."""
        router = ChannelRouter(_echo_runner)
        assert router.is_allowed("anyone") is False

    # --- no allowlist + opt-in flag → admit all ---

    def test_allow_all_flag_permits_any_sender(self) -> None:
        """With allow_all_when_no_allowlist=True and no allowlist, all senders pass."""
        router = ChannelRouter(_echo_runner, allow_all_when_no_allowlist=True)
        out = router.dispatch(InboundMessage(channel="test", sender_id="anyone", text="hi"))
        assert "not authorized" not in out.text
        assert "test:anyone" in out.text

    def test_allow_all_flag_is_allowed_returns_true(self) -> None:
        """is_allowed() returns True for any sender when the opt-in flag is set."""
        router = ChannelRouter(_echo_runner, allow_all_when_no_allowlist=True)
        assert router.is_allowed("alice") is True
        assert router.is_allowed("") is True

    # --- configured (non-empty) allowlist → admit listed, deny others ---

    def test_configured_allowlist_admits_listed_sender(self) -> None:
        """A sender in the allowlist must be admitted."""
        router = ChannelRouter(_echo_runner, allowlist=["alice", "bob"])
        out = router.dispatch(InboundMessage(channel="test", sender_id="alice", text="hello"))
        assert "test:alice" in out.text
        assert "not authorized" not in out.text

    def test_configured_allowlist_denies_unlisted_sender(self) -> None:
        """A sender NOT in the allowlist must be denied."""
        router = ChannelRouter(_echo_runner, allowlist=["alice", "bob"])
        out = router.dispatch(InboundMessage(channel="test", sender_id="charlie", text="hi"))
        assert "not authorized" in out.text

    def test_configured_allowlist_is_allowed_true_for_member(self) -> None:
        router = ChannelRouter(_echo_runner, allowlist=["alice"])
        assert router.is_allowed("alice") is True

    def test_configured_allowlist_is_allowed_false_for_non_member(self) -> None:
        router = ChannelRouter(_echo_runner, allowlist=["alice"])
        assert router.is_allowed("bob") is False

    def test_allowlist_accepts_integer_like_sender_ids(self) -> None:
        """Telegram uses integer chat IDs; the allowlist must work with numeric strings."""
        router = ChannelRouter(_echo_runner, allowlist=["42", "99"])
        assert router.is_allowed("42") is True
        assert router.is_allowed("7") is False

    def test_allowlist_ignores_allow_all_flag_when_allowlist_is_provided(self) -> None:
        """Providing an allowlist always takes precedence over allow_all_when_no_allowlist."""
        router = ChannelRouter(_echo_runner, allowlist=["alice"], allow_all_when_no_allowlist=True)
        assert router.is_allowed("alice") is True
        assert router.is_allowed("bob") is False  # flag ignored when allowlist present

    def test_dispatch_reply_targets_correct_sender_after_allow(self) -> None:
        """The reply recipient_id must match the original sender_id."""
        router = ChannelRouter(_echo_runner, allowlist=["42"])
        out = router.dispatch(InboundMessage(channel="tg", sender_id="42", text="ping"))
        assert out.recipient_id == "42"
        assert out.channel == "tg"

    def test_dispatch_reply_targets_sender_even_when_denied(self) -> None:
        """The denial reply must still target the original sender."""
        router = ChannelRouter(_echo_runner, allowlist=["42"])
        out = router.dispatch(InboundMessage(channel="tg", sender_id="99", text="ping"))
        assert out.recipient_id == "99"
        assert "not authorized" in out.text
