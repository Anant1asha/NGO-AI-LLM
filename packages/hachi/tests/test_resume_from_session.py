"""resume_from_session — direct real-replay coverage (P2-10b).

Proves the cold-start transcript-replay path in ``AgentSession.resume_from_session``
against a REAL SessionStore (temp SQLite DB) and a REAL MemoryManager.  Nothing on
the memory / store path is mocked — the tests lock in production behaviour as a
regression guard.

Construction pattern mirrors ``tests/test_interaction_log.py``:
  sess = AgentSession.__new__(AgentSession)
  sess._session_store = <real SessionStore>
  sess.memory          = <real MemoryManager>
  sess._resumed_transcript = []
"""

from __future__ import annotations

from pathlib import Path

from hachi.core.llm import Message
from hachi.core.memory import MemoryManager
from hachi.core.session_store import SessionStore
from hachi.gateway.orchestrator import AgentSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> SessionStore:
    """Return a fresh SQLite-backed SessionStore in a temp directory."""
    return SessionStore(db_path=str(tmp_path / "resume_test.db"))


def _session(store: SessionStore | None, memory: MemoryManager) -> AgentSession:
    """Minimal AgentSession wired for resume_from_session only.

    Mirrors the ``AgentSession.__new__`` pattern from test_interaction_log.py.
    Only the three attributes touched by ``resume_from_session`` are set:
    ``_session_store``, ``memory``, and ``_resumed_transcript``.
    """
    sess = AgentSession.__new__(AgentSession)
    sess._session_store = store
    sess.memory = memory
    sess._resumed_transcript = []
    return sess


def _write_transcript(
    store: SessionStore,
    session_id: str,
    rows: list[tuple[str, str]],
) -> None:
    """Write (role, content) pairs to the store and flush so reads see them."""
    for role, content in rows:
        store.log_message(session_id, role, content)
    store.flush_sync()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResumeFromSessionHappyPath:
    """Happy-path: user + assistant messages land in real MemoryManager history."""

    def test_returns_seeded_count(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(
                store,
                sid,
                [
                    ("user", "Hello Hachi"),
                    ("assistant", "Hi! How can I help?"),
                ],
            )
            mm = MemoryManager()
            sess = _session(store, mm)

            result = sess.resume_from_session(sid)

            assert result == 2
        finally:
            store.shutdown()

    def test_messages_land_in_memory_history_in_order(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(
                store,
                sid,
                [
                    ("user", "What is 2+2?"),
                    ("assistant", "It's 4."),
                ],
            )
            mm = MemoryManager()
            sess = _session(store, mm)

            sess.resume_from_session(sid)

            history = mm.history
            assert len(history) == 2

            # Oldest message first (chronological order preserved by seed_history).
            assert history[0].role == "user"
            assert history[0].content == "What is 2+2?"
            assert history[1].role == "assistant"
            assert history[1].content == "It's 4."
        finally:
            store.shutdown()

    def test_history_contains_message_objects(self, tmp_path: Path) -> None:
        """seed_history stores proper Message objects, not raw dicts."""
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(store, sid, [("user", "ping"), ("assistant", "pong")])
            mm = MemoryManager()
            sess = _session(store, mm)

            sess.resume_from_session(sid)

            for msg in mm.history:
                assert isinstance(msg, Message)
        finally:
            store.shutdown()


class TestToolAndEmptyRowsSkipped:
    """Tool and empty-content rows must be filtered out; they must never land in memory."""

    def test_tool_rows_not_seeded(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(
                store,
                sid,
                [
                    ("user", "Run a search"),
                    ("tool", '{"name":"search","result":"ok"}'),
                    ("assistant", "Done, I found something."),
                ],
            )
            mm = MemoryManager()
            sess = _session(store, mm)

            result = sess.resume_from_session(sid)

            # Only user + assistant rows counted; tool row is silently dropped.
            assert result == 2
            roles = [m.role for m in mm.history]
            assert "tool" not in roles
            assert roles == ["user", "assistant"]
        finally:
            store.shutdown()

    def test_empty_content_rows_not_seeded(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            # log_message with empty string — store accepts it; filter must drop it.
            store.log_message(sid, "user", "")
            store.log_message(sid, "assistant", "Non-empty reply")
            store.flush_sync()

            mm = MemoryManager()
            sess = _session(store, mm)

            result = sess.resume_from_session(sid)

            # Empty-content user row is skipped; only the assistant row lands.
            assert result == 1
            assert mm.history[0].role == "assistant"
            assert mm.history[0].content == "Non-empty reply"
        finally:
            store.shutdown()

    def test_mixed_rows_only_user_assistant_land(self, tmp_path: Path) -> None:
        """A realistic mix: user / tool / assistant interleaved."""
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(
                store,
                sid,
                [
                    ("user", "step 1"),
                    ("tool", "tool output"),
                    ("assistant", "step 1 done"),
                    ("user", "step 2"),
                    ("tool", "more tool output"),
                    ("assistant", "step 2 done"),
                ],
            )
            mm = MemoryManager()
            sess = _session(store, mm)

            result = sess.resume_from_session(sid)

            assert result == 4  # two user + two assistant rows
            roles = [m.role for m in mm.history]
            assert roles == ["user", "assistant", "user", "assistant"]
            contents = [m.content for m in mm.history]
            assert contents == ["step 1", "step 1 done", "step 2", "step 2 done"]
        finally:
            store.shutdown()


class TestResumedTranscriptPopulated:
    """_resumed_transcript must mirror exactly what was seeded into memory."""

    def test_resumed_transcript_matches_seeded_messages(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(
                store,
                sid,
                [
                    ("user", "First question"),
                    ("assistant", "First answer"),
                    ("user", "Follow-up"),
                    ("assistant", "Follow-up answer"),
                ],
            )
            mm = MemoryManager()
            sess = _session(store, mm)

            sess.resume_from_session(sid)

            expected = [
                ("user", "First question"),
                ("assistant", "First answer"),
                ("user", "Follow-up"),
                ("assistant", "Follow-up answer"),
            ]
            assert sess._resumed_transcript == expected
        finally:
            store.shutdown()

    def test_resumed_transcript_excludes_tool_rows(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(
                store,
                sid,
                [
                    ("user", "go"),
                    ("tool", "tool noise"),
                    ("assistant", "done"),
                ],
            )
            mm = MemoryManager()
            sess = _session(store, mm)

            sess.resume_from_session(sid)

            assert sess._resumed_transcript == [("user", "go"), ("assistant", "done")]
        finally:
            store.shutdown()

    def test_resumed_transcript_is_tuple_pairs(self, tmp_path: Path) -> None:
        """Each entry must be a (role, content) tuple, not a dict or Message."""
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(store, sid, [("user", "hi"), ("assistant", "hello")])
            mm = MemoryManager()
            sess = _session(store, mm)

            sess.resume_from_session(sid)

            for entry in sess._resumed_transcript:
                assert isinstance(entry, tuple)
                assert len(entry) == 2
                role, content = entry
                assert isinstance(role, str)
                assert isinstance(content, str)
        finally:
            store.shutdown()


class TestMaxMessagesCap:
    """max_messages is passed as limit= to get_session_messages, bounding the pull."""

    def test_max_messages_limits_seeded_count(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            # Write 10 messages; request only the 4 most recent.
            rows = [(("user" if i % 2 == 0 else "assistant"), f"msg {i}") for i in range(10)]
            _write_transcript(store, sid, rows)

            mm = MemoryManager()
            sess = _session(store, mm)

            result = sess.resume_from_session(sid, max_messages=4)

            assert result == 4
            assert len(mm.history) == 4
        finally:
            store.shutdown()

    def test_max_messages_pulls_most_recent(self, tmp_path: Path) -> None:
        """get_session_messages returns oldest-first within the cap; the cap selects
        the N most-recent rows from the DB so we should see the tail of the transcript."""
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            rows = [
                ("user", "early message"),
                ("assistant", "early reply"),
                ("user", "recent question"),
                ("assistant", "recent answer"),
            ]
            _write_transcript(store, sid, rows)

            mm = MemoryManager()
            sess = _session(store, mm)

            # Pull only the 2 most-recent messages.
            result = sess.resume_from_session(sid, max_messages=2)

            assert result == 2
            # The two most-recent messages are the last pair.
            contents = [m.content for m in mm.history]
            assert contents == ["recent question", "recent answer"]
        finally:
            store.shutdown()


class TestNoStoreBound:
    """When _session_store is None, resume_from_session must return 0 and seed nothing."""

    def test_no_store_returns_zero(self) -> None:
        mm = MemoryManager()
        sess = _session(None, mm)

        result = sess.resume_from_session("any-session-id")

        assert result == 0

    def test_no_store_seeds_nothing_to_memory(self) -> None:
        mm = MemoryManager()
        sess = _session(None, mm)

        sess.resume_from_session("any-session-id")

        assert mm.history == []

    def test_no_store_leaves_resumed_transcript_empty(self) -> None:
        mm = MemoryManager()
        sess = _session(None, mm)

        sess.resume_from_session("any-session-id")

        # _resumed_transcript is initialised to [] and must not be mutated.
        assert sess._resumed_transcript == []


class TestEmptySourceSession:
    """Resuming a session with no messages must return 0 and leave history clean."""

    def test_empty_session_returns_zero(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            # No messages written.
            mm = MemoryManager()
            sess = _session(store, mm)

            result = sess.resume_from_session(sid)

            assert result == 0
        finally:
            store.shutdown()

    def test_empty_session_leaves_history_clean(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            mm = MemoryManager()
            sess = _session(store, mm)

            sess.resume_from_session(sid)

            assert mm.history == []
            assert sess._resumed_transcript == []
        finally:
            store.shutdown()


class TestSeedHistoryNuances:
    """Cover seed_history behaviour that resume_from_session implicitly relies on."""

    def test_last_user_query_updated_after_resume(self, tmp_path: Path) -> None:
        """seed_history sets _last_user_query to the most-recent user message content."""
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(
                store,
                sid,
                [
                    ("user", "earlier question"),
                    ("assistant", "earlier answer"),
                    ("user", "most recent question"),
                    ("assistant", "most recent answer"),
                ],
            )
            mm = MemoryManager()
            sess = _session(store, mm)

            sess.resume_from_session(sid)

            # seed_history walks reversed to find the last user message.
            assert mm._last_user_query == "most recent question"
        finally:
            store.shutdown()

    def test_seed_history_appends_not_prepends(self, tmp_path: Path) -> None:
        """seed_history uses extend(), so existing history comes BEFORE resumed messages."""
        store = _store(tmp_path)
        try:
            sid = store.start_session(model="test")
            _write_transcript(store, sid, [("user", "resumed msg"), ("assistant", "resumed reply")])

            mm = MemoryManager()
            # Pre-existing message (e.g. a system seed already added).
            existing_msg = Message(role="user", content="pre-existing")
            mm._history.append(existing_msg)

            sess = _session(store, mm)
            sess.resume_from_session(sid)

            # The pre-existing message is first; resumed messages follow.
            assert mm.history[0].content == "pre-existing"
            assert mm.history[1].content == "resumed msg"
            assert mm.history[2].content == "resumed reply"
        finally:
            store.shutdown()
