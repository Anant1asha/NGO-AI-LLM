"""Tests for the `hachi skill deps` CLI command — surfaces the .og
typed dependency-chain resolver (engine.get_dependency_chain)."""

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


def test_skill_deps_json_resolves_chain(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "deps", "deploy_to_prod", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["name"] == "deploy_to_prod"
    assert "run_tests" in payload["chain"]  # fixture: deploy_to_prod requires run_tests
    assert payload["has_cycle"] is False


def test_skill_deps_human_readable(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "deps", "deploy_to_prod"])
    assert result.exit_code == 0, result.output
    assert "run_tests" in result.output
    assert "dependencies" in result.output


def test_skill_deps_not_found_exits_nonzero(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "deps", "ghost_skill"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
