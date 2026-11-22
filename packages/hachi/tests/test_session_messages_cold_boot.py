"""Regression test for BB-35: session_messages() returns [] on cold boot.

Root cause:
  _InProcessGatewayRuntime.session_messages() returns [] when _agents is empty.
  recent_sessions() has the BB-13 SessionStore fallback; session_messages() did not.
  GET /sessions/{id}/events synthesizes events via session_messages(), so on a
  fresh server start ALL past-session histories are empty and chat messages never
  appear when the user switches to a previous session.

Fix:
  Apply the same BB-13 pattern to session_messages(): when _agents is empty,
  read from SessionStore directly (same as recent_sessions).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from hachi.cli.main import _InProcessGatewayRuntime
from hachi.core.session_store import SessionStore


def _make_store(tmp_path: Path) -> SessionStore:
    return SessionStore(db_path=tmp_path / "sessions.db")


def _seed_session(store: SessionStore) -> str:
    """Write a two-message session and return its session id."""
    sid = store.start_session(model="test-model")
    store.log_message(sid, role="user", content="hello from past session")
    store.log_message(sid, role="assistant", content="hi there from past assistant")
    store.flush_sync()
    return sid


class TestSessionMessagesColdBoot:
    """session_messages() must return persisted messages even when no agent is booted."""

    def test_session_messages_returns_transcript_on_cold_boot(self, tmp_path: Path) -> None:
        """BB-35: session_messages must fall back to SessionStore when _agents is empty.

        FAILS before the fix (returns []).
        PASSES after the fix (returns the two persisted messages).
        """
        store = _make_store(tmp_path)
        sid = _seed_session(store)

        runtime = _InProcessGatewayRuntime()
        assert not runtime._agents, "precondition: no live agents (cold boot)"

        # Route the fallback SessionStore to our temp DB.
        mock_paths = MagicMock()
        mock_paths.sessions_db = tmp_path / "sessions.db"

        with patch("hachi.cli.main.get_hachi_paths", return_value=mock_paths):
            result = runtime.session_messages(sid)

        assert len(result) == 2, (
            f"BB-35: expected 2 messages on cold boot, got {len(result)}: {result!r}. "
            "session_messages() must fall back to SessionStore when _agents is empty."
        )
        assert result[0]["content"] == "hello from past session"
        assert result[1]["content"] == "hi there from past assistant"

    def test_session_messages_unknown_session_returns_empty(self, tmp_path: Path) -> None:
        """Unknown session id returns [] (not an error) both before and after the fix."""
        _make_store(tmp_path)  # create the DB but write nothing

        runtime = _InProcessGatewayRuntime()
        assert not runtime._agents, "precondition: no live agents"

        mock_paths = MagicMock()
        mock_paths.sessions_db = tmp_path / "sessions.db"

        with patch("hachi.cli.main.get_hachi_paths", return_value=mock_paths):
            result = runtime.session_messages("nonexistent-session-id")

        assert result == [], "unknown session must return [] not raise"
