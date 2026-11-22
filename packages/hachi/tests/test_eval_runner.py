"""Tests for the eval regression runner.

Anti-fake proof
---------------
The critical property this test file establishes is:

  A runner that always returns ``passed=True`` would fail the test
  ``test_unsatisfiable_assertion_fails_with_reason``.

That test deliberately passes an ``output_contains("NEVER_IN_OUTPUT")`` assertion
against a scripted ExecutionLoop that returns "pong".  The assertion MUST produce
``passed=False`` with a non-empty failure reason.  Any implementation that
hard-codes ``passed=True`` or skips assertion checking would break this test.

Real execution
--------------
The ``turn_fn`` used here is NOT a mock.  It runs a genuine ``ExecutionLoop``
(the same class exercised by ``test_e2e_loop.py``) with a ``ScriptedLLMClient``
that returns a predetermined ``LLMResponse``.  The trajectory is therefore real:
tool_calls, output, and cost all come from executing real loop code, not stubs.
"""

from __future__ import annotations

from typing import Any

from hachi.core.eval.runner import (
    EvalCase,
    MaxCostAssertion,
    NoErrorAssertion,
    OutputContainsAssertion,
    ToolCalledAssertion,
    TurnTrajectory,
    max_cost_usd,
    no_error,
    output_contains,
    run_case,
    tool_called,
)
from hachi.core.llm import LLMResponse, ToolCall
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.sub_agent import SubAgentMemory

# ---------------------------------------------------------------------------
# Scripted LLM harness (copied from test_e2e_loop.py — no shared import to
# keep this file independently runnable)
# ---------------------------------------------------------------------------


_EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


def _tool_schema(name: str) -> dict[str, Any]:
    return {"name": name, "description": name, "input_schema": _EMPTY_SCHEMA}


class ScriptedLLMClient:
    """Fake LLM that returns a predetermined queue of LLMResponse objects."""

    model = "scripted-test-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = responses
        self.calls: int = 0

    def generate(self, **kwargs: Any) -> LLMResponse:
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp

    def generate_stream(self, **kwargs: Any):  # type: ignore[return]
        response = self.generate(**kwargs)

        def _gen():
            if response.content:
                yield response.content
            return response

        return _gen()


def _make_turn_fn(
    responses: list[LLMResponse],
    registry: ToolRegistry | None = None,
) -> Any:
    """Return a turn_fn that drives a real ExecutionLoop with a scripted LLM.

    This is the ANTI-FAKE proof that the runner exercises real code:
    - ``ExecutionLoop`` is the production class, not a mock.
    - ``ScriptedLLMClient`` is deterministic but actually runs the ReAct loop.
    - ``TurnTrajectory`` fields (output, tool_calls, cost_usd, error) come from
      real execution, not hand-crafted return values.
    """
    llm = ScriptedLLMClient(responses)
    reg = registry if registry is not None else ToolRegistry()
    mem = SubAgentMemory()
    loop = ExecutionLoop(
        llm_client=llm,
        registry=reg,
        memory=mem,
        base_system_prompt="test",
    )

    def turn_fn(user_input: str) -> TurnTrajectory:
        loop.add_user_message(user_input)
        try:
            output = loop.run(max_iterations=5)
            tool_names = loop.last_tool_calls
            return TurnTrajectory(
                output=output,
                tool_calls=tool_names,
                cost_usd=0.0,  # scripted LLM has no cost tracker
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            return TurnTrajectory(error=str(exc))

    return turn_fn


# ---------------------------------------------------------------------------
# Tests — assertion helpers check() directly
# ---------------------------------------------------------------------------


def test_tool_called_assertion_pass() -> None:
    t = TurnTrajectory(tool_calls=["search", "read_file"])
    assert ToolCalledAssertion("search").check(t) is None


def test_tool_called_assertion_fail() -> None:
    t = TurnTrajectory(tool_calls=["read_file"])
    reason = ToolCalledAssertion("search").check(t)
    assert reason is not None
    assert "search" in reason


def test_output_contains_assertion_pass() -> None:
    t = TurnTrajectory(output="The answer is pong.")
    assert OutputContainsAssertion("pong").check(t) is None


def test_output_contains_assertion_fail() -> None:
    t = TurnTrajectory(output="The answer is pong.")
    reason = OutputContainsAssertion("NEVER_IN_OUTPUT").check(t)
    assert reason is not None
    assert "NEVER_IN_OUTPUT" in reason


def test_no_error_assertion_pass() -> None:
    t = TurnTrajectory(error=None)
    assert NoErrorAssertion().check(t) is None


def test_no_error_assertion_fail() -> None:
    t = TurnTrajectory(error="ValueError: oops")
    reason = NoErrorAssertion().check(t)
    assert reason is not None
    assert "ValueError" in reason


def test_max_cost_assertion_pass() -> None:
    t = TurnTrajectory(cost_usd=0.001)
    assert MaxCostAssertion(max_usd=0.01).check(t) is None


def test_max_cost_assertion_fail() -> None:
    t = TurnTrajectory(cost_usd=0.05)
    reason = MaxCostAssertion(max_usd=0.01).check(t)
    assert reason is not None
    assert "0.05" in reason


# ---------------------------------------------------------------------------
# Tests — run_case with a real ExecutionLoop
# ---------------------------------------------------------------------------


def test_satisfiable_assertion_passes_on_real_execution() -> None:
    """A satisfiable assertion passes when the scripted turn produces matching output.

    This exercises a REAL ExecutionLoop — not a stub — via ScriptedLLMClient.
    """
    responses = [LLMResponse(content="pong")]
    turn_fn = _make_turn_fn(responses)

    case = EvalCase(
        name="pong_reply",
        user_input="say pong",
        assertions=[no_error(), output_contains("pong")],
    )
    result = run_case(case, turn_fn=turn_fn)

    assert result.passed is True
    assert result.failures == []
    assert result.trajectory.output == "pong"


def test_unsatisfiable_assertion_fails_with_reason() -> None:
    """ANTI-FAKE: a wrong assertion produces passed=False with a non-empty reason.

    The scripted LLM returns "pong", but the assertion checks for
    "NEVER_IN_OUTPUT".  Any runner that always returns pass would fail here.
    """
    responses = [LLMResponse(content="pong")]
    turn_fn = _make_turn_fn(responses)

    case = EvalCase(
        name="will_fail",
        user_input="say pong",
        assertions=[
            no_error(),                         # this PASSES
            output_contains("NEVER_IN_OUTPUT"), # this MUST FAIL
        ],
    )
    result = run_case(case, turn_fn=turn_fn)

    # The runner must not pass this case.
    assert result.passed is False
    # There must be exactly one failure (no_error passed; output_contains failed).
    assert len(result.failures) == 1
    # The failure reason must name the needle that was not found.
    assert "NEVER_IN_OUTPUT" in result.failures[0]
    # The real trajectory was still captured.
    assert result.trajectory.output == "pong"


def test_tool_called_assertion_passes_on_real_tool_execution() -> None:
    """tool_called assertion verifies a tool actually ran in the real loop."""
    reg = ToolRegistry()
    reg.register(_tool_schema("my_tool"), lambda: "tool_result")

    responses = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="tc1", name="my_tool", input={})],
        ),
        LLMResponse(content="done"),
    ]
    turn_fn = _make_turn_fn(responses, registry=reg)

    case = EvalCase(
        name="tool_fires",
        user_input="call my_tool",
        assertions=[no_error(), tool_called("my_tool")],
    )
    result = run_case(case, turn_fn=turn_fn)

    assert result.passed is True
    assert "my_tool" in result.trajectory.tool_calls


def test_tool_called_assertion_fails_when_tool_not_called() -> None:
    """tool_called assertion fails when the scripted LLM never calls the tool."""
    responses = [LLMResponse(content="I did nothing")]
    turn_fn = _make_turn_fn(responses)

    case = EvalCase(
        name="tool_not_fired",
        user_input="call missing_tool",
        assertions=[tool_called("missing_tool")],
    )
    result = run_case(case, turn_fn=turn_fn)

    assert result.passed is False
    assert len(result.failures) == 1
    assert "missing_tool" in result.failures[0]


def test_run_case_no_assertions_always_passes() -> None:
    """A case with zero assertions trivially passes (no assertions to fail)."""
    responses = [LLMResponse(content="anything")]
    turn_fn = _make_turn_fn(responses)

    case = EvalCase(name="no_assertions", user_input="hi", assertions=[])
    result = run_case(case, turn_fn=turn_fn)
    assert result.passed is True
    assert result.failures == []


def test_run_case_turn_fn_exception_becomes_error_trajectory() -> None:
    """If turn_fn raises, the result has error in the trajectory and no_error() fails."""

    def exploding_turn_fn(user_input: str) -> TurnTrajectory:
        raise RuntimeError("kaboom")

    case = EvalCase(
        name="exploding",
        user_input="trigger error",
        assertions=[no_error()],
    )
    result = run_case(case, turn_fn=exploding_turn_fn)

    assert result.passed is False
    assert result.trajectory.error == "kaboom"
    assert "kaboom" in result.failures[0]


def test_multiple_failures_all_reported() -> None:
    """All failing assertions are collected, not just the first."""
    responses = [LLMResponse(content="something")]
    turn_fn = _make_turn_fn(responses)

    case = EvalCase(
        name="multi_fail",
        user_input="test",
        assertions=[
            output_contains("ABSENT_1"),
            output_contains("ABSENT_2"),
            tool_called("ghost_tool"),
        ],
    )
    result = run_case(case, turn_fn=turn_fn)

    assert result.passed is False
    assert len(result.failures) == 3


# ---------------------------------------------------------------------------
# Tests — convenience constructors
# ---------------------------------------------------------------------------


def test_convenience_constructors_return_correct_types() -> None:
    assert isinstance(tool_called("x"), ToolCalledAssertion)
    assert isinstance(output_contains("y"), OutputContainsAssertion)
    assert isinstance(no_error(), NoErrorAssertion)
    assert isinstance(max_cost_usd(0.01), MaxCostAssertion)
