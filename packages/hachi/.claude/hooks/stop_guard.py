#!/usr/bin/env python
"""Stop hook — refuse to finish while `ruff check` is red.

A fast, deterministic backstop so the agent can't declare "done" on top of an
obviously broken tree. It deliberately runs only `ruff check src tests` (seconds),
NOT the full suite: the authoritative gate is `scripts/preflight.py` (full pytest +
types + contract), which the agent must run green before proposing a push.

Guards against infinite loops via `stop_hook_active`, and fails OPEN on any
execution problem so a broken hook never traps the user.
"""

from __future__ import annotations

import sys

import _common


def main() -> int:
    event = _common.read_event()
    if event.get("stop_hook_active"):
        return 0  # already nudged once this stop-cycle — let Claude stop.

    ruff = _common.venv_tool("ruff") or _common.uv_tool("ruff")
    if not ruff:
        return 0  # can't check — fail open.
    try:
        proc = _common.run([*ruff, "check", "src", "tests"], timeout=120)
    except Exception:
        return 0  # fail open on execution error.

    if proc.returncode != 0:
        tail = "\n".join((proc.stdout or "").strip().splitlines()[-15:])
        sys.stderr.write(
            "[stop_guard] `ruff check src tests` is RED — fix it before finishing:\n" + tail + "\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
