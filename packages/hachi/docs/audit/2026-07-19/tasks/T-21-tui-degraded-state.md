# T-21 · Give the TUI cockpit an explicit DEGRADED state instead of plausible fiction

|  |  |
|---|---|
| **Source finding** | CF-4(e) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P2** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none (independent) |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | Medium (one design decision in §5; then ~25 mechanical edits) |
| **Files you will touch** | `src/hachi/tui/cockpit/data.py`, a small number of `src/hachi/tui/cockpit/views/*.py`, `tests/test_cockpit_*.py`, `docs/bug-bank.md` |

---

## 1. Brief

`CockpitData` is the facade every one of the TUI's 12 views reads through. Its contract,
stated in its own docstring, is that it **never raises and always returns real or
placeholder data**. In practice that means a crashed or unreachable gateway renders as a
perfectly healthy cockpit populated with fabricated approvals, spend and audit rows —
and the only trace is a `log.debug` line nobody sees at the default level. When you are
done, a *failed live call* produces a visible DEGRADED state; a *deliberately offline*
cockpit keeps behaving as it does today.

## 2. Why this matters

Of everything in CF-4, this is the one that lies to the operator's face. A user runs
`hachi run`, the gateway has died, and the cockpit shows: one pending approval to write
`~/Documents/report.md`, a spend figure, an audit log. None of it is real. The
governance screens of a governance product are displaying invented governance data,
confidently, with no error anywhere on screen.

The distinction that makes this fixable without a rewrite: `CockpitData(None)` is
**deliberate offline mode** — used by tests and by an intentionally disconnected
cockpit, and placeholders there are a design choice. The bug is the *other* branch:
`client is not None`, the call raised, and the failure is converted into fiction. Fix
that branch only.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The contract, stated in the file's own docstring — `src/hachi/tui/cockpit/data.py:1-7`

```python
"""CockpitData — the data facade for all 12 cockpit views.

Constructed with an optional GatewayClient (None ⇒ pure-offline mode).
Every method wraps the client call in try/except GatewayError and falls
back to the matching placeholder_*() from hachi.client.gaps.
Methods NEVER raise to the caller — they always return real or placeholder data.
"""
```

Line 6 is the sentence this task changes.

### 3.2 Twenty-four placeholder imports — `src/hachi/tui/cockpit/data.py:15-40`

```python
from hachi.client.gaps import (
    placeholder_active_jobs,
    placeholder_activity,
    placeholder_agents,
    placeholder_approvals,
    placeholder_audit_log,
    placeholder_auth_targets,
    placeholder_capabilities,
    placeholder_config,
    placeholder_dashboard,
    placeholder_failed_jobs,
    placeholder_health,
    placeholder_mcp_servers,
    placeholder_mcp_tools,
    placeholder_memory,
    placeholder_models,
    placeholder_og_nodes,
    placeholder_recall,
    placeholder_routines,
    placeholder_sessions,
    placeholder_setup,
    placeholder_skills,
    placeholder_spend,
    placeholder_tool_calls,
    placeholder_trust_bar,
)
```

Measured: **25 `return placeholder_*` sites** across a 604-line file
(`rg -c "return placeholder_" src/hachi/tui/cockpit/data.py` → `25`; `placeholder_trust_bar`
and `placeholder_dashboard` each appear twice).

### 3.3 The pattern, three times over

`data.py:166-173`, `spend`:

```python
    def spend(self, session_id: str | None = None) -> SpendSnapshot:
        """Return the spend snapshot (turns, tidies, models)."""
        if self._client is not None:
            try:
                return self._client.get_spend(session_id=session_id)
            except Exception as exc:
                log.debug("spend() fallback: %s", exc)
        return placeholder_spend()
```

`data.py:179-186`, `approvals`:

```python
    def approvals(self) -> list[Approval]:
        """Return the list of pending approval requests."""
        if self._client is not None:
            try:
                return self._client.list_approvals()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("approvals() fallback: %s", exc)
        return placeholder_approvals()  # type: ignore[no-any-return]
```

`data.py:212-219`, `audit`:

```python
    def audit(self, limit: int = 50) -> list[AuditEntry]:
        """Return the permission audit log."""
        if self._client is not None:
            try:
                return self._client.permissions_audit(limit=limit)  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("audit() fallback: %s", exc)
        return placeholder_audit_log()  # type: ignore[no-any-return]
```

Note `except Exception` — not `except GatewayError` as the docstring claims — so an
auth failure, a JSON decode error and a `TypeError` in the client all land in the same
silent fallback. And `log.debug`: **at the default log level, a dead gateway leaves no
visible trace at all.** (Compare **BB-71** in `docs/bug-bank.md`: a router fallback
swallowed at DEBUG level is already on the bug-bank for exactly this.)

### 3.4 What the fiction actually looks like — `src/hachi/client/gaps.py:202-219`

```python
def placeholder_approvals() -> list[Approval]:
    """Return representative pending approval rows."""
    return [
        Approval(
            id="req-001",
            icon="file",
            request="write_file",
            why="Need to save analysis results",
            action="write_file → ~/Documents/report.md",
            op="write",
            policy="asks first",
            touches=("~/Documents/report.md",),
            risk="medium",
            scope="write",
            expires_at=0,
            total_ms=0,
        ),
    ]
```

A user whose gateway just died sees a **medium-risk pending write to their Documents
folder**, with a working Allow button. Pressing it calls
`decide_approval("req-001", …)`, which will 404 against any real gateway.

### 3.5 The honest outlier — cite this as the in-repo precedent — `data.py:188-206`

```python
    def decide_approval(
        self, request_id: str, action: str, rationale: str = ""
    ) -> dict[str, object]:
        """Decide on an approval request.

        *action* must be one of: 'allow', 'deny', 'always'.
        Returns the raw API response dict, or {} on error.
        """
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.decide_approval(
                    request_id, action, rationale=rationale
                )
                return result
            except Exception as exc:
                log.debug(
                    "decide_approval(%r, %r) error: %s", request_id, action, exc
                )
        return {}
```

Same shape, but it returns **`{}`** — an honest empty — rather than inventing a
successful response. The file already knows the right answer for mutations; it just
never applied it to reads. Four other methods follow the honest form:
`set_capability` (`:314-326`), `add_fact` (`:412-425`), `delete_fact` (`:427-…`),
`switch_model` (`:445-…`), `change_tier` (`:461-…`), `authoring_apply` (`:481-…`),
`authoring_revert` (`:491-…`).

### 3.6 The views already have an empty state — `src/hachi/tui/cockpit/views/approvals.py:40`

```python
_EMPTY_TEXT = "✓ no approvals waiting — Hachi is resting"
```

So a view already distinguishes "empty" from "populated". A DEGRADED state is a
**third** case — "we do not know" — and must not be rendered as the reassuring empty
one.

### 3.7 The 12 views — `src/hachi/tui/cockpit/views/`

`agents.py`, `approvals.py`, `audit.py`, `chat.py`, `connections.py`, `dashboard.py`,
`governance.py`, `memory.py`, `resources.py`, `settings.py`, `skills.py`, `tasks.py`
(plus the shared `table.py`).

## 4. Reproduce the failure

Fully reproducible from a shell with a stub client — no gateway needed.

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run python -c "
from unittest.mock import MagicMock
from hachi.tui.cockpit.data import CockpitData

client = MagicMock()
client.list_approvals.side_effect = ConnectionError('gateway is down')
client.get_spend.side_effect = ConnectionError('gateway is down')

data = CockpitData(client)
print('approvals:', data.approvals())
print('spend    :', data.spend())
"
```

**You will see now:** a fabricated pending approval (`id='req-001'`, *write_file →
~/Documents/report.md*) and a fabricated spend snapshot — from a client that raised
`ConnectionError` on **every** call. No warning is printed, because the only trace is
`log.debug`.

**You should see after the fix:** empty collections, `data.degraded_reasons()`
(or equivalent) reporting `approvals` and `spend` as unavailable, and a WARNING in the
log.

**Manual confirmation:** run `hachi run` with no gateway process and page through the
Approvals / Resources / Audit views. Today they render as a healthy, populated cockpit.

## 5. What "fixed" looks like

> ### DECISION REQUIRED — how to carry the degraded signal
>
> **(a) Record the state on the facade; return an honest empty — RECOMMENDED.**
> Add `self._degraded: dict[str, str] = {}` to `CockpitData.__init__` and one helper:
>
> ```python
> def _degrade(self, key: str, exc: Exception) -> None:
>     """Record that a live call failed so views can render DEGRADED, not fiction."""
>     self._degraded[key] = str(exc)
>     log.warning("cockpit: %s unavailable — %s", key, exc)
>
> def degraded(self, key: str) -> str | None:
>     """Return the failure reason for *key*, or None when the last read was good."""
>     return self._degraded.get(key)
> ```
>
> Each of the 25 `except` blocks becomes two lines (`self._degrade("approvals", exc)`
> then `return []`), and views opt in one at a time by checking `data.degraded("…")`
> before rendering their empty state.
> *For:* return types are unchanged, so **no view is forced to change on day one** and
> `mypy` stays quiet; the 25 edits are genuinely mechanical; existing offline tests
> (§12) keep passing untouched. *Against:* the state is side-channel rather than in the
> return value, so a view that forgets to check silently shows an empty list — which is
> still strictly better than showing fiction.
>
> **(b) Change every return type to a `Result`/tuple.**
> *For:* impossible to ignore — the compiler forces every view to handle it.
> *Against:* 25 signature changes **plus** every call site in 12 view modules, in one
> commit, with almost no test coverage on the views. That is a rewrite, not a fix.
>
> **(c) Let the methods raise and catch in the views.**
> *For:* simplest to reason about. *Against:* directly inverts the file's stated
> contract, and a Textual view that raises during `compose()` takes the whole app down.
>
> **Recommendation: (a).** Introduce the state **once**, apply it mechanically to all
> 25 sites, and wire the views that show governance data first (`approvals`, `audit`,
> `resources`/spend, `dashboard`) — the rest can follow.

Target state:

1. `CockpitData.__init__` gains `self._degraded: dict[str, str] = {}` plus `_degrade` /
   `degraded` per §5(a). A successful call **clears** the key (otherwise a recovered
   gateway stays permanently degraded).
2. **`client is None` behaviour is unchanged.** Placeholders remain the deliberate
   offline mode. This is what keeps the existing test suite green (§12) and it is a
   real, wanted mode — do not delete it.
3. **`client is not None` and the call raised** → record the reason, log at **WARNING**,
   and return an honest empty (`[]`, `{}`, or the type's neutral value). **Never a
   placeholder.**
4. Views that render governance data check `degraded(...)` and show an explicit
   unavailable state rather than the reassuring empty text — e.g. in
   `views/approvals.py`, alongside `_EMPTY_TEXT` (`:40`):

   ```python
   _DEGRADED_TEXT = "⚠ can't reach Hachi — approvals unknown, not empty"
   ```

5. The module docstring (`data.py:6`) is rewritten to state the new contract:
   *methods never raise; on a failed live call they return empty and record a degraded
   reason; placeholders are used only in offline mode (`client is None`).*
6. `except Exception` stays (a Textual view must not crash), but the log level moves
   from `debug` to `warning` at all 25 sites.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add `_degraded`, `_degrade()` and `degraded()` to `CockpitData` (`data.py:89-90`).
3. Update the module docstring (`data.py:1-7`).
4. Apply the mechanical change to all 25 fallback sites. Work top to bottom so you can
   count: `skills:103`, `memory:116`, `recall:125`, `og:138`, `authoring_targets:151`,
   `authoring_source:160`, `spend:173`, `approvals:186`, `audit:219`,
   `active_tasks:232`, `failed_tasks:241`, `routines:254`, `agents:267`,
   `activity:285`, `tool_calls:299`, `capabilities:312`, `mcp:335`, `sessions:348`,
   `config:361`, `models:370`, `setup:379`, `health:388`, `trust_bar:558`/`:579`,
   `dashboard:588`/`:604`. **Re-confirm each with Read — do not trust this list blind.**
5. Clear the key on the success path of each method (one line before the `return`).
6. Wire the DEGRADED render into the four governance-facing views first:
   `views/approvals.py`, `views/audit.py`, `views/resources.py`, `views/dashboard.py`.
7. Run the full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_cockpit_degraded.py` (**new** — do not bolt this onto
  `TestCockpitDataOffline` in `tests/test_cockpit_foundation.py:173`, which asserts the
  opposite contract for the *offline* case and must keep doing so)
- **Test names:**
  `test_failed_live_call_returns_empty_not_placeholder`,
  `test_failed_live_call_records_a_degraded_reason`,
  `test_offline_mode_still_returns_placeholders`,
  `test_recovered_call_clears_the_degraded_flag`
- **It must assert:** the real, observed return value from a client that raises — that
  `approvals()` returns `[]` and **not** a list containing `id="req-001"`. Assert on the
  fabricated id specifically; asserting `len(...) == 0` alone would pass against a
  future placeholder that happens to be empty.
- **It must FAIL before your fix** with:
  `AssertionError: assert [Approval(id='req-001', …)] == []`

```python
# sketch — adapt to the repo's existing fixtures
from unittest.mock import MagicMock

import pytest

from hachi.tui.cockpit.data import CockpitData


def _broken_client() -> MagicMock:
    client = MagicMock()
    client.list_approvals.side_effect = ConnectionError("gateway is down")
    client.permissions_audit.side_effect = ConnectionError("gateway is down")
    return client


def test_failed_live_call_returns_empty_not_placeholder() -> None:
    """A dead gateway must never render as a healthy cockpit full of fake approvals.

    Regression: every read method converted an exception into placeholder_*() data,
    so an unreachable gateway showed a fabricated medium-risk pending write to
    ~/Documents/report.md with a working Allow button.
    """
    data = CockpitData(_broken_client())

    assert data.approvals() == []
    assert data.audit() == []
    # The specific fiction must be gone, not merely a different length.
    assert all(getattr(a, "id", None) != "req-001" for a in data.approvals())


def test_failed_live_call_records_a_degraded_reason(caplog: pytest.LogCaptureFixture) -> None:
    data = CockpitData(_broken_client())
    data.approvals()

    assert data.degraded("approvals") is not None
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_offline_mode_still_returns_placeholders() -> None:
    """client=None is a deliberate offline mode, not a failure — keep it working."""
    data = CockpitData(None)
    assert len(data.approvals()) > 0


def test_recovered_call_clears_the_degraded_flag() -> None:
    client = MagicMock()
    client.list_approvals.side_effect = ConnectionError("down")
    data = CockpitData(client)
    data.approvals()
    assert data.degraded("approvals") is not None

    client.list_approvals.side_effect = None
    client.list_approvals.return_value = []
    data.approvals()
    assert data.degraded("approvals") is None
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Likely cause: you passed `CockpitData(None)` instead of a client that raises — that is
> the offline path, which is supposed to return placeholders.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and `test_failed_live_call_returns_empty_not_placeholder` failed before the fix with the `req-001` placeholder present.
- [ ] **All 25** `return placeholder_*` sites are unreachable when `self._client is not None` — verify by grep and by reading, not by memory.
- [ ] `rg -n "log.debug" src/hachi/tui/cockpit/data.py` returns **nothing** (all fallback logs are WARNING).
- [ ] `CockpitData(None)` behaviour is byte-identical to today — `tests/test_cockpit_foundation.py::TestCockpitDataOffline` passes **unmodified**.
- [ ] A recovered gateway clears the degraded flag.
- [ ] At least the four governance views render an explicit unavailable state, distinct from their empty state.
- [ ] The module docstring states the new contract.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not delete `hachi/client/gaps.py` or the `placeholder_*` functions.** They are
  the offline mode and they are pinned by `tests/test_client_gaps.py` and
  `tests/test_cockpit_gaps.py`. This task narrows *where* they are used, not *whether*
  they exist.
- **Do not change `CockpitData(None)` behaviour.** The pull to "make it honest
  everywhere" is strong and it is wrong: `client is None` means the operator chose
  offline, and 40+ existing assertions depend on it.
- **Do not add a reconnect / retry loop.** Detecting degradation and recovering from it
  are different tasks; a poll loop inside a data facade is a new concurrency surface.
- **Do not redesign the 12 views.** Add one degraded branch beside the existing empty
  branch. Layout work is not this task.
- **Do not fix the same pattern in the web store.** `frontend/` fixtures are
  [T-22](T-22-web-fixtures-out-of-prod-bundle.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — A dead gateway rendered as a healthy TUI cockpit full of fabricated governance data

- **Symptom:** With the gateway down or unreachable, `hachi run` showed a fully populated cockpit: a pending medium-risk approval to write `~/Documents/report.md` (with a working Allow button that would 404), a spend figure, and an audit log — none of it real. Nothing on screen indicated a problem, and the only trace was a `log.debug` line invisible at the default level.
- **Root cause:** `CockpitData` (`src/hachi/tui/cockpit/data.py`) documented and implemented "methods NEVER raise — they always return real or placeholder data". All 25 read methods wrapped the client call in `except Exception: log.debug(...)` and fell through to `placeholder_*()` from `hachi.client.gaps`, so a *failed live call* was indistinguishable from *deliberate offline mode*. `decide_approval` was the lone honest method — it returned `{}` on error.
- **Fix:** Split the two cases. `client is None` (deliberate offline) still returns placeholders. `client is not None` and the call raised now records a reason via `_degrade(key, exc)`, logs at WARNING, and returns an honest empty; a later success clears the flag. Views check `data.degraded(key)` and render an explicit unavailable state distinct from their empty state.
- **Avoid:** a fallback must distinguish "no data" from "could not fetch". Never let a caught exception return the same value as a successful empty result — and never log a swallowed failure at DEBUG (see BB-71).
- **Locked by:** `tests/test_cockpit_degraded.py` — `test_failed_live_call_returns_empty_not_placeholder`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **Two existing tests pin the OFFLINE contract and must stay untouched.**
  `tests/test_cockpit_foundation.py:173-180` (`TestCockpitDataOffline`, fixture
  `CockpitData(None)`) asserts "every method returns non-empty data in offline mode and
  must never raise", and `:296-320` (`test_no_method_raises`) walks every public method
  reflectively on `CockpitData(None)`. **Both only exercise `client is None`** — so if
  you scope the change to the `client is not None` failure path, they pass unmodified.
  **If either goes red, you have changed the offline path** — revert and re-read §5.2.
  This is the single most important scoping check in the task.
- **`tests/test_cockpit_gaps.py:273-287`** also builds `CockpitData(None)`. Same rule.
- **Clear the flag on success**, or the first transient blip leaves the cockpit
  permanently marked degraded and the state becomes as untrustworthy as the fiction it
  replaced.
- **Two methods degrade twice.** `trust_bar` (`data.py:550-579`) and `dashboard`
  (`:581-604`) each have **two** placeholder returns — an early guard and an exception
  handler. Both need handling; a naive "one edit per method" pass misses 2 of the 25.
- **`mcp()` returns a tuple** (`data.py:328-335`:
  `return placeholder_mcp_servers(), placeholder_mcp_tools()`). Its honest empty is
  `([], [])`, not `[]`.
- **`authoring_source()` already returns an honest-ish fallback** (`data.py:153-160`:
  `("# offline — no source available\n", [])`) rather than a placeholder. Keep the
  string, add the degraded record.
- **`config()`, `setup()`, `health()`, `memory()`, `spend()`, `trust_bar()`,
  `dashboard()` return model objects, not lists.** Their "honest empty" needs a
  deliberate choice per type — a default-constructed model is fine, but do **not**
  reuse the placeholder constructor with the values blanked; grep the model definition
  in `src/hachi/client/models.py` and construct it explicitly.
- **`mypy` gate:** many of these methods carry `# type: ignore[no-any-return]`. Returning
  `[]` instead of the placeholder may make some of those ignores unnecessary, and
  `--warn-unused-ignores` (if on for this file) will then fail. Check whether
  `src/hachi/tui/cockpit/data.py` is in the blocking mypy set before assuming.
