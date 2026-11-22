"""Concurrent-chat hammer test for AgentSession (P1-01).

Two threads hit the same session simultaneously. Without the per-session
_chat_lock, history becomes corrupted: alternating user/assistant turns and
tool-pair structure get interleaved. With the lock, turns are serialized —
history is always intact after both finish.

This test must be written FIRST (before the lock) so it acts as a regression
guard. After P1-01 it must pass green.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from hachi.core.loop import ExecutionLoop
from hachi.core.memory import MemoryManager
from hachi.gateway.orchestrator import AgentSession


def _make_session() -> AgentSession:
    """Return a minimal AgentSession backed by a fake synchronous LLM."""
    from hachi.core.llm import LLMResponse

    def _stream_once(**_kwargs):
        response = LLMResponse(
            content="reply",
            tool_calls=[],
            stop_reason="end_turn",
            usage={},
        )
        if False:
            yield ""
        return response

    memory = MemoryManager(max_active_messages=100)

    registry = MagicMock()
    registry.get_schemas.return_value = []

    llm_client = MagicMock()
    llm_client.generate.return_value = LLMResponse(
        content="reply",
        tool_calls=[],
        stop_reason="end_turn",
        usage={},
    )
    llm_client.generate_stream.side_effect = _stream_once

    loop = ExecutionLoop(
        llm_client=llm_client,
        registry=registry,
        memory=memory,
        base_system_prompt="system",
    )

    skill_engine = MagicMock()
    skill_engine.search.return_value = []
    skill_engine.record_use = MagicMock()

    integrations = MagicMock()
    mcp_manager = MagicMock()
    mcp_manager.get_tools.return_value = []
    permission_gate = MagicMock()

    session = AgentSession(
        loop=loop,
        skill_engine=skill_engine,
        memory=memory,
        integrations=integrations,
        mcp_manager=mcp_manager,
        permission_gate=permission_gate,
        model_name="test-model",
    )
    return session


def test_concurrent_chat_serializes_turns() -> None:
    """Two concurrent chat() calls must not corrupt the history."""
    session = _make_session()

    results: list[str] = []
    errors: list[Exception] = []

    def _call(msg: str) -> None:
        try:
            r = session.chat(msg)
            results.append(r)
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=_call, args=("message A",))
    t2 = threading.Thread(target=_call, args=("message B",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"Unexpected errors: {errors}"
    assert len(results) == 2, "Both calls must return a result"

    # History must be well-formed: each user message must be immediately
    # followed by an assistant message (no interleaving).
    history = session.loop.memory.history
    for i, msg in enumerate(history):
        if msg.role == "user" and isinstance(msg.content, str):
            if i + 1 < len(history):
                assert history[i + 1].role == "assistant", (
                    f"user turn at index {i} not followed by assistant — "
                    "history corrupted by concurrent access"
                )


def test_session_busy_event_emitted_on_contention() -> None:
    """session.busy event is emitted when a second caller has to queue."""
    from hachi.core.runtime_events import SESSION_BUSY

    session = _make_session()
    events: list[tuple[str, dict]] = []
    session._event_emitter = lambda name, payload: events.append((name, payload))

    # Simulate contention: hold the lock manually, then call chat() from a thread
    barrier = threading.Event()
    released = threading.Event()

    def _hold_lock() -> None:
        session._chat_lock.acquire()
        barrier.set()
        released.wait(timeout=5)
        session._chat_lock.release()

    holder = threading.Thread(target=_hold_lock)
    holder.start()
    barrier.wait(timeout=5)  # wait until the lock is held

    # Now call chat() from a second thread — it should emit SESSION_BUSY
    result_holder: list[str] = []

    def _queued_call() -> None:
        result_holder.append(session.chat("queued message"))

    waiter = threading.Thread(target=_queued_call)
    waiter.start()

    # Give the waiter a moment to hit the lock and emit the event
    import time
    time.sleep(0.05)

    # Release the lock so the waiter can proceed
    released.set()
    holder.join(timeout=5)
    waiter.join(timeout=10)

    busy_events = [name for name, _ in events if name == SESSION_BUSY]
    assert busy_events, "SESSION_BUSY event must be emitted when a turn is queued"
