"""Tests for .og delta-loading: SkillEngine.get_node_changelog + the
skill_changelog tool. Lets an agent check a skill's version/changelog cheaply
instead of re-loading its heavy content."""

from __future__ import annotations

import json
from pathlib import Path

from hachi.core.loop import ToolRegistry
from hachi.og_engine.engine import SkillEngine
from hachi.tools.og_tools import _make_skill_changelog, register_og_tools


def test_get_node_changelog_after_create_and_refine(tmp_path: Path) -> None:
    eng = SkillEngine()
    r1 = eng.upsert_skill(
        name="Rotate Keys",
        keywords=["rotate"],
        dense="rotate|keys",
        full="do it",
        reason="initial",
        skills_dir=tmp_path,
    )
    assert r1["status"] == "created"
    slug = r1["name"]

    cl = eng.get_node_changelog(slug)
    assert cl is not None
    assert cl["name"] == slug
    assert cl["version"] == "1.0.0"
    assert len(cl["changelog"]) == 1
    assert cl["changelog"][0]["action"] == "added"

    # Refine the same skill → version bumps, changelog grows.
    r2 = eng.upsert_skill(
        name="Rotate Keys",
        keywords=["rotate"],
        dense="rotate|keys|v2",
        full="do it better",
        reason="tightened",
        skills_dir=tmp_path,
    )
    assert r2["status"] == "updated"

    cl2 = eng.get_node_changelog(slug)
    assert cl2 is not None
    assert cl2["version"] == "1.0.1"
    assert len(cl2["changelog"]) == 2
    assert cl2["changelog"][-1]["action"] == "updated"


def test_get_node_changelog_unknown_returns_none() -> None:
    assert SkillEngine().get_node_changelog("does_not_exist") is None


def test_skill_changelog_tool(tmp_path: Path) -> None:
    eng = SkillEngine()
    r = eng.upsert_skill(
        name="Deploy", keywords=["deploy"], dense="deploy|prod", skills_dir=tmp_path
    )
    tool = _make_skill_changelog(eng)

    data = json.loads(tool(r["name"]))
    assert data["name"] == r["name"]
    assert data["version"] == "1.0.0"
    assert isinstance(data["changelog"], list)

    assert "not found" in tool("ghost_skill")


def test_register_og_tools_includes_skill_changelog() -> None:
    reg = ToolRegistry()
    register_og_tools(reg, SkillEngine())
    names = {s["name"] for s in reg.get_schemas()}
    assert "skill_changelog" in names
