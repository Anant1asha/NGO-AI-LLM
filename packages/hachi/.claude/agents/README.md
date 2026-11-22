# Hachi role subagents

These are committed **Claude Code subagents** (Guardrails Phase 4) — reusable roles that encode
the disciplines a hook can't enforce on its own. The hooks in [`../hooks/`](../hooks/README.md)
are the mechanical floor (they *block*); these agents are the *workflow* (they do the work the
right way). Claude Code auto-delegates to them based on their `description`, or you can ask for
one by name.

| Agent | Use it when | Can edit? | Model |
|-------|-------------|-----------|-------|
| [`regression-guard`](regression-guard.md) | Fixing a bug / regression | yes | sonnet |
| [`scope-sentinel`](scope-sentinel.md) | Reviewing a diff before commit | no (read-only) | inherit |
| [`gate-keeper`](gate-keeper.md) | Checking the preflight gate before a push | no | sonnet |

## Why these three
They map to the three disciplines that can't be a one-shot hook:

- **The regression law** (failing test → fix → bug-bank entry) needs judgement and code, so it
  can't be a Stop hook — `regression-guard` carries the whole ritual so a fix never lands with the
  test step skipped.
- **Scope & contract review** is a reading-and-judgement task — `scope-sentinel` reads the diff
  against CLAUDE.md (scope, tests-as-contract, deps, layering, security) without touching it.
- **The gate is multi-minute and easy to fake** — `gate-keeper` runs `scripts/preflight.py` and
  reports the REAL result, never an assumed green. (`stop_guard.py` only blocks on red `ruff`;
  the full gate is bigger than a hook should run.)

## Important: subagents do NOT inherit CLAUDE.md
A subagent's Markdown body is its **entire** system prompt — it does not receive the project's
CLAUDE.md, the conversation history, or the main Claude Code system prompt. So each agent file
**restates** the rules it needs (the regression law, the gate command, the BB-1 Windows fallback,
the layering, the security guardrails). **When a project rule changes, update the agent files too**
— they are deliberately redundant with CLAUDE.md, and that redundancy has to be maintained.

## Editing / adding
- Frontmatter: `name`, `description` (required); `tools`, `model`, `color`, … (optional). Omit
  `tools` to inherit all; listing it narrows the grant. `model` may be `sonnet`/`opus`/`haiku`/
  `inherit`.
- Keep them **self-contained** (see above) and **in scope** — these encode existing rules; they
  don't invent policy. New policy goes through CLAUDE.md / DECISIONS.md first.
