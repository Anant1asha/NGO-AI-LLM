#!/usr/bin/env python
"""SessionStart hook — inject Hachi's regression memory + repo state into context.

So a fresh agent never starts cold: the gate command, the current branch, and the
top bug-bank "Avoid:" rules are loaded before planning begins. Never blocks — on any
error it emits nothing and exits 0.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import _common


def _git(root: Path, *args: str) -> str:
    git = shutil.which("git")
    if not git:
        return ""
    try:
        proc = subprocess.run(
            [git, *args], cwd=str(root), capture_output=True, text=True, timeout=10
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def _top_avoids(root: Path, limit: int = 8) -> list[str]:
    """Extract `BB-N — title — Avoid: …` one-liners from docs/bug-bank.md."""
    bb = root / "docs" / "bug-bank.md"
    if not bb.exists():
        return []
    lines = bb.read_text(encoding="utf-8", errors="replace").splitlines()
    title: str | None = None
    out: list[str] = []
    i = 0
    while i < len(lines) and len(out) < limit:
        line = lines[i]
        m = re.match(r"^###\s+(BB-\d+)\s+—\s+(.+?)\s*$", line)
        if m:
            title = f"{m.group(1)} {m.group(2)}"
            i += 1
            continue
        a = re.match(r"^-\s+\*\*Avoid:\*\*\s+(.+)$", line)
        if a and title:
            # Join wrapped continuation lines so the injected rule is complete, not a fragment.
            parts = [a.group(1).strip()]
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip() or nxt.lstrip().startswith(("- **", "###", "<!--")):
                    break
                parts.append(nxt.strip())
                j += 1
            avoid = " ".join(parts)
            if len(avoid) > 200:
                avoid = avoid[:197].rstrip() + "…"
            out.append(f"{title} → {avoid}")
            title = None
            i = j
            continue
        i += 1
    return out


def main() -> int:
    try:
        root = _common.project_dir()
        branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
        dirty = [ln for ln in _git(root, "status", "--porcelain").splitlines() if ln.strip()]
        avoids = _top_avoids(root)

        lines = [
            "Hachi guardrails — session warm-up:",
            "• Gate: run `uv run python scripts/preflight.py` and get it GREEN before proposing any push.",
            f"• Branch: {branch} · {len(dirty)} uncommitted file(s). Never push to main without the user's explicit OK.",
            "• Map: ARCHITECTURE.md · Decisions/ADRs: docs/DECISIONS.md · .og spec: docs/reference/objectgraph-spec.md",
            "• Regression law: for every bug, write a failing test FIRST, then fix, then lock it in docs/bug-bank.md.",
        ]
        if avoids:
            lines.append("• Bug bank (docs/bug-bank.md) — do NOT re-introduce:")
            lines.extend(f"    - {a}" for a in avoids)

        payload = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join(lines),
            }
        }
        sys.stdout.write(json.dumps(payload))
    except Exception:
        # Never let warm-up block a session.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
