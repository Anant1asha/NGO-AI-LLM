"""Tests for .og typed dependency traversal: SkillEngine.get_dependency_chain
and the skill_dependencies tool."""

from __future__ import annotations

import json

from hachi.core.loop import ToolRegistry
from hachi.og_engine.engine import SkillEngine
from hachi.og_engine.parser import OGNode
from hachi.tools.og_tools import _make_skill_dependencies, register_og_tools


def _node(name: str, requires=None, edges=None) -> OGNode:
    return OGNode(name=name, source_file="test_deps.og", requires=requires or [], edges=edges or [])


def _engine(nodes: list[OGNode]) -> SkillEngine:
    eng = SkillEngine()
    for n in nodes:
        qid = f"test_deps:{n.name}"
        eng._nodes[qid] = n
        eng._bare_name_index.setdefault(n.name, []).append(qid)
    return eng


def test_transitive_chain() -> None:
    eng = _engine([_node("a", requires=["b"]), _node("b", requires=["c"]), _node("c")])
    r = eng.get_dependency_chain("a")
    assert r is not None
    assert r["direct"] == ["b"]
    assert r["chain"] == ["b", "c"]
    assert r["missing"] == []
    assert r["has_cycle"] is False


def test_missing_dependency() -> None:
    r = _engine([_node("a", requires=["x"])]).get_dependency_chain("a")
    assert r is not None
    assert r["missing"] == ["x"]
    assert r["chain"] == []


def test_cycle_detected() -> None:
    r = _engine([_node("a", requires=["b"]), _node("b", requires=["a"])]).get_dependency_chain("a")
    assert r is not None
    assert r["has_cycle"] is True
    assert r["chain"] == ["b"]  # 'a' not re-added


def test_edge_based_requires() -> None:
    r = _engine([_node("a", edges=["->[:requires] b"]), _node("b")]).get_dependency_chain("a")
    assert r is not None
    assert "b" in r["direct"]
    assert r["chain"] == ["b"]


def test_diamond_visits_shared_dep_once_no_false_cycle() -> None:
    eng = _engine(
        [
            _node("a", requires=["b", "c"]),
            _node("b", requires=["d"]),
            _node("c", requires=["d"]),
            _node("d"),
        ]
    )
    r = eng.get_dependency_chain("a")
    assert r is not None
    assert r["has_cycle"] is False
    assert r["chain"].count("d") == 1
    assert set(r["chain"]) == {"b", "c", "d"}


def test_unknown_returns_none() -> None:
    assert SkillEngine().get_dependency_chain("nope") is None


def test_tool_json_and_not_found() -> None:
    tool = _make_skill_dependencies(_engine([_node("a", requires=["b"]), _node("b")]))
    data = json.loads(tool("a"))
    assert data["chain"] == ["b"]
    assert "not found" in tool("ghost")


def test_register_includes_skill_dependencies() -> None:
    reg = ToolRegistry()
    register_og_tools(reg, SkillEngine())
    names = {s["name"] for s in reg.get_schemas()}
    assert "skill_dependencies" in names
