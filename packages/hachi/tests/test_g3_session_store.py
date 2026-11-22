"""G3 Epic — SessionStore performance and reliability tests.

Covers:
  G3-T5 (MED-001): Batch log_message commits — <=6 commits for 30 messages,
                    flush_sync() persists all pending rows, reads auto-flush,
                    FK integrity (parent session always committed before children).
  G3-T7 (REL-04):  WAL mode active on file-backed DB; backup() produces a
                    readable copy with identical rows.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from hachi.core.session_store import SessionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class CommitCounter:
    """Wraps a sqlite3.Connection and counts how many times commit() is called."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.count = 0
        self._lock = threading.Lock()

    def __getattr__(self, name: str):  # noqa: ANN001
        return getattr(self._conn, name)

    def commit(self) -> None:
        with self._lock:
            self.count += 1
        self._conn.commit()


def _make_store_with_counter(tmp_path: Path) -> tuple[SessionStore, CommitCounter]:
    """Create a SessionStore whose connection is wrapped by CommitCounter."""
    db_path = str(tmp_path / "sessions.db")
    store = SessionStore(db_path=db_path)
    counter = CommitCounter(store._conn)
    # Replace the connection with our spy *after* schema init (which commits itself).
    store._conn = counter  # type: ignore[assignment]
    return store, counter


# ---------------------------------------------------------------------------
# G3-T5-a: <=6 commits for 30 log_message calls
# ---------------------------------------------------------------------------


def test_30_messages_produce_at_most_6_commits(tmp_path: Path) -> None:
    """MED-001: 30 log_message calls must result in <=6 SQLite commits."""
    store, counter = _make_store_with_counter(tmp_path)
    try:
        session_id = store.start_session(model="test")
        # start_session itself commits (1 commit) — reset counter so we only
        # measure log_message commit behaviour.
        counter.count = 0

        for i in range(30):
            store.log_message(session_id, "user", f"message {i}")

        # Give the timer a brief chance to fire if batch-size hasn't fired yet.
        time.sleep(store._BATCH_INTERVAL_S + 0.2)

        assert counter.count <= 6, (
            f"Expected <=6 commits for 30 messages, got {counter.count}"
        )
    finally:
        store.shutdown()


# ---------------------------------------------------------------------------
# G3-T5-b: flush_sync() commits all pending messages, visible on re-read
# ---------------------------------------------------------------------------


def test_flush_sync_persists_all_buffered_messages(tmp_path: Path) -> None:
    """flush_sync() must make all buffered rows durable on a new connection."""
    db_path = str(tmp_path / "sessions.db")
    store = SessionStore(db_path=db_path)
    try:
        session_id = store.start_session(model="test")

        # Log fewer than _BATCH_SIZE so nothing auto-commits.
        n = min(store._BATCH_SIZE - 1, 5)
        for i in range(n):
            store.log_message(session_id, "user", f"msg {i}")

        # Some messages should be pending (uncommitted).
        assert store._uncommitted > 0, "Expected uncommitted messages before flush"

        store.flush_sync()
        assert store._uncommitted == 0
    finally:
        store.shutdown()

    # Open a brand-new connection to verify durability (not just same-conn read).
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT content FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()

    assert len(rows) == n
    for i, row in enumerate(rows):
        assert row["content"] == f"msg {i}"


# ---------------------------------------------------------------------------
# G3-T5-c: read methods flush pending first
# ---------------------------------------------------------------------------


def test_get_session_messages_flushes_pending(tmp_path: Path) -> None:
    """get_session_messages must include messages not yet committed when called."""
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        session_id = store.start_session(model="test")

        # Keep below batch size so there is definitely something uncommitted.
        n = min(store._BATCH_SIZE - 1, 5)
        for i in range(n):
            store.log_message(session_id, "user", f"pending {i}")

        # Cancel timer to prove flush_sync() is called, not the timer.
        with store._lock:
            if store._flush_timer and store._flush_timer.is_alive():
                store._flush_timer.cancel()
        store._flush_timer = None

        msgs = store.get_session_messages(session_id)
        assert len(msgs) == n, (
            f"Expected {n} messages from get_session_messages, got {len(msgs)}"
        )
    finally:
        store.shutdown()


# ---------------------------------------------------------------------------
# G3-T5-d: FK integrity — message always has a committed parent session
# ---------------------------------------------------------------------------


def test_fk_integrity_log_message_rejects_unknown_session(tmp_path: Path) -> None:
    """log_message must raise IntegrityError immediately for a non-existent session.

    This verifies that start_session commits synchronously (parent row exists)
    while log_message defers only the COMMIT, not the INSERT — so FK enforcement
    still triggers on INSERT with an unknown session_id.
    """
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            store.log_message("nonexistent-session-id", "user", "orphan")
    finally:
        store.shutdown()


def test_fk_integrity_valid_session_messages_survive_flush(tmp_path: Path) -> None:
    """Messages for a real (committed) session must survive a full flush."""
    db_path = str(tmp_path / "sessions.db")
    store = SessionStore(db_path=db_path)
    try:
        session_id = store.start_session(model="test")
        for i in range(5):
            store.log_message(session_id, "assistant", f"response {i}")
        store.flush_sync()
    finally:
        store.shutdown()

    # Confirm rows on a clean connection (FK parent committed before flush).
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    rows = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    assert rows[0] == 5


def test_start_session_is_committed_synchronously(tmp_path: Path) -> None:
    """start_session row must be readable from a separate connection immediately."""
    db_path = str(tmp_path / "sessions.db")
    store = SessionStore(db_path=db_path)
    try:
        session_id = store.start_session(model="test")
        # Check from a brand-new connection — no flush needed.
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        conn.close()
        assert row is not None, "start_session must commit the session row immediately"
    finally:
        store.shutdown()


# ---------------------------------------------------------------------------
# G3-T7-a: WAL mode active for file-backed DB
# ---------------------------------------------------------------------------


def test_wal_mode_is_active_for_file_db(tmp_path: Path) -> None:
    """PRAGMA journal_mode must return 'wal' for a file-backed SessionStore."""
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        row = store._conn.execute("PRAGMA journal_mode").fetchone()
        assert row is not None
        mode = row[0] if isinstance(row, (list, tuple)) else row["journal_mode"]
        assert mode == "wal", f"Expected WAL mode, got {mode!r}"
    finally:
        store.shutdown()


# ---------------------------------------------------------------------------
# G3-T7-b: backup() produces a readable copy with identical rows
# ---------------------------------------------------------------------------


def test_backup_produces_readable_copy_with_same_rows(tmp_path: Path) -> None:
    """backup() must create a file-backed copy containing the same sessions and messages."""
    db_path = str(tmp_path / "sessions.db")
    backup_path = tmp_path / "sessions.backup.db"

    store = SessionStore(db_path=db_path)
    try:
        session_id = store.start_session(model="backup-test")
        for i in range(5):
            store.log_message(session_id, "user", f"backup msg {i}")
        store.end_session(session_id)

        store.backup(backup_path)
    finally:
        store.shutdown()

    # Read the backup on a fresh connection.
    conn = sqlite3.connect(str(backup_path))
    conn.row_factory = sqlite3.Row

    sessions = conn.execute("SELECT id FROM sessions").fetchall()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id

    msgs = conn.execute(
        "SELECT content FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()

    assert len(msgs) == 5
    for i, row in enumerate(msgs):
        assert row["content"] == f"backup msg {i}"


def test_backup_includes_pending_uncommitted_messages(tmp_path: Path) -> None:
    """backup() must flush pending messages before snapshotting."""
    db_path = str(tmp_path / "sessions.db")
    backup_path = tmp_path / "pending_backup.db"

    store = SessionStore(db_path=db_path)
    try:
        session_id = store.start_session(model="test")
        # Write fewer than batch-size so there are pending uncommitted rows.
        n = min(store._BATCH_SIZE - 1, 3)
        for i in range(n):
            store.log_message(session_id, "user", f"pending {i}")

        # backup() must flush first.
        store.backup(backup_path)
    finally:
        store.shutdown()

    conn = sqlite3.connect(str(backup_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    conn.close()
    assert count == n


# ---------------------------------------------------------------------------
# G3-T5-e: end_session flushes before reading turn count
# ---------------------------------------------------------------------------


def test_end_session_flushes_and_counts_turns_accurately(tmp_path: Path) -> None:
    """end_session must flush pending messages so turn count is accurate."""
    db_path = str(tmp_path / "sessions.db")
    store = SessionStore(db_path=db_path)
    try:
        session_id = store.start_session(model="test")
        # Log 3 user messages and 2 assistant messages (turns = user count = 3).
        for i in range(3):
            store.log_message(session_id, "user", f"u{i}")
            store.log_message(session_id, "assistant", f"a{i}")

        # Don't manually flush — end_session should do it.
        store.end_session(session_id)

        row = store._conn.execute(
            "SELECT total_turns FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == 3
    finally:
        store.shutdown()
