"""Tests for `hachi session stats` CLI command.

All tests use a patched SessionStore so no real SQLite I/O is needed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

_SESSIONS = [
    {
        "id": "aabb0001-0000-0000-0000-000000000001",
        "started_at": "2026-06-01T09:00:00",
        "ended_at": "2026-06-01T09:05:00",
        "model": "claude-opus-4-5",
        "total_turns": 4,
    },
    {
        "id": "aabb0002-0000-0000-0000-000000000002",
        "started_at": "2026-06-01T14:00:00",
        "ended_at": "2026-06-01T14:10:00",
        "model": "claude-opus-4-5",
        "total_turns": 6,
    },
    {
        "id": "aabb0003-0000-0000-0000-000000000003",
        "started_at": "2026-06-02T10:00:00",
        "ended_at": "2026-06-02T10:20:00",
        "model": "claude-sonnet-4-5",
        "total_turns": 10,
    },
]


def _mock_store(sessions=None) -> MagicMock:
    store = MagicMock()
    store.get_recent_sessions.return_value = sessions if sessions is not None else _SESSIONS
    return store


def test_session_stats_human_output() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats"])
    assert result.exit_code == 0
    assert "3" in result.output  # total_sessions
    assert "20" in result.output  # total_turns (4+6+10)


def test_session_stats_json_output() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total_sessions"] == 3
    assert payload["total_turns"] == 20


def test_session_stats_avg_turns() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    payload = json.loads(result.output)
    # (4+6+10)/3 = 6.666... rounded to 6.7
    assert payload["avg_turns_per_session"] == pytest.approx(6.7, abs=0.1)


def test_session_stats_date_range() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    payload = json.loads(result.output)
    assert payload["first_session"] == "2026-06-01"
    assert payload["last_session"] == "2026-06-02"


def test_session_stats_most_active_date() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    payload = json.loads(result.output)
    assert payload["most_active_date"] == "2026-06-01"
    assert payload["most_active_date_count"] == 2


def test_session_stats_most_used_model() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    payload = json.loads(result.output)
    assert payload["most_used_model"] == "claude-opus-4-5"


def test_session_stats_empty_exits_0() -> None:
    store = _mock_store(sessions=[])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats"])
    assert result.exit_code == 0
    assert "No sessions" in result.output


def test_session_stats_empty_json() -> None:
    store = _mock_store(sessions=[])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total_sessions"] == 0


def test_session_stats_single_session() -> None:
    single = [_SESSIONS[0]]
    store = _mock_store(sessions=single)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    payload = json.loads(result.output)
    assert payload["total_sessions"] == 1
    assert payload["first_session"] == payload["last_session"] == "2026-06-01"


def test_session_stats_null_turns_treated_as_zero() -> None:
    sessions = [{**_SESSIONS[0], "total_turns": None}]
    store = _mock_store(sessions=sessions)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "stats", "--json"])
    payload = json.loads(result.output)
    assert payload["total_turns"] == 0


import pytest  # noqa: E402
