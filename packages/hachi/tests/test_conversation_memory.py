"""Tests for the ConversationMemory Protocol and its implementations.

Verifies:
- InMemoryConversationMemory satisfies the Protocol at runtime.
- MemoryManager satisfies the Protocol at runtime.
- The ExecutionLoop works correctly with InMemoryConversationMemory.
- prepare_for_turn() returns a proper IterationState.
- complete_task() captures calls correctly.
"""

from __future__ import annotations

import pytest

from hachi.core.conversation_memory import ConversationMemory, IterationState
from hachi.core.llm import LLMResponse, TokenUsage
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.memory import MemoryManager
from hachi.core.testing import InMemoryConversationMemory

# ---------------------------------------------------------------------------
# Protocol satisfaction
# ---------------------------------------------------------------------------


def test_in_memory_adaptor_satisfies_protocol() -> None:
    """InMemoryConversationMemory must be recognised as a ConversationMemory at runtime."""
    mem = InMemoryConversationMemory()
    assert isinstance(mem, ConversationMemory)


def test_memory_manager_satisfies_protocol() -> None:
    """MemoryManager must be recognised as a ConversationMemory at runtime."""
    mm = MemoryManager()
    assert isinstance(mm, ConversationMemory)


# ---------------------------------------------------------------------------
# IterationState
# ---------------------------------------------------------------------------


def test_prepare_for_turn_returns_iteration_state() -> None:
    """InMemoryConversationMemory.prepare_for_turn() returns an IterationState."""
    mem = InMemoryConversationMemory()
    state = mem.prepare_for_turn()
    assert isinstance(state, IterationState)
    assert state.compacted is False
    assert state.old_skill == ""
    assert state.tool_results_cleared == 0
    assert state.history_repaired == 0


def test_iteration_state_is_frozen() -> None:
    """IterationState is a frozen dataclass — mutation must raise."""
    state = IterationState(
        compacted=True, old_skill="my_skill", tool_results_cleared=3, history_repaired=1
    )
    with pytest.raises((AttributeError, TypeError)):
        state.compacted = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# complete_task recording
# ---------------------------------------------------------------------------


def test_complete_task_records_call() -> None:
    """complete_task() appends (user_query, result) to _complete_task_calls."""
    mem = InMemoryConversationMemory()
    assert mem._complete_task_calls == []

    mem.complete_task("What is 2+2?", "4")
    assert mem._complete_task_calls == [("What is 2+2?", "4")]

    mem.complete_task("Another query", "Another result")
    assert len(mem._complete_task_calls) == 2
    assert mem._complete_task_calls[1] == ("Another query", "Another result")


# ---------------------------------------------------------------------------
# ExecutionLoop integration
# ---------------------------------------------------------------------------


class _FinishingLLM:
    """Returns a single text response with no tool calls — loop finishes after 1 turn."""

    model = "fake-model"
    response_text = "All done!"

    def generate(self, **_kwargs) -> LLMResponse:
        return LLMResponse(content=self.response_text, tool_calls=[], usage=TokenUsage())

    def generate_stream(self, **kwargs):  # noqa: ANN201
        response = self.generate(**kwargs)
        if False:
            yield ""
        return response


def test_loop_uses_in_memory_adaptor() -> None:
    """ExecutionLoop works with InMemoryConversationMemory and calls complete_task."""
    mem = InMemoryConversationMemory()
    loop = ExecutionLoop(
        llm_client=_FinishingLLM(),
        registry=ToolRegistry(),
        memory=mem,
        base_system_prompt="test",
    )

    user_query = "Hello, agent!"
    loop.add_user_message(user_query)
    result = loop.run(max_iterations=3)

    assert result == _FinishingLLM.response_text

    # complete_task must have been called exactly once.
    # Without TurnContext, user_input_for_turn is captured via getattr(_last_user_query, "")
    # — InMemoryConversationMemory doesn't have that attribute, so it falls back to "".
    assert len(mem._complete_task_calls) == 1
    _query, result_logged = mem._complete_task_calls[0]
    assert result_logged == _FinishingLLM.response_text


def test_loop_uses_in_memory_adaptor_with_turn_context() -> None:
    """When a TurnContext is supplied, user_input comes from it — not from memory."""
    from hachi.core.turn_context import TurnContext

    mem = InMemoryConversationMemory()
    loop = ExecutionLoop(
        llm_client=_FinishingLLM(),
        registry=ToolRegistry(),
        memory=mem,
        base_system_prompt="test",
    )

    tc = TurnContext.build(
        turn_id="t1",
        session_id="s1",
        user_input="explicit query from TurnContext",
        system_prompt_base="base",
    )
    loop.add_user_message("explicit query from TurnContext")
    loop.run(max_iterations=3, turn_context=tc)

    assert len(mem._complete_task_calls) == 1
    query_logged, _ = mem._complete_task_calls[0]
    assert query_logged == "explicit query from TurnContext"


def test_loop_calls_prepare_for_turn_each_iteration() -> None:
    """prepare_for_turn() is invoked on every loop iteration via the memory seam."""

    class _CountingMemory(InMemoryConversationMemory):
        prepare_calls: int = 0

        def prepare_for_turn(self) -> IterationState:
            self.prepare_calls += 1
            return super().prepare_for_turn()

    class _TwoTurnLLM:
        """Calls a dummy tool on turn 1, returns text on turn 2."""

        model = "fake-model"
        _call = 0

        def generate(self, **_kwargs) -> LLMResponse:
            from hachi.core.llm import ToolCall

            self._call += 1
            if self._call == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="tc1", name="noop", input={})],
                    usage=TokenUsage(),
                )
            return LLMResponse(content="done", tool_calls=[], usage=TokenUsage())

        def generate_stream(self, **kwargs):  # noqa: ANN201
            response = self.generate(**kwargs)
            if False:
                yield ""
            return response

    _schema = {
        "name": "noop",
        "description": "noop",
        "input_schema": {"type": "object", "properties": {}},
    }
    registry = ToolRegistry()
    registry.register(_schema, lambda **_kw: "ok")

    mem = _CountingMemory()
    loop = ExecutionLoop(
        llm_client=_TwoTurnLLM(),
        registry=registry,
        memory=mem,
        base_system_prompt="test",
    )
    loop.add_user_message("go")
    loop.run(max_iterations=5)

    # Two LLM iterations → two prepare_for_turn calls.
    assert mem.prepare_calls == 2
