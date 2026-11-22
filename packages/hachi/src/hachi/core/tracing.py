"""Optional OpenTelemetry tracing.

Emits spans for agent turns, LLM calls, and tool calls so operators can see where
time goes and how requests flow. It is **opt-in and degrades gracefully**: if the
OpenTelemetry SDK isn't installed (``pip install 'hachi-og[tracing]'``) or tracing
hasn't been configured, :func:`span` is a zero-cost no-op and the agent behaves
identically. Enable at runtime with ``HACHI_TRACING=true`` (console exporter),
or call :func:`setup_tracing` with your own exporter.

Implementation note: we hold our own ``TracerProvider`` + tracer rather than the
global OTel singleton, so configuration is re-entrant (tests can swap exporters)
and never collides with a host app that already set a global provider.

Exporter selection (``[observability].exporter`` in ``settings.toml``):
- ``"console"`` (default) — ``ConsoleSpanExporter`` via ``HACHI_TRACING=true``
- ``"otlp"`` — OTLP gRPC/HTTP exporter; endpoint via ``OTEL_EXPORTER_OTLP_ENDPOINT``
- ``"langfuse"`` — OTLP→Langfuse; endpoint + headers via env (opt-in, no live
  endpoint assumed; install ``hachi-og[observability]`` to get the dependencies).

All non-test exporters are wired through :class:`BatchSpanProcessor` so emission
never blocks the turn thread (Gate-C amendment A5).
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from typing import Any

try:  # pragma: no cover - import guard
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover - SDK not installed
    _OTEL_AVAILABLE = False

_tracer: Any = None
_configured = False


def is_available() -> bool:
    """True if the OpenTelemetry SDK is importable."""
    return _OTEL_AVAILABLE


def is_active() -> bool:
    """True if tracing has been configured and spans will be recorded."""
    return _tracer is not None


def setup_tracing(
    service_name: str = "hachi",
    exporter: Any = None,
    *,
    force: bool = False,
    batch: bool = False,
) -> bool:
    """Configure tracing. Idempotent unless ``force=True``.

    Args:
        service_name: ``service.name`` resource attribute.
        exporter: An OTel ``SpanExporter`` (e.g. console, OTLP, or in-memory for
            tests). When ``None``, a provider is created with no exporter (spans are
            produced but dropped) — pass an exporter to actually record them.
        force: Reconfigure even if already set up (used by tests to swap exporters).
        batch: When ``True``, wrap *exporter* in a :class:`BatchSpanProcessor`
            (async, buffered) instead of :class:`SimpleSpanProcessor`. Use ``True``
            for production exporters; ``False`` (default) for tests so spans are
            flushed synchronously and immediately visible to assertions.

    Returns:
        True if tracing is now active, False if the SDK is unavailable.
    """
    global _tracer, _configured
    if not _OTEL_AVAILABLE:
        return False
    if _configured and not force:
        return True
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if exporter is not None:
        if batch:
            provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            provider.add_span_processor(SimpleSpanProcessor(exporter))
    _tracer = provider.get_tracer("hachi")
    _configured = True
    return True


def configure_from_env() -> bool:
    """Auto-enable tracing when ``HACHI_TRACING`` is truthy (console exporter).

    Called during gateway boot. A no-op when the env flag is unset or the SDK is
    missing, so the default experience is unchanged.
    """
    if os.environ.get("HACHI_TRACING", "").lower() not in {"1", "true", "yes"}:
        return False
    if not _OTEL_AVAILABLE:
        return False
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    return setup_tracing(exporter=ConsoleSpanExporter(), batch=True)


def setup_from_config(exporter_kind: str, endpoint: str | None = None) -> bool:
    """Configure tracing from ``[observability]`` settings.

    Selects the exporter based on *exporter_kind* and wraps it in a
    :class:`BatchSpanProcessor` so export never blocks the turn thread (A5).

    Args:
        exporter_kind: One of ``"console"``, ``"otlp"``, or ``"langfuse"``.
        endpoint: OTLP endpoint URL (used for ``"otlp"`` and ``"langfuse"``).
            Falls back to the ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var.

    Returns:
        True if tracing is now active, False if the SDK / required extra is
        unavailable or the kind is unrecognised.
    """
    if not _OTEL_AVAILABLE:
        return False

    kind = exporter_kind.lower()

    if kind == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        return setup_tracing(exporter=ConsoleSpanExporter(), batch=True, force=True)

    if kind in {"otlp", "langfuse"}:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            kwargs: dict[str, Any] = {}
            ep = endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            if ep:
                kwargs["endpoint"] = ep
            return setup_tracing(exporter=OTLPSpanExporter(**kwargs), batch=True, force=True)
        except ImportError:
            # opentelemetry-exporter-otlp not installed; hint to the user.
            import logging

            logging.getLogger(__name__).warning(
                "OTLP exporter requested but 'opentelemetry-exporter-otlp' is not installed. "
                "Install with: pip install 'hachi-og[observability]'"
            )
            return False

    import logging

    logging.getLogger(__name__).warning(
        "Unknown [observability].exporter %r — expected 'console', 'otlp', or 'langfuse'. "
        "Tracing not configured.",
        exporter_kind,
    )
    return False


@contextlib.contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Record a span for the wrapped block. No-op if tracing isn't active.

    Args:
        name: Span name (e.g. ``"tool.call"``).
        **attributes: Span attributes (only str/bool/int/float are set).
    """
    if _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if isinstance(value, str | bool | int | float):
                try:
                    current.set_attribute(key, value)
                except Exception:  # pragma: no cover - never let tracing break a turn
                    pass
        yield


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the *current* active span.

    Safe to call when no span is active or tracing is unconfigured — a no-op in
    those cases.  Only ``str | bool | int | float`` values are forwarded.

    Args:
        **attributes: Key/value pairs to attach to the active span.
    """
    if _tracer is None:
        return
    try:
        from opentelemetry import trace as _otel_trace

        current = _otel_trace.get_current_span()
        for key, value in attributes.items():
            if isinstance(value, str | bool | int | float):
                try:
                    current.set_attribute(key, value)
                except Exception:  # pragma: no cover - never let tracing break a turn
                    pass
    except Exception:  # pragma: no cover - OTel unavailable
        pass


def add_span_event(name: str, **attributes: Any) -> None:
    """Add a named span-event to the *current* active span.

    Safe to call when no span is active or tracing is unconfigured — a no-op
    in those cases.  Only ``str | bool | int | float`` attribute values are
    forwarded.

    Args:
        name:       Span event name (e.g. ``"tool.call.started"``).
        **attributes: Key/value pairs to attach to the span event.
    """
    if _tracer is None:
        return
    try:
        from opentelemetry import trace as _otel_trace

        current = _otel_trace.get_current_span()
        safe_attrs = {
            k: v for k, v in attributes.items() if isinstance(v, str | bool | int | float)
        }
        current.add_event(name, attributes=safe_attrs)
    except Exception:  # pragma: no cover — OTel unavailable
        pass


def _reset_for_tests() -> None:
    """Clear tracing state so a test can reconfigure from scratch."""
    global _tracer, _configured
    _tracer = None
    _configured = False


__all__ = [
    "add_span_attributes",
    "add_span_event",
    "configure_from_env",
    "is_active",
    "is_available",
    "setup_from_config",
    "setup_tracing",
    "span",
]
