"""Tests for exporter selection in core/tracing.py — console / otlp / langfuse."""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry")

import hachi.core.tracing as _tracing  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    _tracing._reset_for_tests()
    yield
    _tracing._reset_for_tests()


# ---------------------------------------------------------------------------
# console exporter (default, always available with OTel SDK)
# ---------------------------------------------------------------------------


def test_setup_from_config_console():
    ok = _tracing.setup_from_config("console")
    assert ok is True
    assert _tracing.is_active()


def test_setup_from_config_console_case_insensitive():
    ok = _tracing.setup_from_config("CONSOLE")
    assert ok is True


# ---------------------------------------------------------------------------
# otlp / langfuse — construct the processor; don't export over network
# ---------------------------------------------------------------------------


def test_setup_from_config_otlp_without_sdk_logs_warning(caplog):
    """When the OTLP exporter extra is NOT installed we get a warning, not a crash."""
    import importlib.util

    if importlib.util.find_spec("opentelemetry.exporter.otlp.proto.http") is not None:
        pytest.skip("OTLP exporter is installed; skip 'not installed' path")

    import logging

    with caplog.at_level(logging.WARNING, logger="hachi.core.tracing"):
        ok = _tracing.setup_from_config("otlp", endpoint="http://localhost:4318/v1/traces")
    assert ok is False
    assert "opentelemetry-exporter-otlp" in caplog.text


def test_setup_from_config_otlp_with_sdk(monkeypatch):
    """When OTLP exporter IS installed, setup_from_config returns True."""
    import importlib.util

    if importlib.util.find_spec("opentelemetry.exporter.otlp.proto.http") is None:
        pytest.skip("OTLP exporter not installed")

    import opentelemetry.exporter.otlp.proto.http.trace_exporter as _otlp_mod
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    # Replace OTLPSpanExporter with in-memory so no network call happens.
    monkeypatch.setattr(_otlp_mod, "OTLPSpanExporter", lambda **kw: InMemorySpanExporter())
    _tracing._reset_for_tests()

    ok = _tracing.setup_from_config("otlp", endpoint="http://localhost:4318/v1/traces")
    assert ok is True


def test_setup_from_config_unknown_kind_returns_false(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="hachi.core.tracing"):
        ok = _tracing.setup_from_config("prometheus")
    assert ok is False
    assert "prometheus" in caplog.text


# ---------------------------------------------------------------------------
# batch parameter
# ---------------------------------------------------------------------------


def test_setup_tracing_with_batch():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exp = InMemorySpanExporter()
    ok = _tracing.setup_tracing(exporter=exp, batch=True, force=True)
    assert ok is True
    assert _tracing.is_active()


def test_setup_tracing_simple_default():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exp = InMemorySpanExporter()
    ok = _tracing.setup_tracing(exporter=exp, force=True)  # batch=False default
    assert ok is True
    assert _tracing.is_active()


# ---------------------------------------------------------------------------
# configure_from_env
# ---------------------------------------------------------------------------


def test_configure_from_env_off_by_default():
    result = _tracing.configure_from_env()
    assert result is False
    assert not _tracing.is_active()


def test_configure_from_env_enabled(monkeypatch):
    monkeypatch.setenv("HACHI_TRACING", "true")
    result = _tracing.configure_from_env()
    assert result is True
    assert _tracing.is_active()
