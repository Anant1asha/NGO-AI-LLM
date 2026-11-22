"""Tests for P1-05: 500-handler hygiene.

The catch-all exception handler must:
1. Return HTTP 500 with a generic message (no exception text/paths)
2. Include a correlation_id in the response details
3. Log the full exception server-side (not tested here — that's implementation detail)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app


def _app_with_exploding_route() -> tuple:
    """Return a FastAPI TestClient whose /health endpoint raises an exception."""
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    # Inject a route that blows up with sensitive detail
    from fastapi import APIRouter
    boom = APIRouter()

    @boom.get("/test-boom")
    async def explode():
        raise RuntimeError("secret internal path: /etc/shadow; token=abc123")

    app.include_router(boom)
    return TestClient(app, raise_server_exceptions=False)


def test_500_response_has_generic_message() -> None:
    client = _app_with_exploding_route()
    resp = client.get("/test-boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["message"] == "An unexpected error occurred."
    # Exception text must NOT appear in the response
    assert "secret" not in resp.text
    assert "/etc/shadow" not in resp.text
    assert "abc123" not in resp.text


def test_500_response_has_correlation_id() -> None:
    client = _app_with_exploding_route()
    resp = client.get("/test-boom")
    assert resp.status_code == 500
    body = resp.json()
    assert "correlation_id" in (body.get("details") or {})
    correlation_id = body["details"]["correlation_id"]
    # Must be a UUID-like string
    assert len(correlation_id) == 36
    assert correlation_id.count("-") == 4


def test_500_response_code_is_internal_error() -> None:
    client = _app_with_exploding_route()
    resp = client.get("/test-boom")
    assert resp.json()["code"] == "internal_error"
