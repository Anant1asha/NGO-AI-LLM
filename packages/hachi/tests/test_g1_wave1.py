"""Tests for Epic G1 Wave 1 gateway backend surface.

Covers:
- G1-T3: PUT /config/limits, POST /config/permissions/folders, POST /config/permissions/commands
- T2b: DELETE /config/permissions/folders, DELETE /config/permissions/commands
- G1-T4: POST /sessions/{id}/permissions/always-allow
- G1-T5: POST /runtime/mcp/register
- G1-T6: GET /skills/kennel, POST /skills/add
- G1-T7: session resume wiring (_InProcessGatewayRuntime._pending_resume_session_id)
- G1-T8: hachi serve StaticFiles mount
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cp(**kwargs: Any) -> GatewayControlPlane:
    """Construct a GatewayControlPlane with only the supplied handlers."""
    return GatewayControlPlane(**kwargs)


def _app(**kwargs: Any) -> TestClient:
    return TestClient(create_gateway_app(_cp(**kwargs)))


# ---------------------------------------------------------------------------
# G1-T3 — PUT /config/limits
# ---------------------------------------------------------------------------


def test_put_config_limits_returns_200() -> None:
    result: list[dict] = []

    def _stub(payload: dict) -> dict:
        result.append(payload)
        return {"limits": {"max_turn_cost_usd": 1.0, "max_session_cost_usd": 5.0}}

    client = _app(update_limits=_stub)
    resp = client.put("/config/limits", json={"per_task_cap_usd": 1.0, "daily_cap_usd": 5.0})
    assert resp.status_code == 200
    assert result[0]["per_task_cap_usd"] == 1.0
    assert result[0]["daily_cap_usd"] == 5.0


def test_put_config_limits_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.put("/config/limits", json={"per_task_cap_usd": 1.0})
    assert resp.status_code == 503


def test_put_config_limits_empty_body_accepted() -> None:
    """PUT /config/limits with an empty body must be valid (all fields optional)."""
    client = _app(update_limits=lambda p: {"limits": {}})
    resp = client.put("/config/limits", json={})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# G1-T3 — POST /config/permissions/folders
# ---------------------------------------------------------------------------


def test_post_allowed_folder_returns_200() -> None:
    received: list[str] = []

    def _stub(path: str) -> dict:
        received.append(path)
        return {"ok": True, "path": path, "modified": True}

    client = _app(add_allowed_folder=_stub)
    resp = client.post("/config/permissions/folders", json={"path": "/home/user/projects"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "/home/user/projects" in data["path"]


def test_post_allowed_folder_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.post("/config/permissions/folders", json={"path": "/tmp"})
    assert resp.status_code == 503


def test_post_allowed_folder_rejects_missing_body() -> None:
    client = _app(add_allowed_folder=lambda p: {"ok": True, "path": p, "modified": True})
    resp = client.post("/config/permissions/folders", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# G1-T3 — POST /config/permissions/commands
# ---------------------------------------------------------------------------


def test_post_allowed_command_returns_200() -> None:
    received: list[str] = []

    def _stub(cmd: str) -> dict:
        received.append(cmd)
        return {"ok": True, "command": cmd, "modified": True}

    client = _app(add_allowed_command=_stub)
    resp = client.post("/config/permissions/commands", json={"command": "git"})
    assert resp.status_code == 200
    assert received[0] == "git"


def test_post_allowed_command_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.post("/config/permissions/commands", json={"command": "ls"})
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# G1-T4 — POST /sessions/{id}/permissions/always-allow
# ---------------------------------------------------------------------------


def test_always_allow_sentinel_current_returns_200() -> None:
    received: list[tuple] = []

    def _stub(session_id: str, request: str, action: str) -> dict:
        received.append((session_id, request, action))
        return {"ok": True, "request": request, "action": action}

    client = _app(add_always_allow=_stub)
    resp = client.post(
        "/sessions/current/permissions/always-allow",
        json={"request": "/home/user/doc.txt", "action": "read"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert received[0][0] == "current"
    assert received[0][2] == "read"


def test_always_allow_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.post(
        "/sessions/current/permissions/always-allow",
        json={"request": "x", "action": "read"},
    )
    assert resp.status_code == 503


def test_always_allow_missing_fields_returns_422() -> None:
    client = _app(add_always_allow=lambda s, r, a: {"ok": True})
    resp = client.post(
        "/sessions/current/permissions/always-allow",
        json={"request": "x"},  # missing action
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# G1-T5 — POST /runtime/mcp/register
# ---------------------------------------------------------------------------


def test_mcp_register_valid_server_returns_200() -> None:
    received: list[dict] = []

    def _stub(**kwargs) -> dict:  # type: ignore[no-untyped-def]
        received.append(kwargs)
        return {"name": kwargs["name"], "message": f"MCP server '{kwargs['name']}' registered."}

    client = _app(register_mcp_server=_stub)
    resp = client.post(
        "/runtime/mcp/register",
        json={"name": "github", "command": "npx", "args": "-y @mcp/github", "env_vars": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "github"
    assert received[0]["command"] == "npx"


def test_mcp_register_invalid_command_returns_422() -> None:
    client = _app(register_mcp_server=lambda *a: {})
    resp = client.post(
        "/runtime/mcp/register",
        json={"name": "srv", "command": "bash", "args": "run.sh"},
    )
    assert resp.status_code == 422


def test_mcp_register_invalid_name_returns_422() -> None:
    client = _app(register_mcp_server=lambda *a: {})
    resp = client.post(
        "/runtime/mcp/register",
        json={"name": "bad name!", "command": "npx", "args": "pkg"},
    )
    assert resp.status_code == 422


def test_mcp_register_shell_meta_in_args_returns_422() -> None:
    client = _app(register_mcp_server=lambda *a: {})
    resp = client.post(
        "/runtime/mcp/register",
        json={"name": "srv", "command": "npx", "args": "pkg; rm -rf /"},
    )
    assert resp.status_code == 422


def test_mcp_register_secret_env_key_returns_422() -> None:
    client = _app(register_mcp_server=lambda *a: {})
    resp = client.post(
        "/runtime/mcp/register",
        json={
            "name": "srv",
            "command": "npx",
            "args": "pkg",
            "env_vars": {"GITHUB_TOKEN": "secret"},
        },
    )
    assert resp.status_code == 422


def test_mcp_register_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.post(
        "/runtime/mcp/register",
        json={"name": "srv", "command": "npx", "args": "pkg"},
    )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# G1-T6 — GET /skills/kennel + POST /skills/add
# ---------------------------------------------------------------------------


def test_kennel_returns_list() -> None:
    stub = [
        {"id": "research", "name": "Deep Research", "description": "", "version": "", "tags": []}
    ]
    client = _app(get_kennel=lambda: stub)
    resp = client.get("/skills/kennel")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "research"


def test_kennel_returns_empty_when_not_attached() -> None:
    client = _app()
    resp = client.get("/skills/kennel")
    assert resp.status_code == 200
    assert resp.json() == []


def test_skill_add_returns_ok() -> None:
    received: list[str] = []

    def _stub(kennel_id: str) -> dict:
        received.append(kennel_id)
        return {"ok": True, "kennel_id": kennel_id, "installed": True}

    client = _app(add_skill=_stub)
    resp = client.post("/skills/add", json={"kennel_id": "research"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert received[0] == "research"


def test_skill_add_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.post("/skills/add", json={"kennel_id": "research"})
    assert resp.status_code == 503


def test_skill_add_missing_kennel_id_returns_422() -> None:
    client = _app(add_skill=lambda k: {"ok": True})
    resp = client.post("/skills/add", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# G1-T7 — Session resume wiring
# ---------------------------------------------------------------------------


def test_pending_resume_session_id_consumed_on_first_connect() -> None:
    """The pending resume id is consumed on the first register_connection call."""
    from hachi.cli.main import _InProcessGatewayRuntime
    from hachi.gateway.control_plane import ConnectRequest

    runtime = _InProcessGatewayRuntime()
    runtime._pending_resume_session_id = "old-session-123"

    booted_resume_ids: list[str | None] = []

    def _fake_boot(session_id: str, resume_session_id: str | None = None) -> MagicMock:
        booted_resume_ids.append(resume_session_id)
        agent = MagicMock()
        agent.skill_engine = MagicMock()
        agent.vault = None
        return agent

    runtime._boot_session_agent = _fake_boot  # type: ignore[method-assign]

    req = ConnectRequest(
        client_id="test-client",
        surface="tui",
        protocol_version="1.0",
    )
    runtime.register_connection("session-new", req)

    # The pending id must have been forwarded and cleared.
    assert booted_resume_ids[0] == "old-session-123"
    assert runtime._pending_resume_session_id is None


def test_pending_resume_not_consumed_when_agents_already_exist() -> None:
    """The pending resume id is only consumed for the very first session."""
    from hachi.cli.main import _InProcessGatewayRuntime
    from hachi.gateway.control_plane import ConnectRequest

    runtime = _InProcessGatewayRuntime()
    runtime._pending_resume_session_id = "old-session-456"

    booted_resume_ids: list[str | None] = []

    def _fake_boot(session_id: str, resume_session_id: str | None = None) -> MagicMock:
        booted_resume_ids.append(resume_session_id)
        agent = MagicMock()
        agent.skill_engine = MagicMock()
        agent.vault = None
        return agent

    runtime._boot_session_agent = _fake_boot  # type: ignore[method-assign]

    # Simulate an existing agent so the pending id is not consumed.
    runtime._agents["existing"] = MagicMock()
    req = ConnectRequest(client_id="c", surface="api", protocol_version="1.0")
    runtime.register_connection("session-2", req)

    assert booted_resume_ids[0] is None
    # Pending id untouched because agents was non-empty.
    assert runtime._pending_resume_session_id == "old-session-456"


def test_update_limits_runtime_writes_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """update_limits writes max_turn_cost_usd (per-task) and max_daily_cost_usd (daily)."""
    from types import SimpleNamespace

    from hachi.cli.main import _InProcessGatewayRuntime

    class _FakeLimits:
        max_turn_cost_usd: float | None = None
        max_session_cost_usd: float | None = None
        max_daily_cost_usd: float | None = None

    class _FakeConfig:
        limits = _FakeLimits()
        provider = SimpleNamespace(
            kind="anthropic", model="haiku", base_url=None, api_key_ref=None, api_key_env=None
        )
        permissions = SimpleNamespace(tier="guided")
        memory = SimpleNamespace(enable_session_history=True, enable_semantic_memory=True)
        capabilities: dict = {}
        channels = SimpleNamespace(telegram=SimpleNamespace(allowlist=[]))

        def model_dump(self, *, mode: str = "python", exclude_none: bool = False) -> dict:
            return {
                "limits": {
                    "max_turn_cost_usd": self.limits.max_turn_cost_usd,
                    "max_session_cost_usd": self.limits.max_session_cost_usd,
                    "max_daily_cost_usd": self.limits.max_daily_cost_usd,
                }
            }

    cfg = _FakeConfig()
    written: list[Any] = []
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda c: written.append(c))

    runtime = _InProcessGatewayRuntime()
    runtime.update_limits({"per_task_cap_usd": 2.0, "daily_cap_usd": 10.0})

    assert cfg.limits.max_turn_cost_usd == 2.0
    assert cfg.limits.max_daily_cost_usd == 10.0
    assert len(written) == 1


# ---------------------------------------------------------------------------
# G1-T8 — hachi serve StaticFiles mount
# ---------------------------------------------------------------------------


def test_serve_mounts_static_files_when_dist_exists(tmp_path: Path) -> None:
    """create_gateway_app mounts StaticFiles when frontend_dist is a valid directory."""
    from hachi.gateway.fastapi_app import create_gateway_app

    # Create a minimal dist directory with an index.html carrying a marker that
    # cannot appear in any API response.
    #
    # This previously used the literal "Hachi" as the assertion — which the
    # gateway's own service descriptor ({"service": "Hachi Gateway"}) also
    # satisfies. The test therefore passed while GET / was returning JSON
    # instead of the SPA, and never verified the mount at all.
    marker = "<!--SPA-MOUNT-MARKER-->"
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(f"<html><body>{marker}</body></html>", encoding="utf-8")

    cp = GatewayControlPlane()
    app = create_gateway_app(cp, frontend_dist=dist_dir)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert marker in resp.text, (
        "GET / must serve the mounted SPA, not the service descriptor JSON: "
        f"{(resp.text or '')[:120]}"
    )


def test_serve_skips_mount_when_dist_missing() -> None:
    """create_gateway_app does NOT mount StaticFiles when frontend_dist does not exist."""
    cp = GatewayControlPlane()
    # Non-existent path — should not raise, just log a warning.
    app = create_gateway_app(cp, frontend_dist=Path("/nonexistent/path/dist"))

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# T2b — DELETE /config/permissions/folders and /config/permissions/commands
# ---------------------------------------------------------------------------


def test_delete_allowed_folder_returns_200() -> None:
    received: list[str] = []

    def _stub(path: str) -> dict:
        received.append(path)
        return {"ok": True, "path": path, "modified": True}

    client = _app(remove_allowed_folder=_stub)
    resp = client.request(
        "DELETE",
        "/config/permissions/folders",
        json={"path": "/home/user/projects"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert received[0] == "/home/user/projects"


def test_delete_allowed_folder_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.request("DELETE", "/config/permissions/folders", json={"path": "/tmp"})
    assert resp.status_code == 503


def test_delete_allowed_command_returns_200() -> None:
    received: list[str] = []

    def _stub(cmd: str) -> dict:
        received.append(cmd)
        return {"ok": True, "command": cmd, "modified": True}

    client = _app(remove_allowed_command=_stub)
    resp = client.request(
        "DELETE",
        "/config/permissions/commands",
        json={"command": "npm"},
    )
    assert resp.status_code == 200
    assert received[0] == "npm"


def test_delete_allowed_command_returns_503_when_not_attached() -> None:
    client = _app()
    resp = client.request("DELETE", "/config/permissions/commands", json={"command": "git"})
    assert resp.status_code == 503
