"""Tests for core/obs/metrics.py — thin metrics facade."""

from __future__ import annotations

import pytest

import hachi.core.obs.metrics as _metrics


@pytest.fixture(autouse=True)
def _reset():
    _metrics._reset_for_tests()
    yield
    _metrics._reset_for_tests()


# ---------------------------------------------------------------------------
# No-op safety (instruments == None)
# ---------------------------------------------------------------------------


def test_record_turn_noop_when_not_configured():
    """record_turn() is a no-op when setup_metrics has not been called."""
    _metrics.record_turn("cli", latency_ms=100.0)  # must not raise


def test_record_tool_call_noop_when_not_configured():
    _metrics.record_tool_call("bash", error=False, latency_ms=50.0)


def test_record_provider_error_noop_when_not_configured():
    _metrics.record_provider_error("claude-haiku-4-5", "rate_limit")


def test_record_route_selection_noop_when_not_configured():
    _metrics.record_route_selection("REASONING", "claude-haiku-4-5")


def test_turn_timer_noop_when_not_configured():
    with _metrics.TurnTimer("web"):
        pass  # must not raise


# ---------------------------------------------------------------------------
# Setup (requires OTel SDK)
# ---------------------------------------------------------------------------


otel = pytest.importorskip("opentelemetry")


def test_setup_metrics_returns_true():
    ok = _metrics.setup_metrics()  # no exporter — instruments exist but not flushed
    assert ok is True


def test_setup_metrics_creates_instruments():
    _metrics.setup_metrics()
    assert _metrics._turn_counter is not None
    assert _metrics._tool_counter is not None
    assert _metrics._error_counter is not None
    assert _metrics._route_counter is not None


def test_record_turn_after_setup():
    _metrics.setup_metrics()
    # Must not raise; counters increment internally.
    _metrics.record_turn("cli", latency_ms=250.0)


def test_record_tool_call_after_setup():
    _metrics.setup_metrics()
    _metrics.record_tool_call("read_file", error=False, latency_ms=10.0)
    _metrics.record_tool_call("bash", error=True)


def test_record_provider_error_after_setup():
    _metrics.setup_metrics()
    _metrics.record_provider_error("claude-haiku-4-5", "timeout")


def test_record_route_selection_after_setup():
    _metrics.setup_metrics()
    _metrics.record_route_selection("VISION", "claude-sonnet-4-5")


def test_turn_timer_context_manager():
    _metrics.setup_metrics()
    with _metrics.TurnTimer("tui"):
        pass  # records latency


def test_setup_metrics_idempotent():
    """setup_metrics can be called multiple times without error."""
    assert _metrics.setup_metrics() is True
    assert _metrics.setup_metrics() is True  # second call is a new provider (reset in fixture)
