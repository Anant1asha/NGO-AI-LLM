"""Tests for ObjectGraph visualization (Mermaid / Graphviz DOT renderers + CLI)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.og_engine.graph_viz import (
    render_dot,
    render_graph,
    render_html,
    render_mermaid,
)

runner = CliRunner()

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"

# deploy_to_prod -> run_tests; secret_rotation + run_tests have no deps.
_GRAPH = {
    "skill_count": 3,
    "edge_count": 1,
    "edges": [["deploy_to_prod", "run_tests"]],
    "roots": ["deploy_to_prod", "secret_rotation"],
    "missing": [],
    "cyclic": [],
    "nodes": [
        {"name": "deploy_to_prod", "role": "skill", "direct": ["run_tests"], "has_cycle": False},
        {"name": "run_tests", "role": "skill", "direct": [], "has_cycle": False},
        {"name": "secret_rotation", "role": "skill", "direct": [], "has_cycle": False},
    ],
}


# --- pure renderers ------------------------------------------------------
def test_mermaid_has_header_nodes_and_edge() -> None:
    out = render_mermaid(_GRAPH)
    assert out.startswith("graph TD")
    assert '["deploy_to_prod"]' in out
    assert '["run_tests"]' in out
    # the edge between the slugged ids
    assert "deploy_to_prod --> run_tests" in out
    # root styling for an entry point
    assert "deploy_to_prod[" in out and ":::root" in out
    assert "classDef root" in out


def test_mermaid_slugs_unsafe_ids_but_keeps_label() -> None:
    graph = {
        "nodes": [{"name": "anthropic/claude", "role": "skill", "direct": [], "has_cycle": False}],
        "edges": [],
        "roots": ["anthropic/claude"],
        "missing": [],
        "cyclic": [],
    }
    out = render_mermaid(graph)
    assert "anthropic_claude[" in out  # id slugged
    assert '"anthropic/claude"' in out  # label preserves the real name


def test_mermaid_marks_missing_and_cycles() -> None:
    graph = {
        "nodes": [{"name": "a", "role": "skill", "direct": ["ghost"], "has_cycle": True}],
        "edges": [["a", "ghost"]],
        "roots": [],
        "missing": ["ghost"],
        "cyclic": ["a"],
    }
    out = render_mermaid(graph)
    assert ":::cycle" in out
    assert '"ghost (missing)"' in out
    assert ":::missing" in out


def test_dot_is_valid_digraph_with_edges() -> None:
    out = render_dot(_GRAPH)
    assert out.startswith("digraph skills {")
    assert out.rstrip().endswith("}")
    assert '"deploy_to_prod" -> "run_tests";' in out
    assert '"deploy_to_prod" [fillcolor=' in out


def test_html_is_self_contained_with_embedded_data() -> None:
    out = render_html(_GRAPH)
    assert out.startswith("<!DOCTYPE html>")
    assert "vis-network" in out  # the interactive graph library (CDN)
    # node/edge data embedded as JSON (no separate data file needed)
    assert '"id": "deploy_to_prod"' in out
    assert '"from": "deploy_to_prod"' in out and '"to": "run_tests"' in out
    # counts surfaced in the legend, and no leftover placeholders
    assert "3 skills" in out
    assert "__NODES__" not in out and "__COUNT__" not in out


def test_html_marks_missing_nodes() -> None:
    graph = {
        "skill_count": 1,
        "edge_count": 1,
        "nodes": [{"name": "a", "role": "skill", "direct": ["ghost"], "has_cycle": False}],
        "edges": [["a", "ghost"]],
        "roots": [],
        "missing": ["ghost"],
        "cyclic": [],
    }
    out = render_html(graph)
    assert "(missing)" in out
    assert '"borderDashes"' in out  # missing nodes drawn dashed


def test_render_graph_dispatch_and_bad_format() -> None:
    assert render_graph(_GRAPH, "mermaid").startswith("graph TD")
    assert render_graph(_GRAPH, "DOT").startswith("digraph")  # case-insensitive
    assert render_graph(_GRAPH, "html").startswith("<!DOCTYPE html>")
    with pytest.raises(ValueError):
        render_graph(_GRAPH, "svg")


# --- CLI -----------------------------------------------------------------
def _isolate(monkeypatch, tmp_path: Path) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    shutil.copy(FIXTURE, skills_dir / "sample_skill.og")
    monkeypatch.setattr("hachi.gateway.workspace.get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return skills_dir


def test_cli_viz_mermaid_to_stdout(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "viz", "--format", "mermaid"])
    assert result.exit_code == 0, result.output
    assert "graph TD" in result.output
    assert "deploy_to_prod --> run_tests" in result.output


def test_cli_viz_dot_to_file(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    out_file = tmp_path / "skills.dot"
    result = runner.invoke(app, ["skill", "viz", "-f", "dot", "-o", str(out_file)])
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert content.startswith("digraph skills {")
    assert '"deploy_to_prod" -> "run_tests";' in content


def test_cli_viz_html_to_file(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    out_file = tmp_path / "skills.html"
    result = runner.invoke(app, ["skill", "viz", "-f", "html", "-o", str(out_file)])
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    assert "vis-network" in content
    assert '"id": "deploy_to_prod"' in content


def test_cli_viz_bad_format_exits_2(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "viz", "--format", "png"])
    assert result.exit_code == 2
    assert "Unknown format" in result.output
