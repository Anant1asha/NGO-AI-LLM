"""Shared helpers for Hachi's Claude Code hooks.

Stdlib only, cross-platform. Each hook is invoked as
`python ${CLAUDE_PROJECT_DIR}/.claude/hooks/<name>.py` with the event payload on
stdin (see https://code.claude.com/docs/en/hooks). These helpers parse that
payload, locate the project root + the project's venv tools, and run subprocesses
portably (Windows PowerShell / Git Bash / Linux / macOS).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def read_event() -> dict:
    """Parse the hook event JSON from stdin. Returns {} on any problem."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def project_dir() -> Path:
    """Absolute repo root. Prefers $CLAUDE_PROJECT_DIR; else walks up to pyproject.toml."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parents[2]  # .claude/hooks/_common.py -> repo root


def venv_tool(name: str) -> list[str] | None:
    """argv to run a tool from the project venv (fast, no uv overhead), or None.

    Falls back to PATH. Returns a list so callers can splat extra args onto it.
    """
    root = project_dir()
    for candidate in (
        root / ".venv" / "Scripts" / f"{name}.exe",  # Windows
        root / ".venv" / "bin" / name,  # POSIX
    ):
        if candidate.exists():
            return [str(candidate)]
    found = shutil.which(name)
    return [found] if found else None


def uv_tool(*args: str) -> list[str] | None:
    """argv to run `uv run <args...>`, or None if uv is not on PATH."""
    uv = shutil.which("uv")
    return [uv, "run", *args] if uv else None


def run(argv: list[str], cwd: str | Path | None = None, timeout: float | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing text output. Never raises on non-zero exit."""
    return subprocess.run(
        argv,
        cwd=str(cwd or project_dir()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
