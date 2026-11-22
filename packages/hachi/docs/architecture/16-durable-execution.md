# 16 — Durable Execution & Agent Runtime

> Phase 2 / Gate B. Initiative **D**. Contract + one impl + seam. Seams are `file:line`.
> Related: ADR-0004. **This is the highest correctness-risk initiative** (Gate-A R1/R2).

## 1. Problem

Turn execution is a synchronous loop (`loop.py:574`) with no persisted run state; outcomes are
magic strings (`[CANCELLED]`, `[WORKFLOW SUSPENDED]`, …). A restart loses every in-flight run.
**`core_suspend_workflow` is a verified no-op** that *tells the model* its state is saved and it
will auto-wake (`workflow_tools.py:15-21`) — it saves nothing and never resumes; shipped skills
depend on it. The durable `JobRegistry` path exists but is unwired (`queue.py:617-626`).

## 2. Contract — run state, waits, runtime

```python
# core/runtime/state.py
class RunStatus(StrEnum):
    PENDING="pending"; RUNNING="running"; WAITING="waiting"; BLOCKED="blocked"
    COMPLETED="completed"; FAILED="failed"; CANCELLED="cancelled"

class WaitKind(StrEnum):
    USER="user"; EVENT="event"; WEBHOOK="webhook"; TOOL="tool"; TIME="time"

class WaitCondition(BaseModel):
    kind: WaitKind
    key: str                      # event pattern / approval id / webhook token / iso-time
    created_at: str
    timeout_at: str | None = None

class RunState(BaseModel):
    run_id: str
    session_id: str
    status: RunStatus
    wait: WaitCondition | None = None
    resume_cursor: int            # turn index to resume AT (NOT a mid-loop pointer — see §3)
    payload: dict                 # minimal continuation context (NOT full history — that's in SessionStore)
    updated_at: str

# core/runtime/store.py
class RunStateStore:              # SQLite, reuses SessionStore WAL/backup/migration patterns
    def upsert(self, run: RunState) -> None: ...
    def get(self, run_id: str) -> RunState | None: ...
    def waiting(self) -> list[RunState]: ...           # for restart recovery
    def by_session(self, session_id: str) -> list[RunState]: ...

# core/runtime/waits.py — generalizes PendingApprovalRegistry (approvals.py:121)
class WaitConditionRegistry:
    def arm(self, run_id: str, wait: WaitCondition) -> None: ...
    def resolve(self, key: str, result: dict) -> str | None: ...   # returns run_id to wake
```

The magic-string outcomes map onto `RunStatus` (e.g. `[CANCELLED]`→CANCELLED,
`[BUDGET LIMIT REACHED]`→FAILED, suspend→WAITING), giving a real state machine without
rewriting the loop body.

## 3. Replace `core_suspend_workflow` (the R2 fix)

```
suspend_workflow(reason, wait):              # agent calls this mid-turn
   1. raise SuspendWorkflow → the loop catches it and ENDS THE CURRENT TURN cleanly
   2. persist RunState(status=WAITING, wait=wait, resume_cursor=<turn index>,
                       payload=<wait-result injection context>)   via RunStateStore
   3. WaitConditionRegistry.arm(run_id, wait); emit `run.suspended`
resume(run_id, result):                      # wake fires a `resume_run` JobContext handler (see §4)
   1. load the session; replay its durable transcript into a FRESH MemoryManager
      (reuse session-resume, orchestrator.py:477) — no mid-loop state to reconstruct
   2. inject the wait result as new context ("the event you awaited occurred: {result}")
   3. start a NEW turn; RunState→RUNNING; on finish→COMPLETED
```

This design is **turn-granular** (Gate-C amendment A2): suspend ends the turn; resume **replays the
durable transcript into a fresh turn** with the wait result injected, reusing proven session-resume
machinery (`orchestrator.py:477`). There is no fragile mid-iteration checkpoint to reconstruct, and a
fresh turn is idempotent — eliminating the double-execution risk. Until resume is wired end-to-end,
`core_suspend_workflow` **fails honestly** ("suspend/resume not yet enabled") rather than lying; the
dishonest description is removed immediately and the real mechanism lands incrementally.

## 4. Wait conditions & wake sources

| WaitKind | Wake source | Status |
|---|---|---|
| `USER` | approval `resolve()` (generalized `approvals.py:159`) | **build** (exists in shipped skills) |
| `EVENT` | `EventBus.subscribe(pattern)` → `WaitConditionRegistry.resolve` ([12](12-event-architecture.md)) | **build** (exists in shipped skills) |
| `TIME` | `Scheduler` tick (`jobs/scheduler.py`, already durable) | **build** (cheap; scheduler exists) |
| `WEBHOOK` | `POST /channels/{c}/inbound` / a new `/runs/{id}/wake` route | seam |
| `TOOL` | async tool completion event | seam |

Only the three that real skills use (USER, EVENT, TIME) are built now; WEBHOOK/TOOL are seams on the
same `WaitCondition` mechanism. **Timeout enforcement (Gate-C amendment A4):** the durable
`Scheduler` (`jobs/scheduler.py`, already ticking) sweeps `WAITING` runs past `wait.timeout_at` and
wakes them with a timeout result (or fails them) — a never-firing event cannot hang a run forever.

## 5. Activate the durable job substrate (the R6 fix)

Turn on the built-but-unwired path (`queue.py:473`):

```python
# boot: one JobRegistry, named handlers, passed to BOTH workers (orchestrator.py:425, 2100)
registry = JobRegistry()
registry.register("extract_fact", handle_extract_fact)        # was func= (memory.py:174)
registry.register("generate_title", handle_generate_title)    # was func= (orchestrator.py:1068)
registry.register("resume_run", handle_resume_run)            # NEW — durable resume
registry.register("react", handle_reactive_subscriber)        # NEW — async bus dispatch
JobWorker(queue, registry=registry)
```

Production jobs convert from `func=` to `handler_name=`+`payload=`, so they survive restart
instead of being discarded (`queue.py:617-626`). Reactive subscribers (C) and run resumes (D)
become durable handler jobs.

**Handlers receive a `JobContext` (Gate-C amendment A3).** Today's `func=` jobs close over live
services (compaction closes over the `MemoryManager` + LLM client, `memory.py:851`); a serializable
`handler_name`+`payload` job has none of that. So handlers are invoked with a `JobContext`
service-locator (session lookup, vault, router, memory) and rebuild what they need from
`{session_id, …}`. Without this, the conversion would silently break background memory writes — it
is a required part of the work, not an afterthought.

**Worker concurrency (Gate-C amendment A9).** Memory writes, titles, reactive handlers, and resumes
now share the single worker (`queue.py:336`). For single-node/single-user the volume is low, so one
worker is acceptable; worker count is made **configurable (default 1)** and resume/wake jobs get a
priority lane — the documented seam to add throughput later. A pool is not built now (§4a).

## 6. Restart recovery

On boot: `RunStateStore.waiting()` → re-arm each `WaitCondition` (re-subscribe EVENT waits to
the bus, re-register TIME waits with the scheduler, restore USER approvals); `RUNNING` runs
left by a crash are either resumed (if a cursor exists) or marked `FAILED` with a clear reason.
The daemon already restarts the *process* (`daemon.py:234`); this makes the *work* survive too.

## 7. What it touches

| File | Change |
|---|---|
| `core/runtime/*` (new) | `RunState`, `RunStateStore`, `WaitConditionRegistry`, `AgentRuntime` |
| `core/runtime/store.py` + `core/migrations.py` (new) | `runs` table via shared `apply_migrations` (fixes debt D9) |
| `tools/workflow_tools.py:15` | replace the no-op; honest-fail then real suspend |
| `core/loop.py:574,919` | resume-from-cursor; map outcomes → `RunStatus` |
| `core/approvals.py:121` | generalize to `WaitConditionRegistry` (USER kind keeps current behavior) |
| `jobs/queue.py:473` | wire `JobRegistry`; convert func jobs to handler jobs |
| `gateway/orchestrator.py:425,2100` | pass `JobRegistry` to workers; recovery on boot |
| `gateway/fastapi_app.py` | `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/wake` (typed `response_model`) |

## 8. What could break (and the guard)

- **Shipped "pause-until-X" skills change from silently-dying to actually-working** (a
  correctness *improvement*, but a behavior change). *Guard:* E2E test per skill kind — an
  EVENT-wait skill suspends, the event fires, the run resumes and completes; a regression test
  asserts the dishonest description is gone.
- **`func=`→`handler=` conversion** could regress background memory/title writes. *Guard:* the
  existing tests for those paths plus a new "job survives simulated restart" test (the exact
  gap `queue.py:617` describes).
- **Resume re-entrancy** (double-execution if a wake fires twice). *Guard:* `WaitCondition`
  resolution is idempotent (single-use key, mirrors `allow_once` semantics); resume is guarded
  by `RunStatus` transition (only WAITING→RUNNING).

## 9. Deferred (seam only, per §4a)

Distributed/multi-worker execution, saga/compensation, `wait_for_file`, arbitrary
`wait_for_tool` beyond the seam, sub-second scheduling. The `WaitCondition` + `JobRegistry`
substrate accommodates each later without touching the loop.
