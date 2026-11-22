"""Tests for the SKILL.md -> ObjectGraph bridge."""

from __future__ import annotations

from pathlib import Path

from hachi.og_engine.engine import SkillEngine
from hachi.og_engine.parser import parse_og_file
from hachi.og_engine.serializer import serialize_og_file
from hachi.og_engine.skill_md import skill_md_to_og

_SAMPLE = """---
name: PDF Processing
description: Extract text and tables from PDF documents
---

# PDF Processing

Use this skill to pull text and tables out of PDFs.

1. Open the PDF file.
2. Extract the text layer.
3. Parse tables into rows.
"""


def test_skill_md_converts_frontmatter_body_and_steps() -> None:
    og = skill_md_to_og(_SAMPLE)
    assert og.meta.title == "PDF Processing"
    node = og.nodes[0]
    assert node.name == "pdf_processing"  # slugified
    assert node.dense.startswith("Extract text and tables")
    assert "pdf" in node.keywords
    assert "and" not in node.keywords  # stopword removed
    assert node.steps == [
        "Open the PDF file.",
        "Extract the text layer.",
        "Parse tables into rows.",
    ]
    assert "pull text and tables" in node.full


def test_skill_md_without_frontmatter_uses_fallback_name() -> None:
    og = skill_md_to_og("Just some markdown, no frontmatter.", fallback_name="my-skill")
    assert og.nodes[0].name == "my_skill"
    assert og.nodes[0].full == "Just some markdown, no frontmatter."


def test_skill_md_round_trips_through_serializer() -> None:
    og = skill_md_to_og(_SAMPLE)
    text = serialize_og_file(og)
    # Write/parse to confirm the produced .og is valid and stable.
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pdf_processing.og"
        path.write_text(text, encoding="utf-8")
        reparsed = parse_og_file(str(path))
    assert reparsed.nodes[0].name == "pdf_processing"
    assert reparsed.nodes[0].steps == og.nodes[0].steps


def test_engine_import_skill_md_writes_and_hotloads(tmp_path: Path) -> None:
    md = tmp_path / "pdf.md"
    md.write_text(_SAMPLE, encoding="utf-8")

    engine = SkillEngine()
    engine.load_directory(tmp_path)  # sets _skills_dir
    result = engine.import_skill_md(md)

    assert result["status"] == "imported"
    assert result["name"] == "pdf_processing"
    out = Path(result["path"])
    assert out.exists()
    assert out.parent == tmp_path / "imported"

    # Immediately searchable + loadable via the 3-pass engine.
    assert "pdf_processing" in {r["name"] for r in engine.search("pdf")}
    assert "Open the PDF file." in engine.resolve_node("pdf_processing")
