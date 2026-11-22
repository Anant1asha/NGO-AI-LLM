"""RunStateStore — SQLite persistence for durable run state.

Mirrors SessionStore WAL/backup patterns:
- Single persistent connection with RLock
- WAL journal mode
- Additive migrations via core.migrations.apply_migrations
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from hachi.core.migrations import apply_migrations
from hachi.core.runtime.state import RunState, RunStatus, WaitCondition, WaitKind

logger = logging.getLogger(__name__)

_INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    wait_kind       TEXT,
    wait_key        TEXT,
    wait_timeout_at TEXT,
    resume_cursor   INTEGER NOT NULL DEFAULT 0,
    payload         TEXT NOT NULL DEFAULT '{}',
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs (session_id);
CREATE INDEX IF NOT EXISTS idx_runs_status  ON runs (status);
"""

# Migration list: (column, definition) pairs to add if missing.
# Use apply_migrations() for safe additive evolution.
_MIGRATIONS: list[tuple[str, str]] = [
    # Example future migration:
    # ("created_at", "TEXT"),
]


def _default_db_path() -> Path:
    from hachi.core.paths import get_hachi_paths

    paths = get_hachi_paths()
    data_dir: Path = paths.data_dir
    return data_dir / "runs.db"


class RunStateStore:
    """SQLite-backed store for durable run state.

    Thread-safe via RLock.  Single persistent connection (WAL mode).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Args:
            db_path: Path to the SQLite database file.
                     Defaults to ``<hachi-data-dir>/runs.db``.
        """
        self._db_path = db_path or _default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self._db_path), timeout=10, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    @contextmanager
    def _db(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_INITIAL_SCHEMA)
            self._conn.commit()
            apply_migrations(self._conn, "runs", _MIGRATIONS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert(self, run: RunState) -> None:
        """Insert or replace a run state record."""
        wait = run.wait
        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO runs
                    (run_id, session_id, status, wait_kind, wait_key,
                     wait_timeout_at, resume_cursor, payload, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id) DO UPDATE SET
                    session_id      = excluded.session_id,
                    status          = excluded.status,
                    wait_kind       = excluded.wait_kind,
                    wait_key        = excluded.wait_key,
                    wait_timeout_at = excluded.wait_timeout_at,
                    resume_cursor   = excluded.resume_cursor,
                    payload         = excluded.payload,
                    updated_at      = excluded.updated_at
                """,
                (
                    run.run_id,
                    run.session_id,
                    run.status.value,
                    wait.kind.value if wait else None,
                    wait.key if wait else None,
                    wait.timeout_at if wait else None,
                    run.resume_cursor,
                    json.dumps(run.payload),
                    run.updated_at,
                ),
            )

    def get(self, run_id: str) -> RunState | None:
        """Return a RunState by run_id, or None if not found."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def waiting(self) -> list[RunState]:
        """Return all runs in WAITING status (for restart recovery)."""
        with self._lock:
            rows = self._conn.execute("SELECT * FROM runs WHERE status = 'waiting'").fetchall()
        return [self._row_to_run(r) for r in rows]

    def by_session(self, session_id: str) -> list[RunState]:
        """Return all runs for a session, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs WHERE session_id = ? ORDER BY updated_at DESC",
                (session_id,),
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def list_all(self, limit: int = 100) -> list[RunState]:
        """Return recent runs across all sessions (for GET /runs)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> RunState:
        wait: WaitCondition | None = None
        if row["wait_kind"]:
            wait = WaitCondition(
                kind=WaitKind(row["wait_kind"]),
                key=row["wait_key"] or "",
                created_at=row["updated_at"],  # approximation for restored records
                timeout_at=row["wait_timeout_at"],
            )
        payload_raw = row["payload"] or "{}"
        try:
            payload = json.loads(payload_raw)
        except Exception:
            payload = {}
        return RunState(
            run_id=row["run_id"],
            session_id=row["session_id"],
            status=RunStatus(row["status"]),
            wait=wait,
            resume_cursor=int(row["resume_cursor"] or 0),
            payload=payload,
            updated_at=row["updated_at"],
        )
