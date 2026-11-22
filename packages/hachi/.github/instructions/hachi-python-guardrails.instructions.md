---
description: "Use when editing Python code in hachi, including core runtime, CLI, TUI, tools, and tests. Enforces project coding conventions, runtime safety guardrails, and validation expectations."
name: "Hachi Python Guardrails"
applyTo: "**/*.py"
---
# Hachi Python Guardrails

- Target Python 3.11+ syntax and typing.
- Keep line length at 100 and maintain existing Ruff-compatible style.
- Add type hints and docstrings for public functions and classes.
- Prefer focused modules and small functions over broad multi-purpose files.
- Use `pathlib.Path` for filesystem paths.

## Runtime and Security Rules

- Do not introduce `subprocess` calls with `shell=True`.
- Do not add interactive credential prompts during Textual boot.
- Resolve credentials lazily at call time and return actionable missing-token errors.
- Avoid mutating shared loop prompt state per turn; use turn-scoped context patterns.
- Prefer durable queued background work over fire-and-forget daemon threads.

## Change and Verification Expectations

- Keep behavior and public APIs stable unless the task explicitly requests a change.
- Add or update focused tests under `tests/` for behavior changes.
- Before finishing a change, run:
  - `uv run ruff check src tests`
  - `uv run mypy src --ignore-missing-imports`
  - `uv run pytest -q`
- On Windows, if editable install lock breaks pytest, use:
  - `PYTHONPATH=src uv run --with pytest --no-project pytest -q`
