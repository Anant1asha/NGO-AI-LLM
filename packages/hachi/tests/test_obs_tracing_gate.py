"""GATE-TRACE — proves tool.call spans nest UNDER agent.turn (parent/child).

This is the headline gap fixed in Slice 2.3: the OTel context is captured on the
turn thread before submitting tasks to the ThreadPoolExecutor so tool.call spans
produced inside the pool carry the agent.turn span as their parent.

Uses the OTel in-memory exporter and hachi.core.tracing._reset_for_tests().
"""

from __future__ import annotations

import concurrent.futures
import threading
from typing import Any

import pytest

pytest.importorskip("opentelemetry")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,  # noqa: E402
)

import hachi.core.tracing as _tracing  # noqa: E402
from hachi.core.obs.trace import (  # noqa: E402
    TraceContext,
    attach_otel_context,
    bind,
    copy_otel_context,
    detach_otel_context,
)


@pytest.fixture(autouse=True)
def _reset_tracing():
    """Reset tracing state before and after each test."""
    _tracing._reset_for_tests()
    yield
    _tracing._reset_for_tests()


def _configure_in_memory() -> InMemorySpanExporter:
    """Wire an in-memory exporter to the hachi tracer and return it."""
    exporter = InMemorySpanExporter()
    _tracing.setup_tracing(exporter=exporter, force=True)
    return exporter


# ---------------------------------------------------------------------------
# GATE-TRACE: the critical parent/child nesting test
# ---------------------------------------------------------------------------


def test_gate_trace_tool_call_nests_under_agent_turn():
    """GATE-TRACE: tool.call span is a CHILD of agent.turn (parent_span_id matches).

    Simulates the exact pattern in loop.py:
    1. Open agent.turn root span.
    2. Capture OTel context + TraceContext on the turn thread.
    3. Submit a worker to the thread pool that re-attaches the context and opens
       a tool.call span.
    4. Assert parent_span_id of tool.call == span_id of agent.turn.
    """
    exporter = _configure_in_memory()
    ctx = TraceContext(
        trace_id="gate-trace-001",
        session_id="ses-001",
        principal="p",
        surface="cli",
    )

    # Simulate: open the agent.turn root span and capture context while inside it.
    with bind(ctx):
        with _tracing.span("agent.turn", turn_id="gate-trace-001", session_id="ses-001"):
            otel_ctx = copy_otel_context()
            trace_ctx = ctx

            # Simulate ThreadPoolExecutor worker.
            def _worker(otel_context: Any, trace_context: TraceContext) -> None:
                token = attach_otel_context(otel_context)
                try:
                    with bind(trace_context):
                        with _tracing.span("tool.call", tool="test_tool"):
                            pass  # represent tool execution
                finally:
                    detach_otel_context(token)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_worker, otel_ctx, trace_ctx)
                fut.result()  # wait for completion

    finished = exporter.get_finished_spans()
    names = [s.name for s in finished]
    assert "agent.turn" in names, f"agent.turn span not found in {names}"
    assert "tool.call" in names, f"tool.call span not found in {names}"

    turn_span = next(s for s in finished if s.name == "agent.turn")
    tool_span = next(s for s in finished if s.name == "tool.call")

    # THE CRITICAL ASSERTION: tool.call's parent == agent.turn
    assert tool_span.parent is not None, "tool.call has no parent — context propagation failed"
    assert tool_span.parent.span_id == turn_span.context.span_id, (
        f"tool.call parent span_id {tool_span.parent.span_id!r} != "
        f"agent.turn span_id {turn_span.context.span_id!r}"
    )


def test_llm_generate_span_is_child_of_agent_turn():
    """llm.generate spans (opened inline on the turn thread) are also children."""
    exporter = _configure_in_memory()
    ctx = TraceContext(
        trace_id="gate-trace-002",
        session_id="ses-002",
        principal="p",
        surface="web",
    )
    with bind(ctx):
        with _tracing.span("agent.turn", turn_id="gate-trace-002"):
            with _tracing.span("llm.generate", model="claude-haiku-4-5"):
                pass

    finished = exporter.get_finished_spans()
    names = [s.name for s in finished]
    assert "agent.turn" in names
    assert "llm.generate" in names

    turn_span = next(s for s in finished if s.name == "agent.turn")
    llm_span = next(s for s in finished if s.name == "llm.generate")

    assert llm_span.parent is not None
    assert llm_span.parent.span_id == turn_span.context.span_id


def test_span_attributes_on_llm_generate():
    """add_span_attributes injects cost/token attributes onto the current span."""
    from hachi.core.tracing import add_span_attributes

    exporter = _configure_in_memory()
    with _tracing.span("llm.generate", model="claude-haiku-4-5"):
        add_span_attributes(
            llm_input_tokens=100,
            llm_output_tokens=50,
            llm_cache_read_tokens=200,
            llm_cache_creation_tokens=0,
            llm_model="claude-haiku-4-5",
        )

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    attrs = finished[0].attributes or {}
    assert attrs.get("llm_input_tokens") == 100
    assert attrs.get("llm_output_tokens") == 50
    assert attrs.get("llm_model") == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# No-op safety
# ---------------------------------------------------------------------------


def test_spans_are_noop_when_tracing_not_configured():
    """span() is a complete no-op when tracing is off — no import errors, no overhead."""
    assert not _tracing.is_active()
    # Must not raise.
    with _tracing.span("agent.turn"):
        with _tracing.span("tool.call", tool="x"):
            pass


def test_add_span_attributes_noop_when_tracing_off():
    from hachi.core.tracing import add_span_attributes

    # Must not raise.
    add_span_attributes(some_attr="value")


# ---------------------------------------------------------------------------
# Context propagation helpers (unit tests)
# ---------------------------------------------------------------------------


def test_copy_attach_detach_otel_context():
    """copy/attach/detach round-trip does not raise."""
    # Even without tracing configured the helpers must be safe.
    ctx = copy_otel_context()
    token = attach_otel_context(ctx)
    detach_otel_context(token)


def test_copy_attach_with_active_span():
    """Captured context carries the active span for later re-attachment."""
    exporter = _configure_in_memory()
    captured_ctx: Any = None

    with _tracing.span("root.span"):
        captured_ctx = copy_otel_context()

    def _worker() -> None:
        tok = attach_otel_context(captured_ctx)
        try:
            with _tracing.span("child.span"):
                pass
        finally:
            detach_otel_context(tok)

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    finished = exporter.get_finished_spans()
    root = next((s for s in finished if s.name == "root.span"), None)
    child = next((s for s in finished if s.name == "child.span"), None)
    assert root is not None
    assert child is not None
    # Child's parent must be the root span.
    assert child.parent is not None
    assert child.parent.span_id == root.context.span_id
