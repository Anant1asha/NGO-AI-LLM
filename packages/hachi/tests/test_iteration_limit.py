"""Tests for graceful iteration-limit exit (P1-04).

The loop must return a partial-summary string (not raise AgentException) when
max_iterations is reached, and must emit a SESSION_ITERATION_LIMIT event.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hachi.core.llm import LLMResponse, ToolCall
from hachi.core.loop import ExecutionLoop
from hachi.core.memory import MemoryManager
from hachi.core.runtime_events import SESSION_ITERATION_LIMIT


def _make_loop(max_iterations: int = 1) -> tuple[ExecutionLoop, list]:
    """Return a minimal ExecutionLoop that always calls tools (never finishes),
    forcing it to exhaust max_iterations. Also returns the events list."""
    events: list[tuple[str, dict]] = []

    memory = MemoryManager(max_active_messages=50)

    registry = MagicMock()
    registry.get_schemas.return_value = []
    registry.execute.return_value = "tool result"

    llm_client = MagicMock()

    loop = ExecutionLoop(
        llm_client=llm_client,
        registry=registry,
        memory=memory,
        base_system_prompt="system",
        on_event=lambda name, payload=None: events.append((name, payload or {})),
    )

    # Make _stream_generate return a tool_use response so the loop keeps iterating.
    # run() now uses streaming generation and no longer calls _generate_with_retry.
    fake_tool_call = ToolCall(id="tc1", name="dummy_tool", input={})
    fake_response = LLMResponse(
        content="partial work done",
        tool_calls=[fake_tool_call],
        stop_reason="tool_use",
        usage={},
    )
    loop._stream_generate = MagicMock(return_value=fake_response)

    # Prime the memory with a user message
    from hachi.core.llm import Message
    memory.add_message(Message(role="user", content="do something long"))

    return loop, events


def test_iteration_limit_returns_string_not_exception() -> None:
    """Loop must return an [INCOMPLETE] string, never raise, when limit is hit."""
    loop, _ = _make_loop(max_iterations=1)
    result = loop.run(max_iterations=1)
    assert isinstance(result, str), "run() must return str, never raise"
    assert "[INCOMPLETE]" in result


def test_iteration_limit_emits_event() -> None:
    """SESSION_ITERATION_LIMIT event must be emitted when the limit is hit."""
    loop, events = _make_loop(max_iterations=1)
    loop.run(max_iterations=1)

    event_names = [name for name, _ in events]
    assert SESSION_ITERATION_LIMIT in event_names

    limit_payload = next(p for n, p in events if n == SESSION_ITERATION_LIMIT)
    assert limit_payload["iterations"] == 1
    assert limit_payload["status"] == "incomplete"


def test_iteration_limit_calls_complete_task() -> None:
    """memory.complete_task() must be called so the turn is properly closed."""
    loop, _ = _make_loop(max_iterations=1)
    # Patch complete_task to observe it being called
    with patch.object(loop.memory, "complete_task") as mock_complete:
        loop.run(max_iterations=1)

    mock_complete.assert_called_once()
    _task_arg, summary_arg = mock_complete.call_args[0]
    assert "Partial" in summary_arg or "iteration" in summary_arg.lower()


def test_normal_completion_unaffected() -> None:
    """A turn that finishes before the limit must still return normally."""
    memory = MemoryManager(max_active_messages=50)
    registry = MagicMock()
    registry.get_schemas.return_value = []

    llm_client = MagicMock()
    loop = ExecutionLoop(
        llm_client=llm_client,
        registry=registry,
        memory=memory,
        base_system_prompt="system",
    )

    # LLM returns text-only (no tool calls) → loop exits cleanly on first iteration
    loop._stream_generate = MagicMock(
        return_value=LLMResponse(
            content="Done!",
            tool_calls=[],
            stop_reason="end_turn",
            usage={},
        )
    )

    from hachi.core.llm import Message
    memory.add_message(Message(role="user", content="hello"))

    result = loop.run(max_iterations=5)
    assert result == "Done!"
    assert "[INCOMPLETE]" not in result
