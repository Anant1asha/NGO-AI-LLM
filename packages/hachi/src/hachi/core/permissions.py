"""
Device Permission Gate

The single enforcement layer for all device access in Hachi.
Reads ~/.hachi/device-permissions.og on boot and gates every tool call
that touches the user's filesystem or terminal.

Architecture:
    device-permissions.og → PermissionGate (immutable) → wraps all tools

Security Invariants:
    1. Only device-permissions.og can grant device access.
    2. blocked_paths always wins over allowed_paths.
    3. Missing file = Sandbox tier (fail safe, never fail open).
    4. All paths resolved to canonical absolute form (no .. traversal).
    5. The gate is immutable after construction — no runtime modification.
"""

import os
import shlex
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# ==========================================
# Data Models (Immutable)
# ==========================================


@dataclass(frozen=True)
class PermissionResult:
    """
    The outcome of a single permission check.

    Attributes:
        allowed: Whether the operation is permitted.
        reason: Human-readable explanation. Shown to the LLM on denial
                so it can inform the user what to change.
    """

    allowed: bool
    reason: str


@dataclass(frozen=True)
class PermissionRequest:
    """A runtime approval request emitted when policy denies a sensitive action."""

    request_id: str
    operation: str
    tool: str
    target: str
    reason: str
    policy_summary: str


@dataclass(frozen=True)
class PermissionDecision:
    """User decision returned by approval UIs (TUI modal, future APIs)."""

    action: Literal["approve", "deny", "allow_once"]
    rationale: str = ""


@dataclass(frozen=True)
class FilesystemRules:
    """Immutable ruleset for filesystem access."""

    allowed_paths: tuple[Path, ...]
    blocked_paths: tuple[Path, ...]
    allow_all: bool
    allow_write: bool
    allow_delete: bool
    max_file_size_mb: int


@dataclass(frozen=True)
class TerminalRules:
    """Immutable ruleset for terminal command execution."""

    enabled: bool
    allowed_commands: tuple[str, ...]
    blocked_commands: tuple[str, ...]
    allow_all: bool
    timeout: int


@dataclass(frozen=True)
class MCPRules:
    """Immutable ruleset for MCP servers."""

    filesystem_enabled: bool
    # SEC-005: non-filesystem MCP servers run arbitrary commands at boot.
    # Community-pack-sourced servers are default-denied unless allow-listed by
    # name ([mcp_servers] allowed_servers in device-permissions.og) or the tier
    # is unrestricted (allowed_servers="*").
    allow_all_servers: bool = False
    server_allowlist: tuple[str, ...] = ()


# ==========================================
# Constants
# ==========================================

_HOME = Path.home()
_PERMISSIONS_FILE_NAME = "device-permissions.og"
_PERMISSIONS_HINT = f"~/.hachi/{_PERMISSIONS_FILE_NAME}"

# Commands that are safe for everyday use
_SAFE_COMMANDS = (
    # Filesystem navigation & management
    "dir",
    "ls",
    "mkdir",
    "md",
    "move",
    "copy",
    "ren",
    "rename",
    "type",
    "cat",
    "head",
    "tail",
    "echo",
    "find",
    "where",
    "which",
    "tree",
    "cd",
    "pushd",
    "popd",
    # App launching (Windows: start, macOS: open, Linux: xdg-open)
    "start",
    "open",
    "xdg-open",
    "explorer",
    # Developer tools
    "pip",
    "pip3",
    "git",
    "npm",
    "npx",
    "code",
    "notepad",
    # System info (read-only)
    "cls",
    "clear",
    "whoami",
    "hostname",
    "ping",
)

# Commands that can read or exfiltrate file contents — their arguments must be
# checked against blocked_paths even when the executable itself is on the allowlist.
_EXFIL_STEMS: frozenset[str] = frozenset(
    {
        "cat",
        "type",
        "copy",
        "move",
        "find",
        "head",
        "tail",
        "dir",
        "ls",
        "tree",
        "xcopy",
        "ren",
        "rename",
    }
)

# Commands that can cause irreversible damage
_DANGEROUS_COMMANDS = (
    "rm -rf",
    "del /s /q",
    "del /f /s /q",
    "format",
    "diskpart",
    "shutdown",
    "restart",
    "taskkill",
    "reg delete",
    "reg add",
    "net user",
    "net localgroup",
    "cipher /w",
    "sfc",
    "dism",
    "bcdedit",
    "powershell -enc",
    "powershell -e ",
)

# The OS-specific user application-data directory holds app configs, OAuth tokens,
# and (on macOS) the Keychain — block the agent from reading it by default. The
# directory differs per platform, so a single hardcoded ``~/AppData`` (Windows-only)
# left ``~/Library`` (macOS) and ``~/.config`` (Linux) unguarded.
if sys.platform == "darwin":
    _APP_DATA_DIR = _HOME / "Library"
elif sys.platform == "win32":
    _APP_DATA_DIR = _HOME / "AppData"
else:  # linux and other POSIX
    _APP_DATA_DIR = _HOME / ".config"

# Paths that should always be blocked by default
_DEFAULT_BLOCKED = (
    _HOME / ".ssh",
    _HOME / ".hachi",
    _APP_DATA_DIR,
)

# ==========================================
# Tier Default Configurations
# ==========================================
# Each tier defines the default config values per permission category.
# User-provided values in device-permissions.og override these.

_TIER_DEFAULTS: dict[str, dict[str, dict[str, str]]] = {
    "sandbox": {
        "filesystem": {
            "allowed_paths": str(_HOME / "Desktop"),
            "blocked_paths": ", ".join(str(p) for p in _DEFAULT_BLOCKED),
            "allow_write": "true",
            "allow_delete": "false",
            "max_file_size_mb": "50",
        },
        "terminal": {
            "enabled": "false",
            "allowed_commands": "",
            "blocked_commands": "",
            "timeout": "120",
        },
        "mcp_filesystem": {
            "enabled": "true",
        },
    },
    "guided": {
        "filesystem": {
            "allowed_paths": ", ".join(
                str(p)
                for p in [
                    _HOME / "Desktop",
                    _HOME / "Downloads",
                    _HOME / "Documents",
                ]
            ),
            "blocked_paths": ", ".join(str(p) for p in _DEFAULT_BLOCKED),
            "allow_write": "true",
            "allow_delete": "false",
            "max_file_size_mb": "50",
        },
        "terminal": {
            "enabled": "true",
            "allowed_commands": ", ".join(_SAFE_COMMANDS),
            "blocked_commands": ", ".join(_DANGEROUS_COMMANDS),
            "timeout": "120",
        },
        "mcp_filesystem": {
            "enabled": "true",
        },
    },
    "unrestricted": {
        "filesystem": {
            "allowed_paths": "*",
            "blocked_paths": str(_HOME / ".ssh"),
            "allow_write": "true",
            "allow_delete": "true",
            "max_file_size_mb": "500",
        },
        "terminal": {
            "enabled": "true",
            "allowed_commands": "*",
            "blocked_commands": "format, shutdown",
            "timeout": "120",
        },
        "mcp_filesystem": {
            "enabled": "true",
        },
    },
}


# ==========================================
# Helpers
# ==========================================


def _is_unc(raw: str) -> bool:
    """Return True if *raw* is a Windows UNC path (``\\\\server\\share`` or ``//server/share``)."""
    stripped = raw.strip()
    return stripped.startswith("\\\\") or stripped.startswith("//")


def _resolve_path(raw: str) -> Path:
    """Resolve a raw path string to an absolute canonical path."""
    raw = raw.strip()
    if raw.startswith("~"):
        return Path(raw).expanduser().resolve()
    return Path(raw).resolve()


def _parse_csv(raw: str) -> tuple[str, ...]:
    """Parse a comma-separated string into a tuple of stripped values."""
    if not raw or not raw.strip():
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _is_subpath(child: Path, parent: Path) -> bool:
    """Check if child is equal to or a descendant of parent."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _get_config(node_map: dict, node_name: str, tier: str) -> dict[str, str]:
    """
    Get merged config for a permission category.
    User-provided values override tier defaults.
    """
    defaults = _TIER_DEFAULTS.get(tier, _TIER_DEFAULTS["sandbox"]).get(node_name, {})
    parsed = node_map.get(node_name)
    user_config = parsed.config if parsed else {}
    return {**defaults, **user_config}


# ==========================================
# PermissionGate
# ==========================================


class PermissionGate:
    """
    The central permission enforcement layer for Hachi.

    Constructed once on boot from device-permissions.og. Immutable after init.
    All tool functions that touch the device must call check_path() or
    check_command() before executing.

    Usage:
        gate = PermissionGate(Path("~/.hachi/device-permissions.og"))
        result = gate.check_path("/Users/x/Desktop/file.txt", "read")
        if not result.allowed:
            return f"⛔ Permission Denied: {result.reason}"
    """

    def __init__(self, permissions_file: Path):
        """
        Parse device-permissions.og and build immutable rule sets.
        Falls back to Sandbox defaults if the file is missing or malformed.
        """
        node_map: dict = {}

        if permissions_file.exists():
            try:
                from hachi.og_engine.parser import parse_og_file

                og_file = parse_og_file(str(permissions_file))
                node_map = {n.name: n for n in og_file.nodes}
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error("Failed to parse device permissions: %s", e)
                # Malformed file → Sandbox fallback

        # Determine tier
        device_node = node_map.get("device_access")
        self._tier = device_node.config.get("tier", "sandbox") if device_node else "sandbox"
        if self._tier not in _TIER_DEFAULTS:
            self._tier = "sandbox"

        # Build immutable rule sets
        self._fs = self._build_filesystem_rules(node_map)
        self._term = self._build_terminal_rules(node_map)
        self._mcp = self._build_mcp_rules(node_map)

    # ── Rule Builders ──

    def _build_filesystem_rules(self, node_map: dict) -> FilesystemRules:
        """Construct FilesystemRules from parsed config + tier defaults."""
        cfg = _get_config(node_map, "filesystem", self._tier)
        raw_allowed = cfg.get("allowed_paths", "")
        raw_blocked = cfg.get("blocked_paths", "")

        allow_all = raw_allowed.strip() == "*"
        allowed = () if allow_all else tuple(_resolve_path(p) for p in _parse_csv(raw_allowed))
        blocked = tuple(_resolve_path(p) for p in _parse_csv(raw_blocked))

        return FilesystemRules(
            allowed_paths=allowed,
            blocked_paths=blocked,
            allow_all=allow_all,
            allow_write=cfg.get("allow_write", "true").lower() == "true",
            allow_delete=cfg.get("allow_delete", "false").lower() == "true",
            max_file_size_mb=int(cfg.get("max_file_size_mb", "50")),
        )

    def _build_terminal_rules(self, node_map: dict) -> TerminalRules:
        """Construct TerminalRules from parsed config + tier defaults."""
        cfg = _get_config(node_map, "terminal", self._tier)
        raw_allowed = cfg.get("allowed_commands", "")
        raw_blocked = cfg.get("blocked_commands", "")

        allow_all = raw_allowed.strip() == "*"
        allowed = () if allow_all else _parse_csv(raw_allowed)
        blocked = _parse_csv(raw_blocked)

        return TerminalRules(
            enabled=cfg.get("enabled", "false").lower() == "true",
            allowed_commands=allowed,
            blocked_commands=blocked,
            allow_all=allow_all,
            timeout=int(cfg.get("timeout", "120")),
        )

    def _build_mcp_rules(self, node_map: dict) -> MCPRules:
        """Construct MCPRules from parsed config + tier defaults."""
        cfg = _get_config(node_map, "mcp_filesystem", self._tier)
        servers_cfg = _get_config(node_map, "mcp_servers", self._tier)
        raw_allowed = servers_cfg.get("allowed_servers", "").strip()
        # Tier default when undeclared: unrestricted allows all, others deny.
        if not raw_allowed and self._tier == "unrestricted":
            raw_allowed = "*"
        allow_all = raw_allowed == "*"
        allowlist = () if allow_all else tuple(_parse_csv(raw_allowed))
        return MCPRules(
            filesystem_enabled=cfg.get("enabled", "true").lower() == "true",
            allow_all_servers=allow_all,
            server_allowlist=allowlist,
        )

    # ── Internal Helpers ──

    def _check_path_args(
        self, arg_tokens: list[str], *, assume_paths: bool = False
    ) -> PermissionResult | None:
        """
        Scan command argument tokens for filesystem paths that fall inside a blocked_path.

        Tokens that start with ``-`` or ``--`` (flags) are skipped.  For each
        remaining token that can be resolved as a Path, the canonical form is
        checked against every entry in ``self._fs.blocked_paths``.

        Args:
            arg_tokens: The argv[1:] slice of the original command token list.
            assume_paths: Treat bare tokens (no separator, ``~`` or ``.``) as
                filenames even when they do not exist yet. Passed for commands
                classified as path-takers (``_EXFIL_STEMS``). For every other
                command a bare token is still resolved when it *does* exist,
                because a relative filename is a path whenever the process cwd
                sits inside a blocked directory.

        Returns:
            A denied ``PermissionResult`` if any argument resolves inside a
            blocked path, otherwise ``None`` (caller continues as normal).
        """
        for token in arg_tokens:
            token = token.strip("\"'")
            if not token:
                continue
            if token.startswith("-"):
                # P-01b: `--flag=value` carries its path in the right-hand side.
                # Skipping every token that starts with "-" meant
                # `code --file=~/.ssh/id_rsa` was never inspected. Keep skipping
                # bare flags, but look at the value half when there is one.
                if "=" not in token:
                    continue
                token = token.split("=", 1)[1].strip("\"'")
                if not token:
                    continue
            # P-01: tokens with a separator, ``~`` or ``.`` are paths outright.
            # A bare token used to be skipped unconditionally, which meant
            # `cat id_rsa` was permitted whenever cwd was inside a blocked
            # directory — the token was never resolved against that cwd.
            looks_like_path = any(c in token for c in ("/", "\\", "~", "."))
            if not looks_like_path and not assume_paths:
                try:
                    if not Path(token).exists():
                        continue
                except OSError:
                    continue
            try:
                resolved = Path(token).expanduser().resolve()
            except Exception:
                continue
            for bp in self._fs.blocked_paths:
                if _is_subpath(resolved, bp):
                    return PermissionResult(False, "Access to blocked path denied.")
        return None

    # ── Public Check Methods ──

    def check_path(self, path: str, operation: str) -> PermissionResult:
        """
        Check if a filesystem path is accessible for a given operation.

        Args:
            path: Absolute or relative path to check.
            operation: One of 'read', 'write', 'delete', 'list'.

        Evaluation order:
            1. Resolve to canonical absolute path.
            2. Blocked paths check → DENY (always wins).
            3. Allow-all check → proceed to operation check.
            4. Allowed paths check → if match, proceed to operation check.
            5. Default → DENY.

        Returns:
            PermissionResult with .allowed and .reason.
        """
        # UC-PERM-002: reject Windows UNC paths before any resolution attempt.
        # UNC paths (\\server\share or //server/share) bypass blocked-path checks
        # because they resolve to network locations that cannot be matched against
        # the local allowed_paths list.
        if _is_unc(path):
            return PermissionResult(False, "UNC network paths are not permitted.")

        try:
            resolved = _resolve_path(path)
        except Exception:
            return PermissionResult(False, f"Invalid path: '{path}'.")

        # 1. Blocked paths always win
        for bp in self._fs.blocked_paths:
            if _is_subpath(resolved, bp):
                return PermissionResult(
                    False,
                    f"'{resolved}' is inside blocked directory '{bp}'. "
                    f"This restriction cannot be overridden.",
                )

        # 2. Path accessibility check
        path_allowed = self._fs.allow_all
        if not path_allowed:
            for ap in self._fs.allowed_paths:
                if _is_subpath(resolved, ap):
                    path_allowed = True
                    break

        if not path_allowed:
            return PermissionResult(
                False,
                f"'{resolved}' is not in your allowed directories. "
                f"Add it to allowed_paths in {_PERMISSIONS_HINT}.",
            )

        # 3. Operation-specific checks
        if operation == "write" and not self._fs.allow_write:
            return PermissionResult(
                False,
                f"Write operations are disabled. Set allow_write=true in {_PERMISSIONS_HINT}.",
            )

        if operation == "delete" and not self._fs.allow_delete:
            return PermissionResult(
                False,
                f"Delete operations are disabled. Set allow_delete=true in {_PERMISSIONS_HINT}.",
            )

        if operation in {"read", "write"} and resolved.exists() and resolved.is_file():
            max_bytes = self._fs.max_file_size_mb * 1024 * 1024
            try:
                current_size = resolved.stat().st_size
            except OSError:
                current_size = 0
            if current_size > max_bytes:
                return PermissionResult(
                    False,
                    f"'{resolved}' exceeds max_file_size_mb={self._fs.max_file_size_mb}. "
                    f"Reduce file size or increase max_file_size_mb in {_PERMISSIONS_HINT}.",
                )

        return PermissionResult(True, f"Path '{resolved}' is accessible for '{operation}'.")

    def check_command(self, command: str) -> PermissionResult:
        """
        Check if a terminal command is allowed to execute.

        Args:
            command: The raw shell command string.

        Evaluation order:
            1. Is terminal enabled? → DENY if not.
            2. Check blocked_commands (substring match) → DENY.
            3. Is allowed_commands '*'? → ALLOW.
            4. Check allowed_commands (prefix match) → ALLOW.
            5. Default → DENY.

        Returns:
            PermissionResult with .allowed and .reason.
        """
        if not self._term.enabled:
            return PermissionResult(
                False,
                f"Terminal access is disabled in '{self._tier}' tier. "
                f"Set terminal enabled=true in {_PERMISSIONS_HINT}.",
            )

        cmd_lower = command.strip().lower()
        cmd_tokens_lower = cmd_lower.split()

        # Blocked commands — multi-token patterns use order-insensitive token matching;
        # single-token patterns use exact name match against the first token.
        for bc in self._term.blocked_commands:
            bc_lower = bc.lower()
            bc_tokens = bc_lower.split()
            if len(bc_tokens) > 1:
                # Multi-token pattern: every pattern token must appear in the command tokens
                if all(t in cmd_tokens_lower for t in bc_tokens):
                    return PermissionResult(
                        False,
                        f"'{bc}' is a blocked command pattern. "
                        f"This restriction is in place for your safety.",
                    )
            else:
                # Single-token pattern: match the token anywhere in the command
                # (covers compound commands like "echo foo && shutdown /r /t 0")
                if bc_lower in cmd_tokens_lower:
                    return PermissionResult(
                        False,
                        f"'{bc}' is a blocked command pattern. "
                        f"This restriction is in place for your safety.",
                    )

        # Allow-all shortcut
        if self._term.allow_all:
            return PermissionResult(True, "Command allowed (unrestricted mode).")

        # P-01b: tokenise exactly the way the executor will. `os_tools` runs the
        # command through shlex.split, so using plain .split() here let a quoted
        # argument fragment into harmless pieces: with a blocked path containing a
        # space, `code "/…/blocked dir/id_rsa"` produced the tokens `code`,
        # `"/…/blocked`, `dir/id_rsa"` — none of which resolved inside the blocked
        # directory — and was allowed. Fall back on unbalanced quotes so we still
        # return a verdict instead of raising.
        try:
            tokens = shlex.split(command, posix=(os.name != "nt"))
        except ValueError:
            tokens = command.strip().split()
        executable = tokens[0] if tokens else ""
        executable_name = Path(executable.strip("\"'")).name.lower()
        executable_stem = Path(executable_name).stem.lower()
        interpreter_stems = {
            "python",
            "python3",
            "node",
            "pwsh",
            "powershell",
            "bash",
            "sh",
            "zsh",
            "cmd",
        }

        # In guided/sandbox modes, block general-purpose interpreters that can bypass
        # filesystem path constraints from within an allowed terminal command.
        if self._tier != "unrestricted" and executable_stem in interpreter_stems:
            return PermissionResult(
                False,
                f"'{executable_stem}' is blocked in {self._tier} tier because it can bypass "
                "filesystem protections.",
            )

        # Prevent wrapper command bypasses like "npx node ..." in guided/sandbox tiers.
        if self._tier != "unrestricted" and executable_stem in {"npx", "npm", "pip", "pip3"}:
            for token in tokens[1:]:
                candidate = token.strip("\"'")
                if not candidate or candidate.startswith("-"):
                    continue
                candidate_name = Path(candidate).name.lower()
                candidate_stem = Path(candidate_name).stem.lower()
                if candidate_stem in interpreter_stems:
                    return PermissionResult(
                        False,
                        f"Nested interpreter '{candidate_stem}' is blocked in {self._tier} tier.",
                    )

        # Allowed commands (executable name match)
        for ac in self._term.allowed_commands:
            expected = ac.lower().strip()
            if executable_name == expected or executable_stem == expected:
                # FIX C1b — privileged sub-command guard (runs after allowlist match)
                arg_tokens = [t.lower() for t in tokens[1:]]
                if executable_stem == "git" and ("-c" in arg_tokens or "config" in arg_tokens):
                    return PermissionResult(
                        False, f"Command is privileged and blocked in {self._tier} tier."
                    )
                if executable_stem in ("pip", "pip3") and "install" in arg_tokens:
                    return PermissionResult(
                        False, f"Command is privileged and blocked in {self._tier} tier."
                    )

                # P-01c: `find` takes a NESTED COMMAND, so scanning its arguments
                # for paths does not help — `find / -name id_rsa -exec cat {} +`
                # has no blocked path among its tokens (`/`, `cat`, `{}`, `+` are
                # all harmless) yet reads the file end to end. Deny the exec
                # primaries outright in guided/sandbox, mirroring the git/pip
                # privileged-subcommand guard above. `-execdir`, `-ok` and `-okdir`
                # are the same primitive with slightly different confirmation.
                if executable_stem == "find" and any(
                    flag in arg_tokens for flag in ("-exec", "-execdir", "-ok", "-okdir")
                ):
                    return PermissionResult(
                        False,
                        f"'find' with -exec is blocked in {self._tier} tier because it "
                        "runs an arbitrary command against matched files.",
                    )

                # P-01 — scan arguments for blocked paths on EVERY allowlisted
                # command. This was previously gated on `executable_stem in
                # _EXFIL_STEMS`, so the GUI/editor launchers that sit in
                # _SAFE_COMMANDS but not in that set (code, open, notepad,
                # xdg-open, explorer, start) returned "allowed" without
                # inspecting a single argument: `code ~/.ssh/id_rsa` passed
                # while `cat ~/.ssh/id_rsa` was denied.
                #
                # _EXFIL_STEMS is retained because it still carries meaning: for
                # path-taking commands, bare arguments are presumed to be
                # filenames even before they exist on disk.
                blocked_result = self._check_path_args(
                    tokens[1:], assume_paths=executable_stem in _EXFIL_STEMS
                )
                if blocked_result is not None:
                    return blocked_result

                return PermissionResult(True, f"Command '{ac}' is allowed.")

        return PermissionResult(
            False,
            f"'{command.split()[0]}' is not in your allowed commands. "
            f"Add it to allowed_commands in {_PERMISSIONS_HINT}.",
        )

    def require_action(self, action: str, summary: str, detail: str = "") -> PermissionResult:
        """Tier-gated approval for a destructive/outbound action.

        When no human approver is connected the tier determines the outcome:
        - ``unrestricted`` → allowed.
        - ``guided`` / ``sandbox`` → denied with an actionable message (UC-PERM-005
          timeout-driven denials carry "timed out" in their rationale to distinguish
          them from explicit user denials that flow through this method).

        Args:
            action:  Canonical action name, e.g. ``"send_email"`` or ``"trash_file"``.
            summary: Short human-readable description shown to the user.
            detail:  Optional extended context.

        Returns:
            :class:`PermissionResult` with ``allowed`` and ``reason`` set.
        """
        if self._tier == "unrestricted":
            return PermissionResult(True, "auto-approved (unrestricted tier)")
        return PermissionResult(
            False,
            "This action needs human approval. Connect the TUI or web companion to approve, "
            "or set tier=unrestricted in ~/.hachi/device-permissions.og.",
        )

    def is_mcp_filesystem_enabled(self) -> bool:
        """Whether the MCP filesystem server should be started."""
        return self._mcp.filesystem_enabled

    def is_mcp_server_allowed(self, name: str, *, trusted: bool = False) -> PermissionResult:
        """Whether a non-filesystem MCP server may be started (SEC-005).

        Built-in (``trusted``) servers shipped with Hachi are always permitted
        (still subject to capability/OAuth gating elsewhere).  A server whose
        ``.og`` definition came from an installed community pack runs an
        arbitrary ``command`` at boot, so it is default-denied unless the tier
        is unrestricted or the server is explicitly allow-listed by name in
        ``device-permissions.og`` ([mcp_servers] allowed_servers=...).
        """
        if trusted:
            return PermissionResult(True, "Built-in MCP server.")
        if self._mcp.allow_all_servers:
            return PermissionResult(True, "MCP servers unrestricted by tier.")
        if name in self._mcp.server_allowlist:
            return PermissionResult(True, "MCP server explicitly allow-listed.")
        return PermissionResult(
            False,
            f"Untrusted MCP server {name!r} is not approved for tier "
            f"{self._tier!r}. Add it to [mcp_servers] allowed_servers in "
            "device-permissions.og to enable it.",
        )

    def get_allowed_paths(self) -> list[Path]:
        """
        Resolved absolute paths the agent can access.
        Used by the MCP boot sequence to configure the filesystem server.
        Returns all user-accessible paths (excluding blocked).
        """
        if self._fs.allow_all:
            # For unrestricted, give MCP common user dirs (MCP needs explicit paths)
            return [_HOME / "Desktop", _HOME / "Downloads", _HOME / "Documents"]
        return list(self._fs.allowed_paths)

    def get_system_prompt_injection(self) -> str:
        """
        Returns a system prompt block informing the LLM of its boundaries.
        Prevents the LLM from wasting tokens on operations that will be blocked.
        """
        lines = ["\n--- DEVICE PERMISSIONS ---"]
        lines.append(f"Access Tier: {self._tier.upper()}")

        if self._fs.allow_all:
            lines.append("Filesystem: FULL ACCESS (some paths still blocked for safety)")
        else:
            path_names = [p.name for p in self._fs.allowed_paths]
            lines.append(f"Accessible Folders: {', '.join(path_names)}")

        if self._term.enabled:
            lines.append("Terminal: ENABLED (some commands may be restricted)")
        else:
            lines.append("Terminal: DISABLED — do NOT use run_terminal_command")

        if not self._fs.allow_delete:
            lines.append("Delete Operations: DISABLED — do NOT delete files")

        lines.append(
            "If a tool returns '⛔ Permission Denied', do NOT retry. "
            "Inform the user and suggest they update " + _PERMISSIONS_HINT
        )
        return "\n".join(lines)

    # ── Properties ──

    @property
    def tier(self) -> str:
        """The active permission tier: 'sandbox', 'guided', or 'unrestricted'."""
        return self._tier

    @property
    def terminal_timeout(self) -> int:
        """Max seconds a terminal command is allowed to run."""
        return self._term.timeout

    @property
    def max_file_size_bytes(self) -> int:
        """Max bytes allowed for filesystem read/write operations."""
        return self._fs.max_file_size_mb * 1024 * 1024

    @property
    def summary(self) -> str:
        """Human-readable one-liner for the boot banner."""
        if self._fs.allow_all:
            paths_str = "All"
        else:
            paths_str = ", ".join(p.name for p in self._fs.allowed_paths)
        terminal_str = "ON" if self._term.enabled else "OFF"
        return f"Tier: {self._tier.capitalize()} | Folders: {paths_str} | Terminal: {terminal_str}"


class InteractivePermissionGate:
    """Permission gate wrapper that supports interactive escalation decisions.

    The base PermissionGate remains the source of truth. Escalations only apply
    in-memory for the current process and never modify device-permissions.og.
    """

    def __init__(
        self,
        base_gate: PermissionGate,
        approval_handler: Callable[[PermissionRequest], PermissionDecision] | None = None,
        event_emitter: Callable[[str, dict[str, str]], None] | None = None,
    ):
        self._base = base_gate
        self._approval_handler = approval_handler
        self._emit = event_emitter or (lambda *_a, **_kw: None)
        self._allowed_session_paths: set[tuple[str, str]] = set()
        self._allowed_session_commands: set[str] = set()

    @property
    def summary(self) -> str:
        return self._base.summary

    @property
    def terminal_timeout(self) -> int:
        return self._base.terminal_timeout

    @property
    def tier(self) -> str:
        return self._base.tier

    @property
    def max_file_size_bytes(self) -> int:
        return self._base.max_file_size_bytes

    def is_mcp_filesystem_enabled(self) -> bool:
        return self._base.is_mcp_filesystem_enabled()

    def is_mcp_server_allowed(self, name: str, *, trusted: bool = False) -> PermissionResult:
        return self._base.is_mcp_server_allowed(name, trusted=trusted)

    def get_allowed_paths(self) -> list[Path]:
        return self._base.get_allowed_paths()

    def get_system_prompt_injection(self) -> str:
        return self._base.get_system_prompt_injection()

    def _request_decision(
        self,
        operation: str,
        tool: str,
        target: str,
        reason: str,
    ) -> PermissionDecision:
        request = PermissionRequest(
            request_id=uuid.uuid4().hex,
            operation=operation,
            tool=tool,
            target=target,
            reason=reason,
            policy_summary=self._base.summary,
        )

        self._emit(
            "permission.requested",
            {
                "request_id": request.request_id,
                "operation": operation,
                "tool": tool,
                "target": target,
                "reason": reason,
                "policy_summary": request.policy_summary,
            },
        )

        if not self._approval_handler:
            decision = PermissionDecision(action="deny", rationale="No approval handler available")
        else:
            try:
                decision = self._approval_handler(request)
            except Exception as exc:
                decision = PermissionDecision(
                    action="deny", rationale=f"Approval handler failed: {exc}"
                )

        self._emit(
            "permission.decided",
            {
                "request_id": request.request_id,
                "operation": operation,
                "tool": tool,
                "target": target,
                "decision": decision.action,
                "reason": decision.rationale or reason,
            },
        )

        return decision

    def check_path(self, path: str, operation: str) -> PermissionResult:
        try:
            resolved_target = str(_resolve_path(path))
        except Exception:
            resolved_target = path
        if (operation, resolved_target) in self._allowed_session_paths:
            return PermissionResult(True, "Allowed for current runtime session.")

        base_result = self._base.check_path(path, operation)
        if base_result.allowed:
            return base_result

        decision = self._request_decision(
            operation=operation,
            tool="filesystem",
            target=resolved_target,
            reason=base_result.reason,
        )

        if decision.action == "approve":
            self._allowed_session_paths.add((operation, resolved_target))
            return PermissionResult(True, "Approved for session by operator.")
        if decision.action == "allow_once":
            # MED-007: allow_once is single-use — do NOT add to the session set so
            # the next identical request is sent to the approval handler again.
            return PermissionResult(True, "Allowed once by operator.")
        return PermissionResult(False, decision.rationale or base_result.reason)

    def check_command(self, command: str) -> PermissionResult:
        normalized = command.strip()
        if normalized in self._allowed_session_commands:
            return PermissionResult(True, "Allowed for current runtime session.")

        base_result = self._base.check_command(command)
        if base_result.allowed:
            return base_result

        decision = self._request_decision(
            operation="execute",
            tool="run_terminal_command",
            target=normalized,
            reason=base_result.reason,
        )

        if decision.action == "approve":
            self._allowed_session_commands.add(normalized)
            return PermissionResult(True, "Approved for session by operator.")
        if decision.action == "allow_once":
            # MED-007: allow_once is single-use — do NOT add to the session set so
            # the next identical request is sent to the approval handler again.
            return PermissionResult(True, "Allowed once by operator.")
        return PermissionResult(False, decision.rationale or base_result.reason)

    def require_action(self, action: str, summary: str, detail: str = "") -> PermissionResult:
        """Gate a destructive/outbound action through the TUI approval handler.

        Reuses the existing ``_request_decision`` modal path so the TUI's
        approval UI handles action approvals the same way it handles path/command
        escalations.  ``approve`` and ``allow_once`` both map to ``allowed=True``;
        ``deny`` maps to ``allowed=False`` with the operator's rationale preserved
        (UC-PERM-005: explicit user denials contain the operator rationale, while
        timeout-driven denials contain "timed out" set by the registry wait).

        Args:
            action:  Canonical action name, e.g. ``"send_email"``.
            summary: Short human-readable description of the action.
            detail:  Optional extended context for the approval UI.

        Returns:
            :class:`PermissionResult` with ``allowed`` and ``reason`` set.
        """
        decision = self._request_decision(
            operation="action",
            tool=action,
            target=summary,
            reason=detail or summary,
        )
        if decision.action in ("approve", "allow_once"):
            return PermissionResult(True, decision.rationale or "approved by operator")
        return PermissionResult(False, decision.rationale or "denied by operator")


# ==========================================
# Dry-Run Gate
# ==========================================


class DryRunGate:
    """Read-only wrapper around :class:`PermissionGate` for workflow dry-runs.

    All read operations are forwarded transparently.  Write, delete, and
    outbound-send operations are **denied** with a ``"[dry-run]"`` prefix so
    the LLM can report *what would happen* without touching any external state.

    Usage::

        dry = DryRunGate(base_gate)
        result = dry.check_path("/home/user/doc.txt", "write")
        # result.allowed == False
        # result.reason == "[dry-run] Write blocked — dry-run mode is active."
    """

    _WRITE_OPS = frozenset({"write", "delete", "create", "update"})

    def __init__(self, base_gate: PermissionGate | InteractivePermissionGate) -> None:
        self._base = base_gate

    @property
    def summary(self) -> str:
        return self._base.summary + "  [dry-run]"

    def is_dry_run(self) -> bool:
        return True

    def check_path(self, path: str, operation: str) -> PermissionResult:
        """Allow reads; block writes and deletes with a dry-run explanation."""
        if operation in self._WRITE_OPS:
            return PermissionResult(
                False,
                f"[dry-run] {operation.capitalize()} blocked — dry-run mode is active. "
                "No files will be modified.",
            )
        return self._base.check_path(path, operation)

    def check_command(self, command: str) -> PermissionResult:
        """Allow read-only commands; block mutating shell commands."""
        _safe_prefixes = ("ls ", "ls\n", "cat ", "head ", "tail ", "echo ", "grep ", "find ")
        cmd_lower = command.lstrip().lower()
        is_safe = any(cmd_lower.startswith(p) for p in _safe_prefixes) or cmd_lower in {
            "ls",
            "pwd",
            "date",
            "whoami",
        }
        if not is_safe:
            return PermissionResult(
                False,
                "[dry-run] Shell command blocked — dry-run mode only allows read-only commands.",
            )
        return self._base.check_command(command)

    def stub_outbound(self, tool: str, payload: dict) -> str:
        """Return a human-readable stub for outbound tool calls during dry-run."""
        return f"[dry-run] would call {tool!r} with: {payload}"


# ==========================================
# Template Generator
# ==========================================


def generate_permissions_og(tier: str, custom_paths: list[str] | None = None) -> str:
    """
    Generate the contents of a device-permissions.og file for the given tier.

    Args:
        tier: One of 'sandbox', 'guided', 'unrestricted'.
        custom_paths: Optional list of custom paths for the filesystem node.
                      If None, tier defaults are used.

    Returns:
        The full .og file content as a string.
    """
    defaults = _TIER_DEFAULTS.get(tier, _TIER_DEFAULTS["sandbox"])
    fs = defaults["filesystem"].copy()
    term = defaults["terminal"]
    mcp = defaults["mcp_filesystem"]

    if custom_paths:
        fs["allowed_paths"] = ", ".join(custom_paths)

    lines = [
        "# ============================================================",
        "#  Hachi Device Permissions",
        "#  Controls what the agent can access on your device.",
        "#  Edit this file anytime, or run: hachi permissions",
        "# ============================================================",
        "",
        "::meta",
        "  title: Device Permissions Configuration",
        "  version: 1.0.0",
        "  domain: security|permissions|device|filesystem|terminal",
        "  scope: core",
        "",
        "::index",
        "  # node-id          | type     | scope  | conf | keywords",
        "  device_access       | concept  | all    | 1.0  | tier, level, mode",
        "  filesystem          | concept  | all    | 1.0  | folders, paths, read, write",
        "  terminal            | concept  | all    | 1.0  | shell, cmd, bash, execute",
        "  mcp_filesystem      | concept  | all    | 1.0  | mcp, server, context",
        "",
        "# ────────────────────────────────────────────────────────────",
        "::node[device_access]",
        "->[:role=permission]",
        "::dense",
        f"Master device access tier configuration. Currently set to: {tier}",
        "::config",
        f"tier={tier}",
        "",
        "# ────────────────────────────────────────────────────────────",
        "::node[filesystem]",
        "->[:role=permission]",
        "::dense",
        "Controls which local directories the agent is permitted to read, write, and delete.",
        "::config",
        f"allowed_paths={fs['allowed_paths']}",
        f"blocked_paths={fs['blocked_paths']}",
        f"allow_write={fs['allow_write']}",
        f"allow_delete={fs['allow_delete']}",
        f"max_file_size_mb={fs['max_file_size_mb']}",
        "",
        "# ────────────────────────────────────────────────────────────",
        "::node[terminal]",
        "->[:role=permission]",
        "::dense",
        "Controls whether the agent can execute shell commands, and which commands are "
        "allowed or blocked.",
        "::config",
        f"enabled={term['enabled']}",
        f"allowed_commands={term['allowed_commands']}",
        f"blocked_commands={term['blocked_commands']}",
        f"timeout={term['timeout']}",
        "",
        "# ────────────────────────────────────────────────────────────",
        "::node[mcp_filesystem]",
        "->[:role=permission]",
        "::dense",
        "Controls whether the native MCP filesystem server is started for IDE-like context "
        "integration.",
        "::config",
        f"enabled={mcp['enabled']}",
        "",
    ]
    return "\n".join(lines)
