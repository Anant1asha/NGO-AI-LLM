"""Tests for P1-4 — POST /sessions/{id}/interrupt server-side turn cancellation.

Covers:
1. interrupt() on a live session with on_interrupt wired calls the handler and returns
   {"interrupted": true}.
2. interrupt() on an unknown session returns {"interrupted": false} (safe, no 5xx).
3. POST /sessions/{id}/interrupt route — live session with on_interrupt attached.
4. POST /sessions/{id}/interrupt route — unknown session returns 200 {"interrupted": false}.
5. Ownership enforcement — 403 when a different bearer token hits the route.
6. GatewayControlPlane.interrupt() swallows handler exceptions and returns
   {"interrupted": false} (never leaks a 5xx).
7. on_interrupt=None (runtime not attached) returns {"interrupted": false}.
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(client: Any, **extra: Any) -> str:
    """Create a session via POST /sessions and return the session_id."""
    resp = client.post(
        "/sessions",
        json={
            "client_id": "test-client",
            "surface": "web",
            "protocol_version": "1.0",
            "capabilities": [],
            **extra,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# Unit tests — GatewayControlPlane.interrupt()
# ---------------------------------------------------------------------------


def test_interrupt_live_session_calls_handler_and_returns_true() -> None:
    """When on_interrupt is wired and session is live, interrupt() delivers the signal."""
    calls: list[str] = []

    def _on_interrupt(session_id: str) -> dict[str, Any]:
        calls.append(session_id)
        return {"interrupted": True}

    cp = GatewayControlPlane(on_interrupt=_on_interrupt)
    sid = cp.create_session(client_id="c1", surface="tui")["session_id"]

    result = cp.interrupt(sid)

    assert result == {"interrupted": True}
    assert calls == [sid]


def test_interrupt_unknown_session_returns_false() -> None:
    """interrupt() on an unknown session_id is safe — returns {"interrupted": False}."""
    cp = GatewayControlPlane()

    result = cp.interrupt("non-existent-session-id")

    assert result == {"interrupted": False}


def test_interrupt_no_runtime_attached_returns_false() -> None:
    """When on_interrupt is None (standalone gateway), interrupt() is safe."""
    cp = GatewayControlPlane(on_interrupt=None)
    sid = cp.create_session(client_id="c2", surface="web")["session_id"]

    result = cp.interrupt(sid)

    assert result == {"interrupted": False}


def test_interrupt_handler_exception_returns_false_not_500() -> None:
    """A buggy on_interrupt handler must not propagate — returns {"interrupted": false}."""

    def _bad_handler(_session_id: str) -> dict[str, Any]:
        raise RuntimeError("boom")

    cp = GatewayControlPlane(on_interrupt=_bad_handler)
    sid = cp.create_session(client_id="c3", surface="web")["session_id"]

    result = cp.interrupt(sid)

    assert result == {"interrupted": False}


# ---------------------------------------------------------------------------
# Integration tests — POST /sessions/{id}/interrupt via HTTP
# ---------------------------------------------------------------------------


def test_interrupt_route_live_session_returns_interrupted_true() -> None:
    """POST /sessions/{id}/interrupt on a live session returns 200 {"interrupted": true}."""
    cancel_record: list[str] = []

    def _on_interrupt(session_id: str) -> dict[str, Any]:
        cancel_record.append(session_id)
        return {"interrupted": True}

    cp = GatewayControlPlane(on_interrupt=_on_interrupt)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        sid = _make_session(client)
        resp = client.post(f"/sessions/{sid}/interrupt")

    assert resp.status_code == 200
    assert resp.json() == {"interrupted": True}
    assert cancel_record == [sid]


def test_interrupt_route_unknown_session_returns_interrupted_false() -> None:
    """POST /sessions/{unknown}/interrupt returns 200 {"interrupted": false} — safe."""
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        resp = client.post("/sessions/no-such-session/interrupt")

    assert resp.status_code == 200
    assert resp.json() == {"interrupted": False}


def test_interrupt_route_no_runtime_attached_returns_false() -> None:
    """When on_interrupt is None, the route still returns 200 {"interrupted": false}."""
    cp = GatewayControlPlane(on_interrupt=None)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        sid = _make_session(client)
        resp = client.post(f"/sessions/{sid}/interrupt")

    assert resp.status_code == 200
    assert resp.json() == {"interrupted": False}


def test_interrupt_route_ownership_enforced() -> None:
    """POST /sessions/{id}/interrupt is rejected (403) when ownership hash differs.

    A gateway enforces a single bearer token, so to test ownership enforcement we:
    1. Create the session with TOKEN_A (owner=HASH_A stamped).
    2. Overwrite the owner to HASH_B via set_session_owner().
    3. Calling with TOKEN_A now gets 403 because HASH_A != HASH_B.
    """
    _TOKEN_A = "token-a"
    _HASH_B = hashlib.sha256(b"token-b").hexdigest()

    cp = GatewayControlPlane()
    app = create_gateway_app(cp, auth_token=_TOKEN_A)

    with TestClient(app) as client:
        # Create session stamped with HASH_A
        sid = client.post(
            "/sessions",
            json={
                "client_id": "c",
                "surface": "web",
                "protocol_version": "1.0",
                "capabilities": [],
            },
            headers={"Authorization": f"Bearer {_TOKEN_A}"},
        ).json()["session_id"]

        # Overwrite owner to HASH_B — TOKEN_A callers now get 403
        cp.set_session_owner(sid, _HASH_B)

        denied = client.post(
            f"/sessions/{sid}/interrupt",
            headers={"Authorization": f"Bearer {_TOKEN_A}"},
        )
        assert denied.status_code == 403


def test_interrupt_route_requires_auth_when_token_configured() -> None:
    """POST /sessions/{id}/interrupt requires a bearer token when auth is configured."""
    cp = GatewayControlPlane()
    app = create_gateway_app(cp, auth_token="my-token")

    with TestClient(app) as client:
        sid = client.post(
            "/sessions",
            json={
                "client_id": "c",
                "surface": "web",
                "protocol_version": "1.0",
                "capabilities": [],
            },
            headers={"Authorization": "Bearer my-token"},
        ).json()["session_id"]

        # No token → 401
        no_auth = client.post(f"/sessions/{sid}/interrupt")
        assert no_auth.status_code == 401

        # Correct token → 200
        authed = client.post(
            f"/sessions/{sid}/interrupt",
            headers={"Authorization": "Bearer my-token"},
        )
        assert authed.status_code == 200


# ---------------------------------------------------------------------------
# Wiring smoke test — on_interrupt receives the right session_id
# ---------------------------------------------------------------------------


def test_interrupt_delivers_correct_session_id() -> None:
    """The session_id forwarded by interrupt() matches the one from create_session."""
    received: list[str] = []

    def _capture(session_id: str) -> dict[str, Any]:
        received.append(session_id)
        return {"interrupted": True}

    cp = GatewayControlPlane(on_interrupt=_capture)
    sid1 = cp.create_session(client_id="c1", surface="web")["session_id"]
    sid2 = cp.create_session(client_id="c2", surface="web")["session_id"]

    cp.interrupt(sid1)
    cp.interrupt(sid2)

    assert received == [sid1, sid2]


# ---------------------------------------------------------------------------
# Thread-safety smoke test — cancel is set on the real threading.Event
# ---------------------------------------------------------------------------


def test_interrupt_sets_cancel_event_on_real_loop() -> None:
    """interrupt_session sets the threading.Event inside a real ExecutionLoop."""
    from unittest.mock import MagicMock

    from hachi.core.loop import ExecutionLoop, ToolRegistry

    registry = ToolRegistry()
    llm = MagicMock()
    memory = MagicMock()
    loop = ExecutionLoop(
        llm_client=llm,
        registry=registry,
        memory=memory,
        base_system_prompt="test",
    )

    assert not loop._cancel_event.is_set()

    # Simulate what interrupt_session does (runtime.interrupt_session calls loop.cancel()).
    loop.cancel()

    assert loop._cancel_event.is_set()

    loop.shutdown(wait=False)
