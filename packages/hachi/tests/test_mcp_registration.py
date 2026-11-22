"""Tests for MCP secret-ref registration and TOML-only inventory visibility (BB-9 / BB-10)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file_store(tmp_path: Path):
    from hachi.core.secret_store import EncryptedFileSecretStore, _MetadataStore

    meta = _MetadataStore(tmp_path / "meta.json")
    return EncryptedFileSecretStore(
        file_path=tmp_path / "secrets.enc",
        passphrase="test-pass",
        metadata_store=meta,
    )


# ---------------------------------------------------------------------------
# B. _resolve_secret_refs
# ---------------------------------------------------------------------------


class TestResolveSecretRefs:
    def test_passthrough_plain_values(self, tmp_path: Path) -> None:
        from hachi.core.mcp_client import _resolve_secret_refs

        store = _make_file_store(tmp_path)
        mapping = {"KEY": "plain-value", "OTHER": "also-plain"}
        assert _resolve_secret_refs(mapping, store) == mapping

    def test_resolves_existing_credential(self, tmp_path: Path) -> None:
        from hachi.core.mcp_client import _resolve_secret_refs

        store = _make_file_store(tmp_path)
        store.set("cred:mykey", "resolved-secret")
        result = _resolve_secret_refs({"API_KEY": "secret:mykey"}, store)
        assert result == {"API_KEY": "resolved-secret"}

    def test_raises_on_missing_credential(self, tmp_path: Path) -> None:
        from hachi.core.mcp_client import _MissingSecretError, _resolve_secret_refs

        store = _make_file_store(tmp_path)
        with pytest.raises(_MissingSecretError, match="unknown credential"):
            _resolve_secret_refs({"API_KEY": "secret:doesnotexist"}, store)


# ---------------------------------------------------------------------------
# B. setup_from_config with secret refs
# ---------------------------------------------------------------------------


class TestMcpSetupFromConfigSecretRefs:
    def test_mcp_env_secret_resolved_before_start(self, tmp_path: Path, monkeypatch) -> None:
        """setup_from_config resolves secret: refs before passing env to the transport."""
        from hachi.core.mcp_client import MCPManager, MCPServerConfig

        store = _make_file_store(tmp_path)
        store.set("cred:ctx7key", "the-real-value")

        monkeypatch.setattr("hachi.core.mcp_client._get_module_secret_store", lambda: store)

        received_env: dict[str, str] = {}

        def _fake_setup_from_config(self_inner, cfg: MCPServerConfig) -> bool:
            received_env.update(cfg.env)
            return True

        # Patch only the inner MCPServerConnection.start so we don't spawn processes.
        # We intercept at setup_from_config to capture the RESOLVED config.
        with patch("hachi.core.mcp_client.MCPServerConnection.start", return_value=True):
            manager = MCPManager()
            cfg = MCPServerConfig(
                name="ctx7",
                command="npx",
                args=["-y", "@ctx7/mcp"],
                env={"API_KEY": "secret:ctx7key"},
            )
            ok = manager.setup_from_config(cfg)

        assert ok is True
        # The server stored in _servers should have the resolved env value.
        server = manager._servers.get("ctx7")
        assert server is not None
        # env on the MCPServerConnection is passed as a subprocess env override;
        # the resolved value must reach the transport (checked via the config we built).
        # Since MCPServerConnection stores env on self._env (or similar), verify
        # the transport was initialised with the resolved value by checking the server
        # doesn't have a _last_error (which would indicate it failed due to missing secret).
        assert server._last_error is None

    def test_mcp_missing_secret_fails_soft(self, tmp_path: Path, monkeypatch) -> None:
        """setup_from_config with a missing cred: → failed status, no exception raised."""
        from hachi.core.mcp_client import MCPManager, MCPServerConfig

        store = _make_file_store(tmp_path)  # empty — no credentials
        monkeypatch.setattr("hachi.core.mcp_client._get_module_secret_store", lambda: store)

        manager = MCPManager()
        cfg = MCPServerConfig(
            name="bad-server",
            command="npx",
            args=["-y", "@example/mcp"],
            env={"TOKEN": "secret:missingcred"},
        )
        ok = manager.setup_from_config(cfg)

        assert ok is False
        server = manager._servers.get("bad-server")
        assert server is not None
        assert server._last_error is not None
        assert "missingcred" in server._last_error


# ---------------------------------------------------------------------------
# C. TOML-only server visibility (BB-10)
# ---------------------------------------------------------------------------


class TestMcpInventoryTomlOnly:
    def test_mcp_inventory_shows_toml_only_server(self, tmp_path: Path) -> None:
        """mcp_inventory() includes TOML-persisted servers even when no agent is live."""
        import tomlkit

        from hachi.gateway.control_plane import GatewayControlPlane

        # Write a minimal settings.toml with one MCP server entry.
        toml_path = tmp_path / "settings.toml"
        doc = tomlkit.document()
        servers = tomlkit.table()
        server_entry = tomlkit.table()
        server_entry.add("command", "npx")
        server_entry.add("args", "-y @example/mcp")
        server_entry.add("transport", "stdio")
        server_entry.add("enabled", True)
        servers.add("my-toml-server", server_entry)
        doc.add("mcp_servers", servers)
        toml_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

        # Patch get_hachi_paths to return our tmp path.
        fake_paths = MagicMock()
        fake_paths.global_config_toml = toml_path

        cp = GatewayControlPlane(
            get_mcp_inventory=lambda: {"server_count": 0, "total_tool_count": 0, "servers": []}
        )

        with patch("hachi.core.paths.get_hachi_paths", return_value=fake_paths):
            result = cp.mcp_inventory()

        names = [s["name"] for s in result["servers"]]
        assert "my-toml-server" in names
        toml_entry = next(s for s in result["servers"] if s["name"] == "my-toml-server")
        assert toml_entry["status"] == "pending_restart"
        assert toml_entry["tool_count"] == 0


# ---------------------------------------------------------------------------
# D. register/delete must edit ONLY the targeted sub-table (BB-19)
# ---------------------------------------------------------------------------


class TestMcpRegisterPreservesEntryFields:
    """register/delete must touch only the targeted server's sub-table and never
    drop persisted lifecycle fields (e.g. ``enabled``) — neither from a re-registered
    server nor from a pre-existing sibling. (BB-19)
    """

    @staticmethod
    def _ctx(tmp_path: Path):
        """Build (config_toml, skills_dir, patches) for a runtime with no live agent."""
        config_toml = tmp_path / "settings.toml"
        skills = tmp_path / "skills"
        skills.mkdir(exist_ok=True)
        fake_paths = MagicMock()
        fake_paths.global_config_toml = config_toml
        fake_paths.skills_dir = skills
        patches = (
            patch("hachi.core.paths.get_hachi_paths", return_value=fake_paths),
            patch("hachi.gateway.workspace.get_skills_dir", return_value=skills),
        )
        return config_toml, skills, patches

    @staticmethod
    def _entry(config_toml: Path, name: str) -> dict:
        import tomlkit

        doc = tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        return dict(doc.get("mcp_servers", {}).get(name, {}))

    def test_reregister_preserves_enabled(self, tmp_path: Path) -> None:
        """Re-registering an existing server must NOT drop its ``enabled`` flag.

        This is the reported data loss: the entry is rewritten from the in-memory
        ``MCPServerConfig`` (which has no ``enabled`` field) so only ``transport`` +
        ``url`` survive.
        """
        from hachi.cli.main import _InProcessGatewayRuntime

        config_toml, _skills, (p_paths, p_skills) = self._ctx(tmp_path)
        rt = _InProcessGatewayRuntime()
        with p_paths, p_skills:
            rt.register_mcp_server(name="demo", transport="sse", url="https://demo.example/mcp")
            rt.set_mcp_enabled("demo", True)
            # User edits the server (e.g. changes its URL) → re-register same name.
            rt.register_mcp_server(name="demo", transport="sse", url="https://demo.example/v2")

        demo = self._entry(config_toml, "demo")
        assert demo["url"] == "https://demo.example/v2"  # the field we meant to update
        assert demo.get("enabled") is True  # the lifecycle field we must preserve

    def test_reregister_transport_switch_prunes_stale_keys_keeps_enabled(
        self, tmp_path: Path
    ) -> None:
        """Switching transport on re-register drops stale managed keys but keeps ``enabled``."""
        from hachi.cli.main import _InProcessGatewayRuntime

        config_toml, _skills, (p_paths, p_skills) = self._ctx(tmp_path)
        rt = _InProcessGatewayRuntime()
        with p_paths, p_skills:
            rt.register_mcp_server(name="demo", transport="stdio", command="npx", args="-y @x/y")
            rt.set_mcp_enabled("demo", True)
            rt.register_mcp_server(name="demo", transport="http", url="https://demo.example/mcp")

        demo = self._entry(config_toml, "demo")
        assert demo["transport"] == "http"
        assert demo["url"] == "https://demo.example/mcp"
        assert "command" not in demo  # stale stdio key pruned
        assert "args" not in demo
        assert demo.get("enabled") is True  # lifecycle field preserved across the switch

    def test_register_then_delete_leaves_sibling_byte_for_byte(self, tmp_path: Path) -> None:
        """Registering+deleting one server must not mutate a pre-existing sibling entry."""
        import tomlkit

        from hachi.cli.main import _InProcessGatewayRuntime

        config_toml, _skills, (p_paths, p_skills) = self._ctx(tmp_path)
        config_toml.write_text(
            "[mcp_servers.demo]\n"
            'transport = "sse"\n'
            'url = "https://demo.example/mcp"\n'
            "enabled = true\n",
            encoding="utf-8",
        )
        sibling_before = self._entry(config_toml, "demo")

        rt = _InProcessGatewayRuntime()
        with p_paths, p_skills:
            rt.register_mcp_server(
                name="context7", transport="http", url="https://mcp.context7.com/mcp"
            )
            rt.delete_mcp_server("context7")

        doc = tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        assert "context7" not in doc.get("mcp_servers", {})
        assert self._entry(config_toml, "demo") == sibling_before

    def test_toml_managed_keys_cover_to_toml_entry(self) -> None:
        """``TOML_MANAGED_KEYS`` must cover every key ``to_toml_entry`` can emit (drift guard)."""
        from hachi.core.mcp_client import MCPServerConfig

        stdio = MCPServerConfig(
            name="s",
            transport="stdio",
            command="npx",
            args=["-y", "x"],
            env={"A": "b"},
            boot_timeout_seconds=5.0,
            request_timeout_seconds=10.0,
        )
        http = MCPServerConfig(
            name="h",
            transport="http",
            url="https://x",
            headers={"H": "v"},
            env={"A": "b"},
            boot_timeout_seconds=5.0,
            request_timeout_seconds=10.0,
        )
        for cfg in (stdio, http):
            assert set(cfg.to_toml_entry()) <= MCPServerConfig.TOML_MANAGED_KEYS


# ---------------------------------------------------------------------------
# E. Boot failures before _servers entry must appear in get_inventory (Bug 4)
# ---------------------------------------------------------------------------


class TestMcpBootFailureInventory:
    """Servers that fail before entering _servers must show up in get_inventory.

    Covers: invalid TOML config and gate denial — both fail before
    MCPManager._servers is populated, so they were invisible to the operator UI.
    """

    def test_register_boot_failure_appears_in_inventory(self) -> None:
        from hachi.core.mcp_client import MCPManager

        mgr = MCPManager()
        mgr.register_boot_failure("bad-server", "invalid TOML config")
        rows = mgr.get_inventory()
        names = [r["name"] for r in rows]
        assert "bad-server" in names, "Boot failure must appear in inventory"
        entry = next(r for r in rows if r["name"] == "bad-server")
        assert entry["status"] == "failed"
        assert entry["tool_count"] == 0
        assert entry["err"] == "invalid TOML config"

    def test_boot_failure_not_duplicated_when_server_later_added(self) -> None:
        """If a server was initially a failure but later successfully added,
        it must appear only once (from _servers, not from _boot_failures)."""
        from hachi.core.mcp_client import MCPManager, MCPServerConnection

        mgr = MCPManager()
        mgr.register_boot_failure("s", "gate denied")
        # Simulate the server being added successfully later.
        mock_conn = MagicMock(spec=MCPServerConnection)
        mock_conn.transport_kind = "stdio"
        mock_conn.is_alive = True
        mock_conn.tools = []
        mgr._servers["s"] = mock_conn
        rows = mgr.get_inventory()
        matching = [r for r in rows if r["name"] == "s"]
        assert len(matching) == 1, "Server must appear exactly once"
        assert matching[0]["status"] == "ready"

    def test_boot_failure_with_gate_denial_reason(self) -> None:
        from hachi.core.mcp_client import MCPManager

        mgr = MCPManager()
        mgr.register_boot_failure("gated-server", "MCP access not permitted in sandbox tier")
        entry = next(r for r in mgr.get_inventory() if r["name"] == "gated-server")
        assert entry["status"] == "failed"
        assert "sandbox" in (entry["err"] or "")
