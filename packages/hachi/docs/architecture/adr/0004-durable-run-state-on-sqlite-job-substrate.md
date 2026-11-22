# ADR-0004 — Durable agent run-state on the existing SQLite job substrate

- **Status:** Proposed (Gate B)
- **Date:** 2026-06-21
- **Related:** [16](../16-durable-execution.md); depends on ADR-0003

## Context

There is no durable agent run-state; a restart loses in-flight runs. `core_suspend_workflow`
is a verified no-op that lies about persistence (`workflow_tools.py:15-21`). Meanwhile a durable
`SQLiteJobQueue` + `JobRegistry` already exists but is unwired — every production job is
`func=`-only and is deliberately failed on restart (`queue.py:617-626`). The durable Scheduler
and the approval-wait registry already model "park → external resolve → wake".

## Decision

Build the agent runtime on the substrate already present rather than adopting an external engine:
add a `RunState` record + `RunStateStore` (a SQLite table reusing `SessionStore`'s WAL/backup/
migration patterns), generalize `PendingApprovalRegistry` into a durable `WaitConditionRegistry`
(USER/EVENT/TIME now; WEBHOOK/TOOL as seams), and **activate `JobRegistry`** so resumes and
reactive handlers run as named, restart-surviving jobs. Replace `core_suspend_workflow` with a
real suspend (persist `RunState=WAITING` + `WaitCondition`) and **turn-granular resume** — on wake,
replay the durable transcript into a *fresh turn* with the wait result injected (reusing
session-resume, `orchestrator.py:477`), rather than reconstructing fragile mid-loop state; until
resume is fully wired, the tool **fails honestly** instead of lying.

## Alternatives considered

1. **External workflow engine (Temporal/Restate/Airflow).** Rejected — heavyweight external
   dependency and operational surface for a single-node single-user app; the in-house job queue +
   session store already provide the primitives. Revisit only at multi-node scale.
2. **Keep `core_suspend_workflow`, add persistence later.** Rejected — it actively misinforms the
   model and shipped skills depend on it; the dishonesty must be removed now (fail-honest), not
   deferred.
3. **Persist full conversation in `RunState.payload`.** Rejected — the transcript is already
   durable in `SessionStore`; `payload` carries only minimal continuation context to avoid
   duplication and drift.
4. **Mid-iteration resume (re-enter the loop at a saved cursor).** Rejected at Gate C (amendment
   A2) — a turn's live state is more than a cursor (history, partial tool calls, in-flight
   reasoning); reconstructing it exactly is fragile and a double-execution hazard. Turn-granular
   resume (replay → fresh turn) reuses proven machinery and is idempotent.

## Consequences

**Positive:** in-flight runs survive restart; `wait_for_user`/`wait_for_event`/`wait_until`
become real and resumable; the dishonest suspend is eliminated; the dormant durable-job path is
finally used (also fixing background-job loss); one shared migration helper lands (debt D9).
**Negative:** a new core subsystem and a `runs` table; `func=`→`handler=` job conversion must be
regression-tested; resume re-entrancy needs idempotent wakes; single-threaded worker remains a
throughput limit (documented, deferred). **Reversibility:** medium — the runtime is additive and
the loop is unchanged when nothing suspends, but adoption by skills makes removal costly.
