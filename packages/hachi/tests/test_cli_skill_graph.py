"""Tests for the `hachi skill graph` CLI command — whole-library dependency
graph (adjacency + roots + missing + cycles) built from typed `requires` edges."""

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


def test_skill_graph_json_adjacency_and_roots(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "graph", "--json"])
    assert result.exit_code == 0, result.output
    graph = json.loads(result.output)

    # fixture: deploy_to_prod -> run_tests; secret_rotation, run_tests have no deps
    assert graph["skill_count"] == 3
    assert ["deploy_to_prod", "run_tests"] in graph["edges"]
    # run_tests is depended on, so it is NOT a root; deploy_to_prod IS a root.
    assert "deploy_to_prod" in graph["roots"]
    assert "run_tests" not in graph["roots"]
    assert graph["missing"] == []
    assert graph["cyclic"] == []

    by_name = {n["name"]: n for n in graph["nodes"]}
    assert by_name["deploy_to_prod"]["direct"] == ["run_tests"]
    assert by_name["run_tests"]["direct"] == []


def test_skill_graph_human_readable(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "graph"])
    assert result.exit_code == 0, result.output
    assert "Skill dependency graph" in result.output
    assert "deploy_to_prod" in result.output
    assert "run_tests" in result.output
    assert "entry-point roots" in result.output


def test_skill_graph_flags_missing_dependency(monkeypatch, tmp_path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    # A skill that requires a node which is not loaded anywhere.
    (skills_dir / "lonely.og").write_text(
        "::index\n  lonely | skill | all | 0.9 | lonely\n\n"
        "::node[lonely]\n->[:role=skill]\n->[:requires=ghost_dep]\n->[:keywords=lonely]\n"
        "::dense\nlonely\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("hachi.gateway.workspace.get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = runner.invoke(app, ["skill", "graph", "--json"])
    assert result.exit_code == 0, result.output
    graph = json.loads(result.output)
    assert "ghost_dep" in graph["missing"]


def test_skill_graph_empty_dir(monkeypatch, tmp_path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    monkeypatch.setattr("hachi.gateway.workspace.get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = runner.invoke(app, ["skill", "graph"])
    assert result.exit_code == 0, result.output
    assert "No skills loaded" in result.output
