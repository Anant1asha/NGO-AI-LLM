"""Tests for ::traverse hint integration.

Covers:
1. search() priority ordering — high > normal > low nodes rank first
2. peek() includes traverse dict in results
3. get_traverse_hints() returns correct data for nodes with ::traverse block
4. get_traverse_hints() returns empty traverse dict for nodes without ::traverse
5. get_traverse_hints() returns None for unknown node
6. skill traverse CLI — JSON output with correct keys
7. skill traverse CLI — no hints message for node without ::traverse
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.og_engine.engine import SkillEngine

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_og(tmp_path: Path, filename: str, content: str) -> None:
    (tmp_path / filename).write_text(textwrap.dedent(content), encoding="utf-8")


def _engine_with_priority_nodes(tmp_path: Path) -> SkillEngine:
    """Build an engine with three keyword-matching nodes at different priorities."""
    _write_og(
        tmp_path,
        "high.og",
        """\
        ::node[high_node]
        ->[:keywords=deploy, production]

        ::dense
        Deploy (HIGH priority)

        ::traverse
        priority: high
        """,
    )
    _write_og(
        tmp_path,
        "low.og",
        """\
        ::node[low_node]
        ->[:keywords=deploy, production]

        ::dense
        Deploy (LOW priority)

        ::traverse
        priority: low
        """,
    )
    _write_og(
        tmp_path,
        "normal.og",
        """\
        ::node[normal_node]
        ->[:keywords=deploy, production]

        ::dense
        Deploy (normal priority)
        """,
    )
    engine = SkillEngine()
    engine.load_directory(tmp_path)
    return engine


# ---------------------------------------------------------------------------
# 1. search() priority ordering
# ---------------------------------------------------------------------------


def test_search_high_priority_node_ranked_first(tmp_path: Path) -> None:
    engine = _engine_with_priority_nodes(tmp_path)
    results = engine.search("deploy production")
    assert results, "Expected search results"
    names = [r["name"] for r in results]
    # high_node must appear before low_node
    assert "high_node" in names and "low_node" in names
    assert names.index("high_node") < names.index("low_node")


def test_search_low_priority_node_ranked_last(tmp_path: Path) -> None:
    engine = _engine_with_priority_nodes(tmp_path)
    results = engine.search("deploy production")
    names = [r["name"] for r in results]
    # low_node must be last
    assert names[-1] == "low_node"


# ---------------------------------------------------------------------------
# 2. peek() includes traverse dict
# ---------------------------------------------------------------------------


def test_peek_includes_traverse_hints(tmp_path: Path) -> None:
    _write_og(
        tmp_path,
        "with_traverse.og",
        """\
        ::node[with_traverse]
        ->[:keywords=test]

        ::dense
        Test node

        ::traverse
        priority: high
        entry: sub_node
        depth: 2
        """,
    )
    engine = SkillEngine()
    engine.load_directory(tmp_path)
    result = engine.peek(["with_traverse"])
    assert "with_traverse" in result
    traverse = result["with_traverse"].get("traverse")
    assert traverse is not None
    assert traverse.get("priority") == "high"
    assert traverse.get("entry") == "sub_node"
    assert traverse.get("depth") == "2"


def test_peek_traverse_empty_for_node_without_traverse(tmp_path: Path) -> None:
    _write_og(
        tmp_path,
        "no_traverse.og",
        """\
        ::node[no_traverse]
        ->[:keywords=test]

        ::dense
        No traverse block
        """,
    )
    engine = SkillEngine()
    engine.load_directory(tmp_path)
    result = engine.peek(["no_traverse"])
    assert result["no_traverse"]["traverse"] == {}


# ---------------------------------------------------------------------------
# 3. get_traverse_hints() returns correct data
# ---------------------------------------------------------------------------


def test_get_traverse_hints_full_data(tmp_path: Path) -> None:
    _write_og(
        tmp_path,
        "rich.og",
        """\
        ::node[rich_node]
        ->[:keywords=rich]

        ::dense
        Rich node

        ::traverse
        priority: high
        entry: start_here
        depth: 3
        """,
    )
    engine = SkillEngine()
    engine.load_directory(tmp_path)
    hints = engine.get_traverse_hints("rich_node")
    assert hints is not None
    assert hints["name"] == "rich_node"
    assert hints["traverse"]["priority"] == "high"
    assert hints["traverse"]["entry"] == "start_here"
    assert hints["traverse"]["depth"] == "3"


# ---------------------------------------------------------------------------
# 4. get_traverse_hints() returns empty traverse for nodes without ::traverse
# ---------------------------------------------------------------------------


def test_get_traverse_hints_empty_for_no_traverse_block(tmp_path: Path) -> None:
    _write_og(
        tmp_path,
        "plain.og",
        """\
        ::node[plain_node]
        ->[:keywords=plain]

        ::dense
        Plain
        """,
    )
    engine = SkillEngine()
    engine.load_directory(tmp_path)
    hints = engine.get_traverse_hints("plain_node")
    assert hints is not None
    assert hints["traverse"] == {}


# ---------------------------------------------------------------------------
# 5. get_traverse_hints() returns None for unknown node
# ---------------------------------------------------------------------------


def test_get_traverse_hints_returns_none_for_unknown(tmp_path: Path) -> None:
    engine = SkillEngine()
    engine.load_directory(tmp_path)
    assert engine.get_traverse_hints("does_not_exist") is None


# ---------------------------------------------------------------------------
# 6. skill traverse CLI — JSON output
# ---------------------------------------------------------------------------


def test_skill_traverse_cli_json(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _write_og(
        skills_dir,
        "t.og",
        """\
        ::node[my_node]
        ->[:keywords=x]

        ::dense
        X

        ::traverse
        priority: high
        entry: child
        """,
    )
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["skill", "traverse", "my_node", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["name"] == "my_node"
    assert data["traverse"]["priority"] == "high"
    assert data["traverse"]["entry"] == "child"


# ---------------------------------------------------------------------------
# 7. skill traverse CLI — no hints message
# ---------------------------------------------------------------------------


def test_skill_traverse_cli_no_hints(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _write_og(
        skills_dir,
        "plain.og",
        """\
        ::node[plain_node]
        ->[:keywords=plain]

        ::dense
        Plain
        """,
    )
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["skill", "traverse", "plain_node"])
    assert result.exit_code == 0, result.output
    assert "no ::traverse hints" in result.output
