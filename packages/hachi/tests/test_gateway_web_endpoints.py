"""Tests for the six new web UI HTTP endpoint groups (#1–#6).

Each test builds a ``GatewayControlPlane`` with a stub callable,
wraps it in ``create_gateway_app``, and uses ``TestClient`` to verify
route wiring and response shapes.  No live agent is needed.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app  # noqa: F401 (used via TestClient)

# ---------------------------------------------------------------------------
# #1 GET /skills
# ---------------------------------------------------------------------------


def test_skills_returns_list_from_stub() -> None:
    stub = [
        {
            "name": "deep_research",
            "role": "researcher",
            "keyword_count": 12,
            "use_count": 3,
            "last_used": "2026-06-16T09:00:00+00:00",
        }
    ]
    cp = GatewayControlPlane(get_skills=lambda: stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/skills")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "deep_research"
    assert data[0]["keyword_count"] == 12


def test_skills_returns_empty_list_when_not_attached() -> None:
    cp = GatewayControlPlane()  # get_skills not wired
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/skills")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# #2a GET /memory
# ---------------------------------------------------------------------------


def test_memory_returns_groups_blocked_proposed() -> None:
    stub = {
        "groups": [
            {
                "id": "user_profile",
                "title": "About you",
                "facts": [{"id": "fact-1", "text": "Prefers dark mode", "source": "preference"}],
            }
        ],
        "blocked": [],
        "proposed": None,
    }
    cp = GatewayControlPlane(get_memory=lambda: stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/memory")
    assert response.status_code == 200
    data = response.json()
    assert "groups" in data
    assert "blocked" in data
    assert data["proposed"] is None
    assert data["groups"][0]["id"] == "user_profile"
    assert data["groups"][0]["facts"][0]["text"] == "Prefers dark mode"


def test_memory_returns_503_when_not_attached() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/memory")
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# #2b GET /memory/recall
# ---------------------------------------------------------------------------


def test_memory_recall_returns_hits_from_stub() -> None:
    stub_hits = [{"fact": "Project uses FastAPI", "score": "0.91", "src": "workspace_state"}]
    cp = GatewayControlPlane(get_memory_recall=lambda q, k: stub_hits)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/memory/recall", params={"query": "framework", "top_k": 5})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["fact"] == "Project uses FastAPI"
    assert data[0]["score"] == "0.91"


def test_memory_recall_missing_query_param_returns_422() -> None:
    cp = GatewayControlPlane(get_memory_recall=lambda q, k: [])
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/memory/recall")  # missing required query param
    assert response.status_code == 422


def test_memory_recall_returns_503_when_not_attached() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/memory/recall", params={"query": "test"})
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# #3 GET /og/graph
# ---------------------------------------------------------------------------


def test_og_graph_returns_nodes_from_stub() -> None:
    stub = {
        "nodes": [
            {
                "id": "brain",
                "name": "brain",
                "kind": "root",
                "index": 30,
                "dense": 220,
                "full": 1840,
                "deps": ["deep_research"],
            }
        ]
    }
    cp = GatewayControlPlane(get_og_graph=lambda: stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/og/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert data["nodes"][0]["kind"] == "root"
    assert data["nodes"][0]["deps"] == ["deep_research"]


def test_og_graph_returns_empty_nodes_when_not_attached() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/og/graph")
    assert response.status_code == 200
    assert response.json() == {"nodes": []}


# ---------------------------------------------------------------------------
# #4 Authoring endpoints
# ---------------------------------------------------------------------------


def test_authoring_targets_returns_list_from_stub() -> None:
    stub_targets = [
        {"name": "brain-core.og", "path": "brain-core.og", "kind": "brain", "dirty": False}
    ]
    cp = GatewayControlPlane(get_authoring_targets=lambda: stub_targets)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/authoring/targets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["name"] == "brain-core.og"
    assert data[0]["kind"] == "brain"


def test_authoring_target_returns_source_from_stub() -> None:
    stub = {"name": "brain-core.og", "source": "::brain brain-core\n->[:role=brain]\n"}
    cp = GatewayControlPlane(get_authoring_target=lambda name: stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/authoring/targets/brain-core.og")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "brain-core.og"
    assert "::brain" in data["source"]


def test_authoring_apply_returns_ok_stub() -> None:
    cp = GatewayControlPlane(
        get_authoring_targets=lambda: [
            {"name": "brain-core.og", "path": "brain-core.og", "kind": "brain", "dirty": False}
        ],
        authoring_apply=lambda name: {"ok": True, "reindexed_ms": 0},
    )
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.post("/authoring/targets/brain-core.og/apply", json={})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "reindexed_ms": 0}


def test_authoring_revert_returns_ok_stub() -> None:
    cp = GatewayControlPlane(
        get_authoring_targets=lambda: [
            {"name": "brain-core.og", "path": "brain-core.og", "kind": "brain", "dirty": False}
        ],
        authoring_revert=lambda name: {"ok": True},
    )
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.post("/authoring/targets/brain-core.og/revert", json={})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_authoring_targets_returns_503_when_not_attached() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/authoring/targets")
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# #5 GET /spend
# ---------------------------------------------------------------------------


def test_spend_returns_turns_tidies_models_from_stub() -> None:
    stub = {
        "turns": [{"n": 1, "inT": 0, "out": 320, "cost": 0.04}],
        "tidies": [{"ts": "14:32", "before": 22000, "after": 8000}],
        "models": [{"name": "claude-sonnet-4-5", "tokens": 48210, "cost": 0.41, "color": ""}],
    }
    cp = GatewayControlPlane(get_spend=lambda session_id: stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/spend")
    assert response.status_code == 200
    data = response.json()
    assert "turns" in data
    assert "tidies" in data
    assert "models" in data
    assert data["turns"][0]["n"] == 1
    assert data["tidies"][0]["before"] == 22000
    assert data["models"][0]["name"] == "claude-sonnet-4-5"


def test_spend_accepts_session_id_query_param() -> None:
    received: list[str | None] = []

    def _stub(session_id: str | None) -> dict:
        received.append(session_id)
        return {"turns": [], "tidies": [], "models": []}

    cp = GatewayControlPlane(get_spend=_stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/spend", params={"session_id": "abc-123"})
    assert response.status_code == 200
    assert received[0] == "abc-123"


def test_spend_returns_empty_when_not_attached() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.get("/spend")
    assert response.status_code == 200
    assert response.json() == {"turns": [], "tidies": [], "models": []}


# ---------------------------------------------------------------------------
# #6 PUT /capabilities/{id}/enabled
# ---------------------------------------------------------------------------


def test_capability_toggle_returns_updated_state() -> None:
    def _stub(cap_id: str, enabled: bool) -> dict:
        return {"id": cap_id, "enabled": enabled, "configured": True}

    cp = GatewayControlPlane(set_capability_enabled=_stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.put(
            "/capabilities/gmail/enabled", json={"enabled": True}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "gmail"
    assert data["enabled"] is True
    assert data["configured"] is True


def test_capability_toggle_disable() -> None:
    def _stub(cap_id: str, enabled: bool) -> dict:
        return {"id": cap_id, "enabled": enabled, "configured": False}

    cp = GatewayControlPlane(set_capability_enabled=_stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.put(
            "/capabilities/slack/enabled", json={"enabled": False}
        )
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_capability_toggle_missing_body_returns_422() -> None:
    cp = GatewayControlPlane(set_capability_enabled=lambda cap_id, enabled: {})
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        # Send empty body — missing required ``enabled`` field.
        response = client.put("/capabilities/gmail/enabled", json={})
    assert response.status_code == 422


def test_capability_toggle_returns_503_when_not_attached() -> None:
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.put("/capabilities/gmail/enabled", json={"enabled": True})
    assert response.status_code == 503
