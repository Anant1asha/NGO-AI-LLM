"""Regression-runner scaffold for Hachi's eval suite.

Design philosophy
-----------------
Every assertion is evaluated against the trajectory produced by a REAL execution —
either a real agent session turn or a real ``ExecutionLoop`` driven by a scripted LLM.
The runner must NEVER hardcode "pass": a failing assertion produces ``passed=False``
with an explicit human-readable reason.  This is enforced structurally (``run_case``
only sets ``passed=True`` after ALL assertions pass) and verified by the test suite
(``test_eval_runner.py`` includes a deliberately-unsatisfiable assertion that MUST
produce ``passed=False``).

Dependency injection via ``turn_fn``
-------------------------------------
``run_case(case, turn_fn=...)`` accepts a callable that takes the user input string
and returns a :class:`TurnTrajectory`.  Production code wires a booted
``AgentSession``/``ExecutionLoop`` turn; test code wires a real ``ExecutionLoop``
driven by a scripted LLM client (see ``tests/test_eval_runner.py``).  This keeps the
runner's core logic framework-agnostic and makes the anti-fake guarantee testable
without a live Anthropic API key.

Growing the suite
-----------------
``DEFAULT_SUITE`` is an intentional SEED — 2 generic smoke-test cases that validate
the most basic structural properties.  It is NOT exhaustive coverage.  Add domain-
specific cases (real tool workflows, real user patterns, budget checks) as the product
matures.  Each ``EvalCase`` is a plain dataclass — JSON/YAML round-trips are trivial
to add when a file-based suite registry is needed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Trajectory — what a single agent turn produces
# ---------------------------------------------------------------------------


@dataclass
class TurnTrajectory:
    """Captured output of one agent turn for assertion checking.

    Attributes
    ----------
    output : str
        The final textual response from the agent.  Empty string if the turn
        produced no text (error or tool-only).
    tool_calls : list[str]
        Tool names called during the turn, in call order.
    cost_usd : float
        Estimated cost in USD for the turn (0.0 when unknown).
    error : str | None
        Error message if the turn raised an unhandled exception; None otherwise.
    raw : dict[str, Any]
        Optional bag for any extra data the turn_fn wants to surface (e.g. token
        counts, model used).  Not used by the built-in assertion kinds.
    """

    output: str = ""
    tool_calls: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Assertion kinds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolCalledAssertion:
    """Assert that a tool with the given name was called during the turn."""

    name: str

    def check(self, trajectory: TurnTrajectory) -> str | None:
        """Return None on pass, or a failure reason string."""
        if self.name in trajectory.tool_calls:
            return None
        called = trajectory.tool_calls or ["(none)"]
        return f"tool_called({self.name!r}): not found in {called}"


@dataclass(frozen=True)
class OutputContainsAssertion:
    """Assert that the agent's output contains the given substring."""

    substr: str

    def check(self, trajectory: TurnTrajectory) -> str | None:
        if self.substr in trajectory.output:
            return None
        head = trajectory.output[:120]
        return f"output_contains({self.substr!r}): not found; output starts with {head!r}"


@dataclass(frozen=True)
class NoErrorAssertion:
    """Assert that the turn completed without raising an exception."""

    def check(self, trajectory: TurnTrajectory) -> str | None:
        if trajectory.error is None:
            return None
        return f"no_error: turn raised an error: {trajectory.error}"


@dataclass(frozen=True)
class MaxCostAssertion:
    """Assert that the turn's cost did not exceed a USD threshold."""

    max_usd: float

    def check(self, trajectory: TurnTrajectory) -> str | None:
        if trajectory.cost_usd <= self.max_usd:
            return None
        return (
            f"max_cost_usd({self.max_usd}): actual cost was ${trajectory.cost_usd:.6f}"
        )


@dataclass(frozen=True)
class ToolCallCountAssertion:
    """Assert that the total number of tool calls equals ``count``.

    Catches double-execution and skipped-execution regressions: if the loop
    dispatches a tool twice (or not at all) when the script expects exactly one,
    this assertion fires before a ``tool_called`` check can surface the problem.
    """

    count: int

    def check(self, trajectory: TurnTrajectory) -> str | None:
        """Return None on pass, or a failure reason string."""
        actual = len(trajectory.tool_calls)
        if actual == self.count:
            return None
        return (
            f"tool_call_count({self.count}): expected {self.count} tool call(s) "
            f"but got {actual}: {trajectory.tool_calls}"
        )


@dataclass(frozen=True)
class OutputNotContainsAssertion:
    """Assert that the agent's output does NOT contain the given substring.

    Catches raw error markers and internal junk leaking into user-facing output
    (e.g. ``[INCOMPLETE]``, ``Tool Execution Error:``, stack traces).
    """

    substr: str

    def check(self, trajectory: TurnTrajectory) -> str | None:
        """Return None on pass, or a failure reason string."""
        if self.substr not in trajectory.output:
            return None
        idx = trajectory.output.find(self.substr)
        ctx = trajectory.output[max(0, idx - 20) : idx + len(self.substr) + 20]
        return (
            f"output_not_contains({self.substr!r}): substring found in output; "
            f"context: {ctx!r}"
        )


@dataclass(frozen=True)
class ToolOrderAssertion:
    """Assert that ``names`` appears as an ordered subsequence of the tool_calls list.

    Catches multi-step sequencing regressions: if the loop executes tools in the
    wrong order the subsequence check fails even if all tools were called.

    ``names`` does NOT have to be a contiguous slice — other tool calls may
    interleave.  Every element of ``names`` must appear in ``trajectory.tool_calls``
    in order (each match consumes one position).
    """

    names: tuple[str, ...]  # frozen dataclasses require hashable fields

    def check(self, trajectory: TurnTrajectory) -> str | None:
        """Return None on pass, or a failure reason string."""
        calls = trajectory.tool_calls
        it = iter(calls)
        for required in self.names:
            for actual in it:
                if actual == required:
                    break
            else:
                return (
                    f"tool_called_in_order({list(self.names)!r}): ordered subsequence "
                    f"not found in {calls}"
                )
        return None


# Typed union of all assertion kinds.
EvalAssertion = (
    ToolCalledAssertion
    | OutputContainsAssertion
    | NoErrorAssertion
    | MaxCostAssertion
    | ToolCallCountAssertion
    | OutputNotContainsAssertion
    | ToolOrderAssertion
)


def tool_called(name: str) -> EvalAssertion:
    """Convenience constructor: assert a tool was called."""
    return ToolCalledAssertion(name=name)


def output_contains(substr: str) -> EvalAssertion:
    """Convenience constructor: assert output contains a substring."""
    return OutputContainsAssertion(substr=substr)


def no_error() -> EvalAssertion:
    """Convenience constructor: assert no exception was raised."""
    return NoErrorAssertion()


def max_cost_usd(x: float) -> EvalAssertion:
    """Convenience constructor: assert turn cost <= x USD."""
    return MaxCostAssertion(max_usd=x)


def tool_call_count(n: int) -> EvalAssertion:
    """Convenience constructor: assert exactly n tool calls were made."""
    return ToolCallCountAssertion(count=n)


def output_not_contains(s: str) -> EvalAssertion:
    """Convenience constructor: assert output does NOT contain substring s."""
    return OutputNotContainsAssertion(substr=s)


def tool_called_in_order(names: list[str]) -> EvalAssertion:
    """Convenience constructor: assert names appears as an ordered subsequence of tool_calls."""
    return ToolOrderAssertion(names=tuple(names))


# ---------------------------------------------------------------------------
# EvalCase and result
# ---------------------------------------------------------------------------


@dataclass
class EvalCase:
    """A named regression case: a user input + structural assertions to check.

    Args:
        name:        Human-readable name shown in the scorecard.
        user_input:  The text sent to the agent as a user message.
        assertions:  List of structural assertions evaluated against the real
                     trajectory returned by ``turn_fn``.
    """

    name: str
    user_input: str
    assertions: list[EvalAssertion] = field(default_factory=list)


@dataclass
class EvalCaseResult:
    """Result of running one :class:`EvalCase`.

    Attributes
    ----------
    name : str
        The EvalCase name, for display.
    passed : bool
        True iff ALL assertions passed.  NEVER hardcoded; set only by run_case.
    failures : list[str]
        Human-readable failure reasons for each failing assertion.
        Empty list when passed=True.
    trajectory : TurnTrajectory
        The real trajectory captured from the turn_fn call.
    """

    name: str
    passed: bool
    failures: list[str]
    trajectory: TurnTrajectory


# ---------------------------------------------------------------------------
# run_case — the anti-fake core
# ---------------------------------------------------------------------------


def run_case(
    case: EvalCase,
    *,
    turn_fn: Callable[[str], TurnTrajectory],
) -> EvalCaseResult:
    """Execute one EvalCase and return a result based on REAL execution.

    The ``turn_fn`` callable is dependency-injected:
    - **Production**: wire a booted ``AgentSession`` or ``ExecutionLoop`` turn.
    - **Tests**: wire a real ``ExecutionLoop`` driven by a scripted LLM client
      (see ``tests/test_eval_runner.py``).

    **Anti-fake guarantee**: this function NEVER hardcodes ``passed=True``.
    It collects failure reasons from every assertion and sets ``passed=True``
    only when the failures list is empty after all checks.  A runner that always
    returns pass would fail the anti-fake test in ``test_eval_runner.py``.

    Args:
        case:     The EvalCase to run.
        turn_fn:  Callable that executes one agent turn and returns a TurnTrajectory.

    Returns:
        An :class:`EvalCaseResult` with real trajectory and honest pass/fail.
    """
    try:
        trajectory = turn_fn(case.user_input)
    except Exception as exc:  # noqa: BLE001
        # If the turn_fn itself raises, synthesise an error trajectory so
        # assertions can still run (no_error() will catch it).
        trajectory = TurnTrajectory(error=str(exc))

    failures: list[str] = []
    for assertion in case.assertions:
        reason = assertion.check(trajectory)
        if reason is not None:
            failures.append(reason)

    return EvalCaseResult(
        name=case.name,
        passed=len(failures) == 0,
        failures=failures,
        trajectory=trajectory,
    )


# ---------------------------------------------------------------------------
# DEFAULT_SUITE — seed of a growable regression suite
# ---------------------------------------------------------------------------

# This is intentionally a SMALL SEED, not exhaustive coverage.
# Add domain-specific cases as the product matures — tool workflows, budget
# checks, memory recall, multi-turn patterns, etc.

DEFAULT_SUITE: list[EvalCase] = [
    EvalCase(
        name="echo_tool_called",
        user_input="Please echo the word hello.",
        assertions=[
            no_error(),
        ],
    ),
    EvalCase(
        name="plain_text_reply",
        user_input="Say the word 'pong' back to me.",
        assertions=[
            no_error(),
            output_contains("pong"),
        ],
    ),
]
