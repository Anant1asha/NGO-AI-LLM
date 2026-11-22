"""Thin metrics facade — counters and histograms for Hachi's key signals.

Phase 3: fully activated.  ``setup_from_config(kind, endpoint)`` mirrors
the tracing API; call sites in ``loop.py`` / ``cost.py`` / ``boot_agent``
record real data.  All calls are no-ops when OTel metrics is not configured
so there is zero overhead in the default deployment.

Layering note
-------------
``metrics.py`` is imported *by* loop/cost/boot; it must **not** import
gateway/, jobs/, or any layer above core/.  The observable queue-depth gauge
uses a registered callback seam (``register_gauge_source``) so boot can hand
in the live queue's ``depth()`` callable without creating a cross-layer import.

Instruments
-----------
- ``hachi.turns.total``          Counter   surface
- ``hachi.tool_calls.total``     Counter   tool, error
- ``hachi.provider_errors.total``Counter   model, kind
- ``hachi.route_selections.total``Counter  capability, model
- ``hachi.turn.latency_ms``      Histogram surface
- ``hachi.tool.latency_ms``      Histogram tool, error
- ``hachi.llm.latency_ms``       Histogram model
- ``hachi.memory.latency_ms``    Histogram (no label)
- ``hachi.tokens.total``         Counter   model, kind
- ``hachi.cost.usd.total``       Counter   model, provider, feature
- ``hachi.cache.hits.total``     Counter   (no label)
- ``hachi.cache.calls.total``    Counter   (no label)
- ``hachi.jobs.queue_depth``     ObservableGauge (callback registered at boot)
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_meter: Any = None
_turn_counter: Any = None
_tool_counter: Any = None
_error_counter: Any = None
_route_counter: Any = None
_turn_latency: Any = None
_tool_latency: Any = None
_llm_latency: Any = None
_memory_latency: Any = None
_token_counter: Any = None
_cost_counter: Any = None
_cache_hit_counter: Any = None
_cache_call_counter: Any = None


def setup_metrics(exporter: Any = None) -> bool:
    """Configure OTel metrics.  Idempotent; safe to call multiple times.

    Args:
        exporter: An OTel ``MetricExporter`` or ``None`` (instruments created
                  but not exported — useful for testing the call path without
                  a live backend).

    Returns:
        True if metrics are now active, False if the OTel SDK is unavailable.
    """
    global _meter, _turn_counter, _tool_counter, _error_counter
    global _route_counter, _turn_latency, _tool_latency
    global _llm_latency, _memory_latency, _token_counter, _cost_counter
    global _cache_hit_counter, _cache_call_counter
    try:
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            PeriodicExportingMetricReader,
        )

        readers = []
        if exporter is not None:
            readers.append(PeriodicExportingMetricReader(exporter, export_interval_millis=15_000))

        provider = MeterProvider(metric_readers=readers)
        _meter = provider.get_meter("hachi")

        _turn_counter = _meter.create_counter(
            "hachi.turns.total",
            description="Number of agent turns completed.",
        )
        _tool_counter = _meter.create_counter(
            "hachi.tool_calls.total",
            description="Number of tool calls executed.",
        )
        _error_counter = _meter.create_counter(
            "hachi.provider_errors.total",
            description="Number of provider/LLM errors (retryable and fatal).",
        )
        _route_counter = _meter.create_counter(
            "hachi.route_selections.total",
            description="Number of model route selections made.",
        )
        _turn_latency = _meter.create_histogram(
            "hachi.turn.latency_ms",
            unit="ms",
            description="Wall-clock latency of a complete agent turn.",
        )
        _tool_latency = _meter.create_histogram(
            "hachi.tool.latency_ms",
            unit="ms",
            description="Wall-clock latency of a single tool call.",
        )
        _llm_latency = _meter.create_histogram(
            "hachi.llm.latency_ms",
            unit="ms",
            description="Wall-clock latency of a single LLM generation call.",
        )
        _memory_latency = _meter.create_histogram(
            "hachi.memory.latency_ms",
            unit="ms",
            description="Wall-clock latency of a memory recall operation.",
        )
        _token_counter = _meter.create_counter(
            "hachi.tokens.total",
            description="Total tokens used (input / output / cache_read / cache_creation).",
        )
        _cost_counter = _meter.create_counter(
            "hachi.cost.usd.total",
            unit="USD",
            description="Cumulative cost in USD.",
        )
        _cache_hit_counter = _meter.create_counter(
            "hachi.cache.hits.total",
            description="Number of cache hit events.",
        )
        _cache_call_counter = _meter.create_counter(
            "hachi.cache.calls.total",
            description="Total cache calls (hits + misses).",
        )
        return True
    except Exception:  # pragma: no cover — SDK not installed
        return False


def setup_from_config(exporter_kind: str | None, endpoint: str | None = None) -> bool:
    """Configure metrics from ``[observability]`` settings.

    Mirrors ``tracing.setup_from_config``; uses a lazy OTLP import so the
    ``[observability]`` extra is only required when ``kind="otlp"``.

    Args:
        exporter_kind: ``"console"`` (or ``None``) for no real export but
                       instruments created; ``"otlp"`` for OTLP metric export.
        endpoint:      OTLP endpoint URL (``"otlp"`` only; falls back to
                       ``OTEL_EXPORTER_OTLP_ENDPOINT``).

    Returns:
        True if metrics are now active, False on error.
    """
    if exporter_kind is None or exporter_kind.lower() in {"console", ""}:
        return setup_metrics(exporter=None)

    kind = exporter_kind.lower()
    if kind == "otlp":
        try:
            import os

            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )

            kwargs: dict[str, Any] = {}
            ep = endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            if ep:
                kwargs["endpoint"] = ep
            return setup_metrics(exporter=OTLPMetricExporter(**kwargs))
        except ImportError:
            logger.warning(
                "OTLP metric exporter requested but 'opentelemetry-exporter-otlp' is "
                "not installed.  Install with: pip install 'hachi-og[observability]'"
            )
            return False

    logger.warning(
        "Unknown [observability] metrics exporter %r — expected 'console' or 'otlp'. "
        "Metrics not configured.",
        exporter_kind,
    )
    return False


def register_gauge_source(name: str, callback: Any) -> None:
    """Register a callable as an observable gauge source.

    Intended for use at boot to wire the live ``SQLiteJobQueue.depth()`` into
    the ``hachi.jobs.queue_depth`` gauge without creating a cross-layer import
    inside ``metrics.py``.

    The callback is called by the OTel SDK on each collection cycle (async,
    non-blocking from the turn thread's perspective).

    Args:
        name:     Metric instrument name (e.g. ``"hachi.jobs.queue_depth"``).
        callback: Zero-argument callable that returns the current gauge value
                  (int or float).
    """
    if _meter is None:
        return
    try:

        def _observe(options: Any) -> Any:
            try:
                val = callback()
                from opentelemetry.metrics import Observation

                yield Observation(value=val)
            except Exception:
                pass

        _meter.create_observable_gauge(
            name,
            callbacks=[_observe],
            description=f"Observable gauge: {name}",
        )
    except Exception:
        logger.debug("register_gauge_source: failed to register %r", name, exc_info=True)


def record_turn(surface: str = "unknown", *, latency_ms: float | None = None) -> None:
    """Increment the turn counter and optionally record latency.

    Args:
        surface: Request origin (``"cli"``, ``"web"``, etc.).
        latency_ms: Elapsed milliseconds for the turn, if available.
    """
    if _turn_counter is None:
        return
    try:
        _turn_counter.add(1, {"surface": surface})
        if latency_ms is not None and _turn_latency is not None:
            _turn_latency.record(latency_ms, {"surface": surface})
    except Exception:
        pass


def record_tool_call(
    tool_name: str, *, error: bool = False, latency_ms: float | None = None
) -> None:
    """Increment the tool-call counter.

    Args:
        tool_name:  Name of the tool that was called.
        error:      True when the tool raised an exception.
        latency_ms: Elapsed milliseconds for the call, if available.
    """
    if _tool_counter is None:
        return
    try:
        attrs = {"tool": tool_name, "error": str(error).lower()}
        _tool_counter.add(1, attrs)
        if latency_ms is not None and _tool_latency is not None:
            _tool_latency.record(latency_ms, attrs)
    except Exception:
        pass


def record_llm_call(model: str = "unknown", *, latency_ms: float | None = None) -> None:
    """Record LLM generation latency.

    Args:
        model:      Model id.
        latency_ms: Elapsed milliseconds for the LLM call.
    """
    if _llm_latency is None:
        return
    try:
        if latency_ms is not None:
            _llm_latency.record(latency_ms, {"model": model})
    except Exception:
        pass


def record_memory_recall(*, latency_ms: float | None = None) -> None:
    """Record memory recall latency.

    Args:
        latency_ms: Elapsed milliseconds for the recall.
    """
    if _memory_latency is None:
        return
    try:
        if latency_ms is not None:
            _memory_latency.record(latency_ms)
    except Exception:
        pass


def record_tokens(model: str, kind: str, count: int) -> None:
    """Increment the token counter.

    Args:
        model: Model id.
        kind:  One of ``"input"``, ``"output"``, ``"cache_read"``, ``"cache_creation"``.
        count: Number of tokens.
    """
    if _token_counter is None or count <= 0:
        return
    try:
        _token_counter.add(count, {"model": model, "kind": kind})
    except Exception:
        pass


def record_cost(model: str, provider: str, feature: str, cost_usd: float) -> None:
    """Increment the cumulative cost counter.

    Args:
        model:    Model id.
        provider: Provider name (``"anthropic"``, ``"openai"``, etc.).
        feature:  Usage feature (``"agent"``, ``"subagent"``, etc.).
        cost_usd: Cost in USD for this event.
    """
    if _cost_counter is None or cost_usd <= 0:
        return
    try:
        _cost_counter.add(cost_usd, {"model": model, "provider": provider, "feature": feature})
    except Exception:
        pass


def record_cache_hit() -> None:
    """Increment the cache-hit counter."""
    if _cache_hit_counter is None:
        return
    try:
        _cache_hit_counter.add(1)
    except Exception:
        pass


def record_cache_call() -> None:
    """Increment the total cache-call counter (hits + misses)."""
    if _cache_call_counter is None:
        return
    try:
        _cache_call_counter.add(1)
    except Exception:
        pass


def record_provider_error(model: str, error_kind: str = "unknown") -> None:
    """Increment the provider-error counter.

    Args:
        model:      Model id that produced the error.
        error_kind: Short classification (e.g. ``"rate_limit"``, ``"timeout"``).
    """
    if _error_counter is None:
        return
    try:
        _error_counter.add(1, {"model": model, "kind": error_kind})
    except Exception:
        pass


def record_route_selection(capability: str, model: str) -> None:
    """Increment the route-selection counter.

    Args:
        capability: The capability being routed (e.g. ``"REASONING"``, ``"VISION"``).
        model:      The model id selected.
    """
    if _route_counter is None:
        return
    try:
        _route_counter.add(1, {"capability": capability, "model": model})
    except Exception:
        pass


class TurnTimer:
    """Simple context manager to time a turn and call :func:`record_turn`.

    Usage::

        with TurnTimer(surface="web"):
            ...
    """

    def __init__(self, surface: str = "unknown") -> None:
        self.surface = surface
        self._start: float = 0.0

    def __enter__(self) -> TurnTimer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        elapsed_ms = (time.monotonic() - self._start) * 1000.0
        record_turn(self.surface, latency_ms=elapsed_ms)


def _reset_for_tests() -> None:
    """Reset all metric instruments (tests only)."""
    global _meter, _turn_counter, _tool_counter, _error_counter
    global _route_counter, _turn_latency, _tool_latency
    global _llm_latency, _memory_latency, _token_counter, _cost_counter
    global _cache_hit_counter, _cache_call_counter
    _meter = None
    _turn_counter = None
    _tool_counter = None
    _error_counter = None
    _route_counter = None
    _turn_latency = None
    _tool_latency = None
    _llm_latency = None
    _memory_latency = None
    _token_counter = None
    _cost_counter = None
    _cache_hit_counter = None
    _cache_call_counter = None
