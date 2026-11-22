"""Tests for SuspendWorkflow + suspend handling in loop.py."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hachi.core.loop import SuspendWorkflow
from hachi.tools.workflow_tools import register_workflow_tools

# ---------------------------------------------------------------------------
# SuspendWorkflow exception contract
# ---------------------------------------------------------------------------


class TestSuspendWorkflow:
    def test_basic_construction(self):
        exc = SuspendWorkflow(reason="waiting for approval")
        assert exc.reason == "waiting for approval"
        assert exc.wait_kind == "user"
        assert exc.wait_key == ""

    def test_full_construction(self):
        exc = SuspendWorkflow(
            reason="waiting for event",
            wait_kind="event",
            wait_key="session.*",
        )
        assert exc.reason == "waiting for event"
        assert exc.wait_kind == "event"
        assert exc.wait_key == "session.*"

    def test_is_exception(self):
        exc = SuspendWorkflow(reason="test")
        assert isinstance(exc, Exception)

    def test_str_is_reason(self):
        exc = SuspendWorkflow(reason="some reason")
        assert str(exc) == "some reason"

    def test_wait_kinds(self):
        for kind in ("user", "event", "time", "webhook"):
            exc = SuspendWorkflow(reason="r", wait_kind=kind, wait_key="k")
            assert exc.wait_kind == kind

    def test_raises_and_catches(self):
        with pytest.raises(SuspendWorkflow) as exc_info:
            raise SuspendWorkflow(reason="paused", wait_kind="user", wait_key="req-001")
        caught = exc_info.value
        assert caught.reason == "paused"
        assert caught.wait_kind == "user"
        assert caught.wait_key == "req-001"


# ---------------------------------------------------------------------------
# workflow_tools.py: register_workflow_tools
# ---------------------------------------------------------------------------


class MockRegistry:
    """Minimal ToolRegistry stub for testing register_workflow_tools."""

    def __init__(self) -> None:
        self.specs: list[dict] = []
        self.handlers: dict[str, object] = {}

    def register(self, spec: dict, handler: object) -> None:
        self.specs.append(spec)
        self.handlers[spec["name"]] = handler


class TestRegisterWorkflowTools:
    def test_registers_core_suspend_workflow(self):
        reg = MockRegistry()
        register_workflow_tools(reg)
        assert any(s["name"] == "core_suspend_workflow" for s in reg.specs)

    def test_tool_spec_has_required_fields(self):
        reg = MockRegistry()
        register_workflow_tools(reg)
        spec = next(s for s in reg.specs if s["name"] == "core_suspend_workflow")
        assert "description" in spec
        assert "input_schema" in spec
        schema = spec["input_schema"]
        assert "reason" in schema["properties"]
        assert "wait_kind" in schema["properties"]
        assert "wait_key" in schema["properties"]
        assert "reason" in schema["required"]

    def test_tool_spec_wait_kind_has_enum(self):
        reg = MockRegistry()
        register_workflow_tools(reg)
        spec = next(s for s in reg.specs if s["name"] == "core_suspend_workflow")
        kinds = spec["input_schema"]["properties"]["wait_kind"]["enum"]
        assert set(kinds) == {"user", "event", "time", "webhook"}

    def test_description_honest_no_auto_wake_promise(self):
        """Ensure the description no longer promises automatic wake-up."""
        reg = MockRegistry()
        register_workflow_tools(reg)
        spec = next(s for s in reg.specs if s["name"] == "core_suspend_workflow")
        desc = spec["description"].lower()
        # Old dishonest description contained "automatically wake up"
        assert "automatically wake up" not in desc

    def test_handler_raises_suspend_workflow(self):
        reg = MockRegistry()
        register_workflow_tools(reg)
        handler = reg.handlers["core_suspend_workflow"]

        with pytest.raises(SuspendWorkflow) as exc_info:
            handler(reason="need approval", wait_kind="user", wait_key="req-1")

        exc = exc_info.value
        assert exc.reason == "need approval"
        assert exc.wait_kind == "user"
        assert exc.wait_key == "req-1"

    def test_handler_defaults_for_wait_kind_and_key(self):
        reg = MockRegistry()
        register_workflow_tools(reg)
        handler = reg.handlers["core_suspend_workflow"]

        with pytest.raises(SuspendWorkflow) as exc_info:
            handler(reason="minimal")

        exc = exc_info.value
        assert exc.wait_kind == "user"
        assert exc.wait_key == ""

    def test_handler_event_kind(self):
        reg = MockRegistry()
        register_workflow_tools(reg)
        handler = reg.handlers["core_suspend_workflow"]

        with pytest.raises(SuspendWorkflow) as exc_info:
            handler(reason="waiting for event", wait_kind="event", wait_key="session.*")

        exc = exc_info.value
        assert exc.wait_kind == "event"
        assert exc.wait_key == "session.*"


# ---------------------------------------------------------------------------
# Producer: AgentSession persists a durable WAITING run + arms the registry (P0-1)
# ---------------------------------------------------------------------------


def _suspending_session(tmp_path, suspend):
    """A minimally-constructed AgentSession wired for _persist_suspended_run_if_any."""
    from hachi.gateway.orchestrator import AgentSession

    sess = AgentSession.__new__(AgentSession)
    sess._session_id = "sess-9"
    sess._emit_event = lambda *a, **k: None
    sess.loop = SimpleNamespace(last_suspend=suspend)
    return sess


class TestSuspendProducer:
    """The producer half the audit found missing: a suspend must create a durable
    RunState(WAITING) and arm the wait registry, or the wake/recover/sweep subsystem and
    GET /runs have zero inputs."""

    def test_persist_creates_waiting_run_and_arms(self, tmp_path) -> None:
        from hachi.core.runtime.state import RunStatus, WaitKind
        from hachi.core.runtime.store import RunStateStore
        from hachi.core.runtime.waits import WaitConditionRegistry

        store = RunStateStore(db_path=tmp_path / "runs.db")
        registry = WaitConditionRegistry()
        sess = _suspending_session(
            tmp_path,
            SuspendWorkflow("await boss", wait_kind="event", wait_key="email:boss"),
        )
        with (
            patch("hachi.core.runtime.store.RunStateStore", return_value=store),
            patch("hachi.core.runtime.waits.get_wait_registry", return_value=registry),
        ):
            sess._persist_suspended_run_if_any(turn_id="t1")

        waiting = store.waiting()
        assert len(waiting) == 1
        run = waiting[0]
        assert run.status == RunStatus.WAITING
        assert run.session_id == "sess-9"
        assert run.wait is not None
        assert run.wait.kind == WaitKind.EVENT
        assert run.wait.key == "email:boss"
        # Armed → resolving the key returns this run_id: the wake path now has an input.
        assert registry.resolve("email:boss", {}) == run.run_id

    def test_unknown_wait_kind_defaults_to_user(self, tmp_path) -> None:
        from hachi.core.runtime.state import WaitKind
        from hachi.core.runtime.store import RunStateStore
        from hachi.core.runtime.waits import WaitConditionRegistry

        store = RunStateStore(db_path=tmp_path / "runs.db")
        registry = WaitConditionRegistry()
        sess = _suspending_session(
            tmp_path, SuspendWorkflow("hmm", wait_kind="bogus", wait_key="k")
        )
        with (
            patch("hachi.core.runtime.store.RunStateStore", return_value=store),
            patch("hachi.core.runtime.waits.get_wait_registry", return_value=registry),
        ):
            sess._persist_suspended_run_if_any(turn_id="t2")
        run = store.waiting()[0]
        assert run.wait is not None and run.wait.kind == WaitKind.USER

    def test_noop_when_not_suspended(self, tmp_path) -> None:
        from hachi.core.runtime.store import RunStateStore

        store = RunStateStore(db_path=tmp_path / "runs.db")
        sess = _suspending_session(tmp_path, None)
        with patch("hachi.core.runtime.store.RunStateStore", return_value=store):
            sess._persist_suspended_run_if_any(turn_id="t3")
        assert store.waiting() == []
