"""Tests for the record/replay eval harness.

Anti-fake contract
------------------
This test file enforces three properties that prevent the replay harness from
ever lying about pass/fail:

1. Real execution: ``run_replay_suite(DEFAULT_REPLAY_SUITE)`` must produce
   trajectories whose content comes from the scripted ``ExecutionLoop`` — not
   from hand-crafted stubs.  We check that tool names actually appear in
   ``trajectory.tool_calls`` and that output substrings come from the scripted
   responses.

2. Anti-fake: a ``ReplayCase`` with an unsatisfiable assertion MUST produce
   ``passed=False`` with a non-empty failure reason.  Any harness that always
   returns ``passed=True`` would fail ``test_failing_case_produces_failed_result``.

3. CLI exit codes: ``eval run`` must exit 0 when all cases pass and exit != 0
   when any case fails.  We verify both paths by (a) running against
   ``DEFAULT_REPLAY_SUITE`` directly and (b) injecting a suite containing a
   deliberately-broken case via monkeypatching.
"""

from __future__ import annotations

from typing import Any  # noqa: UP035 — needed for the Any annotation in test helpers

import pytest

from hachi.core.eval.corpus import DEFAULT_REPLAY_SUITE
from hachi.core.eval.replay import (
    ReplayCase,
    ScriptedLLMClient,
    ToolSpec,
    make_replay_turn_fn,
    run_replay_suite,
)
from hachi.core.eval.runner import (
    EvalCase,
    no_error,
    output_contains,
    tool_called,
)
from hachi.core.llm import LLMResponse, ToolCall

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_replay_case(
    name: str,
    responses: list[LLMResponse],
    assertions: list,
    tools: list[ToolSpec] | None = None,
) -> ReplayCase:
    """Build a minimal ReplayCase for use in tests."""
    return ReplayCase(
        case=EvalCase(name=name, user_input="test input", assertions=assertions),
        llm_script=responses,
        tools=tools or [],
    )


# ---------------------------------------------------------------------------
# ScriptedLLMClient unit tests
# ---------------------------------------------------------------------------


def test_scripted_client_replays_responses() -> None:
    """ScriptedLLMClient returns each response in order."""
    responses = [LLMResponse(content="a"), LLMResponse(content="b")]
    client = ScriptedLLMClient(responses)
    r1 = client.generate()
    r2 = client.generate()
    assert r1.content == "a"
    assert r2.content == "b"
    assert client.calls == 2


def test_scripted_client_repeats_last_when_exhausted() -> None:
    """ScriptedLLMClient repeats the last response once the queue is exhausted."""
    client = ScriptedLLMClient([LLMResponse(content="only")])
    for _ in range(5):
        r = client.generate()
        assert r.content == "only"


def test_scripted_client_requires_nonempty_responses() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ScriptedLLMClient([])


def test_scripted_client_generate_stream_yields_content() -> None:
    """generate_stream() yields the content and returns the LLMResponse."""
    client = ScriptedLLMClient([LLMResponse(content="hello")])
    gen = client.generate_stream()
    chunks = []
    try:
        while True:
            chunks.append(next(gen))
    except StopIteration as si:
        final = si.value
    assert chunks == ["hello"]
    assert final.content == "hello"


# ---------------------------------------------------------------------------
# make_replay_turn_fn — drives a REAL ExecutionLoop
# ---------------------------------------------------------------------------


def test_turn_fn_plain_text_reply() -> None:
    """A simple scripted reply comes through as trajectory.output."""
    rc = _simple_replay_case(
        "text_only",
        [LLMResponse(content="hello world")],
        [no_error(), output_contains("hello world")],
    )
    turn_fn = make_replay_turn_fn(rc)
    traj = turn_fn("say hello")
    assert traj.error is None
    assert "hello world" in traj.output


def test_turn_fn_tool_call_fires_and_appears_in_trajectory() -> None:
    """A tool_call in the script causes the tool to run and appear in tool_calls."""
    tool_was_called = []

    def my_tool(**_kw: Any) -> str:
        tool_was_called.append(True)
        return "my_result"

    rc = ReplayCase(
        case=EvalCase(
            name="tool_fires",
            user_input="call my_tool",
            assertions=[no_error(), tool_called("my_tool")],
        ),
        llm_script=[
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="my_tool", input={})],
            ),
            LLMResponse(content="done"),
        ],
        tools=[ToolSpec(name="my_tool", callable=my_tool)],
    )
    turn_fn = make_replay_turn_fn(rc)
    traj = turn_fn("call my_tool")
    assert traj.error is None
    assert "my_tool" in traj.tool_calls
    assert tool_was_called, "tool callable was never invoked"


def test_turn_fn_cost_is_zero() -> None:
    """cost_usd is always 0.0 for scripted/replay runs (no real cost meter)."""
    rc = _simple_replay_case("cost_check", [LLMResponse(content="x")], [no_error()])
    traj = make_replay_turn_fn(rc)("hi")
    assert traj.cost_usd == 0.0


# ---------------------------------------------------------------------------
# run_replay_suite — integration over the full corpus
# ---------------------------------------------------------------------------


def test_default_replay_suite_all_pass() -> None:
    """Every case in DEFAULT_REPLAY_SUITE must pass.

    This is the primary regression gate: a broken corpus case or a broken loop
    produces a failed result, which fails this test.
    """
    results = run_replay_suite(DEFAULT_REPLAY_SUITE)
    assert len(results) == len(DEFAULT_REPLAY_SUITE)
    for r in results:
        assert r.passed is True, (
            f"Case '{r.name}' failed unexpectedly. Failures: {r.failures}"
        )


def test_default_replay_suite_has_minimum_cases() -> None:
    """DEFAULT_REPLAY_SUITE must contain at least 12 meaningful cases.

    This guards against accidental corpus shrinkage: the E6 expansion grew the
    suite to 14 cases covering real loop-mechanics invariants.  Any PR that drops
    below 12 cases will fail this test.
    """
    assert len(DEFAULT_REPLAY_SUITE) >= 12, (
        f"Expected at least 12 cases but found {len(DEFAULT_REPLAY_SUITE)}. "
        "Do not remove corpus cases without a deliberate decision."
    )


def test_default_replay_suite_case_names_are_unique() -> None:
    """All case names in DEFAULT_REPLAY_SUITE must be unique.

    Duplicate names make scorecard output ambiguous and can hide failures.
    """
    names = [rc.case.name for rc in DEFAULT_REPLAY_SUITE]
    assert len(names) == len(set(names)), (
        f"Duplicate case names found: {[n for n in names if names.count(n) > 1]}"
    )


def test_default_replay_suite_tool_case_has_tool_in_trajectory() -> None:
    """The 'single_tool_call' corpus case must have the tool in trajectory.tool_calls.

    This proves the trajectory is REAL (from ExecutionLoop execution) — not fabricated.
    """
    results = run_replay_suite(DEFAULT_REPLAY_SUITE)
    tool_result = next(r for r in results if r.name == "single_tool_call")
    assert "fetch_summary" in tool_result.trajectory.tool_calls


def test_default_replay_suite_two_tool_case_has_both_tools() -> None:
    """The 'two_tool_trajectory' corpus case must have both tools in the trajectory."""
    results = run_replay_suite(DEFAULT_REPLAY_SUITE)
    two_tool = next(r for r in results if r.name == "two_tool_trajectory")
    assert "step_one" in two_tool.trajectory.tool_calls
    assert "step_two" in two_tool.trajectory.tool_calls


def test_default_replay_suite_output_contains_paris() -> None:
    """The 'output_contains_smoke' corpus case must have 'Paris' in the output."""
    results = run_replay_suite(DEFAULT_REPLAY_SUITE)
    paris = next(r for r in results if r.name == "output_contains_smoke")
    assert "Paris" in paris.trajectory.output


# ---------------------------------------------------------------------------
# Anti-fake: a failing case MUST produce passed=False
# ---------------------------------------------------------------------------


def test_failing_case_produces_failed_result() -> None:
    """ANTI-FAKE: an unsatisfiable assertion must produce passed=False.

    The scripted LLM returns 'pong', but the assertion checks for
    'NEVER_PRESENT_IN_OUTPUT'.  Any harness that always returns passed=True
    would fail this test.
    """
    rc = _simple_replay_case(
        "anti_fake",
        [LLMResponse(content="pong")],
        [
            no_error(),                              # this PASSES
            output_contains("NEVER_PRESENT_IN_OUTPUT"),  # this MUST FAIL
        ],
    )
    results = run_replay_suite([rc])
    assert len(results) == 1
    result = results[0]
    assert result.passed is False, "Anti-fake violated: harness returned passed=True"
    assert len(result.failures) == 1
    assert "NEVER_PRESENT_IN_OUTPUT" in result.failures[0]
    # The real trajectory was still captured (output comes from the scripted loop).
    assert result.trajectory.output == "pong"


def test_missing_tool_assertion_fails_with_reason() -> None:
    """tool_called for an uncalled tool produces passed=False with a useful reason."""
    rc = _simple_replay_case(
        "ghost_tool",
        [LLMResponse(content="I did nothing")],
        [tool_called("ghost_tool")],
    )
    results = run_replay_suite([rc])
    result = results[0]
    assert result.passed is False
    assert "ghost_tool" in result.failures[0]


def test_multiple_failing_assertions_all_reported() -> None:
    """All failing assertions are collected, not just the first."""
    rc = _simple_replay_case(
        "multi_fail",
        [LLMResponse(content="something else")],
        [
            output_contains("ABSENT_1"),
            output_contains("ABSENT_2"),
            tool_called("ghost"),
        ],
    )
    results = run_replay_suite([rc])
    result = results[0]
    assert result.passed is False
    assert len(result.failures) == 3


# ---------------------------------------------------------------------------
# CLI exit-code tests
# ---------------------------------------------------------------------------


def _get_cli_app():
    """Return the Typer app from the CLI main entry point."""
    from hachi.cli.main import app
    return app


def test_eval_run_cli_exits_zero_on_all_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """``hachi eval run`` exits 0 when DEFAULT_REPLAY_SUITE all pass."""
    from typer.testing import CliRunner

    app = _get_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["eval", "run"])
    # Exit code 0 means all cases passed.
    assert result.exit_code == 0, (
        f"Expected exit code 0 but got {result.exit_code}.\nOutput:\n{result.output}"
    )
    assert "passed" in result.output.lower()


def test_eval_run_cli_exits_nonzero_on_failing_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """``hachi eval run --suite <failing.py>`` exits non-zero when a case fails.

    We write a tiny .py suite file containing a deliberately-broken ReplayCase
    (unsatisfiable output_contains assertion) and pass it via --suite so we
    don't need to monkeypatch the corpus module.
    """
    from typer.testing import CliRunner

    suite_py = tmp_path / "failing_suite.py"
    suite_py.write_text(
        """\
from hachi.core.eval.replay import ReplayCase, ToolSpec
from hachi.core.eval.runner import EvalCase, no_error, output_contains
from hachi.core.llm import LLMResponse

SUITE = [
    ReplayCase(
        case=EvalCase(
            name="will_fail",
            user_input="say pong",
            assertions=[
                no_error(),
                output_contains("NEVER_PRESENT"),
            ],
        ),
        llm_script=[LLMResponse(content="pong")],
    ),
]
""",
        encoding="utf-8",
    )

    app = _get_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["eval", "run", "--suite", str(suite_py)])

    # The command must exit non-zero when any case fails.
    assert result.exit_code != 0, (
        f"Expected non-zero exit code but got 0.\nOutput:\n{result.output}"
    )
    assert "FAIL" in result.output or "failed" in result.output.lower()


def test_eval_run_cli_suite_option_respects_all_pass_file(tmp_path) -> None:
    """A .py suite file with all-passing cases exits 0."""
    from typer.testing import CliRunner

    suite_py = tmp_path / "passing_suite.py"
    suite_py.write_text(
        """\
from hachi.core.eval.replay import ReplayCase
from hachi.core.eval.runner import EvalCase, no_error, output_contains
from hachi.core.llm import LLMResponse

SUITE = [
    ReplayCase(
        case=EvalCase(
            name="passes",
            user_input="say hello",
            assertions=[no_error(), output_contains("hello")],
        ),
        llm_script=[LLMResponse(content="hello there")],
    ),
]
""",
        encoding="utf-8",
    )

    app = _get_cli_app()
    runner = CliRunner()
    result = runner.invoke(app, ["eval", "run", "--suite", str(suite_py)])
    assert result.exit_code == 0, (
        f"Expected exit code 0 but got {result.exit_code}.\nOutput:\n{result.output}"
    )
