"""P2-7: job-queue dead-letter + re-drive tests.

Verifies:
1. A retry-exhausted job (handler exists, keeps raising) ends in DEAD_LETTER, not FAILED,
   and is NOT deleted by cleanup_completed.
2. A structurally-unexecutable job (no handler) remains terminal FAILED and may be
   cleaned up by cleanup_completed.
3. redrive_dead_letter() resets dead-lettered jobs to PENDING (attempt=0), returns the
   count, and a re-driven job can execute successfully.
4. SQLite durability: a DEAD_LETTER row persists across a fresh queue instance on the same DB.

Uses the same patterns as tests/test_p2_02_job_queue.py (SQLiteJobQueue + JobWorker +
JobRegistry + a deterministically-failing handler).
"""

from __future__ import annotations

from pathlib import Path

from hachi.jobs.queue import (
    InMemoryJobQueue,
    Job,
    JobRegistry,
    JobStatus,
    JobWorker,
    SQLiteJobQueue,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sqlite_queue(tmp_path: Path) -> SQLiteJobQueue:
    return SQLiteJobQueue(db_path=tmp_path / "jobs.db")


def _failing_registry(name: str = "always.fail") -> JobRegistry:
    """Registry that always raises for ``name``."""
    reg = JobRegistry()
    reg.register(name, lambda **_kw: (_ for _ in ()).throw(RuntimeError("transient error")))
    return reg


def _make_job(handler: str = "always.fail", max_retries: int = 1) -> Job:
    """Build a named job with max_retries=1 so it dead-letters on the first failure."""
    return Job(
        job_id="",
        name=handler,
        handler_name=handler,
        payload={},
        status=JobStatus.PENDING,
        max_retries=max_retries,
    )


def _exhaust_to_dead_letter(q: SQLiteJobQueue | InMemoryJobQueue, handler: str) -> str:
    """Enqueue a job that always fails and run it once (max_retries=1 → dead-letter immediately).

    Returns the job_id.
    """
    jid = q.enqueue(_make_job(handler, max_retries=1))
    reg = _failing_registry(handler)
    worker = JobWorker(q, registry=reg)
    worker.execute_one()
    return jid


# ---------------------------------------------------------------------------
# 1. Retry-exhausted (handler exists) → DEAD_LETTER, preserved by cleanup
# ---------------------------------------------------------------------------


def test_retry_exhausted_lands_in_dead_letter_sqlite(tmp_path: Path) -> None:
    """A job that exceeds max_retries ends in DEAD_LETTER (not FAILED)."""
    q = _sqlite_queue(tmp_path)
    jid = _exhaust_to_dead_letter(q, "always.fail")

    job = q.get_job(jid)
    assert job is not None, "job must still exist"
    assert job.status == JobStatus.DEAD_LETTER, f"expected DEAD_LETTER, got {job.status}"
    assert job.result is not None
    assert job.result.error is not None
    q.shutdown()


def test_retry_exhausted_lands_in_dead_letter_inmemory() -> None:
    """InMemoryJobQueue: retry-exhausted job also ends in DEAD_LETTER."""
    q = InMemoryJobQueue()
    jid = _exhaust_to_dead_letter(q, "always.fail")

    stored = q.get_job(jid)
    assert stored is not None
    assert stored.status == JobStatus.DEAD_LETTER


def test_cleanup_preserves_dead_letter_sqlite(tmp_path: Path) -> None:
    """cleanup_completed must NOT delete DEAD_LETTER jobs."""
    q = _sqlite_queue(tmp_path)
    jid = _exhaust_to_dead_letter(q, "always.fail")

    job = q.get_job(jid)
    assert job is not None and job.status == JobStatus.DEAD_LETTER

    removed = q.cleanup_completed(older_than_hours=0)
    assert removed == 0, "cleanup must not remove dead-letter jobs"
    assert q.get_job(jid) is not None, "dead-letter job must survive cleanup"
    q.shutdown()


def test_cleanup_preserves_dead_letter_inmemory() -> None:
    """InMemoryJobQueue: cleanup_completed also preserves DEAD_LETTER."""
    q = InMemoryJobQueue()
    jid = _exhaust_to_dead_letter(q, "always.fail")

    job = q.get_job(jid)
    assert job is not None and job.status == JobStatus.DEAD_LETTER

    removed = q.cleanup_completed(older_than_hours=0)
    assert removed == 0
    assert q.get_job(jid) is not None


# ---------------------------------------------------------------------------
# 2. Structurally-unexecutable job → terminal FAILED (not DEAD_LETTER)
# ---------------------------------------------------------------------------


def test_no_handler_job_is_terminal_failed_sqlite(tmp_path: Path) -> None:
    """A job with no callable and no registered handler stays terminal FAILED."""
    q = _sqlite_queue(tmp_path)
    jid = q.enqueue(
        Job(
            job_id="",
            name="no_handler",
            handler_name="unknown.handler",
            payload={},
            max_retries=3,
        )
    )
    worker = JobWorker(q)  # no registry
    worker.execute_one()

    job = q.get_job(jid)
    assert job is not None
    assert job.status == JobStatus.FAILED, f"expected FAILED, got {job.status}"
    q.shutdown()


def test_no_handler_job_is_cleaned_up_by_cleanup(tmp_path: Path) -> None:
    """Terminal FAILED (structural) jobs are removed by cleanup_completed."""
    q = _sqlite_queue(tmp_path)
    jid = q.enqueue(Job(job_id="", name="no_handler", handler_name="unknown.handler", payload={}))
    worker = JobWorker(q)
    worker.execute_one()

    job = q.get_job(jid)
    assert job is not None and job.status == JobStatus.FAILED

    removed = q.cleanup_completed(older_than_hours=0)
    assert removed == 1
    assert q.get_job(jid) is None
    q.shutdown()


# ---------------------------------------------------------------------------
# 3. redrive_dead_letter() resets and re-runs
# ---------------------------------------------------------------------------


def test_redrive_resets_to_pending_and_returns_count_sqlite(tmp_path: Path) -> None:
    """redrive_dead_letter resets DEAD_LETTER to PENDING (attempt=0), returns count."""
    q = _sqlite_queue(tmp_path)
    jid = _exhaust_to_dead_letter(q, "always.fail")

    job = q.get_job(jid)
    assert job is not None and job.status == JobStatus.DEAD_LETTER

    count = q.redrive_dead_letter()
    assert count == 1

    redriven = q.get_job(jid)
    assert redriven is not None
    assert redriven.status == JobStatus.PENDING
    assert redriven.attempt == 0
    q.shutdown()


def test_redrive_resets_to_pending_and_returns_count_inmemory() -> None:
    """InMemoryJobQueue: redrive_dead_letter also resets attempt=0 and returns count."""
    q = InMemoryJobQueue()
    jid = _exhaust_to_dead_letter(q, "always.fail")

    job = q.get_job(jid)
    assert job is not None and job.status == JobStatus.DEAD_LETTER

    count = q.redrive_dead_letter()
    assert count == 1

    redriven = q.get_job(jid)
    assert redriven is not None
    assert redriven.status == JobStatus.PENDING
    assert redriven.attempt == 0


def test_redriven_job_can_succeed(tmp_path: Path) -> None:
    """A re-driven job actually runs when the handler succeeds on the next attempt."""
    q = _sqlite_queue(tmp_path)

    # Phase 1: always-failing handler exhausts retries → DEAD_LETTER.
    jid = _exhaust_to_dead_letter(q, "my.job")
    assert q.get_job(jid) is not None
    assert q.get_job(jid).status == JobStatus.DEAD_LETTER  # type: ignore[union-attr]

    # Phase 2: re-drive then run with a succeeding handler.
    count = q.redrive_dead_letter()
    assert count == 1

    ran: list[str] = []
    success_reg = JobRegistry()
    success_reg.register("my.job", lambda **_kw: ran.append("ok"))
    worker = JobWorker(q, registry=success_reg)
    worker.execute_one()

    done = q.get_job(jid)
    assert done is not None and done.status == JobStatus.COMPLETED
    assert ran == ["ok"]
    q.shutdown()


def test_redrive_returns_zero_when_no_dead_letter(tmp_path: Path) -> None:
    """redrive_dead_letter returns 0 when there are no dead-letter jobs."""
    q = _sqlite_queue(tmp_path)
    assert q.redrive_dead_letter() == 0
    q.shutdown()


def test_redrive_multiple_jobs(tmp_path: Path) -> None:
    """Multiple dead-letter jobs are all re-driven; count equals the number of jobs."""
    q = _sqlite_queue(tmp_path)
    reg = _failing_registry("job.a")
    reg.register("job.b", lambda **_kw: (_ for _ in ()).throw(RuntimeError("boom")))

    worker = JobWorker(q, registry=reg)
    jid_a = q.enqueue(_make_job("job.a", max_retries=1))
    jid_b = q.enqueue(_make_job("job.b", max_retries=1))
    worker.execute_one()
    worker.execute_one()

    assert q.get_job(jid_a) is not None
    assert q.get_job(jid_a).status == JobStatus.DEAD_LETTER  # type: ignore[union-attr]
    assert q.get_job(jid_b) is not None
    assert q.get_job(jid_b).status == JobStatus.DEAD_LETTER  # type: ignore[union-attr]

    count = q.redrive_dead_letter()
    assert count == 2

    for jid in (jid_a, jid_b):
        j = q.get_job(jid)
        assert j is not None and j.status == JobStatus.PENDING and j.attempt == 0
    q.shutdown()


# ---------------------------------------------------------------------------
# 4. SQLite durability: DEAD_LETTER persists across queue instances
# ---------------------------------------------------------------------------


def test_dead_letter_persists_across_restart(tmp_path: Path) -> None:
    """A DEAD_LETTER row in the SQLite DB survives a process-restart simulation."""
    db = tmp_path / "jobs.db"

    # Phase 1: exhaust retries → DEAD_LETTER.
    q1 = SQLiteJobQueue(db_path=db)
    jid = _exhaust_to_dead_letter(q1, "crash.job")
    job1 = q1.get_job(jid)
    assert job1 is not None and job1.status == JobStatus.DEAD_LETTER
    q1.shutdown()

    # Phase 2: new instance on the same DB — job must still be DEAD_LETTER.
    q2 = SQLiteJobQueue(db_path=db)
    job2 = q2.get_job(jid)
    assert job2 is not None, "dead-letter job must persist across restart"
    assert job2.status == JobStatus.DEAD_LETTER, (
        f"expected DEAD_LETTER after restart, got {job2.status}"
    )
    q2.shutdown()


def test_dead_letter_not_picked_up_as_pending(tmp_path: Path) -> None:
    """DEAD_LETTER jobs are not returned by get_pending (worker must not pick them up)."""
    db = tmp_path / "jobs.db"
    q1 = SQLiteJobQueue(db_path=db)
    jid = _exhaust_to_dead_letter(q1, "dead.job")
    q1.shutdown()

    q2 = SQLiteJobQueue(db_path=db)
    pending = q2.get_pending(limit=10)
    assert not any(j.job_id == jid for j in pending), "DEAD_LETTER jobs must not be in pending"
    q2.shutdown()


def test_redrive_then_persist_across_restart(tmp_path: Path) -> None:
    """After re-drive, the PENDING state also persists across a restart."""
    db = tmp_path / "jobs.db"

    # Phase 1: dead-letter it.
    q1 = SQLiteJobQueue(db_path=db)
    jid = _exhaust_to_dead_letter(q1, "rdr.job")
    count = q1.redrive_dead_letter()
    assert count == 1
    q1.shutdown()

    # Phase 2: new instance — must see it as PENDING.
    q2 = SQLiteJobQueue(db_path=db)
    job = q2.get_job(jid)
    assert job is not None and job.status == JobStatus.PENDING
    q2.shutdown()


# ---------------------------------------------------------------------------
# Guard: cleanup removes completed but not dead-letter (mixed queue)
# ---------------------------------------------------------------------------


def test_cleanup_removes_completed_but_not_dead_letter(tmp_path: Path) -> None:
    """cleanup_completed removes COMPLETED and terminal-FAILED but spares DEAD_LETTER."""
    q = _sqlite_queue(tmp_path)

    # Enqueue a job that will complete successfully.
    completed_jid = q.enqueue(Job(job_id="", name="ok.job", handler_name="ok.job", payload={}))
    ok_reg = JobRegistry()
    ok_reg.register("ok.job", lambda **_kw: "done")
    JobWorker(q, registry=ok_reg).execute_one()

    assert q.get_job(completed_jid) is not None
    assert q.get_job(completed_jid).status == JobStatus.COMPLETED  # type: ignore[union-attr]

    # Enqueue a job that will dead-letter.
    dl_jid = _exhaust_to_dead_letter(q, "fail.job")
    assert q.get_job(dl_jid) is not None
    assert q.get_job(dl_jid).status == JobStatus.DEAD_LETTER  # type: ignore[union-attr]

    removed = q.cleanup_completed(older_than_hours=0)
    assert removed == 1  # only the completed job removed
    assert q.get_job(completed_jid) is None
    assert q.get_job(dl_jid) is not None
    q.shutdown()
