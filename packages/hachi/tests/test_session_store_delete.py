"""Tests for SessionStore.delete_session.

Covers:
  1. Delete a session that exists — returns True, session + messages gone
  2. Delete a session that doesn't exist — returns False, no error
  3. Delete removes only the targeted session, not others
  4. Delete is idempotent — second call returns False (already gone)
"""

from __future__ import annotations

import pytest

from hachi.core.session_store import SessionStore


@pytest.fixture()
def store(tmp_path):
    s = SessionStore(db_path=str(tmp_path / "test.db"))
    yield s
    s.shutdown()


def _seed(store: SessionStore, messages: int = 2) -> str:
    """Start a session, log `messages` user messages, return the session ID."""
    sid = store.start_session(model="test-model")
    for i in range(messages):
        store.log_message(sid, "user", f"message {i}")
    return sid


# ---------------------------------------------------------------------------
# 1. Delete existing session — True, rows removed
# ---------------------------------------------------------------------------


def test_delete_existing_session_returns_true(store: SessionStore) -> None:
    sid = _seed(store)
    assert store.delete_session(sid) is True


def test_delete_removes_session_row(store: SessionStore) -> None:
    sid = _seed(store)
    store.delete_session(sid)
    remaining = store.get_recent_sessions(limit=100)
    assert all(s["id"] != sid for s in remaining)


def test_delete_removes_associated_messages(store: SessionStore) -> None:
    sid = _seed(store, messages=3)
    store.delete_session(sid)
    msgs = store.get_session_messages(sid)
    assert msgs == []


# ---------------------------------------------------------------------------
# 2. Delete non-existent session — False
# ---------------------------------------------------------------------------


def test_delete_nonexistent_returns_false(store: SessionStore) -> None:
    assert store.delete_session("does-not-exist") is False


# ---------------------------------------------------------------------------
# 3. Delete only targets the specified session
# ---------------------------------------------------------------------------


def test_delete_leaves_other_sessions_intact(store: SessionStore) -> None:
    sid_a = _seed(store, messages=1)
    sid_b = _seed(store, messages=2)

    store.delete_session(sid_a)

    # sid_b survives
    remaining = store.get_recent_sessions(limit=100)
    ids = [s["id"] for s in remaining]
    assert sid_b in ids
    assert sid_a not in ids

    # Messages for sid_b still there
    msgs = store.get_session_messages(sid_b)
    assert len(msgs) == 2


# ---------------------------------------------------------------------------
# 4. Idempotent — second delete returns False
# ---------------------------------------------------------------------------


def test_delete_idempotent(store: SessionStore) -> None:
    sid = _seed(store)
    assert store.delete_session(sid) is True
    assert store.delete_session(sid) is False
