"""Shared logging bootstrap for CLI / gateway / TUI entry points — Phase 5.

Adds a JSON formatter (``HachiJsonFormatter``) and a ``TraceContextFilter``
that injects ``turn_id``, ``session_id``, and (when OTel is active)
``otel_trace_id`` / ``otel_span_id`` into every log record — without touching
any existing call sites.  All existing ``getLogger(__name__)`` calls emit
correlated JSON when ``log_format="json"`` is set at the entry-point.

Modes
-----
- ``log_format="text"`` (default): existing text format; ``TraceContextFilter``
  injects ids as extra fields (visible if the formatter uses them).
- ``log_format="json"``: ``HachiJsonFormatter`` produces a single-line JSON
  object with ``ts``, ``level``, ``logger``, ``message``, ``turn_id``,
  ``session_id``, ``otel_trace_id``, ``otel_span_id``, and optional
  ``exc_info``.

Usage in entry points::

    from hachi.core.obs.logging_setup import setup_logging

    setup_logging(__name__, log_format="json")
    # or simply:
    setup_logging(__name__)  # text mode, same as today

    # For per-logger trace correlation (incremental polish):
    logger = traced_logger(logging.getLogger(__name__))
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any


class HachiJsonFormatter(logging.Formatter):
    """Single-line JSON log formatter with TraceContext correlation ids.

    Injects ``turn_id``, ``session_id``, ``otel_trace_id``, ``otel_span_id``
    from the active context at format time — so every ``getLogger(__name__)``
    call emits correlated JSON without any call-site changes.
    """

    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject TraceContext ids.
        turn_id, session_id = _get_trace_ids()
        if turn_id:
            out["turn_id"] = turn_id
        if session_id:
            out["session_id"] = session_id

        # Inject OTel span ids when a span is active.
        otel_trace_id, otel_span_id = _get_otel_ids()
        if otel_trace_id:
            out["otel_trace_id"] = otel_trace_id
        if otel_span_id:
            out["otel_span_id"] = otel_span_id

        # Extra fields injected by filters or LoggerAdapters.
        for key in getattr(record, "__dict__", {}):
            if key.startswith("_") or key in _LOGGING_BUILTINS:
                continue
            if key in out:
                continue
            val = getattr(record, key, None)
            if isinstance(val, str | bool | int | float):
                out[key] = val

        if record.exc_info:
            out["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(out, ensure_ascii=False)


# Standard LogRecord attributes we never want to re-emit as extra fields.
_LOGGING_BUILTINS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }
)


class TraceContextFilter(logging.Filter):
    """Injects ``turn_id``, ``session_id``, ``otel_trace_id`` into every record.

    Install on the root logger so all existing ``getLogger(__name__)`` calls
    emit correlated records without call-site changes::

        root = logging.getLogger()
        root.addFilter(TraceContextFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        turn_id, session_id = _get_trace_ids()
        if turn_id:
            record.turn_id = turn_id  # type: ignore[attr-defined]
        if session_id:
            record.session_id = session_id  # type: ignore[attr-defined]

        otel_trace_id, otel_span_id = _get_otel_ids()
        if otel_trace_id:
            record.otel_trace_id = otel_trace_id  # type: ignore[attr-defined]
        if otel_span_id:
            record.otel_span_id = otel_span_id  # type: ignore[attr-defined]

        return True


def setup_logging(
    name: str | None = None,
    *,
    level: int | None = None,
    log_format: str = "text",
) -> logging.Logger:
    """Bootstrap the root logger and return a logger for *name*.

    Idempotent: if the root logger already has handlers this only adjusts the
    level and installs the ``TraceContextFilter`` if not already present.

    Args:
        name:       Logger name (typically ``__name__`` of the caller).
                    ``None`` returns the root logger.
        level:      Override the log level.  When ``None``, reads
                    ``HACHI_LOG_LEVEL`` (``WARNING`` by default).
        log_format: ``"text"`` (default, existing format) or ``"json"``
                    (``HachiJsonFormatter`` — correlated JSON on every line).

    Returns:
        A configured :class:`logging.Logger`.
    """
    effective_level = level if level is not None else _level_from_env()
    root = logging.getLogger()

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(effective_level)
        if log_format == "json":
            handler.setFormatter(HachiJsonFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                    datefmt="%H:%M:%S",
                )
            )
        root.addHandler(handler)

    if root.level == logging.NOTSET or root.level > effective_level:
        root.setLevel(effective_level)

    # Install the filter once (idempotent check by class name).
    if not any(isinstance(f, TraceContextFilter) for f in root.filters):
        root.addFilter(TraceContextFilter())

    return logging.getLogger(name)


def traced_logger(logger: logging.Logger) -> logging.LoggerAdapter[logging.Logger]:
    """Wrap *logger* in an adapter that injects ``trace_id`` from the active TraceContext.

    When no :class:`~hachi.core.obs.trace.TraceContext` is bound the adapter
    omits the ``trace_id`` key so log records produced outside a turn remain
    unchanged.

    Args:
        logger: Base :class:`logging.Logger` to wrap.

    Returns:
        A :class:`logging.LoggerAdapter` with dynamic ``trace_id`` injection.
    """
    return _TracedAdapter(logger, extra={})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _level_from_env() -> int:
    """Resolve the log level from ``HACHI_LOG_LEVEL`` (default ``WARNING``)."""
    raw = os.environ.get("HACHI_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, raw, None)
    if isinstance(level, int):
        return level
    return logging.WARNING


def _get_trace_ids() -> tuple[str | None, str | None]:
    """Return (turn_id, session_id) from the active TraceContext, or (None, None)."""
    try:
        from hachi.core.obs.trace import current as _current

        tc = _current()
        if tc is not None:
            return tc.trace_id, tc.session_id
    except Exception:
        pass
    return None, None


def _get_otel_ids() -> tuple[str | None, str | None]:
    """Return (otel_trace_id, otel_span_id) from the active OTel span, or (None, None)."""
    try:
        from opentelemetry import trace as _otel_trace

        span = _otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is not None and ctx.is_valid:
            return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:
        pass
    return None, None


class _TracedAdapter(logging.LoggerAdapter):  # type: ignore[type-arg]
    """LoggerAdapter that dynamically injects ``trace_id`` from the active TraceContext."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        try:
            from hachi.core.obs.trace import current as _current

            tc = _current()
            if tc is not None:
                extra = dict(kwargs.get("extra") or {})
                extra.setdefault("trace_id", tc.trace_id)
                kwargs = dict(kwargs)
                kwargs["extra"] = extra
        except Exception:  # pragma: no cover — obs not available
            pass
        return msg, kwargs
