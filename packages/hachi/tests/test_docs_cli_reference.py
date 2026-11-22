"""Guard: every CLI command referenced in the user-facing docs must exist.

This locks the doc-vs-CLI drift class that this audit uncovered — the cookbook
and security guide referenced commands/subcommands that were never registered
(`hachi secret set`, `hachi schedule delete`, …), so copy-pasting from the docs
errored with ``No such command``. The test introspects the live Typer app for
the real command/group/subcommand names and asserts that each ``hachi <cmd>``
(and ``hachi <group> <sub>``) invocation in the reference docs resolves.

Scope: the user-facing reference docs only. Historical audit/strategy/plan docs
intentionally describe aspirational commands and are excluded.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer

from hachi.cli.main import app

_REPO_ROOT = Path(__file__).resolve().parents[1]

# User-facing command references (NOT the historical audit/strategy corpora).
_REFERENCE_DOCS = [
    "README.md",
    "docs/guides/cookbook.md",
    "docs/guides/configuration.md",
    "docs/reference/benchmark.md",
    "docs/reference/og-security.md",
]

# `hachi foo` or `hachi foo bar`, optionally behind `uv run `. Tokens must look
# like command names (lowercase, may contain hyphens); flags/placeholders such
# as `--json`, `<id>`, `$(...)` naturally fail the token pattern and are skipped.
_INVOCATION = re.compile(r"\bhachi\s+([a-z][a-z0-9-]*)(?:\s+([a-z][a-z0-9-]*))?")


def _command_tree() -> tuple[set[str], dict[str, set[str]]]:
    """Return (top-level names, {group_name: {subcommand names}}) from the app."""
    click_cmd = typer.main.get_command(app)
    top_names: set[str] = set(click_cmd.commands)
    groups: dict[str, set[str]] = {
        name: set(cmd.commands)
        for name, cmd in click_cmd.commands.items()
        if getattr(cmd, "commands", None)
    }
    return top_names, groups


def _invocations() -> list[tuple[str, str, str | None]]:
    """Extract (source 'file:line', token1, token2|None) for each doc invocation."""
    found: list[tuple[str, str, str | None]] = []
    for rel in _REFERENCE_DOCS:
        path = _REPO_ROOT / rel
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in _INVOCATION.finditer(line):
                found.append((f"{rel}:{lineno}", m.group(1), m.group(2)))
    return found


def test_documented_cli_commands_exist() -> None:
    top_names, groups = _command_tree()
    problems: list[str] = []

    for source, t1, t2 in _invocations():
        if t1 not in top_names:
            problems.append(f"{source}: `hachi {t1}` is not a registered command")
            continue
        # Only validate the second token when the first is a command *group*
        # (for leaf commands the second token is a positional argument).
        if t1 in groups and t2 is not None and t2 not in groups[t1]:
            problems.append(f"{source}: `hachi {t1} {t2}` — no such subcommand of `{t1}`")

    assert not problems, "Docs reference non-existent CLI commands:\n" + "\n".join(problems)


def test_command_tree_sanity() -> None:
    # Guards the introspection itself: if this breaks, the drift test above is
    # silently vacuous.
    top_names, groups = _command_tree()
    assert {"run", "doctor", "schedule", "skill", "session"} <= top_names
    assert "schedule" in groups and "remove" in groups["schedule"]
    assert "delete" not in groups["schedule"]  # the exact drift we fixed
