#!/usr/bin/env python3
"""Lint all shipped .og skill files in default_skills/.

Exits 0 when every file is error-free; exits 1 and prints a report on any error.
Warnings are printed but do not affect the exit code — only errors do.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hachi.og_engine.engine import lint_og_file  # noqa: E402

_SKILLS_ROOT = Path(__file__).parent.parent / "src" / "hachi" / "default_skills"


def main() -> int:
    og_files = sorted(_SKILLS_ROOT.rglob("*.og"))
    if not og_files:
        print(f"ERROR: no .og files found under {_SKILLS_ROOT}", file=sys.stderr)
        return 1

    total_errors = 0
    total_warnings = 0
    files_with_errors = 0

    for og_file in og_files:
        result = lint_og_file(og_file)
        rel = og_file.relative_to(_SKILLS_ROOT)
        errors = result["summary"]["errors"]
        warnings = result["summary"]["warnings"]
        total_errors += errors
        total_warnings += warnings

        if errors:
            files_with_errors += 1
            print(f"\n[FAIL] {rel}  ({errors} error(s), {warnings} warning(s))")
            for issue in result["issues"]:
                prefix = "  ERROR" if issue["level"] == "error" else "  warn "
                print(f"{prefix}  [{issue['node']}]  {issue['code']}: {issue['message']}")
        elif warnings:
            print(f"[warn] {rel}  ({warnings} warning(s))")
        else:
            print(f"[ ok ] {rel}")

    print(
        f"\n{'='*60}\n"
        f"Scanned {len(og_files)} file(s): "
        f"{files_with_errors} with errors, "
        f"{total_warnings} total warning(s)\n"
        f"{'='*60}"
    )

    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
