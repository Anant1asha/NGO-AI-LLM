"""Tests for `hachi session delete` and `hachi session export` CLI commands.

All tests use a patched SessionStore (injected at the source module so lazy
imports inside the command functions resolve correctly) — no real SQLite or
filesystem I/O.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FULL_SESSION_ID = "aabb1122-0000-0000-0000-000000000001"
_SESSION_ROW = {
    "id": _FULL_SESSION_ID,
    "started_at": "2026-06-07T10:00:00",
    "ended_at": "2026-06-07T10:05:00",
    "model": "claude-opus-4-5",
    "total_turns": 3,
}
_MESSAGES = [
    {
        "role": "user",
        "content": "Hello agent",
        "tool_name": None,
        "timestamp": "2026-06-07T10:00:01",
    },
    {
        "role": "assistant",
        "content": "Hello! How can I help?",
        "tool_name": None,
        "timestamp": "2026-06-07T10:00:05",
    },
    {
        "role": "tool",
        "content": "tool result here",
        "tool_name": "search_skills",
        "timestamp": "2026-06-07T10:01:00",
    },
]


def _mock_store(
    sessions: list[dict] | None = None,
    messages: list[dict] | None = None,
    delete_result: bool = True,
) -> MagicMock:
    store = MagicMock()
    store.get_recent_sessions.return_value = sessions if sessions is not None else [_SESSION_ROW]
    store.get_session_messages.return_value = messages if messages is not None else _MESSAGES
    store.delete_session.return_value = delete_result
    store.search_sessions.return_value = []
    return store


# ---------------------------------------------------------------------------
# session delete — happy path
# ---------------------------------------------------------------------------


def test_session_delete_full_id_success() -> None:
    store = _mock_store(delete_result=True)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "delete", _FULL_SESSION_ID, "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    store.delete_session.assert_called_once_with(_FULL_SESSION_ID)


def test_session_delete_prefix_success() -> None:
    store = _mock_store(delete_result=True)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "delete", "aabb1122", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    # Resolved to full ID
    store.delete_session.assert_called_once_with(_FULL_SESSION_ID)


def test_session_delete_json_success() -> None:
    store = _mock_store(delete_result=True)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "delete", _FULL_SESSION_ID, "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["session_id"] == _FULL_SESSION_ID


def test_session_delete_not_found_exits_1() -> None:
    store = _mock_store(delete_result=False)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "delete", _FULL_SESSION_ID, "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_session_delete_json_not_found_exits_1() -> None:
    store = _mock_store(delete_result=False)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "delete", _FULL_SESSION_ID, "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False


def test_session_delete_ambiguous_prefix_exits_1() -> None:
    two_sessions = [
        {**_SESSION_ROW, "id": "aabb1122-0000-0000-0000-000000000001"},
        {**_SESSION_ROW, "id": "aabb1122-0000-0000-0000-000000000002"},
    ]
    store = _mock_store(sessions=two_sessions)
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "delete", "aabb1122", "--yes"])
    assert result.exit_code == 1
    assert "Ambiguous" in result.output or "ambiguous" in result.output.lower()


def test_session_delete_no_match_exits_1() -> None:
    store = _mock_store(sessions=[])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "delete", "zzzz", "--yes"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# session export — stdout Markdown
# ---------------------------------------------------------------------------


def test_session_export_markdown_stdout() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "export", _FULL_SESSION_ID])
    assert result.exit_code == 0
    assert f"# Session {_FULL_SESSION_ID}" in result.output
    assert "## You" in result.output
    assert "Hello agent" in result.output
    assert "## Agent" in result.output
    assert "Hello! How can I help?" in result.output
    assert "### Tool: search_skills" in result.output


def test_session_export_json_stdout() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "export", _FULL_SESSION_ID, "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["session_id"] == _FULL_SESSION_ID
    assert len(payload["messages"]) == 3


def test_session_export_invalid_format_exits_1() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "export", _FULL_SESSION_ID, "--format", "xml"])
    assert result.exit_code == 1
    assert "xml" in result.output


def test_session_export_to_file(tmp_path) -> None:
    store = _mock_store()
    out = str(tmp_path / "transcript.md")
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "export", _FULL_SESSION_ID, "-o", out])
    assert result.exit_code == 0
    assert "Exported" in result.output
    content = (tmp_path / "transcript.md").read_text(encoding="utf-8")
    assert "Hello agent" in content


def test_session_export_prefix_resolves() -> None:
    store = _mock_store()
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "export", "aabb1122"])
    assert result.exit_code == 0
    assert f"# Session {_FULL_SESSION_ID}" in result.output


def test_session_export_no_messages_empty_markdown() -> None:
    store = _mock_store(messages=[])
    with patch("hachi.core.session_store.SessionStore", return_value=store):
        result = runner.invoke(app, ["session", "export", _FULL_SESSION_ID])
    assert result.exit_code == 0
    # Should produce just the header line
    assert f"# Session {_FULL_SESSION_ID}" in result.output
