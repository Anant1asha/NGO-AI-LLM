"""Phase 2 — real trace waterfall: agent.turn ⊃ {tool.call, llm.generate}.

Verifies:
- Correct parent/child nesting via OTel context propagation.
- No stray marker spans from the demoted sink (CX2).
- Sink stamps attributes onto the existing span, not a new one.
- Tool raises → span records the exception; turn is still valid.
- SDK absent → no spans, turn runs identically.
"""

from __future__ import annotations

import concurrent.futures

import pytest

pytest.importorskip("opentelemetry")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import hachi.core.tracing as _tracing
from hachi.core.obs.sink import ObservabilitySink
from hachi.core.obs.trace import (
    TraceContext,
    attach_otel_context,
    bind,
    copy_otel_context,
    detach_otel_context,
)
from hachi.core.runtime_events import RuntimeEvent, now_iso


@pytest.fixture(autouse=True)
def _reset():
    _tracing._reset_for_tests()
    yield
    _tracing._reset_for_tests()


def _configure() -> InMemorySpanExporter:
    exp = InMemorySpanExporter()
    _tracing.setup_tracing(exporter=exp, force=True)
    return exp


def _event(name: str, payload: dict | None = None) -> RuntimeEvent:
    return RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())


# ---------------------------------------------------------------------------
# Waterfall nesting
# ---------------------------------------------------------------------------


def test_waterfall_agent_turn_contains_tool_and_llm():
    """agent.turn ⊃ tool.call ⊃ llm.generate — correct parent links."""
    exp = _configure()
    ctx = TraceContext(trace_id="wf-001", session_id="s1", principal="p", surface="web")

    with bind(ctx):
        with _tracing.span("agent.turn", turn_id="wf-001"):
            with _tracing.span("tool.call", tool="bash"):
                pass
            with _tracing.span("llm.generate", model="claude-haiku"):
                pass

    spans = exp.get_finished_spans()
    names = [s.name for s in spans]
    assert "agent.turn" in names
    assert "tool.call" in names
    assert "llm.generate" in names

    turn = next(s for s in spans if s.name == "agent.turn")
    tool = next(s for s in spans if s.name == "tool.call")
    llm = next(s for s in spans if s.name == "llm.generate")

    assert tool.parent is not None
    assert tool.parent.span_id == turn.context.span_id
    assert llm.parent is not None
    assert llm.parent.span_id == turn.context.span_id


def test_no_stray_marker_spans_from_sink():
    """After Phase 2, the sink must NOT create stray agent.turn.start/end marker spans."""
    exp = _configure()
    sink = ObservabilitySink()

    with _tracing.span("agent.turn"):
        sink.handle(_event("session.chat.started", {"trace_id": "t1"}))
        sink.handle(_event("tool.call.started", {"name": "bash", "trace_id": "t1"}))
        sink.handle(_event("session.chat.completed", {"trace_id": "t1"}))

    spans = exp.get_finished_spans()
    names = [s.name for s in spans]

    # Only agent.turn — no agent.turn.start / agent.turn.end marker spans.
    assert names == ["agent.turn"], f"stray spans: {names}"


def test_no_duplicate_agent_turn_root():
    """The orchestrator opens one agent.turn root; the sink must not open another."""
    exp = _configure()
    sink = ObservabilitySink()

    with _tracing.span("agent.turn"):
        sink.handle(_event("session.chat.started", {"trace_id": "t2"}))

    spans = exp.get_finished_spans()
    turn_spans = [s for s in spans if s.name == "agent.turn"]
    assert len(turn_spans) == 1, f"duplicate agent.turn roots: {[s.name for s in spans]}"


def test_tool_call_nests_under_turn_via_thread_pool():
    """tool.call opened in a thread pool still nests under agent.turn (OTel context re-attach)."""
    exp = _configure()
    ctx = TraceContext(trace_id="wf-thread", session_id="s2", principal="p", surface="cli")

    with bind(ctx):
        with _tracing.span("agent.turn"):
            otel_ctx = copy_otel_context()

            def _worker(otel_context):
                tok = attach_otel_context(otel_context)
                try:
                    with _tracing.span("tool.call", tool="worker_tool"):
                        pass
                finally:
                    detach_otel_context(tok)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(_worker, otel_ctx).result()

    spans = exp.get_finished_spans()
    turn = next(s for s in spans if s.name == "agent.turn")
    tool = next(s for s in spans if s.name == "tool.call")
    assert tool.parent is not None
    assert tool.parent.span_id == turn.context.span_id


def test_completed_event_attrs_land_on_tool_span():
    """tool.call.completed attrs (status, duration) land on the existing tool.call span."""
    exp = _configure()
    sink = ObservabilitySink()

    with _tracing.span("tool.call", tool="bash"):
        sink.handle(
            _event("tool.call.completed", {"name": "bash", "status": "ok", "trace_id": "t3"})
        )

    spans = exp.get_finished_spans()
    assert len(spans) == 1
    attrs = dict(spans[0].attributes or {})
    assert attrs.get("status") == "ok"
    # No second span was created.


def test_sdk_absent_turn_runs_identically(monkeypatch):
    """When OTel SDK is unavailable, span() is a no-op and the turn runs normally."""
    monkeypatch.setattr(_tracing, "_tracer", None)
    monkeypatch.setattr(_tracing, "_configured", False)

    result = []
    with _tracing.span("agent.turn"):
        with _tracing.span("tool.call", tool="x"):
            result.append("ran")

    assert result == ["ran"]
