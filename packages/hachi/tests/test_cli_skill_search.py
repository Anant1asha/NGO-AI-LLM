"""Tests for the `hachi skill search` CLI command — surfaces the .og Pass-1
keyword routing (engine.search) the agent uses to pick which skill to load."""

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


def test_skill_search_json_matches_by_keyword(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "search", "deploy", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["query"] == "deploy"
    names = {m["name"] for m in payload["matches"]}
    assert "deploy_to_prod" in names  # fixture keyword: deploy


def test_skill_search_fuzzy_keyword(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "search", "pytest", "--json"])
    assert result.exit_code == 0, result.output
    names = {m["name"] for m in json.loads(result.output)["matches"]}
    assert "run_tests" in names  # fixture keyword: pytest


def test_skill_search_human_readable(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "search", "secret"])
    assert result.exit_code == 0, result.output
    assert "secret_rotation" in result.output
    assert "matched" in result.output


def test_skill_search_no_match_is_friendly(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "search", "zzzznotarealkeyword"])
    assert result.exit_code == 0  # an empty result is not an error
    assert "No skills matched" in result.output


def test_skill_search_no_match_json_empty(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "search", "zzzznotarealkeyword", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["matches"] == []
