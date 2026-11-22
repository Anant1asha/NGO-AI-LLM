#!/usr/bin/env python
"""PreToolUse(Bash/PowerShell) guard — the mechanical wall around dangerous git moves.

Three jobs (exit 2 blocks the Bash call; exit 0 lets it through):
  1. Push-lock: block `git push` to main/master unless a one-shot approval sentinel
     (.claude/.push-approved) exists; the sentinel is consumed on use.
  2. Secret-scan: block `git commit` that stages a .env or a high-confidence secret.
  3. Anti-forge: block any Bash command that tries to create the sentinel itself —
     approval must come from the human, not the agent.

This converts "ask before pushing" and "don't commit secrets" from advice the model
can rationalise away into a gate it cannot. The git pre-commit hook is intentionally
NOT used (core.hooksPath points into a junction here); this covers the agent, which is
the committer in this workflow.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import _common

SENTINEL = ".claude/.push-approved"

_PUSH = re.compile(r"\bgit\b[^\n]*\bpush\b", re.IGNORECASE)
_MAIN = re.compile(r"\b(?:origin/)?(?:main|master)\b|HEAD:(?:main|master)\b", re.IGNORECASE)
_FORGE = re.compile(r"\.push-approved", re.IGNORECASE)
_FORGE_VERB = re.compile(
    r"(?:touch|echo|printf|new-item|set-content|add-content|tee|>>?)", re.IGNORECASE
)
_COMMIT = re.compile(r"\bgit\b[^\n]*\bcommit\b", re.IGNORECASE)

# High-confidence secret patterns only — kept deliberately narrow so the gate doesn't
# false-positive on test fixtures and train the user to disable it.
_SECRETS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
        "private key block",
    ),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub token"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API key"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}"), "OpenAI-style API key"),
]
# .env.* suffixes that are safe to commit (templates, not real secrets).
_ENV_OK = {"example", "sample", "template", "dist", "defaults"}


def _block(msg: str) -> int:
    sys.stderr.write(msg + "\n")
    return 2


def _scan_staged(root: Path) -> str | None:
    git = shutil.which("git")
    if not git:
        return None
    try:
        names = subprocess.run(
            [git, "diff", "--cached", "--name-only"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        for name in (n.strip() for n in names.stdout.splitlines() if n.strip()):
            base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if base == ".env":
                return f"a .env file is staged ({name})"
            if base.startswith(".env.") and base.split(".env.", 1)[1] not in _ENV_OK:
                return f"a secret env file is staged ({name})"
        diff = subprocess.run(
            [git, "diff", "--cached", "--unified=0"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=20,
        )
        added = "\n".join(
            ln for ln in diff.stdout.splitlines() if ln.startswith("+") and not ln.startswith("+++")
        )
        for pattern, label in _SECRETS:
            if pattern.search(added):
                return f"a possible {label} in the staged diff"
    except Exception:
        return None
    return None


def main() -> int:
    event = _common.read_event()
    cmd = (event.get("tool_input") or {}).get("command") or ""
    if not cmd:
        return 0
    root = _common.project_dir()

    # (3) The sentinel must be created by the human, never forged via Bash.
    if _FORGE.search(cmd) and _FORGE_VERB.search(cmd):
        return _block(
            "[bash_guard] The push-approval sentinel may only be created by the human, not via Bash.\n"
            "Ask the user to approve the push explicitly."
        )

    # (1) Push-lock on main/master.
    if _PUSH.search(cmd) and _MAIN.search(cmd):
        sentinel = root / SENTINEL
        if sentinel.exists():
            try:
                sentinel.unlink()  # one-shot: consume the approval
            except Exception:
                pass
            return 0
        return _block(
            "[bash_guard] Push to main/master is LOCKED.\n"
            "1) Run `uv run python scripts/preflight.py` and show it green.\n"
            "2) Get the user's explicit OK in this conversation.\n"
            f"3) The user (not you) creates the sentinel file: {SENTINEL}\n"
            "Then the push is allowed exactly once."
        )

    # (2) Secret-scan on commits.
    if _COMMIT.search(cmd):
        hit = _scan_staged(root)
        if hit:
            return _block(
                f"[bash_guard] Refusing to commit: {hit}.\n"
                "Unstage it and move the secret to the keyring vault or an ignored .env."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
