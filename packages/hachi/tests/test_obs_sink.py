"""Tests for core/obs/sink.py — ObservabilitySink.

Phase 2 contract change (CX2, intentional — see docs/DECISIONS.md):
The sink was demoted from a span *emitter* to an attribute *stamper*.
It no longer creates new spans; instead it stamps attributes + span-events
onto the *currently active* span.  The three tests below that previously
asserted marker-span creation have been rewritten to assert the new contract.
This is an intended contract change, not a weakened test.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,  # noqa: E402
)

import hachi.core.tracing as _tracing  # noqa: E402
from hachi.core.obs.sink import ObservabilitySink  # noqa: E402
from hachi.core.runtime_events import RuntimeEvent, now_iso  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    _tracing._reset_for_tests()
    yield
    _tracing._reset_for_tests()


def _make_event(name: str, payload: dict | None = None) -> RuntimeEvent:
    return RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())


def _configure() -> InMemorySpanExporter:
    exp = InMemorySpanExporter()
    _tracing.setup_tracing(exporter=exp, force=True)
    return exp


# ---------------------------------------------------------------------------
# Phase 2 contract: sink stamps attributes onto the current span, does NOT
# create new spans.  The three tests below replace the old marker-span tests.
# ---------------------------------------------------------------------------


def test_sink_stamps_correlation_attrs_on_current_span():
    """NEW (Phase 2): sink stamps hachi.trace_id onto the *active* span — no new span created."""
    exp = _configure()
    sink = ObservabilitySink()
    event = _make_event("tool.call.started", {"name": "bash", "trace_id": "t1", "session_id": "s1"})

    with _tracing.span("tool.call", tool="bash") as _:
        sink.handle(event)

    spans = exp.get_finished_spans()
    # Still exactly one span — no extra marker span was created.
    assert len(spans) == 1
    assert spans[0].name == "tool.call"
    attrs = dict(spans[0].attributes or {})
    assert attrs.get("hachi.trace_id") == "t1" or attrs.get("hachi.turn_id") == "t1"


def test_sink_carries_correlation_attributes_on_active_span():
    """NEW (Phase 2): correlation ids land on the active span, not a throwaway span."""
    exp = _configure()
    sink = ObservabilitySink()
    event = _make_event(
        "tool.call.started",
        {"name": "read_file", "trace_id": "trace-xyz", "session_id": "ses-abc"},
    )

    with _tracing.span("tool.call"):
        sink.handle(event)

    spans = exp.get_finished_spans()
    assert len(spans) == 1, "sink must not create extra spans"
    attrs = dict(spans[0].attributes or {})
    assert attrs.get("hachi.trace_id") == "trace-xyz"
    assert attrs.get("hachi.session_id") == "ses-abc"


def test_sink_noop_when_tracing_off():
    """Sink is a no-op when tracing is not configured — no error, no spans."""
    assert not _tracing.is_active()
    sink = ObservabilitySink()
    sink.handle(_make_event("tool.call.started", {"name": "bash"}))
    # No assertion needed — we just verify it doesn't raise.


def test_sink_ignores_unmapped_events():
    """Events not in _SPAN_EVENTS are silently dropped."""
    exp = _configure()
    sink = ObservabilitySink()
    sink.handle(_make_event("text.stream.delta", {"text": "hello"}))
    assert exp.get_finished_spans() == ()


def test_sink_does_not_block():
    """The sink handle() call must return quickly (does not sleep or block)."""
    import time

    _configure()
    sink = ObservabilitySink()
    event = _make_event("tool.call.started", {"name": "x"})
    start = time.monotonic()
    sink.handle(event)
    elapsed = time.monotonic() - start
    # Should return in well under 1 second (conservative bound; normally <1ms).
    assert elapsed < 1.0


def test_sink_does_not_raise_on_exception(monkeypatch):
    """An internal error in _handle_safe is caught and logged — never propagated."""
    _configure()
    sink = ObservabilitySink()

    # Force _handle_safe to raise.
    def _bad(event):  # type: ignore[misc]
        raise RuntimeError("injected error")

    monkeypatch.setattr(sink, "_handle_safe", _bad)
    sink.handle(_make_event("tool.call.started"))  # must not raise


# ---------------------------------------------------------------------------
# Secret redaction guard
# ---------------------------------------------------------------------------


def test_sink_does_not_leak_secrets():
    """NEW (Phase 2): denied payload keys never reach span attributes (same intent, new mechanism).

    The sink now stamps attributes onto the *active* span.  Denied fields
    (prompt_preview, user_input, authorization, *_body, etc.) must not appear
    in any attribute on the active span, just as they could not reach the old
    marker spans.
    """
    exp = _configure()
    sink = ObservabilitySink()

    event = _make_event(
        "tool.call.started",
        {
            "name": "post_to_slack",
            "trace_id": "t99",
            "prompt_preview": "TOPSECRET",
            "authorization": "Bearer TOPSECRET",
        },
    )
    with _tracing.span("tool.call"):
        sink.handle(event)

    spans = exp.get_finished_spans()
    assert spans, "expected a span"
    all_attr_values = " ".join(str(v) for v in (spans[0].attributes or {}).values())
    assert "TOPSECRET" not in all_attr_values


# ---------------------------------------------------------------------------
# id stamping via _event helper
# ---------------------------------------------------------------------------


def test_event_stamped_with_trace_id_when_context_active():
    """_event() stamps trace_id/session_id from the active TraceContext."""
    from hachi.core.obs.trace import TraceContext, bind
    from hachi.core.runtime_events import _event

    ctx = TraceContext(trace_id="tr-stamp", session_id="ses-stamp", principal="p", surface="cli")
    with bind(ctx):
        ev = _event("session.chat.started", {"turn_id": "t1"})

    assert ev.payload.get("trace_id") == "tr-stamp"
    assert ev.payload.get("session_id") == "ses-stamp"


def test_event_not_stamped_without_context():
    """_event() does not inject ids when no TraceContext is active."""
    from hachi.core.runtime_events import _event

    ev = _event("session.chat.started", {"turn_id": "t1"})
    assert "trace_id" not in ev.payload
    assert "session_id" not in ev.payload


def test_event_payload_does_not_override_explicit_ids():
    """Explicit trace_id in the payload takes precedence over the injected one."""
    from hachi.core.obs.trace import TraceContext, bind
    from hachi.core.runtime_events import _event

    ctx = TraceContext(trace_id="injected", session_id="injected-ses", principal="p", surface="cli")
    with bind(ctx):
        ev = _event("x", {"trace_id": "explicit", "session_id": "explicit-ses"})

    assert ev.payload["trace_id"] == "explicit"
    assert ev.payload["session_id"] == "explicit-ses"
