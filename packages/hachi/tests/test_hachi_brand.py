"""Tests for the Hachi brand theme helpers (pure, no Textual runtime needed)."""

from __future__ import annotations

from hachi.tui import theme
from hachi.tui.art import ouroboros


def test_hachi_eye_known_states() -> None:
    for state in ("idle", "thinking", "working", "success", "error"):
        glyph, color = theme.hachi_eye(state)
        assert glyph
        assert color.startswith("#")


def test_hachi_eye_unknown_falls_back_to_idle() -> None:
    assert theme.hachi_eye("nonsense") == theme.HACHI_STATE_EYES["idle"]
    assert theme.hachi_eye(None) == theme.HACHI_STATE_EYES["idle"]


def test_hachi_state_for_event_mapping() -> None:
    assert theme.hachi_state_for_event("tool.call.started") == "working"
    assert theme.hachi_state_for_event("session.chat.started") == "thinking"
    assert theme.hachi_state_for_event("session.chat.completed") == "success"
    assert theme.hachi_state_for_event("boot.complete") == "idle"
    assert theme.hachi_state_for_event("boot.failed") == "error"


def test_hachi_state_for_event_tool_completed_branches() -> None:
    assert theme.hachi_state_for_event("tool.call.completed", is_error=False) == "thinking"
    assert theme.hachi_state_for_event("tool.call.completed", is_error=True) == "error"


def test_hachi_state_for_event_unknown_is_none() -> None:
    assert theme.hachi_state_for_event("usage.updated") is None
    assert theme.hachi_state_for_event("text.stream.delta") is None


def test_loyal_loop_art_carries_brand_colors() -> None:
    art = ouroboros()
    styles = {str(span.style) for span in art.spans}
    assert theme.HACHI_BODY in styles  # loop body — torii red
    assert theme.HACHI_BODY_BRIGHT in styles  # crossing-point bright red
    assert theme.HACHI_EYE_CREAM in styles  # cream glint inside each lobe
    assert theme.HACHI_TONGUE in styles  # amber rim accent
    assert "\n" in art.plain  # multi-line block


def test_hachi_eye_frames_define_active_states() -> None:
    assert set(theme.HACHI_EYE_FRAMES) == {"thinking", "working"}
    for frames in theme.HACHI_EYE_FRAMES.values():
        assert len(frames) >= 2
