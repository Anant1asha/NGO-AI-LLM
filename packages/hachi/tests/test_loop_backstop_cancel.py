"""Tests for spend backstops (MR-6/UC-SPEND-001/ADV-013) and mid-turn cancel (UC-CORE-005).

Covers:
1. Wall-clock backstop: loop stops with TIME LIMIT status/event when max_wall_seconds elapsed.
2. Token safety ceiling: loop stops even when max_tokens=0 (no opt-in budget set).
3. cancel() mid-stream: generation stops promptly; partial text preserved; status = user_cancel.
4. cancel() at iteration boundary: distinct user_cancel status (regression guard).
5. Backward-compat: ExecutionLoop constructs fine with the original argument set (no new args).
6. Nudge: budget_nudge event emitted once when no budget is configured.
7. Distinct statuses: timeout vs iteration_limit vs user_cancel are distinguishable.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock

from hachi.core.cost import CostSnapshot, CostTracker
from hachi.core.llm import LLMResponse, TokenUsage, ToolCall
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.sub_agent import SubAgentMemory

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def _tool(name: str) -> dict[str, Any]:
    return {"name": name, "description": name, "input_schema": _EMPTY_SCHEMA}


def _noop_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_tool("noop"), lambda **_kw: "ok")
    return registry


def _tracker_with_tokens(total_tokens: int) -> CostTracker:
    """Return a CostTracker whose snapshot() always reports given token count."""
    tracker = MagicMock(spec=CostTracker)
    tracker.snapshot.return_value = CostSnapshot(
        input_tokens=total_tokens,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        total_tokens=total_tokens,
        estimated_cost_usd=0.0,
        call_count=1,
    )
    return tracker


# ---------------------------------------------------------------------------
# Fake LLM clients
# ---------------------------------------------------------------------------


class _SlowToolLLM:
    """Asks for a noop tool on every call; sleeps `chunk_delay` seconds per chunk."""

    model = "fake-slow"

    def __init__(self, chunk_delay: float = 0.0, n_chunks: int = 3) -> None:
        self.chunk_delay = chunk_delay
        self.n_chunks = n_chunks
        self.calls = 0

    def generate(self, **_kw) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{self.calls}", name="noop", input={})],
        )

    def generate_stream(self, **_kw):  # noqa: ANN201
        """Yield n_chunks text deltas then return a tool-call response."""
        for i in range(self.n_chunks):
            if self.chunk_delay > 0:
                time.sleep(self.chunk_delay)
            yield f"chunk{i}"
        # Final value carries the tool call so the loop keeps iterating.
        self.calls += 1
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id=f"t{self.calls}", name="noop", input={})],
        )


class _FinishLLM:
    """Returns a final text response immediately (no tool calls)."""

    model = "fake-finish"

    def __init__(self, text: str = "done") -> None:
        self.text = text
        self.calls = 0

    def generate(self, **_kw) -> LLMResponse:
        self.calls += 1
        return LLMResponse(content=self.text)

    def generate_stream(self, **_kw):  # noqa: ANN201
        self.calls += 1
        yield self.text
        return LLMResponse(content=self.text)


class _SlowFinishLLM:
    """Yields chunks slowly, then finishes (no tool calls)."""

    model = "fake-slow-finish"

    def __init__(self, chunks: list[str], chunk_delay: float = 0.0) -> None:
        self._chunks = chunks
        self.chunk_delay = chunk_delay

    def generate(self, **_kw) -> LLMResponse:
        return LLMResponse(content="".join(self._chunks))

    def generate_stream(self, **_kw):  # noqa: ANN201
        for ch in self._chunks:
            if self.chunk_delay > 0:
                time.sleep(self.chunk_delay)
            yield ch
        return LLMResponse(content="".join(self._chunks))


class _RunawayTokenLLM:
    """Always asks for a tool call and reports massive token usage each call."""

    model = "fake-runaway"

    def __init__(self, tokens_per_call: int = 1_000_000) -> None:
        self.tokens_per_call = tokens_per_call
        self.calls = 0
        self._tracker: CostTracker | None = None  # injected by test

    def generate(self, **_kw) -> LLMResponse:
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


# ---------------------------------------------------------------------------
# 1. Wall-clock backstop
# ---------------------------------------------------------------------------


def test_wall_clock_backstop_stops_loop() -> None:
    """Loop stops with [TIME LIMIT REACHED] when max_wall_seconds elapses."""
    # Use a tiny timeout (0.05 s) and a LLM that sleeps 0.1 s per chunk.
    llm = _SlowToolLLM(chunk_delay=0.05, n_chunks=5)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        max_wall_seconds=0.05,  # very short — first chunk sleep should trigger it
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=50)
    assert "[TIME LIMIT REACHED]" in result, f"Expected time-limit result, got: {result!r}"
    # The loop should NOT have run 50 full iterations.
    assert llm.calls < 10, f"Loop ran too many LLM calls before stopping: {llm.calls}"


def test_wall_clock_backstop_emits_event() -> None:
    """session_time_limit event is emitted when the wall-clock limit fires."""
    events: list[tuple[str, dict]] = []
    llm = _SlowToolLLM(chunk_delay=0.05, n_chunks=5)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=lambda et, d: events.append((et, d)),
        max_wall_seconds=0.05,
    )
    loop.add_user_message("go")
    loop.run(max_iterations=50)
    time_limit_events = [e for e in events if e[0] == "session.time.limit"]
    assert time_limit_events, "Expected at least one session.time.limit event"
    payload = time_limit_events[0][1]
    assert payload.get("status") == "time_limit"


def test_wall_clock_disabled_when_zero() -> None:
    """max_wall_seconds=0 disables the wall-clock backstop; iteration cap still works."""
    llm = _SlowToolLLM(chunk_delay=0.0, n_chunks=1)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        max_wall_seconds=0.0,  # disabled
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=3)
    # Should hit the iteration limit, NOT the time limit.
    assert "[INCOMPLETE]" in result
    assert "[TIME LIMIT REACHED]" not in result


# ---------------------------------------------------------------------------
# 2. Token safety ceiling
# ---------------------------------------------------------------------------


def test_token_safety_ceiling_fires_with_no_opt_in_budget() -> None:
    """Safety ceiling stops the loop even when max_tokens=0 (opt-in budget not set)."""
    tracker = CostTracker()
    llm = _RunawayTokenLLM(tokens_per_call=500_000)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        cost_tracker=tracker,
        max_tokens=0,  # no opt-in budget
        max_cost_usd=0.0,  # no opt-in cost cap
        max_wall_seconds=0.0,  # disable wall-clock so only ceiling fires
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=50)
    # After 4+ calls (4 × 500k = 2M tokens) the ceiling (2M) should fire.
    assert "[BUDGET LIMIT REACHED]" in result
    assert "safety ceiling" in result.lower() or "ceiling" in result.lower()
    assert llm.calls <= 10, f"Ceiling should fire early, got {llm.calls} calls"


def test_token_safety_ceiling_distinct_from_opt_in_budget(monkeypatch) -> None:
    """The ceiling fires at _TOKEN_SAFETY_CEILING, not at max_tokens."""
    # Patch the ceiling to a small value for a fast test.
    monkeypatch.setattr(ExecutionLoop, "_TOKEN_SAFETY_CEILING", 100)
    tracker = CostTracker()
    llm = _RunawayTokenLLM(tokens_per_call=60)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        cost_tracker=tracker,
        max_tokens=0,  # opt-in budget NOT set
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=50)
    assert "[BUDGET LIMIT REACHED]" in result
    assert "ceiling" in result.lower()


def test_token_safety_ceiling_is_preflight_not_post_hoc(monkeypatch) -> None:
    """S1: the ceiling must be checked pre-flight against the upcoming call's
    worst-case token cost, not only against the already-recorded snapshot.

    With ceiling=100 and a single call reporting 90 tokens, a post-hoc-only
    check (snapshot >= ceiling) would let a SECOND 90-token call start (90 <
    100), overshooting the ceiling by 80 tokens before it is ever caught. A
    pre-flight check that adds the upcoming call's worst-case tokens (bounded
    by the client's configured `max_tokens` output cap) to the current
    snapshot must refuse to start that second call.
    """
    monkeypatch.setattr(ExecutionLoop, "_TOKEN_SAFETY_CEILING", 100)
    tracker = CostTracker()
    llm = _RunawayTokenLLM(tokens_per_call=90)
    llm.max_tokens = 50  # worst-case output tokens for the NEXT call
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        cost_tracker=tracker,
        max_tokens=0,  # opt-in budget NOT set
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=50)
    assert "[BUDGET LIMIT REACHED]" in result
    assert "ceiling" in result.lower()
    # Pre-flight must stop BEFORE the 2nd call would push cumulative usage to
    # 180 (90 + 90), i.e. it must catch the overrun risk after just 1 call —
    # not let a 2nd 90-token call complete and overshoot to 180 >> 100.
    assert llm.calls <= 1, (
        f"Pre-flight ceiling check should refuse the 2nd call before it starts, "
        f"got {llm.calls} calls (cumulative would overshoot the 100-token ceiling)"
    )


# ---------------------------------------------------------------------------
# 3. cancel() mid-stream
# ---------------------------------------------------------------------------


def test_cancel_mid_stream_stops_generation() -> None:
    """cancel() called mid-stream causes the loop to stop promptly with [CANCELLED]."""
    # A LLM that yields chunks with a small delay so we can cancel mid-stream.
    llm = _SlowFinishLLM(chunks=["hello", " ", "world"], chunk_delay=0.03)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        max_wall_seconds=0.0,  # wall-clock off; test cancel independently
    )
    loop.add_user_message("go")

    result_holder: list[str] = []

    def _run() -> None:
        result_holder.append(loop.run(max_iterations=20))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # Cancel after one chunk can arrive (~10 ms) but before streaming finishes.
    time.sleep(0.015)
    loop.cancel()
    t.join(timeout=5.0)
    assert t.is_alive() is False, "Loop did not finish after cancel()"

    result = result_holder[0] if result_holder else ""
    assert "[CANCELLED]" in result, f"Expected CANCELLED, got: {result!r}"


def test_cancel_mid_stream_preserves_partial_text() -> None:
    """Partial text emitted before cancel() is preserved in the result."""
    chunks = ["alpha", "beta", "gamma"]
    llm = _SlowFinishLLM(chunks=chunks, chunk_delay=0.03)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")

    result_holder: list[str] = []

    def _run() -> None:
        result_holder.append(loop.run(max_iterations=20))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.015)  # let at least the first chunk land
    loop.cancel()
    t.join(timeout=5.0)

    result = result_holder[0] if result_holder else ""
    # The result should contain some partial text (at least the first chunk).
    assert "[CANCELLED]" in result
    # At least one chunk should be present in the partial text.
    assert any(ch in result for ch in chunks), f"No chunk text found in cancel result: {result!r}"


def test_cancel_mid_stream_emits_user_cancel_event() -> None:
    """session_cancelled event emitted on mid-stream cancel has status=user_cancel."""
    events: list[tuple[str, dict]] = []
    llm = _SlowFinishLLM(chunks=["a", "b", "c"], chunk_delay=0.03)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=lambda et, d: events.append((et, d)),
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")

    t = threading.Thread(target=lambda: loop.run(max_iterations=20), daemon=True)
    t.start()
    time.sleep(0.015)
    loop.cancel()
    t.join(timeout=5.0)

    cancel_events = [e for e in events if e[0] == "session_cancelled"]
    assert cancel_events, "Expected session_cancelled event"
    assert cancel_events[0][1].get("status") == "user_cancel"


# ---------------------------------------------------------------------------
# 4. cancel() at iteration boundary
# ---------------------------------------------------------------------------


def test_cancel_at_iteration_boundary() -> None:
    """cancel() set during run() stops the loop with user_cancel status.

    run() clears the cancel event at startup (so a stale cancel from a
    previous run doesn't bleed over), so we must set it *after* run() begins.
    We do this by setting it from the on_event callback when the first
    "thinking" event fires (i.e. we're inside the loop but before the LLM call).
    """
    events: list[tuple[str, dict]] = []

    def _on_event(et: str, d: dict) -> None:
        events.append((et, d))
        # Cancel on the first thinking event (iteration 1, before LLM call).
        if et == "thinking" and d.get("iteration") == 1:
            loop.cancel()

    llm = _SlowToolLLM(chunk_delay=0.0, n_chunks=1)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=_on_event,
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=10)
    # Cancel is set just before the LLM call; the check fires at the TOP of
    # iteration 2 (after the first tool round-trip) or mid-stream. Either way
    # we must see a cancel-flavoured result.
    assert "[CANCELLED]" in result
    cancel_events = [e for e in events if e[0] == "session_cancelled"]
    assert cancel_events
    assert cancel_events[0][1].get("status") == "user_cancel"


# ---------------------------------------------------------------------------
# 5. Backward-compat: old argument set still works
# ---------------------------------------------------------------------------


def test_backward_compat_no_new_args() -> None:
    """ExecutionLoop constructs fine with the original params (no max_wall_seconds)."""
    llm = _FinishLLM("hello")
    loop = ExecutionLoop(
        llm,
        ToolRegistry(),
        SubAgentMemory(),
        base_system_prompt="test",
    )
    loop.add_user_message("hi")
    result = loop.run(max_iterations=3)
    assert result == "hello"


def test_backward_compat_all_original_params() -> None:
    """All original keyword params (cost_tracker, max_cost_usd, etc.) still accepted."""
    tracker = MagicMock(spec=CostTracker)
    tracker.snapshot.return_value = CostSnapshot(
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        total_tokens=0,
        estimated_cost_usd=0.0,
        call_count=0,
    )
    llm = _FinishLLM("done")
    loop = ExecutionLoop(
        llm,
        ToolRegistry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=lambda *a: None,
        skill_engine=None,
        cost_tracker=tracker,
        max_cost_usd=1.0,
        max_tokens=10000,
        max_cost_per_turn=0.1,
        max_tokens_per_turn=500,
        # new param:
        max_wall_seconds=60.0,
    )
    loop.add_user_message("hi")
    result = loop.run(max_iterations=3)
    assert result == "done"


# ---------------------------------------------------------------------------
# 6. Budget nudge
# ---------------------------------------------------------------------------


def test_budget_nudge_emitted_once_when_no_budget() -> None:
    """budget_nudge event fires exactly once when neither max_cost_usd nor max_tokens is set."""
    events: list[tuple[str, dict]] = []
    llm = _FinishLLM("ok")
    loop = ExecutionLoop(
        llm,
        ToolRegistry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=lambda et, d: events.append((et, d)),
        max_cost_usd=0.0,
        max_tokens=0,
    )
    # Two separate runs — nudge should fire only once.
    loop.add_user_message("first")
    loop.run(max_iterations=3)
    loop.add_user_message("second")
    loop.run(max_iterations=3)

    nudge_events = [e for e in events if e[0] == "budget_nudge"]
    assert len(nudge_events) == 1, f"Expected exactly 1 nudge, got {len(nudge_events)}"


def test_budget_nudge_suppressed_when_budget_set() -> None:
    """budget_nudge is NOT emitted when max_cost_usd is configured."""
    events: list[tuple[str, dict]] = []
    llm = _FinishLLM("ok")
    loop = ExecutionLoop(
        llm,
        ToolRegistry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=lambda et, d: events.append((et, d)),
        max_cost_usd=0.50,  # budget is set
        max_tokens=0,
    )
    loop.add_user_message("hi")
    loop.run(max_iterations=3)
    nudge_events = [e for e in events if e[0] == "budget_nudge"]
    assert not nudge_events, "Nudge should be suppressed when a budget is configured"


# ---------------------------------------------------------------------------
# 7. Distinct status / event names for each stop reason
# ---------------------------------------------------------------------------


def test_iteration_limit_status_is_incomplete() -> None:
    """SESSION_ITERATION_LIMIT carries the established P1-04 status='incomplete'.

    The iteration-cap exit stays distinguishable from the new time-limit / cancel /
    safety-ceiling exits by its unique event name (SESSION_ITERATION_LIMIT), not by
    overloading the status string — the P1-04 contract pins that to 'incomplete'.
    """
    from hachi.core.runtime_events import SESSION_ITERATION_LIMIT

    events: list[tuple[str, dict]] = []
    llm = _SlowToolLLM(chunk_delay=0.0, n_chunks=1)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=lambda et, d: events.append((et, d)),
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=2)
    assert "[INCOMPLETE]" in result
    iter_limit_events = [e for e in events if e[0] == SESSION_ITERATION_LIMIT]
    assert iter_limit_events
    assert iter_limit_events[0][1].get("status") == "incomplete"


def test_time_limit_result_prefix() -> None:
    """[TIME LIMIT REACHED] prefix distinguishes timeout from iteration-cap or cancel."""
    llm = _SlowToolLLM(chunk_delay=0.05, n_chunks=5)
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        max_wall_seconds=0.05,
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=50)
    assert result.startswith("[TIME LIMIT REACHED]")
    assert "[INCOMPLETE]" not in result
    assert "[CANCELLED]" not in result


def test_user_cancel_result_prefix() -> None:
    """[CANCELLED] prefix distinguishes user-cancel from timeout or iteration-cap.

    Note: run() clears the cancel event at startup, so cancel must be set
    after run() begins.  We use on_event("thinking") to set it mid-run.
    """

    def _on_event(et: str, d: dict) -> None:
        if et == "thinking":
            loop.cancel()

    llm = _SlowToolLLM(chunk_delay=0.0, n_chunks=1)  # slow enough to be cancelled mid-stream
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        on_event=_on_event,
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=10)
    assert result.startswith("[CANCELLED]")
    assert "[INCOMPLETE]" not in result
    assert "[TIME LIMIT REACHED]" not in result
