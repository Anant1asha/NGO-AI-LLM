"""Tests for P1-03: Loud memory failures.

Verifies that memory write failures are never silently swallowed:
- A broken Chroma backend causes a job failure, visible in failed_jobs()
- Enqueue failures log loudly (no thread fallback)
- No daemon thread is spawned when no queue is configured (warning emitted instead)
"""

from __future__ import annotations

import logging
import threading
import time
from unittest.mock import MagicMock, patch

from hachi.core.memory import MemoryManager
from hachi.core.runtime_events import RuntimeEvent
from hachi.core.runtime_read_models import RuntimeReadModelStore
from hachi.jobs.queue import InMemoryJobQueue, JobWorker

# Long enough to pass the len < 30 guard in sync_turn
_USER = "The user prefers Python over Ruby and uses dark mode consistently"
_ASSISTANT = "Understood, I will remember your preferences for future sessions"


def _make_manager_with_queue() -> tuple[MemoryManager, InMemoryJobQueue]:
    queue = InMemoryJobQueue()
    mgr = MemoryManager(max_active_messages=50, job_queue=queue)
    return mgr, queue


def test_broken_vault_routes_failure_to_jobs_failed() -> None:
    """A broken vault backend → job fails → appears in queue's failed jobs."""
    mgr, queue = _make_manager_with_queue()
    vault = MagicMock()
    mgr.set_vault(vault)

    def broken_extraction(combined: str) -> None:
        raise RuntimeError("Chroma unavailable: disk full")

    with patch.object(mgr, "_run_fact_extraction", broken_extraction):
        mgr.sync_turn(_USER, _ASSISTANT)

    pending = queue.get_pending(limit=1)
    assert pending, "sync_turn should have enqueued a fact_extraction job"

    # Force single-attempt failure
    pending[0].max_retries = 1

    worker = JobWorker(queue, on_job_event=lambda name, payload: None)
    worker.execute_one()  # attempt 1 → fails, max_retries=1 → immediately FAILED
    worker.execute_one()  # noop (nothing pending)

    failed = queue.get_failed_jobs(limit=10)
    assert failed, "Broken vault must produce a FAILED job in the queue"
    assert any(j.name == "fact_extraction" for j in failed)


def test_broken_vault_routes_to_read_model() -> None:
    """job.failed events from broken vault flow into RuntimeReadModelStore.failed_jobs()."""
    mgr, queue = _make_manager_with_queue()
    vault = MagicMock()
    mgr.set_vault(vault)

    def broken_extraction(combined: str) -> None:
        raise RuntimeError("Chroma disk full")

    with patch.object(mgr, "_run_fact_extraction", broken_extraction):
        mgr.sync_turn(_USER, _ASSISTANT)

    pending = queue.get_pending(limit=1)
    assert pending
    pending[0].max_retries = 1

    read_models = RuntimeReadModelStore()

    def on_event(name: str, payload: dict) -> None:
        read_models.append_event(
            RuntimeEvent(name=name, payload=payload, timestamp="2026-01-01T00:00:00+00:00")
        )

    worker = JobWorker(queue, on_job_event=on_event)
    worker.execute_one()
    worker.execute_one()

    failures = read_models.failed_jobs(limit=10)
    assert failures, "RuntimeReadModelStore must capture the job failure"
    assert any("extraction" in f.label or "fact" in f.label for f in failures)


def test_no_thread_spawned_when_no_queue(caplog) -> None:
    """When no job queue is configured, sync_turn logs a warning and spawns no thread."""
    mgr = MemoryManager(max_active_messages=50)  # no job_queue
    vault = MagicMock()
    mgr.set_vault(vault)

    before = threading.active_count()

    with caplog.at_level(logging.WARNING, logger="hachi.core.memory"):
        mgr.sync_turn(_USER, _ASSISTANT)

    time.sleep(0.05)  # let any accidental thread start
    after = threading.active_count()

    assert after <= before, "No daemon thread must be spawned when no queue is configured"
    warn_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("job queue" in m.lower() or "queue" in m.lower() for m in warn_messages), (
        f"Expected a warning about missing job queue, got: {warn_messages}"
    )


def test_enqueue_failure_logs_error_not_thread(caplog) -> None:
    """If enqueueing fails, an error is logged — no silent thread fallback."""
    queue = MagicMock()
    queue.enqueue.side_effect = RuntimeError("queue is full")

    mgr = MemoryManager(max_active_messages=50, job_queue=queue)
    vault = MagicMock()
    mgr.set_vault(vault)

    before = threading.active_count()

    with caplog.at_level(logging.ERROR, logger="hachi.core.memory"):
        mgr.sync_turn(_USER, _ASSISTANT)

    time.sleep(0.05)
    after = threading.active_count()

    assert after <= before, "No daemon thread must be spawned on enqueue failure"
    error_messages = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
    assert any(
        "enqueue" in m.lower() or "fact extraction" in m.lower()
        for m in error_messages
    ), f"Expected an error log for enqueue failure, got: {error_messages}"
