"""P4-02: Shared-services gateway — process singletons.

Tests:
  1. ProcessSharedServices.get_or_create() returns the same instance on repeat calls.
  2. ProcessSharedServices.clear() destroys the singleton.
  3. After clear(), get_or_create() returns a fresh instance.
  4. Singleton has expected fields: skill_engine, mcp_manager, vault, graph_index, memory_writer.
  5. skill_engine field is non-None when init succeeds.
  6. uptime_seconds() increases monotonically.
  7. force_reinit=True creates a new instance even without clear().
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helper: build a fake ProcessSharedServices without touching disk or subprocesses.
# We patch _init() rather than its 5 internal imports so tests stay simple.
# ---------------------------------------------------------------------------


def _make_fake_instance():
    from hachi.gateway.shared_services import ProcessSharedServices

    return ProcessSharedServices(
        skill_engine=MagicMock(),
        mcp_manager=MagicMock(),
        vault=None,
        graph_index=None,
        memory_writer=None,
        brain_dir="/tmp/fake_brain",
    )


def _patched_shared(tmp_path_str: str = "/tmp/fake_brain"):
    """Call get_or_create() with _init() mocked so no real services are started."""
    from hachi.gateway.shared_services import ProcessSharedServices

    ProcessSharedServices.clear()
    with patch.object(ProcessSharedServices, "_init", return_value=_make_fake_instance()):
        instance = ProcessSharedServices.get_or_create(config={}, brain_dir=tmp_path_str)
    return instance


# ---------------------------------------------------------------------------
# 1. Same instance on repeat calls
# ---------------------------------------------------------------------------


def test_get_or_create_returns_singleton() -> None:
    from hachi.gateway.shared_services import ProcessSharedServices

    try:
        inst1 = _patched_shared()
        # Second call with no patching — _init should NOT be called again
        inst2 = ProcessSharedServices.get_or_create(config={}, brain_dir="/tmp/fake_brain")
        assert inst1 is inst2, "Second call must return the same instance"
    finally:
        ProcessSharedServices.clear()


# ---------------------------------------------------------------------------
# 2. clear() destroys the singleton
# ---------------------------------------------------------------------------


def test_clear_destroys_singleton() -> None:
    import hachi.gateway.shared_services as _mod
    from hachi.gateway.shared_services import ProcessSharedServices

    _patched_shared()
    ProcessSharedServices.clear()
    # ADV-024: the singleton store is now a fingerprint-keyed dict; clear() empties it.
    assert _mod._INSTANCES == {}


# ---------------------------------------------------------------------------
# 3. After clear(), get_or_create() returns a fresh instance
# ---------------------------------------------------------------------------


def test_after_clear_new_instance_is_created() -> None:
    from hachi.gateway.shared_services import ProcessSharedServices

    inst1 = _patched_shared()
    ProcessSharedServices.clear()
    inst2 = _patched_shared()
    assert inst1 is not inst2


# ---------------------------------------------------------------------------
# 4. Singleton has expected fields
# ---------------------------------------------------------------------------


def test_singleton_has_expected_fields() -> None:
    from hachi.gateway.shared_services import ProcessSharedServices

    try:
        inst = _patched_shared()
        assert hasattr(inst, "skill_engine")
        assert hasattr(inst, "mcp_manager")
        assert hasattr(inst, "vault")
        assert hasattr(inst, "graph_index")
        assert hasattr(inst, "memory_writer")
        assert hasattr(inst, "brain_dir")
        assert hasattr(inst, "initialized_at")
    finally:
        ProcessSharedServices.clear()


# ---------------------------------------------------------------------------
# 5. skill_engine is non-None when init succeeds
# ---------------------------------------------------------------------------


def test_skill_engine_is_present() -> None:
    from hachi.gateway.shared_services import ProcessSharedServices

    try:
        inst = _patched_shared()
        assert inst.skill_engine is not None
    finally:
        ProcessSharedServices.clear()


# ---------------------------------------------------------------------------
# 6. uptime_seconds() increases
# ---------------------------------------------------------------------------


def test_uptime_seconds_increases() -> None:
    from hachi.gateway.shared_services import ProcessSharedServices

    try:
        inst = _patched_shared()
        t1 = inst.uptime_seconds()
        time.sleep(0.01)
        t2 = inst.uptime_seconds()
        assert t2 > t1
    finally:
        ProcessSharedServices.clear()


# ---------------------------------------------------------------------------
# 7. force_reinit=True creates a new instance
# ---------------------------------------------------------------------------


def test_force_reinit_creates_new_instance() -> None:
    from hachi.gateway.shared_services import ProcessSharedServices

    try:
        inst1 = _patched_shared()

        with patch.object(ProcessSharedServices, "_init", return_value=_make_fake_instance()):
            inst2 = ProcessSharedServices.get_or_create(
                config={}, brain_dir="/tmp/fake_brain", force_reinit=True
            )

        assert inst1 is not inst2, "force_reinit=True must produce a new instance"
    finally:
        ProcessSharedServices.clear()


# ---------------------------------------------------------------------------
# 8. load_directory (not index_directory) populates the shared skill engine
#    with the bundled default_skills — confirming the fix for the OG Explorer
#    showing zero nodes.
# ---------------------------------------------------------------------------


def test_skill_engine_loads_default_skills() -> None:
    """SkillEngine.load_directory() on the bundled default_skills must yield >0 nodes.

    This is the critical regression guard for the fix in shared_services.py:
    the old code called ``skill_engine.index_directory()`` (non-existent method,
    silently swallowed by except-Exception), leaving the engine empty.  The fix
    replaces it with ``skill_engine.load_directory()``.
    """
    from pathlib import Path

    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine(agent_role="orchestrator")
    default_skills_dir = Path(__file__).parent.parent / "src" / "hachi" / "default_skills"
    assert default_skills_dir.exists(), f"default_skills not found at {default_skills_dir}"

    engine.load_directory(default_skills_dir)
    nodes = engine.get_all_nodes()
    assert len(nodes) > 0, (
        f"Expected >0 nodes after load_directory on {default_skills_dir}, got 0. "
        "Check that .og files exist and that load_directory is the correct method name."
    )


# ---------------------------------------------------------------------------
# 9. og_graph_from_engine returns non-empty nodes and count when engine is loaded
#    — confirming the pre-session fallback path in get_og_graph().
# ---------------------------------------------------------------------------


def test_og_graph_from_engine_returns_nodes() -> None:
    """og_graph_from_engine() must return a dict with nodes>0 and matching count.

    This guards the pre-session fallback added to _InProcessGatewayRuntime.get_og_graph():
    when no active agent session exists, the shared skill engine is used via
    og_graph_from_engine(), so the OG Explorer shows default-skill nodes immediately.
    """
    from pathlib import Path

    from hachi.gateway.orchestrator import og_graph_from_engine
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine(agent_role="orchestrator")
    default_skills_dir = Path(__file__).parent.parent / "src" / "hachi" / "default_skills"
    engine.load_directory(default_skills_dir)

    result = og_graph_from_engine(engine)

    assert "nodes" in result, "Result must contain 'nodes' key"
    assert "count" in result, "Result must contain 'count' key"
    assert len(result["nodes"]) > 0, (
        "og_graph_from_engine must return >0 nodes when engine is loaded "
        "with default_skills"
    )
    assert result["count"] == len(result["nodes"]), (
        "'count' must equal len(nodes)"
    )


# ---------------------------------------------------------------------------
# 10. get_og_graph() on the in-process runtime returns nodes BEFORE any session.
#     The shared services are created lazily on first session boot, so the
#     runtime must build a standalone engine for the OG Explorer.  Regression:
#     it returned 0 nodes live until a conversation was opened, and the loader
#     used the non-existent ``paths.workspace_dir`` attribute (AttributeError).
# ---------------------------------------------------------------------------


def test_get_og_graph_runtime_populated_without_session() -> None:
    """_InProcessGatewayRuntime.get_og_graph() returns nodes with no active session.

    ``ProcessSharedServices.instance()`` is ``None`` until the first session
    boots, so get_og_graph must fall back to a standalone SkillEngine built from
    the bundled default skills (loaded via ``skills_dir``, not the non-existent
    ``paths.workspace_dir``).
    """
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    graph = runtime.get_og_graph()

    assert graph.get("count", 0) > 0, (
        "OG Explorer must show skill nodes before any conversation is started"
    )
    assert len(graph.get("nodes", [])) == graph["count"]
    # Node ids must be unique — the OG Explorer keys the SVG diagram by id, and
    # multiple skill files define same-named nodes (e.g. "identity").
    ids = [n["id"] for n in graph["nodes"]]
    assert len(ids) == len(set(ids)), "OG graph node ids must be unique"
