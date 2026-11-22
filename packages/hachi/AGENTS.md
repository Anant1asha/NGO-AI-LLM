# AGENTS.md

Cross-tool entrypoint for coding agents working in **Hachi**. The authoritative,
detailed operating rules live in **[CLAUDE.md](CLAUDE.md)** — read it first. It is the
single source of truth and **overrides anything here** on conflict; don't duplicate its
rules into this file.

## Quick start

```bash
uv sync --extra dev                    # install dev deps
uv run python scripts/preflight.py     # the gate (lint, types, tests, FE) — must be GREEN before a push
uv run pytest -q                       # full test suite (the contract)
uv run hachi run                       # launch the Textual TUI
uv run hachi doctor                    # diagnostics / resolved paths
```

Windows: if a `.exe` shim breaks `pytest`/`mypy` (OS error 4551), fall back to
`python -m pytest` / `python -m mypy` — see [docs/bug-bank.md](docs/bug-bank.md) (BB-1).

## The rules — see CLAUDE.md

CLAUDE.md is the contract: the gate, the non-negotiable rules (git as the safety net,
tests-are-a-contract + the regression law, stay-in-scope, verify-library-APIs, be honest
about state), and the **inviolable security guardrails** (no `subprocess(shell=True)`, lazy
credential resolution, `TurnContext` for per-turn state, queued background work over
fire-and-forget threads). They are not repeated here.

## Map & source docs (link, don't duplicate)

- Architecture & enforced module layering: [ARCHITECTURE.md](ARCHITECTURE.md)
- Entry point `src/hachi/cli/main.py` → orchestrator → `core/loop.py` → tools → LLM
- Settled decisions / ADRs: [docs/DECISIONS.md](docs/DECISIONS.md)
- ObjectGraph (`.og`) spec: [docs/reference/objectgraph-spec.md](docs/reference/objectgraph-spec.md)
- Contribution process & standards: [CONTRIBUTING.md](CONTRIBUTING.md)
- Full documentation index: [docs/README.md](docs/README.md)
- Historical (pre-rename) roadmap: [docs/history/god-tier-plan.md](docs/history/god-tier-plan.md)
- CI pipeline: [.github/workflows/ci.yml](.github/workflows/ci.yml)
