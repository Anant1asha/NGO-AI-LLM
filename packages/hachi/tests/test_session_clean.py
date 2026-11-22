"""Tests for `hachi session clean` CLI command and SessionStore.delete_sessions_before.

Uses patched SessionStore and a real in-memory SQLite store (via tmp_path) to test
the backend independently.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.core.session_store import SessionStore

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A date far enough in the past that any --older-than N will include it.
_OLD_DATE = "2020-01-01T00:00:00+00:00"
# A date far enough in the future that it will never be cleaned.
_NEW_DATE = "2099-12-31T23:59:59+00:00"

_OLD_SESSION = {
    "id": "old000-0000-0000-0000-000000000001",
    "started_at": _OLD_DATE,
    "ended_at": _OLD_DATE,
    "model": "claude-opus-4-5",
    "total_turns": 5,
}
_NEW_SESSION = {
    "id": "new000-0000-0000-0000-000000000002",
    "started_at": _NEW_DATE,
    "ended_at": _NEW_DATE,
    "model": "claude-opus-4-5",
    "total_turns": 3,
}


def _mock_store(sessions=None, delete_before_result: int = 1) -> MagicMock:
    store = MagicMock()
    store.get_recent_sessions.return_value = sessions if sessions is not None else [_OLD_SESSION]
    store.delete_sessions_before.return_value = delete_before_result
    return store


# ---------------------------------------------------------------------------
# SessionStore.delete_sessions_before — real SQLite backend
# ---------------------------------------------------------------------------


def _real_store(tmp_path: Path) -> SessionStore:
    """Return a SessionStore backed by a temp file (no global state pollution)."""
    from unittest.mock import patch as _patch

    db_path = tmp_path / "sessions.db"
    with _patch(
        "hachi.core.session_store.SessionStore._db_path",
        new_callable=lambda: property(lambda self: db_path),
    ):  # noqa: E501
        store = SessionStore()
    return store


def _seed_sessions(conn: sqlite3.Connection) -> None:
    """Insert two sessions directly into the DB (bypass the store's lock)."""
    conn.execute(
        "INSERT INTO sessions (id, started_at, model, total_turns) VALUES (?,?,?,?)",
        ("old001", "2020-06-01T00:00:00", "m", 2),
    )
    conn.execute(
        "INSERT INTO sessions (id, started_at, model, total_turns) VALUES (?,?,?,?)",
        ("new001", "2099-06-01T00:00:00", "m", 1),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
        ("old001", "user", "hello", "2020-06-01T00:00:01"),
    )
    conn.commit()


def test_delete_sessions_before_removes_old_and_messages(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SessionStore.__new__(SessionStore)
    import threading

    store._conn = sqlite3.connect(str(db_path), check_same_thread=False)
    store._conn.row_factory = sqlite3.Row
    store._lock = threading.Lock()
    store._init_schema()

    _seed_sessions(store._conn)

    cutoff = "2050-01-01T00:00:00"
    deleted = store.delete_sessions_before(cutoff)

    assert deleted == 1
    # old session gone
    assert store._conn.execute("SELECT id FROM sessions WHERE id='old001'").fetchone() is None
    # new session untouched
    assert store._conn.execute("SELECT id FROM sessions WHERE id='new001'").fetchone() is not None
    # messages for old session deleted
    assert (
        store._conn.execute("SELECT id FROM messages WHERE session_id='old001'").fetchone() is None
    )
    store.shutdown()


def test_delete_sessions_before_returns_zero_when_nothing_matches(tmp_path: Path) -> None:
    db_path = tmp_path / "sessions.db"
    store = SessionStore.__new__(SessionStore)
    import threading

    store._conn = sqlite3.connect(str(db_path), check_same_thread=False)
    store._conn.row_factory = sqlite3.Row
    store._lock = threading.Lock()
    store._init_schema()

    _seed_sessions(store._conn)

    # Cutoff in the distant past — nothing matches
    deleted = store.delete_sessions_before("1990-01-01T00:00:00")
    assert deleted == 0
    store.shutdown()


# ---------------------------------------------------------------------------
# CLI: session clean — happy path
# ---------------------------------------------------------------------------


def test_session_clean_yes_deletes_old_sessions() -> None:
    store = _mock_store(sessions=[_OLD_SESSION])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    store.delete_sessions_before.assert_called_once()


def test_session_clean_json_deletes_and_returns_count() -> None:
    store = _mock_store(sessions=[_OLD_SESSION], delete_before_result=1)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deleted"] == 1
    assert payload["dry_run"] is False
    assert "cutoff" in payload


def test_session_clean_nothing_to_clean() -> None:
    store = _mock_store(sessions=[_NEW_SESSION])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--yes"])
    assert result.exit_code == 0
    assert "Nothing to clean" in result.output
    store.delete_sessions_before.assert_not_called()


def test_session_clean_nothing_json() -> None:
    store = _mock_store(sessions=[_NEW_SESSION])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deleted"] == 0


def test_session_clean_dry_run_does_not_delete() -> None:
    store = _mock_store(sessions=[_OLD_SESSION])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run" in result.output or "would delete" in result.output.lower()
    store.delete_sessions_before.assert_not_called()


def test_session_clean_dry_run_json() -> None:
    store = _mock_store(sessions=[_OLD_SESSION])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--dry-run", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["would_delete"] == 1
    assert payload["deleted"] == 0
    store.delete_sessions_before.assert_not_called()


def test_session_clean_custom_older_than() -> None:
    """--older-than 365 should still catch the year-2020 fixture session."""
    store = _mock_store(sessions=[_OLD_SESSION])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--older-than", "365", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_session_clean_multiple_sessions() -> None:
    old2 = {**_OLD_SESSION, "id": "old000-0000-0000-0000-000000000099"}
    store = _mock_store(sessions=[_OLD_SESSION, old2], delete_before_result=2)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "clean", "--json"])
    payload = json.loads(result.output)
    assert payload["deleted"] == 2
