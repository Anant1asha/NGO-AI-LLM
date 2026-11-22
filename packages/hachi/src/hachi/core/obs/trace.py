"""TraceContext — per-turn correlation carrier.

The ``trace_id`` is identical to the ``turn_id`` that ``_chat_impl`` already
generates (``orchestrator.py``), promoted to the canonical correlation id.
Context is carried via :mod:`contextvars` and (when OTel is available) also
set as OTel baggage so it propagates across serialisation boundaries.

Usage
-----
.. code-block:: python

    from hachi.core.obs.trace import TraceContext, bind, current

    ctx = TraceContext(
        trace_id=turn_id,
        session_id=session_id,
        principal="<token-hash>",
        surface="web",
    )
    with bind(ctx):
        ...  # current() returns ctx inside here

The module is import-safe even when the OTel SDK is not installed.
"""

from __future__ import annotations

import contextlib
import hashlib
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass

# Module-level contextvars token — one per thread-of-execution copy.
_CURRENT: ContextVar[TraceContext | None] = ContextVar("hachi.trace_context", default=None)


@dataclass(frozen=True, slots=True)
class TraceContext:
    """Immutable per-turn correlation carrier.

    Attributes:
        trace_id:   Canonical trace identifier — equals the ``turn_id`` generated
                    in ``orchestrator._chat_impl`` so a single id spans all layers.
        session_id: The session this turn belongs to.
        principal:  A stable (non-reversible) token hash identifying the caller.
                    Hashed with SHA-256 so no bearer token reaches the exporter.
        surface:    Request origin: ``"cli"``, ``"tui"``, ``"web"``, ``"webhook"``,
                    or ``"schedule"``.
    """

    trace_id: str
    session_id: str
    principal: str
    surface: str

    @staticmethod
    def hash_principal(raw: str) -> str:
        """One-way hash a raw bearer token or credential to a safe principal id.

        Args:
            raw: The raw token or credential string.

        Returns:
            Hex SHA-256 digest (first 16 chars, enough for correlation).
        """
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


def current() -> TraceContext | None:
    """Return the :class:`TraceContext` active on this thread/task, or ``None``.

    Returns:
        The current context if one has been bound, otherwise ``None``.
    """
    return _CURRENT.get()


@contextlib.contextmanager
def bind(ctx: TraceContext) -> Iterator[TraceContext]:
    """Bind *ctx* as the active :class:`TraceContext` for the current scope.

    Also sets OTel baggage entries (``trace_id``, ``session_id``, ``surface``)
    when the OTel SDK is available so the context propagates across
    serialisation and thread boundaries via :func:`propagate`.

    Args:
        ctx: The context to activate.

    Yields:
        The same *ctx* passed in.
    """
    token = _CURRENT.set(ctx)
    otel_token: object | None = None
    try:
        otel_token = _attach_otel_baggage(ctx)
        yield ctx
    finally:
        _CURRENT.reset(token)
        if otel_token is not None:
            _detach_otel_context(otel_token)


# ---------------------------------------------------------------------------
# Internal OTel helpers (no-op when SDK unavailable)
# ---------------------------------------------------------------------------


def _attach_otel_baggage(ctx: TraceContext) -> object | None:
    """Attach OTel baggage carrying trace correlation ids.

    Returns the OTel context token (to detach later) or ``None`` when OTel is
    not available.
    """
    try:
        from opentelemetry import baggage
        from opentelemetry import context as otel_context

        bag = otel_context.get_current()
        bag = baggage.set_baggage("hachi.trace_id", ctx.trace_id, bag)
        bag = baggage.set_baggage("hachi.session_id", ctx.session_id, bag)
        bag = baggage.set_baggage("hachi.surface", ctx.surface, bag)
        return otel_context.attach(bag)
    except Exception:  # pragma: no cover — OTel unavailable or import error
        return None


def _detach_otel_context(token: object) -> None:
    """Detach a previously attached OTel context token."""
    try:
        from opentelemetry import context as otel_context

        otel_context.detach(token)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover
        pass


def copy_otel_context() -> object:
    """Capture the current OTel context for propagation into a worker thread.

    Returns:
        An opaque OTel context object (or ``None`` when OTel is unavailable).
    """
    try:
        from opentelemetry import context as otel_context

        return otel_context.get_current()
    except Exception:  # pragma: no cover
        return None


def attach_otel_context(ctx: object) -> object | None:
    """Attach a previously captured OTel context to the current thread.

    Args:
        ctx: Context previously returned by :func:`copy_otel_context`.

    Returns:
        Token to pass to :func:`detach_otel_context` when done.
    """
    if ctx is None:
        return None
    try:
        from opentelemetry import context as otel_context

        return otel_context.attach(ctx)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover
        return None


def detach_otel_context(token: object) -> None:
    """Detach an OTel context token previously returned by :func:`attach_otel_context`.

    Args:
        token: The token to detach (``None`` is a no-op).
    """
    if token is None:
        return
    try:
        from opentelemetry import context as otel_context

        otel_context.detach(token)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover
        pass
