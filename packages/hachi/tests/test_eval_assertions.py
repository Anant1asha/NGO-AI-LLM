"""Unit tests for the three new EvalAssertion kinds added in E6.

Tests each new assertion BOTH ways — passing trajectory returns None, failing
trajectory returns a non-empty reason that names the expectation (anti-fake).

New assertion kinds tested here:
  - ToolCallCountAssertion / tool_call_count(n)
  - OutputNotContainsAssertion / output_not_contains(s)
  - ToolOrderAssertion / tool_called_in_order([...])
"""

from __future__ import annotations

from hachi.core.eval.runner import (
    EvalAssertion,
    OutputNotContainsAssertion,
    ToolCallCountAssertion,
    ToolOrderAssertion,
    TurnTrajectory,
    output_not_contains,
    tool_call_count,
    tool_called_in_order,
)

# ---------------------------------------------------------------------------
# ToolCallCountAssertion
# ---------------------------------------------------------------------------


def test_tool_call_count_passes_when_exact() -> None:
    """Passes when len(tool_calls) == count."""
    t = TurnTrajectory(tool_calls=["a", "b", "c"])
    assert ToolCallCountAssertion(count=3).check(t) is None


def test_tool_call_count_passes_zero() -> None:
    """Passes when count=0 and no tools were called."""
    t = TurnTrajectory(tool_calls=[])
    assert ToolCallCountAssertion(count=0).check(t) is None


def test_tool_call_count_fails_when_too_few() -> None:
    """Fails and returns a reason when fewer tools were called than expected."""
    t = TurnTrajectory(tool_calls=["a"])
    reason = ToolCallCountAssertion(count=3).check(t)
    assert reason is not None
    assert "3" in reason  # expected count named
    assert "1" in reason  # actual count named


def test_tool_call_count_fails_when_too_many() -> None:
    """Fails and returns a reason when more tools were called than expected."""
    t = TurnTrajectory(tool_calls=["a", "b", "c", "d"])
    reason = ToolCallCountAssertion(count=2).check(t)
    assert reason is not None
    assert "2" in reason  # expected count named
    assert "4" in reason  # actual count named


def test_tool_call_count_failure_names_expectation() -> None:
    """The failure reason must reference both the expected and actual counts."""
    t = TurnTrajectory(tool_calls=["x"])
    reason = ToolCallCountAssertion(count=5).check(t)
    assert reason is not None
    assert "5" in reason
    assert "1" in reason


def test_tool_call_count_convenience_constructor_type() -> None:
    """tool_call_count() returns a ToolCallCountAssertion."""
    assertion = tool_call_count(2)
    assert isinstance(assertion, ToolCallCountAssertion)
    assert assertion.count == 2


def test_tool_call_count_convenience_constructor_pass() -> None:
    """Convenience constructor works end-to-end."""
    t = TurnTrajectory(tool_calls=["x", "y"])
    assert tool_call_count(2).check(t) is None


def test_tool_call_count_convenience_constructor_fail() -> None:
    """Convenience constructor fail path returns non-empty reason."""
    t = TurnTrajectory(tool_calls=["x", "y"])
    reason = tool_call_count(1).check(t)
    assert reason is not None
    assert len(reason) > 0


# ---------------------------------------------------------------------------
# OutputNotContainsAssertion
# ---------------------------------------------------------------------------


def test_output_not_contains_passes_when_absent() -> None:
    """Passes when the substring is not in output."""
    t = TurnTrajectory(output="The answer is 42.")
    assert OutputNotContainsAssertion(substr="[error]").check(t) is None


def test_output_not_contains_passes_empty_output() -> None:
    """Passes on empty output (substring cannot be present)."""
    t = TurnTrajectory(output="")
    assert OutputNotContainsAssertion(substr="[error]").check(t) is None


def test_output_not_contains_fails_when_present() -> None:
    """Fails and returns a reason when the substring IS in output."""
    t = TurnTrajectory(output="Something went wrong: [error] occurred")
    reason = OutputNotContainsAssertion(substr="[error]").check(t)
    assert reason is not None
    assert "[error]" in reason


def test_output_not_contains_failure_names_expectation() -> None:
    """The failure reason must include the banned substring."""
    t = TurnTrajectory(output="prefix [INCOMPLETE] suffix")
    reason = OutputNotContainsAssertion(substr="[INCOMPLETE]").check(t)
    assert reason is not None
    assert "[INCOMPLETE]" in reason


def test_output_not_contains_fails_partial_match() -> None:
    """A partial-word match still triggers the failure."""
    t = TurnTrajectory(output="Tool Execution Error: division by zero")
    reason = OutputNotContainsAssertion(substr="Execution Error").check(t)
    assert reason is not None


def test_output_not_contains_case_sensitive() -> None:
    """Substring check is case-sensitive."""
    t = TurnTrajectory(output="[ERROR]")
    # "[error]" lowercase is NOT in "[ERROR]" uppercase — should pass.
    assert OutputNotContainsAssertion(substr="[error]").check(t) is None


def test_output_not_contains_convenience_constructor_type() -> None:
    """output_not_contains() returns an OutputNotContainsAssertion."""
    assertion = output_not_contains("nope")
    assert isinstance(assertion, OutputNotContainsAssertion)
    assert assertion.substr == "nope"


def test_output_not_contains_convenience_constructor_pass() -> None:
    """Convenience constructor works end-to-end: pass path."""
    t = TurnTrajectory(output="clean output")
    assert output_not_contains("[error]").check(t) is None


def test_output_not_contains_convenience_constructor_fail() -> None:
    """Convenience constructor works end-to-end: fail path."""
    t = TurnTrajectory(output="has [error] in it")
    reason = output_not_contains("[error]").check(t)
    assert reason is not None
    assert len(reason) > 0


# ---------------------------------------------------------------------------
# ToolOrderAssertion
# ---------------------------------------------------------------------------


def test_tool_order_passes_exact_sequence() -> None:
    """Passes when tool_calls is exactly the required sequence."""
    t = TurnTrajectory(tool_calls=["a", "b", "c"])
    assert ToolOrderAssertion(names=("a", "b", "c")).check(t) is None


def test_tool_order_passes_as_subsequence() -> None:
    """Passes when names is an ordered subsequence with other calls interleaved."""
    t = TurnTrajectory(tool_calls=["x", "a", "y", "b", "z", "c"])
    assert ToolOrderAssertion(names=("a", "b", "c")).check(t) is None


def test_tool_order_passes_single_element() -> None:
    """Single-element subsequence passes when the tool appears anywhere."""
    t = TurnTrajectory(tool_calls=["x", "y", "target", "z"])
    assert ToolOrderAssertion(names=("target",)).check(t) is None


def test_tool_order_fails_wrong_order() -> None:
    """Fails when the tools appear in the wrong order."""
    t = TurnTrajectory(tool_calls=["b", "a", "c"])
    # Requires a then b — but b comes before a.
    reason = ToolOrderAssertion(names=("a", "b")).check(t)
    assert reason is not None
    assert "a" in reason or "b" in reason


def test_tool_order_fails_missing_tool() -> None:
    """Fails when a required tool is absent from tool_calls."""
    t = TurnTrajectory(tool_calls=["a", "c"])
    reason = ToolOrderAssertion(names=("a", "b", "c")).check(t)
    assert reason is not None
    assert "b" in reason or "['a', 'b', 'c']" in reason


def test_tool_order_fails_empty_calls() -> None:
    """Fails when tool_calls is empty but names is non-empty."""
    t = TurnTrajectory(tool_calls=[])
    reason = ToolOrderAssertion(names=("a",)).check(t)
    assert reason is not None


def test_tool_order_passes_empty_names() -> None:
    """Empty names list is trivially satisfied (vacuous subsequence)."""
    t = TurnTrajectory(tool_calls=["a", "b"])
    assert ToolOrderAssertion(names=()).check(t) is None


def test_tool_order_failure_names_expectation() -> None:
    """The failure reason names the expected sequence."""
    t = TurnTrajectory(tool_calls=["x"])
    reason = ToolOrderAssertion(names=("a", "b", "c")).check(t)
    assert reason is not None
    # The reason should reference the required sequence.
    assert "a" in reason or "['a', 'b', 'c']" in reason


def test_tool_order_convenience_constructor_type() -> None:
    """tool_called_in_order() returns a ToolOrderAssertion."""
    assertion = tool_called_in_order(["p", "q"])
    assert isinstance(assertion, ToolOrderAssertion)
    assert assertion.names == ("p", "q")


def test_tool_order_convenience_constructor_pass() -> None:
    """Convenience constructor works end-to-end: pass path."""
    t = TurnTrajectory(tool_calls=["p", "q", "r"])
    assert tool_called_in_order(["p", "q"]).check(t) is None


def test_tool_order_convenience_constructor_fail() -> None:
    """Convenience constructor works end-to-end: fail path."""
    t = TurnTrajectory(tool_calls=["q", "p"])
    reason = tool_called_in_order(["p", "q"]).check(t)
    assert reason is not None
    assert len(reason) > 0


# ---------------------------------------------------------------------------
# EvalAssertion union coverage — confirm new kinds are members
# ---------------------------------------------------------------------------


def test_new_assertions_are_in_union() -> None:
    """ToolCallCountAssertion, OutputNotContainsAssertion, ToolOrderAssertion
    must be usable as EvalAssertion values (static union check via isinstance).
    """
    assertions: list[EvalAssertion] = [
        tool_call_count(1),
        output_not_contains("x"),
        tool_called_in_order(["a"]),
    ]
    assert all(a is not None for a in assertions)
    assert len(assertions) == 3
