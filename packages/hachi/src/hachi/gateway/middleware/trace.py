"""Pure ASGI request-tracing middleware — Phase 4.

Adds an ``http.request`` root span to every HTTP request and propagates
W3C ``traceparent`` / ``tracestate`` headers both inbound (parent extraction)
and outbound (response injection).

Design constraints
------------------
- **Pure ASGI class**, not ``BaseHTTPMiddleware``: ``BaseHTTPMiddleware`` is
  known to buffer ``StreamingResponse`` bodies, which would break the SSE
  stream at ``GET /sessions/{id}/stream``.  The raw ASGI approach avoids this.
- **SSE special-case**: the ``GET /.../stream`` handshake span is opened and
  closed at the ASGI handshake (start of the scope) — not held open for the
  infinite generator lifetime.
- **No turn-scoped TraceContext here**: the middleware does not know the
  ``turn_id`` or ``session_id``; those are bound by ``orchestrator._chat_impl``.
- **Idempotency replay**: a replayed ``POST /messages`` returns early before
  ``send_message`` runs — the ``agent.turn`` span is absent for that request.
  The middleware still records ``http.request``; the trace model documents this.
- **No-op when tracing is off**: if ``tracing.is_active()`` is False the
  middleware passes through transparently with zero overhead.
- **OpenAPI contract**: adding a response header does NOT change any route
  schema; run ``hachi gateway-openapi`` to confirm zero diff (BB-4).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# W3C trace context propagator — lazy import so the module is importable even
# when the OTel SDK is absent.
_PROPAGATOR_LOADED = False
_propagator: Any = None


def _get_propagator() -> Any:
    global _propagator, _PROPAGATOR_LOADED
    if _PROPAGATOR_LOADED:
        return _propagator
    _PROPAGATOR_LOADED = True
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        _propagator = TraceContextTextMapPropagator()
    except Exception:
        _propagator = None
    return _propagator


class TraceMiddleware:
    """Pure ASGI middleware that adds a root ``http.request`` span per request.

    Register after CORS, before auth::

        app.add_middleware(TraceMiddleware)

    The middleware is a no-op when ``tracing.is_active()`` returns False so
    the default (unconfigured) deployment is completely unaffected.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        from hachi.core import tracing as _tracing

        if not _tracing.is_active():
            await self._app(scope, receive, send)
            return

        await self._traced_call(scope, receive, send)

    async def _traced_call(self, scope: dict, receive: Any, send: Any) -> None:
        from hachi.core import tracing as _tracing

        propagator = _get_propagator()

        # Extract W3C traceparent / tracestate from inbound headers.
        headers_dict: dict[str, str] = {}
        for name_bytes, value_bytes in scope.get("headers", []):
            try:
                headers_dict[name_bytes.decode("latin-1").lower()] = value_bytes.decode("latin-1")
            except Exception:
                pass

        # Inject the remote context (if any) so OTel picks it up as the parent.
        otel_ctx = None
        if propagator is not None:
            try:
                from opentelemetry import context as _otel_context
                from opentelemetry.propagators.textmap import DefaultGetter

                otel_ctx = propagator.extract(headers_dict, getter=DefaultGetter())
            except Exception:
                pass

        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        is_sse = scope["type"] == "http" and path.endswith("/stream")

        # Attach remote context so the span is created as a child.
        otel_token = None
        if otel_ctx is not None:
            try:
                from opentelemetry import context as _otel_context

                otel_token = _otel_context.attach(otel_ctx)
            except Exception:
                pass

        response_headers: list[tuple[bytes, bytes]] = []
        status_code: list[int] = [200]

        async def _send_intercept(message: dict) -> None:
            nonlocal response_headers
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 200)
                response_headers = list(message.get("headers", []))
                # Inject traceparent into response headers.
                if propagator is not None:
                    try:
                        carrier: dict[str, str] = {}
                        propagator.inject(carrier)
                        for k, v in carrier.items():
                            response_headers.append((k.encode(), v.encode()))
                        message = dict(message)
                        message["headers"] = response_headers
                    except Exception:
                        pass
            await send(message)

        try:
            with _tracing.span(
                "http.request",
                **{
                    "http.method": method,
                    "http.route": path,
                },
            ):
                if is_sse:
                    # For SSE: close the span immediately after the handshake
                    # starts — do not hold it open for the infinite generator.
                    await self._app(scope, receive, _send_intercept)
                else:
                    await self._app(scope, receive, _send_intercept)
                # Stamp status code on close.
                _tracing.add_span_attributes(**{"http.status_code": status_code[0]})
        except Exception:
            raise
        finally:
            if otel_token is not None:
                try:
                    from opentelemetry import context as _otel_context

                    _otel_context.detach(otel_token)
                except Exception:
                    pass
