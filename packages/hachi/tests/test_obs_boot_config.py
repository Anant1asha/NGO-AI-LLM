"""Phase 0 — BB-73: verify that [observability] config actually drives boot.

These tests are written FIRST (regression law) against the helper
``gateway.orchestrator._apply_observability_settings`` that Phase 0 introduces.
Before the fix, the helper does not exist and boot_agent never calls
setup_from_config / setup_metrics regardless of config.

Flakiness discipline: boot-path tests assert only activation/config
(is_active(), exporter kind) — NEVER span contents (those use in-memory
SimpleSpanProcessor paths in other test files).
"""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("opentelemetry")

import hachi.core.tracing as _tracing  # noqa: E402
from hachi.core.obs import metrics as _metrics  # noqa: E402
from hachi.core.settings import EventsSettings, ObservabilitySettings  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    _tracing._reset_for_tests()
    _metrics._reset_for_tests()
    yield
    _tracing._reset_for_tests()
    _metrics._reset_for_tests()


def _apply(obs_cfg: ObservabilitySettings, bus_funnel: bool = True) -> None:
    """Call the orchestrator helper under test."""
    from hachi.gateway.orchestrator import _apply_observability_settings

    events_cfg = EventsSettings(bus_funnel=bus_funnel)
    _apply_observability_settings(obs_cfg, events_cfg)


# ---------------------------------------------------------------------------
# BB-73 — dead wiring
# ---------------------------------------------------------------------------


def test_obs_disabled_by_default_tracing_off():
    """Default ObservabilitySettings → tracing stays off."""
    _apply(ObservabilitySettings())
    assert not _tracing.is_active()


def test_obs_enabled_console_activates_tracing():
    """enabled=True, exporter='console' → is_active() True after helper runs."""
    _apply(ObservabilitySettings(enabled=True, exporter="console"))
    assert _tracing.is_active()


def test_obs_enabled_metrics_activates_metrics():
    """enabled=True, metrics_enabled=True → metrics meter is non-None."""
    _apply(ObservabilitySettings(enabled=True, exporter="console", metrics_enabled=True))
    assert _metrics._meter is not None


def test_obs_metrics_not_started_when_flag_off():
    """metrics_enabled=False → _meter stays None."""
    _apply(ObservabilitySettings(enabled=True, exporter="console", metrics_enabled=False))
    assert _metrics._meter is None


def test_obs_sdk_absent_returns_gracefully(monkeypatch):
    """When OTel SDK is unavailable, setup_from_config returns False — boot continues."""
    monkeypatch.setattr(_tracing, "_OTEL_AVAILABLE", False)
    # Must not raise.
    _apply(ObservabilitySettings(enabled=True, exporter="console"))
    assert not _tracing.is_active()


def test_obs_unknown_exporter_warns_and_continues(caplog):
    """An unknown exporter kind logs a warning and leaves tracing off — boot never crashes."""
    with caplog.at_level(logging.WARNING, logger="hachi.core.tracing"):
        _apply(ObservabilitySettings(enabled=True, exporter="prometheus"))
    assert not _tracing.is_active()
    assert "prometheus" in caplog.text.lower() or "unknown" in caplog.text.lower()


# ---------------------------------------------------------------------------
# BB-73 — degraded mode (bus_funnel=false)
# ---------------------------------------------------------------------------


def test_obs_enabled_bus_funnel_false_warns(caplog):
    """enabled=True + bus_funnel=False → WARNING logged; tracing still activates."""
    with caplog.at_level(logging.WARNING):
        _apply(ObservabilitySettings(enabled=True, exporter="console"), bus_funnel=False)
    assert _tracing.is_active(), "tracing should still activate despite bus_funnel=false"
    assert any(
        "bus_funnel" in r.message.lower() or "observability" in r.message.lower()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )


def test_obs_enabled_bus_funnel_true_no_warning(caplog):
    """enabled=True + bus_funnel=True → no degraded-mode warning."""
    with caplog.at_level(logging.WARNING):
        _apply(ObservabilitySettings(enabled=True, exporter="console"), bus_funnel=True)
    degraded_warnings = [
        r
        for r in caplog.records
        if r.levelno >= logging.WARNING and "bus_funnel" in r.message.lower()
    ]
    assert not degraded_warnings
