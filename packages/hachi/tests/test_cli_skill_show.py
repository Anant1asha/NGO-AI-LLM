"""Tests for the `hachi skill show` CLI command — surfaces the .og Pass-2
view (metadata + dense summary + heavy-block manifest) without loading bodies."""

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    shutil.copy(FIXTURE, skills_dir / "sample_skill.og")
    monkeypatch.setattr("hachi.gateway.workspace.get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)  # isolate usage store
    return skills_dir


def test_skill_show_json_surfaces_metadata_and_manifest(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "show", "deploy_to_prod", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["name"] == "deploy_to_prod"
    assert payload["role"] == "skill"
    assert payload["version"] == "1.0.0"  # from the fixture ::meta
    assert "deploy" in payload["keywords"]
    assert payload["requires"] == ["run_tests"]
    assert payload["dense"].startswith("deploy|prod")
    assert payload["warning"]  # has a ::warning block
    # The heavy blocks are advertised with token costs but NOT their content.
    assert "full" in payload["available_blocks"]
    assert "steps" in payload["available_blocks"]
    assert payload["full_load_tokens"] > 0
    assert "multi-step process" not in result.output  # the ::full body is never dumped


def test_skill_show_human_readable(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "show", "deploy_to_prod"])
    assert result.exit_code == 0, result.output
    assert "deploy_to_prod" in result.output
    assert "keywords" in result.output
    assert "full load" in result.output  # token-cost footer


def test_skill_show_dense_only_node(monkeypatch, tmp_path) -> None:
    # run_tests has full/steps but secret_rotation has only dense+full; pick one
    # with no warning to exercise the no-warning branch.
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "show", "secret_rotation"])
    assert result.exit_code == 0, result.output
    assert "secret_rotation" in result.output


def test_skill_show_not_found_exits_nonzero(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "show", "ghost_skill"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
