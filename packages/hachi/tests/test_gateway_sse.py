"""Tests for the gateway SSE streaming endpoint (C2)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane, GatewayEvent
from hachi.gateway.fastapi_app import create_gateway_app

_EVENTS = [
    GatewayEvent(
        sequence=1, event_type="tool.call.started", payload={"name": "read_file"}, time="t"
    ),
    GatewayEvent(sequence=2, event_type="text.stream.delta", payload={"text": "hi"}, time="t"),
]


def _read_events(_session_id: str, after: int, limit: int) -> list[GatewayEvent]:
    return [e for e in _EVENTS if e.sequence > after][:limit]


def _client_with_session() -> tuple[TestClient, str]:
    cp = GatewayControlPlane(read_events=_read_events)
    app = create_gateway_app(cp)
    client = TestClient(app)
    resp = client.post(
        "/sessions",
        json={
            "client_id": "c1",
            "surface": "web",
            "protocol_version": "1.0",
            "capabilities": ["events"],
        },
    )
    assert resp.status_code == 200
    return client, resp.json()["session_id"]


def test_stream_pushes_buffered_events_then_closes() -> None:
    client, session_id = _client_with_session()
    with client.stream(
        "GET",
        f"/sessions/{session_id}/stream",
        params={"poll_interval": 0, "max_idle_cycles": 1},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = "".join(response.iter_text())

    # SSE framing + both events delivered, newest cursor advanced.
    assert ": connected" in body
    assert "event: tool.call.started" in body
    assert "read_file" in body
    assert "id: 2" in body


def test_stream_resumes_after_cursor() -> None:
    client, session_id = _client_with_session()
    with client.stream(
        "GET",
        f"/sessions/{session_id}/stream",
        params={"after": 1, "poll_interval": 0, "max_idle_cycles": 1},
    ) as response:
        body = "".join(response.iter_text())

    # Only the event after sequence 1 should appear.
    assert "text.stream.delta" in body
    assert "tool.call.started" not in body


def test_stream_unknown_session_is_rejected() -> None:
    cp = GatewayControlPlane(read_events=_read_events)
    app = create_gateway_app(cp)
    with TestClient(app) as client:
        response = client.get("/sessions/does-not-exist/stream", params={"max_idle_cycles": 1})
        assert response.status_code == 400


def test_stream_response_carries_proxy_buffering_headers() -> None:
    """StreamingResponse must disable proxy buffering and cache on the SSE route (B1)."""
    client, session_id = _client_with_session()
    with client.stream(
        "GET",
        f"/sessions/{session_id}/stream",
        params={"poll_interval": 0, "max_idle_cycles": 1},
    ) as response:
        assert response.status_code == 200
        assert response.headers.get("x-accel-buffering") == "no"
        assert response.headers.get("cache-control") == "no-cache"
        # Consume the body so the context manager exits cleanly.
        response.read()
