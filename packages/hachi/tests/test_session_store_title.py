"""Tests for session title persistence in SessionStore.

Covers:
  1. New stores carry a `title` column; it defaults to None
  2. set_session_title round-trips via get_session / get_recent_sessions
  3. get_sessions_missing_title returns only untitled sessions with messages
  4. Migration: a legacy DB without the title column is upgraded in place
"""

from __future__ import annotations

import sqlite3

import pytest

from hachi.core.session_store import SessionStore


@pytest.fixture()
def store(tmp_path):
    s = SessionStore(db_path=str(tmp_path / "test.db"))
    yield s
    s.shutdown()


def _seed(store: SessionStore, messages: int = 1) -> str:
    sid = store.start_session(model="test-model")
    for i in range(messages):
        store.log_message(sid, "user", f"message {i}")
    return sid


# ---------------------------------------------------------------------------
# 1. Default title is None
# ---------------------------------------------------------------------------


def test_new_session_has_null_title(store: SessionStore) -> None:
    sid = _seed(store)
    meta = store.get_session(sid)
    assert meta is not None
    assert meta["title"] is None


def test_get_recent_sessions_includes_title_key(store: SessionStore) -> None:
    _seed(store)
    recent = store.get_recent_sessions(limit=5)
    assert recent and "title" in recent[0]


# ---------------------------------------------------------------------------
# 2. set_session_title round-trips
# ---------------------------------------------------------------------------


def test_set_and_get_title(store: SessionStore) -> None:
    sid = _seed(store)
    store.set_session_title(sid, "Fix Login Bug")
    assert store.get_session(sid)["title"] == "Fix Login Bug"


def test_title_appears_in_recent_sessions(store: SessionStore) -> None:
    sid = _seed(store)
    store.set_session_title(sid, "Plan The Day")
    recent = store.get_recent_sessions(limit=10)
    match = next(s for s in recent if s["id"] == sid)
    assert match["title"] == "Plan The Day"


def test_set_title_overwrites(store: SessionStore) -> None:
    sid = _seed(store)
    store.set_session_title(sid, "First")
    store.set_session_title(sid, "Second")
    assert store.get_session(sid)["title"] == "Second"


def test_get_session_unknown_returns_none(store: SessionStore) -> None:
    assert store.get_session("nope") is None


# ---------------------------------------------------------------------------
# 3. get_sessions_missing_title
# ---------------------------------------------------------------------------


def test_missing_title_lists_untitled(store: SessionStore) -> None:
    titled = _seed(store)
    untitled = _seed(store)
    store.set_session_title(titled, "Has Title")

    ids = [s["id"] for s in store.get_sessions_missing_title()]
    assert untitled in ids
    assert titled not in ids


def test_missing_title_respects_limit(store: SessionStore) -> None:
    for _ in range(3):
        _seed(store)
    assert len(store.get_sessions_missing_title(limit=2)) == 2


def test_missing_title_treats_empty_string_as_missing(store: SessionStore) -> None:
    sid = _seed(store)
    store.set_session_title(sid, "")
    ids = [s["id"] for s in store.get_sessions_missing_title()]
    assert sid in ids


# ---------------------------------------------------------------------------
# 4. Migration of a legacy DB (no title column)
# ---------------------------------------------------------------------------


def test_migration_adds_title_to_legacy_db(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    # Hand-build a pre-title schema and seed a row.
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            model TEXT,
            total_turns INTEGER DEFAULT 0
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_name TEXT,
            timestamp TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO sessions (id, started_at, model) "
        "VALUES ('legacy1', '2020-01-01T00:00:00', 'm')"
    )
    conn.commit()
    conn.close()

    # Opening via SessionStore should migrate the column in place.
    store = SessionStore(db_path=str(db_path))
    try:
        meta = store.get_session("legacy1")
        assert meta is not None
        assert meta["title"] is None
        store.set_session_title("legacy1", "Recovered Title")
        assert store.get_session("legacy1")["title"] == "Recovered Title"
    finally:
        store.shutdown()
