"""S2 — sub-agents must inherit the parent's cost/token budget caps by default.

Bug: SubAgentRuntime.run() constructs the sub-agent's ExecutionLoop with only
llm_client/registry/memory/base_system_prompt/on_event/cost_tracker — never
max_cost_usd/max_tokens/max_cost_per_turn/max_tokens_per_turn. Even though the
sub-agent shares the parent's CostTracker (so spend is recorded), the
sub-agent's own ExecutionLoop budget checks (_budget_exceeded /
_turn_budget_exceeded) were always no-ops (default 0 = unlimited), so a
delegated sub-agent could run its full iteration budget completely unchecked
by any cost/token cap, only for the parent to notice on its NEXT turn (after
the sub-agent already finished draining the budget).

These tests pin: SubAgentRuntime accepts the same 4 cap kwargs ExecutionLoop
does, and threads them down so the sub-agent's own loop stops itself early
when a shared CostTracker crosses the cap — not just recording it silently.
"""

from __future__ import annotations

from hachi.core.cost import CostTracker
from hachi.core.llm import LLMResponse, TokenUsage, ToolCall
from hachi.core.loop import ToolRegistry
from hachi.core.sub_agent import SubAgentRuntime, SubAgentStatus

_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def _tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        {"name": "noop", "description": "noop", "input_schema": _EMPTY_SCHEMA},
        lambda **_kw: "ok",
    )
    return registry


class _RunawaySubAgentLLM:
    """Always asks for a tool call and reports a fixed token cost per call."""

    model = "fake-runaway-sub"

    def __init__(self, tokens_per_call: int = 1000) -> None:
        self.tokens_per_call = tokens_per_call
        self.calls = 0

    def generate(self, **_kw):  # noqa: ANN201
        self.calls += 1
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{self.calls}", name="noop", input={})],
            usage=TokenUsage(input_tokens=self.tokens_per_call, output_tokens=0),
        )

    def generate_stream(self, **_kw):  # noqa: ANN201
        self.calls += 1
        yield ""
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{self.calls}", name="noop", input={})],
            usage=TokenUsage(input_tokens=self.tokens_per_call, output_tokens=0),
        )


def test_sub_agent_inherits_parent_token_budget_and_stops_early() -> None:
    """A max_tokens cap passed to SubAgentRuntime must reach the sub-agent's own
    ExecutionLoop and stop it well before max_iterations, instead of running
    unchecked to the iteration limit.
    """
    tracker = CostTracker()
    llm = _RunawaySubAgentLLM(tokens_per_call=1000)

    runtime = SubAgentRuntime(
        role="analyst",
        task="loop forever calling tools",
        llm_client=llm,
        tool_registry=_tool_registry(),
        cost_tracker=tracker,
        max_iterations=50,  # generous — the budget cap must bite first
        max_tokens=2500,  # inherited "parent" cap: should stop after ~3 calls
    )
    report = runtime.run()

    assert llm.calls <= 5, (
        f"Expected the inherited token budget to stop the sub-agent loop early, "
        f"got {llm.calls} calls (cap=2500 tokens, 1000/call)"
    )
    assert report.status == SubAgentStatus.SUCCESS
    assert "BUDGET" in report.summary.upper()


def test_sub_agent_runtime_accepts_all_four_cap_kwargs() -> None:
    """SubAgentRuntime must accept the same 4 cap kwargs ExecutionLoop exposes,
    so callers (delegate_task) can thread the parent's configured caps down
    without SubAgentRuntime silently ignoring them (TypeError would mean the
    plumbing was never wired).
    """
    runtime = SubAgentRuntime(
        role="analyst",
        task="noop",
        llm_client=_RunawaySubAgentLLM(),
        max_cost_usd=1.0,
        max_tokens=1000,
        max_cost_per_turn=0.5,
        max_tokens_per_turn=500,
    )
    assert runtime is not None
