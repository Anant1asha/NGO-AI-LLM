"""Agent-accessible configuration and MCP-management tools.

The agent can inspect and modify a NARROW slice of configuration at runtime.
Every operation here is intentionally limited and validated — these are NOT
general-purpose file-write tools.

Security model
--------------
MCP server management
~~~~~~~~~~~~~~~~~~~~~
* ``command`` must be in :data:`ALLOWED_MCP_COMMANDS` — no arbitrary executables.
* ``args`` must not contain shell metacharacters (``; && || | > < ` $( ${``).
  Arguments are passed directly to the launcher (``shell=False``), but storing
  dangerous strings in .og files would let a later process interpret them.
* ``env_vars`` key names must NOT match :data:`_SECRET_ENV_PATTERNS`
  (``*KEY*, *TOKEN*, *SECRET*, *PASSWORD*, *CREDENTIAL*, *PRIVATE*, *AUTH*``).
  Secrets belong in the SecretStore, never in plain .og files on disk.
* ``name`` must be slug-safe (letters, digits, hyphens, underscores only).
* Sandbox tier: ``add_mcp_server`` and ``remove_mcp_server`` are blocked.
* ``remove_mcp_server`` only removes files named ``mcp-<name>.og`` — the
  same convention used by ``hachi mcp add``; bundled system nodes are safe.
* An existing server node cannot be overwritten (write-once, change via remove→add).

Config management
~~~~~~~~~~~~~~~~~
* :func:`get_agent_config` returns a *safe* snapshot: provider kind / model,
  agent name, permissions tier, memory backend.  API keys and credential refs
  are never included.
* :func:`set_agent_config` writes ONLY to :data:`SETTABLE_CONFIG_KEYS` — a
  curated allowlist of non-security settings.  Anything involving the provider
  credential, permission tier, or internal meta is permanently blocked.
* Config changes are persisted to ``settings.toml`` (atomic write).  They take
  effect on the **next** agent boot — the running process is not hot-reloaded.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# MCP security constants
# ---------------------------------------------------------------------------

#: Launchers the agent is allowed to specify as the ``command`` for an MCP server.
ALLOWED_MCP_COMMANDS: frozenset[str] = frozenset({"npx", "uvx", "python", "python3", "node", "uv"})

#: Substring patterns (case-insensitive) that make an env-var name look like a secret.
#: Keys matching any of these are rejected to prevent secrets being written to disk.
_SECRET_ENV_PATTERNS: tuple[str, ...] = (
    "key",
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "private",
    "auth",
    "bearer",
    "apikey",
    "api_key",
)

#: Shell metacharacters / injection sequences we refuse to store in args.
_SHELL_META_RE = re.compile(r"[;&|><`]|\$[({]|&&|\|\|")

# ---------------------------------------------------------------------------
# Config security constants
# ---------------------------------------------------------------------------

#: Dot-path config keys the agent is allowed to modify.
#: Everything not on this list is permanently blocked — even at depth.
SETTABLE_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "agent.name",
        "agent.persona",
        "provider.model",
        "provider.allowed_models",
        "memory.backend",
        "memory.enable_session_history",
        "memory.enable_semantic_memory",
    }
)

#: Keys that are always blocked regardless of any future expansion.
_BLOCKED_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        # Credentials — the agent must NEVER write these
        "provider.api_key",
        "provider.api_key_ref",
        "provider.api_key_env",
        # Provider kind — changing this breaks auth for the running session
        "provider.kind",
        "provider.base_url",
        # Permission escalation — hardest wall
        "permissions.tier",
        # Internal versioning
        "meta.config_version",
        "meta.created_at",
    }
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_mcp_name(name: str) -> str | None:
    """Return an error string if ``name`` is not slug-safe, else None."""
    if not name:
        return "Name must not be empty."
    if not re.match(r"^[\w-]+$", name):
        return (
            f"Name {name!r} is not slug-safe. Use letters, digits, hyphens, and underscores only."
        )
    return None


def _validate_mcp_command(command: str) -> str | None:
    """Return an error string if ``command`` is not in the allowlist, else None."""
    if command not in ALLOWED_MCP_COMMANDS:
        return (
            f"Command {command!r} is not allowed. "
            f"Permitted launchers: {sorted(ALLOWED_MCP_COMMANDS)}."
        )
    return None


def _validate_mcp_args(args: str) -> str | None:
    """Return an error string if ``args`` contains shell metacharacters, else None."""
    if _SHELL_META_RE.search(args):
        return (
            f"Args contain shell metacharacters: {args!r}. "
            "Arguments are passed directly to the launcher (no shell), "
            "but storing injection sequences is not allowed."
        )
    return None


def _validate_env_var_key(key: str) -> str | None:
    """Return an error string if the env-var key looks like a secret, else None."""
    lower = key.lower()
    for pattern in _SECRET_ENV_PATTERNS:
        if pattern in lower:
            return (
                f"Env-var key {key!r} matches secret pattern {pattern!r}. "
                "Use the SecretStore to store credentials — never write secrets to .og files."
            )
    return None


# ---------------------------------------------------------------------------
# MED-026: SkillEngine singleton for list_mcp_servers
#
# Building a SkillEngine and re-indexing all .og files on every call is
# expensive (O(#skills) I/O + parse).  We cache one engine per skills-directory
# path.  The cache is invalidated automatically if the directory changes —
# callers that add/remove .og files can pass ``invalidate=True`` to
# ``_get_cached_skill_engine`` to force a reload.
# ---------------------------------------------------------------------------

_skill_engine_lock: threading.Lock = threading.Lock()
# Maps absolute skills-dir path → cached SkillEngine instance.
_skill_engine_cache: dict[str, Any] = {}


def _get_cached_skill_engine(skills_dir: Path) -> Any:
    """Return a cached :class:`~hachi.og_engine.engine.SkillEngine` for *skills_dir*.

    The engine is built and indexed on first call for a given directory.
    Subsequent calls return the same instance.  Thread-safe via a module-level
    lock (boot is fast; contention is negligible).

    Args:
        skills_dir: Absolute path to the skills directory.

    Returns:
        A ``SkillEngine`` that has already loaded *skills_dir*.
    """
    key = str(skills_dir.resolve())
    with _skill_engine_lock:
        if key not in _skill_engine_cache:
            from hachi.og_engine.engine import SkillEngine

            engine = SkillEngine()
            engine.load_directory(skills_dir)
            _skill_engine_cache[key] = engine
        return _skill_engine_cache[key]


def _invalidate_skill_engine_cache(skills_dir: Path | None = None) -> None:
    """Invalidate the cached SkillEngine for *skills_dir* (or all entries).

    Call this after adding or removing ``.og`` files so the next
    :func:`list_mcp_servers` call sees the updated state.

    Args:
        skills_dir: Directory whose cache entry should be dropped.
                    ``None`` clears the entire cache.
    """
    with _skill_engine_lock:
        if skills_dir is None:
            _skill_engine_cache.clear()
        else:
            _skill_engine_cache.pop(str(skills_dir.resolve()), None)


# ---------------------------------------------------------------------------
# MCP tool factories
# ---------------------------------------------------------------------------

_MCP_OG_TEMPLATE = """\
::node[{name}]
->[:role=mcp]
->[:keywords=mcp, {name}]

::dense
MCP server: {name}
Command: {command} {args}

::config
command: {command}
args: {args}
"""


def _make_add_mcp_server(gate: Any = None) -> Any:
    """Factory for the add_mcp_server tool."""

    def add_mcp_server(
        name: str,
        command: str,
        args: str,
        env_vars: dict[str, str] | None = None,
    ) -> str:
        """Register a new MCP server so the agent can call its tools.

        The server is declared as an .og node (``mcp-<name>.og``) in your skills
        directory.  It is activated the **next time the agent boots** — restart
        the session after calling this.

        Security constraints (non-negotiable):
        * ``command`` must be one of: npx, uvx, python, python3, node, uv.
        * ``args`` must not contain shell metacharacters.
        * ``env_vars`` keys must not look like secrets — use SecretStore instead.
        * Existing servers cannot be overwritten; remove first if needed.
        * Not available in sandbox tier.

        Args:
            name:      Short slug identifier (e.g. ``"github"``).
            command:   Launcher executable (e.g. ``"npx"``).
            args:      Package / script arguments
                       (e.g. ``"-y @modelcontextprotocol/server-github"``).
            env_vars:  Optional plain (non-secret) env vars injected when the server starts.

        Returns:
            Confirmation string or error description.
        """
        # Tier check
        if gate is not None:
            tier = getattr(gate, "tier", None)
            if tier == "sandbox":
                return (
                    "add_mcp_server is not available in sandbox tier. "
                    "Ask the user to change the permission tier to 'guided' or higher."
                )

        # Input validation
        err = _validate_mcp_name(name)
        if err:
            return f"Validation error: {err}"
        err = _validate_mcp_command(command)
        if err:
            return f"Validation error: {err}"
        err = _validate_mcp_args(args)
        if err:
            return f"Validation error: {err}"

        for key in env_vars or {}:
            err = _validate_env_var_key(key)
            if err:
                return f"Validation error (env var {key!r}): {err}"

        # Write the .og file
        try:
            from hachi.gateway.workspace import get_skills_dir

            skills_dir = get_skills_dir()
            dest = skills_dir / f"mcp-{name}.og"

            if dest.exists():
                return (
                    f"Server {name!r} already exists at {dest}. "
                    f"Remove it first with remove_mcp_server({name!r}) "
                    "if you want to reconfigure it."
                )

            og_text = _MCP_OG_TEMPLATE.format(name=name, command=command, args=args)
            if env_vars:
                env_lines = [f"env_{k}: {v}" for k, v in env_vars.items()]
                og_text = og_text.rstrip() + "\n" + "\n".join(env_lines) + "\n"

            dest.write_text(og_text, encoding="utf-8")
            # Invalidate the SkillEngine cache so list_mcp_servers reflects the new entry.
            _invalidate_skill_engine_cache(skills_dir)
            return (
                f"MCP server {name!r} registered at {dest}. "
                f"Restart the agent session to activate it. "
                f"Command: {command} {args}" + (f" | env: {list(env_vars)}" if env_vars else "")
            )
        except OSError as exc:
            return f"Failed to write MCP server config: {exc}"

    return add_mcp_server


def _make_remove_mcp_server(gate: Any = None) -> Any:
    """Factory for the remove_mcp_server tool."""

    def remove_mcp_server(name: str) -> str:
        """Remove a user-registered MCP server.

        Only removes files named ``mcp-<name>.og`` created by ``add_mcp_server``
        or ``hachi mcp add``.  Bundled / system MCP nodes are not touched.
        Takes effect on the next agent boot.

        Args:
            name: The server's slug identifier.

        Returns:
            Confirmation string or error description.
        """
        if gate is not None:
            tier = getattr(gate, "tier", None)
            if tier == "sandbox":
                return "remove_mcp_server is not available in sandbox tier."

        err = _validate_mcp_name(name)
        if err:
            return f"Validation error: {err}"

        try:
            from hachi.gateway.workspace import get_skills_dir

            skills_dir = get_skills_dir()
            target = skills_dir / f"mcp-{name}.og"

            if not target.exists():
                return (
                    f"MCP server {name!r} not found (expected mcp-{name}.og in {skills_dir}). "
                    "Use list_mcp_servers() to see what's configured."
                )

            target.unlink()
            # Invalidate the SkillEngine cache so list_mcp_servers no longer shows this entry.
            _invalidate_skill_engine_cache(skills_dir)
            return (
                f"MCP server {name!r} removed. "
                "Restart the agent session for the change to take effect."
            )
        except OSError as exc:
            return f"Failed to remove MCP server config: {exc}"

    return remove_mcp_server


def _make_list_mcp_servers() -> Any:
    """Factory for the list_mcp_servers tool."""

    def list_mcp_servers() -> str:
        """List all configured MCP servers (static declarations).

        Reads ``.og`` nodes with ``role=mcp`` from the skills directory.
        Returns the name, command, args, and declared env-var keys (not values)
        for each server.  Tool counts are only available when the session is active.

        Returns:
            JSON string with a ``servers`` list.
        """
        try:
            from hachi.gateway.workspace import get_skills_dir

            # MED-026: use the cached engine instead of rebuilding on every call.
            skills_dir = get_skills_dir()
            engine = _get_cached_skill_engine(skills_dir)
            nodes = engine.get_nodes_by_role("mcp")

            servers = [
                {
                    "name": n.name,
                    "command": n.config.get("command", ""),
                    "args": n.config.get("args", ""),
                    # Expose key NAMES only — never values (they might be secrets)
                    "env_var_keys": [k[4:] for k in n.config if k.startswith("env_")],
                }
                for n in nodes
            ]
            return json.dumps(
                {"servers": servers, "count": len(servers)},
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc), "servers": []})

    return list_mcp_servers


# ---------------------------------------------------------------------------
# Config tool factories
# ---------------------------------------------------------------------------


def _safe_config_snapshot(config: Any) -> dict[str, Any]:
    """Return a safe, secret-free subset of ``config`` for the agent to read."""
    out: dict[str, Any] = {}
    if config is None:
        return out
    try:
        raw = config.model_dump(mode="python", exclude_none=True)
    except AttributeError:
        raw = dict(config) if isinstance(config, dict) else {}

    # provider — strip all credential fields
    provider = raw.get("provider", {})
    out["provider"] = {
        "kind": provider.get("kind", ""),
        "model": provider.get("model", ""),
        "allowed_models": provider.get("allowed_models", []),
        # base_url kept — useful for diagnosing connectivity; not a secret
        "base_url": provider.get("base_url"),
    }
    # agent
    agent = raw.get("agent", {})
    out["agent"] = {
        "name": agent.get("name", ""),
        "persona": agent.get("persona", ""),
    }
    # permissions
    perms = raw.get("permissions", {})
    out["permissions"] = {"tier": perms.get("tier", "guided")}
    # memory
    memory = raw.get("memory", {})
    out["memory"] = {
        "backend": memory.get("backend", "chroma"),
        "enable_session_history": memory.get("enable_session_history", True),
        "enable_semantic_memory": memory.get("enable_semantic_memory", True),
    }
    # limits (safe to expose)
    out["limits"] = raw.get("limits", {})
    return out


def _apply_config_patch(config: Any, key: str, raw_value: str) -> tuple[Any, str | None]:
    """Apply a single key=value patch to ``config``.

    Returns ``(updated_config, error_string | None)``.
    """
    if key in _BLOCKED_CONFIG_KEYS:
        return config, (
            f"Key {key!r} is permanently blocked for security reasons. "
            "The agent cannot modify provider credentials or permission tier."
        )
    if key not in SETTABLE_CONFIG_KEYS:
        return config, (
            f"Key {key!r} is not in the settable allowlist. "
            f"Allowed keys: {sorted(SETTABLE_CONFIG_KEYS)}."
        )

    # Parse the value into the correct Python type based on the key
    section, _, field = key.partition(".")
    if not section or not field:
        return config, f"Invalid key format {key!r} — expected 'section.field'."

    try:
        raw = config.model_dump(mode="python", exclude_none=True)
    except AttributeError:
        return config, "Config object does not support model_dump."

    # Coerce value to appropriate type
    coerced: Any = raw_value
    existing = raw.get(section, {}).get(field)
    if isinstance(existing, bool):
        if raw_value.lower() in ("true", "1", "yes"):
            coerced = True
        elif raw_value.lower() in ("false", "0", "no"):
            coerced = False
        else:
            return config, f"Expected boolean for {key!r} (true/false), got {raw_value!r}."
    elif isinstance(existing, list):
        # Comma-separated list
        coerced = [v.strip() for v in raw_value.split(",") if v.strip()]

    # Write into the raw dict and re-validate
    if section not in raw:
        raw[section] = {}
    raw[section][field] = coerced

    from hachi.core.settings import ResolvedConfig

    try:
        updated = ResolvedConfig.model_validate(raw)
    except Exception as exc:
        return config, f"Config validation failed for {key}={raw_value!r}: {exc}"

    return updated, None


def _make_get_agent_config(get_config_fn: Any) -> Any:
    """Factory for the get_agent_config tool."""

    def get_agent_config() -> str:
        """Read the current agent configuration (no secrets included).

        Returns a JSON snapshot of the active config covering provider kind/model,
        agent name, permission tier, memory backend, and any defined limits.
        API keys and credential refs are NEVER returned.

        Returns:
            JSON string with the safe config snapshot.
        """
        try:
            config = get_config_fn()
            return json.dumps(_safe_config_snapshot(config), indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    return get_agent_config


def _make_set_agent_config(get_config_fn: Any, write_config_fn: Any) -> Any:
    """Factory for the set_agent_config tool."""

    def set_agent_config(key: str, value: str) -> str:
        """Update a single non-security agent configuration setting.

        Persists the change to ``settings.toml`` (atomic write).  Changes take
        effect on the **next** agent boot — the running process is NOT hot-reloaded.

        Allowed keys::

            agent.name            — agent display name
            agent.persona         — brief personality description
            provider.model        — active model (validated against allowed_models if set)
            provider.allowed_models — comma-separated model allowlist
            memory.backend        — "chroma" or "in_memory"
            memory.enable_session_history — true/false
            memory.enable_semantic_memory — true/false

        Permanently blocked (security boundary):
        * ``provider.api_key``, ``provider.api_key_ref``, ``provider.api_key_env``
        * ``provider.kind``, ``provider.base_url``
        * ``permissions.tier`` (cannot escalate)
        * ``meta.*``

        Args:
            key:   Dot-path config key (e.g. ``"provider.model"``).
            value: String representation of the new value.

        Returns:
            Confirmation string or error description.
        """
        try:
            config = get_config_fn()
            updated, err = _apply_config_patch(config, key, value)
            if err:
                return f"Config update rejected: {err}"
            write_config_fn(updated)
            return (
                f"Config updated: {key} = {value!r}. "
                "Restart the agent session for the change to take effect."
            )
        except Exception as exc:
            return f"Failed to update config: {exc}"

    return set_agent_config


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

ADD_MCP_SERVER_SCHEMA: dict[str, Any] = {
    "name": "add_mcp_server",
    "description": (
        "Register a new MCP (Model Context Protocol) server so the agent can use its tools. "
        "Creates an .og config node in the skills directory. "
        "The server is activated on the NEXT agent session restart — not immediately. "
        "SECURITY: command must be npx/uvx/python/python3/node/uv; "
        "args must not contain shell metacharacters; "
        "env_vars must not contain credential keys (use SecretStore for secrets). "
        "Use list_mcp_servers() to check what is already configured. "
        "Blocked in sandbox permission tier."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "Short slug identifier (letters, digits, hyphens, underscores). E.g. 'github'."
                ),
            },
            "command": {
                "type": "string",
                "description": (
                    "Launcher executable. Must be one of: npx, uvx, python, python3, node, uv."
                ),
                "enum": sorted(ALLOWED_MCP_COMMANDS),
            },
            "args": {
                "type": "string",
                "description": (
                    "Arguments passed to the command. "
                    "E.g. '-y @modelcontextprotocol/server-github'. "
                    "No shell metacharacters allowed."
                ),
            },
            "env_vars": {
                "type": "object",
                "description": (
                    "Non-secret environment variables injected when the server starts. "
                    "Keys matching credential patterns (key, token, secret, password, auth, ...) "
                    "are REJECTED — use the SecretStore for those."
                ),
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["name", "command", "args"],
    },
}

REMOVE_MCP_SERVER_SCHEMA: dict[str, Any] = {
    "name": "remove_mcp_server",
    "description": (
        "Remove a user-registered MCP server (one created via add_mcp_server or "
        "hachi mcp add). Only removes files named mcp-<name>.og — bundled system "
        "servers are not affected. Takes effect on the next session restart. "
        "Blocked in sandbox permission tier."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The server's slug identifier (as shown by list_mcp_servers).",
            }
        },
        "required": ["name"],
    },
}

LIST_MCP_SERVERS_SCHEMA: dict[str, Any] = {
    "name": "list_mcp_servers",
    "description": (
        "List all configured MCP servers (static declarations from .og files). "
        "Returns name, command, args, and declared env-var key names "
        "(values are never returned). Use this before add_mcp_server to avoid duplicates."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

GET_AGENT_CONFIG_SCHEMA: dict[str, Any] = {
    "name": "get_agent_config",
    "description": (
        "Read the current agent configuration (safe subset — no API keys or credential refs). "
        "Returns provider kind/model, agent name, permission tier, memory backend, and limits. "
        "Call this first to understand what's currently configured before making changes."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

SET_AGENT_CONFIG_SCHEMA: dict[str, Any] = {
    "name": "set_agent_config",
    "description": (
        "Update a single non-security agent configuration setting. "
        "Persisted to settings.toml; takes effect on the NEXT session restart. "
        "Allowed keys: agent.name, agent.persona, provider.model, "
        "provider.allowed_models (comma-separated), memory.backend, "
        "memory.enable_session_history (true/false), "
        "memory.enable_semantic_memory (true/false). "
        "BLOCKED: any credential key, provider.kind, permissions.tier — "
        "the agent CANNOT escalate its own permissions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Dot-path config key to update (e.g. 'provider.model').",
                "enum": sorted(SETTABLE_CONFIG_KEYS),
            },
            "value": {
                "type": "string",
                "description": "New value as a string. Lists use comma-separation.",
            },
        },
        "required": ["key", "value"],
    },
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_config_tools(
    registry: Any,
    gate: Any = None,
) -> None:
    """Mount configuration and MCP-management tools onto the ToolRegistry.

    Args:
        registry: The agent's ToolRegistry.
        gate:     Optional PermissionGate for tier checks.
    """
    from hachi.core.config_loader import load_effective_config, write_global_config

    registry.register(ADD_MCP_SERVER_SCHEMA, _make_add_mcp_server(gate))
    registry.register(REMOVE_MCP_SERVER_SCHEMA, _make_remove_mcp_server(gate))
    registry.register(LIST_MCP_SERVERS_SCHEMA, _make_list_mcp_servers())
    registry.register(
        GET_AGENT_CONFIG_SCHEMA,
        _make_get_agent_config(load_effective_config),
    )
    registry.register(
        SET_AGENT_CONFIG_SCHEMA,
        _make_set_agent_config(load_effective_config, write_global_config),
    )
