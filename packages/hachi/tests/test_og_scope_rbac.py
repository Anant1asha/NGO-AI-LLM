"""Tests for .og scope-based RBAC enforcement in SkillEngine.

The parser's ``OGFile.filter_by_scope`` has always existed, but ``SkillEngine``
previously ignored it — every agent role could see every node.  These tests
verify that scope filtering is now applied at query time in all four engine
methods: ``search``, ``list_all_skills``, ``peek``, and ``resolve_node`` (and
their dependent accessors ``get_node`` / ``get_all_nodes``).

The fixture ``tests/fixtures/sample_skill.og`` contains:
  - ``deploy_to_prod``   scope=all          — always visible
  - ``run_tests``        scope=all          — always visible
  - ``secret_rotation``  scope=orchestrator — hidden from non-orchestrators
"""

from __future__ import annotations

from pathlib import Path

from hachi.og_engine.engine import SkillEngine

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"

# Orchestrator-scoped node name in the fixture.
_ORCH_NODE = "secret_rotation"
# Public nodes always visible.
_PUBLIC_NODES = {"deploy_to_prod", "run_tests"}


def _engine(agent_role: str) -> SkillEngine:
    engine = SkillEngine(agent_role=agent_role)
    engine.load_file(FIXTURE)
    return engine


# ------------------------------------------------------------------ #
# search()                                                            #
# ------------------------------------------------------------------ #


def test_search_hides_orchestrator_node_from_worker() -> None:
    engine = _engine("worker")
    names = {r["name"] for r in engine.search("secret")}
    assert _ORCH_NODE not in names


def test_search_shows_orchestrator_node_to_orchestrator() -> None:
    engine = _engine("orchestrator")
    names = {r["name"] for r in engine.search("secret")}
    assert _ORCH_NODE in names


def test_search_public_nodes_always_visible() -> None:
    for role in ("worker", "all", "orchestrator", "*"):
        engine = _engine(role)
        names = {r["name"] for r in engine.search("deploy")}
        assert "deploy_to_prod" in names, f"deploy_to_prod hidden for role={role!r}"


def test_search_bypass_sees_all_nodes() -> None:
    engine = _engine("*")
    names = {r["name"] for r in engine.search("secret")}
    assert _ORCH_NODE in names


# ------------------------------------------------------------------ #
# list_all_skills()                                                   #
# ------------------------------------------------------------------ #


def test_list_hides_orchestrator_node_from_worker() -> None:
    engine = _engine("all")
    names = {n["name"] for n in engine.list_all_skills()}
    assert _ORCH_NODE not in names
    assert _PUBLIC_NODES.issubset(names)


def test_list_shows_orchestrator_node_to_orchestrator() -> None:
    engine = _engine("orchestrator")
    names = {n["name"] for n in engine.list_all_skills()}
    assert _ORCH_NODE in names


def test_list_bypass_shows_all() -> None:
    engine = _engine("*")
    names = {n["name"] for n in engine.list_all_skills()}
    assert _ORCH_NODE in names
    assert _PUBLIC_NODES.issubset(names)


# ------------------------------------------------------------------ #
# peek()                                                              #
# ------------------------------------------------------------------ #


def test_peek_returns_error_for_hidden_node() -> None:
    engine = _engine("worker")
    result = engine.peek([_ORCH_NODE])
    assert "error" in result[_ORCH_NODE]


def test_peek_returns_dense_for_allowed_node() -> None:
    engine = _engine("orchestrator")
    result = engine.peek([_ORCH_NODE])
    assert "error" not in result[_ORCH_NODE]
    assert result[_ORCH_NODE]["dense"]


def test_peek_public_nodes_always_accessible() -> None:
    engine = _engine("worker")
    result = engine.peek(["deploy_to_prod"])
    assert "error" not in result["deploy_to_prod"]


# ------------------------------------------------------------------ #
# resolve_node()                                                      #
# ------------------------------------------------------------------ #


def test_resolve_returns_not_found_for_hidden_node() -> None:
    engine = _engine("worker")
    out = engine.resolve_node(_ORCH_NODE)
    assert "not found" in out.lower()


def test_resolve_returns_content_for_allowed_node() -> None:
    engine = _engine("orchestrator")
    out = engine.resolve_node(_ORCH_NODE)
    assert _ORCH_NODE in out
    assert "not found" not in out.lower()


def test_resolve_public_node_always_works() -> None:
    engine = _engine("all")
    out = engine.resolve_node("run_tests")
    assert "run_tests" in out


# ------------------------------------------------------------------ #
# get_node() and get_all_nodes()                                      #
# ------------------------------------------------------------------ #


def test_get_node_returns_none_when_hidden() -> None:
    engine = _engine("worker")
    assert engine.get_node(_ORCH_NODE) is None


def test_get_node_returns_node_when_allowed() -> None:
    engine = _engine("orchestrator")
    node = engine.get_node(_ORCH_NODE)
    assert node is not None
    assert node.name == _ORCH_NODE


def test_get_all_nodes_filters_by_role() -> None:
    worker_engine = _engine("worker")
    worker_names = {n.name for n in worker_engine.get_all_nodes()}
    assert _ORCH_NODE not in worker_names

    orch_engine = _engine("orchestrator")
    orch_names = {n.name for n in orch_engine.get_all_nodes()}
    assert _ORCH_NODE in orch_names


# ------------------------------------------------------------------ #
# node_count property respects role                                   #
# ------------------------------------------------------------------ #


def test_node_count_excludes_hidden_nodes() -> None:
    # fixture has 3 nodes total; worker only sees 2
    worker_engine = _engine("worker")
    orch_engine = _engine("orchestrator")
    assert worker_engine.node_count < orch_engine.node_count


def test_default_engine_is_bypass() -> None:
    """Backward-compat: SkillEngine() with no args uses '*' (bypass) so CLI tools
    and existing callers that pass no role still see every node."""
    engine = SkillEngine()
    engine.load_file(FIXTURE)
    names = {n["name"] for n in engine.list_all_skills()}
    assert _ORCH_NODE in names  # default bypasses RBAC
