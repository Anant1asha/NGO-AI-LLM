"""P2-06 — E2E loop harness.

Scripted fake LLM drives ExecutionLoop + real ToolRegistry through multi-turn
scenarios. This is the regression net for all loop-adjacent features.

Scenarios covered here:
  - Multi-turn tool call → result → text finish
  - Multiple sequential tool calls across iterations
  - Batch tool calls (multiple tool_use in one response)
  - Tool error → is_error=True in history; loop continues
  - Malformed/empty LLM response exits gracefully
  - Compaction event fires after skill switch
  - on_event fires in correct order (thinking, tool_call, tool_result, text_delta)
  - Iteration limit returns [INCOMPLETE], not raises (P1-04)
  - Session budget stop (session-level cap)

Stream-cancel (P2-01b) is added when streaming lands.
Concurrent-chat regression lives in test_session_concurrency.py (P1-01).
"""

from __future__ import annotations

from typing import Any

from hachi.core.llm import LLMResponse, TokenUsage, ToolCall
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.memory import MemoryManager
from hachi.core.sub_agent import SubAgentMemory

# ---------------------------------------------------------------------------
# Harness primitives — reused by all scenarios
# ---------------------------------------------------------------------------

_EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


def _tool(name: str, description: str = "") -> dict[str, Any]:
    return {"name": name, "description": description or name, "input_schema": _EMPTY_SCHEMA}


class ScriptedLLMClient:
    """Fake LLM that returns a predetermined queue of LLMResponse objects.

    The last response is repeated when the queue is exhausted so tests that
    overshoot their expected iteration count fail on assertion, not IndexError.
    """

    model = "scripted-test-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        assert responses, "ScriptedLLMClient requires at least one response"
        self._responses = responses
        self.calls: int = 0
        self.call_kwargs: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> LLMResponse:
        self.call_kwargs.append(kwargs)
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp

    def generate_stream(self, **kwargs: Any):  # type: ignore[return]
        """Single-chunk streaming wrapper around generate() for harness compatibility."""
        response = self.generate(**kwargs)

        def _gen():
            if response.content:
                yield response.content
            return response

        return _gen()


def _make_loop(
    responses: list[LLMResponse],
    registry: ToolRegistry | None = None,
    memory: Any = None,
    on_event: Any = None,
) -> tuple[ExecutionLoop, ScriptedLLMClient]:
    llm = ScriptedLLMClient(responses)
    reg = registry if registry is not None else ToolRegistry()
    mem = memory if memory is not None else SubAgentMemory()
    loop = ExecutionLoop(
        llm_client=llm,
        registry=reg,
        memory=mem,
        base_system_prompt="test-system-prompt",
        on_event=on_event,
    )
    return loop, llm


# ---------------------------------------------------------------------------
# Multi-turn: tool call → result → text finish
# ---------------------------------------------------------------------------


def test_single_tool_call_then_text_finish() -> None:
    """LLM calls one tool, receives the result, then returns text — basic happy path."""
    reg = ToolRegistry()
    reg.register(_tool("echo"), lambda text="": f"echoed:{text}")

    responses = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="t1", name="echo", input={"text": "hi"})],
        ),
        LLMResponse(content="I echoed hi for you."),
    ]
    loop, llm = _make_loop(responses, registry=reg)
    loop.add_user_message("echo hi")

    result = loop.run(max_iterations=5)

    assert result == "I echoed hi for you."
    assert llm.calls == 2

    # History must contain: initial user, assistant+tool_use, user+tool_result, assistant+text
    history = loop.memory.history
    roles = [m.role for m in history]
    assert roles.count("user") >= 2
    assert roles.count("assistant") == 2


def test_two_sequential_tool_calls() -> None:
    """Two separate tool calls across two iterations — history stays valid."""
    reg = ToolRegistry()
    reg.register(_tool("get_a"), lambda: "value_a")
    reg.register(_tool("get_b"), lambda: "value_b")

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="get_a", input={})]),
        LLMResponse(content="", tool_calls=[ToolCall(id="t2", name="get_b", input={})]),
        LLMResponse(content="Got both values."),
    ]
    loop, llm = _make_loop(responses, registry=reg)
    loop.add_user_message("get a and b")

    result = loop.run(max_iterations=5)

    assert result == "Got both values."
    assert llm.calls == 3


# ---------------------------------------------------------------------------
# Batch tool calls — all in one response
# ---------------------------------------------------------------------------


def test_batch_tool_calls_all_get_paired_results() -> None:
    """All tool_use blocks in one response must each get a tool_result."""
    reg = ToolRegistry()
    reg.register(_tool("tool_a"), lambda: "a_result")
    reg.register(_tool("tool_b"), lambda: "b_result")
    reg.register(_tool("tool_c"), lambda: "c_result")

    responses = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(id="t1", name="tool_a", input={}),
                ToolCall(id="t2", name="tool_b", input={}),
                ToolCall(id="t3", name="tool_c", input={}),
            ],
        ),
        LLMResponse(content="All three done."),
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.add_user_message("run all")

    result = loop.run(max_iterations=3)

    assert result == "All three done."

    tool_result_msgs = [
        m for m in loop.memory.history if m.role == "user" and isinstance(m.content, list)
    ]
    assert tool_result_msgs, "no tool_results message in history"
    answered_ids = {
        b["tool_use_id"]
        for b in tool_result_msgs[-1].content
        if isinstance(b, dict) and b.get("type") == "tool_result"
    }
    assert {"t1", "t2", "t3"} == answered_ids, (
        f"not all tool_use blocks got a result; got: {answered_ids}"
    )


# ---------------------------------------------------------------------------
# Tool error → is_error in history; loop continues
# ---------------------------------------------------------------------------


def test_tool_error_sets_is_error_in_history() -> None:
    """An exception in a tool must produce a tool_result with is_error=True."""
    reg = ToolRegistry()
    reg.register(_tool("bad_tool"), lambda **_kw: (_ for _ in ()).throw(ValueError("boom")))

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="bad_tool", input={})]),
        LLMResponse(content="I saw the error."),
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.add_user_message("run bad tool")

    result = loop.run(max_iterations=3)

    assert result == "I saw the error."

    tool_result_msgs = [
        m for m in loop.memory.history if m.role == "user" and isinstance(m.content, list)
    ]
    assert tool_result_msgs
    result_block = next(
        (
            b
            for b in tool_result_msgs[-1].content
            if isinstance(b, dict) and b.get("tool_use_id") == "t1"
        ),
        None,
    )
    assert result_block is not None, "no tool_result block for t1"
    assert result_block.get("is_error") is True, "is_error must be True for a failed tool"
    assert "boom" in str(result_block.get("content", ""))


def test_tool_error_does_not_abort_loop() -> None:
    """A tool error is captured; loop continues to next iteration."""
    reg = ToolRegistry()
    call_count: dict[str, int] = {"n": 0}

    def _fail_first(**_kw: Any) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("first-time failure")
        return "succeeded"

    reg.register(_tool("sometimes_bad"), _fail_first)

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="sometimes_bad", input={})]),
        LLMResponse(content="", tool_calls=[ToolCall(id="t2", name="sometimes_bad", input={})]),
        LLMResponse(content="Done after recovery."),
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.add_user_message("use flaky tool")

    result = loop.run(max_iterations=5)
    assert result == "Done after recovery."
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# BB-54 — a ToolCall with a parse_error (malformed/truncated tool-arg JSON)
# must FAIL that specific tool call (is_error=True) instead of silently
# executing the underlying tool with empty/wrong arguments.
# ---------------------------------------------------------------------------


def test_tool_call_with_parse_error_fails_instead_of_running_with_empty_input() -> None:
    """A ToolCall carrying parse_error must never reach the tool function."""
    reg = ToolRegistry()
    calls: list[dict[str, Any]] = []
    reg.register(_tool("transfer_funds"), lambda **kw: calls.append(kw) or "transferred")

    responses = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="t1",
                    name="transfer_funds",
                    input={},
                    parse_error="truncated JSON: unterminated object",
                )
            ],
        ),
        LLMResponse(content="I saw the error."),
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.add_user_message("transfer money")

    result = loop.run(max_iterations=3)

    assert result == "I saw the error."
    # The dangerous behaviour this guards against: executing transfer_funds
    # with empty/wrong arguments instead of failing loudly.
    assert calls == [], "tool must NOT execute when the call carries a parse_error"

    tool_result_msgs = [
        m for m in loop.memory.history if m.role == "user" and isinstance(m.content, list)
    ]
    result_block = next(
        (
            b
            for b in tool_result_msgs[-1].content
            if isinstance(b, dict) and b.get("tool_use_id") == "t1"
        ),
        None,
    )
    assert result_block is not None, "no tool_result block for t1"
    assert result_block.get("is_error") is True, "parse_error must surface as is_error=True"


# ---------------------------------------------------------------------------
# Malformed / empty responses
# ---------------------------------------------------------------------------


def test_empty_response_exits_gracefully() -> None:
    """An empty LLMResponse (no text, no tool_calls) exits cleanly, returns empty string."""
    loop, _ = _make_loop([LLMResponse(content="", tool_calls=[])])
    loop.add_user_message("do something")

    result = loop.run(max_iterations=3)
    assert result == ""


def test_text_only_response_returns_immediately() -> None:
    """A text-only response with no tool calls exits on the first iteration."""
    loop, llm = _make_loop([LLMResponse(content="Simple answer.")])
    loop.add_user_message("hello")

    result = loop.run(max_iterations=10)
    assert result == "Simple answer."
    assert llm.calls == 1


# ---------------------------------------------------------------------------
# Compaction event fires after skill switch
# ---------------------------------------------------------------------------


def test_compaction_event_fires_on_skill_switch() -> None:
    """load_skill triggers compaction when switching from one named skill to another.

    Compaction requires:
    1. A prior named skill (active_skill != None)
    2. Enough prior history to compact (at least one real user message before the new one)

    We seed both: set active_skill='prior_skill' and populate history with a prior
    turn, then call load_skill('weather'). The next iteration must emit 'compaction'.
    """
    memory = MemoryManager(max_active_messages=200)
    # Seed a prior skill and its history so compaction has something to compact
    memory._active_skill = "prior_skill"  # simulate a skill already loaded
    from hachi.core.llm import Message as Msg

    memory._history = [
        Msg(role="user", content="previous user message"),
        Msg(role="assistant", content="previous assistant reply"),
    ]

    events: list[tuple[str, dict[str, Any]]] = []

    reg = ToolRegistry()
    reg.register(_tool("load_skill"), lambda name="": f"loaded {name}")

    responses = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="t1", name="load_skill", input={"name": "weather"})],
        ),
        LLMResponse(content="Switched to weather."),
    ]
    loop, _ = _make_loop(
        responses,
        registry=reg,
        memory=memory,
        on_event=lambda name, data: events.append((name, data)),
    )
    loop.add_user_message("switch to weather")

    result = loop.run(max_iterations=3)

    assert "Switched to weather." in result
    compaction_events = [e for e in events if e[0] == "compaction"]
    assert compaction_events, f"Expected compaction event; got: {[e[0] for e in events]}"


# ---------------------------------------------------------------------------
# Event emission order
# ---------------------------------------------------------------------------


def test_event_order_thinking_tool_result_text() -> None:
    """on_event fires in the expected order across a tool-call turn."""
    reg = ToolRegistry()
    reg.register(_tool("echo"), lambda text="": f"echo:{text}")

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="echo", input={"text": "x"})]),
        LLMResponse(content="done"),
    ]
    event_names: list[str] = []
    loop, _ = _make_loop(
        responses,
        registry=reg,
        on_event=lambda name, _data: event_names.append(name),
    )
    loop.add_user_message("go")

    loop.run(max_iterations=3)

    assert "thinking" in event_names
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    # Streaming emits text_delta per chunk. text_chunk is the non-streaming
    # fallback only, and is suppressed when deltas streamed so delta listeners
    # (TUI transcript, gateway SSE) don't render the reply twice.
    assert "text_delta" in event_names
    assert "text_chunk" not in event_names
    assert event_names.index("thinking") < event_names.index("tool_call")
    assert event_names.index("tool_call") < event_names.index("tool_result")
    assert event_names.index("tool_result") < event_names.index("text_delta")


# ---------------------------------------------------------------------------
# Iteration limit — [INCOMPLETE] not exception (P1-04)
# ---------------------------------------------------------------------------


def test_iteration_limit_returns_incomplete_string() -> None:
    """Loop must return [INCOMPLETE] at the iteration limit, never raise."""
    reg = ToolRegistry()
    reg.register(_tool("noop"), lambda: "ok")

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id=f"t{i}", name="noop", input={})])
        for i in range(20)
    ]
    loop, llm = _make_loop(responses, registry=reg)
    loop.add_user_message("run forever")

    result = loop.run(max_iterations=3)

    assert "[INCOMPLETE]" in result
    assert llm.calls == 3  # stopped exactly at the limit


# ---------------------------------------------------------------------------
# Budget stop — session token cap
# ---------------------------------------------------------------------------


def test_session_token_budget_stops_loop() -> None:
    """A session token cap stops the loop before hitting the iteration limit."""
    from hachi.core.cost import CostTracker

    reg = ToolRegistry()
    reg.register(_tool("noop"), lambda: "ok")
    tracker = CostTracker()

    responses = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{i}", name="noop", input={})],
            usage=TokenUsage(input_tokens=500, output_tokens=500),
        )
        for i in range(20)
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.cost_tracker = tracker
    loop.max_tokens = 800  # 1 call = 1 000 tokens → stops after the first
    loop.add_user_message("go")

    result = loop.run(max_iterations=20)

    assert "BUDGET LIMIT REACHED" in result


# ---------------------------------------------------------------------------
# Scripted LLM returns tool call result directly to subsequent LLM prompt
# ---------------------------------------------------------------------------


def test_tool_result_reaches_next_llm_call() -> None:
    """The tool result text must appear in the messages sent to the second LLM call."""
    reg = ToolRegistry()
    reg.register(_tool("get_secret"), lambda: "secret_value_42")

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="get_secret", input={})]),
        LLMResponse(content="The secret is out."),
    ]
    loop, llm = _make_loop(responses, registry=reg)
    loop.add_user_message("get the secret")

    loop.run(max_iterations=3)

    assert llm.calls == 2
    second_call_messages = llm.call_kwargs[1].get("messages", [])
    # The second call must contain the tool result in the user message
    all_content = " ".join(str(m.content) for m in second_call_messages)
    assert "secret_value_42" in all_content, (
        "tool result must be present in messages sent to second LLM call"
    )


# ---------------------------------------------------------------------------
# Cooperative cancel (P2-01b)
# ---------------------------------------------------------------------------


def test_cancel_stops_at_iteration_boundary() -> None:
    """cancel() prevents the second LLM call; returns [CANCELLED]."""
    reg = ToolRegistry()
    reg.register(_tool("noop"), lambda: "ok")

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="noop", input={})]),
        LLMResponse(content="Should never be reached."),
    ]
    loop, llm = _make_loop(responses, registry=reg)

    # Monkey-patch generate_stream to set the cancel flag after the first call.
    orig_generate = llm.generate

    def _cancel_after_first(**kwargs: Any) -> LLMResponse:
        resp = orig_generate(**kwargs)
        loop.cancel()  # set flag; loop checks it at the next iteration boundary
        return resp

    llm.generate = _cancel_after_first  # type: ignore[method-assign]

    loop.add_user_message("start")
    result = loop.run(max_iterations=5)

    assert result.startswith("[CANCELLED]"), f"expected [CANCELLED] prefix, got: {result!r}"
    assert llm.calls == 1, f"expected 1 LLM call before cancel, got {llm.calls}"


def test_cancel_leaves_history_well_formed() -> None:
    """After cancel, every tool_use block in history has a matching tool_result."""
    reg = ToolRegistry()
    reg.register(_tool("step"), lambda: "step_result")

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="step", input={})]),
        LLMResponse(content="Would not reach here."),
    ]
    loop, llm = _make_loop(responses, registry=reg)

    orig_generate = llm.generate

    def _cancel_after_first(**kwargs: Any) -> LLMResponse:
        resp = orig_generate(**kwargs)
        loop.cancel()
        return resp

    llm.generate = _cancel_after_first  # type: ignore[method-assign]

    loop.add_user_message("start")
    loop.run(max_iterations=5)

    history = loop.memory.history
    # Collect all tool_use ids and tool_result ids from assistant / user messages.
    tool_use_ids: set[str] = set()
    tool_result_ids: set[str] = set()
    for msg in history:
        if isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        tool_use_ids.add(block["id"])
                    elif block.get("type") == "tool_result":
                        tool_result_ids.add(block.get("tool_use_id", ""))
    assert tool_use_ids == tool_result_ids, (
        f"Unmatched tool_use ids after cancel: "
        f"tool_use={tool_use_ids} tool_result={tool_result_ids}"
    )


def test_cancel_carries_partial_text() -> None:
    """If text was emitted before cancel, it appears after the [CANCELLED] prefix."""
    reg = ToolRegistry()
    reg.register(_tool("noop"), lambda: "ok")

    responses = [
        # First iteration: returns text AND a tool call (mixed response)
        LLMResponse(
            content="partial answer",
            tool_calls=[ToolCall(id="t1", name="noop", input={})],
        ),
        LLMResponse(content="Should not appear."),
    ]
    loop, llm = _make_loop(responses, registry=reg)

    orig_generate = llm.generate

    def _cancel_after_first(**kwargs: Any) -> LLMResponse:
        resp = orig_generate(**kwargs)
        loop.cancel()
        return resp

    llm.generate = _cancel_after_first  # type: ignore[method-assign]

    loop.add_user_message("go")
    result = loop.run(max_iterations=5)

    assert "[CANCELLED]" in result
    assert "partial answer" in result


def test_text_delta_events_emitted_per_chunk() -> None:
    """Each streaming chunk from the LLM emits a separate text_delta event."""
    # Override generate_stream on ScriptedLLMClient to yield multiple chunks.
    loop, llm = _make_loop([LLMResponse(content="hello world")])

    chunks_from_stream = ["hello", " ", "world"]

    def _multi_chunk_stream(**_kwargs: Any):  # type: ignore[return]
        def _gen():
            yield from chunks_from_stream
            return LLMResponse(content="hello world")

        return _gen()

    llm.generate_stream = _multi_chunk_stream  # type: ignore[method-assign]

    delta_events: list[str] = []
    loop.on_event = lambda name, data: (  # type: ignore[assignment]
        delta_events.append(data["text"]) if name == "text_delta" else None
    )

    loop.add_user_message("hi")
    loop.run(max_iterations=3)

    assert delta_events == ["hello", " ", "world"], (
        f"Expected one text_delta per chunk; got: {delta_events}"
    )


def test_text_chunk_suppressed_when_streaming() -> None:
    """When deltas stream, the full-content text_chunk must NOT also fire.

    Regression: the loop used to emit both the per-chunk text_delta events AND a
    final full text_chunk. Both canonicalize to text.stream.delta, so the TUI and
    gateway SSE accumulators rendered the reply twice (the full chunk appended on
    top of the already-streamed deltas).
    """
    loop, llm = _make_loop([LLMResponse(content="hello world")])

    def _multi_chunk_stream(**_kwargs: Any):  # type: ignore[return]
        def _gen():
            yield from ["hello", " ", "world"]
            return LLMResponse(content="hello world")

        return _gen()

    llm.generate_stream = _multi_chunk_stream  # type: ignore[method-assign]

    names: list[str] = []
    loop.on_event = lambda name, _data: names.append(name)  # type: ignore[assignment]

    loop.add_user_message("hi")
    loop.run(max_iterations=3)

    assert "text_delta" in names
    assert "text_chunk" not in names, (
        "text_chunk must be suppressed when streaming produced deltas, "
        f"else the reply renders twice; got events: {names}"
    )


def test_text_chunk_emitted_as_non_streaming_fallback() -> None:
    """A client whose stream yields no chunks still surfaces text via text_chunk.

    This is the fallback path the suppression above must preserve: non-delta
    listeners (and the CLI) still receive the model's text exactly once.
    """
    loop, llm = _make_loop([LLMResponse(content="final answer")])

    def _empty_stream(**_kwargs: Any):  # type: ignore[return]
        def _gen():
            if False:  # never yields — non-streaming client shape
                yield ""
            return LLMResponse(content="final answer")

        return _gen()

    llm.generate_stream = _empty_stream  # type: ignore[method-assign]

    chunks: list[str] = []
    loop.on_event = lambda name, data: (  # type: ignore[assignment]
        chunks.append(data["text"]) if name == "text_chunk" else None
    )

    loop.add_user_message("hi")
    loop.run(max_iterations=3)

    assert chunks == ["final answer"], (
        f"Expected exactly one text_chunk in the no-delta fallback; got: {chunks}"
    )


# ---------------------------------------------------------------------------
# Per-turn tool-call record for the interaction_log (AUDIT P0-2)
# ---------------------------------------------------------------------------


def test_last_tool_calls_records_batch_in_order() -> None:
    reg = ToolRegistry()
    reg.register(_tool("tool_a"), lambda: "a")
    reg.register(_tool("tool_b"), lambda: "b")
    responses = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(id="t1", name="tool_a", input={}),
                ToolCall(id="t2", name="tool_b", input={}),
            ],
        ),
        LLMResponse(content="done"),
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.add_user_message("go")
    loop.run(max_iterations=3)
    assert loop.last_tool_calls == ["tool_a", "tool_b"]


def test_last_tool_calls_empty_before_run() -> None:
    loop, _ = _make_loop([LLMResponse(content="hi")])
    assert loop.last_tool_calls == []


def test_last_tool_calls_resets_each_run() -> None:
    reg = ToolRegistry()
    reg.register(_tool("tool_a"), lambda: "a")
    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="tool_a", input={})]),
        LLMResponse(content="done"),
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.add_user_message("go")
    loop.run(max_iterations=3)
    assert loop.last_tool_calls == ["tool_a"]
    # A second run whose responses carry no tool calls must reset the record to empty.
    loop.add_user_message("again")
    loop.run(max_iterations=3)
    assert loop.last_tool_calls == []


def test_last_suspend_records_wait_condition_on_suspend() -> None:
    from hachi.core.loop import SuspendWorkflow

    reg = ToolRegistry()

    def _suspend(**_kw: object) -> str:
        raise SuspendWorkflow("need approval", wait_kind="event", wait_key="email.received:boss")

    reg.register(_tool("core_suspend_workflow"), _suspend)
    responses = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="t1", name="core_suspend_workflow", input={})],
        ),
        LLMResponse(content="unreached"),
    ]
    loop, _ = _make_loop(responses, registry=reg)
    loop.add_user_message("do it")
    result = loop.run(max_iterations=3)
    assert result.startswith("[WORKFLOW SUSPENDED]")
    assert loop.last_suspend is not None
    assert loop.last_suspend.wait_kind == "event"
    assert loop.last_suspend.wait_key == "email.received:boss"


def test_last_suspend_is_none_on_normal_turn() -> None:
    loop, _ = _make_loop([LLMResponse(content="all done")])
    loop.add_user_message("hello")
    loop.run(max_iterations=2)
    assert loop.last_suspend is None
