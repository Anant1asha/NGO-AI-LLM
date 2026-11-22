"""Regression tests for BB-72 — retention/prune sweep never wired.

``cleanup_completed()`` was defined in three places and called by zero production
code; ``session_store`` idempotency keys, interaction log, and daily-spend rows
had no cleanup path at all; ``CheckpointManager`` snapshots grew forever.

Each test below is RED on the un-fixed codebase and GREEN after the fix.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hachi.core.checkpoints import CheckpointManager
from hachi.core.session_store import SessionStore
from hachi.jobs.queue import (
    InMemoryJobQueue,
    Job,
    JobRegistry,
    JobStatus,
    JobWorker,
    ResidentWorkerThread,
    SQLiteJobQueue,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _old_iso(hours: int = 25) -> str:
    """ISO timestamp `hours` hours in the past."""
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat()


def _old_ts(hours: int = 25) -> float:
    """Unix timestamp `hours` hours in the past."""
    return time.time() - hours * 3600


def _insert_raw_completed_job(q: SQLiteJobQueue, job_id: str, hours_old: int = 25) -> None:
    old = _old_iso(hours_old)
    with q._conn() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, name, handler_name, payload, status, created_at,"
            " completed_at, attempt, max_retries) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, job_id, "noop", "{}", "completed", old, old, 1, 3),
        )


# ---------------------------------------------------------------------------
# BB-72-1: idle ResidentWorkerThread must prune old completed jobs
# ---------------------------------------------------------------------------


def test_worker_idle_prunes_old_completed_jobs(tmp_path: Path) -> None:
    """Idle ResidentWorkerThread must prune completed jobs older than retention TTL.

    FAILS before the fix: ResidentWorkerThread does not accept
    ``sweep_interval_seconds`` / ``jobs_retention_hours`` and never calls
    ``cleanup_completed()``, so the job persists forever.

    PASSES after the fix: the sweep fires on the first idle cycle and removes the
    stale row.
    """
    q = SQLiteJobQueue(db_path=tmp_path / "jobs.db")
    _insert_raw_completed_job(q, "stale-job-1", hours_old=25)

    # Confirm the job exists before the worker runs.
    assert len(q.get_recent_jobs(limit=10)) == 1

    worker = JobWorker(q, registry=JobRegistry())
    # sweep_interval_seconds=0.1 → sweep fires within the first 0.2-second window.
    # jobs_retention_hours=0    → all completed jobs are eligible immediately.
    rt = ResidentWorkerThread(
        worker,
        poll_interval=0.05,
        sweep_interval_seconds=0.1,
        jobs_retention_hours=0,
    )
    rt.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if len(q.get_recent_jobs(limit=10)) == 0:
            break
        time.sleep(0.05)

    rt.stop()

    remaining = q.get_recent_jobs(limit=10)
    assert len(remaining) == 0, (
        "ResidentWorkerThread idle sweep must prune completed jobs older than "
        "jobs_retention_hours (BB-72)"
    )


def test_inmemory_queue_also_swept(tmp_path: Path) -> None:
    """InMemoryJobQueue cleanup_completed is also exercised by the sweep.

    Ensures the sweep does not hard-code the SQLite path.
    """
    from hachi.jobs.queue import JobResult

    q = InMemoryJobQueue()
    j = Job(job_id="test-old", name="old", handler_name="noop", payload={})
    q.enqueue(j)
    # Manually mark the in-memory job as completed, then back-date it.
    q.update_status(
        j.job_id,
        JobStatus.COMPLETED,
        result=JobResult(status=JobStatus.COMPLETED, output={"done": True}),
    )
    with q._lock:
        q._jobs[j.job_id].completed_at = _old_iso(25)

    assert len(q.get_recent_jobs(limit=10)) == 1

    worker = JobWorker(q, registry=JobRegistry())
    rt = ResidentWorkerThread(
        worker,
        poll_interval=0.05,
        sweep_interval_seconds=0.1,
        jobs_retention_hours=0,
    )
    rt.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if len(q.get_recent_jobs(limit=10)) == 0:
            break
        time.sleep(0.05)

    rt.stop()

    assert len(q.get_recent_jobs(limit=10)) == 0, (
        "InMemoryJobQueue stale completed jobs must also be swept (BB-72)"
    )


# ---------------------------------------------------------------------------
# BB-72-2: SessionStore.cleanup_idempotency_keys
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path):
    s = SessionStore(db_path=str(tmp_path / "test.db"))
    yield s
    s.shutdown()


def test_session_store_cleanup_idempotency_keys(store: SessionStore) -> None:
    """cleanup_idempotency_keys must delete keys older than the retention window.

    FAILS before the fix: method does not exist (AttributeError).
    PASSES after the fix: old key is deleted, fresh key is preserved.
    """
    session_id = store.start_session()

    old_ts = _old_ts(hours=25)
    fresh_ts = time.time()

    with store._lock:
        store._conn.execute(
            "INSERT INTO idempotency_keys (session_id, idem_key, response_json, created_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, "old-key", json.dumps({"ok": 1}), old_ts),
        )
        store._conn.execute(
            "INSERT INTO idempotency_keys (session_id, idem_key, response_json, created_at)"
            " VALUES (?, ?, ?, ?)",
            (session_id, "fresh-key", json.dumps({"ok": 2}), fresh_ts),
        )
        store._conn.commit()

    removed = store.cleanup_idempotency_keys(older_than_hours=24)
    assert removed == 1, f"Expected 1 key removed, got {removed} (BB-72)"

    rows = store._conn.execute(
        "SELECT idem_key FROM idempotency_keys WHERE session_id = ?", (session_id,)
    ).fetchall()
    keys = {r[0] for r in rows}
    assert "old-key" not in keys, "old-key must be pruned (BB-72)"
    assert "fresh-key" in keys, "fresh-key must be preserved (BB-72)"


# ---------------------------------------------------------------------------
# BB-72-3: SessionStore.cleanup_interaction_log
# ---------------------------------------------------------------------------


def test_session_store_cleanup_interaction_log(store: SessionStore) -> None:
    """cleanup_interaction_log must delete rows older than the retention window.

    FAILS before the fix: method does not exist (AttributeError).
    PASSES after the fix: old row is deleted, fresh row is preserved.
    """
    session_id = store.start_session()

    old_ts_iso = _old_iso(hours=25 * 24)  # ~25 days old
    fresh_ts_iso = datetime.now(UTC).isoformat()

    with store._lock:
        store._conn.execute(
            "INSERT INTO interaction_log (id, session_id, ts, user_input, agent_output)"
            " VALUES (?, ?, ?, ?, ?)",
            ("old-row", session_id, old_ts_iso, "hi", "hello"),
        )
        store._conn.execute(
            "INSERT INTO interaction_log (id, session_id, ts, user_input, agent_output)"
            " VALUES (?, ?, ?, ?, ?)",
            ("fresh-row", session_id, fresh_ts_iso, "hey", "hey"),
        )
        store._conn.commit()

    removed = store.cleanup_interaction_log(older_than_days=1)
    assert removed == 1, f"Expected 1 row removed, got {removed} (BB-72)"

    rows = store._conn.execute(
        "SELECT id FROM interaction_log WHERE session_id = ?", (session_id,)
    ).fetchall()
    ids = {r[0] for r in rows}
    assert "old-row" not in ids, "old interaction_log row must be pruned (BB-72)"
    assert "fresh-row" in ids, "fresh interaction_log row must be preserved (BB-72)"


# ---------------------------------------------------------------------------
# BB-72-4: CheckpointManager.prune_old_snapshots
# ---------------------------------------------------------------------------


def test_checkpoint_manager_prune_old_snapshots(tmp_path: Path) -> None:
    """prune_old_snapshots must remove checkpoint entries older than the TTL.

    FAILS before the fix: method does not exist (AttributeError).
    PASSES after the fix: old snapshot is deleted, fresh snapshot is preserved.
    """
    cm = CheckpointManager(base_dir=tmp_path / "checkpoints")

    # Create a real file to snapshot.
    target = tmp_path / "edit_me.txt"
    target.write_text("original content")

    # Snapshot it so an entry appears in the index.
    snap_id = cm.snapshot(target, label="test-snap")
    assert snap_id is not None

    # Back-date the snapshot entry to make it look ancient.
    old_iso = _old_iso(hours=25 * 24)  # ~25 days old
    index = cm._load_index()
    for entry in index:
        if entry["id"] == snap_id:
            entry["ts"] = old_iso
    cm._save_index(index)

    # Add a fresh snapshot that must survive pruning.
    target2 = tmp_path / "edit_me2.txt"
    target2.write_text("second file")
    fresh_id = cm.snapshot(target2, label="fresh-snap")
    assert fresh_id is not None

    removed = cm.prune_old_snapshots(older_than_days=1)
    assert removed == 1, f"Expected 1 checkpoint pruned, got {removed} (BB-72)"

    remaining_ids = {e["id"] for e in cm._load_index()}
    assert snap_id not in remaining_ids, "old snapshot must be pruned (BB-72)"
    assert fresh_id in remaining_ids, "fresh snapshot must be preserved (BB-72)"


# ---------------------------------------------------------------------------
# BB-72-5: SessionStore.cleanup_daily_spend
# ---------------------------------------------------------------------------


def test_session_store_cleanup_daily_spend(store: SessionStore) -> None:
    """cleanup_daily_spend must delete rows for dates older than the retention window.

    FAILS before the fix: method does not exist (AttributeError).
    PASSES after the fix: old date row is deleted, recent date row is preserved.
    """
    import datetime as _dt

    old_date = (_dt.date.today() - _dt.timedelta(days=400)).isoformat()
    recent_date = _dt.date.today().isoformat()

    with store._lock:
        store._conn.execute(
            "INSERT INTO daily_spend (date, total_cost_usd, updated_at) VALUES (?, ?, ?)",
            (old_date, 1.23, time.time()),
        )
        store._conn.execute(
            "INSERT INTO daily_spend (date, total_cost_usd, updated_at) VALUES (?, ?, ?)",
            (recent_date, 0.45, time.time()),
        )
        store._conn.commit()

    removed = store.cleanup_daily_spend(older_than_days=365)
    assert removed == 1, f"Expected 1 daily_spend row removed, got {removed} (BB-72)"

    rows = store._conn.execute("SELECT date FROM daily_spend").fetchall()
    dates = {r[0] for r in rows}
    assert old_date not in dates, "old daily_spend row must be pruned (BB-72)"
    assert recent_date in dates, "recent daily_spend row must be preserved (BB-72)"
