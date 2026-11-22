"""Tests for RunState domain models (state.py) — pure data, no I/O."""

from __future__ import annotations

from hachi.core.runtime.state import (
    RunState,
    RunStateView,
    RunStatus,
    WaitCondition,
    WaitKind,
    WakeRequest,
)
from hachi.core.runtime_events import now_iso

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    run_id: str = "run-001",
    session_id: str = "sess-001",
    status: RunStatus = RunStatus.PENDING,
    wait: WaitCondition | None = None,
    resume_cursor: int = 0,
) -> RunState:
    return RunState(
        run_id=run_id,
        session_id=session_id,
        status=status,
        wait=wait,
        resume_cursor=resume_cursor,
        payload={},
        updated_at=now_iso(),
    )


def _make_wait(kind: WaitKind = WaitKind.USER, key: str = "approval-123") -> WaitCondition:
    return WaitCondition(kind=kind, key=key, created_at=now_iso())


# ---------------------------------------------------------------------------
# RunStatus StrEnum
# ---------------------------------------------------------------------------


class TestRunStatus:
    def test_all_values_accessible(self):
        assert RunStatus.PENDING == "pending"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.WAITING == "waiting"
        assert RunStatus.BLOCKED == "blocked"
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.CANCELLED == "cancelled"

    def test_from_string(self):
        assert RunStatus("waiting") == RunStatus.WAITING
        assert RunStatus("completed") == RunStatus.COMPLETED


class TestWaitKind:
    def test_all_values_accessible(self):
        assert WaitKind.USER == "user"
        assert WaitKind.EVENT == "event"
        assert WaitKind.TIME == "time"
        assert WaitKind.WEBHOOK == "webhook"
        assert WaitKind.TOOL == "tool"


# ---------------------------------------------------------------------------
# WaitCondition
# ---------------------------------------------------------------------------


class TestWaitCondition:
    def test_basic_construction(self):
        wc = _make_wait(WaitKind.EVENT, "session.*")
        assert wc.kind == WaitKind.EVENT
        assert wc.key == "session.*"
        assert wc.timeout_at is None

    def test_with_timeout(self):
        wc = WaitCondition(
            kind=WaitKind.TIME,
            key="2026-07-01T00:00:00+00:00",
            created_at=now_iso(),
            timeout_at="2026-07-02T00:00:00+00:00",
        )
        assert wc.timeout_at is not None

    def test_serialise_roundtrip(self):
        wc = _make_wait(WaitKind.WEBHOOK, "tok-abc")
        data = wc.model_dump()
        restored = WaitCondition.model_validate(data)
        assert restored.kind == WaitKind.WEBHOOK
        assert restored.key == "tok-abc"


# ---------------------------------------------------------------------------
# RunState
# ---------------------------------------------------------------------------


class TestRunState:
    def test_basic_construction(self):
        run = _make_run()
        assert run.status == RunStatus.PENDING
        assert run.resume_cursor == 0
        assert run.wait is None

    def test_with_wait_condition(self):
        wait = _make_wait(WaitKind.USER, "appr-xyz")
        run = _make_run(status=RunStatus.WAITING, wait=wait)
        assert run.wait is not None
        assert run.wait.kind == WaitKind.USER

    def test_model_copy_update(self):
        run = _make_run(status=RunStatus.PENDING)
        updated = run.model_copy(update={"status": RunStatus.RUNNING})
        assert updated.status == RunStatus.RUNNING
        assert run.status == RunStatus.PENDING  # original unchanged

    def test_payload_default_empty(self):
        run = _make_run()
        assert run.payload == {}

    def test_serialise_roundtrip(self):
        wait = _make_wait(WaitKind.EVENT, "tool.*")
        run = _make_run(status=RunStatus.WAITING, wait=wait, resume_cursor=3)
        data = run.model_dump()
        restored = RunState.model_validate(data)
        assert restored.run_id == run.run_id
        assert restored.status == RunStatus.WAITING
        assert restored.resume_cursor == 3
        assert restored.wait is not None
        assert restored.wait.key == "tool.*"


# ---------------------------------------------------------------------------
# RunStateView
# ---------------------------------------------------------------------------


class TestRunStateView:
    def test_from_run_state_no_wait(self):
        run = _make_run(status=RunStatus.COMPLETED)
        view = RunStateView.from_run_state(run)
        assert view.status == "completed"
        assert view.wait_kind is None
        assert view.wait_key is None
        assert view.wait_timeout_at is None

    def test_from_run_state_with_wait(self):
        wait = WaitCondition(
            kind=WaitKind.USER,
            key="appr-001",
            created_at=now_iso(),
            timeout_at="2099-01-01T00:00:00+00:00",
        )
        run = _make_run(status=RunStatus.WAITING, wait=wait)
        view = RunStateView.from_run_state(run)
        assert view.status == "waiting"
        assert view.wait_kind == "user"
        assert view.wait_key == "appr-001"
        assert view.wait_timeout_at == "2099-01-01T00:00:00+00:00"

    def test_view_resume_cursor(self):
        run = _make_run(resume_cursor=7)
        view = RunStateView.from_run_state(run)
        assert view.resume_cursor == 7

    def test_view_serialise(self):
        run = _make_run()
        view = RunStateView.from_run_state(run)
        d = view.model_dump()
        assert "run_id" in d
        assert "status" in d


# ---------------------------------------------------------------------------
# WakeRequest
# ---------------------------------------------------------------------------


class TestWakeRequest:
    def test_defaults(self):
        req = WakeRequest()
        assert req.result == {}
        assert req.source == "webhook"

    def test_custom_result(self):
        req = WakeRequest(result={"decision": "approved"}, source="api")
        assert req.result["decision"] == "approved"
        assert req.source == "api"
