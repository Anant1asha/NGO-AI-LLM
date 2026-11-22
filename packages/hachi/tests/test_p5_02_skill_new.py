"""P5-02 tests — hachi skill new scaffold command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from hachi.cli.commands.skill import skill_app
from hachi.og_engine.parser import parse_og_file

runner = CliRunner()


def test_skill_new_creates_file_at_default_path(tmp_path: Path) -> None:
    """Running `skill new <name>` without --output creates <name>.og in cwd."""
    result = runner.invoke(skill_app, ["new", "hello-world"], catch_exceptions=False)
    assert result.exit_code == 0, result.output

    default_file = Path("hello-world.og")
    assert default_file.exists(), "Expected hello-world.og to be created in cwd"
    assert "Created" in result.output

    # Clean up
    default_file.unlink(missing_ok=True)


def test_skill_new_output_flag_respects_path(tmp_path: Path) -> None:
    """--output directs the file to the specified path."""
    out = tmp_path / "custom" / "my_skill.og"
    out.parent.mkdir(parents=True, exist_ok=True)

    result = runner.invoke(
        skill_app, ["new", "my-skill", "--output", str(out)], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert out.exists(), f"Expected file at {out}"
    assert "Created" in result.output
    # Rich may line-wrap long paths; check the filename is somewhere in the output
    assert out.name in result.output


def test_skill_new_domain_appears_in_output(tmp_path: Path) -> None:
    """--domain value is written into the generated .og file."""
    out = tmp_path / "domain-test.og"
    result = runner.invoke(
        skill_app,
        ["new", "domain-test", "--output", str(out), "--domain", "productivity"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    content = out.read_text(encoding="utf-8")
    assert "productivity" in content, "domain should appear in the generated file"


def test_skill_new_generates_parseable_og_file(tmp_path: Path) -> None:
    """The generated file must be parseable by parse_og_file without error."""
    out = tmp_path / "parseable-skill.og"
    result = runner.invoke(
        skill_app,
        ["new", "parseable-skill", "--output", str(out), "--domain", "test", "--author", "ci"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert out.exists()

    og = parse_og_file(str(out))
    assert og.meta.title == "Parseable Skill"
    assert og.meta.domain == "test"
    assert len(og.nodes) == 1
    node = og.nodes[0]
    assert node.name == "parseable-skill"
    assert node.role == "skill"
    assert node.dense != ""
    assert len(node.steps) >= 1
    assert len(og.index) == 1
    assert og.index[0].node_id == "parseable-skill"
