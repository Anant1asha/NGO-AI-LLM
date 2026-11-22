#!/usr/bin/env python
"""ADR-lint -- keep the architecture decision records honest (Guardrails Phase 3).

A documentation convention with no check rots; this is the check. It verifies the numbered
ADRs under ``docs/architecture/adr/`` stay well-formed and indexed:

  1. Every ``NNNN-*.md`` ADR is linked from ``adr/README.md`` (no orphan ADRs).
  2. ADR filenames match ``NNNN-kebab-case.md`` with a unique, zero-padded number.
  3. Each ADR carries a ``Status:`` line and the required sections.

Advisory in the gate today (like the other Phase-2 rails); ratchet to blocking once the
baseline is clean. Exits non-zero on any violation. Stdlib only -- never imports the product.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = ROOT / "docs" / "architecture" / "adr"
INDEX = ADR_DIR / "README.md"
TEMPLATE_STEM = "0000-template"

FILENAME_RE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
STATUS_RE = re.compile(r"^\s*[-*]?\s*\**\s*Status\b", re.IGNORECASE | re.MULTILINE)
REQUIRED_SECTIONS = ("## Context", "## Decision", "## Consequences")


def _adr_files() -> list[Path]:
    """Numbered ADRs only -- excludes the index and the copy-me template."""
    return sorted(
        p for p in ADR_DIR.glob("*.md") if p.name.lower() != "readme.md" and p.stem != TEMPLATE_STEM
    )


def main() -> int:
    if not ADR_DIR.is_dir():
        print(f"adr-lint: no ADR directory at {ADR_DIR.relative_to(ROOT).as_posix()} -- skipping.")
        return 0

    problems: list[str] = []
    index_text = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else ""
    if not index_text:
        problems.append(f"missing ADR index: {INDEX.relative_to(ROOT).as_posix()}")

    seen: dict[str, str] = {}
    adrs = _adr_files()
    for adr in adrs:
        rel = adr.relative_to(ROOT).as_posix()
        match = FILENAME_RE.match(adr.name)
        if match is None:
            problems.append(f"{rel}: filename is not NNNN-kebab-case.md")
            continue
        number = match.group(1)
        if number in seen:
            problems.append(f"{rel}: duplicate ADR number {number} (also {seen[number]})")
        seen[number] = adr.name

        if index_text and adr.name not in index_text:
            problems.append(f"{rel}: not linked from adr/README.md (orphan ADR)")

        body = adr.read_text(encoding="utf-8")
        if STATUS_RE.search(body) is None:
            problems.append(f"{rel}: missing a 'Status:' line")
        for section in REQUIRED_SECTIONS:
            if section not in body:
                problems.append(f"{rel}: missing required section '{section}'")

    if problems:
        print("adr-lint: FAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"adr-lint: OK -- {len(adrs)} ADR(s) well-formed and indexed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
