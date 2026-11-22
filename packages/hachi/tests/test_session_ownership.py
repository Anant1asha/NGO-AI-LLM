"""Integration tests for C1 — session ownership enforcement.

Verifies that:
- Sessions created with token A are inaccessible to token B (403).
- Token A can access its own sessions (200).
- GET /sessions for token B does not list sessions owned by token A.
- Single-token deployments (both callers share the same token) continue to work.
- No-auth mode (auth_token=None) remains accessible for backward compat / tests.

Design note: a gateway instance enforces exactly one bearer token, so to simulate
two different callers we:
  (a) Verify ownership at the control-plane level directly (unit layer), and
  (b) Verify HTTP 403 responses by manually stamping a session with a *different*
      token hash than the authenticated caller's, using set_session_owner().
"""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOKEN_A = "token-owner-aaa"
_TOKEN_B = "token-owner-bbb"
_HASH_A = hashlib.sha256(_TOKEN_A.encode()).hexdigest()
_HASH_B = hashlib.sha256(_TOKEN_B.encode()).hexdigest()

_CONNECT = {
    "client_id": "c",
    "surface": "tui",
    "protocol_version": "1.0",
    "capabilities": [],
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# C1-unit — control-plane ownership methods work correctly
# ---------------------------------------------------------------------------


class TestControlPlaneOwnership:
    """Direct unit tests for GatewayControlPlane.set/get_session_owner."""

    def test_set_and_get_owner(self) -> None:
        cp = GatewayControlPlane()
        sess = cp.create_session(
            client_id="c", surface="tui", protocol_version="1.0", capabilities=[]
        )
        sid = sess["session_id"]
        assert cp.get_session_owner(sid) is None  # not set yet

        cp.set_session_owner(sid, _HASH_A)
        assert cp.get_session_owner(sid) == _HASH_A

    def test_get_owner_unknown_session_returns_none(self) -> None:
        cp = GatewayControlPlane()
        assert cp.get_session_owner("nonexistent") is None


# ---------------------------------------------------------------------------
# C1-http — HTTP 403 when session is owned by a different hash
# ---------------------------------------------------------------------------
#
# Strategy: create the gateway with TOKEN_A, create a session (which gets
# owner=HASH_A stamped), then immediately overwrite the owner with HASH_B.
# Now TOKEN_A's hash no longer matches, so its requests get 403 — this
# exercises the same code path as a real cross-caller scenario.


def _session_stamped_with_b() -> tuple[TestClient, str]:
    """Return (client, sid) where the session is owned by HASH_B but the client uses TOKEN_A."""
    cp = GatewayControlPlane(
        on_chat=lambda _sid, p: f"echo:{p}",
        read_events=lambda _sid, _after, _limit: [],
        get_session_state=lambda sid: {"session_id": sid},
    )
    app = create_gateway_app(cp, auth_token=_TOKEN_A)
    client = TestClient(app)
    # Create with TOKEN_A (owner=HASH_A)
    resp = client.post("/sessions", json=_CONNECT, headers=_auth(_TOKEN_A))
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    # Now forcibly overwrite owner to HASH_B → TOKEN_A callers will get 403
    cp.set_session_owner(sid, _HASH_B)
    return client, sid


class TestCrossCallerDenied:
    """Routes must return 403 when caller's hash differs from session's owner hash."""

    def test_get_session_forbidden(self) -> None:
        client, sid = _session_stamped_with_b()
        resp = client.get(f"/sessions/{sid}", headers=_auth(_TOKEN_A))
        assert resp.status_code == 403

    def test_post_message_forbidden(self) -> None:
        client, sid = _session_stamped_with_b()
        resp = client.post(
            f"/sessions/{sid}/messages",
            json={"prompt": "hi"},
            headers=_auth(_TOKEN_A),
        )
        assert resp.status_code == 403

    def test_delete_session_forbidden(self) -> None:
        client, sid = _session_stamped_with_b()
        resp = client.delete(f"/sessions/{sid}", headers=_auth(_TOKEN_A))
        assert resp.status_code == 403

    def test_events_forbidden(self) -> None:
        client, sid = _session_stamped_with_b()
        resp = client.get(f"/sessions/{sid}/events", headers=_auth(_TOKEN_A))
        assert resp.status_code == 403

    def test_stream_forbidden(self) -> None:
        client, sid = _session_stamped_with_b()
        resp = client.get(f"/sessions/{sid}/stream", headers=_auth(_TOKEN_A))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# C1-http — owner can access their own session
# ---------------------------------------------------------------------------


class TestOwnerAllowed:
    """The token that created the session must retain full access."""

    def test_owner_can_get_session(self) -> None:
        cp = GatewayControlPlane(get_session_state=lambda sid: {"session_id": sid, "ok": True})
        app = create_gateway_app(cp, auth_token=_TOKEN_A)
        client = TestClient(app)
        resp = client.post("/sessions", json=_CONNECT, headers=_auth(_TOKEN_A))
        sid = resp.json()["session_id"]

        r = client.get(f"/sessions/{sid}", headers=_auth(_TOKEN_A))
        assert r.status_code == 200

    def test_owner_can_post_message(self) -> None:
        cp = GatewayControlPlane(on_chat=lambda _sid, p: f"echo:{p}")
        app = create_gateway_app(cp, auth_token=_TOKEN_A)
        client = TestClient(app)
        resp = client.post("/sessions", json=_CONNECT, headers=_auth(_TOKEN_A))
        sid = resp.json()["session_id"]

        r = client.post(
            f"/sessions/{sid}/messages", json={"prompt": "hello"}, headers=_auth(_TOKEN_A)
        )
        assert r.status_code == 200
        assert r.json()["response"] == "echo:hello"

    def test_owner_can_delete_session(self) -> None:
        cp = GatewayControlPlane()
        app = create_gateway_app(cp, auth_token=_TOKEN_A)
        client = TestClient(app)
        resp = client.post("/sessions", json=_CONNECT, headers=_auth(_TOKEN_A))
        sid = resp.json()["session_id"]

        r = client.delete(f"/sessions/{sid}", headers=_auth(_TOKEN_A))
        assert r.status_code == 200
        assert r.json()["closed"] is True


# ---------------------------------------------------------------------------
# C1-http — GET /sessions scoped to caller
# ---------------------------------------------------------------------------


class TestListSessionsScoped:
    """GET /sessions must not return sessions owned by a different token."""

    def test_list_excludes_sessions_owned_by_other_caller(self) -> None:
        # We use a mutable list to give get_recent_sessions dynamic access to
        # sessions created after the control plane is built.
        session_records: list[dict] = []

        def _recent(limit: int) -> list[dict]:
            return session_records[:limit]

        cp = GatewayControlPlane(get_recent_sessions=_recent)
        app = create_gateway_app(cp, auth_token=_TOKEN_A)
        client = TestClient(app)

        # Create a session with TOKEN_A (owner = HASH_A)
        r1 = client.post("/sessions", json=_CONNECT, headers=_auth(_TOKEN_A))
        assert r1.status_code == 200
        sid_a = r1.json()["session_id"]
        session_records.append({"session_id": sid_a, "title": "A"})

        # Directly create a second session and stamp it as owned by HASH_B
        s2 = cp.create_session(
            client_id="b", surface="tui", protocol_version="1.0", capabilities=[]
        )
        sid_b = s2["session_id"]
        cp.set_session_owner(sid_b, _HASH_B)
        session_records.append({"session_id": sid_b, "title": "B"})

        # TOKEN_A's list should include sid_a but not sid_b
        r_list = client.get("/sessions", headers=_auth(_TOKEN_A))
        assert r_list.status_code == 200
        body = r_list.json()
        assert isinstance(body, list)
        ids = [s.get("session_id") or s.get("id") or "" for s in body]
        # sid_a (owned by HASH_A = TOKEN_A's hash) must be visible
        assert sid_a in ids
        # sid_b (owned by HASH_B != HASH_A) must be filtered out
        assert sid_b not in ids


# ---------------------------------------------------------------------------
# C1-http — single-token deployment: same token = same hash = no breakage
# ---------------------------------------------------------------------------


class TestSingleTokenDeployment:
    """When all callers use the same token, ownership never blocks access."""

    def test_same_token_can_access_own_session(self) -> None:
        _TOKEN = "shared-single-token"
        cp = GatewayControlPlane(on_chat=lambda _sid, p: f"pong:{p}")
        app = create_gateway_app(cp, auth_token=_TOKEN)
        client = TestClient(app)

        resp = client.post("/sessions", json=_CONNECT, headers=_auth(_TOKEN))
        sid = resp.json()["session_id"]

        r1 = client.post(
            f"/sessions/{sid}/messages", json={"prompt": "a"}, headers=_auth(_TOKEN)
        )
        r2 = client.post(
            f"/sessions/{sid}/messages", json={"prompt": "b"}, headers=_auth(_TOKEN)
        )
        assert r1.status_code == 200
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# C1-http — no-auth mode: all sessions accessible (backward compat)
# ---------------------------------------------------------------------------


class TestNoAuthMode:
    """In no-auth mode (auth_token=None), ownership is not enforced."""

    def test_no_auth_can_access_any_session(self) -> None:
        cp = GatewayControlPlane()
        app = create_gateway_app(cp, auth_token=None)
        client = TestClient(app)

        resp = client.post("/sessions", json=_CONNECT)
        assert resp.status_code == 200
        sid = resp.json()["session_id"]

        r = client.delete(f"/sessions/{sid}")
        assert r.status_code == 200
