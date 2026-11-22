"""
Operating System Tools

This module provides Hachi with its physical hands—allowing it to read files, write files,
and execute raw terminal commands. These functions are bound to Anthropic-compatible JSON schemas
for seamless ingestion by the ToolRegistry.

All tool functions are gated by the PermissionGate. If a gate is provided during registration,
every call is checked against the user's device-permissions.og before execution.
If no gate is provided, tools run unrestricted (used only during internal boot operations).
"""

import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from hachi.core.loop import ToolRegistry

_HOME_ALIAS_NAMES = {"desktop", "downloads", "documents"}


def _normalize_user_path(raw_path: str) -> Path:
    """Resolve paths with friendly aliases like 'Desktop' to user home folders."""
    raw = raw_path.strip()
    if not raw:
        return Path(raw_path).resolve()

    if raw.startswith("~"):
        return Path(raw).expanduser().resolve()

    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()

    parts = [part for part in candidate.parts if part and part != "."]
    if parts and parts[0].lower() in _HOME_ALIAS_NAMES:
        home_candidate = Path.home().joinpath(*parts)
        cwd_candidate = Path.cwd().joinpath(*parts)
        if home_candidate.exists() or not cwd_candidate.exists():
            return home_candidate.resolve()

    return candidate.resolve()


def _format_directory_listing(target: Path, max_entries: int = 200) -> str:
    """Render a small, deterministic directory listing for plain-text tool results."""
    try:
        entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    except Exception as e:
        return f"Error listing directory '{target}': {str(e)}"

    lines = [f"Directory listing for '{target}':"]
    if not entries:
        lines.append("(empty)")
        return "\n".join(lines)

    for item in entries[:max_entries]:
        suffix = "/" if item.is_dir() else ""
        lines.append(f"- {item.name}{suffix}")

    remaining = len(entries) - max_entries
    if remaining > 0:
        lines.append(f"... and {remaining} more entries")

    return "\n".join(lines)


# ==========================================
# Raw Tool Implementations (Ungated)
# ==========================================
# These are the actual executors. They contain no permission logic.
# They can be called directly by internal boot code that needs
# unrestricted access (e.g., reading config files during startup).


def _raw_read_file(path: str) -> str:
    """Read the contents of a local file."""
    try:
        target = _normalize_user_path(path)
        if not target.exists():
            return f"Error: File '{target}' does not exist."
        if target.is_dir():
            return _format_directory_listing(target)
        if not target.is_file():
            return f"Error: '{target}' is not a regular file."

        with open(target, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def _raw_write_file(path: str, content: str) -> str:
    """Write string content to a local file, creating parent directories if necessary."""
    try:
        target = _normalize_user_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to '{target}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


def _raw_run_terminal_command(command: str, cwd: str = ".", timeout: int = 120) -> str:
    """Execute a single command (argv-style) and return its stdout and stderr."""
    try:
        target_cwd = Path(cwd).resolve()
        if not target_cwd.exists() or not target_cwd.is_dir():
            return f"Error: Working directory '{target_cwd}' is invalid."

        raw = command.strip()
        if not raw:
            return "Error: Empty command is not allowed."

        # Hard-block shell chaining/redirection operators since commands run without a shell.
        # MED-008: also block ^ (cmd.exe escape/continuation) and % (variable expansion
        # in cmd.exe / PowerShell environment-variable injection e.g. %COMSPEC%).
        blocked_fragments = ("&&", "||", "|", ";", "`", "$(", ">", "<", "^", "%")
        for fragment in blocked_fragments:
            if fragment in raw:
                return (
                    "Error: Shell operators are not allowed in run_terminal_command. "
                    "Provide a single executable with arguments only."
                )

        argv = shlex.split(raw, posix=(os.name != "nt"))
        if not argv:
            return "Error: Command parsing produced no executable."
        if os.name == "nt":
            argv = [
                (
                    token[1:-1]
                    if len(token) >= 2 and token.startswith('"') and token.endswith('"')
                    else token
                )
                for token in argv
            ]

        executable = Path(argv[0]).name.lower()
        # Strip .exe suffix so "mkdir.exe" and "mkdir" both match.
        executable = executable.removesuffix(".exe")

        if executable in {"pwd", "cd"}:
            return f"--- STDOUT ---\n{target_cwd}\n\nExit Code: 0"

        if executable in {"ls", "dir"}:
            list_target = target_cwd
            if len(argv) > 1 and argv[1] not in {".", "./"}:
                list_target = _normalize_user_path(argv[1])
            if not list_target.exists():
                return f"Error: Path '{list_target}' does not exist."
            if list_target.is_file():
                return f"--- STDOUT ---\n{list_target.name}\n\nExit Code: 0"
            return f"--- STDOUT ---\n{_format_directory_listing(list_target)}\n\nExit Code: 0"

        # --- Shell built-ins that have no standalone executable on Windows ---
        # Implement them natively so the agent doesn't need run_shell_script for basics.

        if executable in {"mkdir", "md"}:
            # mkdir [-p] <dir> [<dir> ...]
            dirs = [a for a in argv[1:] if not a.startswith("-")]
            if not dirs:
                return "Error: mkdir requires at least one directory argument."
            created = []
            for d in dirs:
                target = _normalize_user_path(d) if not Path(d).is_absolute() else Path(d)
                if not target.is_absolute():
                    target = target_cwd / target
                target.mkdir(parents=True, exist_ok=True)
                created.append(str(target))
            return f"--- STDOUT ---\nCreated: {', '.join(created)}\n\nExit Code: 0"

        if executable in {"rmdir", "rd"}:
            if len(argv) < 2:
                return "Error: rmdir requires a directory argument."
            target = Path(argv[-1])
            if not target.is_absolute():
                target = target_cwd / target
            target = target.resolve()
            if not target.exists():
                return f"Error: '{target}' does not exist."
            if not target.is_dir():
                return f"Error: '{target}' is not a directory."
            recursive = any(a in {"-r", "-rf", "/s", "/q"} for a in argv[1:])
            if recursive:
                shutil.rmtree(target)
            else:
                target.rmdir()
            return f"--- STDOUT ---\nRemoved: {target}\n\nExit Code: 0"

        if executable in {"rm", "del", "erase"}:
            if len(argv) < 2:
                return "Error: rm requires at least one argument."
            recursive = any(a in {"-r", "-rf", "-f"} for a in argv[1:])
            targets = [a for a in argv[1:] if not a.startswith("-")]
            removed = []
            for t in targets:
                p = Path(t) if Path(t).is_absolute() else target_cwd / t
                p = p.resolve()
                if p.is_dir() and recursive:
                    shutil.rmtree(p)
                    removed.append(str(p))
                elif p.is_file():
                    p.unlink()
                    removed.append(str(p))
                else:
                    return f"Error: '{p}' does not exist or is a directory (use -r to remove dirs)."
            return f"--- STDOUT ---\nRemoved: {', '.join(removed)}\n\nExit Code: 0"

        if executable in {"cp", "copy"}:
            if len(argv) < 3:
                return "Error: cp requires source and destination arguments."
            src = Path(argv[-2])
            dst = Path(argv[-1])
            if not src.is_absolute():
                src = (target_cwd / src).resolve()
            if not dst.is_absolute():
                dst = (target_cwd / dst).resolve()
            if not src.exists():
                return f"Error: Source '{src}' does not exist."
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return f"--- STDOUT ---\nCopied '{src}' → '{dst}'\n\nExit Code: 0"

        if executable in {"mv", "move"}:
            if len(argv) < 3:
                return "Error: mv requires source and destination arguments."
            src = Path(argv[-2])
            dst = Path(argv[-1])
            if not src.is_absolute():
                src = (target_cwd / src).resolve()
            if not dst.is_absolute():
                dst = (target_cwd / dst).resolve()
            if not src.exists():
                return f"Error: Source '{src}' does not exist."
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"--- STDOUT ---\nMoved '{src}' → '{dst}'\n\nExit Code: 0"

        if executable == "echo":
            text = " ".join(argv[1:])
            return f"--- STDOUT ---\n{text}\n\nExit Code: 0"

        if executable in {"touch"}:
            if len(argv) < 2:
                return "Error: touch requires a filename."
            for name in argv[1:]:
                p = Path(name) if Path(name).is_absolute() else target_cwd / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            return f"--- STDOUT ---\nTouched: {', '.join(argv[1:])}\n\nExit Code: 0"

        if executable in {"cat", "type"}:
            if len(argv) < 2:
                return "Error: cat/type requires a filename."
            parts = []
            for name in argv[1:]:
                p = Path(name) if Path(name).is_absolute() else target_cwd / name
                if not p.exists():
                    return f"Error: '{p}' does not exist."
                parts.append(p.read_text(encoding="utf-8", errors="replace"))
            return f"--- STDOUT ---\n{''.join(parts)}\n\nExit Code: 0"

        if executable in {"which", "where"}:
            if len(argv) < 2:
                return "Error: which/where requires a command name."
            found = shutil.which(argv[1])
            if found:
                return f"--- STDOUT ---\n{found}\n\nExit Code: 0"
            return f"--- STDERR ---\n{argv[1]}: not found\n\nExit Code: 1"

        result = subprocess.run(
            argv,
            shell=False,
            cwd=target_cwd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )

        output = []
        if result.stdout:
            output.append(f"--- STDOUT ---\n{result.stdout.strip()}")
        if result.stderr:
            output.append(f"--- STDERR ---\n{result.stderr.strip()}")

        if not output:
            output.append("Command executed successfully with no output.")

        output.append(f"\nExit Code: {result.returncode}")
        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"


def _raw_run_shell_script(script: str, cwd: str = ".", timeout: int = 120) -> str:
    """Execute a multi-line shell script via PowerShell (Windows) or bash (Linux/Mac)."""
    try:
        target_cwd = Path(cwd).resolve()
        if not target_cwd.exists() or not target_cwd.is_dir():
            return f"Error: Working directory '{target_cwd}' is invalid."

        if not script.strip():
            return "Error: Empty script is not allowed."

        suffix = ".ps1" if os.name == "nt" else ".sh"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            script_path = Path(f.name)

        try:
            if os.name == "nt":
                argv = [
                    "powershell.exe",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ]
            else:
                argv = ["bash", str(script_path)]

            result = subprocess.run(
                argv,
                shell=False,
                cwd=target_cwd,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
            )

            output = []
            if result.stdout:
                output.append(f"--- STDOUT ---\n{result.stdout.strip()}")
            if result.stderr:
                output.append(f"--- STDERR ---\n{result.stderr.strip()}")
            if not output:
                output.append("Script executed successfully with no output.")
            output.append(f"\nExit Code: {result.returncode}")
            return "\n".join(output)
        finally:
            script_path.unlink(missing_ok=True)

    except subprocess.TimeoutExpired:
        return f"Error: Script timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing script: {str(e)}"


# ==========================================
# Gated Tool Factories
# ==========================================
# Each factory takes the PermissionGate and returns a guarded version
# of the raw tool. The gate checks happen BEFORE execution — if denied,
# the raw function is never called.


def _make_guarded_read_file(gate: Any):
    """Create a permission-gated read_file tool."""

    def guarded_read_file(path: str) -> str:
        normalized = _normalize_user_path(path)
        result = gate.check_path(str(normalized), "read")
        if not result.allowed:
            return f"Permission Denied: {result.reason}"

        # UC-PERF-005: Fail CLOSED on the size check — if we cannot determine the
        # file size (e.g. a broken stat), refuse the read rather than swallowing the
        # error and proceeding with an unbounded read.
        target = normalized
        if target.exists() and target.is_file():
            try:
                file_size = target.stat().st_size
            except Exception as exc:
                return (
                    f"Permission Denied: Cannot determine file size for '{target}': {exc}. "
                    "Read refused to avoid loading an unverified file."
                )
            if file_size > gate.max_file_size_bytes:
                return (
                    "Permission Denied: File exceeds configured max_file_size_mb. "
                    "Update device-permissions.og to raise the limit."
                )

        return _raw_read_file(str(normalized))

    return guarded_read_file


def _make_guarded_write_file(gate: Any, checkpoints: Any = None):
    """Create a permission-gated write_file tool (snapshots before overwriting)."""

    def guarded_write_file(path: str, content: str) -> str:
        normalized = _normalize_user_path(path)
        result = gate.check_path(str(normalized), "write")
        if not result.allowed:
            return f"Permission Denied: {result.reason}"
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > gate.max_file_size_bytes:
            return (
                "Permission Denied: Content exceeds configured max_file_size_mb. "
                "Split the file or increase the limit in device-permissions.og."
            )
        # Snapshot the pre-write state so the user can rollback this change.
        # ADV-026: A failed checkpoint must NOT be silently ignored — if we cannot
        # take a snapshot, we refuse the destructive write so that rollback remains
        # possible.  Only skip the snapshot when checkpoints is None (not registered).
        if checkpoints is not None:
            try:
                checkpoints.snapshot(normalized, label="write_file")
            except Exception as exc:
                return (
                    f"Write aborted: Could not create a rollback checkpoint for '{normalized}': "
                    f"{exc}. The file has NOT been modified. "
                    "Resolve the checkpoint storage issue and retry."
                )
        return _raw_write_file(str(normalized), content)

    return guarded_write_file


def _make_rollback_changes(checkpoints: Any):
    """Create the rollback tool that undoes the most recent file change."""

    def rollback_changes(path: str = "") -> str:
        target = _normalize_user_path(path) if path.strip() else None
        result = checkpoints.rollback(target)
        status = result.get("status")
        if status == "restored":
            return f"Restored previous version of {result['path']}."
        if status == "removed":
            return f"Removed {result['path']} (it did not exist before the change)."
        return "Nothing to roll back."

    return rollback_changes


ROLLBACK_CHANGES_SCHEMA = {
    "name": "rollback_changes",
    "description": (
        "Undo the most recent file change you made (restores the previous version, or removes "
        "a file you just created). Optionally pass a specific file path to undo its last change."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional file path to roll back. Omit to undo the last change.",
            }
        },
        "required": [],
    },
}


_CAT_STEMS: frozenset[str] = frozenset({"cat", "type"})
_COPY_STEMS: frozenset[str] = frozenset({"cp", "copy"})
_MOVE_STEMS: frozenset[str] = frozenset({"mv", "move"})


def _make_guarded_run_terminal(gate: Any):
    """Create a permission-gated run_terminal_command tool."""

    def guarded_run_terminal(command: str, cwd: str = ".") -> str:
        # Check command against terminal rules (allowlist/blocklist)
        # Note: We intentionally do NOT gate the cwd here. The command allowlist
        # already controls what the agent can execute. Gating cwd creates false
        # positives (e.g., blocking "start kiro" because hachi runs from
        # D:\OG\object-graph which isn't in allowed_paths). File-level access
        # is already gated by read_file and write_file independently.
        cmd_result = gate.check_command(command)
        if not cmd_result.allowed:
            return f"Permission Denied: {cmd_result.reason}"

        # UC-PERM-003: check_command's _check_path_args skips bare filename tokens
        # (those without any path separator, ~, or .) so "cat id_rsa" from a blocked
        # cwd passes the gate unchecked.  After the command-level check passes, we
        # resolve every non-flag argument for cat/type builtins against the actual cwd
        # and explicitly re-check each resolved path via check_path.
        import shlex as _shlex

        try:
            argv = _shlex.split(command.strip(), posix=(os.name != "nt"))
        except ValueError:
            argv = command.strip().split()

        if argv:
            executable_stem = Path(argv[0].strip("\"'")).stem.lower().removesuffix(".exe")
            if executable_stem in _CAT_STEMS:
                effective_cwd = Path(cwd).resolve()
                for token in argv[1:]:
                    tok = token.strip("\"'")
                    if not tok or tok.startswith("-"):
                        continue
                    # Resolve relative (including bare) filenames against the actual cwd.
                    p = Path(tok)
                    if not p.is_absolute():
                        p = (effective_cwd / p).resolve()
                    else:
                        p = p.resolve()
                    path_result = gate.check_path(str(p), "read")
                    if not path_result.allowed:
                        return f"Permission Denied: {path_result.reason}"

            # M3: check_command's blocked_paths scan now covers the arguments of
            # every allowlisted command (P-01), but it still only tests them against
            # blocked_paths — it never consults the full read/write/delete tier for
            # paths outside that list. Mirror the _CAT_STEMS re-check above: resolve
            # src/dst the same way _raw_run_terminal_command does and gate them
            # explicitly.
            if executable_stem in _COPY_STEMS or executable_stem in _MOVE_STEMS:
                non_flag = [t.strip("\"'") for t in argv[1:] if not t.startswith("-")]
                if len(non_flag) >= 2:
                    effective_cwd = Path(cwd).resolve()

                    def _resolve(tok: str) -> Path:
                        p = Path(tok)
                        return p.resolve() if p.is_absolute() else (effective_cwd / p).resolve()

                    src = _resolve(non_flag[-2])
                    dst = _resolve(non_flag[-1])

                    write_result = gate.check_path(str(dst), "write")
                    if not write_result.allowed:
                        return f"Permission Denied: {write_result.reason}"

                    if executable_stem in _MOVE_STEMS:
                        delete_result = gate.check_path(str(src), "delete")
                        if not delete_result.allowed:
                            return f"Permission Denied: {delete_result.reason}"
                    else:
                        read_result = gate.check_path(str(src), "read")
                        if not read_result.allowed:
                            return f"Permission Denied: {read_result.reason}"

        return _raw_run_terminal_command(command, cwd, timeout=gate.terminal_timeout)

    return guarded_run_terminal


def _make_guarded_run_shell_script(gate: Any):
    """Create a permission-gated run_shell_script tool."""

    def guarded_run_shell_script(script: str, cwd: str = ".") -> str:
        # Gate on the shell interpreter name — if the user can run powershell/bash,
        # they can run a script through it.
        shell = "powershell" if os.name == "nt" else "bash"
        cmd_result = gate.check_command(shell)
        if not cmd_result.allowed:
            return f"Permission Denied: {cmd_result.reason}"
        return _raw_run_shell_script(script, cwd, timeout=gate.terminal_timeout)

    return guarded_run_shell_script


# ==========================================
# JSON Schemas
# ==========================================

READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "Read the contents of a local file from the system.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path to the file to read.",
            }
        },
        "required": ["path"],
    },
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": "Write string content to a local file. Will overwrite the file if it already "
    "exists, and will create parent directories if needed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path where the file should be written.",
            },
            "content": {
                "type": "string",
                "description": "The string content to write into the file.",
            },
        },
        "required": ["path", "content"],
    },
}

RUN_TERMINAL_COMMAND_SCHEMA = {
    "name": "run_terminal_command",
    "description": (
        "Execute a single command with arguments (no shell operators). Use this to run "
        "a specific executable with known args (e.g. `git status`, `python script.py`). "
        "For multi-step scripts, piping, redirection, or `&&` chaining, use run_shell_script."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to execute."},
            "cwd": {
                "type": "string",
                "description": "The working directory where the command should be run. "
                "Defaults to the current directory ('.').",
            },
        },
        "required": ["command"],
    },
}

RUN_SHELL_SCRIPT_SCHEMA = {
    "name": "run_shell_script",
    "description": (
        "Execute a shell script with full shell capabilities: piping (`|`), redirection (`>`), "
        "conditionals (`if`/`&&`/`||`), loops, and multi-line logic. "
        "On Windows runs via PowerShell; on Linux/Mac via bash. "
        "IMPORTANT: This tool is only available when the shell interpreter "
        "('powershell' on Windows, 'bash' on Linux/Mac) is explicitly listed in the "
        "terminal allowed_commands in device-permissions.og. At the 'sandbox' and 'guided' "
        "permission tiers the shell interpreter is blocked, so this tool will be denied. "
        "It is available at the 'unrestricted' tier or when the user has explicitly "
        "allowlisted the shell in their configuration. "
        "For pure Python computation use python_sandbox instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "script": {
                "type": "string",
                "description": "The shell script to execute (multi-line supported).",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the script. Defaults to '.'.",
            },
        },
        "required": ["script"],
    },
}

# ==========================================
# Registration Helper
# ==========================================


def register_os_tools(registry: ToolRegistry, gate: Any | None = None, checkpoints: Any = None):
    """
    Mount all OS tools onto the provided ToolRegistry.

    If a PermissionGate is provided, all tools are wrapped with permission checks.
    If not, raw (unrestricted) tools are registered — used only for internal testing.

    Args:
        registry: The tool registry to register into.
        gate: Optional PermissionGate loaded from device-permissions.og.
    """
    if gate:
        registry.register(READ_FILE_SCHEMA, _make_guarded_read_file(gate))
        registry.register(WRITE_FILE_SCHEMA, _make_guarded_write_file(gate, checkpoints))
        registry.register(RUN_TERMINAL_COMMAND_SCHEMA, _make_guarded_run_terminal(gate))
        registry.register(RUN_SHELL_SCRIPT_SCHEMA, _make_guarded_run_shell_script(gate))
    else:
        registry.register(READ_FILE_SCHEMA, _raw_read_file)
        registry.register(WRITE_FILE_SCHEMA, _raw_write_file)
        registry.register(RUN_TERMINAL_COMMAND_SCHEMA, _raw_run_terminal_command)
        registry.register(RUN_SHELL_SCRIPT_SCHEMA, _raw_run_shell_script)

    if checkpoints is not None:
        registry.register(ROLLBACK_CHANGES_SCHEMA, _make_rollback_changes(checkpoints))
