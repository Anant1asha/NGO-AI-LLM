"""Tests for session cost/token persistence.

Covers:
  1. record_session_cost — stores total_tokens and total_cost_usd
  2. get_session returns new columns (total_tokens, total_cost_usd)
  3. get_recent_sessions includes the new columns
  4. Migration: old DBs that lack the columns still open without error
  5. session stats --json includes total_tokens and total_cost_usd
  6. session stats --json sums cost across all sessions
  7. session show --json includes total_tokens and total_cost_usd
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


# ─── SessionStore unit tests ─────────────────────────────────────────────────


class TestRecordSessionCost:
    def test_record_stores_tokens_and_cost(self, tmp_path: Path) -> None:
        store = SessionStore(db_path=str(tmp_path / "s.db"))
        try:
            sid = store.start_session(model="claude-sonnet")
            store.record_session_cost(sid, total_tokens=5000, total_cost_usd=0.015)
            row = store.get_session(sid)
            assert row is not None
            assert int(row["total_tokens"]) == 5000
            assert abs(float(row["total_cost_usd"]) - 0.015) < 1e-9
        finally:
            store.shutdown()

    def test_record_overwrites_previous_values(self, tmp_path: Path) -> None:
        store = SessionStore(db_path=str(tmp_path / "s.db"))
        try:
            sid = store.start_session(model="m")
            store.record_session_cost(sid, 1000, 0.003)
            store.record_session_cost(sid, 2000, 0.006)
            row = store.get_session(sid)
            assert int(row["total_tokens"]) == 2000  # type: ignore[index]
        finally:
            store.shutdown()

    def test_new_session_defaults_to_zero(self, tmp_path: Path) -> None:
        store = SessionStore(db_path=str(tmp_path / "s.db"))
        try:
            sid = store.start_session(model="m")
            row = store.get_session(sid)
            assert int(row["total_tokens"] or 0) == 0  # type: ignore[index]
            assert float(row["total_cost_usd"] or 0.0) == 0.0  # type: ignore[index]
        finally:
            store.shutdown()

    def test_get_recent_sessions_includes_cost_columns(self, tmp_path: Path) -> None:
        store = SessionStore(db_path=str(tmp_path / "s.db"))
        try:
            sid = store.start_session(model="m")
            store.record_session_cost(sid, 300, 0.001)
            sessions = store.get_recent_sessions(limit=5)
            assert sessions
            row = sessions[0]
            assert "total_tokens" in row
            assert "total_cost_usd" in row
        finally:
            store.shutdown()


class TestMigrationCompatibility:
    def test_old_db_without_cost_columns_opens_without_error(self, tmp_path: Path) -> None:
        db_path = tmp_path / "old.db"
        # Create a DB with the old schema (no total_tokens / total_cost_usd columns).
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
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
        """)
        conn.commit()
        conn.close()

        # Opening via SessionStore should apply migrations without crashing.
        store = SessionStore(db_path=str(db_path))
        try:
            sid = store.start_session(model="m")
            store.record_session_cost(sid, 100, 0.0005)
            row = store.get_session(sid)
            assert int(row["total_tokens"]) == 100  # type: ignore[index]
        finally:
            store.shutdown()


# ─── CLI tests ────────────────────────────────────────────────────────────────


def _fake_sessions_with_cost() -> list[dict]:
    return [
        {
            "id": "aaa111",
            "started_at": "2026-06-01T10:00:00+00:00",
            "ended_at": "2026-06-01T10:30:00+00:00",
            "model": "claude-sonnet",
            "total_turns": 5,
            "title": "Session A",
            "total_tokens": 8000,
            "total_cost_usd": 0.024,
        },
        {
            "id": "bbb222",
            "started_at": "2026-06-02T09:00:00+00:00",
            "ended_at": None,
            "model": "claude-sonnet",
            "total_turns": 3,
            "title": "Session B",
            "total_tokens": 3000,
            "total_cost_usd": 0.009,
        },
    ]


class TestSessionStatsWithCost:
    def test_json_includes_total_tokens_and_cost(self) -> None:
        sessions = _fake_sessions_with_cost()
        fake_store = MagicMock()
        fake_store.get_recent_sessions.return_value = sessions
        with patch("hachi.core.session_store.SessionStore", return_value=fake_store):
            result = runner.invoke(app, ["session", "stats", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_tokens"] == 11000
        assert abs(data["total_cost_usd"] - 0.033) < 1e-6

    def test_json_zero_cost_when_columns_missing(self) -> None:
        sessions = [
            {"id": "x", "started_at": "2026-06-01T00:00:00+00:00", "model": "m", "total_turns": 1}
        ]
        fake_store = MagicMock()
        fake_store.get_recent_sessions.return_value = sessions
        with patch("hachi.core.session_store.SessionStore", return_value=fake_store):
            result = runner.invoke(app, ["session", "stats", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_tokens"] == 0
        assert data["total_cost_usd"] == 0.0


class TestSessionShowWithCost:
    def test_json_includes_cost_columns(self) -> None:
        sessions = _fake_sessions_with_cost()
        fake_store = MagicMock()
        fake_store.get_recent_sessions.return_value = sessions
        fake_store.get_session.return_value = sessions[0]
        fake_store.get_session_messages.return_value = [
            {"role": "user", "content": "hi", "tool_name": None, "timestamp": "2026-06-01T10:00:00"}
        ]
        with patch("hachi.core.session_store.SessionStore", return_value=fake_store):
            result = runner.invoke(app, ["session", "show", "aaa111", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_tokens"] == 8000
        assert abs(data["total_cost_usd"] - 0.024) < 1e-9

    def test_human_output_shows_cost_when_nonzero(self) -> None:
        sessions = _fake_sessions_with_cost()
        fake_store = MagicMock()
        fake_store.get_recent_sessions.return_value = sessions
        fake_store.get_session.return_value = sessions[0]
        fake_store.get_session_messages.return_value = [
            {
                "role": "user",
                "content": "hello",
                "tool_name": None,
                "timestamp": "2026-06-01T10:00:00",
            }
        ]
        with patch("hachi.core.session_store.SessionStore", return_value=fake_store):
            result = runner.invoke(app, ["session", "show", "aaa111"])
        assert result.exit_code == 0
        assert "8,000" in result.output or "8000" in result.output
        assert "0.024" in result.output
