# CLAUDE.md — Hachi (agent rules)

How you (Claude Code) must work in **Hachi**, an autonomous agent engine whose skills are
ObjectGraph (`.og`) files. Core loop: **CLI → Orchestrator → ExecutionLoop → ToolRegistry → LLM**.
These rules win where they conflict with your defaults. If a rule makes a task impossible,
STOP and ask — never silently work around it.

Some rules are enforced **mechanically** by hooks in `.claude/` (push-lock, secret-scan,
auto-format, red-tests-block-stop) — see `.claude/hooks/README.md`. Hooks are the wall; this
file is the advice. Don't route around either.

Reusable **role subagents** live in `.claude/agents/` — delegate to `regression-guard` for
bug-fixes (failing test first), `scope-sentinel` to review a diff before commit, and
`gate-keeper` to run the gate. They restate these rules because subagents don't inherit this
file; see `.claude/agents/README.md`.

## The gate — verification is not optional

"Looks done" is **not** done. A change you can't verify doesn't land. One command runs the
whole gate (and mirrors CI):

```bash
uv run python scripts/preflight.py          # full: ruff, mypy-gate, skill-lint, eval, FULL pytest, frontend
uv run python scripts/preflight.py --quick  # fast inner loop (skips full pytest + FE build)
```

Run it yourself and report the **actual** result. Other key commands:

```bash
uv sync --extra dev      # install dev deps
uv run pytest -q         # full suite — the contract (Rule 2)
uv run hachi run         # Textual TUI
```

Windows: if a `.exe` shim breaks pytest/mypy (OS error 4551), fall back to `python -m pytest` /
`python -m mypy` (see BB-1).

## Non-negotiable rules

1. **Git is the safety net.** Report pre-existing uncommitted WIP before you start so your work
   isn't conflated with it. Commit only when asked or at a natural close (Conventional Commits:
   `feat`/`fix`/`docs`/`refactor`/`test`). Never amend/rebase/force-push/`reset --hard` existing
   commits without permission. **Never push to main/master without my explicit OK in this
   conversation** (the push-lock enforces it). If something breaks and 2 attempts don't fix it,
   STOP and report the last known-good commit.
2. **Tests are a contract — don't cheat them.** Never weaken, skip, comment out, or delete a
   test to go green; fix the **code**. **For every bug: write a FAILING regression test first,
   then fix, then lock it with an entry in `docs/bug-bank.md` (the regression law).** Tests must
   assert real, observed behavior. Run the **FULL** `pytest` suite before claiming done and
   report actual pass/fail counts — scoped runs miss Hachi's cross-module regressions.
3. **Stay in scope.** Change only what the task needs — no drive-by refactors, renames, or
   reformats. **Never run a repo-wide `ruff format`** (it reflows ~100 files; the auto-format
   hook handles touched files). Never delete functionality, edge-case handling, validation, or
   comments unless told — flag it. Reuse existing code; **don't add a dependency without
   asking**; search before writing new logic.
4. **Don't guess library APIs.** Verify against installed package source / real docs (especially
   `anthropic`, `chromadb`, `textual`, `fastapi`) and the pins in `pyproject.toml`.
5. **Be honest about state.** If you're stuck, blocked, or unsure, say so. Never claim
   unverified success — especially on Windows. Don't over-engineer: solve the stated problem.

## Security guardrails (inviolable)

- No `subprocess` with `shell=True`.
- No interactive credential prompts during Textual boot — resolve credentials lazily at call time.
- No `.env` autoload in the core/library import path — the CLI edge merges it, gated by
  `HACHI_DISABLE_DOTENV_AUTOLOAD`; resolve creds lazily at call time (BB-2). No mutation of
  shared loop state per turn — use `TurnContext` (frozen dataclass).
- Prefer queued background work (`jobs/queue.py`) over fire-and-forget threads.

## Before knowledge / decisions — check these first

- **`docs/bug-bank.md`** — prior autopsies & recurring gotchas. Check it BEFORE debugging; the
  SessionStart hook injects the top entries. Add an entry for every bug you fix.
- **`ARCHITECTURE.md`** — the map: entry points, loop, memory, permissions, gateway, frontend
  contract, CI, and the **enforced module layering** (`import-linter` blocks new cross-layer
  imports — the engine must not import `cli`/`tui`/`gateway`; `og_engine` stays pure).
- **`docs/DECISIONS.md`** — settled decisions / ADRs. Don't relitigate; record new ones here.
- **`docs/reference/objectgraph-spec.md`** — the `.og` format. Conventions & PR flow:
  **`CONTRIBUTING.md`**.

## Out of scope — do not build unless explicitly asked

- **Multi-tenant** support (single-tenant is load-bearing) — flag for a decision.
- **Encryption-at-rest** and other security-architecture changes — flag, don't auto-build.
- **Desktop / mobile apps** — deferred until the product is feature-rich and stable.
- **New runtime dependencies** — propose first; don't add to `pyproject.toml` unprompted.
- **`tokoboros` compatibility shims** — explicitly removed; do not reintroduce. Tracked
  code/docs stay tokoboros-free.
