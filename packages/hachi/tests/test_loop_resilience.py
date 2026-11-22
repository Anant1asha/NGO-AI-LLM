"""Regression tests for ExecutionLoop correctness fixes (audit P0/P1).

- On workflow suspend, every assistant tool_use block must get a paired
  tool_result (else the next turn's history is rejected by the Anthropic API).
- Transient LLM errors are retried with backoff; non-transient errors are not.
"""

from __future__ import annotations

import pytest

from hachi.core.cost import CostTracker
from hachi.core.llm import LLMResponse, TokenUsage, ToolCall
from hachi.core.loop import ExecutionLoop, SuspendWorkflow, ToolRegistry
from hachi.core.sub_agent import SubAgentMemory


class _SpendingLLM:
    """Always asks for a tool call (never finishes) and reports token usage."""

    model = "claude-haiku-4-5"

    def __init__(self) -> None:
        self.n = 0

    def generate(self, **_kwargs) -> LLMResponse:
        self.n += 1
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{self.n}", name="noop", input={})],
            usage=TokenUsage(input_tokens=500, output_tokens=500),
        )

    def generate_stream(self, **kwargs):  # noqa: ANN201
        response = self.generate(**kwargs)
        if False:
            yield ""
        return response


def _noop_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_tool("noop"), lambda **_kw: "ok")
    return registry


def test_loop_stops_at_token_budget() -> None:
    tracker = CostTracker()
    loop = ExecutionLoop(
        _SpendingLLM(),
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        cost_tracker=tracker,
        max_tokens=800,
    )
    loop.add_user_message("go")
    out = loop.run(max_iterations=50)
    assert "BUDGET LIMIT REACHED" in out
    assert tracker.snapshot().call_count <= 2  # stopped almost immediately, not 50x


def test_loop_stops_at_cost_budget() -> None:
    tracker = CostTracker()
    loop = ExecutionLoop(
        _SpendingLLM(),
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        cost_tracker=tracker,
        max_cost_usd=0.002,  # one 1000-token haiku turn already exceeds this
    )
    loop.add_user_message("go")
    out = loop.run(max_iterations=50)
    assert "BUDGET LIMIT REACHED" in out


def test_no_budget_does_not_stop_early() -> None:
    tracker = CostTracker()
    llm = _SpendingLLM()
    loop = ExecutionLoop(
        llm, _noop_registry(), SubAgentMemory(), base_system_prompt="x", cost_tracker=tracker
    )
    loop.add_user_message("go")
    # No cap → not stopped early; runs to iteration limit and returns INCOMPLETE (not raises).
    result = loop.run(max_iterations=4)
    assert "[INCOMPLETE]" in result
    assert llm.n == 4


_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def _tool(name: str):
    return {"name": name, "description": name, "input_schema": _EMPTY_SCHEMA}


class _ScriptedLLM:
    model = "fake-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def generate(self, **_kwargs) -> LLMResponse:
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp

    def generate_stream(self, **kwargs):  # noqa: ANN201
        response = self.generate(**kwargs)
        if False:
            yield ""
        return response


def test_suspend_pairs_every_tool_use() -> None:
    registry = ToolRegistry()
    registry.register(_tool("echo"), lambda **_kw: "ok")

    def _suspend(**_kw):
        raise SuspendWorkflow(reason="approval needed")

    registry.register(_tool("suspend_it"), _suspend)

    # suspend is the FIRST tool call → 'echo' never runs, but BOTH tool_use blocks
    # must still be answered.
    response = LLMResponse(
        content="",
        tool_calls=[
            ToolCall(id="t1", name="suspend_it", input={}),
            ToolCall(id="t2", name="echo", input={}),
        ],
    )
    memory = SubAgentMemory()
    loop = ExecutionLoop(_ScriptedLLM([response]), registry, memory, base_system_prompt="x")
    loop.add_user_message("do stuff")

    out = loop.run(max_iterations=3)
    assert "SUSPENDED" in out

    tool_result_msgs = [
        m for m in memory.history if m.role == "user" and isinstance(m.content, list)
    ]
    assert tool_result_msgs, "expected a tool_results user message"
    paired = {
        b["tool_use_id"]
        for b in tool_result_msgs[-1].content
        if isinstance(b, dict) and b.get("type") == "tool_result"
    }
    assert paired == {"t1", "t2"}  # both tool_use blocks answered → valid next turn


def test_transient_llm_error_is_retried(monkeypatch) -> None:
    monkeypatch.setattr("hachi.core.loop.time.sleep", lambda *_a, **_k: None)

    calls = {"n": 0}

    class _Flaky:
        model = "fake-model"

        def generate(self, **_kwargs) -> LLMResponse:
            calls["n"] += 1
            if calls["n"] == 1:
                err = Exception("Overloaded")
                err.status_code = 529  # type: ignore[attr-defined]
                raise err
            return LLMResponse(content="done")

        def generate_stream(self, **kwargs):  # noqa: ANN201
            response = self.generate(**kwargs)
            if False:
                yield ""
            return response

    loop = ExecutionLoop(_Flaky(), ToolRegistry(), SubAgentMemory(), base_system_prompt="x")
    loop.add_user_message("hi")
    assert loop.run(max_iterations=2) == "done"
    assert calls["n"] == 2  # retried exactly once


def test_non_transient_llm_error_is_not_retried(monkeypatch) -> None:
    monkeypatch.setattr("hachi.core.loop.time.sleep", lambda *_a, **_k: None)

    calls = {"n": 0}

    class _AuthError:
        model = "fake-model"

        def generate(self, **_kwargs) -> LLMResponse:
            calls["n"] += 1
            err = Exception("invalid x-api-key")
            err.status_code = 401  # type: ignore[attr-defined]
            raise err

        def generate_stream(self, **kwargs):  # noqa: ANN201
            response = self.generate(**kwargs)
            if False:
                yield ""
            return response

    loop = ExecutionLoop(_AuthError(), ToolRegistry(), SubAgentMemory(), base_system_prompt="x")
    loop.add_user_message("hi")
    with pytest.raises(Exception, match="invalid x-api-key"):
        loop.run(max_iterations=2)
    assert calls["n"] == 1  # 401 is not retryable
