from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from hachi.core.session_store import SessionStore


def test_log_message_rejects_unknown_session_id(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            store.log_message("missing-session", "user", "orphan")
    finally:
        store.shutdown()


def test_log_message_truncates_content_at_50k_boundary(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        session_id = store.start_session(model="test")
        exact = "a" * 50_000
        over = "b" * 50_001

        store.log_message(session_id, "assistant", exact)
        store.log_message(session_id, "assistant", over)

        rows = store._conn.execute(
            "SELECT content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        assert len(rows[0]["content"]) == 50_000
        assert len(rows[1]["content"]) == 50_000
        assert rows[0]["content"] == exact
        assert rows[1]["content"] == "b" * 50_000
    finally:
        store.shutdown()


def test_log_message_preserves_unicode_and_control_characters(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        session_id = store.start_session(model="test")
        payload = "unicode snowman: \u2603\ncontrol:\x00\x1f\nrtl:\u202e"

        store.log_message(session_id, "user", payload)
        row = store._conn.execute(
            "SELECT content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()

        assert row is not None
        assert row["content"] == payload
    finally:
        store.shutdown()


def test_concurrent_log_writes_remain_consistent(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        session_id = store.start_session(model="test")
        workers = 8
        per_worker = 40

        def _writer(worker_id: int) -> None:
            for i in range(per_worker):
                store.log_message(session_id, "user", f"w{worker_id}:{i}")

        threads = [threading.Thread(target=_writer, args=(idx,)) for idx in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        row = store._conn.execute(
            "SELECT COUNT(*) AS total FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        assert row is not None
        assert row["total"] == workers * per_worker
    finally:
        store.shutdown()


def test_search_and_recent_reads_survive_parallel_writes_and_session_end(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        session_ids = [store.start_session(model="test") for _ in range(3)]
        errors: list[Exception] = []
        stop = threading.Event()

        def _writer(session_id: str, worker_id: int) -> None:
            try:
                for i in range(120):
                    store.log_message(session_id, "user", f"needle worker={worker_id} i={i}")
                    if i % 20 == 0:
                        time.sleep(0.001)
            except Exception as exc:  # pragma: no cover - diagnostic capture
                errors.append(exc)

        def _reader() -> None:
            try:
                while not stop.is_set():
                    store.search_sessions("needle", limit=20)
                    store.get_recent_sessions(limit=10)
            except Exception as exc:  # pragma: no cover - diagnostic capture
                errors.append(exc)

        def _ender() -> None:
            try:
                for session_id in session_ids:
                    time.sleep(0.002)
                    store.end_session(session_id)
            except Exception as exc:  # pragma: no cover - diagnostic capture
                errors.append(exc)

        writers = [
            threading.Thread(target=_writer, args=(session_id, idx))
            for idx, session_id in enumerate(session_ids)
        ]
        reader = threading.Thread(target=_reader)
        ender = threading.Thread(target=_ender)

        reader.start()
        ender.start()
        for thread in writers:
            thread.start()

        for thread in writers:
            thread.join()
        ender.join()
        stop.set()
        reader.join(timeout=1.0)

        assert errors == []

        found = store.search_sessions("needle", limit=50)
        assert found
        assert {row["session_id"] for row in found}.issubset(set(session_ids))

        recent = store.get_recent_sessions(limit=10)
        assert recent
        assert {row["id"] for row in recent}.issubset(set(session_ids))
    finally:
        store.shutdown()
