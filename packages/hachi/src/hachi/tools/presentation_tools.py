"""Presentation generation tool — create PowerPoint files from natural language.

The agent describes the presentation it wants (title, theme, outline), and this
tool builds a ``.pptx`` file on disk using ``python-pptx``.  The result is the
absolute path to the created file so the agent can reference or send it.

``python-pptx`` is an optional dependency (``uv sync --extra presentations``).
When absent the tool degrades gracefully with an actionable install hint.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON schema — registered into the tool registry
# ---------------------------------------------------------------------------

GENERATE_PRESENTATION_SCHEMA: dict[str, Any] = {
    "name": "generate_presentation",
    "description": (
        "Generate a PowerPoint (.pptx) presentation from a natural language description. "
        "Provide a title, a list of slide specifications (each with a heading and bullet "
        "points), and optional styling. Returns the path to the saved .pptx file."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Presentation title (shown on the first title slide).",
            },
            "subtitle": {
                "type": "string",
                "description": "Optional subtitle or date for the title slide.",
            },
            "slides": {
                "type": "array",
                "description": "Ordered list of content slides.",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {
                            "type": "string",
                            "description": "Slide title / section heading.",
                        },
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Bullet points for the slide body.",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Optional presenter notes (not visible to audience).",
                        },
                    },
                    "required": ["heading"],
                },
            },
            "theme": {
                "type": "string",
                "enum": ["default", "dark", "light", "professional"],
                "description": "Visual theme. Affects background and accent colours.",
            },
            "output_path": {
                "type": "string",
                "description": (
                    "Where to save the .pptx file. "
                    "Defaults to ~/Downloads/<title>.pptx (spaces replaced by underscores)."
                ),
            },
        },
        "required": ["title", "slides"],
    },
}

# ---------------------------------------------------------------------------
# Theme colour palettes  (R, G, B)
# ---------------------------------------------------------------------------

_THEMES: dict[str, dict[str, tuple[int, int, int]]] = {
    "default": {
        "background": (255, 255, 255),
        "title_text": (31, 73, 125),
        "body_text": (64, 64, 64),
        "accent": (31, 73, 125),
    },
    "dark": {
        "background": (30, 30, 30),
        "title_text": (255, 255, 255),
        "body_text": (220, 220, 220),
        "accent": (0, 120, 215),
    },
    "light": {
        "background": (245, 245, 245),
        "title_text": (50, 50, 50),
        "body_text": (80, 80, 80),
        "accent": (0, 112, 192),
    },
    "professional": {
        "background": (255, 255, 255),
        "title_text": (0, 70, 127),
        "body_text": (51, 51, 51),
        "accent": (0, 70, 127),
    },
}


def _rgb(r: int, g: int, b: int) -> Any:
    """Return an RGBColor from python-pptx."""
    from pptx.dml.color import RGBColor
    from pptx.util import Pt  # noqa: F401 — ensure pptx importable

    return RGBColor(r, g, b)


def _safe_filename(name: str) -> str:
    """Turn an arbitrary string into a filesystem-safe filename."""
    slug = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[\s]+", "_", slug) or "presentation"


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _build_pptx(
    title: str,
    subtitle: str,
    slides: list[dict[str, Any]],
    theme_name: str,
    output_path: Path,
) -> None:
    """Assemble the PPTX file using python-pptx primitives."""
    from pptx import Presentation
    from pptx.enum.text import PP_ALIGN  # noqa: F401
    from pptx.util import Inches, Pt

    theme = _THEMES.get(theme_name, _THEMES["default"])

    prs = Presentation()
    # Widescreen 16:9
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    slide_layouts = prs.slide_layouts

    # -- Title slide --
    title_layout = slide_layouts[0]  # "Title Slide"
    tslide = prs.slides.add_slide(title_layout)

    # Background colour
    _set_slide_background(tslide, theme["background"])

    # Title placeholder
    tf = tslide.shapes.title.text_frame
    tf.text = title
    for para in tf.paragraphs:
        for run in para.runs:
            run.font.color.rgb = _rgb(*theme["title_text"])
            run.font.size = Pt(36)
            run.font.bold = True

    # Subtitle placeholder (index 1)
    if len(tslide.placeholders) > 1:
        sub_tf = tslide.placeholders[1].text_frame
        sub_tf.text = subtitle
        for para in sub_tf.paragraphs:
            for run in para.runs:
                run.font.color.rgb = _rgb(*theme["body_text"])
                run.font.size = Pt(20)

    # -- Content slides --
    content_layout = slide_layouts[1]  # "Title and Content"
    for slide_spec in slides:
        cslide = prs.slides.add_slide(content_layout)
        _set_slide_background(cslide, theme["background"])

        # Slide title
        heading = slide_spec.get("heading", "")
        cslide.shapes.title.text = heading
        h_tf = cslide.shapes.title.text_frame
        for para in h_tf.paragraphs:
            for run in para.runs:
                run.font.color.rgb = _rgb(*theme["title_text"])
                run.font.size = Pt(28)
                run.font.bold = True

        # Body bullets
        bullets = slide_spec.get("bullets") or []
        if len(cslide.placeholders) > 1 and bullets:
            body_tf = cslide.placeholders[1].text_frame
            body_tf.clear()
            for i, bullet in enumerate(bullets):
                if i == 0:
                    para = body_tf.paragraphs[0]
                else:
                    para = body_tf.add_paragraph()
                para.text = bullet
                para.level = 0
                for run in para.runs:
                    run.font.color.rgb = _rgb(*theme["body_text"])
                    run.font.size = Pt(18)

        # Presenter notes
        notes_text = slide_spec.get("notes", "")
        if notes_text:
            notes_slide = cslide.notes_slide
            notes_slide.notes_text_frame.text = notes_text

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))


def _set_slide_background(slide: Any, rgb_tuple: tuple[int, int, int]) -> None:
    """Fill a slide's background with a solid colour."""
    from pptx.dml.color import RGBColor
    from pptx.enum.dml import MSO_THEME_COLOR  # noqa: F401

    # Access the background fill via XML manipulation (python-pptx's cleanest path)
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(*rgb_tuple)


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def make_generate_presentation(gate: Any | None = None) -> Any:
    """Return the ``generate_presentation`` callable, permission-gated."""

    def generate_presentation(
        title: str,
        slides: list[dict[str, Any]],
        subtitle: str = "",
        theme: str = "default",
        output_path: str = "",
    ) -> str:
        """Build a .pptx file from structured slide data."""
        # Dependency check
        try:
            import pptx  # noqa: F401
        except ImportError:
            return (
                "python-pptx is not installed. "
                "Run `uv sync --extra presentations` to enable presentation generation."
            )

        # Resolve output path
        if output_path:
            dest = Path(output_path).expanduser()
        else:
            downloads = Path.home() / "Downloads"
            dest = downloads / f"{_safe_filename(title)}.pptx"

        # Permission check (write path)
        if gate is not None:
            check = gate.check_path(str(dest), "write")
            if not getattr(check, "allowed", True):
                return f"Permission Denied: write access to '{dest}' is not allowed."

        if not slides:
            return "Error: at least one slide is required."

        if theme not in _THEMES:
            return f"Unknown theme '{theme}'. Valid themes: {', '.join(sorted(_THEMES))}."

        try:
            _build_pptx(
                title=title,
                subtitle=subtitle,
                slides=slides,
                theme_name=theme,
                output_path=dest,
            )
        except Exception as exc:
            logger.exception("Presentation generation failed")
            return f"Error generating presentation: {exc}"

        return f"Presentation saved to: {dest}  ({len(slides)} content slide(s))"

    return generate_presentation


def register_presentation_tools(registry: Any, gate: Any | None = None) -> None:
    """Register generate_presentation into *registry*."""
    registry.register(
        GENERATE_PRESENTATION_SCHEMA,
        make_generate_presentation(gate),
        group="presentations",
    )
