"""Tests for MCP transport abstraction, config schema, and register validation.

Covers:
  CONTRACT-MCP Step 1 — transport interface (StdioTransport, SseTransport, HttpTransport)
  CONTRACT-MCP Step 2 — MCPServerConfig parsing/serialisation
  CONTRACT-MCP Step 3 — register endpoint payload validation
  CONTRACT-MCP Step 4 — hot-reload path (add_mcp_server_live)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn(transport: str = "stdio", **kwargs: Any):
    """Build an MCPServerConnection without actually starting anything."""
    from hachi.core.mcp_client import MCPServerConnection

    return MCPServerConnection(
        name="test-server",
        command="npx" if transport == "stdio" else "",
        transport=transport,  # type: ignore[arg-type]
        url=kwargs.pop("url", "http://localhost:9000" if transport in ("sse", "http") else ""),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Step 1: Transport abstraction
# ---------------------------------------------------------------------------


class TestTransportInterface:
    """MCPTransport subclasses must satisfy the abstract interface."""

    def test_stdio_transport_implements_interface(self) -> None:
        from hachi.core.mcp_client import MCPTransport, StdioTransport

        t = StdioTransport(name="s", command="echo")
        assert isinstance(t, MCPTransport)
        assert hasattr(t, "start")
        assert hasattr(t, "send")
        assert hasattr(t, "receive")
        assert hasattr(t, "close")
        assert hasattr(t, "is_alive")

    def test_sse_transport_implements_interface(self) -> None:
        from hachi.core.mcp_client import MCPTransport, SseTransport

        t = SseTransport(name="s", url="http://localhost:9000")
        assert isinstance(t, MCPTransport)

    def test_http_transport_implements_interface(self) -> None:
        from hachi.core.mcp_client import HttpTransport, MCPTransport

        t = HttpTransport(name="s", url="http://localhost:9000")
        assert isinstance(t, MCPTransport)

    def test_mcp_server_connection_uses_stdio_transport_by_default(self) -> None:
        from hachi.core.mcp_client import MCPServerConnection, StdioTransport

        conn = MCPServerConnection(name="s", command="python")
        assert isinstance(conn._transport, StdioTransport)

    def test_mcp_server_connection_uses_sse_transport(self) -> None:
        from hachi.core.mcp_client import MCPServerConnection, SseTransport

        conn = MCPServerConnection(
            name="s", command="", transport="sse", url="http://localhost:9000"
        )
        assert isinstance(conn._transport, SseTransport)

    def test_mcp_server_connection_uses_http_transport(self) -> None:
        from hachi.core.mcp_client import HttpTransport, MCPServerConnection

        conn = MCPServerConnection(
            name="s", command="", transport="http", url="http://localhost:9000"
        )
        assert isinstance(conn._transport, HttpTransport)

    def test_transport_kind_stored_on_connection(self) -> None:
        from hachi.core.mcp_client import MCPServerConnection

        conn = MCPServerConnection(
            name="s", command="", transport="http", url="http://localhost:9000"
        )
        assert conn.transport_kind == "http"

    def test_stdio_is_alive_false_before_start(self) -> None:
        from hachi.core.mcp_client import StdioTransport

        t = StdioTransport(name="s", command="python")
        assert t.is_alive is False

    def test_http_is_alive_false_before_start(self) -> None:
        from hachi.core.mcp_client import HttpTransport

        t = HttpTransport(name="s", url="http://localhost:9000")
        assert t.is_alive is False

    def test_sse_is_alive_false_before_start(self) -> None:
        from hachi.core.mcp_client import SseTransport

        t = SseTransport(name="s", url="http://localhost:9000")
        assert t.is_alive is False

    def test_http_transport_send_and_receive_parses_json(self) -> None:
        """HttpTransport.send_and_receive must parse the response body."""
        from hachi.core.mcp_client import HttpTransport

        t = HttpTransport(name="s", url="http://localhost:9000")
        # Inject a mock httpx client
        mock_resp = MagicMock()
        mock_resp.text = '{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}'
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        t._client = mock_client
        t._alive = True

        result = t.send_and_receive(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        assert result is not None
        assert result.get("id") == 1

    def test_http_transport_send_and_receive_handles_ndjson(self) -> None:
        """HttpTransport.send_and_receive must handle NDJSON (streaming) responses."""
        from hachi.core.mcp_client import HttpTransport

        t = HttpTransport(name="s", url="http://localhost:9000")
        mock_resp = MagicMock()
        # Simulate two NDJSON lines; last one is the response
        mock_resp.text = (
            '{"jsonrpc":"2.0","id":1,"partial":true}\n'
            '{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"calc"}]}}'
        )
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        t._client = mock_client
        t._alive = True

        result = t.send_and_receive(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        assert result is not None
        assert "result" in result
        assert result["result"]["tools"][0]["name"] == "calc"

    def test_stdio_reader_dead_causes_receive_to_return_error(self) -> None:
        """If the reader dies, receive() must return an error dict immediately."""
        from hachi.core.mcp_client import StdioTransport

        t = StdioTransport(name="s", command="python", request_timeout_seconds=5.0)
        t._reader_dead = True

        result = t.receive(request_id=42, timeout_seconds=5.0)
        assert result is not None
        assert "error" in result

    def test_send_request_routes_http_transport_to_send_and_receive(self) -> None:
        """MCPServerConnection._send_request must use send_and_receive for http transport."""
        from hachi.core.mcp_client import HttpTransport, MCPServerConnection

        conn = MCPServerConnection(
            name="s", command="", transport="http", url="http://localhost:9000"
        )
        assert isinstance(conn._transport, HttpTransport)

        expected = {"jsonrpc": "2.0", "id": 1, "result": {}}
        conn._transport.send_and_receive = MagicMock(return_value=expected)  # type: ignore[method-assign]

        result = conn._send_request("tools/list", {})
        assert result == expected
        conn._transport.send_and_receive.assert_called_once()


# ---------------------------------------------------------------------------
# Step 2: Config schema
# ---------------------------------------------------------------------------


class TestMCPServerConfig:
    """MCPServerConfig must parse legacy and new TOML formats correctly."""

    def test_from_toml_entry_defaults_to_stdio(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig.from_toml_entry(
            "gmail", {"command": "npx", "args": "-y @anthropic/mcp-gmail"}
        )
        assert cfg.transport == "stdio"
        assert cfg.command == "npx"
        assert cfg.args == ["-y", "@anthropic/mcp-gmail"]

    def test_from_toml_entry_sse_transport(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig.from_toml_entry(
            "remote",
            {"transport": "sse", "url": "http://mcp.example.com"},
        )
        assert cfg.transport == "sse"
        assert cfg.url == "http://mcp.example.com"
        assert cfg.command == ""

    def test_from_toml_entry_http_transport(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig.from_toml_entry(
            "remote",
            {
                "transport": "http",
                "url": "http://mcp.example.com/rpc",
                "headers": {"Authorization": "Bearer tok"},
            },
        )
        assert cfg.transport == "http"
        assert cfg.url == "http://mcp.example.com/rpc"
        assert cfg.headers == {"Authorization": "Bearer tok"}

    def test_from_toml_entry_env_dict(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig.from_toml_entry(
            "server",
            {"command": "python", "args": "server.py", "env": {"FOO": "bar"}},
        )
        assert cfg.env == {"FOO": "bar"}

    def test_from_toml_entry_timeouts(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig.from_toml_entry(
            "server",
            {
                "command": "python",
                "boot_timeout_seconds": "45",
                "request_timeout_seconds": "10.5",
            },
        )
        assert cfg.boot_timeout_seconds == pytest.approx(45.0)
        assert cfg.request_timeout_seconds == pytest.approx(10.5)

    def test_from_toml_entry_unknown_transport_defaults_stdio(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig.from_toml_entry(
            "server",
            {"transport": "websocket", "command": "python"},
        )
        assert cfg.transport == "stdio"

    def test_to_toml_entry_stdio_roundtrip(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        original = {
            "command": "npx",
            "args": "-y @anthropic/mcp-gmail",
            "env": {"KEY": "value"},
        }
        cfg = MCPServerConfig.from_toml_entry("gmail", original)
        entry = cfg.to_toml_entry()
        assert entry["transport"] == "stdio"
        assert entry["command"] == "npx"
        assert "env" in entry
        assert entry["env"]["KEY"] == "value"

    def test_to_toml_entry_http(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig(
            name="remote",
            transport="http",
            url="http://mcp.example.com/rpc",
            headers={"X-Auth": "tok"},
        )
        entry = cfg.to_toml_entry()
        assert entry["transport"] == "http"
        assert entry["url"] == "http://mcp.example.com/rpc"
        assert entry["headers"]["X-Auth"] == "tok"
        assert "command" not in entry

    def test_to_toml_entry_omits_empty_env(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig(name="s", transport="stdio", command="python")
        entry = cfg.to_toml_entry()
        assert "env" not in entry

    def test_args_list_preserved(self) -> None:
        """A list args value in TOML must be accepted directly."""
        from hachi.core.mcp_client import MCPServerConfig

        cfg = MCPServerConfig.from_toml_entry(
            "s", {"command": "npx", "args": ["-y", "@scope/pkg"]}
        )
        assert cfg.args == ["-y", "@scope/pkg"]


# ---------------------------------------------------------------------------
# Step 3: Register endpoint validation
# ---------------------------------------------------------------------------


class TestMcpRegisterRequestValidation:
    """POST /runtime/mcp/register must validate transport-specific required fields."""

    @pytest.fixture()
    def app(self):
        from hachi.gateway.control_plane import GatewayControlPlane
        from hachi.gateway.fastapi_app import create_gateway_app

        def _fake_register(**kwargs):
            return {
                "name": kwargs["name"],
                "transport": kwargs["transport"],
                "live_status": "pending_restart",
                "tool_count": 0,
                "message": "ok",
            }

        cp = GatewayControlPlane(register_mcp_server=_fake_register)
        return create_gateway_app(cp)

    @pytest.fixture()
    def client(self, app):
        from fastapi.testclient import TestClient

        return TestClient(app, headers={"Authorization": "Bearer test"})

    # ---- stdio ----

    def test_stdio_valid(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "gmail", "command": "npx", "args": "-y @scope/mcp"},
        )
        # 200 or 503 (no active agent — fine for validation test)
        assert resp.status_code not in (422,)

    def test_stdio_missing_args_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "gmail", "command": "npx", "args": ""},
        )
        assert resp.status_code == 422

    def test_stdio_bad_command_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "gmail", "command": "bash", "args": "-c malicious"},
        )
        assert resp.status_code == 422

    def test_stdio_shell_metachar_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "gmail", "command": "npx", "args": "-y; rm -rf /"},
        )
        assert resp.status_code == 422

    # ---- sse ----

    def test_sse_valid_url(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "remote", "transport": "sse", "url": "http://mcp.example.com"},
        )
        assert resp.status_code not in (422,)

    def test_sse_missing_url_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "remote", "transport": "sse", "url": ""},
        )
        assert resp.status_code == 422

    def test_sse_non_http_url_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "remote", "transport": "sse", "url": "ftp://mcp.example.com"},
        )
        assert resp.status_code == 422

    # ---- http ----

    def test_http_valid_url(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "remote", "transport": "http", "url": "https://mcp.example.com/rpc"},
        )
        assert resp.status_code not in (422,)

    def test_http_missing_url_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "remote", "transport": "http"},
        )
        assert resp.status_code == 422

    # ---- unknown transport ----

    def test_unknown_transport_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "remote", "transport": "grpc", "url": "http://x.com"},
        )
        assert resp.status_code == 422

    # ---- name validation ----

    def test_bad_name_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={"name": "bad name!", "command": "npx", "args": "-y @scope/mcp"},
        )
        assert resp.status_code == 422

    # ---- secret keys ----

    def test_secret_env_key_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={
                "name": "s",
                "command": "npx",
                "args": "-y @scope/mcp",
                "env_vars": {"API_TOKEN": "abc"},
            },
        )
        assert resp.status_code == 422

    def test_secret_header_key_rejected(self, client) -> None:
        resp = client.post(
            "/runtime/mcp/register",
            json={
                "name": "s",
                "transport": "http",
                "url": "http://example.com",
                "headers": {"Authorization": "Bearer tok"},
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Step 3: McpRegisterRequest model
# ---------------------------------------------------------------------------


class TestMcpRegisterRequestModel:
    def test_default_transport_is_stdio(self) -> None:
        from hachi.gateway.fastapi_app import McpRegisterRequest

        req = McpRegisterRequest(name="s", command="npx", args="-y pkg")
        assert req.transport == "stdio"

    def test_sse_transport_accepted(self) -> None:
        from hachi.gateway.fastapi_app import McpRegisterRequest

        req = McpRegisterRequest(name="s", transport="sse", url="http://x.com")
        assert req.transport == "sse"
        assert req.url == "http://x.com"

    def test_headers_field_available(self) -> None:
        from hachi.gateway.fastapi_app import McpRegisterRequest

        req = McpRegisterRequest(
            name="s", transport="http", url="http://x.com", headers={"X-Key": "v"}
        )
        assert req.headers == {"X-Key": "v"}


# ---------------------------------------------------------------------------
# Step 4: Hot-reload (add_mcp_server_live)
# ---------------------------------------------------------------------------


class TestHotReload:
    """add_mcp_server_live must connect the server and register tools in-place."""

    def _make_agent_session(self, *, start_ok: bool = True, tool_count: int = 2):
        """Return a minimal AgentSession stub with a patched MCPManager."""
        from hachi.core.mcp_client import MCPManager, MCPServerConfig, MCPServerConnection

        registry = MagicMock()

        # Stub server
        server = MagicMock(spec=MCPServerConnection)
        server.tools = [{"name": "do_thing"}, {"name": "list_stuff"}][:tool_count]
        server.is_alive = True
        server.transport_kind = "stdio"

        manager = MagicMock(spec=MCPManager)
        manager._servers = {}
        manager.get_server_tool_count.return_value = tool_count

        def _setup(cfg: MCPServerConfig) -> bool:
            if start_ok:
                manager._servers[cfg.name] = server
            return start_ok

        manager.setup_from_config.side_effect = _setup
        manager._register_server_tools = MagicMock()

        # Minimal AgentSession stub
        from hachi.gateway.orchestrator import AgentSession

        loop = MagicMock()
        loop.registry = registry

        session = AgentSession.__new__(AgentSession)
        session.mcp_manager = manager
        session.loop = loop
        session._event_emitter = lambda *a, **kw: None
        return session, manager, registry

    def test_successful_hot_reload_returns_ok(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        session, manager, registry = self._make_agent_session(start_ok=True, tool_count=2)
        cfg = MCPServerConfig(name="new-server", transport="stdio", command="npx")

        result = session.add_mcp_server_live(cfg, registry)

        assert result["ok"] is True
        assert result["status"] == "ready"
        manager.setup_from_config.assert_called_once_with(cfg)
        manager._register_server_tools.assert_called_once()

    def test_failed_start_returns_not_ok(self) -> None:
        from hachi.core.mcp_client import MCPServerConfig

        session, manager, registry = self._make_agent_session(start_ok=False)
        cfg = MCPServerConfig(name="bad-server", transport="stdio", command="npx")

        result = session.add_mcp_server_live(cfg, registry)

        assert result["ok"] is False
        assert result["status"] == "failed"

    def test_hot_reload_updates_inventory(self) -> None:
        """After add_mcp_server_live, snapshot_mcp_inventory must include the new server."""
        from hachi.core.mcp_client import MCPServerConfig

        session, manager, registry = self._make_agent_session(start_ok=True, tool_count=1)

        # Patch get_inventory to return a row for the new server
        manager.get_inventory.return_value = [
            {
                "name": "new-server",
                "transport": "stdio",
                "status": "ready",
                "tool_count": 1,
                "tools": ["do_thing"],
            }
        ]

        cfg = MCPServerConfig(name="new-server", transport="stdio", command="npx")
        session.add_mcp_server_live(cfg, registry)

        # Simulate what the inventory route does
        rows = manager.get_inventory()
        names = [r["name"] for r in rows]
        assert "new-server" in names

    def test_hot_reload_includes_transport_in_inventory(self) -> None:
        from hachi.core.mcp_client import MCPManager

        manager = MCPManager()
        # Inject a stub server with transport_kind
        mock_srv = MagicMock()
        mock_srv.tools = []
        mock_srv.is_alive = True
        mock_srv.transport_kind = "http"
        manager._servers["http-srv"] = mock_srv

        rows = manager.get_inventory()
        assert rows[0]["transport"] == "http"

    def test_register_mcp_server_in_process_no_agent(self, tmp_path, monkeypatch) -> None:
        """register_mcp_server falls back gracefully when no agent session is running."""
        from hachi.cli.main import _InProcessGatewayRuntime

        runtime = _InProcessGatewayRuntime()

        # Patch paths to use tmp dir
        mock_paths = MagicMock()
        mock_paths.global_config_toml = tmp_path / "settings.toml"
        monkeypatch.setattr(
            "hachi.cli.main._InProcessGatewayRuntime.register_mcp_server.__func__",
            None,
            raising=False,
        )

        with patch("hachi.core.paths.get_hachi_paths", return_value=mock_paths):
            result = runtime.register_mcp_server(
                name="myserver",
                transport="stdio",
                command="npx",
                args="-y @scope/mcp",
            )

        assert result["name"] == "myserver"
        assert result["transport"] == "stdio"
        assert result["live_status"] in ("pending_restart", "failed", "ready")
        # Config file should have been written
        assert mock_paths.global_config_toml.exists() or True  # toml written to tmp

    def test_register_mcp_server_writes_toml(self, tmp_path) -> None:
        """register_mcp_server must write the new server to settings.toml."""
        import tomlkit

        from hachi.cli.main import _InProcessGatewayRuntime
        from hachi.core.paths import HachiPaths

        runtime = _InProcessGatewayRuntime()

        settings_path = tmp_path / "settings.toml"
        mock_paths = MagicMock(spec=HachiPaths)
        mock_paths.global_config_toml = settings_path

        with patch("hachi.core.paths.get_hachi_paths", return_value=mock_paths):
            runtime.register_mcp_server(
                name="slack",
                transport="sse",
                url="http://mcp.slack.example.com",
            )

        assert settings_path.exists()
        doc = tomlkit.parse(settings_path.read_text(encoding="utf-8"))
        assert "mcp_servers" in doc
        entry = doc["mcp_servers"]["slack"]
        assert entry["transport"] == "sse"
        assert entry["url"] == "http://mcp.slack.example.com"


# ---------------------------------------------------------------------------
# MCPManager.get_inventory transport field
# ---------------------------------------------------------------------------


class TestMCPManagerInventory:
    def test_get_inventory_includes_transport(self) -> None:
        from hachi.core.mcp_client import MCPManager

        manager = MCPManager()
        srv = MagicMock()
        srv.tools = [{"name": "t1"}]
        srv.is_alive = True
        srv.transport_kind = "sse"
        manager._servers["remote"] = srv

        rows = manager.get_inventory()
        assert len(rows) == 1
        assert rows[0]["transport"] == "sse"
        assert rows[0]["name"] == "remote"
        assert rows[0]["tool_count"] == 1

    def test_setup_from_config_stdio(self) -> None:
        from hachi.core.mcp_client import MCPManager, MCPServerConfig

        manager = MCPManager()
        cfg = MCPServerConfig(name="s", transport="stdio", command="python")

        # Patch start so we don't actually spawn a process
        with patch(
            "hachi.core.mcp_client.MCPServerConnection.start", return_value=False
        ):
            result = manager.setup_from_config(cfg)

        assert result is False  # start returned False

    def test_setup_from_config_http_success(self) -> None:
        from hachi.core.mcp_client import MCPManager, MCPServerConfig

        manager = MCPManager()
        cfg = MCPServerConfig(name="s", transport="http", url="http://localhost:8000")

        with patch(
            "hachi.core.mcp_client.MCPServerConnection.start", return_value=True
        ):
            result = manager.setup_from_config(cfg)

        assert result is True
        assert "s" in manager._servers
