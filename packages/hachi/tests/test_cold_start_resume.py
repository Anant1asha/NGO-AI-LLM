"""Tests for P2-10 — cold-start resume.

Verifies that resume_run() rehydrates a session from the durable SQLite
transcript when the live-session map is empty (simulating a gateway restart),
instead of raising HonestResumeError.

Anti-fake-masking guarantee
---------------------------
The scripted LLM client is fake, but the session rehydration path is REAL:
* A real SessionStore records transcript rows.
* resume_run → _do_resume → _InProcessGatewayRuntime.rehydrate_session →
  _boot_session_agent → boot_agent(resume_session_id=<sid>) is called.
* The test's fake boot_agent captures the resume_session_id argument and
  builds a _ScriptedAgent that loads the prior messages from the REAL store.
* The key assertion checks that the rehydrated agent's
  ``seen_resume_session_id`` equals the original session's id — proving that
  boot_agent was called with the right argument, not with a faked session.
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hachi.core.runtime.resume import HonestResumeError, resume_run
from hachi.core.runtime.state import RunState, RunStatus, WaitCondition, WaitKind
from hachi.core.runtime.store import RunStateStore  # noqa: F401 (used in monkeypatch target)
from hachi.core.runtime_events import now_iso
from hachi.core.session_store import SessionStore

# ---------------------------------------------------------------------------
# Scripted agent stub
# ---------------------------------------------------------------------------


class _ScriptedAgent:
    """Minimal AgentSession stand-in that records the resume_session_id it was
    booted with and can report replayed messages from a real SessionStore.

    session_store is passed in from the test so _ScriptedAgent can prove it
    received the right resume_session_id (i.e. that the transcript was looked
    up in the real store, not faked).
    """

    def __init__(
        self,
        session_store: SessionStore,
        resume_session_id: str | None,
    ) -> None:
        self._store = session_store
        #: The resume_session_id argument passed to boot_agent — our proof that
        #: rehydration called boot_agent with the right argument.
        self.seen_resume_session_id: str | None = resume_session_id
        # Eagerly load the transcript so tests can assert on it.
        self.replayed_messages: list[dict[str, Any]] = (
            self._store.get_session_messages(resume_session_id, limit=200)
            if resume_session_id
            else []
        )
        self._chat_lock = threading.Lock()
        self.chat_calls: list[str] = []

    # --- AgentSession interface surface needed by _InProcessGatewayRuntime ---

    def chat(self, prompt: str) -> str:
        with self._chat_lock:
            self.chat_calls.append(prompt)
            return f"scripted-reply:{prompt}"

    def shutdown(self) -> None:
        pass

    def snapshot_events_since(self, after: int, limit: int = 100) -> list[Any]:
        return []

    def snapshot_session_state(self) -> Any:
        return SimpleNamespace(
            session_id="scripted",
            active_skill=None,
            last_user_query="",
            model_name="scripted",
            boot_ready=True,
            pending_job_count=0,
            total_tokens=0,
            estimated_cost_usd=0.0,
        )

    def snapshot_runtime_events(self, limit: int = 100) -> list[Any]:
        return []

    def snapshot_mcp_inventory(self) -> Any:
        return SimpleNamespace(server_count=0, total_tool_count=0, servers=[])

    def snapshot_active_jobs(self) -> list[Any]:
        return []

    def snapshot_failed_jobs(self, limit: int = 10) -> list[Any]:
        return []

    def query_recent_sessions(self, limit: int = 10) -> tuple[dict[str, Any], ...]:
        return tuple(self._store.get_recent_sessions(limit=limit))

    def query_session_messages(
        self, session_id: str, limit: int = 500
    ) -> tuple[dict[str, Any], ...]:
        return tuple(self._store.get_session_messages(session_id, limit=limit))

    def delete_session(self, session_id: str) -> bool:
        return bool(self._store.delete_session(session_id))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> SessionStore:
    """Create a real SessionStore backed by a temp DB."""
    return SessionStore(db_path=tmp_path / "sessions.db")


def _make_run_store(tmp_path: Path) -> RunStateStore:
    """Create a real RunStateStore backed by a temp DB."""
    return RunStateStore(db_path=tmp_path / "runs.db")


def _write_transcript(store: SessionStore, session_id: str) -> list[dict[str, Any]]:
    """Write two user/assistant messages to store and return them."""
    store.log_message(session_id, role="user", content="hello from past session")
    store.log_message(session_id, role="assistant", content="I am the assistant")
    store.flush_sync()
    return store.get_session_messages(session_id)


def _waiting_run(run_id: str, session_id: str, run_store: RunStateStore) -> RunState:
    """Persist a WAITING RunState and return it."""
    run = RunState(
        run_id=run_id,
        session_id=session_id,
        status=RunStatus.WAITING,
        wait=WaitCondition(kind=WaitKind.USER, key="approval-1", created_at=now_iso()),
        resume_cursor=1,
        payload={},
        updated_at=now_iso(),
    )
    run_store.upsert(run)
    return run


# ---------------------------------------------------------------------------
# Test 1 — cold start: rehydrates from transcript, resumed turn runs
# ---------------------------------------------------------------------------


class TestColdStartResume:
    """A WAITING run woken AFTER a gateway restart must rehydrate from transcript."""

    def test_cold_start_rehydrates_and_resumes_turn(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cold path: no live session → rehydrate_session is called → turn runs.

        KEY ASSERTION: agent.seen_resume_session_id == original session_id
        proves that boot_agent was called with resume_session_id=<the WAITING
        run's session_id>, meaning the REAL transcript-replay machinery was
        invoked (not a fake session).
        """
        session_store = _make_store(tmp_path)
        run_store = _make_run_store(tmp_path)

        # Write a real transcript for a prior session.
        prior_sid = session_store.start_session(model="scripted")
        prior_messages = _write_transcript(session_store, prior_sid)
        assert len(prior_messages) == 2, "precondition: transcript has 2 messages"

        # Create a WAITING run referencing that session.
        run = _waiting_run("run-cold-001", prior_sid, run_store)

        # Build a runtime whose boot_agent captures resume_session_id.
        from hachi.cli.main import _InProcessGatewayRuntime

        runtime = _InProcessGatewayRuntime()
        booted_agents: list[_ScriptedAgent] = []

        def _fake_boot_agent(
            on_event: Any = None,
            on_permission_request: Any = None,
            resume_session_id: str | None = None,
        ) -> _ScriptedAgent:
            agent = _ScriptedAgent(session_store, resume_session_id)
            booted_agents.append(agent)
            return agent  # type: ignore[return-value]

        monkeypatch.setattr("hachi.cli.main.boot_agent", _fake_boot_agent)

        # Patch RunStateStore so resume_run uses our temp-dir store.
        monkeypatch.setattr("hachi.core.runtime.store.RunStateStore", lambda: run_store)

        # Publish the runtime so _do_resume can find it.
        # _do_resume reads via getattr(hachi.cli.main, "_ACTIVE_RUNTIME") at call time,
        # so monkeypatching the module attribute is the correct approach.
        import hachi.cli.main as main_mod

        monkeypatch.setattr(main_mod, "_ACTIVE_RUNTIME", runtime)

        # The live-session map is EMPTY — simulates a cold start after restart.
        assert not runtime._agents, "precondition: no live sessions"

        # === THE CALL ===
        reply = resume_run(run.run_id, {"decision": "approved"})

        # 1. A boot_agent was called (rehydration happened).
        assert len(booted_agents) == 1, "boot_agent must have been called for rehydration"
        agent = booted_agents[0]

        # 2. CORE ANTI-FAKE ASSERTION: boot_agent received the right resume_session_id.
        #    If this is the real id, the SQLite transcript was looked up in the REAL store.
        assert agent.seen_resume_session_id == prior_sid, (
            f"boot_agent must be called with resume_session_id={prior_sid!r}, "
            f"got {agent.seen_resume_session_id!r} — rehydration did NOT use the real transcript"
        )

        # 3. The rehydrated agent actually loaded the prior messages from the real store.
        assert len(agent.replayed_messages) == 2
        assert agent.replayed_messages[0]["content"] == "hello from past session"
        assert agent.replayed_messages[1]["content"] == "I am the assistant"

        # 4. The resumed turn ran (inject_text was sent to chat()).
        assert agent.chat_calls, "chat() must have been called with the inject_text"
        assert "[RESUME]" in agent.chat_calls[0]
        assert "approved" in agent.chat_calls[0]

        # 5. resume_run returned the scripted reply.
        assert reply.startswith("scripted-reply:")

        # 6. RunState is COMPLETED after successful resume.
        final = run_store.get(run.run_id)
        assert final is not None
        assert final.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Test 2 — live session path: no unnecessary reboot when session IS live
# ---------------------------------------------------------------------------


class TestLiveSessionPath:
    """When the session is live, rehydrate_session must NOT be called."""

    def test_live_session_used_directly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hot path: live session exists → chat() directly, no boot_agent."""
        session_store = _make_store(tmp_path)
        run_store = _make_run_store(tmp_path)

        prior_sid = session_store.start_session(model="scripted")
        run = _waiting_run("run-live-001", prior_sid, run_store)

        from hachi.cli.main import _InProcessGatewayRuntime

        runtime = _InProcessGatewayRuntime()

        # Pre-register a live scripted agent for this session.
        live_agent = _ScriptedAgent(session_store, resume_session_id=None)
        runtime._agents[prior_sid] = live_agent
        runtime._chat_locks[prior_sid] = threading.Lock()

        boot_call_count = 0

        def _fake_boot_agent(**kwargs: Any) -> _ScriptedAgent:
            nonlocal boot_call_count
            boot_call_count += 1
            return _ScriptedAgent(session_store, kwargs.get("resume_session_id"))  # type: ignore[return-value]

        monkeypatch.setattr("hachi.cli.main.boot_agent", _fake_boot_agent)
        monkeypatch.setattr("hachi.core.runtime.store.RunStateStore", lambda: run_store)
        import hachi.cli.main as main_mod

        monkeypatch.setattr(main_mod, "_ACTIVE_RUNTIME", runtime)

        reply = resume_run(run.run_id, {"decision": "approved"})

        # boot_agent was NOT called (live path skips rehydration).
        assert boot_call_count == 0, "live path must not call boot_agent"

        # The LIVE agent received the chat call.
        assert live_agent.chat_calls, "live agent must have received the inject_text"
        assert "[RESUME]" in live_agent.chat_calls[0]

        assert reply.startswith("scripted-reply:")


# ---------------------------------------------------------------------------
# Test 3 — no runtime: HonestResumeError preserved
# ---------------------------------------------------------------------------


class TestNoRuntimeHonestFail:
    """When no runtime is attached, resume_run must still raise HonestResumeError."""

    def test_raises_honest_resume_error_when_no_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Standalone CLI context: _ACTIVE_RUNTIME is None → honest fail."""
        session_store = _make_store(tmp_path)
        run_store = _make_run_store(tmp_path)

        prior_sid = session_store.start_session(model="scripted")
        run = _waiting_run("run-noruntime-001", prior_sid, run_store)

        monkeypatch.setattr("hachi.core.runtime.store.RunStateStore", lambda: run_store)

        # Ensure _ACTIVE_RUNTIME is None at the time _do_resume reads it.
        import hachi.cli.main as main_mod

        monkeypatch.setattr(main_mod, "_ACTIVE_RUNTIME", None)

        with pytest.raises(HonestResumeError, match="_ACTIVE_RUNTIME is None"):
            resume_run(run.run_id, {"decision": "approved"})

        # The run must be rolled back to WAITING (not FAILED) on HonestResumeError.
        final = run_store.get(run.run_id)
        assert final is not None
        assert final.status == RunStatus.WAITING, (
            "HonestResumeError must roll run back to WAITING, not FAILED"
        )


# ---------------------------------------------------------------------------
# Test 4 — idempotency: double-wake does not double-run
# ---------------------------------------------------------------------------


class TestIdempotency:
    """A second resume_run for an already-RUNNING/COMPLETED run is a no-op."""

    def test_double_wake_is_noop_for_completed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COMPLETED run: second resume_run returns 'no-op' without running again."""
        session_store = _make_store(tmp_path)
        run_store = _make_run_store(tmp_path)

        prior_sid = session_store.start_session(model="scripted")
        run = _waiting_run("run-idem-001", prior_sid, run_store)

        from hachi.cli.main import _InProcessGatewayRuntime

        runtime = _InProcessGatewayRuntime()
        live_agent = _ScriptedAgent(session_store, resume_session_id=None)
        runtime._agents[prior_sid] = live_agent
        runtime._chat_locks[prior_sid] = threading.Lock()

        monkeypatch.setattr("hachi.cli.main.boot_agent", lambda **kw: live_agent)
        monkeypatch.setattr("hachi.core.runtime.store.RunStateStore", lambda: run_store)
        import hachi.cli.main as main_mod

        monkeypatch.setattr(main_mod, "_ACTIVE_RUNTIME", runtime)

        # First wake — runs the turn.
        reply1 = resume_run(run.run_id, {"decision": "approved"})
        assert reply1.startswith("scripted-reply:")
        assert run_store.get(run.run_id).status == RunStatus.COMPLETED

        # Second wake — must be a no-op (run is COMPLETED, not WAITING).
        chat_count_before = len(live_agent.chat_calls)
        reply2 = resume_run(run.run_id, {"decision": "approved"})

        assert "no-op" in reply2, f"Expected 'no-op' reply, got: {reply2!r}"
        assert len(live_agent.chat_calls) == chat_count_before, (
            "chat() must not be called again on a second resume for a COMPLETED run"
        )

    def test_double_wake_is_noop_for_running(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RUNNING run: concurrent second resume_run is a no-op."""
        session_store = _make_store(tmp_path)
        run_store = _make_run_store(tmp_path)

        prior_sid = session_store.start_session(model="scripted")

        # Insert as RUNNING (already in-flight).
        run = RunState(
            run_id="run-idem-running-001",
            session_id=prior_sid,
            status=RunStatus.RUNNING,
            payload={},
            updated_at=now_iso(),
        )
        run_store.upsert(run)

        monkeypatch.setattr("hachi.core.runtime.store.RunStateStore", lambda: run_store)

        reply = resume_run(run.run_id, {"decision": "approved"})
        assert "no-op" in reply
        assert "running" in reply
