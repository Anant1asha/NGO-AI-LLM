#!/usr/bin/env python
"""PostToolUse(Write|Edit|MultiEdit) — auto-format the touched file.

Keeps diffs clean and stops the agent burning turns on whitespace. Python only
(ruff format), because that is the formatter this repo uses and the frontend has no
formatter configured. Best-effort and silent: PostToolUse cannot block, and a
formatting hiccup must never derail the edit. Only the single touched file is
formatted — never a repo-wide reflow (forbidden by CLAUDE.md Rule 3).
"""

from __future__ import annotations

from pathlib import Path

import _common


def main() -> int:
    event = _common.read_event()
    file_path = (event.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return 0
    path = Path(file_path)
    if path.suffix.lower() != ".py" or not path.exists():
        return 0
    ruff = _common.venv_tool("ruff") or _common.uv_tool("ruff")
    if not ruff:
        return 0
    try:
        _common.run([*ruff, "format", str(path)], timeout=60)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
