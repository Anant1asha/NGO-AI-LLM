"""Tests for tools.presentation_tools.

All tests use a real pptx.Presentation object when python-pptx is available,
and verify the graceful-degrade path when it is not.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hachi.tools.presentation_tools import (
    GENERATE_PRESENTATION_SCHEMA,
    _safe_filename,
    make_generate_presentation,
    register_presentation_tools,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_SLIDES = [{"heading": "Intro", "bullets": ["Point A", "Point B"]}]


def _run(
    title: str = "Test Deck",
    slides: list[dict[str, Any]] | None = None,
    theme: str = "default",
    output_path: str = "",
    gate: Any = None,
    tmp: Path | None = None,
) -> str:
    if slides is None:
        slides = _MINIMAL_SLIDES
    fn = make_generate_presentation(gate)
    if output_path == "" and tmp is not None:
        output_path = str(tmp / "out.pptx")
    return fn(title=title, slides=slides, theme=theme, output_path=output_path)


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------


def test_schema_name() -> None:
    assert GENERATE_PRESENTATION_SCHEMA["name"] == "generate_presentation"


def test_schema_required_fields() -> None:
    required = GENERATE_PRESENTATION_SCHEMA["input_schema"]["required"]
    assert "title" in required
    assert "slides" in required


# ---------------------------------------------------------------------------
# _safe_filename
# ---------------------------------------------------------------------------


def test_safe_filename_spaces() -> None:
    assert _safe_filename("My Great Deck") == "My_Great_Deck"


def test_safe_filename_special_chars() -> None:
    result = _safe_filename("Report: Q1/2026!")
    assert "/" not in result
    assert ":" not in result
    assert "!" not in result


def test_safe_filename_empty_fallback() -> None:
    assert _safe_filename("!!!") == "presentation"


# ---------------------------------------------------------------------------
# Graceful degrade — python-pptx not installed
# ---------------------------------------------------------------------------


def test_missing_pptx_returns_hint(tmp_path: Path) -> None:
    with patch.dict(sys.modules, {"pptx": None}):
        result = _run(tmp=tmp_path)
    assert "python-pptx" in result
    assert "uv sync" in result


# ---------------------------------------------------------------------------
# Happy path (requires python-pptx)
# ---------------------------------------------------------------------------


def test_creates_pptx_file(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    result = _run(tmp=tmp_path)
    assert "Presentation saved to:" in result
    # Verify the file actually exists
    dest = Path(result.split("Presentation saved to: ")[1].split()[0])
    assert dest.exists()
    assert dest.suffix == ".pptx"


def test_slide_count_reported(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    slides = [
        {"heading": "S1", "bullets": ["a"]},
        {"heading": "S2", "bullets": ["b"]},
        {"heading": "S3", "bullets": []},
    ]
    result = _run(slides=slides, tmp=tmp_path)
    assert "3 content slide(s)" in result


def test_custom_output_path(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    dest = tmp_path / "custom.pptx"
    result = _run(output_path=str(dest))
    assert dest.exists()
    assert str(dest) in result


def test_all_themes_build(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    for theme in ("default", "dark", "light", "professional"):
        dest = tmp_path / f"{theme}.pptx"
        _run(theme=theme, output_path=str(dest))
        assert dest.exists(), f"Theme '{theme}' did not produce a file"


def test_subtitle_on_title_slide(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    from pptx import Presentation

    dest = tmp_path / "sub.pptx"
    fn = make_generate_presentation()
    fn(
        title="With Subtitle",
        subtitle="Q2 2026",
        slides=_MINIMAL_SLIDES,
        output_path=str(dest),
    )
    prs = Presentation(str(dest))
    title_slide = prs.slides[0]
    # Subtitle placeholder should contain our text
    sub = title_slide.placeholders[1]
    assert "Q2 2026" in sub.text_frame.text


def test_presenter_notes_written(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    from pptx import Presentation

    dest = tmp_path / "notes.pptx"
    fn = make_generate_presentation()
    fn(
        title="Notes Test",
        slides=[{"heading": "Slide 1", "bullets": [], "notes": "Speak slowly here."}],
        output_path=str(dest),
    )
    prs = Presentation(str(dest))
    content_slide = prs.slides[1]  # index 0 = title, index 1 = first content slide
    notes_text = content_slide.notes_slide.notes_text_frame.text
    assert "Speak slowly here." in notes_text


def test_empty_slides_returns_error(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    result = _run(slides=[], tmp=tmp_path)
    assert "Error" in result


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------


def test_permission_denied_write(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    gate = MagicMock()
    denied = MagicMock()
    denied.allowed = False
    gate.check_path.return_value = denied

    dest = tmp_path / "blocked.pptx"
    result = _run(gate=gate, output_path=str(dest))
    assert "Permission Denied" in result
    assert not dest.exists()


def test_permission_allowed_write(tmp_path: Path) -> None:
    pytest.importorskip("pptx")
    gate = MagicMock()
    allowed = MagicMock()
    allowed.allowed = True
    gate.check_path.return_value = allowed

    dest = tmp_path / "allowed.pptx"
    _run(gate=gate, output_path=str(dest))
    assert dest.exists()


# ---------------------------------------------------------------------------
# register_presentation_tools
# ---------------------------------------------------------------------------


def test_register_adds_to_registry() -> None:
    registry = MagicMock()
    register_presentation_tools(registry)
    registry.register.assert_called_once()
    call_args = registry.register.call_args[0]
    assert call_args[0]["name"] == "generate_presentation"
