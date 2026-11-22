"""interaction_log — per-turn eval/audit ground truth (AUDIT P0-2).

Covers the durable SessionStore layer: write one row per turn, read it back (with JSON
fields decoded), per-session scoping, newest-first ordering + limit, and the rating write
side that a future /review surface uses.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from hachi.core.session_store import SessionStore
from hachi.gateway.orchestrator import AgentSession


def _store(tmp_path: Path) -> SessionStore:
    return SessionStore(db_path=str(tmp_path / "s.db"))


def test_log_interaction_round_trips_all_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    row_id = store.log_interaction(
        session_id="sess",
        turn_id="t1",
        user_input="what's the weather?",
        agent_output="It's sunny.",
        tool_calls=["get_weather"],
        memory_hits=["user lives in Berlin"],
        model_used="gpt-4o-mini",
        token_cost=0.0012,
        tokens=345,
    )
    assert row_id
    rows = store.get_interactions("sess")
    assert len(rows) == 1
    rec = rows[0]
    assert rec["id"] == row_id
    assert rec["turn_id"] == "t1"
    assert rec["user_input"] == "what's the weather?"
    assert rec["agent_output"] == "It's sunny."
    assert rec["tool_calls"] == ["get_weather"]  # decoded from JSON
    assert rec["memory_hits"] == ["user lives in Berlin"]
    assert rec["model_used"] == "gpt-4o-mini"
    assert rec["token_cost"] == 0.0012
    assert rec["tokens"] == 345
    assert rec["rating"] is None  # unrated until /review
    assert rec["notes"] is None


def test_empty_tool_calls_and_memory_hits_decode_to_lists(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.log_interaction(session_id="sess", turn_id="t", user_input="hi", agent_output="hello")
    rec = store.get_interactions("sess")[0]
    assert rec["tool_calls"] == []
    assert rec["memory_hits"] == []
    assert rec["model_used"] is None


def test_get_interactions_is_scoped_per_session(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.log_interaction(session_id="a", turn_id="t", user_input="x", agent_output="y")
    store.log_interaction(session_id="b", turn_id="t", user_input="x", agent_output="y")
    assert len(store.get_interactions("a")) == 1
    assert len(store.get_interactions("b")) == 1
    assert len(store.get_interactions()) == 2  # all sessions


def test_get_interactions_newest_first_and_respects_limit(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for i in range(5):
        store.log_interaction(
            session_id="s", turn_id=f"t{i}", user_input=f"q{i}", agent_output=f"a{i}"
        )
    rows = store.get_interactions("s", limit=3)
    assert len(rows) == 3
    # Newest first — the last-written turn id appears first.
    assert rows[0]["turn_id"] == "t4"


def test_set_interaction_rating_updates_row(tmp_path: Path) -> None:
    store = _store(tmp_path)
    row_id = store.log_interaction(session_id="s", turn_id="t", user_input="q", agent_output="a")
    assert store.set_interaction_rating(row_id, "up", notes="great answer") is True
    rec = store.get_interactions("s")[0]
    assert rec["rating"] == "up"
    assert rec["notes"] == "great answer"


def test_set_rating_preserves_notes_when_not_supplied(tmp_path: Path) -> None:
    store = _store(tmp_path)
    row_id = store.log_interaction(session_id="s", turn_id="t", user_input="q", agent_output="a")
    store.set_interaction_rating(row_id, "down", notes="wrong city")
    store.set_interaction_rating(row_id, "up")  # no notes → keep prior
    rec = store.get_interactions("s")[0]
    assert rec["rating"] == "up"
    assert rec["notes"] == "wrong city"


def test_set_rating_on_unknown_id_returns_false(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.set_interaction_rating("nope", "up") is False


def test_interaction_log_survives_restart(tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")
    SessionStore(db_path=db).log_interaction(
        session_id="s", turn_id="t", user_input="q", agent_output="a", tool_calls=["x"]
    )
    rows = SessionStore(db_path=db).get_interactions("s")
    assert len(rows) == 1 and rows[0]["tool_calls"] == ["x"]


# ---------------------------------------------------------------------------
# Orchestrator write site (_write_interaction_log) — the live-turn wiring
# ---------------------------------------------------------------------------


def _session_with_store(store: SessionStore, tool_calls: list[str]) -> AgentSession:
    """A minimally-constructed AgentSession wired for _write_interaction_log only."""
    sess = AgentSession.__new__(AgentSession)
    sess._session_store = store
    sess._session_id = "sess-1"
    sess.model_name = "gpt-4o-mini"
    sess.loop = SimpleNamespace(last_tool_calls=tool_calls)
    return sess


def test_write_interaction_log_maps_turn_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    sess = _session_with_store(store, ["get_weather", "send_slack_message"])
    sess._write_interaction_log(
        turn_id="t1",
        user_input="weather + notify",
        response="done",
        recalled=[{"content": "user in Berlin"}, {"content": "prefers metric"}],
        turn_cost_usd=0.0021,
        turn_tokens=512,
    )
    rows = store.get_interactions("sess-1")
    assert len(rows) == 1
    r = rows[0]
    assert r["turn_id"] == "t1"
    assert r["user_input"] == "weather + notify"
    assert r["agent_output"] == "done"
    assert r["tool_calls"] == ["get_weather", "send_slack_message"]
    assert r["memory_hits"] == ["user in Berlin", "prefers metric"]
    assert r["model_used"] == "gpt-4o-mini"
    assert r["token_cost"] == 0.0021
    assert r["tokens"] == 512


def test_write_interaction_log_is_noop_without_store(tmp_path: Path) -> None:
    sess = AgentSession.__new__(AgentSession)
    sess._session_store = None
    sess._session_id = None
    sess.model_name = "m"
    sess.loop = SimpleNamespace(last_tool_calls=[])
    # Must not raise when there is nowhere to write.
    sess._write_interaction_log(
        turn_id="t", user_input="x", response="y", recalled=[], turn_cost_usd=0.0, turn_tokens=0
    )


def test_write_interaction_log_swallows_store_errors(tmp_path: Path) -> None:
    class _BoomStore:
        def log_interaction(self, **kwargs: object) -> str:
            raise RuntimeError("db down")

    sess = AgentSession.__new__(AgentSession)
    sess._session_store = _BoomStore()
    sess._session_id = "s"
    sess.model_name = "m"
    sess.loop = SimpleNamespace(last_tool_calls=[])
    # Best-effort: a store failure must never propagate out of a turn.
    sess._write_interaction_log(
        turn_id="t", user_input="x", response="y", recalled=[], turn_cost_usd=0.0, turn_tokens=0
    )
