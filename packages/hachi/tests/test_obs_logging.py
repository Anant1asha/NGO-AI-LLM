"""Phase 5 — Structured logging: JSON formatter + TraceContextFilter.

Tests that the new formatter and filter produce correlated JSON logs without
touching any call sites.
"""

from __future__ import annotations

import json
import logging

import pytest

pytest.importorskip("opentelemetry")

import hachi.core.tracing as _tracing  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    _tracing._reset_for_tests()
    yield
    _tracing._reset_for_tests()


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------


def test_json_formatter_produces_valid_json(caplog):
    """setup_logging(log_format='json') makes records emit valid JSON."""
    from hachi.core.obs.logging_setup import HachiJsonFormatter

    fmt = HachiJsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = fmt.format(record)
    data = json.loads(output)  # must be valid JSON
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert "ts" in data
    assert "logger" in data


def test_json_formatter_includes_turn_id_when_bound():
    """When a TraceContext is active, turn_id appears in the JSON record."""
    from hachi.core.obs.logging_setup import HachiJsonFormatter
    from hachi.core.obs.trace import TraceContext, bind

    fmt = HachiJsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="inside turn",
        args=(),
        exc_info=None,
    )

    ctx = TraceContext(trace_id="turn-123", session_id="ses-1", principal="p", surface="web")
    with bind(ctx):
        output = fmt.format(record)

    data = json.loads(output)
    assert data.get("turn_id") == "turn-123"
    assert data.get("session_id") == "ses-1"


def test_json_formatter_no_turn_id_outside_context():
    """Outside a TraceContext, turn_id is absent from the JSON record."""
    from hachi.core.obs.logging_setup import HachiJsonFormatter

    fmt = HachiJsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="no context",
        args=(),
        exc_info=None,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert "turn_id" not in data


def test_json_formatter_includes_otel_trace_id_when_span_active():
    """When an OTel span is active, otel_trace_id appears in the JSON record."""
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from hachi.core.obs.logging_setup import HachiJsonFormatter

    exp = InMemorySpanExporter()
    _tracing.setup_tracing(exporter=exp, force=True)

    fmt = HachiJsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="inside span",
        args=(),
        exc_info=None,
    )

    with _tracing.span("test.span"):
        output = fmt.format(record)

    data = json.loads(output)
    assert "otel_trace_id" in data, f"otel_trace_id missing from: {data}"


# ---------------------------------------------------------------------------
# TraceContextFilter
# ---------------------------------------------------------------------------


def test_trace_context_filter_injects_turn_id_into_vanilla_logger(caplog):
    """A vanilla getLogger() record gets turn_id injected via the filter."""
    from hachi.core.obs.logging_setup import TraceContextFilter
    from hachi.core.obs.trace import TraceContext, bind

    filt = TraceContextFilter()
    record = logging.LogRecord(
        name="some.module",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test",
        args=(),
        exc_info=None,
    )

    ctx = TraceContext(trace_id="filter-turn", session_id="ses-f", principal="p", surface="cli")
    with bind(ctx):
        filt.filter(record)

    assert getattr(record, "turn_id", None) == "filter-turn"
    assert getattr(record, "session_id", None) == "ses-f"


def test_trace_context_filter_omits_turn_id_without_context():
    """Outside a TraceContext, the filter leaves the record unmodified."""
    from hachi.core.obs.logging_setup import TraceContextFilter

    filt = TraceContextFilter()
    record = logging.LogRecord(
        name="some.module",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert not hasattr(record, "turn_id") or getattr(record, "turn_id", None) is None


# ---------------------------------------------------------------------------
# setup_logging with log_format
# ---------------------------------------------------------------------------


def test_setup_logging_text_mode_returns_logger():
    """setup_logging(log_format='text') returns a logger without error."""
    from hachi.core.obs.logging_setup import setup_logging

    log = setup_logging("test.module", log_format="text")
    assert isinstance(log, logging.Logger)


def test_setup_logging_json_mode_returns_logger():
    """setup_logging(log_format='json') returns a logger without error."""
    from hachi.core.obs.logging_setup import setup_logging

    log = setup_logging("test.module", log_format="json")
    assert isinstance(log, logging.Logger)


def test_setup_logging_default_is_text():
    """Default call (no log_format) behaves as 'text'."""
    from hachi.core.obs.logging_setup import setup_logging

    log = setup_logging("test.default")
    assert isinstance(log, logging.Logger)


def test_existing_handlers_are_preserved():
    """setup_logging does not clobber a root logger that already has handlers."""
    from hachi.core.obs.logging_setup import setup_logging

    root = logging.getLogger()
    original_count = len(root.handlers)
    # If root already has handlers, a second call should not add another.
    if original_count > 0:
        setup_logging("test.preserve")
        assert len(root.handlers) == original_count
