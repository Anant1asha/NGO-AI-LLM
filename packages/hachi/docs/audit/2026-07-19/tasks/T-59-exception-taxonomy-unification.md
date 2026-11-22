# T-59 · Unify the two error systems: replace the loop's string-prefix outcomes with a `TurnOutcome`

|  |  |
|---|---|
| **Source finding** | CF-14 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~4 days |
| **Difficulty** | High (a wide, behaviour-preserving refactor with a live eval baseline — read §12 first) |
| **Files you will touch** | `src/hachi/core/loop.py`, `src/hachi/core/sub_agent.py`, `src/hachi/gateway/orchestrator.py`, `src/hachi/core/errors.py`, `src/hachi/core/eval/corpus.py`, ~9 test files, `docs/bug-bank.md` |

---

## 1. Brief

Hachi has a real exception taxonomy in `core/errors.py` — eight classes under one
`HachiError` root — and the agent loop uses **none of it**. `ExecutionLoop.run()`
instead encodes its terminal outcomes as **string prefixes on the returned text**:
nine return sites carrying five distinct prefixes, plus a sixth emitter outside the
loop. Downstream code recovers the outcome with `str.startswith()`.

When you are done, a turn's outcome is a value, not a substring, and callers branch on
a field instead of parsing English. **Read §12 before you touch anything**: those
strings are asserted by the eval corpus and nine test files, and changing them
carelessly turns the gate red for reasons that look unrelated to your diff.

## 2. Why this matters

The loop's return type is `str` (`core/loop.py:831`), so every terminal condition —
user cancellation, wall-clock timeout, budget exhaustion, workflow suspension,
iteration-limit cutoff — has to be smuggled back inside the assistant's text. That has
three concrete costs, all already visible in the code:

1. **The outcome is not addressable.** `sub_agent.py:737` recovers "was this cut off?"
   with `result.startswith(INCOMPLETE_RESULT_PREFIX)`. Any richer question ("*why* was
   it cut off, how much budget was left, what was the wait condition?") has no answer,
   because the structure was thrown away at the return statement.
2. **It already forced a workaround.** `[WORKFLOW SUSPENDED]` had to grow a side
   channel — `self._last_suspend = suspend_exc` (`loop.py:1264`) — because the comment
   at `:1261-1263` says the structured wait condition "were lost inside the return
   string." That is the design failing in-repo and being patched around, once.
3. **The prefixes leak to users.** They are literal text in the assistant's reply. The
   eval corpus has a dedicated case asserting they *don't* appear in clean output
   (`core/eval/corpus.py:412-426`), which is a test defending against your own
   sentinel design.

Meanwhile `core/errors.py` sits there, in the mypy strict gate, unused by the loop.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 System one — the real taxonomy (`core/errors.py`, 133 lines)

| Class | Line | Parent |
|---|---:|---|
| `HachiError` | 16 | `Exception` |
| `OGParseError` | 58 | `HachiError` |
| `OGValidationError` | 67 | `HachiError` |
| `ConfigError` | 81 | `HachiError` |
| `ConfigPermissionError` | 90 | `ConfigError` |
| `ToolError` | 104 | `HachiError` |
| `MCPError` | 113 | `ToolError` |
| `PermissionDeniedError` | 127 | `HachiError` |

This module **is** in the mypy strict gate (`mypy-strict-gate.ini` lists
`src/hachi/core/errors.py`) — anything you add here must be strict-clean.

### 3.2 System two — loop-local (`core/loop.py`)

```python
class AgentException(Exception):        # :106-109
    """Base exception for agent execution errors."""

    pass
```

Not a `HachiError`. Its only consumer is `core/sub_agent.py:771` (`except AgentException`),
and `sub_agent.py:732-734` documents that the branch is effectively unreachable:

```python
            # S2: ExecutionLoop.run() never raises AgentException when max_iterations
            # ... a raised exception) — so the `except AgentException` branch below is
```

### 3.3 System three — the string prefixes

The constant, with a docstring that spells out the whole problem
(`core/loop.py:112-118`):

```python
# P1-04: ExecutionLoop.run() does NOT raise when max_iterations is exhausted —
# it returns this prefix in a graceful, partial-summary string instead (see
# run()'s SESSION_ITERATION_LIMIT branch). Callers that need to distinguish
# "the task genuinely finished" from "the loop was cut off mid-task" (e.g.
# SubAgentRuntime mapping this to a non-SUCCESS status) must check for this
# prefix on the returned string — there is no exception to catch.
INCOMPLETE_RESULT_PREFIX = "[INCOMPLETE]"
```

### 3.4 ⚠️ Count correction: **NINE** outcome sites, **FIVE** prefixes

The review says eight. Verified inside `ExecutionLoop.run()` (`core/loop.py:831`):

| # | Line | Prefix | Trigger |
|---:|---:|---|---|
| 1 | `:918` | `[CANCELLED]` | cancel event at iteration boundary |
| 2 | `:937-940` | `[TIME LIMIT REACHED]` | wall deadline at iteration boundary |
| 3 | `:947` | `[BUDGET LIMIT REACHED]` | session budget |
| 4 | `:957` | `[BUDGET LIMIT REACHED]` | token safety ceiling |
| 5 | `:1066` | `[CANCELLED]` | cancel mid-stream |
| 6 | `:1081-1085` | `[TIME LIMIT REACHED]` | `_StreamTimedOut` mid-stream |
| 7 | `:1108` | `[BUDGET LIMIT REACHED]` | per-turn budget |
| 8 | `:1265` | `[WORKFLOW SUSPENDED]` | `SuspendWorkflow` |
| 9 | `:1275-1279` | `[INCOMPLETE]` | iteration limit |

Two of them are multi-line and easy to miss with a naive grep:

```python
                    return (                                              # :937-940
                        f"[TIME LIMIT REACHED] Turn exceeded "
                        f"{self.max_wall_seconds:.0f}s wall-clock limit.{partial_suffix}"
                    )
```

```python
            return (                                                      # :1275-1279
                f"{INCOMPLETE_RESULT_PREFIX} The task reached the {max_iterations}-iteration "
                "limit and could not be fully completed. Reply 'continue' to pick up where "
                "it left off."
            )
```

Note the near-duplicate pairs (1/5, 2/6) — the same outcome expressed twice, once at
the iteration boundary and once mid-stream, with **different message text**. Any
consolidation must preserve both messages or accept a user-visible change.

### 3.5 A sixth emitter lives OUTSIDE the loop

`gateway/orchestrator.py:1616`, in the daily-spend-cap check:

```python
        daily_cap_reason = self._daily_cap_exceeded()
        if daily_cap_reason:
            self._emit_event(BUDGET_EXCEEDED, {"reason": daily_cap_reason})
            return f"[BUDGET LIMIT REACHED] {daily_cap_reason}"
```

This one is in a different module, a different layer, and does not import the loop's
constant — it hardcodes the literal. A `TurnOutcome` that only covers `loop.py` leaves
this site fabricating the old format.

### 3.6 Consumers parse the strings

```python
            if result.startswith(INCOMPLETE_RESULT_PREFIX):        # core/sub_agent.py:737
```

```python
                output_not_contains("[CANCELLED]"),                # core/eval/corpus.py:418
                output_not_contains("[TIME LIMIT REACHED]"),       # :419
                output_not_contains("[BUDGET LIMIT REACHED]"),     # :420
                output_not_contains("[WORKFLOW SUSPENDED]"),       # :421
                output_not_contains("[INCOMPLETE]"),               # :422
```

`sub_agent.py:737` is the only *production* string consumer. `corpus.py:418-422` (case
`no_internal_markers_in_clean_output`) and `corpus.py:402` are eval assertions — see §12.

## 4. Reproduce the failure

There is nothing to "reproduce" — this is a design defect, not a malfunction. Prove the
shape instead, and say so rather than inventing a failing command.

```bash
# 1. Two exception roots, one of them not under HachiError.
grep -n "^class " src/hachi/core/errors.py
grep -n "class AgentException" src/hachi/core/loop.py

# 2. Nine outcome sites, five prefixes (two are multi-line — read them, don't count grep hits).
grep -n "\[CANCELLED\]\|TIME LIMIT REACHED\|BUDGET LIMIT REACHED\|WORKFLOW SUSPENDED\|INCOMPLETE" src/hachi/core/loop.py

# 3. The sixth emitter, in another layer, hardcoding the literal.
grep -rn "BUDGET LIMIT REACHED" src/hachi/gateway/

# 4. Production string-parsing consumer.
grep -rn "INCOMPLETE_RESULT_PREFIX" src/

# 5. THE IMPORTANT ONE — how much asserts these strings today.
grep -rln "BUDGET LIMIT REACHED\|TIME LIMIT REACHED\|WORKFLOW SUSPENDED\|INCOMPLETE_RESULT_PREFIX\|\[CANCELLED\]" tests/ | grep -v __pycache__
```

**You will see now:** (1) eight `HachiError` descendants and a separate bare
`AgentException`; (2) the nine sites in §3.4; (3) `gateway/orchestrator.py:1616`;
(4) `sub_agent.py:39` (import) and `:737` (use); (5) **nine test files** —
`test_daily_cap_enforcement.py`, `test_e2e_loop.py`, `test_eval_assertions.py`,
`test_eval_report.py`, `test_eventbus_reactivity.py`, `test_iteration_limit.py`,
`test_loop_backstop_cancel.py`, `test_loop_resilience.py`,
`test_sub_agent_iteration_limit_status.py` — with ~47 occurrences between them.

**You should see after the fix:** grep (2) shows the prefixes only inside a single
rendering function; grep (4) shows a field access, not a `startswith`.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> The review offers two targets — "migrate loop sentinels under `HachiError` **or** a
> `TurnOutcome` object". They are not equivalent:
>
> **(a) `TurnOutcome` value object — RECOMMENDED.** Terminal conditions are *normal
> control flow*, not errors: a budget cap firing is the system working. Modelling them
> as exceptions means `run()` raises on success-adjacent paths and every caller grows a
> try/except, including the ones that legitimately want the partial text.
> *For:* keeps the partial text, adds structure (reason, elapsed, spend, wait
> condition), and gives `_last_suspend` (`loop.py:1264`) a proper home. *Against:*
> `run()`'s return type changes, which touches every caller.
>
> **(b) Raise `HachiError` subclasses.** *For:* one taxonomy; `errors.py` finally gets
> used. *Against:* the partial text (`"".join(self._partial_text)`) is *load-bearing* —
> it is what the user sees after a cancel — so you would be smuggling data through
> exception attributes, which is the same defect wearing a different hat.
>
> **Recommendation: (a), and additionally reparent `AgentException` under `HachiError`**
> so the two-root problem goes away even though the loop stops needing it.
>
> **Second decision — the wire format.** Do the strings stay?
> **Keep them, rendered from one place.** `TurnOutcome.render()` produces the exact
> current text, and `run()` keeps returning `str` for compatibility while
> `run_outcome()` (or an out-param) returns the object. This makes the change
> **behaviour-preserving**, which is the only way to land it without churning the eval
> baseline (§12). Deleting the strings is a separate, later, user-visible decision.

Target state:

1. A value object, near the other loop types:

   ```python
   class TurnStatus(str, Enum):
       COMPLETED = "completed"
       CANCELLED = "cancelled"
       TIME_LIMIT = "time_limit"
       BUDGET_LIMIT = "budget_limit"
       SUSPENDED = "suspended"
       INCOMPLETE = "incomplete"


   @dataclass(frozen=True)
   class TurnOutcome:
       status: TurnStatus
       text: str = ""                    # partial or final assistant text
       reason: str = ""                  # the budget/cap/wait reason, machine-readable
       suspend: SuspendWorkflow | None = None

       def render(self) -> str:
           """Return the legacy prefixed string. EXACTLY the current text."""
   ```

   Frozen, per the repo's `TurnContext` precedent (CLAUDE.md: "No mutation of shared
   loop state per turn — use `TurnContext` (frozen dataclass)").

2. The nine sites build a `TurnOutcome` and return `outcome.render()`. `render()` is
   the **only** place a prefix literal appears in `loop.py`.

3. `gateway/orchestrator.py:1616` uses the same object rather than its own literal.

4. `sub_agent.py:737` branches on `status is TurnStatus.INCOMPLETE`. The
   `INCOMPLETE_RESULT_PREFIX` constant stays exported (other things may import it) but
   is consumed only by `render()`.

5. `AgentException(HachiError)` — one root.

6. Observable outcome: **no user-visible change at all.** Byte-identical strings, same
   events, same eval results. The win is that the next feature that needs "why did this
   turn end" has a field to read.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. Add `TurnStatus` + `TurnOutcome` to `core/loop.py`, with `render()` reproducing all
   five formats **character for character**, including the two multi-line ones
   (`:937-940`, `:1275-1279`) and the `if partial else` ternaries at `:918` / `:1066`.
3. Convert the nine sites one at a time, running
   `uv run pytest tests/test_loop_backstop_cancel.py tests/test_iteration_limit.py -q`
   after **each** one. That file has 20 occurrences of these strings; it is your
   fastest signal.
4. Store the outcome on the loop (`self._last_outcome`) alongside the existing
   `self._last_suspend` (`:1264`), and expose it. Do **not** remove `_last_suspend`
   yet — `gateway/orchestrator.py` reads it (see `:1522`).
5. Point `gateway/orchestrator.py:1616` at `TurnOutcome(...).render()`.
6. Change `sub_agent.py:737` to read the status field, keeping the `startswith` as a
   fallback for one release if the outcome is unavailable — and say so in a comment.
7. Reparent `AgentException` under `HachiError`. Check `sub_agent.py:771` still catches.
8. Run the full eval: `uv run hachi eval run`. It must be **unchanged** (§12).
9. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_turn_outcome.py` (**new**)
- **Test names:** `test_turn_outcome_is_addressable_without_string_parsing` and
  `test_turn_outcome_render_is_byte_identical_to_legacy_prefixes`
- **It must assert:** (1) that a real budget-capped run exposes its outcome as a value,
  and (2) that the rendered text is unchanged. Test 2 is the safety net for the whole
  refactor — it is what lets you convert nine sites without fear.
- **It must FAIL before your fix** with
  `ImportError: cannot import name 'TurnOutcome' from 'hachi.core.loop'`.

```python
# sketch — adapt to the repo's existing loop fixtures
# (tests/test_loop_backstop_cancel.py and tests/test_iteration_limit.py already
#  build a driveable ExecutionLoop — copy that harness rather than inventing one)
from __future__ import annotations

import pytest


def test_turn_outcome_render_is_byte_identical_to_legacy_prefixes() -> None:
    """render() must reproduce the exact strings callers and evals depend on.

    This is the safety net for the nine-site conversion: the eval corpus and nine
    test files assert on these literals, so any drift is a red gate.
    """
    from hachi.core.loop import TurnOutcome, TurnStatus

    assert TurnOutcome(TurnStatus.CANCELLED, text="").render() == "[CANCELLED]"
    assert TurnOutcome(TurnStatus.CANCELLED, text="hi").render() == "[CANCELLED] hi"
    assert (
        TurnOutcome(TurnStatus.BUDGET_LIMIT, reason="cap $1.00 reached").render()
        == "[BUDGET LIMIT REACHED] cap $1.00 reached"
    )
    assert TurnOutcome(TurnStatus.SUSPENDED, reason="waiting on x").render() == (
        "[WORKFLOW SUSPENDED] waiting on x"
    )


def test_turn_outcome_is_addressable_without_string_parsing() -> None:
    """A turn that hits the iteration limit must report it as a value.

    Regression: ExecutionLoop.run() encoded five terminal outcomes as prefixes on
    the returned text across nine return sites; the only way to recover the
    outcome was `result.startswith("[INCOMPLETE]")` (core/sub_agent.py:737).
    """
    from hachi.core.loop import TurnStatus

    loop = _build_loop_that_always_calls_a_tool()   # from the existing harness
    result = loop.run(max_iterations=2)

    outcome = loop.last_outcome
    assert outcome is not None, "run() must expose a structured TurnOutcome"
    assert outcome.status is TurnStatus.INCOMPLETE
    # And the legacy contract still holds for existing callers.
    assert result.startswith("[INCOMPLETE]")
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and it failed before the fix with an `ImportError`.
- [ ] `grep -c "\[CANCELLED\]\|TIME LIMIT REACHED\|BUDGET LIMIT REACHED\|WORKFLOW SUSPENDED" src/hachi/core/loop.py` counts only the occurrences inside `render()`.
- [ ] `grep -rn "BUDGET LIMIT REACHED" src/hachi/gateway/` shows the shared object, not a hardcoded literal.
- [ ] `core/sub_agent.py:737` branches on a status field.
- [ ] `AgentException` is a `HachiError` subclass.
- [ ] **`uv run hachi eval run` produces the same result as before your change** — record the before/after in the commit message.
- [ ] All nine string-asserting test files pass **unmodified**. If one needs editing, stop and re-read §12.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change any user-visible string.** This is the thing you will drift into:
  once the strings live in one `render()` function, improving the wording becomes a
  one-line temptation. Don't. The strings are asserted in nine test files and the eval
  corpus; changing them is a separate, deliberate, user-visible decision with its own
  review. Behaviour-preserving is the entire strategy here.
- **Do not collapse the near-duplicate messages** at `:918`/`:1066` or `:937-940`/`:1081-1085`.
  They differ (`"Cancelled: …"` vs `"Cancelled (mid-stream): …"`, and different partial
  suffix construction) and something may depend on the difference. Preserve both,
  even though it looks like duplication you could tidy.
- **Do not migrate the rest of the codebase onto `HachiError`.** `errors.py` has eight
  classes and there are `ToolError`/`MCPError` opportunities everywhere. That is a
  different, larger task. Reparent `AgentException`, stop.
- **Do not delete `INCOMPLETE_RESULT_PREFIX`** or its explanatory comment block
  (`loop.py:112-117`). It is imported by `sub_agent.py:39`, and Rule 3 forbids deleting
  the comment.
- **Do not remove `self._last_suspend`** (`loop.py:1264`). `gateway/orchestrator.py`
  depends on it; folding it into `TurnOutcome` is a follow-up once the object exists.
- **Do not edit `core/eval/corpus.py`'s golden fixtures** to make anything pass. See §12.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run hachi eval run                        # MUST be unchanged — run it early and often
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Run the **full** suite. `ExecutionLoop.run()` is the single hottest path in the product
— every end-to-end test, every eval replay and every gateway turn goes through it, and
the nine converted sites are the exact paths that only fire under cancellation, timeout
and budget conditions that scoped runs rarely reach. Report the **actual** pass/fail
counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Turn outcomes were string prefixes, so the loop's terminal state was unaddressable

- **Symptom:** Callers could not tell *why* a turn ended without substring-matching the assistant's reply (`result.startswith("[INCOMPLETE]")`, `core/sub_agent.py:737`). The structured wait condition for `[WORKFLOW SUSPENDED]` had already been "lost inside the return string" once and needed a side channel (`self._last_suspend`, `core/loop.py:1264`) to recover it.
- **Root cause:** `ExecutionLoop.run() -> str` encoded five terminal outcomes as text prefixes across **nine** return sites (`core/loop.py` `:918`, `:937-940`, `:947`, `:957`, `:1066`, `:1081-1085`, `:1108`, `:1265`, `:1275-1279`), with a sixth emitter hardcoding the literal in another layer (`gateway/orchestrator.py:1616`). A separate loop-local `AgentException` sat outside the `core/errors.py` `HachiError` taxonomy.
- **Fix:** Added a frozen `TurnOutcome(status, text, reason, suspend)` + `TurnStatus` enum; the nine sites build it and return `outcome.render()`, which is now the only place a prefix literal exists. `sub_agent` branches on the status field. `AgentException` reparented under `HachiError`. Rendered text is byte-identical — the change is behaviour-preserving by design.
- **Avoid:** never encode control-flow state in a human-readable return string. It cannot carry structure, it leaks to users, and it makes every downstream branch a substring match that no type checker can verify. If a function must return both text and outcome, return an object.
- **Locked by:** `tests/test_turn_outcome.py` — `test_turn_outcome_render_is_byte_identical_to_legacy_prefixes`
```

## 12. Known traps

- **⚠️ THE EVAL BASELINE. Read this before you edit a single string.**
  `core/eval/corpus.py` is a **golden corpus** — `output_not_contains("[CANCELLED]")`
  and its four siblings at `:418-422`, plus `output_not_contains("[INCOMPLETE]")` at
  `:402`. `uv run hachi eval run` is a **blocking** step in `scripts/preflight.py:117`.
  If you change a prefix, the eval goes red and the failure will read like a model
  regression, not a refactor. Two rules:
  1. Keep `render()` byte-identical and the corpus needs **no** change — that is why §5
     recommends it.
  2. If a corpus change becomes genuinely unavoidable, update it **in the same commit**
     and say so explicitly in the commit message. Per
     [CORRECTIONS.md](CORRECTIONS.md), correcting a test that asserts wrong behaviour is
     allowed; silently re-baselining an eval to go green is not.
- **Nine test files, ~47 assertions.** `test_loop_backstop_cancel.py` alone has 20.
  Run it after every converted site, not at the end.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`core/errors.py` is in the strict mypy gate** (`mypy-strict-gate.ini`).
  `core/loop.py` is **not**. So reparenting `AgentException` under `HachiError` may
  surface strict errors in `errors.py` that `loop.py` never had to satisfy — expect
  that, don't work around it by loosening the gate config.
- **Two of the nine sites are multi-line returns** (`:937-940`, `:1275-1279`). A
  line-oriented grep finds the prefix but not the whole statement; read the full
  expression before replacing it, including the `partial_suffix` interpolation.
- **The `if partial else` shape** at `:918` and `:1066` —
  `f"[CANCELLED] {partial}" if partial else "[CANCELLED]"` — means the empty-partial
  case has **no trailing space**. Reproduce that exactly; a naive
  `f"[CANCELLED] {text}".strip()` is not the same for other inputs.
- **`SuspendWorkflow` is a control-flow exception, not an error** (`loop.py:121-127`).
  Do not reparent it under `HachiError`; its docstring explains it signals a clean
  suspend, and it is caught by the loop itself.
