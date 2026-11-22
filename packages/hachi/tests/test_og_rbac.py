"""Tests for .og scope/RBAC enforcement at query time.

Covers:
  1.  SkillEngine.with_role("worker") hides scope=orchestrator nodes
  2.  SkillEngine.with_role("orchestrator") shows scope=orchestrator nodes
  3.  SkillEngine.with_role("*") bypasses all scope checks
  4.  with_role view shares data (no full copy) with the parent engine
  5.  ToolRegistry.update_handler updates the callable without duplicating schema
  6.  ToolRegistry.update_handler returns False for unknown tool name
  7.  _rebind_og_tools_for_role rebinds registered OG tools to scoped engine
  8.  _rebind_og_tools_for_role skips tools not in the registry (no error)
  9.  _build_scoped_registry with skill_engine + role rebinds OG tools
  10. _build_scoped_registry without engine does NOT rebind (backward-compat)
  11. Sub-agent peek_skill on scope=orchestrator node returns empty result
  12. Main orchestrator peek_skill on scope=orchestrator node returns content
  13. Sub-agent load_skill on scope=orchestrator node returns not-visible error
  14. register_delegation_tools passes skill_engine to _make_delegate_task
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from hachi.core.loop import ToolRegistry
from hachi.og_engine.engine import SkillEngine
from hachi.og_engine.parser import OGNode
from hachi.tools.delegation_tools import (
    _build_scoped_registry,
    _rebind_og_tools_for_role,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(name: str, scope: str = "all") -> OGNode:
    """Return a minimal OGNode with the given name and scope."""
    n = OGNode(name=name, source_file="test_rbac.og")
    n.scope = scope
    return n


def _engine_with_nodes(*nodes: OGNode) -> SkillEngine:
    """Return an engine pre-loaded with the given nodes (bypasses file I/O)."""
    engine = SkillEngine(agent_role="orchestrator")
    for node in nodes:
        qid = f"test_rbac:{node.name}"
        engine._nodes[qid] = node
        engine._bare_name_index.setdefault(node.name, []).append(qid)
        for kw in getattr(node, "keywords", []):
            engine._keyword_index.setdefault(kw, []).append(qid)
    return engine


def _registry_with(tool_name: str, handler=None) -> ToolRegistry:
    registry = ToolRegistry()
    schema = {"name": tool_name}
    registry.register(schema, handler or (lambda: "ok"))
    return registry


# ---------------------------------------------------------------------------
# 1. with_role("worker") hides scope=orchestrator nodes
# ---------------------------------------------------------------------------


def test_with_role_worker_hides_orchestrator_nodes() -> None:
    public_node = _node("public_skill", scope="all")
    private_node = _node("orchestrator_brain", scope="orchestrator")
    engine = _engine_with_nodes(public_node, private_node)

    worker_view = engine.with_role("worker")
    assert worker_view._is_visible(public_node) is True
    assert worker_view._is_visible(private_node) is False


# ---------------------------------------------------------------------------
# 2. with_role("orchestrator") shows scope=orchestrator nodes
# ---------------------------------------------------------------------------


def test_with_role_orchestrator_shows_orchestrator_nodes() -> None:
    private_node = _node("orchestrator_brain", scope="orchestrator")
    engine = _engine_with_nodes(private_node)

    orch_view = engine.with_role("orchestrator")
    assert orch_view._is_visible(private_node) is True


# ---------------------------------------------------------------------------
# 3. with_role("*") bypasses all scope checks
# ---------------------------------------------------------------------------


def test_with_role_star_bypasses_all_checks() -> None:
    private_node = _node("secret", scope="admin")
    engine = _engine_with_nodes(private_node)

    star_view = engine.with_role("*")
    assert star_view._is_visible(private_node) is True


# ---------------------------------------------------------------------------
# 4. with_role view shares data with parent
# ---------------------------------------------------------------------------


def test_with_role_shares_nodes_with_parent() -> None:
    node = _node("shared", scope="all")
    engine = _engine_with_nodes(node)

    view = engine.with_role("worker")
    # Same dictionary objects (identity check)
    assert view._nodes is engine._nodes
    assert view._keyword_index is engine._keyword_index


# ---------------------------------------------------------------------------
# 5. ToolRegistry.update_handler updates callable, no schema duplication
# ---------------------------------------------------------------------------


def test_update_handler_updates_callable_no_schema_duplication() -> None:
    def original() -> str:
        return "original"

    registry = _registry_with("peek_skill", original)

    def new_fn() -> str:
        return "updated"

    schema_count_before = len(registry._schemas)
    result = registry.update_handler("peek_skill", new_fn)

    assert result is True
    assert registry._tools["peek_skill"] is new_fn
    # Schema list must NOT grow
    assert len(registry._schemas) == schema_count_before


# ---------------------------------------------------------------------------
# 6. update_handler returns False for unknown tool
# ---------------------------------------------------------------------------


def test_update_handler_returns_false_for_unknown_tool() -> None:
    registry = _registry_with("known_tool")
    assert registry.update_handler("nonexistent_tool", lambda: None) is False
    # Original tool unaffected
    assert "known_tool" in registry._tools


# ---------------------------------------------------------------------------
# 7. _rebind_og_tools_for_role rebinds registered OG tools
# ---------------------------------------------------------------------------


def test_rebind_og_tools_rebinds_registered_tools() -> None:
    def original_fn() -> str:
        return "original"

    registry = ToolRegistry()
    for name in ("peek_skill", "load_skill", "search_skills"):
        registry.register({"name": name}, original_fn)

    node = _node("public", scope="all")
    engine = _engine_with_nodes(node)
    schema_count_before = len(registry._schemas)

    _rebind_og_tools_for_role(registry, engine, "worker")

    # Handlers updated
    for name in ("peek_skill", "load_skill", "search_skills"):
        assert registry._tools[name] is not original_fn, f"{name} was not rebound"

    # Schema list unchanged (no duplicates added)
    assert len(registry._schemas) == schema_count_before


# ---------------------------------------------------------------------------
# 8. _rebind_og_tools_for_role is silent for unregistered tools
# ---------------------------------------------------------------------------


def test_rebind_og_tools_skips_unregistered_tools() -> None:
    # Registry has NO og tools registered
    registry = ToolRegistry()
    registry.register({"name": "other_tool"}, lambda: "x")

    engine = _engine_with_nodes()
    # Should not raise even though none of the OG tools are registered
    _rebind_og_tools_for_role(registry, engine, "worker")


# ---------------------------------------------------------------------------
# 9. _build_scoped_registry with engine + role rebinds OG tools
# ---------------------------------------------------------------------------


def test_build_scoped_registry_with_engine_rebinds_og_tools() -> None:
    def original_fn() -> str:
        return "parent"

    parent = ToolRegistry()
    for name in ("peek_skill", "load_skill", "search_skills"):
        parent.register({"name": name}, original_fn)

    engine = _engine_with_nodes(_node("skill1"))
    scoped = _build_scoped_registry(parent, skill_engine=engine, sub_agent_role="coder")

    for name in ("peek_skill", "load_skill", "search_skills"):
        assert scoped._tools.get(name) is not original_fn, f"{name} not rebound in scoped"


# ---------------------------------------------------------------------------
# 10. _build_scoped_registry without engine leaves handlers unchanged
# ---------------------------------------------------------------------------


def test_build_scoped_registry_without_engine_preserves_handlers() -> None:
    def original_fn() -> str:
        return "parent"

    parent = ToolRegistry()
    parent.register({"name": "peek_skill"}, original_fn)

    scoped = _build_scoped_registry(parent)
    assert scoped._tools["peek_skill"] is original_fn


# ---------------------------------------------------------------------------
# 11. Sub-agent peek_skill on scope=orchestrator node returns empty
# ---------------------------------------------------------------------------


def test_sub_agent_peek_skill_hides_orchestrator_scoped_nodes(tmp_path: Path) -> None:
    public_node = _node("deploy", scope="all")
    private_node = _node("brain_identity", scope="orchestrator")

    engine = _engine_with_nodes(public_node, private_node)
    worker_engine = engine.with_role("worker")

    # peek() returns a dict: visible nodes → content dict, invisible → {"error": ...}
    results = worker_engine.peek(["brain_identity", "deploy"])
    assert isinstance(results, dict)
    # Public node is accessible
    assert "deploy" in results
    assert "error" not in results["deploy"]
    # Orchestrator-private node is hidden — appears as an error entry
    assert "error" in results["brain_identity"]


# ---------------------------------------------------------------------------
# 12. Main orchestrator peek_skill on scope=orchestrator node returns content
# ---------------------------------------------------------------------------


def test_orchestrator_peek_skill_shows_orchestrator_scoped_nodes() -> None:
    private_node = _node("brain_identity", scope="orchestrator")
    private_node.dense = "I am Hachi, the orchestrator."

    engine = _engine_with_nodes(private_node)
    orch_engine = engine.with_role("orchestrator")

    # peek() returns a dict; orchestrator-scoped node must be present
    results = orch_engine.peek(["brain_identity"])
    assert isinstance(results, dict)
    assert "brain_identity" in results


# ---------------------------------------------------------------------------
# 13. Sub-agent load_skill on scope=orchestrator node returns None
# ---------------------------------------------------------------------------


def test_sub_agent_load_skill_blocked_for_orchestrator_node() -> None:
    private_node = _node("brain_rules", scope="orchestrator")
    private_node.full = "Super secret orchestrator rules."

    engine = _engine_with_nodes(private_node)
    worker_engine = engine.with_role("worker")

    # get_node returns None for invisible nodes
    assert worker_engine.get_node("brain_rules") is None

    # resolve_node returns an error string — the secret content must NOT appear
    result = worker_engine.resolve_node("brain_rules")
    assert "not found" in result.lower() or "error" in result.lower()
    assert "Super secret" not in result


# ---------------------------------------------------------------------------
# 14. register_delegation_tools passes skill_engine to _make_delegate_task
# ---------------------------------------------------------------------------


def test_register_delegation_tools_passes_engine() -> None:
    from hachi.tools.delegation_tools import register_delegation_tools

    registry = MagicMock()
    engine = MagicMock()

    with patch("hachi.tools.delegation_tools._make_delegate_task") as mock_factory:
        mock_factory.return_value = lambda: None
        register_delegation_tools(registry, skill_engine=engine)

    # Verify skill_engine keyword arg was passed in at least one call to the factory.
    # _make_delegate_parallel_tasks also calls _make_delegate_task (without skill_engine)
    # so we check call_args_list rather than call_args (which is the most recent call).
    assert any(c.kwargs.get("skill_engine") is engine for c in mock_factory.call_args_list), (
        f"skill_engine not found in any call: {mock_factory.call_args_list}"
    )
