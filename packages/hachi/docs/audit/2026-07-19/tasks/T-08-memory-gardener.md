# T-08 · MemoryGardener: wire it up or delete the dead surface

|  |  |
|---|---|
| **Source finding** | CF-1 #5 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **corrected by** [CORRECTIONS.md](CORRECTIONS.md) §10 |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) — its gardener assertion depends on which option you pick |
| **Effort** | Option A ~2–3 days · Option B ~2 hours |
| **Difficulty** | High (needs design judgement — read §5 first) |
| **Files you will touch** | depends on the decision — see §5 |

---

## 1. Brief

`MemoryGardener` — the M3 nightly dedupe/supersede/expire pass over `memory/*.og` — has
**zero production instantiations**. Its writer (`run()`) is never called, so
`pending_diffs.json` is never written; its reader
(`AgentSession.snapshot_gardener_diffs`) has **zero callers**; and even if you called
the reader it would return `[]` unconditionally, because it reads `memory_dir` off an
object that has no such attribute. Three dead layers, one feature.

**This task requires a decision** (§5): wire the gardener up end-to-end, or delete the
dead surface and the docstrings that promise it. Either is acceptable to the audit gate —
*"gardener schedule exists **or** the surface is removed"* — but shipping the current
state is not.

## 2. Why this matters

Memory hygiene is a real product need: without it, `memory/*.og` accumulates duplicate
and stale nodes forever, which degrades recall quality over time — the exact failure a
long-lived personal agent must not have. But an unreachable implementation delivers zero
of that value while costing full maintenance, and its docstrings actively mislead the
next reader ("the user can approve via the TUI Memory-Diff screen" — there is no such
screen).

CF-1's thesis is that this repo ships features without an end-to-end activation check.
The gardener is the purest example: 260 lines of correct, tested logic that nothing
calls. Whichever option you pick, the outcome must be that **the state of this feature is
honest** — either it runs and is visible, or it is gone.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Zero production instantiations

```
$ grep -rn "MemoryGardener" src/
src/hachi/core/memory_gardener.py:190:class MemoryGardener:
src/hachi/core/memory_gardener.py:248:            "MemoryGardener: auto_applied=%d pending=%d",
src/hachi/core/memory_gardener.py:347:            logger.debug("MemoryGardener._apply_dedup failed", exc_info=True)
```

Three hits: the class statement and two of its own log strings. **Every construction site
in the repo is in `tests/test_p3_02_memory_gardener.py`** (`:138`, `:158`, `:177`,
`:193`, `:214`, `:230`).

### 3.2 The writer has no production caller

`src/hachi/core/memory_gardener.py:218-252` — `run()`:

```python
    def run(self, *, auto_apply: bool = True) -> GardeningResult:
        """Run a full gardening pass.

        Returns:
            GardeningResult with auto_applied and pending_review lists.
            Also writes pending_diffs.json to the memory dir for the TUI.
        """
        ...
        # 3. Persist pending diffs for TUI
        diffs_path = self._memory_dir / self._PENDING_DIFFS_FILE
        result.save(diffs_path)
```

`_PENDING_DIFFS_FILE = "pending_diffs.json"` (`:204`). Nothing calls `run()`, so
`pending_diffs.json` is never created.

### 3.3 The reader has no callers — and is broken anyway

`src/hachi/gateway/orchestrator.py:745-760` — `AgentSession.snapshot_gardener_diffs`:

```python
    def snapshot_gardener_diffs(self) -> list[dict]:
        """Return pending memory-diff proposals from the last gardener run.

        Reads the pending_diffs.json file written by MemoryGardener.run().
        Returns an empty list if the file is missing or unreadable.
        """
        from hachi.core.memory_gardener import GardeningResult

        memory_dir = getattr(self.memory, "memory_dir", None)
        if memory_dir is None:
            return []
        diffs_path = memory_dir / GardeningResult._PENDING_DIFFS_FILE
        result = GardeningResult.load(diffs_path)
        from dataclasses import asdict

        return [asdict(p) for p in result.pending_review]
```

Two independent defects:

1. **No callers.** `grep -rn "snapshot_gardener_diffs" src/` returns only this
   definition. There is no gateway route, no TUI screen, no CLI command. The review's
   *"the UI's Memory-Diff surface"* overstates it — **there is no UI surface**
   ([CORRECTIONS.md](CORRECTIONS.md) §10).
2. **`self.memory` has no `memory_dir`.** `self.memory` is a `MemoryManager`
   (`orchestrator.py:535` assigns it; `AgentSession.__init__` takes it as `memory`), and
   `grep -c "memory_dir" src/hachi/core/memory.py` returns **0**. So the `getattr`
   default fires on every call and the method returns `[]` before touching the file. This
   is exactly the `getattr`-masks-absent-wiring pattern that
   [T-14](T-14-ban-getattr-own-types.md) bans.

The real path is `get_hachi_paths().memory_dir` (`src/hachi/core/paths.py:76-78`,
`data_dir / "memory"`), which is what `MemoryIndex`/`MemoryWriter` already use
(`shared_services.py:317-325`).

### 3.4 The promised UI does not exist

`src/hachi/core/memory_gardener.py:7-10`:

```python
Controversial proposals (near-duplicate content, contradiction detection, expiry) are
returned as ``pending_review`` items that the user can approve via the TUI Memory-Diff
screen.
```

```
$ grep -rin "memory-diff\|memory_diff\|memorydiff" src/ frontend/src/
src/hachi/core/memory_gardener.py:9:   ...TUI Memory-Diff
src/hachi/gateway/orchestrator.py:746: ...memory-diff proposals
```

Only the two docstrings. `src/hachi/tui/cockpit/views/` contains `memory.py` but no diff
view; the web frontend has no memory-diff route.

### 3.5 What DOES work (the tested, correct part)

`tests/test_p3_02_memory_gardener.py` is green and covers `run()`, `save()`/`load()`,
dedupe, similarity, and expiry. `GardeningResult.save`/`load`
(`memory_gardener.py:60-87`) are a clean JSON round-trip. The logic is not the problem.

## 4. Reproduce the failure

**Not reproducible from a shell** — a feature that is never invoked produces no output,
no error, and no file. The proof is by absence, and each grep below is copy-pasteable:

```bash
# 1. No production instantiation (only the class stmt + its own log strings):
grep -rn "MemoryGardener" src/

# 2. The reader has no callers anywhere:
grep -rn "snapshot_gardener_diffs" src/ frontend/src/

# 3. MemoryManager has no memory_dir, so the reader's getattr always defaults to None:
grep -c "memory_dir" src/hachi/core/memory.py      # -> 0

# 4. No Memory-Diff surface in either UI:
grep -rin "memory-diff\|memory_diff" src/ frontend/src/
```

**You will see now:** hits only inside `memory_gardener.py` itself and the one orphan
method in `orchestrator.py`; `0` for the third command.
**You should see after the fix:** under **Option A**, a scheduler registration, a route,
and a frontend consumer; under **Option B**, no hits at all outside the deleted-module
history.

## 5. What "fixed" looks like

> ## DECISION REQUIRED
>
> Pick **A** or **B** before writing any code, and record the choice in
> `docs/DECISIONS.md`. Do not start Option A and stop halfway — a half-wired gardener is
> the state you are being asked to eliminate.

### Option A — wire it up (three pieces, not one)

The review implies one missing call site. It is three, and they are independent:

| Piece | What it needs | Effort |
|---|---|---|
| **A1 — schedule** | A resident daemon that calls `MemoryGardener(get_hachi_paths().memory_dir).run()` on an interval, gated by a new opt-in `[memory_gardener]` settings section. | ~0.5 day |
| **A2 — route** | A gateway route (e.g. `GET /memory/diffs`) + control-plane handler + `_InProcessGatewayRuntime` method, so `snapshot_gardener_diffs` is reachable. | ~0.5 day |
| **A3 — surface** | A frontend screen (or TUI view) that lists `pending_review` proposals and lets the user approve/reject — **plus the approve/reject write-back path, which does not exist at all today** (`GardeningProposal` has no accept/reject action; `run()` only auto-applies `DEDUP_SAME_NAME`). | ~1–2 days |

**A1** has an exact precedent to copy verbatim: `_start_eval_report_scheduler`
(`src/hachi/gateway/orchestrator.py:2272-2324`) — daemon thread, sleep loop,
`min(interval, 3600)` wake cap, try/except that logs, started from `boot_agent` behind an
opt-in settings flag. Mirror it, including the `[eval_reports]`-style
`EvalReportSettings` model — and register the new section on `ResolvedConfig`, or you
reproduce **[T-07](T-07-eval-reports-config-section.md)** exactly.

**A2** must fix the broken reader while it is there: replace
`getattr(self.memory, "memory_dir", None)` with `get_hachi_paths().memory_dir`. **BB-4
applies** — a new route means regenerating the OpenAPI spec and the frontend API types.

**A3 is where the cost is**, and it is the piece the review does not account for. Approval
UI is not a list view: it needs a decision endpoint, a write-back that respects the
gardener's append-only governance rule (`memory_gardener.py:3-4`), and audit visibility.

**Total honest estimate: 2–3 days**, and it lands a new user-facing surface in a
gate-blocking wave.

### Option B — delete the dead surface

1. Delete `AgentSession.snapshot_gardener_diffs` (`orchestrator.py:745-760`) — it has no
   callers and cannot work.
2. Delete `src/hachi/core/memory_gardener.py` and `tests/test_p3_02_memory_gardener.py`.
3. Remove the "TUI Memory-Diff screen" claim wherever it survives.
4. Record in `docs/DECISIONS.md`: *M3 memory gardening is deferred; the implementation was
   removed rather than left dark. Recoverable from git at `bd24afe`.*

**Cost:** ~2 hours. **Risk:** you delete working, tested logic that a future memory-hygiene
task would want. Git makes that recoverable, and CLAUDE.md Rule 3's "never delete
functionality unless told" is satisfied because this task *is* the instruction — but only
if you take Option B deliberately, not by drift.

### Recommendation — **Option B**, with one amendment

Take Option B for the *wiring and the surface*, but **keep `src/hachi/core/memory_gardener.py`
and its tests**, and add one honest line to its module docstring:

```python
STATUS: not wired. This module has no production caller. The M3 nightly schedule and
the review UI were never built — see docs/DECISIONS.md. Do not describe the "TUI
Memory-Diff screen"; it does not exist.
```

Rationale:

- The gate's requirement is *"gardener schedule exists **or the surface is removed**"*.
  Deleting `snapshot_gardener_diffs` satisfies it, at ~30 minutes.
- Option A's real cost is A3, which is a **new product surface** — that does not belong in
  a P0/P1 wave whose purpose is making already-shipped promises true. Adding a screen is
  not making an existing promise true; it is a new promise.
- Keeping the algorithm costs nothing (it is ~260 self-contained lines with green tests)
  and preserves the option value that pure deletion destroys. The *lie* is the orphan
  reader and the docstring, and both are cheap to remove.
- [T-13](T-13-feature-liveness-smoke.md)'s gardener assertion then becomes trivial and
  permanent: **assert no production module imports `memory_gardener`** — so if someone
  wires it up later, they are forced to wire it up *completely* or fail the smoke.

If the product owner wants memory hygiene in v1, that is Option A and it needs its own
task with A1/A2/A3 as separate specs. Say so; do not smuggle it in here.

## 6. Steps

**Get the decision in writing before step 1.** These steps assume the recommended
Option B.

1. Write the regression test from §7 first. Run it. Watch it fail.
2. Delete `AgentSession.snapshot_gardener_diffs` (`orchestrator.py:745-760`). Confirm
   with `grep -rn "snapshot_gardener_diffs" src/ tests/ frontend/src/` that nothing
   referenced it.
3. Replace the misleading paragraph in `src/hachi/core/memory_gardener.py:7-10` with the
   STATUS block from §5.
4. Add a `docs/DECISIONS.md` entry recording the choice and its rationale.
5. Run the test. Watch it pass.
6. Run `uv run python scripts/preflight.py`. Report real counts — `vulture` (advisory)
   will now flag `MemoryGardener` as unreferenced; that is correct and expected. Say so
   in the PR.
7. Add the bug-bank entry (§11).

If you took **Option A** instead, the steps are: register the `[memory_gardener]` section
on `ResolvedConfig` → add `_start_memory_gardener` mirroring
`_start_eval_report_scheduler` → fix the reader's `memory_dir` resolution → add the route
+ control-plane handler → regenerate OpenAPI + FE types (BB-4) → build the screen. Each
gets its own failing test first.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_memory_gardener_wiring.py` (new)
- **Test name (Option B):** `test_memory_gardener_has_no_half_wired_surface`
- **It must assert:** the *real, observed* import graph and attribute set — that no
  module under `src/hachi/` outside `core/memory_gardener.py` imports the module, and
  that `AgentSession` no longer exposes a `snapshot_gardener_diffs` attribute.
- **It must FAIL before your fix** with:
  `AssertionError: AgentSession still exposes snapshot_gardener_diffs, which has no callers and cannot work`

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "hachi"


def test_memory_gardener_has_no_half_wired_surface() -> None:
    """M3 gardening is deferred: the algorithm may stay, the dead surface may not.

    If you wire the gardener up, this test SHOULD fail — replace it with a test that
    asserts the schedule runs and the route returns proposals (see T-08 Option A).
    """
    from hachi.gateway.orchestrator import AgentSession

    assert not hasattr(AgentSession, "snapshot_gardener_diffs"), (
        "AgentSession still exposes snapshot_gardener_diffs, which has no callers "
        "and cannot work (MemoryManager has no memory_dir attribute)"
    )

    importers = [
        p for p in SRC.rglob("*.py")
        if p.name != "memory_gardener.py" and "memory_gardener" in p.read_text(encoding="utf-8")
    ]
    assert not importers, (
        "memory_gardener is referenced by production code but has no schedule and no "
        f"surface — wire it fully (T-08 Option A) or remove the reference: {importers}"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

**Option A's test instead:** boot a session with `[memory_gardener] enabled = true`,
assert the daemon thread exists by name (mirror how you would check
`"hachi-eval-report"` from `orchestrator.py:2318`), write two duplicate-named nodes into
a `tmp_path` memory dir, force a tick, and assert `pending_diffs.json` exists and the
route returns its `pending_review` contents. Assert on the **file and the HTTP response**,
never on a mock.

## 8. Acceptance criteria

- [ ] The decision (A or B) is recorded in `docs/DECISIONS.md` with its rationale.
- [ ] The regression test from §7 exists, and failed before the fix.
- [ ] **Option B:** `grep -rn "snapshot_gardener_diffs" src/ frontend/src/` returns
      nothing; the "TUI Memory-Diff screen" claim appears nowhere in the repo.
- [ ] **Option A:** a gardener run is observable — `pending_diffs.json` is written on a
      tick, the route returns its contents, and the schedule start is logged at INFO
      (mirroring `orchestrator.py:2320-2324`).
- [ ] No `getattr(x, "field", None)` against a Hachi-owned type survives in whatever code
      you keep (see [T-14](T-14-ban-getattr-own-types.md)).
- [ ] **The failure is loud next time.** Option B: `docs/DECISIONS.md` records the deferral
      and the module's docstring carries the `STATUS: not wired` block, so a future reader
      cannot mistake it for a live feature — and §7's test fails the moment production
      code references it again. Option A: `GardeningResult.load`'s
      `except Exception: logger.debug` (`memory_gardener.py:85-87`) becomes a
      `logger.warning(..., exc_info=True)`, and the schedule start is logged at INFO.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not "just add the call to `run()`" and stop.** That is the drift this task exists
  to prevent: it makes the writer live while the reader is still broken and unreachable,
  producing a `pending_diffs.json` no one ever sees — a *fourth* dead layer. If you
  choose Option A, all three pieces land or none do.
- **Do not build the approve/reject write-back** without a decision. It mutates the
  user's memory files; the gardener's append-only governance rule
  (`memory_gardener.py:3-4`) constrains how, and that design is not in this spec.
- **Do not "fix" `snapshot_gardener_diffs` by changing the `getattr` to
  `get_hachi_paths().memory_dir` and leaving it callerless.** A working method nobody
  calls is still a dead feature; you would just have made it harder to notice.
- **Do not touch `MemoryIndex` / `MemoryWriter` / `graph_recall`.** They are live
  (`shared_services.py:309-331`) and unrelated to the gardener.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). Deleting
  `tests/test_p3_02_memory_gardener.py` is only permissible under a deliberate Option B
  that also deletes the module; the recommendation keeps both.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
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
### BB-N — MemoryGardener shipped with a writer, a reader, and no connection between them

- **Symptom:** M3 memory gardening (dedupe / supersede / expire over `memory/*.og`)
  never ran. `pending_diffs.json` was never written, and the "TUI Memory-Diff screen"
  named in the module docstring did not exist in either UI.
- **Root cause:** three independent dead layers. (1) `MemoryGardener.run()` — the only
  writer — had zero production callers; every construction site was in tests. (2)
  `AgentSession.snapshot_gardener_diffs` — the only reader — also had zero callers: no
  gateway route, no TUI screen, no CLI command. (3) Even when called, that reader did
  `getattr(self.memory, "memory_dir", None)` against a `MemoryManager`, which has no
  `memory_dir` attribute — so it returned `[]` before touching the file. The correct
  path is `get_hachi_paths().memory_dir`.
- **Fix:** <record what you actually did — Option A (schedule + route + surface) or
  Option B (removed the dead surface, kept the algorithm with a STATUS docstring)>, plus
  a `docs/DECISIONS.md` entry.
- **Avoid:** a `getattr(self.x, "field", None)` against one of our OWN types is not
  defensive coding — it converts "this attribute does not exist" into a silent empty
  result. Before shipping a read-model method, grep for its caller; a snapshot method
  with no caller is a dead feature, not a future-proofing.
- **Locked by:** `tests/test_memory_gardener_wiring.py` —
  `test_memory_gardener_has_no_half_wired_surface`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-4:** Option A adds a gateway route ⇒ regenerate the OpenAPI spec **and** the
  frontend API types, or CI fails.
- **BB-5:** `paths.workspace_dir` does not exist — the gardener's directory is
  `get_hachi_paths().memory_dir` (`core/paths.py:76-78`).
- `vulture` (advisory step in `scripts/preflight.py`) will start flagging `MemoryGardener`
  under Option B. That is a true positive by design — call it out in the PR rather than
  suppressing it.
- `MemoryGardener.run()` **writes to the filesystem** and appends `::changelog` entries to
  real `.og` files (`memory_gardener.py:175-182`, `:237`). Any test that calls it must use
  a `tmp_path` memory dir. `get_hachi_paths()` (`core/paths.py:117-124`) has **no env
  override**, so patch it.
- `GardeningResult.load` swallows every exception into an empty result
  (`memory_gardener.py:85-87`) — under Option A that swallow must become a
  `logger.warning`, or you have rebuilt the same class of bug one layer down.
