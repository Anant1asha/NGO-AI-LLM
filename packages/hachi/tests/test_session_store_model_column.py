"""Tests for the model column in the messages table (Bug 6).

Covers:
  1. log_message stores model for assistant messages; None for user messages is fine.
  2. get_session_messages returns model for each row.
  3. Migration: a legacy DB without the model column is upgraded in place.
  4. control_plane synthesized session.chat.completed event carries model from DB.
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


def test_log_message_stores_model_for_assistant(store: SessionStore) -> None:
    """Assistant log_message with a model kw-arg must round-trip via get_session_messages."""
    sid = store.start_session()
    store.log_message(sid, "user", "hello")
    store.log_message(sid, "assistant", "hi there", model="claude-sonnet-4-6")
    msgs = store.get_session_messages(sid)
    assert len(msgs) == 2
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["model"] == "claude-sonnet-4-6"
    # user messages have no model — None is acceptable
    assert msgs[0]["model"] is None


def test_get_session_messages_includes_model_key(store: SessionStore) -> None:
    """Every row in get_session_messages must expose a 'model' key (may be None)."""
    sid = store.start_session()
    store.log_message(sid, "user", "q")
    msgs = store.get_session_messages(sid)
    assert "model" in msgs[0], "model key missing from get_session_messages rows"


def test_messages_model_migration(tmp_path) -> None:
    """A legacy DB without a model column on messages must be migrated in place."""
    db_path = tmp_path / "legacy.db"
    # Build a pre-migration DB without the model column.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            model TEXT,
            total_turns INTEGER DEFAULT 0,
            title TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_name TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO sessions (id, started_at) VALUES ('s1', '2026-01-01')")
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) "
        "VALUES ('s1', 'user', 'hello', '2026-01-01')"
    )
    conn.commit()
    conn.close()

    # Opening via SessionStore must not crash and must add the column.
    store = SessionStore(db_path=str(db_path))
    msgs = store.get_session_messages("s1")
    assert len(msgs) == 1
    assert "model" in msgs[0]
    assert msgs[0]["model"] is None  # NULL for pre-migration rows
    store.shutdown()


def test_messages_composite_index_on_fresh_db(tmp_path) -> None:
    """Fresh SessionStore must have composite idx_msg_session_id (B8)."""
    store = SessionStore(db_path=str(tmp_path / "fresh.db"))
    indexes = {
        row[0]
        for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='messages'"
        )
    }
    store.shutdown()
    assert "idx_msg_session_id" in indexes, "composite index missing on fresh DB"
    assert "idx_msg_session" not in indexes, "old single-column index must not exist on fresh DB"


def test_messages_composite_index_migration(tmp_path) -> None:
    """A DB carrying only the old idx_msg_session must be upgraded to the composite index (B8)."""
    db_path = tmp_path / "old_index.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
            ended_at TEXT, model TEXT, total_turns INTEGER DEFAULT 0, title TEXT,
            total_tokens INTEGER DEFAULT 0, total_cost_usd REAL DEFAULT 0.0,
            owner_token_hash TEXT);
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT,
            tool_name TEXT, timestamp TEXT NOT NULL, model TEXT);
        CREATE INDEX idx_msg_session ON messages(session_id);
    """)
    conn.commit()
    conn.close()

    store = SessionStore(db_path=str(db_path))
    indexes = {
        row[0]
        for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='messages'"
        )
    }
    store.shutdown()
    assert "idx_msg_session_id" in indexes, "composite index not created by migration"
    assert "idx_msg_session" not in indexes, "old single-column index not dropped by migration"


def test_control_plane_synthesized_completed_event_carries_model(tmp_path) -> None:
    """session.chat.completed events synthesised from DB messages must carry model."""
    store = SessionStore(db_path=str(tmp_path / "test.db"))
    sid = store.start_session()
    store.log_message(sid, "user", "q")
    store.log_message(sid, "assistant", "a", model="gpt-4o-mini")
    store.flush_sync()

    from hachi.gateway.control_plane import GatewayControlPlane

    cp = GatewayControlPlane(get_session_messages=store.get_session_messages)
    events = cp._synthesize_history_events(sid, after=0, limit=100)
    completed = [e for e in events if e["event_type"] == "session.chat.completed"]
    assert completed, "No session.chat.completed event synthesised"
    assert completed[0]["payload"].get("model") == "gpt-4o-mini", (
        f"Expected model='gpt-4o-mini' in completed payload, got: {completed[0]['payload']}"
    )
    store.shutdown()
