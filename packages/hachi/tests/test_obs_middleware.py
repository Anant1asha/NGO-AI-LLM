"""Phase 4 — Gateway request-tracing middleware + thread-hop span propagation.

Failing-first per the regression law.  The module
``gateway/middleware/trace.py`` does not exist before Phase 4.

Step A: proves the OTel context survives the sync-route threadpool hop
so agent.turn nests under http.request automatically.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import hachi.core.tracing as _tracing
from hachi.core.obs.trace import (
    attach_otel_context,
    copy_otel_context,
    detach_otel_context,
)


@pytest.fixture(autouse=True)
def _reset():
    _tracing._reset_for_tests()
    yield
    _tracing._reset_for_tests()


def _configure() -> InMemorySpanExporter:
    exp = InMemorySpanExporter()
    _tracing.setup_tracing(exporter=exp, force=True)
    return exp


# ---------------------------------------------------------------------------
# Step A — import / basic structure
# ---------------------------------------------------------------------------


def test_trace_middleware_importable():
    """The middleware module must be importable."""
    from hachi.gateway.middleware.trace import TraceMiddleware  # noqa: F401


def test_trace_middleware_is_callable():
    """TraceMiddleware must accept an ASGI app and be callable."""
    from hachi.gateway.middleware.trace import TraceMiddleware

    async def dummy_app(scope, receive, send):
        pass

    mw = TraceMiddleware(dummy_app)
    assert callable(mw)


# ---------------------------------------------------------------------------
# Step A — thread-hop span propagation
# ---------------------------------------------------------------------------


def test_step_a_context_survives_thread_hop():
    """Step A: OTel context captured inside http.request survives a sync thread hop.

    Simulates the FastAPI sync-route dispatch pattern:
      ASGI thread → captures OTel ctx → submits to sync thread pool →
      thread re-attaches ctx → opens agent.turn → agent.turn is child of http.request.
    """
    import concurrent.futures

    exp = _configure()

    with _tracing.span("http.request", **{"http.method": "POST"}):
        otel_ctx = copy_otel_context()

        def _sync_route(otel_context):
            tok = attach_otel_context(otel_context)
            try:
                with _tracing.span("agent.turn", turn_id="step-a-001"):
                    pass
            finally:
                detach_otel_context(tok)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_sync_route, otel_ctx).result()

    spans = exp.get_finished_spans()
    http_span = next((s for s in spans if s.name == "http.request"), None)
    turn_span = next((s for s in spans if s.name == "agent.turn"), None)

    assert http_span is not None, "http.request span missing"
    assert turn_span is not None, "agent.turn span missing"
    assert turn_span.parent is not None, "agent.turn has no parent — thread-hop propagation failed"
    assert turn_span.parent.span_id == http_span.context.span_id, (
        f"agent.turn parent {turn_span.parent.span_id} != http.request {http_span.context.span_id}"
    )


# ---------------------------------------------------------------------------
# Middleware behaviour (TestClient integration)
# ---------------------------------------------------------------------------


def test_middleware_adds_traceparent_response_header():
    """A request gets a traceparent header in the response when tracing is active."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from hachi.gateway.middleware.trace import TraceMiddleware

    _configure()  # tracing must be active for traceparent to be injected

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert "traceparent" in resp.headers, f"traceparent missing from headers: {dict(resp.headers)}"


def test_middleware_creates_http_request_span():
    """A GET /ping request produces exactly one http.request span."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from hachi.gateway.middleware.trace import TraceMiddleware

    exp = _configure()

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as client:
        client.get("/ping")

    spans = exp.get_finished_spans()
    http_spans = [s for s in spans if s.name == "http.request"]
    assert len(http_spans) == 1, f"expected 1 http.request span, got {[s.name for s in spans]}"
    attrs = dict(http_spans[0].attributes or {})
    assert attrs.get("http.method") == "GET"


def test_middleware_inbound_traceparent_parents_http_span():
    """An inbound traceparent causes the http.request span to be a child of the remote span."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from hachi.gateway.middleware.trace import TraceMiddleware

    exp = _configure()

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    # A well-formed W3C traceparent.
    remote_traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

    with TestClient(app) as client:
        client.get("/ping", headers={"traceparent": remote_traceparent})

    spans = exp.get_finished_spans()
    http_span = next((s for s in spans if s.name == "http.request"), None)
    assert http_span is not None
    assert http_span.parent is not None, (
        "http.request span has no parent despite inbound traceparent"
    )
    # The parent trace_id must match the remote traceparent's trace id.
    expected_trace_id = int("0af7651916cd43dd8448eb211c80319c", 16)
    assert http_span.parent.trace_id == expected_trace_id


def test_middleware_malformed_traceparent_creates_new_root():
    """A malformed traceparent does not crash; a fresh root span is created."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from hachi.gateway.middleware.trace import TraceMiddleware

    exp = _configure()

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as client:
        resp = client.get("/ping", headers={"traceparent": "not-a-valid-traceparent"})

    assert resp.status_code == 200
    spans = exp.get_finished_spans()
    http_spans = [s for s in spans if s.name == "http.request"]
    assert len(http_spans) == 1
    # A fresh root has no parent.
    assert http_spans[0].parent is None


def test_middleware_noop_when_tracing_off():
    """When tracing is not configured the middleware is transparent — no error, no spans."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from hachi.gateway.middleware.trace import TraceMiddleware

    assert not _tracing.is_active()

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as client:
        resp = client.get("/ping")

    assert resp.status_code == 200
