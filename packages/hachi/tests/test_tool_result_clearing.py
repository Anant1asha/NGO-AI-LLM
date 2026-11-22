"""Tests for lossless tool-result clearing (MemoryManager.clear_stale_tool_results)
and its threshold-gated invocation from the execution loop.

Clearing must: shrink only large tool_result *contents* in older messages, keep
tool_use/tool_result pairing intact, be idempotent, and never touch recent turns,
small results, or non-tool_result content.
"""

from __future__ import annotations

import hachi.core.memory as memory_mod
from hachi.core.llm import LLMResponse, Message
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.memory import _CLEARED_TOOL_RESULT, MemoryManager


def _tool_result_msg(tool_use_id: str, content, is_error: bool = False) -> Message:
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return Message(role="user", content=[block])


def _mgr_with(history: list[Message]) -> MemoryManager:
    mgr = MemoryManager(max_active_messages=100)
    mgr._history = list(history)
    return mgr


# --------------------------------------------------------------------------- #
# Method behavior
# --------------------------------------------------------------------------- #
def test_clears_large_old_tool_result() -> None:
    big = "x" * 2000
    history = [_tool_result_msg("t1", big)] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)
    cleared = mgr.clear_stale_tool_results(keep_recent_messages=6)
    assert cleared == 1
    assert mgr.history[0].content[0]["content"] == _CLEARED_TOOL_RESULT
    # pairing preserved
    assert mgr.history[0].content[0]["tool_use_id"] == "t1"


def test_preserves_is_error_flag_when_clearing() -> None:
    big = "boom " * 400
    history = [_tool_result_msg("t1", big, is_error=True)] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)
    mgr.clear_stale_tool_results(keep_recent_messages=6)
    block = mgr.history[0].content[0]
    assert block["content"] == _CLEARED_TOOL_RESULT
    assert block.get("is_error") is True


def test_keeps_recent_messages_untouched() -> None:
    big = "x" * 2000
    # The big tool_result is within the most-recent-6 window → must NOT be cleared.
    history = [Message(role="user", content="q")] * 3 + [_tool_result_msg("t1", big)]
    mgr = _mgr_with(history)
    cleared = mgr.clear_stale_tool_results(keep_recent_messages=6)
    assert cleared == 0
    assert mgr.history[-1].content[0]["content"] == big


def test_leaves_small_results_alone() -> None:
    small = "ok"
    history = [_tool_result_msg("t1", small)] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)
    assert mgr.clear_stale_tool_results(keep_recent_messages=6, min_chars=600) == 0
    assert mgr.history[0].content[0]["content"] == small


def test_ignores_non_tool_result_content() -> None:
    big_text = "x" * 2000
    history = [
        Message(role="assistant", content=[{"type": "text", "text": big_text}]),
        Message(
            role="assistant", content=[{"type": "tool_use", "id": "u1", "name": "f", "input": {}}]
        ),
        Message(role="user", content=big_text),  # plain string, not a tool result
    ] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)
    assert mgr.clear_stale_tool_results(keep_recent_messages=6) == 0
    assert mgr.history[0].content[0]["text"] == big_text
    assert mgr.history[2].content == big_text


def test_idempotent() -> None:
    big = "x" * 2000
    history = [_tool_result_msg("t1", big)] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)
    assert mgr.clear_stale_tool_results(keep_recent_messages=6) == 1
    assert mgr.clear_stale_tool_results(keep_recent_messages=6) == 0  # nothing left to clear


def test_clears_large_image_tool_result() -> None:
    # A multimodal (image) tool_result has list content; its stringified size is huge.
    img_block = {"type": "image", "source": {"type": "base64", "data": "Q" * 5000}}
    history = [_tool_result_msg("t1", [img_block])] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)
    assert mgr.clear_stale_tool_results(keep_recent_messages=6) == 1
    assert mgr.history[0].content[0]["content"] == _CLEARED_TOOL_RESULT


def test_returns_zero_for_short_history() -> None:
    mgr = _mgr_with([Message(role="user", content="hi")])
    assert mgr.clear_stale_tool_results(keep_recent_messages=6) == 0


# --------------------------------------------------------------------------- #
# Loop integration (threshold-gated)
# --------------------------------------------------------------------------- #
class _ScriptedLLM:
    model = "fake-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def generate(self, **_kwargs) -> LLMResponse:
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp

    def generate_stream(self, **kwargs):
        response = self.generate(**kwargs)
        return response
        yield  # makes this a generator function


def test_loop_clears_when_over_threshold(monkeypatch) -> None:
    monkeypatch.setattr(memory_mod, "_TOOL_RESULT_CLEAR_TOKENS", 100)  # tiny → triggers
    big = "x" * 2000
    history = [_tool_result_msg("t1", big)] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)

    events: list[tuple[str, dict]] = []
    loop = ExecutionLoop(
        _ScriptedLLM([LLMResponse(content="final answer", tool_calls=[])]),
        ToolRegistry(),
        mgr,
        base_system_prompt="x",
        on_event=lambda ev, data: events.append((ev, data)),
    )
    out = loop.run(max_iterations=2)

    assert "final answer" in out
    assert mgr.history[0].content[0]["content"] == _CLEARED_TOOL_RESULT
    assert any(ev == "tool_results_cleared" for ev, _ in events)


def test_loop_does_not_clear_when_under_threshold(monkeypatch) -> None:
    monkeypatch.setattr(memory_mod, "_TOOL_RESULT_CLEAR_TOKENS", 1_000_000)  # never triggers
    big = "x" * 2000
    history = [_tool_result_msg("t1", big)] + [Message(role="user", content="q")] * 7
    mgr = _mgr_with(history)

    loop = ExecutionLoop(
        _ScriptedLLM([LLMResponse(content="done", tool_calls=[])]),
        ToolRegistry(),
        mgr,
        base_system_prompt="x",
    )
    loop.run(max_iterations=2)
    assert mgr.history[0].content[0]["content"] == big  # untouched
