"""MCP server lifecycle: enable / disable / delete (live + persisted + boot).

Regression coverage for the user-reported bug where deleting an MCP server from
the web UI left it visible in the inventory and a repeat delete returned 404.

Root cause: ``delete`` only removed the ``[mcp_servers.NAME]`` settings.toml entry,
while the inventory is sourced from the *live* ``MCPManager._servers``. So a server
that was live (or declared in .og, never in settings.toml) kept showing and 404'd
on the second delete. These tests pin the corrected, idempotent, live-aware
behaviour across every layer:

    ToolRegistry.unregister
    MCPManager.remove_server / register_server_tools / unregister_server_tools
    AgentSession.remove_mcp_server_live / set_mcp_tools_active
    _InProcessGatewayRuntime.delete_mcp_server / set_mcp_enabled
    _configure_mcp_servers boot-skip of enabled=false
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import tomlkit


def _fake_server(tool_names: list[str]) -> MagicMock:
    """A stand-in MCPServerConnection with the attributes the manager touches."""
    srv = MagicMock()
    srv.tools = [{"name": n} for n in tool_names]
    srv.is_alive = True
    srv.transport_kind = "stdio"
    srv.stop = MagicMock()
    return srv


# ---------------------------------------------------------------------------
# ToolRegistry.unregister
# ---------------------------------------------------------------------------


class TestToolRegistryUnregister:
    def test_unregister_removes_tool_schema_and_group(self) -> None:
        from hachi.core.loop import ToolRegistry

        reg = ToolRegistry()
        reg.register({"name": "gmail_send"}, lambda: "x", group="mcp")
        reg.register({"name": "gmail_list"}, lambda: "y", group="mcp")
        reg.register({"name": "keep_me"}, lambda: "z")

        removed = reg.unregister(["gmail_send", "gmail_list"])

        assert removed == 2
        assert "gmail_send" not in reg._tools
        assert "gmail_list" not in reg._tools
        assert "keep_me" in reg._tools
        schema_names = {s["name"] for s in reg._schemas}
        assert schema_names == {"keep_me"}
        assert "gmail_send" not in reg._groups

    def test_unregister_unknown_is_noop(self) -> None:
        from hachi.core.loop import ToolRegistry

        reg = ToolRegistry()
        reg.register({"name": "keep_me"}, lambda: "z")
        assert reg.unregister(["nope"]) == 0
        assert reg.unregister([]) == 0
        assert "keep_me" in reg._tools


# ---------------------------------------------------------------------------
# MCPManager lifecycle methods
# ---------------------------------------------------------------------------


class TestMCPManagerLifecycle:
    def test_remove_server_stops_and_unregisters(self) -> None:
        from hachi.core.loop import ToolRegistry
        from hachi.core.mcp_client import MCPManager

        mgr = MCPManager()
        reg = ToolRegistry()
        srv = _fake_server(["send", "list"])
        mgr._servers["gmail"] = srv
        mgr.register_server_tools("gmail", reg)
        assert "gmail_send" in reg._tools

        removed = mgr.remove_server("gmail", reg)

        assert removed is True
        srv.stop.assert_called_once()
        assert "gmail" not in mgr._servers
        assert "gmail_send" not in reg._tools
        assert "gmail_list" not in reg._tools
        # Server is gone from the inventory the UI reads.
        assert mgr.get_inventory() == []

    def test_remove_unknown_server_returns_false(self) -> None:
        from hachi.core.mcp_client import MCPManager

        assert MCPManager().remove_server("ghost") is False

    def test_unregister_then_reregister_no_duplicate_schemas(self) -> None:
        from hachi.core.loop import ToolRegistry
        from hachi.core.mcp_client import MCPManager

        mgr = MCPManager()
        reg = ToolRegistry()
        mgr._servers["gh"] = _fake_server(["a", "b"])

        mgr.register_server_tools("gh", reg)
        mgr.unregister_server_tools("gh", reg)
        assert "gh_a" not in reg._tools

        # Re-enable: tools come back and there is exactly one schema each (idempotent).
        mgr.register_server_tools("gh", reg)
        mgr.register_server_tools("gh", reg)  # second call must not duplicate
        assert "gh_a" in reg._tools
        assert [s["name"] for s in reg._schemas].count("gh_a") == 1


# ---------------------------------------------------------------------------
# AgentSession live methods (real class, minimal instance)
# ---------------------------------------------------------------------------


def _agent_with(mgr) -> object:
    from hachi.core.loop import ToolRegistry
    from hachi.gateway.orchestrator import AgentSession

    agent = AgentSession.__new__(AgentSession)
    agent.mcp_manager = mgr
    agent.loop = SimpleNamespace(registry=ToolRegistry())
    agent.skill_engine = MagicMock()
    agent.skill_engine.get_nodes_by_role.return_value = []
    return agent


class TestAgentSessionLive:
    def test_remove_mcp_server_live(self) -> None:
        from hachi.core.mcp_client import MCPManager

        mgr = MCPManager()
        mgr._servers["x"] = _fake_server(["t"])
        agent = _agent_with(mgr)
        mgr.register_server_tools("x", agent.loop.registry)

        res = agent.remove_mcp_server_live("x")

        assert res["removed_live"] is True
        assert "x" not in mgr._servers
        assert "x_t" not in agent.loop.registry._tools

    def test_set_mcp_tools_active_toggles_registration(self) -> None:
        from hachi.core.mcp_client import MCPManager

        mgr = MCPManager()
        mgr._servers["x"] = _fake_server(["t"])
        agent = _agent_with(mgr)
        mgr.register_server_tools("x", agent.loop.registry)

        off = agent.set_mcp_tools_active("x", False)
        assert off["live"] is True
        assert "x_t" not in agent.loop.registry._tools
        # Server stays listed so it can be re-enabled.
        assert "x" in mgr._servers

        on = agent.set_mcp_tools_active("x", True)
        assert on["live"] is True
        assert "x_t" in agent.loop.registry._tools

    def test_set_active_not_live_is_noop(self) -> None:
        from hachi.core.mcp_client import MCPManager

        agent = _agent_with(MCPManager())
        res = agent.set_mcp_tools_active("ghost", True)
        assert res["live"] is False


# ---------------------------------------------------------------------------
# _InProcessGatewayRuntime.delete_mcp_server / set_mcp_enabled
# ---------------------------------------------------------------------------


@pytest.fixture()
def runtime_with_paths(tmp_path):
    """A runtime plus a HachiPaths mock pointing settings.toml + skills at tmp."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    paths = MagicMock()
    paths.global_config_toml = tmp_path / "settings.toml"
    paths.skills_dir = tmp_path / "skills"
    paths.skills_dir.mkdir()
    return runtime, paths, tmp_path


def _attach_live_server(runtime, name, tool_names, og_node_names=()):
    from hachi.core.mcp_client import MCPManager

    mgr = MCPManager()
    mgr._servers[name] = _fake_server(list(tool_names))
    agent = _agent_with(mgr)
    if og_node_names:
        agent.skill_engine.get_nodes_by_role.return_value = [
            SimpleNamespace(name=n) for n in og_node_names
        ]
    mgr.register_server_tools(name, agent.loop.registry)
    runtime._agents["s1"] = agent
    return agent


class TestRuntimeDelete:
    def test_delete_toml_server_then_idempotent(self, runtime_with_paths) -> None:
        runtime, paths, _ = runtime_with_paths
        paths.global_config_toml.write_text(
            tomlkit.dumps(
                tomlkit.parse('[mcp_servers.slack]\ntransport = "sse"\nurl = "http://x"\n')
            ),
            encoding="utf-8",
        )

        with patch("hachi.core.paths.get_hachi_paths", return_value=paths), patch(
            "hachi.gateway.workspace.get_skills_dir", return_value=paths.skills_dir
        ):
            first = runtime.delete_mcp_server("slack")
            second = runtime.delete_mcp_server("slack")  # the reported 404 path

        assert first["ok"] is True
        assert first["removed_toml"] is True
        # Second delete must NOT raise / 404 — idempotent success.
        assert second["ok"] is True
        assert second["already_absent"] is True
        doc = tomlkit.parse(paths.global_config_toml.read_text(encoding="utf-8"))
        assert "slack" not in doc.get("mcp_servers", {})

    def test_delete_live_server_tears_down_and_drops_from_inventory(
        self, runtime_with_paths
    ) -> None:
        runtime, paths, _ = runtime_with_paths
        agent = _attach_live_server(runtime, "weather", ["forecast"])

        with patch("hachi.core.paths.get_hachi_paths", return_value=paths), patch(
            "hachi.gateway.workspace.get_skills_dir", return_value=paths.skills_dir
        ):
            res = runtime.delete_mcp_server("weather")

        assert res["removed_live"] is True
        # Gone from the live inventory the UI reads — the core of the bug.
        assert agent.mcp_manager.get_inventory() == []
        assert "weather_forecast" not in agent.loop.registry._tools

    def test_delete_bundled_og_server_writes_tombstone(self, runtime_with_paths) -> None:
        runtime, paths, _ = runtime_with_paths
        # Live + declared as an .og node, but NOT in settings.toml and no mcp-*.og file.
        _attach_live_server(runtime, "gmail", ["send"], og_node_names=["gmail"])

        with patch("hachi.core.paths.get_hachi_paths", return_value=paths), patch(
            "hachi.gateway.workspace.get_skills_dir", return_value=paths.skills_dir
        ):
            res = runtime.delete_mcp_server("gmail")

        assert res["tombstoned"] is True
        doc = tomlkit.parse(paths.global_config_toml.read_text(encoding="utf-8"))
        assert doc["mcp_servers"]["gmail"]["enabled"] is False

        # A second delete keeps the tombstone (so the bundled server stays gone).
        with patch("hachi.core.paths.get_hachi_paths", return_value=paths), patch(
            "hachi.gateway.workspace.get_skills_dir", return_value=paths.skills_dir
        ):
            again = runtime.delete_mcp_server("gmail")
        assert again["ok"] is True
        doc2 = tomlkit.parse(paths.global_config_toml.read_text(encoding="utf-8"))
        assert doc2["mcp_servers"]["gmail"]["enabled"] is False

    def test_delete_user_og_file_is_removed(self, runtime_with_paths) -> None:
        runtime, paths, _ = runtime_with_paths
        og_file = paths.skills_dir / "mcp-custom.og"
        og_file.write_text("::index\ncustom\n", encoding="utf-8")

        with patch("hachi.core.paths.get_hachi_paths", return_value=paths), patch(
            "hachi.gateway.workspace.get_skills_dir", return_value=paths.skills_dir
        ):
            res = runtime.delete_mcp_server("custom")

        assert res["removed_og"] is True
        assert not og_file.exists()

    def test_delete_unknown_is_idempotent_not_404(self, runtime_with_paths) -> None:
        runtime, paths, _ = runtime_with_paths
        with patch("hachi.core.paths.get_hachi_paths", return_value=paths), patch(
            "hachi.gateway.workspace.get_skills_dir", return_value=paths.skills_dir
        ):
            res = runtime.delete_mcp_server("does-not-exist")
        assert res["ok"] is True
        assert res["already_absent"] is True


class TestRuntimeSetEnabled:
    def test_disable_og_server_creates_entry_and_applies_live(
        self, runtime_with_paths
    ) -> None:
        runtime, paths, _ = runtime_with_paths
        agent = _attach_live_server(runtime, "gmail", ["send"], og_node_names=["gmail"])

        with patch("hachi.core.paths.get_hachi_paths", return_value=paths):
            res = runtime.set_mcp_enabled("gmail", False)

        assert res["enabled"] is False
        assert res["applied_live"] is True
        # Persisted so the boot path can honour it.
        doc = tomlkit.parse(paths.global_config_toml.read_text(encoding="utf-8"))
        assert doc["mcp_servers"]["gmail"]["enabled"] is False
        # Tools pulled from the live registry, but the server stays listed.
        assert "gmail_send" not in agent.loop.registry._tools
        assert "gmail" in agent.mcp_manager._servers

    def test_enable_reregisters_live(self, runtime_with_paths) -> None:
        runtime, paths, _ = runtime_with_paths
        agent = _attach_live_server(runtime, "gmail", ["send"], og_node_names=["gmail"])

        with patch("hachi.core.paths.get_hachi_paths", return_value=paths):
            runtime.set_mcp_enabled("gmail", False)
            res = runtime.set_mcp_enabled("gmail", True)

        assert res["enabled"] is True
        assert "gmail_send" in agent.loop.registry._tools
        doc = tomlkit.parse(paths.global_config_toml.read_text(encoding="utf-8"))
        assert doc["mcp_servers"]["gmail"]["enabled"] is True

    def test_unknown_server_raises_404(self, runtime_with_paths) -> None:
        from fastapi import HTTPException

        runtime, paths, _ = runtime_with_paths
        with patch("hachi.core.paths.get_hachi_paths", return_value=paths):
            with pytest.raises(HTTPException) as exc:
                runtime.set_mcp_enabled("ghost", False)
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Boot honours enabled=false
# ---------------------------------------------------------------------------


class TestBootHonoursDisabled:
    def _run(self, tmp_path, enabled_flag):
        from hachi.gateway.orchestrator import _configure_mcp_servers

        node = SimpleNamespace(
            name="weather",
            config={"command": "npx", "args": "-y @scope/weather"},
            source_file=str(tmp_path / "weather.og"),
        )
        skill_engine = MagicMock()
        skill_engine.get_nodes_by_role.return_value = [node]

        mcp_manager = MagicMock()
        gate = MagicMock()
        gate.is_mcp_server_allowed.return_value = SimpleNamespace(allowed=True, reason="")
        gate.is_mcp_filesystem_enabled.return_value = True

        config = None
        if enabled_flag is not None:
            config = {"mcp_servers": {"weather": {"enabled": enabled_flag}}}

        paths = MagicMock()
        paths.skills_dir = tmp_path
        with patch("hachi.gateway.orchestrator.get_hachi_paths", return_value=paths):
            _configure_mcp_servers(skill_engine, mcp_manager, gate, lambda *_a: None, config)
        return mcp_manager

    def test_disabled_og_node_is_not_started(self, tmp_path) -> None:
        mgr = self._run(tmp_path, enabled_flag=False)
        mgr.setup_from_node.assert_not_called()
        mgr.setup_from_config.assert_not_called()

    def test_enabled_og_node_is_started(self, tmp_path) -> None:
        mgr = self._run(tmp_path, enabled_flag=True)
        mgr.setup_from_node.assert_called_once()

    def test_absent_flag_defaults_to_started(self, tmp_path) -> None:
        mgr = self._run(tmp_path, enabled_flag=None)
        mgr.setup_from_node.assert_called_once()
