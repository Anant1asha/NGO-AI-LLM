"""Tests for the agent-accessible config and MCP management tools.

Covers:
MCP management
  1.  add_mcp_server — happy path (npx package)
  2.  add_mcp_server — validates command (blocked executable)
  3.  add_mcp_server — validates name (non-slug)
  4.  add_mcp_server — validates args (shell metacharacter)
  5.  add_mcp_server — validates env_vars (secret key rejected)
  6.  add_mcp_server — rejects overwrite of existing server
  7.  add_mcp_server — sandbox tier blocked
  8.  add_mcp_server — with env_vars writes them to .og
  9.  remove_mcp_server — removes existing user-created server
  10. remove_mcp_server — not-found returns helpful message
  11. remove_mcp_server — sandbox tier blocked
  12. list_mcp_servers — returns JSON with count

Config management
  13. _validate_env_var_key — token rejected, plain key passes
  14. _validate_mcp_args — shell metacharacter rejected
  15. _safe_config_snapshot — api_key_ref excluded, model included
  16. _apply_config_patch — settable key updates config
  17. _apply_config_patch — blocked key (permissions.tier) rejected
  18. _apply_config_patch — unknown key rejected
  19. _apply_config_patch — bool coercion (true/false strings)
  20. _apply_config_patch — list coercion (comma-separated)
  21. get_agent_config — returns JSON with safe fields
  22. set_agent_config — persists change to write_config_fn
  23. set_agent_config — blocked key returns error, no write
  24. register_config_tools — all 5 tools registered
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from hachi.tools.config_tools import (
    _apply_config_patch,
    _make_add_mcp_server,
    _make_get_agent_config,
    _make_list_mcp_servers,
    _make_remove_mcp_server,
    _make_set_agent_config,
    _safe_config_snapshot,
    _validate_env_var_key,
    _validate_mcp_args,
    register_config_tools,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_gate(tier: str = "guided") -> MagicMock:
    gate = MagicMock()
    gate.tier = tier
    return gate


def _skills_dir_patch(tmp_path: Path) -> patch:
    return patch(
        "hachi.gateway.workspace.get_skills_dir",
        return_value=tmp_path,
    )


# ---------------------------------------------------------------------------
# 1. add_mcp_server — happy path
# ---------------------------------------------------------------------------


def test_add_mcp_server_happy_path(tmp_path: Path) -> None:
    fn = _make_add_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("github", "npx", "-y @modelcontextprotocol/server-github")
    assert "registered" in result.lower()
    assert (tmp_path / "mcp-github.og").exists()
    content = (tmp_path / "mcp-github.og").read_text(encoding="utf-8")
    assert "::node[github]" in content
    assert "command: npx" in content


# ---------------------------------------------------------------------------
# 2. add_mcp_server — blocked command
# ---------------------------------------------------------------------------


def test_add_mcp_server_blocked_command(tmp_path: Path) -> None:
    fn = _make_add_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("bad", "bash", "-c 'rm -rf /'")
    assert "not allowed" in result.lower()
    assert not (tmp_path / "mcp-bad.og").exists()


# ---------------------------------------------------------------------------
# 3. add_mcp_server — invalid name
# ---------------------------------------------------------------------------


def test_add_mcp_server_invalid_name(tmp_path: Path) -> None:
    fn = _make_add_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("bad name!", "npx", "-y pkg")
    assert "slug" in result.lower() or "not slug" in result.lower()
    assert not (tmp_path / "mcp-bad name!.og").exists()


# ---------------------------------------------------------------------------
# 4. add_mcp_server — shell metacharacter in args
# ---------------------------------------------------------------------------


def test_add_mcp_server_shell_meta_in_args(tmp_path: Path) -> None:
    fn = _make_add_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("tricky", "node", "server.js; rm -rf /")
    assert "metacharacter" in result.lower() or "shell" in result.lower()
    assert not (tmp_path / "mcp-tricky.og").exists()


# ---------------------------------------------------------------------------
# 5. add_mcp_server — secret env var rejected
# ---------------------------------------------------------------------------


def test_add_mcp_server_secret_env_rejected(tmp_path: Path) -> None:
    fn = _make_add_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("gh", "npx", "-y @mcp/server", env_vars={"GITHUB_TOKEN": "ghp_xxx"})
    assert "secret" in result.lower() or "credential" in result.lower()
    assert not (tmp_path / "mcp-gh.og").exists()


# ---------------------------------------------------------------------------
# 6. add_mcp_server — rejects overwrite
# ---------------------------------------------------------------------------


def test_add_mcp_server_no_overwrite(tmp_path: Path) -> None:
    (tmp_path / "mcp-github.og").write_text("::node[github]\n", encoding="utf-8")
    fn = _make_add_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("github", "npx", "-y @mcp/server-github")
    assert "already exists" in result.lower() or "exists" in result.lower()


# ---------------------------------------------------------------------------
# 7. add_mcp_server — sandbox tier blocked
# ---------------------------------------------------------------------------


def test_add_mcp_server_sandbox_blocked(tmp_path: Path) -> None:
    fn = _make_add_mcp_server(gate=_fake_gate("sandbox"))
    with _skills_dir_patch(tmp_path):
        result = fn("github", "npx", "-y @mcp/server-github")
    assert "sandbox" in result.lower()
    assert not (tmp_path / "mcp-github.og").exists()


# ---------------------------------------------------------------------------
# 8. add_mcp_server — env_vars written to .og
# ---------------------------------------------------------------------------


def test_add_mcp_server_env_vars_written(tmp_path: Path) -> None:
    fn = _make_add_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        fn("notion", "npx", "-y @notion/mcp", env_vars={"WORKSPACE_ID": "abc123"})
    content = (tmp_path / "mcp-notion.og").read_text(encoding="utf-8")
    assert "env_WORKSPACE_ID: abc123" in content


# ---------------------------------------------------------------------------
# 9. remove_mcp_server — removes existing
# ---------------------------------------------------------------------------


def test_remove_mcp_server_removes_file(tmp_path: Path) -> None:
    og = tmp_path / "mcp-github.og"
    og.write_text("::node[github]\n", encoding="utf-8")
    fn = _make_remove_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("github")
    assert "removed" in result.lower()
    assert not og.exists()


# ---------------------------------------------------------------------------
# 10. remove_mcp_server — not found
# ---------------------------------------------------------------------------


def test_remove_mcp_server_not_found(tmp_path: Path) -> None:
    fn = _make_remove_mcp_server(gate=_fake_gate())
    with _skills_dir_patch(tmp_path):
        result = fn("missing")
    assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# 11. remove_mcp_server — sandbox tier blocked
# ---------------------------------------------------------------------------


def test_remove_mcp_server_sandbox_blocked(tmp_path: Path) -> None:
    og = tmp_path / "mcp-github.og"
    og.write_text("::node[github]\n", encoding="utf-8")
    fn = _make_remove_mcp_server(gate=_fake_gate("sandbox"))
    with _skills_dir_patch(tmp_path):
        result = fn("github")
    assert "sandbox" in result.lower()
    assert og.exists()  # not deleted


# ---------------------------------------------------------------------------
# 12. list_mcp_servers — returns JSON
# ---------------------------------------------------------------------------


def test_list_mcp_servers_returns_json(tmp_path: Path) -> None:
    fn = _make_list_mcp_servers()
    og_content = """\
::node[myserver]
->[:role=mcp]
->[:keywords=mcp, myserver]

::dense
MCP server: myserver

::config
command: npx
args: -y mypackage
env_API_URL: https://api.example.com
"""
    og_file = tmp_path / "mcp-myserver.og"
    og_file.write_text(og_content, encoding="utf-8")

    with (
        patch("hachi.gateway.workspace.get_skills_dir", return_value=tmp_path),
        patch("hachi.og_engine.engine.SkillEngine") as MockEngine,
    ):
        mock_engine = MagicMock()
        MockEngine.return_value = mock_engine
        node = MagicMock()
        node.name = "myserver"
        node.config = {"command": "npx", "args": "-y mypackage", "env_API_URL": "https://…"}
        mock_engine.get_nodes_by_role.return_value = [node]
        result = fn()

    data = json.loads(result)
    assert data["count"] == 1
    assert data["servers"][0]["name"] == "myserver"
    # env_var VALUES not in result (only keys)
    assert "https://" not in result or data["servers"][0].get("env_var_keys")


# ---------------------------------------------------------------------------
# 13. _validate_env_var_key — patterns
# ---------------------------------------------------------------------------


def test_validate_env_var_key_rejects_token() -> None:
    assert _validate_env_var_key("GITHUB_TOKEN") is not None


def test_validate_env_var_key_rejects_key() -> None:
    assert _validate_env_var_key("API_KEY") is not None


def test_validate_env_var_key_passes_plain() -> None:
    assert _validate_env_var_key("WORKSPACE_ID") is None
    assert _validate_env_var_key("BASE_URL") is None
    assert _validate_env_var_key("REGION") is None


# ---------------------------------------------------------------------------
# 14. _validate_mcp_args — shell metacharacters
# ---------------------------------------------------------------------------


def test_validate_mcp_args_rejects_semicolon() -> None:
    assert _validate_mcp_args("pkg; rm -rf /") is not None


def test_validate_mcp_args_rejects_subshell() -> None:
    assert _validate_mcp_args("pkg $(cat /etc/passwd)") is not None


def test_validate_mcp_args_passes_clean() -> None:
    assert _validate_mcp_args("-y @modelcontextprotocol/server-github") is None
    assert _validate_mcp_args("run --arg value") is None


# ---------------------------------------------------------------------------
# 15. _safe_config_snapshot — no credentials
# ---------------------------------------------------------------------------


def test_safe_config_snapshot_excludes_credentials() -> None:
    from hachi.core.settings import ProviderSettings, ResolvedConfig

    config = ResolvedConfig(
        provider=ProviderSettings(
            model="claude-3-5-sonnet-latest",
            api_key_ref="my-secret-ref",
        )
    )
    snap = _safe_config_snapshot(config)
    assert "api_key_ref" not in json.dumps(snap)
    assert "my-secret-ref" not in json.dumps(snap)
    assert snap["provider"]["model"] == "claude-3-5-sonnet-latest"


# ---------------------------------------------------------------------------
# 16. _apply_config_patch — valid update
# ---------------------------------------------------------------------------


def test_apply_config_patch_valid_key() -> None:
    from hachi.core.settings import AgentSettings, ResolvedConfig

    config = ResolvedConfig(agent=AgentSettings(name="old-name"))
    updated, err = _apply_config_patch(config, "agent.name", "new-name")
    assert err is None
    assert updated.agent.name == "new-name"


# ---------------------------------------------------------------------------
# 17. _apply_config_patch — blocked key
# ---------------------------------------------------------------------------


def test_apply_config_patch_blocked_tier() -> None:
    from hachi.core.settings import ResolvedConfig

    config = ResolvedConfig()
    _, err = _apply_config_patch(config, "permissions.tier", "autonomous")
    assert err is not None
    assert "blocked" in err.lower() or "security" in err.lower()


# ---------------------------------------------------------------------------
# 18. _apply_config_patch — unknown key
# ---------------------------------------------------------------------------


def test_apply_config_patch_unknown_key() -> None:
    from hachi.core.settings import ResolvedConfig

    config = ResolvedConfig()
    _, err = _apply_config_patch(config, "provider.unknown_field", "value")
    assert err is not None
    assert "allowlist" in err.lower() or "settable" in err.lower()


# ---------------------------------------------------------------------------
# 19. _apply_config_patch — bool coercion
# ---------------------------------------------------------------------------


def test_apply_config_patch_bool_coercion() -> None:
    from hachi.core.settings import MemorySettings, ResolvedConfig

    config = ResolvedConfig(memory=MemorySettings(enable_session_history=True))
    updated, err = _apply_config_patch(config, "memory.enable_session_history", "false")
    assert err is None
    assert updated.memory.enable_session_history is False


# ---------------------------------------------------------------------------
# 20. _apply_config_patch — list coercion
# ---------------------------------------------------------------------------


def test_apply_config_patch_list_coercion() -> None:
    from hachi.core.settings import ProviderSettings, ResolvedConfig

    config = ResolvedConfig(provider=ProviderSettings(allowed_models=[]))
    updated, err = _apply_config_patch(
        config, "provider.allowed_models", "claude-3-5-sonnet-latest, claude-haiku-4-5"
    )
    assert err is None
    assert "claude-3-5-sonnet-latest" in updated.provider.allowed_models
    assert "claude-haiku-4-5" in updated.provider.allowed_models


# ---------------------------------------------------------------------------
# 21. get_agent_config — returns JSON with safe fields
# ---------------------------------------------------------------------------


def test_get_agent_config_returns_json() -> None:
    from hachi.core.settings import ResolvedConfig

    config = ResolvedConfig()

    def fake_load() -> ResolvedConfig:
        return config

    fn = _make_get_agent_config(fake_load)
    result = json.loads(fn())
    assert "provider" in result
    assert "permissions" in result
    assert "api_key" not in json.dumps(result)


# ---------------------------------------------------------------------------
# 22. set_agent_config — persists change
# ---------------------------------------------------------------------------


def test_set_agent_config_persists() -> None:
    from hachi.core.settings import AgentSettings, ResolvedConfig

    config = ResolvedConfig(agent=AgentSettings(name="old"))
    written: list = []

    def fake_load() -> ResolvedConfig:
        return config

    def fake_write(cfg: ResolvedConfig) -> None:
        written.append(cfg)

    fn = _make_set_agent_config(fake_load, fake_write)
    result = fn("agent.name", "new-name")
    assert "updated" in result.lower()
    assert len(written) == 1
    assert written[0].agent.name == "new-name"


# ---------------------------------------------------------------------------
# 23. set_agent_config — blocked key → no write
# ---------------------------------------------------------------------------


def test_set_agent_config_blocked_no_write() -> None:
    from hachi.core.settings import ResolvedConfig

    written: list = []

    def fake_load() -> ResolvedConfig:
        return ResolvedConfig()

    def fake_write(cfg: ResolvedConfig) -> None:  # pragma: no cover
        written.append(cfg)

    fn = _make_set_agent_config(fake_load, fake_write)
    result = fn("permissions.tier", "autonomous")
    assert "blocked" in result.lower() or "rejected" in result.lower()
    assert written == []


# ---------------------------------------------------------------------------
# 24. register_config_tools — all 5 tools registered
# ---------------------------------------------------------------------------


def test_register_config_tools_registers_all_five() -> None:
    registry = MagicMock()
    register_config_tools(registry)
    names = [c.args[0]["name"] for c in registry.register.call_args_list]
    assert "add_mcp_server" in names
    assert "remove_mcp_server" in names
    assert "list_mcp_servers" in names
    assert "get_agent_config" in names
    assert "set_agent_config" in names


# ---------------------------------------------------------------------------
# MED-011 — Integration tests: tool-callable path via real ToolRegistry
#
# These tests exercise the full tool-invocation path that the LLM uses:
#   register tools → call via ToolRegistry.execute(ToolCall) → JSON string response.
#
# A real ResolvedConfig is used; no mocked namespaces.  Filesystem side effects
# (add_mcp_server / remove_mcp_server) are contained in tmp_path.
# ---------------------------------------------------------------------------


def _build_real_registry(
    tmp_path: Path | None = None,
    config_override: Any | None = None,
) -> tuple[Any, Any]:
    """Return a (registry, written_configs) tuple with real tool registrations.

    The config tools are wired to an in-memory ResolvedConfig so no real
    ~/.hachi/settings.toml is touched.  MCP-management tools are wired to
    ``tmp_path`` when provided.
    """
    from hachi.core.loop import ToolRegistry
    from hachi.core.settings import ResolvedConfig
    from hachi.tools.config_tools import (
        GET_AGENT_CONFIG_SCHEMA,
        SET_AGENT_CONFIG_SCHEMA,
        _make_get_agent_config,
        _make_set_agent_config,
    )

    registry = ToolRegistry()
    cfg = config_override if config_override is not None else ResolvedConfig()
    written: list[ResolvedConfig] = []

    def _load() -> ResolvedConfig:
        return cfg

    def _write(c: ResolvedConfig) -> None:
        nonlocal cfg
        cfg = c
        written.append(c)

    registry.register(GET_AGENT_CONFIG_SCHEMA, _make_get_agent_config(_load))
    registry.register(SET_AGENT_CONFIG_SCHEMA, _make_set_agent_config(_load, _write))
    return registry, written


class TestToolCallableIntegration:
    """Integration tests: invoke config tools the same way the LLM does."""

    # ------------------------------------------------------------------
    # 25. get_agent_config — no-arg JSON string response via ToolRegistry
    # ------------------------------------------------------------------

    def test_get_agent_config_via_tool_registry(self) -> None:
        """get_agent_config() called with an empty JSON input dict returns valid JSON."""
        from hachi.core.llm import ToolCall
        from hachi.core.settings import AgentSettings, ProviderSettings, ResolvedConfig

        cfg = ResolvedConfig(
            provider=ProviderSettings(model="claude-haiku-4-5"),
            agent=AgentSettings(name="tester"),
        )
        registry, _ = _build_real_registry(config_override=cfg)

        tc = ToolCall(id="tc-1", name="get_agent_config", input={})
        raw = registry.execute(tc)

        # Must be a JSON string (not an exception)
        assert isinstance(raw, str)
        data = json.loads(raw)
        assert data["provider"]["model"] == "claude-haiku-4-5"
        assert data["agent"]["name"] == "tester"
        # Security: no api key fields
        assert "api_key" not in json.dumps(data)
        assert "api_key_ref" not in json.dumps(data)

    # ------------------------------------------------------------------
    # 26. set_agent_config — set agent.name via ToolRegistry; persisted
    # ------------------------------------------------------------------

    def test_set_agent_config_agent_name_via_tool_registry(self) -> None:
        """set_agent_config(key='agent.name', value='hal') updates config and replies."""
        from hachi.core.llm import ToolCall
        from hachi.core.settings import AgentSettings, ResolvedConfig

        cfg = ResolvedConfig(agent=AgentSettings(name="old"))
        registry, written = _build_real_registry(config_override=cfg)

        tc = ToolCall(
            id="tc-2", name="set_agent_config", input={"key": "agent.name", "value": "hal"}
        )
        raw = registry.execute(tc)

        assert isinstance(raw, str)
        # Must confirm the update, not return an error
        assert "updated" in raw.lower()
        # The write function must have been called
        assert len(written) == 1
        assert written[0].agent.name == "hal"

    # ------------------------------------------------------------------
    # 27. set_agent_config — blocked key returns error string, no exception
    # ------------------------------------------------------------------

    def test_set_agent_config_blocked_key_returns_error_not_exception(self) -> None:
        """set_agent_config on a blocked key returns an error string — never raises."""
        from hachi.core.llm import ToolCall
        from hachi.core.settings import ResolvedConfig

        registry, written = _build_real_registry(config_override=ResolvedConfig())

        tc = ToolCall(
            id="tc-3",
            name="set_agent_config",
            input={"key": "permissions.tier", "value": "unrestricted"},
        )
        # Must NOT raise — the LLM gets back an error string
        raw = registry.execute(tc)

        assert isinstance(raw, str)
        assert "blocked" in raw.lower() or "rejected" in raw.lower()
        # Config write must NOT have been called
        assert written == []

    # ------------------------------------------------------------------
    # 28. set_agent_config — unknown key returns error string, no exception
    # ------------------------------------------------------------------

    def test_set_agent_config_unknown_key_returns_error_not_exception(self) -> None:
        """set_agent_config on a key not in the allowlist returns an error string."""
        from hachi.core.llm import ToolCall
        from hachi.core.settings import ResolvedConfig

        registry, written = _build_real_registry(config_override=ResolvedConfig())

        tc = ToolCall(
            id="tc-4",
            name="set_agent_config",
            input={"key": "provider.api_key", "value": "sk-xxx"},
        )
        raw = registry.execute(tc)

        assert isinstance(raw, str)
        # Any of blocked / rejected / not in allowlist is acceptable
        assert any(kw in raw.lower() for kw in ("blocked", "rejected", "allowlist", "settable"))
        assert written == []

    # ------------------------------------------------------------------
    # 29. Full round-trip: set then get reflects the change
    # ------------------------------------------------------------------

    def test_set_then_get_round_trip(self) -> None:
        """set_agent_config followed by get_agent_config reflects the written value."""
        from hachi.core.llm import ToolCall
        from hachi.core.loop import ToolRegistry
        from hachi.core.settings import AgentSettings, ResolvedConfig
        from hachi.tools.config_tools import (
            GET_AGENT_CONFIG_SCHEMA,
            SET_AGENT_CONFIG_SCHEMA,
            _make_get_agent_config,
            _make_set_agent_config,
        )

        # Build a registry where get and set share mutable state.
        registry = ToolRegistry()
        state: list[ResolvedConfig] = [ResolvedConfig(agent=AgentSettings(name="before"))]

        def _load() -> ResolvedConfig:
            return state[0]

        def _write(c: ResolvedConfig) -> None:
            state[0] = c

        registry.register(GET_AGENT_CONFIG_SCHEMA, _make_get_agent_config(_load))
        registry.register(SET_AGENT_CONFIG_SCHEMA, _make_set_agent_config(_load, _write))

        # Step 1: set
        set_tc = ToolCall(
            id="tc-5", name="set_agent_config", input={"key": "agent.name", "value": "after"}
        )
        registry.execute(set_tc)

        # Step 2: get should now reflect the new value
        get_tc = ToolCall(id="tc-6", name="get_agent_config", input={})
        raw = registry.execute(get_tc)
        data = json.loads(raw)
        assert data["agent"]["name"] == "after"
