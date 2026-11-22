"""Offline tests for transcribe_and_summarize tool and summarize_transcript helper.

No network, no API key, no audio player needed — STT is faked via an injectable
transcriber exactly like the existing voice-tools tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from hachi.core.loop import ToolRegistry
from hachi.core.voice import SpeechToText, summarize_transcript
from hachi.tools.voice_tools import (
    _make_transcribe_and_summarize,
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


def _wav(tmp_path: Path, name: str = "meeting.wav") -> Path:
    p = tmp_path / name
    p.write_bytes(b"RIFF....WAVEfmt ")  # bytes irrelevant — STT is faked
    return p


def _ok_transcriber(text: str = "hello world"):
    def _t(url, file_bytes, filename, form_data, headers):
        return 200, json.dumps({"text": text})

    return _t


_SAMPLE_TRANSCRIPT = (
    "The project is on track and we will hit the deadline. "
    "The main blocker is the database migration which is causing delays. "
    "Alice will fix the migration script by Friday. "
    "The new feature improves performance by reducing database round-trips. "
    "We should review the deployment checklist before the release."
)


# ---------------------------------------------------------------------------
# summarize_transcript — pure unit tests (no I/O)
# ---------------------------------------------------------------------------


def test_summarize_empty_returns_zeros() -> None:
    result = summarize_transcript("")
    assert result["word_count"] == 0
    assert result["sentence_count"] == 0
    assert result["key_sentences"] == []
    assert result["estimated_reading_seconds"] == 0


def test_summarize_returns_word_count() -> None:
    result = summarize_transcript(_SAMPLE_TRANSCRIPT)
    assert result["word_count"] == len(_SAMPLE_TRANSCRIPT.split())


def test_summarize_sentence_count() -> None:
    result = summarize_transcript(_SAMPLE_TRANSCRIPT)
    assert result["sentence_count"] == 5


def test_summarize_top_sentences_capped_at_available() -> None:
    short = "One sentence only."
    result = summarize_transcript(short, top_sentences=5)
    assert len(result["key_sentences"]) == 1


def test_summarize_respects_top_sentences_param() -> None:
    result = summarize_transcript(_SAMPLE_TRANSCRIPT, top_sentences=2)
    assert len(result["key_sentences"]) == 2


def test_summarize_default_top_is_three() -> None:
    result = summarize_transcript(_SAMPLE_TRANSCRIPT)
    assert len(result["key_sentences"]) == 3


def test_summarize_preserves_narrative_order() -> None:
    """Key sentences must appear in document order, not ranked order."""
    result = summarize_transcript(_SAMPLE_TRANSCRIPT, top_sentences=3)
    sentences = result["key_sentences"]
    # Each sentence must appear in the original text at a later position
    positions = [_SAMPLE_TRANSCRIPT.index(s) for s in sentences]
    assert positions == sorted(positions), "key_sentences are not in document order"


def test_summarize_estimated_reading_seconds_nonzero_for_long_text() -> None:
    long_text = (_SAMPLE_TRANSCRIPT + " ") * 10  # ~400 words
    result = summarize_transcript(long_text)
    assert result["estimated_reading_seconds"] > 0


def test_summarize_selects_content_rich_sentences() -> None:
    """The database/migration sentence should rank high (repeated key terms)."""
    result = summarize_transcript(_SAMPLE_TRANSCRIPT, top_sentences=2)
    combined = " ".join(result["key_sentences"]).lower()
    # One of the two sentences should mention "database" or "migration" (high-freq words)
    assert "database" in combined or "migration" in combined


# ---------------------------------------------------------------------------
# _make_transcribe_and_summarize — tool factory
# ---------------------------------------------------------------------------


def test_tool_sandbox_blocked(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    gate = _Gate(tier="sandbox")
    fn = _make_transcribe_and_summarize(gate, None)
    result = fn(str(audio))
    assert "Permission Denied" in result
    assert "sandbox" in result


def test_tool_path_denied(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    gate = _Gate(allowed=False)
    fn = _make_transcribe_and_summarize(gate, None)
    result = fn(str(audio))
    assert "Permission Denied" in result


def test_tool_not_configured_returns_hint(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    stt = SpeechToText()  # no api_key
    fn = _make_transcribe_and_summarize(None, stt)
    result = fn(str(audio))
    assert "not configured" in result
    assert "OPENAI_API_KEY" in result or "HACHI_STT_API_KEY" in result


def test_tool_happy_path_contains_summary_and_transcript(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber(_SAMPLE_TRANSCRIPT))
    fn = _make_transcribe_and_summarize(None, stt)
    result = fn(str(audio))
    assert "## Summary" in result
    assert "## Full transcript" in result
    assert _SAMPLE_TRANSCRIPT in result


def test_tool_output_includes_word_count(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber(_SAMPLE_TRANSCRIPT))
    fn = _make_transcribe_and_summarize(None, stt)
    result = fn(str(audio))
    wc = len(_SAMPLE_TRANSCRIPT.split())
    assert str(wc) in result


def test_tool_custom_top_sentences(tmp_path: Path) -> None:
    audio = _wav(tmp_path)
    stt = SpeechToText(api_key="sk-test", transcriber=_ok_transcriber(_SAMPLE_TRANSCRIPT))
    fn = _make_transcribe_and_summarize(None, stt)
    result = fn(str(audio), top_sentences=2)
    # Count bullet points in summary section
    summary_section = result.split("## Full transcript")[0]
    bullets = [ln for ln in summary_section.splitlines() if ln.startswith("- ")]
    assert len(bullets) == 2


def test_tool_transcription_error_returns_friendly_message(tmp_path: Path) -> None:
    def _err_transcriber(url, file_bytes, filename, form_data, headers):
        return 500, "Internal Server Error"

    audio = _wav(tmp_path)
    stt = SpeechToText(api_key="sk-test", transcriber=_err_transcriber)
    fn = _make_transcribe_and_summarize(None, stt)
    result = fn(str(audio))
    assert "Transcription failed" in result


# ---------------------------------------------------------------------------
# register_voice_tools — registration check
# ---------------------------------------------------------------------------


def test_register_voice_tools_includes_transcribe_and_summarize() -> None:
    registry = ToolRegistry()
    register_voice_tools(registry)
    assert "transcribe_and_summarize" in registry._tools
    # Schema present
    names = [s["name"] for s in registry._schemas]
    assert "transcribe_and_summarize" in names
