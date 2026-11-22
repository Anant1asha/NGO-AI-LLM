"""G3-T3 / REL-01 / HIGH-003 — per-session chat serialization in _InProcessGatewayRuntime.

Two assertions:
1. Same-session: concurrent chat() calls are serialized — the second starts only
   after the first finishes (no interleaving of entry/exit timestamps).
2. Different-sessions: chat() calls on separate sessions CAN overlap — their
   execution interleaves, proving no global lock was introduced.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

# We import the class under test directly; no real LLM / ChromaDB involved.
from hachi.cli.main import _InProcessGatewayRuntime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SLEEP = 0.05  # seconds each fake chat() "works" — short but enough to interleave


@dataclass
class _CallRecord:
    """Thread-safe log of (entry_time, exit_time) pairs per session."""

    entries: list[float] = field(default_factory=list)
    exits: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, session_id: str) -> None:  # noqa: ARG002 — kept for readability
        t_enter = time.monotonic()
        time.sleep(SLEEP)
        t_exit = time.monotonic()
        with self.lock:
            self.entries.append(t_enter)
            self.exits.append(t_exit)


def _make_fake_agent(recorder: _CallRecord, session_id: str) -> MagicMock:
    """Return a mock AgentSession whose .chat() records entry/exit timing."""
    agent = MagicMock()
    agent.chat.side_effect = lambda _prompt: recorder.record(session_id) or "ok"
    agent.shutdown.return_value = None
    return agent


def _register(runtime: _InProcessGatewayRuntime, session_id: str, agent: Any) -> None:
    """Inject a fake agent into the runtime without booting a real one."""
    with runtime._agents_lock:
        runtime._agents[session_id] = agent
        if session_id not in runtime._chat_locks:
            runtime._chat_locks[session_id] = threading.Lock()


# ---------------------------------------------------------------------------
# Test 1 — same session: calls must NOT overlap
# ---------------------------------------------------------------------------


class TestSameSessionSerialized:
    def test_two_concurrent_chats_do_not_overlap(self) -> None:
        """Two threads calling chat() on the same session must be serialized.

        If serialized, the earlier call's exit_time < later call's entry_time.
        If they overlapped, both entry_times would be within SLEEP of each other
        and at least one exit_time would precede the other's entry_time.
        """
        runtime = _InProcessGatewayRuntime()
        recorder = _CallRecord()
        session_id = "session-A"
        _register(runtime, session_id, _make_fake_agent(recorder, session_id))

        barrier = threading.Barrier(2)

        def _chat() -> None:
            barrier.wait()  # start both threads simultaneously
            runtime.chat(session_id, "hello")

        t1 = threading.Thread(target=_chat)
        t2 = threading.Thread(target=_chat)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert len(recorder.entries) == 2, "Expected exactly two recorded calls"
        assert len(recorder.exits) == 2

        # Sort by entry time to compare first vs second.
        pairs = sorted(zip(recorder.entries, recorder.exits, strict=True))
        first_exit = pairs[0][1]
        second_entry = pairs[1][0]

        assert first_exit <= second_entry, (
            f"Calls overlapped: first exited at {first_exit:.4f} but second entered "
            f"at {second_entry:.4f} (overlap = {first_exit - second_entry:.4f}s)"
        )


# ---------------------------------------------------------------------------
# Test 2 — different sessions: calls MUST overlap (no global lock)
# ---------------------------------------------------------------------------


class TestDifferentSessionsConcurrent:
    def test_two_sessions_run_concurrently(self) -> None:
        """Two threads chatting on DIFFERENT sessions must be able to run in parallel.

        We measure wall-clock time: if sessions were serialized by a global lock,
        total time ≈ 2 * SLEEP.  Concurrent execution takes ≈ SLEEP.
        We allow up to 1.7 * SLEEP as the pass threshold (generous for slow CI).
        """
        runtime = _InProcessGatewayRuntime()
        recorder_a = _CallRecord()
        recorder_b = _CallRecord()

        _register(runtime, "session-A", _make_fake_agent(recorder_a, "session-A"))
        _register(runtime, "session-B", _make_fake_agent(recorder_b, "session-B"))

        barrier = threading.Barrier(2)
        results: dict[str, float] = {}

        def _chat_a() -> None:
            barrier.wait()
            t0 = time.monotonic()
            runtime.chat("session-A", "hello")
            results["a"] = time.monotonic() - t0

        def _chat_b() -> None:
            barrier.wait()
            t0 = time.monotonic()
            runtime.chat("session-B", "hello")
            results["b"] = time.monotonic() - t0

        t1 = threading.Thread(target=_chat_a)
        t2 = threading.Thread(target=_chat_b)
        t_start = time.monotonic()
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        wall_time = time.monotonic() - t_start

        # Verify both calls completed.
        assert len(recorder_a.entries) == 1
        assert len(recorder_b.entries) == 1

        # Wall-clock must be well under 2 * SLEEP — i.e., they ran concurrently.
        assert wall_time < 1.7 * SLEEP, (
            f"Sessions appear to have been serialized: wall_time={wall_time:.4f}s, "
            f"expected < {1.7 * SLEEP:.4f}s (2 * SLEEP = {2 * SLEEP:.4f}s)"
        )

    def test_interleaving_of_entry_exit_timestamps(self) -> None:
        """Verify overlap via raw timestamps: session-B enters before session-A exits."""
        runtime = _InProcessGatewayRuntime()
        # Shared recorder to capture cross-session ordering.
        global_entries: list[tuple[str, float]] = []
        global_exits: list[tuple[str, float]] = []
        lock = threading.Lock()

        def _make_agent(sid: str) -> MagicMock:
            agent = MagicMock()

            def _side(prompt: str) -> str:  # noqa: ARG001
                t_in = time.monotonic()
                time.sleep(SLEEP)
                t_out = time.monotonic()
                with lock:
                    global_entries.append((sid, t_in))
                    global_exits.append((sid, t_out))
                return "ok"

            agent.chat.side_effect = _side
            agent.shutdown.return_value = None
            return agent

        _register(runtime, "session-X", _make_agent("session-X"))
        _register(runtime, "session-Y", _make_agent("session-Y"))

        barrier = threading.Barrier(2)

        def _go(sid: str) -> None:
            barrier.wait()
            runtime.chat(sid, "hi")

        threads = [threading.Thread(target=_go, args=(s,)) for s in ("session-X", "session-Y")]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=5)

        assert len(global_entries) == 2, "Both sessions must have been called"

        by_entry = sorted(global_entries, key=lambda x: x[1])
        by_exit = {sid: t for sid, t in global_exits}

        first_sid = by_entry[0][0]
        second_sid = by_entry[1][0]
        second_entry_t = by_entry[1][1]
        first_exit_t = by_exit[first_sid]

        # For concurrent execution, the second session enters BEFORE the first exits.
        assert second_entry_t < first_exit_t, (
            f"Sessions did NOT overlap: {second_sid} entered at {second_entry_t:.4f} "
            f"but {first_sid} didn't exit until {first_exit_t:.4f}"
        )


# ---------------------------------------------------------------------------
# Test 3 — lock cleanup on close_connection
# ---------------------------------------------------------------------------


class TestLockCleanup:
    def test_close_connection_removes_chat_lock(self) -> None:
        """close_connection() must drop the per-session lock to avoid a leak."""
        runtime = _InProcessGatewayRuntime()
        agent = MagicMock()
        agent.shutdown.return_value = None
        _register(runtime, "session-Z", agent)

        assert "session-Z" in runtime._chat_locks
        runtime.close_connection("session-Z")
        assert "session-Z" not in runtime._chat_locks
        assert "session-Z" not in runtime._agents
