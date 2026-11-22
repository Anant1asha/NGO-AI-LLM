"""
Durable Job Queue — Replaces background daemon threads with visible work tracking

This module provides a job queue interface and backends:
    - InMemoryJobQueue: fast, no persistence (default for tests)
    - SQLiteJobQueue: durable, survives restarts, supports registry dispatch

Registry dispatch: SQLite jobs store ``handler_name`` + ``payload`` (serializable
dict) instead of a live callable. The ``JobRegistry`` maps names → callables at
worker creation time so jobs survive process restarts.

The resident worker (``ResidentWorkerThread``) drains the queue continuously in the
background; ``_drain_job_queue`` in AgentSession is demoted to a one-shot fallback
used only when no resident worker is running.
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from hachi.core.runtime_events import JOB_RETRY

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    """Job lifecycle states."""

    PENDING = "pending"  # Queued, waiting to execute
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Structurally unexecutable (terminal, no handler)
    DEAD_LETTER = "dead_letter"  # Retry-exhausted but handler exists; re-driveable
    CANCELLED = "cancelled"  # Explicitly cancelled


@dataclass(slots=True)
class JobResult:
    """Outcome of a job execution."""

    status: JobStatus
    output: Any | None = None
    error: str | None = None
    exception: str | None = None
    duration_seconds: float = 0.0


@dataclass(slots=True)
class Job:
    """A single unit of work in the queue."""

    job_id: str
    name: str
    status: JobStatus = JobStatus.PENDING

    # Callable-based dispatch (in-memory only — not persisted to SQLite)
    func: Callable | None = field(default=None, repr=False)
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)

    # Registry-based dispatch (serializable — used by SQLiteJobQueue)
    handler_name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    # Retry logic
    attempt: int = 0
    max_retries: int = 3
    backoff_base_seconds: float = 2.0

    # Timing
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    scheduled_for: str | None = None

    # Results
    result: JobResult | None = None

    # Metadata (for audit/routing)
    session_id: str | None = None
    turn_id: str | None = None
    job_type: str = "background"  # "background", "prefetch", "sync", "persist", "delegate"

    def to_dict(self) -> dict[str, Any]:
        """Serialize job to dict (excluding the callable func)."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status.value,
            "handler_name": self.handler_name,
            "payload": self.payload,
            "attempt": self.attempt,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "scheduled_for": self.scheduled_for,
            "result": {
                "status": self.result.status.value,
                "output": str(self.result.output)[:500] if self.result.output else None,
                "error": self.result.error,
                "duration_seconds": self.result.duration_seconds,
            }
            if self.result
            else None,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "job_type": self.job_type,
        }


class JobQueue(ABC):
    """Abstract interface for a durable job queue backend."""

    @abstractmethod
    def enqueue(self, job: Job) -> str:
        """
        Add a job to the queue.

        Args:
            job: The job to enqueue

        Returns:
            The job ID
        """
        pass

    @abstractmethod
    def get_pending(self, limit: int = 10) -> list[Job]:
        """Fetch up to `limit` pending jobs."""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Job | None:
        """Fetch a job by ID."""
        pass

    @abstractmethod
    def update_status(
        self, job_id: str, status: JobStatus, result: JobResult | None = None
    ) -> bool:
        """
        Update a job's status and optionally set its result.

        Returns:
            True if updated, False if job not found
        """
        pass

    @abstractmethod
    def get_recent_jobs(self, limit: int = 50, job_type: str | None = None) -> list[Job]:
        """Fetch recent jobs, optionally filtered by type."""
        pass

    @abstractmethod
    def get_failed_jobs(self, limit: int = 20) -> list[Job]:
        """Fetch failed jobs for debugging/recovery."""
        pass

    @abstractmethod
    def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Remove completed/failed jobs older than N hours. Returns count removed.

        DEAD_LETTER jobs are NOT removed by this method — they persist until
        explicitly re-driven or purged.
        """
        pass

    @abstractmethod
    def redrive_dead_letter(self) -> int:
        """Reset all DEAD_LETTER jobs to PENDING (attempt=0) so they run again.

        Returns:
            The number of jobs re-queued.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Graceful shutdown (flush pending work if durable backend)."""
        pass


class InMemoryJobQueue(JobQueue):
    """
    Simple in-memory job queue for MVP.

    Note: Jobs are lost on process restart. Durable SQLite backend
    comes in Phase 1 upgrade v1.0.
    """

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._pending_queue: list[str] = []  # job_ids in order
        self._lock = threading.RLock()

    def enqueue(self, job: Job) -> str:
        """Add job to queue."""
        with self._lock:
            if not job.job_id:
                job.job_id = str(uuid.uuid4())
            if not job.scheduled_for:
                job.scheduled_for = datetime.now(UTC).isoformat()
            self._jobs[job.job_id] = job
            self._pending_queue.append(job.job_id)
        logger.debug(f"Enqueued job {job.name} (id={job.job_id})")
        return job.job_id

    def get_pending(self, limit: int = 10) -> list[Job]:
        """Fetch pending jobs."""
        with self._lock:
            result = []
            seen = set()
            now = datetime.now(UTC)
            for job_id in self._pending_queue:
                if job_id in seen or job_id not in self._jobs:
                    continue
                job = self._jobs[job_id]
                if job.status != JobStatus.PENDING:
                    continue

                if job.scheduled_for:
                    try:
                        scheduled_dt = datetime.fromisoformat(job.scheduled_for)
                        if scheduled_dt > now:
                            continue
                    except Exception:
                        pass

                result.append(job)
                seen.add(job_id)
                if len(result) >= limit:
                    break
            return result

    def get_job(self, job_id: str) -> Job | None:
        """Fetch a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(
        self, job_id: str, status: JobStatus, result: JobResult | None = None
    ) -> bool:
        """Update job status."""
        with self._lock:
            if job_id not in self._jobs:
                return False

            job = self._jobs[job_id]
            if status == JobStatus.RUNNING and job.status != JobStatus.PENDING:
                return False

            job.status = status
            if result:
                job.result = result
            if status == JobStatus.RUNNING and not job.started_at:
                job.started_at = datetime.now(UTC).isoformat()

            if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD_LETTER):
                job.completed_at = datetime.now(UTC).isoformat()

            return True

    def get_recent_jobs(self, limit: int = 50, job_type: str | None = None) -> list[Job]:
        """Fetch recent jobs."""
        with self._lock:
            jobs = list(self._jobs.values())
            if job_type:
                jobs = [j for j in jobs if j.job_type == job_type]
            # Sort by creation time, most recent first
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]

    def get_failed_jobs(self, limit: int = 20) -> list[Job]:
        """Fetch failed jobs."""
        with self._lock:
            failed = [j for j in self._jobs.values() if j.status == JobStatus.FAILED]
            failed.sort(key=lambda j: j.completed_at or j.created_at, reverse=True)
            return failed[:limit]

    def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Remove old completed or terminal-structural-failed jobs.

        DEAD_LETTER jobs are intentionally preserved — they hold state needed for
        re-drive and must only be removed by explicit purge or ``redrive_dead_letter``.
        """
        with self._lock:
            cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
            count = 0
            to_delete = []

            for job_id, job in self._jobs.items():
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    if job.completed_at:
                        completed_dt = datetime.fromisoformat(job.completed_at)
                        if completed_dt < cutoff:
                            to_delete.append(job_id)
                            count += 1

            for job_id in to_delete:
                del self._jobs[job_id]
                self._pending_queue = [jid for jid in self._pending_queue if jid != job_id]

        logger.debug(f"Cleaned up {count} old jobs")
        return count

    def redrive_dead_letter(self) -> int:
        """Reset all DEAD_LETTER jobs to PENDING with attempt=0 so they run again.

        Returns:
            The number of jobs re-queued.
        """
        with self._lock:
            count = 0
            for job in self._jobs.values():
                if job.status == JobStatus.DEAD_LETTER:
                    job.status = JobStatus.PENDING
                    job.attempt = 0
                    job.completed_at = None
                    job.scheduled_for = datetime.now(UTC).isoformat()
                    count += 1
        logger.info("InMemoryJobQueue: re-drove %d dead-letter job(s)", count)
        return count

    def shutdown(self) -> None:
        """Shutdown (no-op for in-memory backend)."""
        with self._lock:
            total = len(self._jobs)
        logger.debug(f"InMemoryJobQueue shutdown: {total} jobs in memory")


class JobWorker:
    """
    Executes jobs from the queue with retry logic and event emission.

    Dispatch order:
      1. ``job.func`` — live callable (in-memory only, not durable across restarts).
      2. ``job.handler_name`` resolved via ``registry`` — used by SQLiteJobQueue; the
         handler is called with ``**job.payload``.

    Typically driven by a ``ResidentWorkerThread`` in production.
    """

    def __init__(
        self,
        queue: JobQueue,
        on_job_event: Callable[[str, dict[str, Any]], None] | None = None,
        registry: "JobRegistry | None" = None,
    ):
        self.queue = queue
        self.on_job_event = on_job_event or (lambda *_a, **_kw: None)
        self.registry = registry
        self._running = False

    def execute_one(self) -> bool:
        """
        Fetch and execute one pending job.

        Returns:
            True if a job was executed, False if queue is empty.
        """
        jobs = self.queue.get_pending(limit=1)
        if not jobs:
            return False

        job = jobs[0]
        logger.debug(f"Executing job {job.name} (id={job.job_id})")

        claimed = self.queue.update_status(job.job_id, JobStatus.RUNNING)
        if not claimed:
            return False

        self.on_job_event(
            "job.started",
            {
                "job_id": job.job_id,
                "job_name": job.name,
                "job_type": job.job_type,
                "kind": job.job_type,
                "label": job.name,
            },
        )

        start_time = datetime.now(UTC)
        result = None

        try:
            if job.func:
                output = job.func(*job.args, **job.kwargs)
            elif job.handler_name and self.registry and job.handler_name in self.registry:
                handler = self.registry.resolve(job.handler_name)
                assert handler is not None  # guaranteed by the `in` check above
                output = handler(**job.payload)
            else:
                # No callable and no registered handler — structurally unexecutable.
                # Fail immediately without retrying (retries would all hit the same wall).
                duration = (datetime.now(UTC) - start_time).total_seconds()
                result = JobResult(
                    status=JobStatus.FAILED,
                    error=f"Job {job.name!r}: no callable func and handler_name "
                    f"{job.handler_name!r} is not in registry",
                    duration_seconds=duration,
                )
                logger.warning(
                    "Job %r is unexecutable (no func, no handler) — failing without retry",
                    job.name,
                )
                self.on_job_event(
                    "job.failed",
                    {
                        "job_id": job.job_id,
                        "job_name": job.name,
                        "kind": job.job_type,
                        "status": JobStatus.FAILED.value,
                        "label": job.name,
                        "attempt": job.attempt,
                        "error": result.error,
                        "duration_seconds": duration,
                    },
                )
                self.queue.update_status(job.job_id, JobStatus.FAILED, result=result)
                return True
            duration = (datetime.now(UTC) - start_time).total_seconds()
            result = JobResult(
                status=JobStatus.COMPLETED,
                output=output,
                duration_seconds=duration,
            )
            logger.debug(f"Job {job.name} completed in {duration:.2f}s")
            self.on_job_event(
                "job.completed",
                {
                    "job_id": job.job_id,
                    "job_name": job.name,
                    "duration_seconds": duration,
                    "kind": job.job_type,
                    "label": job.name,
                },
            )
        except Exception as e:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            job.attempt += 1

            if job.attempt < job.max_retries:
                # Retry with backoff
                backoff = job.backoff_base_seconds ** (job.attempt - 1)
                logger.warning(
                    f"Job {job.name} attempt {job.attempt} failed: {e}. "
                    f"Will retry in {backoff:.1f}s"
                )
                job.scheduled_for = (datetime.now(UTC) + timedelta(seconds=backoff)).isoformat()
                # Persist the incremented attempt counter and backoff timestamp.
                # SQLiteJobQueue exposes update_attempt for this; fall back to
                # update_status for the in-memory backend which tracks it in-object.
                _update_attempt = getattr(self.queue, "update_attempt", None)
                if callable(_update_attempt):
                    _update_attempt(job.job_id, job.attempt, job.scheduled_for)
                else:
                    self.queue.update_status(job.job_id, JobStatus.PENDING)
                self.on_job_event(
                    JOB_RETRY,
                    {
                        "job_id": job.job_id,
                        "job_name": job.name,
                        "kind": job.job_type,
                        "label": job.name,
                        "attempt": job.attempt,
                        "error": str(e),
                        "backoff_seconds": backoff,
                    },
                )
            else:
                # Retries exhausted and the handler exists — route to dead-letter so
                # the job is preserved for re-drive rather than silently discarded.
                # (Structurally-unexecutable jobs — no handler — stay terminal FAILED.)
                result = JobResult(
                    status=JobStatus.DEAD_LETTER,
                    error=str(e),
                    exception=f"{type(e).__name__}: {str(e)}",
                    duration_seconds=duration,
                )
                logger.error(
                    "Job %r moved to dead-letter after %d attempt(s): %s",
                    job.name,
                    job.attempt,
                    e,
                )
                self.on_job_event(
                    "job.dead_letter",
                    {
                        "job_id": job.job_id,
                        "job_name": job.name,
                        "kind": job.job_type,
                        "status": JobStatus.DEAD_LETTER.value,
                        "label": job.name,
                        "attempt": job.attempt,
                        "error": str(e),
                        "duration_seconds": duration,
                    },
                )

        if result:
            self.queue.update_status(job.job_id, result.status, result=result)

        return True


# ---------------------------------------------------------------------------
# JobRegistry — maps handler names to callable implementations
# ---------------------------------------------------------------------------


class JobRegistry:
    """Maps job handler names to callable implementations.

    Named handlers are registered once at startup; the SQLiteJobQueue stores the
    name + a serializable payload so jobs survive process restarts.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        """Register a handler under ``name``. Overwrites any prior binding."""
        self._handlers[name] = handler

    def resolve(self, name: str) -> Callable[..., Any] | None:
        return self._handlers.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self._handlers


# ---------------------------------------------------------------------------
# SQLiteJobQueue — durable backend using a local SQLite file
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id              TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    handler_name        TEXT NOT NULL DEFAULT '',
    payload             TEXT NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'pending',
    attempt             INTEGER NOT NULL DEFAULT 0,
    max_retries         INTEGER NOT NULL DEFAULT 3,
    backoff_base_secs   REAL NOT NULL DEFAULT 2.0,
    job_type            TEXT NOT NULL DEFAULT 'background',
    session_id          TEXT,
    turn_id             TEXT,
    owner_id            TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    started_at          TEXT,
    completed_at        TEXT,
    scheduled_for       TEXT,
    result_status       TEXT,
    result_output       TEXT,
    result_error        TEXT,
    result_duration     REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);
"""


def _default_db_path() -> Path:
    from platformdirs import PlatformDirs

    dirs = PlatformDirs("hachi", "opengigantic")
    state_dir = Path(dirs.user_state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "jobs.db"


class SQLiteJobQueue(JobQueue):
    """SQLite-backed durable job queue.

    Jobs with ``handler_name`` set survive process restarts: on boot,
    ``_recover_running()`` resets any RUNNING jobs to PENDING so the resident
    worker picks them up again.

    Jobs with only ``func`` set are stored but cannot be re-executed after a
    restart (the callable is not persisted). They complete normally within the
    same process.

    Func-job ownership: every instance stamps a unique ``_instance_id`` onto the
    ``owner_id`` column of the func-based rows it enqueues (handler-name rows are
    left unowned, ``owner_id=''``, so any worker may run them via the shared
    :class:`JobRegistry`). ``get_pending`` only returns unowned rows or rows this
    instance owns. This prevents a *sibling* instance over the same DB file (the
    gateway boots one ``SQLiteJobQueue`` per agent) from claiming a func job whose
    callable lives only in another instance's in-process side-table and then
    false-failing it with "no callable func and handler_name '' is not in registry".

    HIGH-016: A single persistent ``sqlite3.Connection`` is opened in ``__init__``
    and reused for all operations, eliminating the 2+ open/close cycles per second
    caused by the resident worker's 0.5 s poll interval.  All access is serialised
    through ``self._lock`` (a re-entrant lock so nested acquisitions within the same
    thread, e.g. ``enqueue`` → ``_conn``, are safe).  Call ``shutdown()`` to close
    the connection cleanly.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _default_db_path()
        # Per-instance identity used to scope func-based jobs to their enqueuing
        # instance (see class docstring). Handler-name jobs are left unowned.
        self._instance_id = uuid.uuid4().hex
        # HIGH-016: single persistent connection; all access serialised via _lock.
        # check_same_thread=False is safe because _lock guarantees mutual exclusion.
        self._lock = threading.RLock()
        self._db_conn: sqlite3.Connection = sqlite3.connect(
            str(self._db_path), timeout=10, check_same_thread=False
        )
        self._db_conn.row_factory = sqlite3.Row
        # WAL mode: allows readers to run concurrently with a writer, which
        # matters because the resident worker thread and the main thread both
        # access the queue.  SET HERE before _init_db so the pragma takes effect
        # before any schema writes.  Safe to call on an existing DB — WAL is
        # sticky and survives restarts.
        self._db_conn.execute("PRAGMA journal_mode=WAL")
        # NORMAL durability: can lose the last committed transaction on an OS
        # crash, which is acceptable for ephemeral jobs (prefetch/title/facts)
        # that are meaningless after a restart anyway (see _recover_running).
        self._db_conn.execute("PRAGMA synchronous=NORMAL")
        # In-process side-table for callable (``func``) jobs. SQLite cannot persist a
        # live callable, so func-based jobs are dispatched in-process only — the same
        # model InMemoryJobQueue already uses. The SQLite row still records the job for
        # visibility/audit; the callable is re-attached from here when the worker reads
        # the (func-less) row back. Keyed by job_id, cleared on terminal state, and not
        # durable across a restart: ephemeral work (prefetch/title/fact-extraction) that
        # closes over live runtime state (vault/session) is meaningless after a restart
        # and is failed by ``_recover_running`` instead of silently re-run.
        self._func_table: dict[str, tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = {}
        self._init_db()
        recovered = self._recover_running()
        if recovered:
            logger.info("SQLiteJobQueue: reset %d stale RUNNING jobs to PENDING", recovered)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield the persistent connection under the queue lock.

        Commits on clean exit; rolls back on exception — identical semantics to
        the former per-call open/close pattern, but without the connection overhead.
        The lock is re-entrant (RLock) so callers that already hold it (e.g.
        ``enqueue``) can call ``_conn()`` without deadlocking.
        """
        with self._lock:
            try:
                yield self._db_conn
                self._db_conn.commit()
            except Exception:
                self._db_conn.rollback()
                raise

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA_SQL)
            # Migration: add owner_id to a pre-existing DB created before func-job
            # ownership was introduced. ALTER ADD COLUMN is a no-op-safe one-shot.
            cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "owner_id" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")

    def _recover_running(self) -> int:
        with self._conn() as conn:
            # Reset jobs that were mid-execution when the process died so a worker
            # re-runs them — but ONLY handler-name jobs, which any worker can
            # dispatch via the shared JobRegistry. Func-only jobs cannot resume
            # (their callable lived only in the dead process) so they are swept
            # below instead of being reset into an unrunnable PENDING state.
            cur = conn.execute(
                "UPDATE jobs SET status = 'pending', started_at = NULL "
                "WHERE status = 'running' AND handler_name != ''"
            )
            recovered = int(cur.rowcount)

            # Sweep crash-orphaned func-only rows. Live func jobs run in
            # milliseconds, so any func-only row still pending/running after an
            # hour belongs to a process that is gone. Deleting (not failing) keeps
            # the job header and "Needs attention" list clean — these are internal
            # background jobs with no user action. Fresh sibling-instance func jobs
            # are younger than the cutoff AND invisible to us via the owner_id
            # filter in get_pending(), so they are never touched here.
            cutoff = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
            conn.execute(
                "DELETE FROM jobs "
                "WHERE (handler_name IS NULL OR handler_name = '') "
                "AND status IN ('pending', 'running') AND created_at < ?",
                (cutoff,),
            )

            # One-time cleanup of historical structural false-failures (rows the
            # pre-ownership bug produced) so they stop cluttering the UI on upgrade.
            conn.execute(
                "DELETE FROM jobs WHERE status = 'failed' "
                "AND (result_error LIKE '%no callable func%' "
                "OR result_error LIKE 'Discarded on recovery%')"
            )
            return recovered

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        payload_raw = row["payload"] or "{}"
        try:
            payload = json.loads(payload_raw)
        except Exception:
            payload = {}

        result: JobResult | None = None
        if row["result_status"]:
            result = JobResult(
                status=JobStatus(row["result_status"]),
                output=row["result_output"],
                error=row["result_error"],
                duration_seconds=float(row["result_duration"] or 0.0),
            )

        job = Job(
            job_id=row["job_id"],
            name=row["name"],
            handler_name=row["handler_name"] or "",
            payload=payload,
            status=JobStatus(row["status"]),
            attempt=int(row["attempt"]),
            max_retries=int(row["max_retries"]),
            backoff_base_seconds=float(row["backoff_base_secs"]),
            job_type=row["job_type"] or "background",
            session_id=row["session_id"],
            turn_id=row["turn_id"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            scheduled_for=row["scheduled_for"],
            result=result,
        )
        # Re-attach an in-process callable recorded by enqueue() so the worker can
        # dispatch via job.func, exactly as it would for an InMemoryJobQueue job.
        with self._lock:
            func_entry = self._func_table.get(job.job_id)
        if func_entry is not None:
            job.func, job.args, job.kwargs = func_entry
        return job

    # ------------------------------------------------------------------
    # JobQueue interface
    # ------------------------------------------------------------------

    def enqueue(self, job: Job) -> str:
        with self._lock:
            if not job.job_id:
                job.job_id = str(uuid.uuid4())
            if not job.scheduled_for:
                job.scheduled_for = datetime.now(UTC).isoformat()
            # Retain a callable (func) job in the in-process side-table so the worker
            # can dispatch it after reading the (func-less) row back from SQLite.
            # Func jobs are stamped with this instance's owner_id so a sibling
            # instance over the same DB never claims a callable it does not hold.
            # Handler-name jobs stay unowned ('') — any worker may run them.
            if job.func is not None:
                self._func_table[job.job_id] = (job.func, job.args, job.kwargs)
                owner_id = self._instance_id
            else:
                owner_id = ""
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        job_id, name, handler_name, payload, status, attempt, max_retries,
                        backoff_base_secs, job_type, session_id, turn_id, owner_id,
                        created_at, scheduled_for
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        job.job_id,
                        job.name,
                        job.handler_name,
                        json.dumps(job.payload),
                        job.status.value,
                        job.attempt,
                        job.max_retries,
                        job.backoff_base_seconds,
                        job.job_type,
                        job.session_id,
                        job.turn_id,
                        owner_id,
                        job.created_at,
                        job.scheduled_for,
                    ),
                )
            logger.debug("SQLiteJobQueue: enqueued %s (id=%s)", job.name, job.job_id)
            return job.job_id

    def get_pending(self, limit: int = 10) -> list[Job]:
        now_str = datetime.now(UTC).isoformat()
        # Only consider unowned rows (handler-name jobs, runnable by any worker)
        # or func jobs this instance owns (callable present in our side-table).
        # Excluding sibling-owned func rows at the SQL level avoids both stealing
        # them and starving our own runnable rows behind an un-dispatchable one.
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'pending'
                  AND (scheduled_for IS NULL OR scheduled_for <= ?)
                  AND (owner_id = '' OR owner_id = ?)
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (now_str, self._instance_id, limit),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_job(self, job_id: str) -> Job | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def update_status(
        self, job_id: str, status: JobStatus, result: JobResult | None = None
    ) -> bool:
        now_str = datetime.now(UTC).isoformat()
        with self._lock:
            with self._conn() as conn:
                # Only transition PENDING → RUNNING to avoid double-claiming
                if status == JobStatus.RUNNING:
                    cur = conn.execute(
                        """
                        UPDATE jobs SET status = ?, started_at = ?
                        WHERE job_id = ? AND status = 'pending'
                        """,
                        (status.value, now_str, job_id),
                    )
                    if cur.rowcount == 0:
                        return False
                elif result:
                    conn.execute(
                        """
                        UPDATE jobs SET
                            status = ?,
                            completed_at = ?,
                            result_status = ?,
                            result_output = ?,
                            result_error = ?,
                            result_duration = ?
                        WHERE job_id = ?
                        """,
                        (
                            status.value,
                            now_str,
                            result.status.value,
                            str(result.output)[:500] if result.output else None,
                            result.error,
                            result.duration_seconds,
                            job_id,
                        ),
                    )
                else:
                    conn.execute(
                        "UPDATE jobs SET status = ? WHERE job_id = ?",
                        (status.value, job_id),
                    )
                # A terminal or dead-lettered job no longer needs its callable retained.
                if status in (
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.DEAD_LETTER,
                    JobStatus.CANCELLED,
                ):
                    self._func_table.pop(job_id, None)
                return True

    def update_attempt(self, job_id: str, attempt: int, scheduled_for: str) -> None:
        """Persist a retry attempt and its backoff timestamp."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET attempt = ?, scheduled_for = ?, status = 'pending'"
                " WHERE job_id = ?",
                (attempt, scheduled_for, job_id),
            )

    def get_recent_jobs(self, limit: int = 50, job_type: str | None = None) -> list[Job]:
        if job_type:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE job_type = ? ORDER BY created_at DESC LIMIT ?",
                    (job_type, limit),
                ).fetchall()
        else:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_failed_jobs(self, limit: int = 20) -> list[Job]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'failed' ORDER BY completed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Remove completed or terminal-structural-failed jobs older than N hours.

        DEAD_LETTER jobs are intentionally excluded — they hold state needed for
        re-drive and must only be removed by explicit purge or ``redrive_dead_letter``.
        """
        cutoff = (datetime.now(UTC) - timedelta(hours=older_than_hours)).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """
                DELETE FROM jobs
                WHERE status IN ('completed', 'failed', 'cancelled')
                  AND completed_at IS NOT NULL
                  AND completed_at < ?
                """,
                (cutoff,),
            )
            count = int(cur.rowcount)
        logger.debug("SQLiteJobQueue: cleaned up %d old jobs", count)
        return count

    def redrive_dead_letter(self) -> int:
        """Reset all DEAD_LETTER rows to PENDING with attempt=0 so they run again.

        The ``completed_at`` and ``result_*`` columns are cleared so the job looks
        fresh to the worker.  Returns the count of rows updated.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = 'pending',
                    attempt = 0,
                    completed_at = NULL,
                    scheduled_for = ?,
                    result_status = NULL,
                    result_output = NULL,
                    result_error = NULL,
                    result_duration = NULL
                WHERE status = 'dead_letter'
                """,
                (datetime.now(UTC).isoformat(),),
            )
            count = int(cur.rowcount)
        logger.info("SQLiteJobQueue: re-drove %d dead-letter job(s)", count)
        return count

    def shutdown(self) -> None:
        with self._lock:
            # Best-effort: drop our own un-drained func jobs so they do not linger
            # as zombie rows after we exit (their callable dies with this process).
            # Handler-name jobs (owner_id='') are left for other/future workers.
            try:
                with self._conn() as conn:
                    conn.execute(
                        "DELETE FROM jobs WHERE owner_id = ? AND status IN ('pending', 'running')",
                        (self._instance_id,),
                    )
            except Exception:
                pass
            self._func_table.clear()
            try:
                self._db_conn.close()
            except Exception:
                pass
        logger.debug("SQLiteJobQueue shutdown (db=%s)", self._db_path)


# ---------------------------------------------------------------------------
# ResidentWorkerThread — continuous background queue drainer
# ---------------------------------------------------------------------------


class ResidentWorkerThread:
    """Daemon thread that continuously drains a JobQueue via a JobWorker.

    Start once at agent boot; ``AgentSession._drain_job_queue()`` becomes a
    no-op while this thread is running. On shutdown, ``stop()`` signals the
    thread to exit and joins it with a short timeout.

    When the queue is idle (``execute_one`` returns False), the thread also runs
    a periodic retention sweep every ``sweep_interval_seconds`` seconds (BB-72):
    old completed jobs, idempotency keys, interaction-log rows, daily-spend rows,
    and file-edit checkpoints are pruned according to the configured TTLs.
    """

    def __init__(
        self,
        worker: JobWorker,
        poll_interval: float = 0.5,
        *,
        session_store: "Any | None" = None,
        checkpoint_manager: "Any | None" = None,
        sweep_interval_seconds: float = 3600.0,
        jobs_retention_hours: int = 24,
        interaction_log_retention_days: int = 90,
        idempotency_key_retention_hours: int = 48,
        daily_spend_retention_days: int = 365,
        checkpoint_retention_days: int = 30,
    ) -> None:
        self._worker = worker
        self._poll_interval = poll_interval
        self._session_store = session_store
        self._checkpoint_manager = checkpoint_manager
        self._sweep_interval = sweep_interval_seconds
        self._jobs_retention_hours = jobs_retention_hours
        self._interaction_log_retention_days = interaction_log_retention_days
        self._idempotency_key_retention_hours = idempotency_key_retention_hours
        self._daily_spend_retention_days = daily_spend_retention_days
        self._checkpoint_retention_days = checkpoint_retention_days
        self._last_sweep: float = 0.0  # initialised in _run so first idle fires the sweep
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="hachi-job-worker",
        )

    def start(self) -> None:
        self._thread.start()
        logger.debug("ResidentWorkerThread started")

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        logger.debug("ResidentWorkerThread stopped (alive=%s)", self._thread.is_alive())

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        self._last_sweep = time.monotonic()
        while not self._stop_event.is_set():
            try:
                ran = self._worker.execute_one()
                if not ran:
                    self._stop_event.wait(self._poll_interval)
                    self._maybe_sweep()
            except Exception:
                logger.exception("ResidentWorkerThread: uncaught error in execute_one")
                self._stop_event.wait(self._poll_interval)
                self._maybe_sweep()  # keep sweep ticking even when the job path errors

    def _maybe_sweep(self) -> None:
        now = time.monotonic()
        if now - self._last_sweep < self._sweep_interval:
            return
        self._last_sweep = now
        self._do_sweep()

    def _do_sweep(self) -> None:
        """Run all retention-cleanup routines (BB-72)."""
        try:
            removed = self._worker.queue.cleanup_completed(
                older_than_hours=self._jobs_retention_hours
            )
            if removed:
                logger.info("RetentionSweep: pruned %d completed job(s)", removed)
        except Exception:
            logger.exception("RetentionSweep: error cleaning up jobs")

        if self._session_store is not None:
            try:
                n = self._session_store.cleanup_idempotency_keys(
                    older_than_hours=self._idempotency_key_retention_hours
                )
                if n:
                    logger.info("RetentionSweep: pruned %d idempotency key(s)", n)
            except Exception:
                logger.exception("RetentionSweep: error cleaning up idempotency keys")

            try:
                n = self._session_store.cleanup_interaction_log(
                    older_than_days=self._interaction_log_retention_days
                )
                if n:
                    logger.info("RetentionSweep: pruned %d interaction_log row(s)", n)
            except Exception:
                logger.exception("RetentionSweep: error cleaning up interaction log")

            try:
                n = self._session_store.cleanup_daily_spend(
                    older_than_days=self._daily_spend_retention_days
                )
                if n:
                    logger.info("RetentionSweep: pruned %d daily_spend row(s)", n)
            except Exception:
                logger.exception("RetentionSweep: error cleaning up daily spend")

        if self._checkpoint_manager is not None:
            try:
                n = self._checkpoint_manager.prune_old_snapshots(
                    older_than_days=self._checkpoint_retention_days
                )
                if n:
                    logger.info("RetentionSweep: pruned %d old checkpoint(s)", n)
            except Exception:
                logger.exception("RetentionSweep: error pruning checkpoints")
