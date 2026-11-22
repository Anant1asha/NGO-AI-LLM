# T-46 · Move `AgentSession`'s 20 read-model methods behind a `SessionReadModels` facade

|  |  |
|---|---|
| **Source finding** | CF-6 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | Medium |
| **Files you will touch** | `src/hachi/gateway/session_read_models.py` (new), `src/hachi/gateway/orchestrator.py`, `tests/test_session_read_models.py` (new) |

---

## 1. Brief

`AgentSession` is 1,448 lines and 51 methods, of which **20 are UI read models** —
`snapshot_*` / `query_*` accessors that exist only to feed the TUI and web UI. They have
nothing to do with running a turn. Move them behind a `SessionReadModels` facade so the turn
engine and the UI projection stop sharing a class.

⚠️ **`RuntimeReadModelStore` already exists and cannot absorb all 20.** Read §3.3 before you
size this work — the naive assumption ("delegate everything to the store") is what blows the
estimate.

## 2. Why this matters

CF-6's diagnosis is that `AgentSession` is a god class: it couples the turn engine to UI
read models, live MCP admin, schedule control, and job pipelines. The read models are the
largest single coherent chunk of that and the easiest to lift, because they are **pure
reads** — no read model mutates session state.

The payoff is specific: today, changing a UI projection means editing the class that runs the
agent loop, and every read model has implicit access to every private field of the turn
engine. After the facade, a UI change touches a file the loop does not import.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The class

`src/hachi/gateway/orchestrator.py:507-1954` — `class AgentSession`, **1,448 lines**,
**51 methods** (verified: `awk 'NR>=507 && NR<=1954' … | grep -cE "^    (async )?def "` → 51).

### 3.2 The 20 read models — the complete list

**CF-6 says "~25". It is exactly 20: 16 `snapshot_*` and 4 `query_*`.**

**16 `snapshot_*`:**

| Method | Line | Body lines | Source |
|---|---|---|---|
| `snapshot_session_state` | 690 | 13 | store **+** live |
| `snapshot_usage` | 705 | 6 | live |
| `snapshot_task_ledger` | 714 | 10 | live |
| `snapshot_skills` | 726 | 16 | live (skill engine) |
| `snapshot_gardener_diffs` | 745 | 12 | live (file read) — **dead, see §3.5** |
| `snapshot_og_explorer` | 762 | 12 | live (skill engine) |
| `snapshot_permission_audit` | 840 | 2 | **store** |
| `snapshot_schedules` | 844 | 4 | live (scheduler) |
| `snapshot_mcp_inventory` | 913 | 18 | live (MCP manager) |
| `snapshot_active_jobs` | 1024 | 2 | **store** |
| `snapshot_failed_jobs` | 1028 | 2 | **store** |
| `snapshot_tool_calls` | 1061 | 2 | **store** |
| `snapshot_runtime_events` | 1065 | 2 | **store** |
| `snapshot_events_since` | 1069 | 4 | **store** |
| `snapshot_memory_facts` | 1075 | **60 — the largest** | live (memory manager) |
| `snapshot_og_graph` | 1144 | 10 | live (skill engine) |

**4 `query_*`:**

| Method | Line | Body lines | Source |
|---|---|---|---|
| `query_recent_sessions` | 805 | 4 | live (session store) |
| `query_session_messages` | 811 | 6 | live (session store) |
| `query_memory_recall` | 825 | 13 | live (memory manager) |
| `query_subagent_reports` | 1032 | 25 | store **+** live |

Regenerate the classification:

```bash
python -c "
import re
lines=open('src/hachi/gateway/orchestrator.py',encoding='utf-8').read().split('\n')
seg=lines[506:1954]
alldef=[i for i,l in enumerate(seg) if re.match(r'^    def ',l)]
for i,l in enumerate(seg):
    m=re.match(r'^    def (snapshot_\w+|query_\w+)',l)
    if not m: continue
    end=next((j for j in alldef if j>i), len(seg))
    body=seg[i+1:end]
    print(f'{i+507:5d}  {m.group(1):32s} body={len([b for b in body if b.strip()]):3d}  store={\"self._read_models.\" in \" \".join(body)}')
"
```

### 3.3 ⚠️ CRITICAL SIZING INSIGHT — the store cannot absorb these

`RuntimeReadModelStore` already exists: **`src/hachi/core/runtime_read_models.py:220-450`**,
an event-sourced projection store with 11 methods, fed exclusively by `append_event`
(`:240`), carrying a monotonic sequence counter (`:236-238`) and **14 frozen snapshot
dataclasses** (all `@dataclass(frozen=True, slots=True)`, `:29-145`).

Its public surface: `append_event`, `boot_ready` (`:402`), `active_jobs` (`:406`),
`permission_audit` (`:410`), `subagent_reports` (`:414`), `failed_jobs` (`:418`),
`runtime_events` (`:422`), `read_events_since` (`:426`), `activity` (`:442`),
`tool_calls` (`:447`).

**The store is purely event-derived.** Everything in it arrived through `append_event`.

Measured against the 20 read models:

| | Count | Methods |
|---|---:|---|
| **Already delegation-shaped** (2-line bodies straight into the store) | **5** | `snapshot_permission_audit` 840, `snapshot_active_jobs` 1024, `snapshot_failed_jobs` 1028, `snapshot_tool_calls` 1061, `snapshot_runtime_events` 1065 (+ `snapshot_events_since` 1069 at 4 lines ≈ a 6th) |
| **Hybrid** — touch the store *and* compute | **2** | `snapshot_session_state` 690, `query_subagent_reports` 1032 |
| **Purely live** — compute from subsystems the store has never seen | **12** | `snapshot_usage`, `snapshot_task_ledger`, `snapshot_skills`, `snapshot_gardener_diffs`, `snapshot_og_explorer`, `snapshot_schedules`, `snapshot_mcp_inventory`, `snapshot_memory_facts`, `snapshot_og_graph`, `query_recent_sessions`, `query_session_messages`, `query_memory_recall` |

**Only ~6 of the 20 are already one-line delegations.** The other ~14 read live from the skill
engine, MCP manager, memory manager, scheduler, and session store — **and have no home in the
store, because the store is event-derived and those subsystems emit no events carrying this
data.**

**Two options; the decision is made for you in §5:**

- **(a) The facade wraps BOTH the store and the live subsystems.** ~14 methods move verbatim,
  carrying their subsystem references as facade constructor arguments. Contained, mechanical,
  one week.
- **(b) Extend the store to accept non-event projections.** Requires new ingestion paths for
  five subsystems, breaks the store's single-writer `append_event` invariant, and invalidates
  the sequence-counter contract that SSE paging depends on. Multi-week, and it damages a
  currently-sound design.

**(a) is the smaller change and is what this task specifies. Do NOT assume the store can
absorb all 20** — that assumption is the difference between one week and three.

### 3.4 The turn engine and the read models share private state

Before moving anything, enumerate what each read model touches. They reach into
`self._read_models`, `self.skill_engine`, `self.mcp_manager`, `self.memory`, `self.vault`,
`self._scheduler`, `self._session_store`, `self.loop`, and more. Every one of those becomes a
facade constructor argument or a facade-held back-reference.

```bash
# For each read model, list the self.<attr> it reads.
awk 'NR>=690 && NR<=1160' src/hachi/gateway/orchestrator.py \
  | grep -oE "self\.[_a-z][_a-z0-9]*" | sort | uniq -c | sort -rn
```

### 3.5 `snapshot_gardener_diffs` is dead — coordinate with T-08

`orchestrator.py:745` has **zero callers anywhere in the source tree**:

```bash
grep -rn "gardener_diffs" --include="*.py" --include="*.ts" --include="*.tsx" src/ tests/ frontend/src
# → src/hachi/gateway/orchestrator.py:745    (the definition, and nothing else)
```

(Stale `.pyc` files match it, including one for `src/hachi/tui/app.py` — a module that no
longer exists. Ignore `__pycache__`.)

It reads a file that is never written, and there is no gateway route, TUI screen, or CLI
command behind it. **[T-08](T-08-memory-gardener.md) owns the decision** — wire it up or
delete it. If T-08 deletes it first, this list drops to **19**. Check T-08's status before
you start and do not resolve it yourself.

### 3.6 Relationship to [T-44](T-44-boot-agent-staged-builders.md)

**Disjoint line ranges — technically safe to parallelize.** T-44 restructures
`boot_agent` (`:2557-3694`); this task moves `AgentSession` methods (`:690-1160`). Neither
reads the other's lines.

**But it is the same file**, and `gateway/orchestrator.py` is touched by eleven tasks. Running
both concurrently invites continuous merge friction across a 2-week task. Prefer to serialize;
if you must parallelize, rebase daily and keep this task's commits small.

## 4. Reproduce the failure — there is none. Read the code instead.

**This is a pure refactor. Every read model works.** There is no crash and no wrong output.
Do not invent a repro. Here is how to see the problem:

```bash
# 1. The class size and method count.
awk 'NR>=507 && NR<=1954' src/hachi/gateway/orchestrator.py | wc -l          # 1448
awk 'NR>=507 && NR<=1954' src/hachi/gateway/orchestrator.py | grep -cE "^    (async )?def "   # 51

# 2. 20 of those 51 are UI read models — 39% of the god class.
awk 'NR>=507 && NR<=1954' src/hachi/gateway/orchestrator.py | grep -cE "^    def (snapshot_|query_)"

# 3. A store already exists — and only ~6 read models use it.
sed -n '220,250p' src/hachi/core/runtime_read_models.py
grep -c "self._read_models\." src/hachi/gateway/orchestrator.py

# 4. The god-class coupling: read models reach into the turn engine's privates.
awk 'NR>=690 && NR<=1160' src/hachi/gateway/orchestrator.py \
  | grep -oE "self\.[_a-z][_a-z0-9]*" | sort -u
```

**You will see now:** step 4 lists turn-engine internals being read by UI projections in the
same class.
**You should see after the fix:** `grep -cE "^    def (snapshot_|query_)" ` on the
`AgentSession` range → 0 (or 20 thin forwarders, if you keep back-compat per §5 decision 4);
`src/hachi/gateway/session_read_models.py` holds them; `AgentSession` is ~51−20 = 31 methods.

## 5. What "fixed" looks like

A facade that wraps **both** the event-sourced store and the live subsystems.

```python
# src/hachi/gateway/session_read_models.py (new)
"""UI read models for a live session.

Wraps BOTH the event-sourced RuntimeReadModelStore and the live subsystems
(skill engine, MCP manager, memory manager, scheduler, session store).

The store is purely event-derived — it cannot answer questions about live
subsystem state, so this facade is the join point, not the store. See T-46 §3.3.
"""

from __future__ import annotations

from typing import Any

from hachi.core.runtime_read_models import (
    JobSnapshot,
    PermissionAuditSnapshot,
    RuntimeReadModelStore,
    ...
)


class SessionReadModels:
    def __init__(
        self,
        *,
        store: RuntimeReadModelStore,
        skill_engine: Any,
        mcp_manager: Any,
        memory: Any,
        scheduler: Any = None,
        session_store: Any = None,
        loop: Any = None,
    ) -> None:
        self._store = store
        self._skill_engine = skill_engine
        ...

    # --- store-derived (thin) ---------------------------------------
    def active_jobs(self) -> tuple[JobSnapshot, ...]:
        return self._store.active_jobs()

    # --- live (moved verbatim from AgentSession) ---------------------
    def memory_facts(self) -> dict:
        ...   # the 60 lines from orchestrator.py:1075, unchanged
```

**Decisions already made — do not re-litigate:**

1. **Option (a) from §3.3.** The facade wraps the store *and* the live subsystems. Do not
   extend `RuntimeReadModelStore` to ingest non-event data; it would break its single-writer
   invariant and the sequence contract SSE paging depends on.
2. **`RuntimeReadModelStore` is not modified at all** in this task. Zero diff on
   `core/runtime_read_models.py`.
3. **Facade lives in `hachi.gateway`**, not `hachi.core`. It reads live gateway-layer
   subsystems; putting it in `core` would create a layering violation the import-linter
   will (correctly) reject.
4. **`AgentSession` keeps all 20 methods as one-line forwarders** to the facade, at least
   initially:
   ```python
   def snapshot_memory_facts(self) -> dict:
       return self._read_model_facade.memory_facts()
   ```
   Deleting them outright would break `_InProcessGatewayRuntime` and both UIs in the same
   diff. Removing the forwarders is a separate follow-up once callers are re-pointed.
   **This means `AgentSession` does not shrink by 20 methods in this task — it shrinks by
   ~1,100 lines of body.** State that honestly in the PR; do not claim a method-count win.
5. **Drop the `snapshot_` / `query_` prefixes on the facade.** `facade.memory_facts()` reads
   better than `facade.snapshot_memory_facts()`, and the forwarder preserves the old name.
   The `snapshot`/`query` split is not a real distinction — both are pure reads.
6. **`snapshot_gardener_diffs` is moved as-is** unless [T-08](T-08-memory-gardener.md) has
   already deleted it. Do not decide its fate here (§3.5).
7. **Zero behaviour change.** Same return types, same ordering, same limits, same defaults.

## 6. Steps

**Five commits, thinnest-first.**

### Commit 1 — characterization tests (no source change)

1. Write the tests from §7 against today's behaviour. They must pass.
2. Record full-suite baseline counts.

### Commit 2 — the facade, wired but empty

3. Create `src/hachi/gateway/session_read_models.py` with `SessionReadModels.__init__` and
   no read methods.
4. Construct it in `AgentSession.__init__` and hold it as `self._read_model_facade`. Nothing
   uses it yet. Full suite green.

### Commit 3 — move the 6 store-derived methods

5. Move `snapshot_permission_audit` (840), `snapshot_active_jobs` (1024),
   `snapshot_failed_jobs` (1028), `snapshot_tool_calls` (1061), `snapshot_runtime_events`
   (1065), `snapshot_events_since` (1069). Each is a 2–4 line body.
6. Replace each `AgentSession` body with a forwarder.
7. Full suite.

### Commit 4 — move the 12 live methods

8. Move them in subsystem batches so each batch has one obvious set of constructor args:
   - **skill engine:** `snapshot_skills` 726, `snapshot_og_explorer` 762, `snapshot_og_graph` 1144
   - **memory:** `snapshot_memory_facts` 1075 (60 lines — its own commit if you prefer),
     `query_memory_recall` 825
   - **session store:** `query_recent_sessions` 805, `query_session_messages` 811
   - **MCP:** `snapshot_mcp_inventory` 913
   - **scheduler:** `snapshot_schedules` 844
   - **loop/misc:** `snapshot_usage` 705, `snapshot_task_ledger` 714,
     `snapshot_gardener_diffs` 745
9. **Move verbatim.** For each, the only edits are `self.X` → `self._X` (the facade's own
   attribute name). Do not restructure a 60-line method while relocating it.
10. Full suite after each batch.

### Commit 5 — move the 2 hybrids

11. `snapshot_session_state` (690) and `query_subagent_reports` (1032) read the store **and**
    compute. They move last because they exercise both halves of the facade and are the best
    proof it is correctly wired.
12. Full suite; counts must match the commit-1 baseline.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law), applied to a
refactor.** There is no bug, so the instrument is a **characterization test**: pin the exact
output of all 20 read models *before* the move, so the relocation is provably
behaviour-neutral.

- **File:** `tests/test_session_read_models.py` (new)
- **Test names:** `test_every_read_model_returns_the_same_shape_after_the_move`,
  `test_store_derived_read_models_reflect_appended_events`,
  `test_live_read_models_reflect_subsystem_state`
- **They must assert:** real observed return values from a real session against real
  subsystems — not a mock's return value. Where a subsystem must be faked, fake the
  *subsystem*, then assert the read model reports what the fake actually holds.
- **They PASS before the refactor and must still pass after.** That is what characterization
  means, and it is the correct application of Rule 2 here.

```python
# sketch — adapt to the repo's existing fixtures
READ_MODELS = (
    "snapshot_session_state", "snapshot_usage", "snapshot_task_ledger",
    "snapshot_skills", "snapshot_gardener_diffs", "snapshot_og_explorer",
    "snapshot_permission_audit", "snapshot_schedules", "snapshot_mcp_inventory",
    "snapshot_active_jobs", "snapshot_failed_jobs", "snapshot_tool_calls",
    "snapshot_runtime_events", "snapshot_events_since", "snapshot_memory_facts",
    "snapshot_og_graph", "query_recent_sessions", "query_session_messages",
    "query_memory_recall", "query_subagent_reports",
)


def test_every_read_model_returns_the_same_shape_after_the_move(booted_session) -> None:
    """All 20 read models stay callable and keep their return TYPE.

    Cheap, broad net: catches a dropped method or a return-type change
    across the whole surface in one assertion.
    """
    assert len(READ_MODELS) == 20
    for name in READ_MODELS:
        method = getattr(booted_session, name, None)
        assert callable(method), f"read model disappeared: {name}"
        result = method()
        assert isinstance(result, (tuple, list, dict)), f"{name} changed return type: {type(result)}"


def test_store_derived_read_models_reflect_appended_events(booted_session) -> None:
    """The 6 store-derived models must still read the SAME store instance.

    Guards the most likely wiring mistake: the facade constructing its own
    RuntimeReadModelStore instead of receiving the session's.
    """
    from hachi.core.runtime_read_models import RuntimeEvent

    before = len(booted_session.snapshot_runtime_events(limit=1000))
    booted_session._read_models.append_event(
        RuntimeEvent(name="t46.probe", payload={"k": "v"}, timestamp="2026-07-19T00:00:00Z")
    )
    after = booted_session.snapshot_runtime_events(limit=1000)
    assert len(after) == before + 1
    assert any(e.name == "t46.probe" for e in after)


def test_live_read_models_reflect_subsystem_state(booted_session) -> None:
    """The 12 live models must read the SESSION's subsystems, not fresh ones."""
    skills = booted_session.snapshot_skills()
    assert len(skills) == len(booted_session.skill_engine.list_skills())   # adapt to real API
```

> `test_store_derived_read_models_reflect_appended_events` is the highest-value test here: a
> facade that constructs its own store instead of receiving the session's would pass every
> shape check and silently return empty projections forever. That is exactly the CF-1
> "dead feature reports success" failure mode this repo is trying to eliminate.

## 8. Acceptance criteria

- [ ] The characterization tests from §7 exist and passed before the move.
- [ ] `src/hachi/gateway/session_read_models.py` exists and holds all 20 read-model bodies
      (19 if [T-08](T-08-memory-gardener.md) deleted `snapshot_gardener_diffs` first).
- [ ] `git diff --stat src/hachi/core/runtime_read_models.py` → **no change** (§5 decision 2).
- [ ] `AgentSession` retains 20 one-line forwarders; the ~1,100 lines of read-model *body* are
      gone from `orchestrator.py`. **Report the line delta, not a method-count delta**
      (§5 decision 4).
- [ ] The facade receives the session's `RuntimeReadModelStore` instance — it does not
      construct one. Verified by `test_store_derived_read_models_reflect_appended_events`.
- [ ] `uv run lint-imports` green — the facade is in `hachi.gateway`, not `hachi.core`.
- [ ] Five commits, each green on its own.
- [ ] Full-suite counts identical to the commit-1 baseline. Report both.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change behaviour while moving code.** Primary boundary. Same return types, same
  ordering, same `limit` defaults, same empty-case handling. `snapshot_memory_facts` is 60
  lines — move it, do not rewrite it.
- **Do not extend `RuntimeReadModelStore`** to ingest non-event data (§3.3, §5 decision 1).
  This is the specific way this task turns into a three-week task.
- Do not delete the `AgentSession` forwarders in this task (§5 decision 4).
- Do not decide the fate of `snapshot_gardener_diffs` — that is
  [T-08](T-08-memory-gardener.md) (§3.5).
- Do not move the other 31 `AgentSession` methods. Live MCP admin, schedule control, and job
  pipelines are also god-class symptoms, and they are also not this task.
- Do not "fix" the `getattr`/`except Exception` guards inside the moved bodies. CF-1 tracks
  those; changing failure behaviour inside a relocation is unreviewable.
- Do not run this concurrently with [T-44](T-44-boot-agent-staged-builders.md) unless you
  accept daily rebases (§3.6).
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- **Do not run a repo-wide `ruff format`** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop, after EVERY batch
uv run python scripts/preflight.py           # before you call it done
uv run lint-imports
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — an event-sourced read-model store cannot absorb live-computed projections

- **Symptom:** `AgentSession` carried 20 UI read models. `RuntimeReadModelStore` already
  existed, so "delegate them all to the store" looked like a one-week job. Only ~6 were
  actually store-backed; 12 computed live from the skill engine, MCP manager, memory manager,
  scheduler, and session store, and 2 were hybrids.
- **Root cause:** `RuntimeReadModelStore` is fed exclusively by `append_event` and carries a
  monotonic sequence counter that SSE paging depends on. Live subsystem state never passes
  through it, so there is no event to project from.
- **Fix:** Introduced `SessionReadModels`, a facade wrapping the store **and** the live
  subsystems, rather than extending the store.
- **Avoid:** Before routing read models into an event-sourced store, count how many are
  actually event-derived. Adding non-event ingestion breaks the store's single-writer
  invariant and its sequence contract.
- **Locked by:** `tests/test_session_read_models.py` —
  `test_store_derived_read_models_reflect_appended_events`
```

## 12. Known traps

- **The absorption trap (§3.3).** Assuming the store can take all 20. The single biggest
  estimation risk in this task.
- **The fresh-store trap.** A facade that constructs its own `RuntimeReadModelStore` instead
  of receiving the session's returns empty projections forever, silently, with every shape
  test green. Covered by `test_store_derived_read_models_reflect_appended_events` — do not
  skip that test.
- **The dead-method trap (§3.5).** `snapshot_gardener_diffs` has zero callers. Moving it is
  fine; "fixing" it is [T-08](T-08-memory-gardener.md)'s job.
- **Layering.** The facade must live in `hachi.gateway`. Putting it in `hachi.core` trips the
  frozen-seam contract at `pyproject.toml:213+`.
- **Same-file concurrency.** `gateway/orchestrator.py` is touched by eleven tasks.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. `snapshot_memory_facts` and
  `query_memory_recall` touch the memory stack — a live hazard here.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Several read models
  `getattr` around this; preserve those calls verbatim.
