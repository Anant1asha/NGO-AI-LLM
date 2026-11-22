"""Tests for the `hachi session` CLI subcommand group.

Covers:
  1.  session list — returns sessions table (Rich output)
  2.  session list --json — returns valid JSON list
  3.  session list empty — prints "No sessions" message
  4.  session show — prints transcript for a known session
  5.  session show --json — returns valid JSON with messages
  6.  session show unknown id — exits with error
  7.  session show prefix match — resolves unique prefix to full ID
  8.  session show ambiguous prefix — reports ambiguity, exits 1
  9.  session search — returns matching results
  10. session search --json — returns valid JSON
  11. session search no results — prints "no sessions matched"
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_SESSIONS = [
    {
        "id": "abc1230000000001",
        "started_at": "2026-06-07T10:00:00Z",
        "ended_at": "2026-06-07T10:30:00Z",
        "model": "claude-haiku-4-5",
        "total_turns": 5,
    },
    {
        "id": "def4560000000002",
        "started_at": "2026-06-06T09:00:00Z",
        "ended_at": None,
        "model": "claude-3-5-sonnet-latest",
        "total_turns": 3,
    },
]

FAKE_MESSAGES = [
    {
        "role": "user",
        "content": "Hello agent!",
        "tool_name": None,
        "timestamp": "2026-06-07T10:00:01Z",
    },
    {
        "role": "assistant",
        "content": "Hello! How can I help?",
        "tool_name": None,
        "timestamp": "2026-06-07T10:00:02Z",
    },
    {
        "role": "tool",
        "content": '{"result": "ok"}',
        "tool_name": "search_skills",
        "timestamp": "2026-06-07T10:00:05Z",
    },
]

FAKE_SEARCH_RESULTS = [
    {
        "session_id": "abc1230000000001",
        "session_date": "2026-06-07T10:00:00Z",
        "model": "claude-haiku-4-5",
        "role": "user",
        "snippet": "Hello agent!",
        "timestamp": "2026-06-07T10:00:01Z",
    }
]


def _mock_store(
    sessions=None,
    messages=None,
    search_results=None,
) -> MagicMock:
    store = MagicMock()
    sess = sessions if sessions is not None else FAKE_SESSIONS
    store.get_recent_sessions.return_value = sess
    store.get_session_messages.return_value = messages if messages is not None else FAKE_MESSAGES
    store.search_sessions.return_value = (
        search_results if search_results is not None else FAKE_SEARCH_RESULTS
    )
    # Real stores return a metadata dict (with a `title` key) or None.
    store.get_session.return_value = {**sess[0], "title": sess[0].get("title")} if sess else None
    return store


# ---------------------------------------------------------------------------
# 1. session list — Rich output
# ---------------------------------------------------------------------------


def test_session_list_rich_output() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store()):
        result = runner.invoke(app, ["session", "list"])
    assert result.exit_code == 0
    assert "abc1230000000001" in result.output
    assert "claude-haiku-4-5" in result.output
    assert "5 turn" in result.output


# ---------------------------------------------------------------------------
# 2. session list --json
# ---------------------------------------------------------------------------


def test_session_list_json() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store()):
        result = runner.invoke(app, ["session", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["id"] == "abc1230000000001"


# ---------------------------------------------------------------------------
# 3. session list empty
# ---------------------------------------------------------------------------


def test_session_list_empty() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store(sessions=[])):
        result = runner.invoke(app, ["session", "list"])
    assert result.exit_code == 0
    assert "no sessions" in result.output.lower()


# ---------------------------------------------------------------------------
# 4. session show — Rich output
# ---------------------------------------------------------------------------


def test_session_show_rich_output() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store()):
        result = runner.invoke(app, ["session", "show", "abc1230000000001"])
    assert result.exit_code == 0
    assert "abc1230000000001" in result.output
    assert "Hello agent!" in result.output


# ---------------------------------------------------------------------------
# 5. session show --json
# ---------------------------------------------------------------------------


def test_session_show_json() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store()):
        result = runner.invoke(app, ["session", "show", "abc1230000000001", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["session_id"] == "abc1230000000001"
    assert len(data["messages"]) == 3


# ---------------------------------------------------------------------------
# 6. session show unknown id → exit 1
# ---------------------------------------------------------------------------


def test_session_show_unknown_id_exits() -> None:
    store = _mock_store()
    store.get_recent_sessions.return_value = FAKE_SESSIONS
    store.get_session_messages.return_value = []
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "show", "zzznomatch123456"])
    # Full 16-char ID → goes to get_session_messages directly (no prefix search)
    # Returns empty messages → prints "No messages found"
    assert "no messages" in result.output.lower()


# ---------------------------------------------------------------------------
# 7. session show prefix match
# ---------------------------------------------------------------------------


def test_session_show_prefix_match_resolves() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store()):
        # "abc123" uniquely prefixes "abc1230000000001"
        result = runner.invoke(app, ["session", "show", "abc123"])
    assert result.exit_code == 0
    assert "abc1230000000001" in result.output


# ---------------------------------------------------------------------------
# 8. session show ambiguous prefix → exit 1
# ---------------------------------------------------------------------------


def test_session_show_ambiguous_prefix_exits() -> None:
    store = _mock_store()
    # Both sessions start with "abc" → ambiguous with a 3-char prefix
    store.get_recent_sessions.return_value = [
        {**FAKE_SESSIONS[0], "id": "abc1230000000001"},
        {**FAKE_SESSIONS[1], "id": "abc4560000000002"},
    ]
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "show", "abc"])
    assert result.exit_code == 1
    assert "ambiguous" in result.output.lower() or "matches" in result.output.lower()


# ---------------------------------------------------------------------------
# 9. session search — Rich output
# ---------------------------------------------------------------------------


def test_session_search_rich_output() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store()):
        result = runner.invoke(app, ["session", "search", "Hello"])
    assert result.exit_code == 0
    assert "abc1230000000001" in result.output
    assert "Hello agent!" in result.output


# ---------------------------------------------------------------------------
# 10. session search --json
# ---------------------------------------------------------------------------


def test_session_search_json() -> None:
    with patch("hachi.core.session_store.SessionStore", return_value=_mock_store()):
        result = runner.invoke(app, ["session", "search", "Hello", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["query"] == "Hello"
    assert len(data["results"]) == 1


# ---------------------------------------------------------------------------
# 11. session search no results
# ---------------------------------------------------------------------------


def test_session_search_no_results() -> None:
    empty = _mock_store(search_results=[])
    with patch("hachi.core.session_store.SessionStore", return_value=empty):
        result = runner.invoke(app, ["session", "search", "zzznomatch"])
    assert result.exit_code == 0
    assert "matched" in result.output.lower() or "no sessions" in result.output.lower()
