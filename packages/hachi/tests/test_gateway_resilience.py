"""Regression tests for gateway resilience fixes (audit P0/P1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import (
    GatewayControlPlane,
    GatewayEvent,
    GatewayProtocolError,
)
from hachi.gateway.fastapi_app import create_gateway_app

_CONNECT = {"client_id": "c", "surface": "tui", "protocol_version": "1.0", "capabilities": []}


def test_failed_boot_releases_session_slot() -> None:
    def boom(_session_id, _req):
        raise RuntimeError("boot failed")

    cp = GatewayControlPlane(on_connect=boom, max_active_sessions=1)

    with pytest.raises(RuntimeError):
        cp.create_session(**_CONNECT)

    # If the slot had leaked, this second attempt would raise GatewayProtocolError
    # ("Maximum active sessions reached") instead of the boot RuntimeError.
    with pytest.raises(RuntimeError):
        cp.create_session(**_CONNECT)


def test_sse_stream_closes_gracefully_when_session_vanishes_midstream() -> None:
    state = {"n": 0}

    def read_events(_sid, _after, _limit):
        state["n"] += 1
        if state["n"] == 1:
            return [GatewayEvent(sequence=1, event_type="tool.call.started", payload={}, time="t")]
        raise GatewayProtocolError("Unknown session_id")  # session closed mid-stream

    cp = GatewayControlPlane(read_events=read_events)
    app = create_gateway_app(cp)
    with TestClient(app) as client:
        session_id = client.post("/sessions", json=_CONNECT).json()["session_id"]
        with client.stream(
            "GET",
            f"/sessions/{session_id}/stream",
            params={"poll_interval": 0, "max_idle_cycles": 5},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
    # Graceful close marker rather than an aborted/errored connection.
    assert "event: closed" in body
