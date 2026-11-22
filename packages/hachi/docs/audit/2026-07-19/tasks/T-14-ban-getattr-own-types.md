# T-14 · Make `getattr(x, "field", None)` against our own types a lint error

|  |  |
|---|---|
| **Source finding** | CF-1 recommendation (c) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none — **independent of T-04 … T-13**, can land in parallel |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | Medium (the rule's *scope* is the hard part — read §5) |
| **Files you will touch** | `scripts/check_getattr.py` (new), `scripts/preflight.py`, `docs/bug-bank.md` |

---

## 1. Brief

CF-1's third recommendation is a rule: *"a `getattr(x, "field", None)` against your own
types is a lint error."* That idiom converts *"this attribute was never implemented"*
into a silently-taken fallback, and it directly masked at least four of the dead features
in this wave. Ruff has no built-in rule for it.

Build a small AST checker — modelled on the repo's existing `scripts/check_adrs.py` —
wire it into `scripts/preflight.py`, and start it **advisory with an allowlist of the
current legitimate uses** so it lands green and can be ratcheted.

## 2. Why this matters

Four verified examples from this audit, all of which read as careful defensive code and
all of which were permanently dead:

| Site | What the `getattr` hid |
|---|---|
| `gateway/fastapi_app.py:431`, `core/cost.py:106` | `ProcessSharedServices.session_store` — a field declared **nowhere**. Three readers, zero writers; every "prefer the shared store" branch dead, plus a SQLite handle leaked per message. → [T-10](T-10-shared-session-store.md) |
| `gateway/orchestrator.py:753` | `MemoryManager.memory_dir` — `grep -c "memory_dir" src/hachi/core/memory.py` is **0**. The gardener reader returned `[]` before touching the file. → [T-08](T-08-memory-gardener.md) |
| `core/loop.py:755` | `ResilientClient.max_tokens` — not exposed, so `next_call_ceiling_tokens` silently became `0` and the pre-flight token safety ceiling went inert under routing. → [T-27](T-27-forward-max-tokens-resilient-client.md) |
| `cli/main.py:1313`, `:1389` | `AgentSession.reindex_skills` — **does not exist anywhere in `src/`**. `if callable(reindex)` is permanently `False`, so authoring saves never re-index and `reindexed_ms` is always ~0. |

That last one is not in the audit; it was found while verifying this task, which is
itself the argument for the check.

The rule is not "`getattr` is bad". Three-argument `getattr` against a **foreign** or
genuinely duck-typed object is legitimate. The rule is: **against a type we own and can
change, a missing attribute is a bug, and the code should raise, not default.**

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 There is no such check today

Ruff has no built-in rule for defaulted `getattr`. `scripts/preflight.py:75-140` runs
`ruff check`, `mypy` (scoped strict gate), `lint_skills.py`, `lint-imports`,
`security-audit`, `deptry`, `vulture`, a complexity report, `check_adrs.py`, `hachi eval
run`, the frontend steps, and pytest. **Nothing looks at `getattr`.**

### 3.2 The scale — pick the narrow form

```
$ grep -rc "getattr(" src/ --include=*.py | ...        # 241 total getattr calls
$ # three-arg with a literal string attribute name:    # 217
$ # the narrow form: getattr(self.<attr>, "<name>", <default>)   # 29
```

Per-file for the **narrow** form:

| File | Hits |
|---|---|
| `src/hachi/gateway/orchestrator.py` | 15 |
| `src/hachi/core/loop.py` | 9 |
| `src/hachi/core/memory_vault.py`, `core/oauth.py`, `core/resilience.py`, `core/sub_agent.py`, `jobs/queue.py` | 1 each |

**29 is a tractable first scope. 217 is not.** See §5 for why the narrow form is also the
*right* scope, not merely the convenient one.

Representative real hits:

```python
src/hachi/gateway/orchestrator.py:753:  memory_dir = getattr(self.memory, "memory_dir", None)          # DEAD (T-08)
src/hachi/core/loop.py:755:             next_call_ceiling_tokens = getattr(worst_case_next_call, "max_tokens", 0) or 0   # DEAD under routing (T-27)
src/hachi/core/loop.py:557:             _get_header = getattr(self.memory, "get_context_header", None)  # exists — MemoryManager.get_context_header (memory.py:871)
src/hachi/gateway/orchestrator.py:692:  tracker = getattr(self.loop, "cost_tracker", None)             # exists on ExecutionLoop
src/hachi/gateway/orchestrator.py:1319: client = getattr(self, "_sub_agent_client", None) or getattr(self.loop, "llm_client", None)
```

That last one is the CF-6 "constructor contract fiction": `boot_agent` stashes
`_sub_agent_client` onto the session after construction (`orchestrator.py:3467-3496`), so
the attribute genuinely may not exist. It is a **real** legitimate-today use and belongs
in the allowlist with a comment pointing at CF-6 — not silently suppressed.

### 3.3 The model to copy

`scripts/check_adrs.py:1-27` — stdlib-only, exits non-zero on violations, never imports
the product:

```python
#!/usr/bin/env python
"""ADR-lint -- keep the architecture decision records honest (Guardrails Phase 3).
...
Advisory in the gate today (like the other Phase-2 rails); ratchet to blocking once the
baseline is clean. Exits non-zero on any violation. Stdlib only -- never imports the product.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
```

`scripts/lint_skills.py` is the other precedent (it *does* import the product, which
`check_adrs.py` deliberately avoids — follow `check_adrs.py`).

### 3.4 The gate's advisory-then-ratchet convention

`scripts/preflight.py:92-96`:

```python
    # Advisory rails (Guardrails Phase 2): surfaced every run, never block. Ratchet each to
    # blocking once its baseline reaches zero. Config in pyproject [tool.deptry]/[tool.vulture]
    # and [tool.ruff.lint.pylint]. deptry currently flags 4 declared-but-unused SDK extras.
    Step("deptry (unused/missing deps)", [["uv", "run", "deptry", "src"]], blocking=False),
    Step("vulture (dead code)", [["uv", "run", "vulture"]], blocking=False),
```

This is the established pattern for a new rail, and it is what you should follow.

## 4. Reproduce the failure

Nothing to reproduce — this task adds a missing check.

The **absence** is verifiable in one command:

```bash
grep -rn "getattr" scripts/preflight.py    # -> no output today
```

And the class of bug the check would have caught is demonstrable right now:

```bash
# An attribute three call sites read, declared nowhere:
grep -rn "getattr(.*session_store" src/
grep -rn "session_store" src/hachi/gateway/shared_services.py    # -> no field declaration

# A method two call sites guard on, defined nowhere:
grep -rn "reindex_skills" src/    # -> only the two getattr lookups; no def
```

**You will see now:** readers with no corresponding definition, and no tool that notices.
**You should see after the fix:** `uv run python scripts/check_getattr.py` reporting each
un-allowlisted occurrence with `path:line` and the attribute name.

## 5. What "fixed" looks like

### 5.1 Recommended approach — an AST checker

Grep cannot do this: it cannot tell a 2-arg `getattr` from a 3-arg one reliably, cannot
see a `getattr` split across lines, and cannot exclude a dynamic (non-literal) attribute
name. Use `ast`.

`scripts/check_getattr.py`, stdlib-only, following `check_adrs.py`'s shape:

```python
#!/usr/bin/env python
"""getattr-lint -- a defaulted getattr against one of OUR types is a bug, not a default.

CF-1: `getattr(x, "field", None)` converts "this attribute was never implemented" into a
silently-taken fallback. It masked at least four dead features in the 2026-07-19 audit
(ProcessSharedServices.session_store, MemoryManager.memory_dir, ResilientClient.max_tokens,
AgentSession.reindex_skills -- none of which existed).

Scope: three-argument `getattr()` with a LITERAL string attribute name, where the object
expression is `self.<attr>` or `self`. That is the form that reaches into a
Hachi-owned object; foreign/duck-typed objects reached via locals are out of scope for
now (see ALLOWLIST notes and the module docstring in scripts/check_adrs.py for the
advisory-then-ratchet convention).

Advisory in the gate today. Ratchet to blocking once the allowlist stops growing.
Exits non-zero on any un-allowlisted occurrence. Stdlib only -- never imports the product.
"""
```

Detection:

```python
def _violations(tree: ast.AST) -> list[tuple[int, str]]:
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "getattr" or len(node.args) != 3:
            continue
        target = node.args[1]
        if not (isinstance(target, ast.Constant) and isinstance(target.value, str)):
            continue                      # dynamic attribute name -- out of scope
        obj = node.args[0]
        is_self = isinstance(obj, ast.Name) and obj.id == "self"
        is_self_attr = (
            isinstance(obj, ast.Attribute)
            and isinstance(obj.value, ast.Name)
            and obj.value.id == "self"
        )
        if is_self or is_self_attr:
            out.append((node.lineno, target.value))
    return out
```

The allowlist is an explicit `frozenset` of `"<relative/path.py>:<attr>"` entries, **each
with a one-line comment saying why**:

```python
ALLOWLIST: frozenset[str] = frozenset({
    # CF-6: boot_agent stashes these onto the session AFTER construction
    # (orchestrator.py:3467-3496), so the attribute genuinely may be absent.
    # Burn down by making them constructor args.
    "src/hachi/gateway/orchestrator.py:_sub_agent_client",
    ...
})
```

Key `path:attr`, **not** `path:line` — line numbers drift and would make the allowlist
rot on every unrelated edit.

The output must be actionable — `path:line: getattr(self.x, "attr", ...)` plus a one-line
reminder of the rule and how to allowlist.

### 5.2 Why the narrow scope is the right scope, not just the easy one

`getattr(self.memory, "memory_dir", None)` and `getattr(some_local, "model", "unknown")`
are different animals:

- `self.<attr>` is a **collaborator this class was constructed with**. Its type is known
  to the author, is in this repo, and is changeable. A missing attribute there is a wiring
  bug — exactly what CF-1 is about.
- A defaulted `getattr` on an arbitrary local is frequently legitimate duck typing over
  third-party SDK objects or optional protocol members (`getattr(resp, "usage", None)`
  against an `anthropic` response is correct and must not be flagged).

Starting at 217 sites produces an allowlist nobody reads and a rail everyone ignores.
Starting at 29 produces a rail that means something. **Widen later, deliberately, with
its own task** — and say so in the checker's docstring so the next reader knows the scope
is a choice, not an oversight.

### 5.3 Inventory first, and report the number

**Before writing the fix, run the detector over `src/` and inventory every hit**, sorting
each into: (a) attribute genuinely exists → convert to a direct read;
(b) attribute does not exist → **you have found a new dead feature: file it, do not fix
it here**; (c) legitimately optional → allowlist with a comment.

The initial baseline should be **29** for the narrow form (§3.2). If your number differs,
your detector's scope differs from this spec's — reconcile before continuing.

**State the count and the (a)/(b)/(c) split in your PR description.** That number is the
finding; the script is just how you got it.

### 5.4 Wire it into the gate

Add to `scripts/preflight.py` `STEPS`, next to `adr-lint` (`:116`):

```python
    # Advisory rail (CF-1): a defaulted getattr against one of our own types converts a
    # missing attribute into a silent fallback. Ratchet to blocking once the allowlist
    # stops growing. See scripts/check_getattr.py.
    Step("getattr-lint (own types)", [["uv", "run", "python", "scripts/check_getattr.py"]], blocking=False),
```

`blocking=False` at first, matching `deptry` / `vulture` / `adr-lint`
(`preflight.py:92-116`). **Say in the PR what the ratchet condition is** — e.g. "blocking
once the allowlist has been stable for one cycle" — or the rail stays advisory forever,
which is how a rail becomes noise.

### 5.5 Make it loud (required)

The check *is* the loudness for this task. But also fix at least the ones you can fix
trivially: any hit in category (a) becomes a direct attribute read, so a future typo is an
`AttributeError` instead of a silent default. That is the behavioural half — **a checker
that only reports and never changes a line of production code has not made anything
louder yet.**

Do not attempt category (b) — those are dead features owned by
[T-08](T-08-memory-gardener.md), [T-10](T-10-shared-session-store.md), and
[T-27](T-27-forward-max-tokens-resilient-client.md).

## 6. Steps

1. Write `scripts/check_getattr.py` with an **empty** allowlist.
2. Run it over `src/`. Record the total. Reconcile against 29 (§5.3).
3. Triage every hit into (a)/(b)/(c). Write the triage into the PR description.
4. Write the regression test from §7. Run it. Watch it fail.
5. Populate `ALLOWLIST` with the (c) entries, each with a why-comment.
6. Convert the (a) entries to direct attribute reads. File the (b) entries as findings —
   they are already owned by T-08 / T-10 / T-27; confirm before filing a duplicate.
7. Add the `Step` to `scripts/preflight.py` (§5.4).
8. Run the test. Watch it pass. Run the script; confirm exit 0.
9. Run `uv run python scripts/preflight.py`. Report real counts.
10. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_check_getattr.py` (new)
- **Test names:** `test_detects_defaulted_getattr_on_self_attribute`,
  `test_ignores_two_arg_getattr_and_dynamic_names`,
  `test_src_tree_has_no_unallowlisted_violations`
- **It must assert:** the checker's real output over real source text — including that it
  does **not** fire on the legitimate forms. A detector with no false-negative *and*
  no false-positive test is a detector nobody will trust.
- **It must FAIL before your fix** with:
  `ModuleNotFoundError: No module named 'check_getattr'` (the script does not exist yet).

```python
# sketch — adapt to the repo's existing fixtures
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_getattr import _violations  # noqa: E402


def test_detects_defaulted_getattr_on_self_attribute() -> None:
    src = 'class A:\n    def f(self):\n        return getattr(self.memory, "memory_dir", None)\n'
    assert _violations(ast.parse(src)) == [(3, "memory_dir")]


def test_ignores_two_arg_getattr_and_dynamic_names() -> None:
    cases = [
        'getattr(self.x, "attr")',                # 2-arg: raises on absence — fine
        'getattr(self.x, name, None)',            # dynamic name — out of scope
        'getattr(response, "usage", None)',       # foreign object via a local — out of scope
    ]
    for src in cases:
        assert _violations(ast.parse(src)) == [], src


def test_src_tree_has_no_unallowlisted_violations() -> None:
    """The rail's real contract: the tree is clean, or every exception is documented."""
    from check_getattr import main

    assert main() == 0, "run `uv run python scripts/check_getattr.py` to see the offenders"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The second test is the one that keeps this rail alive: a checker that flags
`getattr(response, "usage", None)` against an `anthropic` SDK object will be disabled
within a week.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and failed before the fix.
- [ ] `scripts/check_getattr.py` exists, is stdlib-only, does not import the product, and
      exits non-zero on an un-allowlisted violation.
- [ ] The **initial hit count** and its (a)/(b)/(c) triage are stated in the PR
      description (§5.3).
- [ ] Every allowlist entry carries a one-line comment explaining why, and is keyed on
      `path:attr` — not on a line number.
- [ ] All category-(a) hits are converted to direct attribute reads.
- [ ] `scripts/preflight.py` has a `getattr-lint (own types)` step, `blocking=False`, with
      the ratchet condition stated in the PR.
- [ ] `uv run python scripts/check_getattr.py` exits 0 on a clean tree.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not widen to all 217 three-arg `getattr` calls.** §5.2 explains why. The most
  likely failure mode of this task is an over-broad rule that generates an allowlist
  nobody reads, gets marked advisory forever, and protects nothing.
- **Do not fix the dead features you find.** Category (b) hits are owned by
  [T-08](T-08-memory-gardener.md) (`memory_dir`), [T-10](T-10-shared-session-store.md)
  (`session_store`), and [T-27](T-27-forward-max-tokens-resilient-client.md)
  (`max_tokens`). If you find one **not** covered by those —
  e.g. `reindex_skills` (`cli/main.py:1313`, `:1389`) — **file it as a finding, do not fix
  it**. Fixing `reindex_skills` means deciding what re-indexing should do, which is a
  design question ([T-04](T-04-kennel-pack-store.md) §9 leaves it deliberately open).
- **Do not make the step blocking on day one.** The repo's convention is
  advisory-then-ratchet (`preflight.py:92-96`), and a new blocking rail that fails on
  someone else's in-flight branch will simply be reverted.
- **Do not write a custom Ruff plugin or add a linter dependency.** The repo already has
  two precedents for a hand-rolled `scripts/*.py` check and a rule against unprompted
  dependencies (CLAUDE.md Rule 3).
- **Do not extend the rule to `hasattr`** in this pass, even though
  `hasattr(_shared, "session_store")` (`fastapi_app.py:1018`) is the same bug in a
  different syntax. Note it in the checker's docstring as the obvious next widening.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/check_getattr.py       # the new rail alone
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — `getattr(x, "field", None)` against our own types silently disabled four features

- **Symptom:** four separate features were permanently inert while their call sites read
  as careful defensive code: `ProcessSharedServices.session_store` (declared nowhere —
  three readers, every "prefer shared store" branch dead, plus a leaked SQLite handle per
  message), `MemoryManager.memory_dir` (does not exist — the gardener reader returned
  `[]` before touching the file), `ResilientClient.max_tokens` (not exposed — the
  pre-flight token safety ceiling silently computed 0 under routing), and
  `AgentSession.reindex_skills` (defined nowhere — authoring saves never re-indexed and
  reported `reindexed_ms: 0`).
- **Root cause:** a three-argument `getattr` against a Hachi-owned collaborator converts
  "this attribute was never implemented" into a silently-taken default. `mypy` cannot
  flag it (the call is well-typed), `ruff` has no rule for it, and it reads as
  future-proofing — so it survives review indefinitely.
- **Fix:** added `scripts/check_getattr.py`, a stdlib-only AST rail that flags
  `getattr(self, "...", default)` and `getattr(self.<attr>, "...", default)` with a
  literal attribute name, allowlisted the genuinely-optional cases with a reason each,
  converted the rest to direct attribute reads, and wired it into
  `scripts/preflight.py` as an advisory step (to be ratcheted to blocking).
- **Avoid:** against a type WE own, a missing attribute is a bug — read it directly and
  let `AttributeError` be loud. Reserve defaulted `getattr` for foreign/SDK objects and
  genuinely optional protocol members, and comment why at each site. `hasattr` guards on
  our own types are the same bug in different syntax.
- **Locked by:** `tests/test_check_getattr.py` —
  `test_src_tree_has_no_unallowlisted_violations`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- `scripts/check_adrs.py` deliberately does **not** import the product; `lint_skills.py`
  does. Follow `check_adrs.py` — a lint rail that imports `hachi` will fail on any branch
  where the package does not import cleanly, which is exactly when you most want the rail
  to run.
- Use `ast.parse(path.read_text(encoding="utf-8"))`. On Windows a missing explicit
  encoding falls back to the ANSI codepage and will raise on any non-ASCII source file.
- Skip `__pycache__`, `.venv`, and `frontend/` when walking. `Path.rglob("*.py")` under
  `src/hachi` is sufficient — do **not** walk the repo root (`.claude/worktrees/` contains
  full repo copies and would triple your hit count with phantom findings).
- `vulture` (advisory) may start flagging things once you convert `getattr` reads to
  direct attribute access. Read its output; do not suppress it reflexively.
- The allowlist must be keyed on `path:attr`. A line-number key rots on the next
  unrelated edit and someone will delete the whole rail rather than maintain it.
