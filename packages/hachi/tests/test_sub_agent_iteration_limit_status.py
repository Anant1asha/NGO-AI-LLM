"""S2 — sub-agent iteration-limit exhaustion must not be reported as SUCCESS.

Bug: ExecutionLoop.run() never raises AgentException when max_iterations is
exhausted (P1-04 made this a graceful [INCOMPLETE] string return, not a raised
exception — see tests/test_iteration_limit.py). SubAgentRuntime.run()'s
`except AgentException as exc:` branch, meant to map iteration-limit
exhaustion to SubAgentStatus.TIMEOUT, is therefore unreachable dead code: the
[INCOMPLETE] result string flows straight into the SUCCESS return path
instead, so a sub-agent that never finished its task (it was still calling
tools when forcibly cut off) is indistinguishable from one that completed
normally.
"""

from __future__ import annotations

from hachi.core.llm import LLMResponse, ToolCall
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


class _NeverFinishesLLM:
    """Always asks for a tool call — the loop can never finish on its own,
    forcing it to exhaust max_iterations and return "[INCOMPLETE] ...".
    """

    model = "fake-never-finishes"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, **_kw):  # noqa: ANN201
        self.calls += 1
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{self.calls}", name="noop", input={})],
        )

    def generate_stream(self, **_kw):  # noqa: ANN201
        self.calls += 1
        yield ""
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{self.calls}", name="noop", input={})],
        )


def test_sub_agent_iteration_limit_exhaustion_is_not_success() -> None:
    llm = _NeverFinishesLLM()
    runtime = SubAgentRuntime(
        role="analyst",
        task="loop forever calling tools",
        llm_client=llm,
        tool_registry=_tool_registry(),
        max_iterations=3,
    )
    report = runtime.run()

    assert report.status != SubAgentStatus.SUCCESS, (
        "iteration-limit exhaustion (the sub-agent never finished its task) "
        "must not be reported as SUCCESS"
    )
    assert report.status == SubAgentStatus.TIMEOUT
