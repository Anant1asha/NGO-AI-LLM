"""Tests for the `hachi skill changelog` CLI command — surfaces a skill's
version + ::changelog entries (engine.get_node_changelog), the .og delta-load."""

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"

# A skill file WITH a ::changelog block (the fixture sample_skill.og has none).
_VERSIONED_OG = """\
::meta
  title: Versioned Skill
  version: 2.1.0
  updated: 2026-06-07

::index
  versioned_skill | skill | all | 0.9 | versioned, demo

::changelog
  2026-06-01 | added | versioned_skill | initial version
  2026-06-07 | updated | versioned_skill | tightened the steps

::node[versioned_skill]
->[:role=skill]
->[:keywords=versioned, demo]
::dense
versioned|demo|delta-load
"""


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    shutil.copy(FIXTURE, skills_dir / "sample_skill.og")  # deploy_to_prod: v1.0.0, no changelog
    (skills_dir / "versioned.og").write_text(_VERSIONED_OG, encoding="utf-8")
    monkeypatch.setattr("hachi.gateway.workspace.get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)  # isolate usage store
    return skills_dir


def test_skill_changelog_json_lists_entries(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "changelog", "versioned_skill", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["name"] == "versioned_skill"
    assert payload["version"] == "2.1.0"
    assert payload["updated"] == "2026-06-07"
    actions = [e["action"] for e in payload["changelog"]]
    assert actions == ["added", "updated"]


def test_skill_changelog_human_readable(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "changelog", "versioned_skill"])
    assert result.exit_code == 0, result.output
    assert "2.1.0" in result.output
    assert "added" in result.output
    assert "tightened the steps" in result.output


def test_skill_changelog_empty_when_no_block(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    # deploy_to_prod's file has version but no ::changelog block.
    result = runner.invoke(app, ["skill", "changelog", "deploy_to_prod"])
    assert result.exit_code == 0, result.output
    assert "no changelog entries" in result.output


def test_skill_changelog_not_found_exits_nonzero(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "changelog", "ghost_skill"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
