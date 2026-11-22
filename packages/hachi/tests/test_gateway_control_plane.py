from __future__ import annotations

from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane, GatewayEvent
from hachi.gateway.fastapi_app import create_gateway_app


def test_create_session_returns_typed_payload() -> None:
    cp = GatewayControlPlane()

    response = cp.create_session(
        client_id="client-1",
        surface="tui",
        protocol_version="1.0",
        capabilities=["stream_events"],
    )

    assert response["accepted"] is True
    assert response["protocol_version"] == "1.0"
    assert response["session_id"]


def test_readiness_endpoint_returns_503_when_not_ready() -> None:
    cp = GatewayControlPlane(readiness_probe=lambda: (False, ["boot_incomplete"]))
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        readiness = client.get("/readiness")
        assert readiness.status_code == 503
        payload = readiness.json()
        assert payload["ready"] is False
        assert payload["blockers"] == ["boot_incomplete"]


def test_sessions_and_messages_endpoints_accept_valid_payload() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        session = client.post(
            "/sessions",
            json={
                "client_id": "client-2",
                "surface": "cli",
                "protocol_version": "1.0",
                "capabilities": ["health"],
            },
        )
        assert session.status_code == 200
        body = session.json()
        assert body["accepted"] is True
        assert body["session_id"]

        recent = client.get("/sessions", params={"limit": 5})
        assert recent.status_code in {200, 503}


def test_chat_endpoint_returns_response_when_runtime_attached() -> None:
    cp = GatewayControlPlane(on_chat=lambda _session_id, prompt: f"echo:{prompt}")
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        connect = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": ["events"],
            },
        )
        session_id = connect.json()["session_id"]

        response = client.post(f"/sessions/{session_id}/messages", json={"prompt": "hello"})
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == session_id
        assert body["response"] == "echo:hello"


def test_events_endpoint_returns_batched_stream() -> None:
    events = [
        GatewayEvent(
            sequence=1, event_type="boot.complete", payload={}, time="2026-05-31T00:00:00Z"
        ),
        GatewayEvent(
            sequence=2,
            event_type="tool.call.started",
            payload={"name": "memory"},
            time="2026-05-31T00:00:01Z",
        ),
    ]

    cp = GatewayControlPlane(read_events=lambda _session_id, _after, _limit: events)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        connect = client.post(
            "/sessions",
            json={
                "client_id": "client-2",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": ["events"],
            },
        )
        session_id = connect.json()["session_id"]

        payload = client.get(f"/sessions/{session_id}/events", params={"after": 0, "limit": 100})
        assert payload.status_code == 200
        body = payload.json()
        assert body["session_id"] == session_id
        assert len(body["events"]) == 2
        assert body["next_sequence"] == 2


def test_session_state_endpoint_returns_snapshot() -> None:
    cp = GatewayControlPlane(
        get_session_state=lambda session_id: {"session_id": session_id, "boot_ready": True}
    )
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        connect = client.post(
            "/sessions",
            json={
                "client_id": "client-3",
                "surface": "web",
                "protocol_version": "1.0",
                "capabilities": ["session_state"],
            },
        )
        session_id = connect.json()["session_id"]

        payload = client.get(f"/sessions/{session_id}")
        assert payload.status_code == 200
        assert payload.json()["boot_ready"] is True
        assert payload.json()["session_id"] == session_id


def test_config_endpoint_round_trip_over_http() -> None:
    state = {"provider": {"kind": "anthropic", "model": "claude-haiku-4-5"}}

    def _get_config() -> dict:
        return state

    def _update_provider(payload: dict) -> dict:
        provider = payload.get("provider", {})
        state["provider"] = {
            "kind": provider.get("kind", "anthropic"),
            "model": provider.get("model", "claude-haiku-4-5"),
        }
        return state

    cp = GatewayControlPlane(get_config=_get_config, update_provider=_update_provider)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        get_resp = client.get("/config")
        assert get_resp.status_code == 200
        assert get_resp.json()["provider"]["kind"] == "anthropic"

        put_resp = client.put(
            "/config/provider",
            json={"provider": {"kind": "ollama", "model": "llama3.1:8b"}},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["provider"]["kind"] == "ollama"


def test_config_mutation_routes_require_bearer_token_when_configured() -> None:
    state = {
        "provider": {"kind": "anthropic", "model": "claude-haiku-4-5", "base_url": None},
        "permissions": {"tier": "guided"},
    }

    def _update_provider(payload: dict) -> dict:
        provider = payload.get("provider", {})
        state["provider"] = {
            "kind": provider.get("kind", state["provider"]["kind"]),
            "model": provider.get("model", state["provider"]["model"]),
            "base_url": provider.get("base_url"),
        }
        return state

    def _update_permissions(payload: dict) -> dict:
        permissions = payload.get("permissions", {})
        state["permissions"] = {"tier": permissions.get("tier", "guided")}
        return state

    cp = GatewayControlPlane(
        update_provider=_update_provider, update_permissions=_update_permissions
    )
    app = create_gateway_app(cp, auth_token="secret-token")

    with TestClient(app) as client:
        denied_provider = client.put(
            "/config/provider",
            json={"provider": {"kind": "ollama", "model": "llama3.1:8b"}},
        )
        assert denied_provider.status_code == 401

        allowed_provider = client.put(
            "/config/provider",
            json={"provider": {"kind": "ollama", "model": "llama3.1:8b"}},
            headers={"Authorization": "Bearer secret-token"},
        )
        assert allowed_provider.status_code == 200
        assert allowed_provider.json()["provider"]["kind"] == "ollama"

        denied_permissions = client.put(
            "/config/permissions",
            json={"permissions": {"tier": "unrestricted"}},
        )
        assert denied_permissions.status_code == 401

        allowed_permissions = client.put(
            "/config/permissions",
            json={"permissions": {"tier": "unrestricted"}},
            headers={"Authorization": "Bearer secret-token"},
        )
        assert allowed_permissions.status_code == 200
        assert allowed_permissions.json()["permissions"]["tier"] == "unrestricted"


def test_runtime_events_endpoint_returns_503_when_not_attached() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/runtime/events", params={"limit": 10})
        assert response.status_code == 503
        payload = response.json()
        assert payload["code"] == "service_unavailable"


def test_openapi_contains_required_route_groups() -> None:
    app = create_gateway_app(GatewayControlPlane())
    with TestClient(app) as client:
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        payload = schema.json()
        paths = payload["paths"]
        assert "/health" in paths
        assert "/readiness" in paths
        assert "/sessions" in paths
        assert "/sessions/{session_id}/messages" in paths
        assert "/sessions/{session_id}" in paths
        assert "/runtime/events" in paths
        assert "/config" in paths
        assert "/setup/apply" in paths


def test_protected_routes_require_bearer_token_when_configured() -> None:
    app = create_gateway_app(GatewayControlPlane(), auth_token="secret-token")
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        readiness = client.get("/readiness")
        assert readiness.status_code == 200

        denied = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        assert denied.status_code == 401

        allowed = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": [],
            },
            headers={"Authorization": "Bearer secret-token"},
        )
        assert allowed.status_code == 200


def test_session_creation_respects_max_active_sessions() -> None:
    cp = GatewayControlPlane(max_active_sessions=1)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        first = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "cli",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        assert first.status_code == 200

        second = client.post(
            "/sessions",
            json={
                "client_id": "client-2",
                "surface": "cli",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        assert second.status_code == 400
        assert "Maximum active sessions reached" in second.json()["message"]


def test_chat_rejects_oversized_prompt() -> None:
    cp = GatewayControlPlane(on_chat=lambda _session_id, prompt: prompt, max_prompt_chars=8)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        connect = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        session_id = connect.json()["session_id"]

        response = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "0123456789"},
        )
        assert response.status_code == 400
        assert "prompt exceeds max length" in response.json()["message"]


def test_delete_session_endpoint_closes_connection() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        connect = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        session_id = connect.json()["session_id"]

        closed = client.delete(f"/sessions/{session_id}")
        assert closed.status_code == 200
        assert closed.json() == {"session_id": session_id, "closed": True}

        missing = client.get(f"/sessions/{session_id}")
        assert missing.status_code == 400


def test_invalid_session_payloads_fail_closed() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        blank_client = client.post(
            "/sessions",
            json={
                "client_id": "   ",
                "surface": "cli",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        assert blank_client.status_code == 400
        assert blank_client.json()["code"] == "protocol_error"

        bad_protocol = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "cli",
                "protocol_version": "9.9",
                "capabilities": [],
            },
        )
        assert bad_protocol.status_code == 400
        assert "Unsupported protocol_version" in bad_protocol.json()["message"]

        wrong_capabilities_type = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "cli",
                "protocol_version": "1.0",
                "capabilities": ["ok", 5],
            },
        )
        assert wrong_capabilities_type.status_code == 422
        assert wrong_capabilities_type.json()["code"] == "validation_error"


def test_invalid_message_and_event_payloads_fail_closed() -> None:
    cp = GatewayControlPlane(on_chat=lambda _session_id, prompt: prompt)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        connect = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        session_id = connect.json()["session_id"]

        blank_prompt = client.post(f"/sessions/{session_id}/messages", json={"prompt": "   "})
        assert blank_prompt.status_code == 400
        assert blank_prompt.json()["code"] == "protocol_error"

        bad_prompt_type = client.post(f"/sessions/{session_id}/messages", json={"prompt": 42})
        assert bad_prompt_type.status_code == 422
        assert bad_prompt_type.json()["code"] == "validation_error"

        negative_after = client.get(
            f"/sessions/{session_id}/events", params={"after": -1, "limit": 10}
        )
        assert negative_after.status_code == 422

        oversized_limit = client.get(
            f"/sessions/{session_id}/events",
            params={"after": 0, "limit": 9999},
        )
        assert oversized_limit.status_code == 422


def test_out_of_order_and_duplicate_operations_are_rejected() -> None:
    cp = GatewayControlPlane(on_chat=lambda _session_id, prompt: f"echo:{prompt}")
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        unknown_session = "00000000-0000-0000-0000-000000000000"

        chat_before_connect = client.post(
            f"/sessions/{unknown_session}/messages",
            json={"prompt": "hello"},
        )
        assert chat_before_connect.status_code == 400
        assert "Unknown session_id" in chat_before_connect.json()["message"]

        connect = client.post(
            "/sessions",
            json={
                "client_id": "client-1",
                "surface": "tui",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        session_id = connect.json()["session_id"]

        first_delete = client.delete(f"/sessions/{session_id}")
        assert first_delete.status_code == 200

        second_delete = client.delete(f"/sessions/{session_id}")
        assert second_delete.status_code == 400
        assert "Unknown session_id" in second_delete.json()["message"]

        events_after_delete = client.get(
            f"/sessions/{session_id}/events", params={"after": 0, "limit": 10}
        )
        assert events_after_delete.status_code == 400
        assert "Unknown session_id" in events_after_delete.json()["message"]


def test_session_churn_respects_limits_and_recovers_capacity() -> None:
    cp = GatewayControlPlane(max_active_sessions=2, max_prompt_chars=8, on_chat=lambda _id, p: p)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        sessions: list[str] = []
        for idx in range(2):
            response = client.post(
                "/sessions",
                json={
                    "client_id": f"client-{idx}",
                    "surface": "cli",
                    "protocol_version": "1.0",
                    "capabilities": [],
                },
            )
            assert response.status_code == 200
            sessions.append(response.json()["session_id"])

        over_limit = client.post(
            "/sessions",
            json={
                "client_id": "client-over",
                "surface": "cli",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        assert over_limit.status_code == 400

        near_limit_prompt = client.post(
            f"/sessions/{sessions[0]}/messages",
            json={"prompt": "12345678"},
        )
        assert near_limit_prompt.status_code == 200
        assert near_limit_prompt.json()["response"] == "12345678"

        over_limit_prompt = client.post(
            f"/sessions/{sessions[0]}/messages",
            json={"prompt": "123456789"},
        )
        assert over_limit_prompt.status_code == 400

        closed = client.delete(f"/sessions/{sessions[1]}")
        assert closed.status_code == 200

        replacement = client.post(
            "/sessions",
            json={
                "client_id": "client-new",
                "surface": "cli",
                "protocol_version": "1.0",
                "capabilities": [],
            },
        )
        assert replacement.status_code == 200
