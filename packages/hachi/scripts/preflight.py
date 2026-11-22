#!/usr/bin/env python
"""Hachi preflight — the single local gate that everything ships through.

Run it before proposing a push:

    uv run python scripts/preflight.py            # full gate (mirrors CI)
    uv run python scripts/preflight.py --quick    # fast inner-loop (skips full pytest + FE build)
    uv run python scripts/preflight.py --no-frontend

Exit code is 0 **only** if every blocking check passes. "Looks done" is not done —
a change the gate can't verify is a change that doesn't land (see CLAUDE.md).

Design notes for this repo specifically:
- There is deliberately **no global `ruff format --check`** step: Hachi is not
  fully ruff-formatted (a repo-wide reformat reflows ~100 files and is forbidden by
  CLAUDE.md Rule 3). Formatting is kept clean *per touched file* by the
  PostToolUse auto-format hook instead — see .claude/hooks/auto_format.py.
- `mypy` runs the **scoped strict gate** (mypy-strict-gate.ini), not the full tree:
  the full tree has known pre-existing debt and is advisory-only in CI.
- pytest runs the **full** suite (the contract, CLAUDE.md Rule 2) **sequentially**, exactly
  like CI — deliberately NOT `-n auto`. Parallel workers starve the wall-clock timing tests
  (e.g. `test_two_sessions_run_concurrently`, the notifier non-blocking test) and make the gate
  flaky; the plan's rule is "run tests sequentially to kill time-based flakiness."
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

# Windows consoles default to cp1252 and choke on non-ASCII output; force UTF-8 so the
# gate never crashes on a glyph. Best-effort.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

# ANSI colours, disabled when output is not a TTY (CI logs, redirects).
_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


GREEN = lambda s: _c("32", s)  # noqa: E731
RED = lambda s: _c("31", s)  # noqa: E731
YELLOW = lambda s: _c("33", s)  # noqa: E731
DIM = lambda s: _c("2", s)  # noqa: E731
BOLD = lambda s: _c("1", s)  # noqa: E731


@dataclass
class Step:
    """One gate check. `cmds` is a sequence of argv lists run in order; the step
    fails if any command exits non-zero (or its executable is missing)."""

    name: str
    cmds: list[list[str]]
    blocking: bool = True
    in_quick: bool = True
    needs_frontend: bool = False


# The gate. Ordered fast-to-slow so cheap failures surface first.
STEPS: list[Step] = [
    Step("ruff check", [["uv", "run", "ruff", "check", "src", "tests"]]),
    Step(
        "mypy strict-gate",
        [["uv", "run", "python", "-m", "mypy", "--config-file", "mypy-strict-gate.ini"]],
    ),
    Step("skill-lint (.og)", [["uv", "run", "python", "scripts/lint_skills.py"]]),
    # Architectural rail (Guardrails Phase 2) -- enforces the import layering so the domain
    # can't grow a new dependency on its delivery edges. Blocking & green; see
    # pyproject [tool.importlinter]. A new cross-layer import fails here.
    Step("import-linter (layers)", [["uv", "run", "lint-imports"]]),
    # Advisory -- mirrors CI (the security job is continue-on-error on main). Surfaced, never blocks.
    Step(
        "security audit (high)",
        [["uv", "run", "hachi", "security-audit", "--json", "--fail-on-high"]],
        blocking=False,
    ),
    # Advisory rails (Guardrails Phase 2): surfaced every run, never block. Ratchet each to
    # blocking once its baseline reaches zero. Config in pyproject [tool.deptry]/[tool.vulture]
    # and [tool.ruff.lint.pylint]. deptry currently flags 4 declared-but-unused SDK extras.
    Step("deptry (unused/missing deps)", [["uv", "run", "deptry", "src"]], blocking=False),
    Step("vulture (dead code)", [["uv", "run", "vulture"]], blocking=False),
    Step(
        "complexity (PLR outliers)",
        [
            [
                "uv",
                "run",
                "ruff",
                "check",
                "src",
                "--select",
                "PLR0911,PLR0912,PLR0913,PLR0915",
                "--statistics",
            ]
        ],
        blocking=False,
    ),
    # Docs rail (Guardrails Phase 3): the ADRs under docs/architecture/adr/ stay well-formed and
    # indexed (no orphans, NNNN-kebab names, required sections). Baseline is clean, so this can
    # ratchet to blocking; kept advisory for one cycle like the other rails. See scripts/check_adrs.py.
    Step("adr-lint (docs)", [["uv", "run", "python", "scripts/check_adrs.py"]], blocking=False),
    Step("eval regression", [["uv", "run", "hachi", "eval", "run"]]),
    Step(
        "frontend typecheck",
        [["npm", "run", "--prefix", "frontend", "typecheck"]],
        needs_frontend=True,
    ),
    Step("frontend vitest", [["npm", "run", "--prefix", "frontend", "test"]], needs_frontend=True),
    Step(
        "openapi <-> frontend contract",
        [
            ["uv", "run", "hachi", "gateway-openapi", "--output", "openapi/hachi-openapi.json"],
            ["npm", "run", "--prefix", "frontend", "check:api"],
        ],
        needs_frontend=True,
    ),
    # Slow steps — skipped by --quick.
    Step("pytest (full suite)", [["uv", "run", "pytest", "-q"]], in_quick=False),
    Step(
        "frontend build",
        [["npm", "run", "--prefix", "frontend", "build"]],
        in_quick=False,
        needs_frontend=True,
    ),
]


@dataclass
class Result:
    step: Step
    status: str  # "pass" | "fail" | "skip"
    seconds: float = 0.0
    detail: str = ""
    tail: str = ""


def _resolve(cmd: list[str]) -> list[str] | None:
    """Resolve the leading executable on PATH (handles npm.cmd / uv.exe on Windows)."""
    exe = shutil.which(cmd[0])
    return None if exe is None else [exe, *cmd[1:]]


def run_step(step: Step) -> Result:
    start = time.monotonic()
    for cmd in step.cmds:
        resolved = _resolve(cmd)
        if resolved is None:
            return Result(
                step, "fail", time.monotonic() - start, detail=f"`{cmd[0]}` not found on PATH"
            )
        proc = subprocess.run(
            resolved,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            combined = (proc.stdout or "") + (proc.stderr or "")
            tail = "\n".join(combined.strip().splitlines()[-40:])
            return Result(
                step,
                "fail",
                time.monotonic() - start,
                detail=f"exit {proc.returncode}: {' '.join(cmd)}",
                tail=tail,
            )
    return Result(step, "pass", time.monotonic() - start)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hachi preflight gate")
    parser.add_argument(
        "--quick", action="store_true", help="skip the slow steps (full pytest, FE build)"
    )
    parser.add_argument("--no-frontend", action="store_true", help="skip all frontend (npm) steps")
    args = parser.parse_args()

    frontend_ready = (FRONTEND / "node_modules").is_dir()
    print(BOLD("\nHachi preflight") + DIM(f"  ({'quick' if args.quick else 'full'} mode)\n"))

    results: list[Result] = []
    for step in STEPS:
        if args.quick and not step.in_quick:
            results.append(Result(step, "skip", detail="--quick"))
            print(f"  {YELLOW('skip')}  {step.name} {DIM('(--quick)')}")
            continue
        if step.needs_frontend and (args.no_frontend or not frontend_ready):
            why = (
                "--no-frontend"
                if args.no_frontend
                else "frontend/node_modules absent (npm install --prefix frontend)"
            )
            results.append(Result(step, "skip", detail=why))
            print(f"  {YELLOW('skip')}  {step.name} {DIM('(' + why + ')')}")
            continue

        print(f"  {DIM('....')}  {step.name} ...", end="\r", flush=True)
        res = run_step(step)
        results.append(res)
        if res.status == "pass":
            mark = GREEN("pass")
        elif res.step.blocking:
            mark = RED("FAIL")
        else:
            mark = YELLOW("warn")
        print(f"  {mark}  {step.name} {DIM(f'({res.seconds:.1f}s)')}            ")
        if res.status == "fail":
            label = "blocking" if res.step.blocking else "advisory"
            print(DIM(f"        -> {label}: {res.detail}"))
            if res.tail:
                for line in res.tail.splitlines():
                    print(DIM(f"        | {line}"))

    # Summary
    failed = [r for r in results if r.status == "fail" and r.step.blocking]
    skipped = [r for r in results if r.status == "skip"]
    passed = [r for r in results if r.status == "pass"]
    print()
    print(
        BOLD("  Summary: ") + f"{GREEN(str(len(passed)) + ' passed')}, "
        f"{RED(str(len(failed)) + ' failed') if failed else '0 failed'}, "
        f"{YELLOW(str(len(skipped)) + ' skipped')}"
    )

    if failed:
        print(RED("\n  [X] preflight FAILED -- do not push. Fix the above, then re-run.\n"))
        return 1
    advisory = [r for r in results if r.status == "fail" and not r.step.blocking]
    if advisory:
        print(
            YELLOW(f"  ({len(advisory)} advisory check(s) failed -- informational, not blocking.)")
        )
    if skipped:
        print(
            YELLOW(
                "\n  [OK] all blocking checks passed; some were skipped -- run without --quick"
                " / install frontend deps for the full gate.\n"
            )
        )
        return 0
    print(GREEN("\n  [OK] preflight passed clean. Safe to propose a push.\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
