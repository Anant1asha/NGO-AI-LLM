"""Tests for RunStateStore — SQLite persistence (GATE-DURABLE)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hachi.core.runtime.state import (
    RunState,
    RunStatus,
    WaitCondition,
    WaitKind,
)
from hachi.core.runtime.store import RunStateStore
from hachi.core.runtime_events import now_iso

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> RunStateStore:
    """Provide a RunStateStore backed by a temp directory."""
    return RunStateStore(db_path=tmp_path / "test_runs.db")


def _run(
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


def _wait(kind: WaitKind = WaitKind.USER, key: str = "approval-123") -> WaitCondition:
    return WaitCondition(kind=kind, key=key, created_at=now_iso())


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------


class TestBasicCrud:
    def test_upsert_and_get(self, store: RunStateStore):
        run = _run()
        store.upsert(run)
        loaded = store.get(run.run_id)
        assert loaded is not None
        assert loaded.run_id == run.run_id
        assert loaded.status == RunStatus.PENDING

    def test_get_missing_returns_none(self, store: RunStateStore):
        assert store.get("nonexistent") is None

    def test_upsert_updates_existing(self, store: RunStateStore):
        run = _run(status=RunStatus.PENDING)
        store.upsert(run)

        updated = run.model_copy(update={"status": RunStatus.RUNNING, "updated_at": now_iso()})
        store.upsert(updated)

        loaded = store.get(run.run_id)
        assert loaded is not None
        assert loaded.status == RunStatus.RUNNING

    def test_upsert_is_idempotent(self, store: RunStateStore):
        run = _run()
        store.upsert(run)
        store.upsert(run)  # second upsert must not raise
        assert store.get(run.run_id) is not None


# ---------------------------------------------------------------------------
# Wait condition persistence
# ---------------------------------------------------------------------------


class TestWaitPersistence:
    def test_wait_persists_and_restores(self, store: RunStateStore):
        wait = _wait(WaitKind.EVENT, "session.*")
        run = _run(status=RunStatus.WAITING, wait=wait)
        store.upsert(run)

        loaded = store.get(run.run_id)
        assert loaded is not None
        assert loaded.wait is not None
        assert loaded.wait.kind == WaitKind.EVENT
        assert loaded.wait.key == "session.*"

    def test_no_wait_restores_as_none(self, store: RunStateStore):
        run = _run(status=RunStatus.RUNNING)
        store.upsert(run)
        loaded = store.get(run.run_id)
        assert loaded is not None
        assert loaded.wait is None

    def test_wait_with_timeout_restores(self, store: RunStateStore):
        wait = WaitCondition(
            kind=WaitKind.TIME,
            key="2099-01-01T00:00:00+00:00",
            created_at=now_iso(),
            timeout_at="2099-01-02T00:00:00+00:00",
        )
        run = _run(status=RunStatus.WAITING, wait=wait)
        store.upsert(run)

        loaded = store.get(run.run_id)
        assert loaded is not None
        assert loaded.wait is not None
        assert loaded.wait.timeout_at == "2099-01-02T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Query methods
# ---------------------------------------------------------------------------


class TestQueryMethods:
    def test_waiting_returns_only_waiting(self, store: RunStateStore):
        store.upsert(_run("r1", status=RunStatus.WAITING, wait=_wait()))
        store.upsert(_run("r2", status=RunStatus.RUNNING))
        store.upsert(_run("r3", status=RunStatus.COMPLETED))

        waiting = store.waiting()
        assert len(waiting) == 1
        assert waiting[0].run_id == "r1"

    def test_by_session_returns_session_runs(self, store: RunStateStore):
        store.upsert(_run("r1", session_id="sess-A"))
        store.upsert(_run("r2", session_id="sess-B"))
        store.upsert(_run("r3", session_id="sess-A"))

        runs_a = store.by_session("sess-A")
        assert len(runs_a) == 2
        assert all(r.session_id == "sess-A" for r in runs_a)

    def test_list_all_respects_limit(self, store: RunStateStore):
        for i in range(10):
            store.upsert(_run(f"run-{i:03d}"))
        runs = store.list_all(limit=3)
        assert len(runs) == 3

    def test_list_all_empty(self, store: RunStateStore):
        assert store.list_all() == []


# ---------------------------------------------------------------------------
# Payload persistence
# ---------------------------------------------------------------------------


class TestPayloadPersistence:
    def test_payload_roundtrip(self, store: RunStateStore):
        run = RunState(
            run_id="r-payload",
            session_id="sess-x",
            status=RunStatus.RUNNING,
            payload={"key": "value", "nested": {"a": 1}},
            updated_at=now_iso(),
        )
        store.upsert(run)
        loaded = store.get("r-payload")
        assert loaded is not None
        assert loaded.payload == {"key": "value", "nested": {"a": 1}}

    def test_resume_cursor_persists(self, store: RunStateStore):
        run = _run(resume_cursor=5)
        store.upsert(run)
        loaded = store.get(run.run_id)
        assert loaded is not None
        assert loaded.resume_cursor == 5


# ---------------------------------------------------------------------------
# GATE-DURABLE: upsert uses ON CONFLICT DO UPDATE (not INSERT OR REPLACE)
# ---------------------------------------------------------------------------


class TestGateDurable:
    def test_on_conflict_preserves_row_not_replace(self, store: RunStateStore):
        """Verify upsert updates fields without deleting the row (ON CONFLICT DO UPDATE)."""
        run = _run("gate-run", status=RunStatus.PENDING, resume_cursor=0)
        store.upsert(run)

        # Update status and resume_cursor
        updated = run.model_copy(
            update={"status": RunStatus.WAITING, "resume_cursor": 3, "updated_at": now_iso()}
        )
        store.upsert(updated)

        loaded = store.get("gate-run")
        assert loaded is not None
        assert loaded.status == RunStatus.WAITING
        assert loaded.resume_cursor == 3
        assert loaded.session_id == "sess-001"  # unchanged

    def test_multiple_sessions_isolated(self, store: RunStateStore):
        store.upsert(_run("r1", "sess-A", RunStatus.RUNNING))
        store.upsert(_run("r2", "sess-B", RunStatus.WAITING, wait=_wait()))

        assert store.get("r1").session_id == "sess-A"
        assert store.get("r2").status == RunStatus.WAITING
