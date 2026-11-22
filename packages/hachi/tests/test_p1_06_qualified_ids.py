"""Tests for P1-06: Qualified node IDs, collision detection, brain exclusion.

Covers the four acceptance criteria from the execution plan:
1. Boot test — shipped library loads with zero node-ID collisions
2. Collision fixture — two files with the same node name: second skipped, error logged
3. Bare-name shim — _resolve_name() disambiguates unambiguous names, None on ambiguous
4. Brain exclusion — search() never returns brain.og nodes
"""

from __future__ import annotations

import logging
from pathlib import Path

from hachi.core.skill_packs import _default_skills_root
from hachi.og_engine.engine import SkillEngine
from hachi.og_engine.parser import OGNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_og_file(directory: Path, stem: str, node_name: str) -> Path:
    """Write a minimal .og file with one node and return its path."""
    path = directory / f"{stem}.og"
    path.write_text(
        f"::node[{node_name}]\n->[:role=skill]\n->[:keywords=test]\n\n::dense\nTest skill.\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# 1. Boot test: shipped default_skills loads with zero collisions
# ---------------------------------------------------------------------------

def test_shipped_skills_load_with_zero_collisions() -> None:
    """Every node in default_skills/ must have a unique qualified ID.

    This guards against accidentally shipping two .og files with the same
    node name.  A collision would cause the second file's node to be silently
    dropped (engine logs the error but continues).
    """
    eng = SkillEngine()
    eng.load_directory(_default_skills_root())
    collision_errors = [
        s for s in eng._skipped_files
        if "collision" in s.get("error", "")
    ]
    assert collision_errors == [], (
        f"Shipped skills have node-ID collisions: {collision_errors}"
    )


# ---------------------------------------------------------------------------
# 2. Collision detection: second node with same name is skipped + logged
# ---------------------------------------------------------------------------

def test_collision_detection_skips_second_file(tmp_path: Path, caplog) -> None:
    """Two .og files with the same node name → second load is skipped and logged."""
    dir_a = tmp_path / "skills_a"
    dir_a.mkdir()
    dir_b = tmp_path / "skills_b"
    dir_b.mkdir()

    # Both files have a node named "duplicate_node"
    _make_og_file(dir_a, "file_alpha", "duplicate_node")
    _make_og_file(dir_b, "file_alpha", "duplicate_node")  # same stem + same node name → collision

    eng = SkillEngine()
    with caplog.at_level(logging.ERROR, logger="hachi.og_engine.engine"):
        eng.load_file(dir_a / "file_alpha.og")
        eng.load_file(dir_b / "file_alpha.og")

    # Exactly one node in the index (the first one wins)
    matching = [qid for qid in eng._nodes if ":duplicate_node" in qid]
    assert len(matching) == 1, (
        f"Expected 1 node for 'duplicate_node', got {len(matching)}: {matching}"
    )

    # Collision must appear in _skipped_files
    assert any("collision" in s.get("error", "") for s in eng._skipped_files), (
        f"Expected a collision entry in _skipped_files, got: {eng._skipped_files}"
    )

    # Collision must be logged at ERROR
    collision_logs = [
        r for r in caplog.records
        if "collision" in r.message.lower() and r.levelno >= logging.ERROR
    ]
    records_summary = [(r.levelno, r.message) for r in caplog.records]
    assert collision_logs, f"Expected ERROR log for collision, records: {records_summary}"


def test_different_stems_same_node_name_both_survive_as_ambiguous(tmp_path: Path) -> None:
    """Two .og files with *different* stems but the same node name are NOT a collision.

    Both nodes get distinct qualified IDs (alpha:shared_node, beta:shared_node).
    However, the bare name becomes ambiguous — _resolve_name("shared_node") returns None.
    """
    _make_og_file(tmp_path, "alpha", "shared_node")
    _make_og_file(tmp_path, "beta", "shared_node")

    eng = SkillEngine()
    eng.load_file(tmp_path / "alpha.og")
    eng.load_file(tmp_path / "beta.og")

    # Both survive with distinct qualified IDs
    assert eng._nodes.get("alpha:shared_node") is not None
    assert eng._nodes.get("beta:shared_node") is not None
    # No collision in _skipped_files
    assert not [s for s in eng._skipped_files if "collision" in s.get("error", "")]
    # Bare name is now ambiguous — must use qualified ID
    assert eng._resolve_name("shared_node") is None
    assert eng._resolve_name("alpha:shared_node") == "alpha:shared_node"
    assert eng._resolve_name("beta:shared_node") == "beta:shared_node"


# ---------------------------------------------------------------------------
# 3. Bare-name resolution via _resolve_name()
# ---------------------------------------------------------------------------

def test_resolve_unambiguous_bare_name(tmp_path: Path) -> None:
    """A bare name maps to its single qualified ID when unambiguous."""
    _make_og_file(tmp_path, "my_skill", "run_tests")
    eng = SkillEngine()
    eng.load_file(tmp_path / "my_skill.og")

    qid = eng._resolve_name("run_tests")
    assert qid == "my_skill:run_tests"


def test_resolve_qualified_id_directly(tmp_path: Path) -> None:
    """A qualified ID resolves directly without touching _bare_name_index."""
    _make_og_file(tmp_path, "my_skill", "run_tests")
    eng = SkillEngine()
    eng.load_file(tmp_path / "my_skill.og")

    assert eng._resolve_name("my_skill:run_tests") == "my_skill:run_tests"


def test_resolve_unknown_returns_none() -> None:
    """_resolve_name() returns None for a name that has no matching node."""
    eng = SkillEngine()
    assert eng._resolve_name("ghost") is None
    assert eng._resolve_name("ghost:node") is None


def test_resolve_bare_name_ambiguous_returns_none_after_two_stems(tmp_path: Path) -> None:
    """When two files with different stems define the same node name, the bare name
    is ambiguous and _resolve_name() returns None — callers must use qualified IDs."""
    _make_og_file(tmp_path, "alpha", "shared_node")
    _make_og_file(tmp_path, "beta", "shared_node")

    eng = SkillEngine()
    eng.load_file(tmp_path / "alpha.og")
    eng.load_file(tmp_path / "beta.og")

    # Both nodes survive — bare name has 2 candidates, so ambiguous → None
    assert eng._resolve_name("shared_node") is None
    # Qualified IDs always resolve
    assert eng._resolve_name("alpha:shared_node") == "alpha:shared_node"
    assert eng._resolve_name("beta:shared_node") == "beta:shared_node"


def test_resolve_bare_name_when_genuinely_ambiguous(tmp_path: Path) -> None:
    """When two nodes with the same bare name coexist (injected directly),
    _resolve_name() returns None — caller must use the qualified form."""
    eng = SkillEngine()
    # Manually inject two nodes with the same bare name under different stems
    n1 = OGNode(name="tool", source_file="alpha.og")
    n2 = OGNode(name="tool", source_file="beta.og")
    eng._nodes["alpha:tool"] = n1
    eng._nodes["beta:tool"] = n2
    eng._bare_name_index["tool"] = ["alpha:tool", "beta:tool"]

    assert eng._resolve_name("tool") is None  # ambiguous
    assert eng._resolve_name("alpha:tool") == "alpha:tool"  # qualified → works
    assert eng._resolve_name("beta:tool") == "beta:tool"   # qualified → works


# ---------------------------------------------------------------------------
# 4. Brain exclusion: brain.og nodes never appear in search()
# ---------------------------------------------------------------------------

def test_brain_og_nodes_excluded_from_search(tmp_path: Path) -> None:
    """Nodes loaded from brain.og must not appear in skill search results.

    Uses load_file() so the BM25 token index is properly populated, then
    verifies that the brain.og node is excluded from search() while the
    normal skill node is included.
    """
    # Normal skill file
    skill_file = tmp_path / "devops.og"
    skill_file.write_text(
        "::node[run_tests]\n->[:role=skill]\n->[:keywords=test, ci]\n\n"
        "::dense\nRun the test suite.\n",
        encoding="utf-8",
    )
    # brain.og file
    brain_file = tmp_path / "brain.og"
    brain_file.write_text(
        "::node[identity]\n->[:role=config]\n->[:scope=orchestrator]\n"
        "->[:keywords=identity, agent]\n\n::dense\nI am Hachi.\n",
        encoding="utf-8",
    )

    eng = SkillEngine(agent_role="orchestrator")
    eng.load_file(skill_file)
    eng.load_file(brain_file)

    results = eng.search("test")
    names = [r["name"] for r in results]

    assert "identity" not in names, f"brain.og 'identity' must not appear in search: {names}"
    assert "run_tests" in names, f"Normal skill 'run_tests' must appear in search: {names}"


def test_brain_og_node_accessible_via_get_node_for_orchestrator(tmp_path: Path) -> None:
    """brain.og exclusion is search-only; get_node() still works for the orchestrator role."""
    brain_file = tmp_path / "brain.og"
    brain_file.write_text(
        "::node[identity]\n->[:role=config]\n->[:scope=orchestrator]\n->[:keywords=identity]\n\n"
        "::dense\nI am Hachi.\n",
        encoding="utf-8",
    )
    eng = SkillEngine(agent_role="orchestrator")
    eng.load_file(brain_file)

    # get_node goes through _resolve_name → should still resolve
    node = eng.get_node("identity")
    assert node is not None, "Orchestrator should be able to access brain.og nodes via get_node()"
