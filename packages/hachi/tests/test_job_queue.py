from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta

from hachi.core.runtime_events import RuntimeEvent, now_iso
from hachi.core.runtime_read_models import RuntimeReadModelStore
from hachi.jobs import InMemoryJobQueue, Job, JobStatus, JobWorker


def _event_sink(read_models: RuntimeReadModelStore):
    def _emit(name: str, payload: dict) -> None:
        read_models.append_event(
            RuntimeEvent(name=name, payload=dict(payload), timestamp=now_iso())
        )

    return _emit


def test_job_queue_defers_future_jobs() -> None:
    queue = InMemoryJobQueue()
    future_job = Job(
        job_id="",
        name="delayed",
        status=JobStatus.PENDING,
        func=lambda: "ok",
        scheduled_for=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )

    queue.enqueue(future_job)

    assert queue.get_pending(limit=10) == []

    future_job.scheduled_for = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    pending = queue.get_pending(limit=10)

    assert len(pending) == 1
    assert pending[0].name == "delayed"


def test_job_worker_retries_then_completes() -> None:
    queue = InMemoryJobQueue()
    read_models = RuntimeReadModelStore()
    worker = JobWorker(queue, on_job_event=_event_sink(read_models))

    attempts = {"count": 0}

    def _flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("boom")
        return "ok"

    job = Job(
        job_id="",
        name="flaky-job",
        status=JobStatus.PENDING,
        func=_flaky,
        max_retries=2,
        backoff_base_seconds=0.01,
        job_type="prefetch",
    )

    queue.enqueue(job)

    assert worker.execute_one() is True
    assert attempts["count"] == 1
    assert job.status == JobStatus.PENDING
    assert job.scheduled_for is not None
    assert datetime.fromisoformat(job.scheduled_for) > datetime.now(UTC)
    assert queue.get_pending(limit=10) == []

    job.scheduled_for = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()

    assert worker.execute_one() is True
    assert attempts["count"] == 2
    assert job.status == JobStatus.COMPLETED
    assert job.result is not None
    assert job.result.output == "ok"


def test_failed_job_reaches_read_model_projection() -> None:
    queue = InMemoryJobQueue()
    read_models = RuntimeReadModelStore()
    worker = JobWorker(queue, on_job_event=_event_sink(read_models))

    def _explode() -> None:
        raise RuntimeError("kaput")

    job = Job(
        job_id="",
        name="explode-job",
        status=JobStatus.PENDING,
        func=_explode,
        max_retries=1,
        job_type="persist",
    )

    queue.enqueue(job)

    assert worker.execute_one() is True

    failures = read_models.failed_jobs()
    assert len(failures) == 1
    assert failures[0].job_id == job.job_id
    assert failures[0].label == "explode-job"
    assert failures[0].error == "kaput"
    # max_retries=1 → retry-exhausted → dead-letter (not terminal FAILED), so the
    # event is "job.dead_letter"; the read-model still surfaces it via failed_jobs().
    assert read_models.runtime_events(limit=10)[-1].name == "job.dead_letter"


def test_pending_job_cannot_be_claimed_twice() -> None:
    queue = InMemoryJobQueue()
    job = Job(
        job_id="",
        name="once-only",
        status=JobStatus.PENDING,
        func=lambda: "ok",
    )
    job_id = queue.enqueue(job)

    first = queue.update_status(job_id, JobStatus.RUNNING)
    second = queue.update_status(job_id, JobStatus.RUNNING)

    assert first is True
    assert second is False


def test_two_workers_race_only_executes_one_claim() -> None:
    queue = InMemoryJobQueue()
    worker_a = JobWorker(queue)
    worker_b = JobWorker(queue)
    attempts = {"count": 0}

    def _work() -> str:
        attempts["count"] += 1
        time.sleep(0.02)
        return "ok"

    queue.enqueue(
        Job(
            job_id="",
            name="single-claim",
            status=JobStatus.PENDING,
            func=_work,
            max_retries=1,
        )
    )

    results: list[bool] = []
    gate = threading.Barrier(2)

    def _run(worker: JobWorker) -> None:
        gate.wait()
        results.append(worker.execute_one())

    t1 = threading.Thread(target=_run, args=(worker_a,))
    t2 = threading.Thread(target=_run, args=(worker_b,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert attempts["count"] == 1
    assert results.count(True) == 1
    assert results.count(False) == 1


def test_retry_backoff_prevents_immediate_reexecution() -> None:
    queue = InMemoryJobQueue()
    worker = JobWorker(queue)

    def _always_fail() -> None:
        raise RuntimeError("retry-me")

    job = Job(
        job_id="",
        name="retry-delay",
        status=JobStatus.PENDING,
        func=_always_fail,
        max_retries=2,
        backoff_base_seconds=30.0,
    )
    queue.enqueue(job)

    assert worker.execute_one() is True
    assert job.status == JobStatus.PENDING
    assert job.attempt == 1
    assert worker.execute_one() is False


def test_cancelled_job_is_never_executed() -> None:
    queue = InMemoryJobQueue()
    worker = JobWorker(queue)
    attempts = {"count": 0}

    def _should_not_run() -> str:
        attempts["count"] += 1
        return "unexpected"

    job = Job(
        job_id="",
        name="cancelled",
        status=JobStatus.PENDING,
        func=_should_not_run,
    )
    job_id = queue.enqueue(job)
    assert queue.update_status(job_id, JobStatus.CANCELLED) is True

    assert worker.execute_one() is False
    assert attempts["count"] == 0


def test_shutdown_does_not_resurrect_completed_or_cancelled_jobs() -> None:
    queue = InMemoryJobQueue()
    worker = JobWorker(queue)

    completed = Job(
        job_id="",
        name="completed",
        status=JobStatus.PENDING,
        func=lambda: "ok",
    )
    cancelled = Job(
        job_id="",
        name="cancelled",
        status=JobStatus.PENDING,
        func=lambda: "nope",
    )

    completed_id = queue.enqueue(completed)
    cancelled_id = queue.enqueue(cancelled)
    assert queue.update_status(cancelled_id, JobStatus.CANCELLED) is True

    assert worker.execute_one() is True
    assert queue.get_job(completed_id).status == JobStatus.COMPLETED

    queue.shutdown()

    assert queue.get_job(completed_id).status == JobStatus.COMPLETED
    assert queue.get_job(cancelled_id).status == JobStatus.CANCELLED
    assert worker.execute_one() is False
