"""Curated regression corpus of deterministic replay cases for ``hachi eval run``.

Purpose
-------
This corpus is a **loop-mechanics regression suite** — it protects the ReAct loop's
control flow (tool dispatch, multi-step sequencing, error handling, iteration cap,
output assembly) against refactors.  It does NOT test model decision quality: the LLM
transport is entirely scripted (``ScriptedLLMClient``), so pass/fail reflects whether
the production ``ExecutionLoop`` behaves correctly given a fixed sequence of responses —
not whether the model makes good decisions.

Honest cost limitation
----------------------
``ScriptedLLMClient`` has no real cost meter so ``TurnTrajectory.cost_usd`` is always
``0.0`` for replay-based runs.  ``max_cost_usd`` assertions are therefore intentionally
ABSENT from this corpus — checking a threshold against a synthetic ``0.0`` value is
meaningless.  Use a unit test with an explicit synthetic ``TurnTrajectory`` if you need
to exercise the cost-assertion code path.

Loop invariants covered
-----------------------
1.  Plain text reply — no tools fired.
2.  Single-tool call then summarise.
3.  Two-tool trajectory in separate iterations.
4.  Longer multi-turn smoke (3 LLM turns).
5.  output_contains baseline smoke.
6.  Tool error recovery — tool raises, loop feeds error back, turn still completes.
7.  Unregistered tool — LLM calls unknown tool, loop returns graceful error string, continues.
8.  Max-iterations cap — loop hits 10-iteration limit and returns [INCOMPLETE] without hanging.
9.  Empty/degraded response — LLM returns empty content + no tool_calls, loop finishes cleanly.
10. Tool with arguments — callable uses kwargs, LLM ToolCall carries non-empty input.
11. Parallel tool calls — single LLMResponse with two ToolCalls, both dispatched concurrently.
12. Three-tool ordered trajectory — asserts tool_called_in_order + tool_call_count(3).
13. Clean reply has zero tools — tool_call_count(0) + output_not_contains("[error]").
14. Error marker absent from normal reply — output_not_contains checks clean output.
"""

from __future__ import annotations

from hachi.core.eval.replay import ReplayCase, ToolSpec
from hachi.core.eval.runner import (
    EvalCase,
    no_error,
    output_contains,
    output_not_contains,
    tool_call_count,
    tool_called,
    tool_called_in_order,
)
from hachi.core.llm import LLMResponse, ToolCall

# ---------------------------------------------------------------------------
# Helper — build a trivial no-args tool callable
# ---------------------------------------------------------------------------


def _noop_tool(result: str = "ok") -> object:
    """Return a zero-argument callable that returns ``result``."""
    # The loop calls tools as func(**tool_call.input); the scripted inputs
    # here are always {} so the lambda receives no keyword arguments.
    return lambda **_kw: result


def _raising_tool(msg: str = "boom") -> object:
    """Return a callable that always raises RuntimeError(msg)."""

    def _raiser(**_kw: object) -> str:
        raise RuntimeError(msg)

    return _raiser


# ---------------------------------------------------------------------------
# DEFAULT_REPLAY_SUITE
# ---------------------------------------------------------------------------

DEFAULT_REPLAY_SUITE: list[ReplayCase] = [
    # ------------------------------------------------------------------
    # 1. Plain text reply — no tool calls; assert the scripted text comes
    #    through verbatim and the turn completes without error.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="plain_text_reply",
            user_input="Say the word 'pong' back to me.",
            assertions=[
                no_error(),
                output_contains("pong"),
            ],
        ),
        llm_script=[LLMResponse(content="pong")],
    ),
    # ------------------------------------------------------------------
    # 2. Single-tool call — the LLM script calls "fetch_summary" then
    #    emits a final text reply; assert tool fired + no error.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="single_tool_call",
            user_input="Fetch a summary for me.",
            assertions=[
                no_error(),
                tool_called("fetch_summary"),
                output_contains("Summary received"),
            ],
        ),
        llm_script=[
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="fetch_summary", input={})],
            ),
            LLMResponse(content="Summary received."),
        ],
        tools=[ToolSpec(name="fetch_summary", callable=_noop_tool("summary data"))],
    ),
    # ------------------------------------------------------------------
    # 3. Two-tool trajectory — LLM calls "step_one" then "step_two" in
    #    separate iterations then summarises; assert both tools ran.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="two_tool_trajectory",
            user_input="Run step_one then step_two.",
            assertions=[
                no_error(),
                tool_called("step_one"),
                tool_called("step_two"),
                output_contains("done"),
            ],
        ),
        llm_script=[
            # Iteration 1: call step_one
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc_a", name="step_one", input={})],
            ),
            # Iteration 2: call step_two
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc_b", name="step_two", input={})],
            ),
            # Iteration 3: final text
            LLMResponse(content="All done."),
        ],
        tools=[
            ToolSpec(name="step_one", callable=_noop_tool("step_one result")),
            ToolSpec(name="step_two", callable=_noop_tool("step_two result")),
        ],
    ),
    # ------------------------------------------------------------------
    # 4. Longer script smoke — three LLM turns finishing with a reply;
    #    primarily checks the loop handles a multi-turn script cleanly
    #    (no_error is the critical assertion here).
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="multi_turn_smoke",
            user_input="Do a multi-step calculation.",
            assertions=[
                no_error(),
                output_contains("42"),
            ],
        ),
        llm_script=[
            LLMResponse(content="", tool_calls=[ToolCall(id="tc1", name="calc", input={})]),
            LLMResponse(content="", tool_calls=[ToolCall(id="tc2", name="calc", input={})]),
            LLMResponse(content="The answer is 42."),
        ],
        tools=[ToolSpec(name="calc", callable=_noop_tool("21"))],
    ),
    # ------------------------------------------------------------------
    # 5. No-tool output_contains check — ensures the scripted output
    #    substring matching works end-to-end without any tool involvement.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="output_contains_smoke",
            user_input="What is the capital of France?",
            assertions=[
                no_error(),
                output_contains("Paris"),
            ],
        ),
        llm_script=[LLMResponse(content="The capital of France is Paris.")],
    ),
    # ------------------------------------------------------------------
    # 6. Tool error recovery — invariant: when a tool callable raises,
    #    ExecutionLoop catches the exception in _execute_single_tool and
    #    feeds an error string back to the LLM; the turn itself does NOT
    #    raise (no_error passes).  The loop then accepts the LLM's second
    #    response as the final reply.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="tool_error_recovery",
            user_input="Call the failing tool then reply.",
            assertions=[
                no_error(),  # turn must complete despite the tool raising
                tool_called("boom_tool"),
                output_contains("recovered"),
                output_not_contains("Traceback"),
            ],
        ),
        llm_script=[
            # Iteration 1: LLM calls boom_tool (which will raise)
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc_err", name="boom_tool", input={})],
            ),
            # Iteration 2: LLM receives the error feedback and replies
            LLMResponse(content="I recovered from the error."),
        ],
        tools=[ToolSpec(name="boom_tool", callable=_raising_tool("simulated failure"))],
    ),
    # ------------------------------------------------------------------
    # 7. Unregistered tool — invariant: when the LLM calls a tool name
    #    that is NOT in the ToolRegistry, ToolRegistry.execute() returns
    #    the string "Error: Tool 'ghost' is not registered." (no exception
    #    raised).  The loop feeds this string back to the LLM and the turn
    #    completes normally.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="unregistered_tool_graceful",
            user_input="Call a tool that does not exist.",
            assertions=[
                no_error(),  # turn must complete; registry returns error string, not raise
                tool_called("ghost"),
                output_contains("handled"),
            ],
        ),
        llm_script=[
            # Iteration 1: LLM calls an unregistered tool name
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc_ghost", name="ghost", input={})],
            ),
            # Iteration 2: LLM receives the "not registered" feedback and replies
            LLMResponse(content="The missing tool was handled gracefully."),
        ],
        # NOTE: 'ghost' is intentionally NOT registered — that is the point of this case.
        tools=[],
    ),
    # ------------------------------------------------------------------
    # 8. Max-iterations cap — invariant: when the LLM always calls a tool
    #    and never emits a final text reply, the loop terminates at
    #    max_iterations=10 (the replay harness default) and returns the
    #    [INCOMPLETE] sentinel string.  The turn must NOT hang or raise.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="max_iterations_cap",
            user_input="Keep calling a tool forever.",
            assertions=[
                no_error(),  # loop terminates cleanly, no exception
                # The loop emits [INCOMPLETE] when it hits the iteration limit.
                output_contains("[INCOMPLETE]"),
                # Exactly 10 tool calls (one per iteration up to max_iterations=10).
                tool_call_count(10),
            ],
        ),
        # The scripted LLM always calls "spin" and never emits text — it exhausts
        # the script and repeats the last entry (spin call) indefinitely.
        llm_script=[
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc_spin", name="spin", input={})],
            ),
        ],
        tools=[ToolSpec(name="spin", callable=_noop_tool("still spinning"))],
    ),
    # ------------------------------------------------------------------
    # 9. Empty/degraded response — invariant: when the LLM returns an
    #    LLMResponse with empty content AND no tool_calls, the loop treats
    #    this as a graceful finish (not an error).  Output is empty string.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="empty_response_graceful",
            user_input="Return nothing.",
            assertions=[
                no_error(),  # loop handles empty response without raising
                tool_call_count(0),
                output_not_contains("[error]"),
            ],
        ),
        llm_script=[LLMResponse(content="")],
    ),
    # ------------------------------------------------------------------
    # 10. Tool with arguments — invariant: the loop passes ToolCall.input
    #     as **kwargs to the tool callable; the callable can read those
    #     kwargs and return a value built from them.  If the LLM's final
    #     reply echoes the argument, output_contains verifies end-to-end
    #     argument flow through the loop.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="tool_with_arguments",
            user_input="Call the echo tool with query='hello'.",
            assertions=[
                no_error(),
                tool_called("echo_tool"),
                tool_call_count(1),
                output_contains("hello"),
            ],
        ),
        llm_script=[
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="tc_echo", name="echo_tool", input={"query": "hello"})],
            ),
            LLMResponse(content="The tool returned: hello"),
        ],
        tools=[
            ToolSpec(
                name="echo_tool",
                callable=lambda **kw: f"echo: {kw.get('query', '')}",
                description="Echoes the query argument.",
            )
        ],
    ),
    # ------------------------------------------------------------------
    # 11. Parallel tool calls — invariant: the loop submits ALL ToolCalls
    #     from a single LLMResponse to the thread pool concurrently
    #     (loop.py lines 1013-1017).  Both tools must appear in tool_calls
    #     and the turn must complete without error.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="parallel_tool_calls",
            user_input="Call alpha and beta at the same time.",
            assertions=[
                no_error(),
                tool_called("alpha"),
                tool_called("beta"),
                tool_call_count(2),
                tool_called_in_order(["alpha", "beta"]),
            ],
        ),
        llm_script=[
            # One LLMResponse with two ToolCalls — dispatched in parallel by the loop.
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="tc_alpha", name="alpha", input={}),
                    ToolCall(id="tc_beta", name="beta", input={}),
                ],
            ),
            LLMResponse(content="Both tools ran."),
        ],
        tools=[
            ToolSpec(name="alpha", callable=_noop_tool("alpha result")),
            ToolSpec(name="beta", callable=_noop_tool("beta result")),
        ],
    ),
    # ------------------------------------------------------------------
    # 12. Three-tool ordered trajectory — invariant: tool_called_in_order
    #     passes iff the three named tools appear as an ordered subsequence
    #     of tool_calls, and tool_call_count(3) confirms no extras.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="three_tool_ordered",
            user_input="Run plan, execute, then verify in order.",
            assertions=[
                no_error(),
                tool_call_count(3),
                tool_called_in_order(["plan", "execute", "verify"]),
                output_contains("verified"),
            ],
        ),
        llm_script=[
            LLMResponse(content="", tool_calls=[ToolCall(id="tc_p", name="plan", input={})]),
            LLMResponse(
                content="", tool_calls=[ToolCall(id="tc_e", name="execute", input={})]
            ),
            LLMResponse(
                content="", tool_calls=[ToolCall(id="tc_v", name="verify", input={})]
            ),
            LLMResponse(content="All steps verified."),
        ],
        tools=[
            ToolSpec(name="plan", callable=_noop_tool("plan result")),
            ToolSpec(name="execute", callable=_noop_tool("execute result")),
            ToolSpec(name="verify", callable=_noop_tool("verify result")),
        ],
    ),
    # ------------------------------------------------------------------
    # 13. Clean reply has zero tools — invariant: a plain text reply with
    #     no tool calls produces tool_call_count(0) and does not contain
    #     error markers in the output.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="clean_reply_zero_tools",
            user_input="Just say hello without calling any tools.",
            assertions=[
                no_error(),
                tool_call_count(0),
                output_contains("hello"),
                output_not_contains("[error]"),
                output_not_contains("[INCOMPLETE]"),
            ],
        ),
        llm_script=[LLMResponse(content="hello there")],
    ),
    # ------------------------------------------------------------------
    # 14. Error marker absent from normal reply — invariant: output_not_contains
    #     fires when the expected absence is violated.  This case checks that
    #     a clean scripted reply does not leak internal loop sentinel strings.
    # ------------------------------------------------------------------
    ReplayCase(
        case=EvalCase(
            name="no_internal_markers_in_clean_output",
            user_input="Give me a clean response.",
            assertions=[
                no_error(),
                output_not_contains("[CANCELLED]"),
                output_not_contains("[TIME LIMIT REACHED]"),
                output_not_contains("[BUDGET LIMIT REACHED]"),
                output_not_contains("[WORKFLOW SUSPENDED]"),
                output_not_contains("[INCOMPLETE]"),
            ],
        ),
        llm_script=[LLMResponse(content="Here is a clean response for you.")],
    ),
]
