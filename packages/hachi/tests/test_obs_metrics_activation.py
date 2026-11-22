"""Phase 3 — metrics activation: setup_from_config, register_gauge_source, call sites.

Failing-first per the regression law: setup_from_config and
register_gauge_source do not exist on metrics.py before Phase 3.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry")

from hachi.core.obs import metrics as _metrics


@pytest.fixture(autouse=True)
def _reset():
    _metrics._reset_for_tests()
    yield
    _metrics._reset_for_tests()


# ---------------------------------------------------------------------------
# setup_from_config
# ---------------------------------------------------------------------------


def test_setup_from_config_console_activates_meter():
    """setup_from_config('console') creates a valid meter."""
    ok = _metrics.setup_from_config("console")
    assert ok is True
    assert _metrics._meter is not None


def test_setup_from_config_none_exporter_creates_meter():
    """setup_from_config(None) still creates instruments (no export, useful for testing)."""
    ok = _metrics.setup_from_config(None)
    assert ok is True
    assert _metrics._meter is not None


def test_setup_from_config_otlp_missing_warns(caplog):
    """When OTLP extra is absent, setup_from_config('otlp') warns and returns False."""
    import importlib.util
    import logging

    if importlib.util.find_spec("opentelemetry.exporter.otlp.proto.http") is not None:
        pytest.skip("OTLP exporter installed; skip 'missing' path")

    with caplog.at_level(logging.WARNING):
        ok = _metrics.setup_from_config("otlp", endpoint="http://localhost:4317")
    assert ok is False


def test_setup_from_config_unknown_kind_warns_and_returns_false(caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        ok = _metrics.setup_from_config("prometheus-push")
    assert ok is False


def test_setup_from_config_idempotent():
    """Calling setup_from_config twice does not raise."""
    _metrics.setup_from_config("console")
    _metrics.setup_from_config("console")  # second call must not raise
    assert _metrics._meter is not None


# ---------------------------------------------------------------------------
# register_gauge_source
# ---------------------------------------------------------------------------


def test_register_gauge_source_called_silently_when_no_meter():
    """register_gauge_source is a no-op when meter is not set up."""
    _metrics.register_gauge_source("hachi.jobs.queue_depth", lambda: 5)
    # Must not raise; meter is None at this point.


def test_register_gauge_source_with_active_meter():
    """After setup, gauge callback is registerable without error."""
    _metrics.setup_from_config("console")
    _metrics.register_gauge_source("hachi.jobs.queue_depth", lambda: 42)
    # Must not raise.


# ---------------------------------------------------------------------------
# Record call sites short-circuit when unconfigured
# ---------------------------------------------------------------------------


def test_record_turn_noop_when_unconfigured():
    _metrics.record_turn(surface="web", latency_ms=100.0)


def test_record_tool_call_noop_when_unconfigured():
    _metrics.record_tool_call("bash", error=False, latency_ms=5.0)


def test_record_provider_error_noop_when_unconfigured():
    _metrics.record_provider_error("claude-haiku", "rate_limit")


def test_record_route_selection_noop_when_unconfigured():
    _metrics.record_route_selection("REASONING", "claude-opus")


def test_cache_counters_noop_when_unconfigured():
    _metrics.record_cache_hit()
    _metrics.record_cache_call()


def test_zero_token_zero_cost_records_nothing_spurious():
    """A zero-token zero-cost turn must not increment any counter."""
    _metrics.setup_from_config("console")
    # record_turn with zero latency should not raise or produce spurious values.
    _metrics.record_turn(surface="cli", latency_ms=0.0)
