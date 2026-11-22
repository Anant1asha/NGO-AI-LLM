// ============================================================
// Hachi Web App — Work domain loader
// Wires jobs + schedules to the real gateway.
//
// Endpoints:
//   GET /jobs/active       → Job[]          → Run[]
//   GET /jobs/failed?limit=20 → JobFailure[]  → FailedTask[]
//   GET /schedules         → { schedules: Schedule[] } → Routine[]
//   GET /runs              → { runs: RunStateView[] }  → Run[] / FailedTask[]
//   GET /runs/{run_id}     → RunStateView
//   POST /runs/{run_id}/wake
//   DELETE /runs/{run_id}
//   PUT /schedules/{id}/enabled body { enabled }
//   DELETE /schedules/{id}
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { useStore } from "../../store/store";
import type { Run, FailedTask, FinishedTask, Routine } from "../types";

// ---- Gateway shapes (mirror Python dataclasses / dict exactly) ----

interface GatewayJob {
  job_id: string;
  kind: string;
  label: string;
  status: string;
}

interface GatewayJobFailure {
  job_id: string;
  kind: string;
  label: string;
  attempt: number;
  error: string;
  duration_seconds: number;
  timestamp: string;
}

interface GatewaySchedule {
  schedule_id: string;
  name: string;
  task: string;
  kind: "interval" | "cron";
  interval_seconds?: number | null;
  cron?: string | null;
  timezone: string;
  condition_skill?: string | null;
  enabled: boolean;
  created_at: string;
  last_run?: string | null;
  next_run?: string | null;
}

interface GatewaySchedulesResponse {
  schedules: GatewaySchedule[];
}

interface GatewayRunStateView {
  run_id: string;
  session_id: string;
  status: "pending" | "running" | "waiting" | "blocked" | "completed" | "failed" | "cancelled" | string;
  wait_kind?: string | null;
  wait_key?: string | null;
  wait_timeout_at?: string | null;
  resume_cursor?: number;
  updated_at: string;
}

interface GatewayRunsResponse {
  runs: GatewayRunStateView[];
}

// ---- Stable numeric-id mapper ----
// Maps string gateway ids → stable numeric React keys.
// The string id is preserved on the UI object in a side field so mutations
// can resolve it back without keeping a separate Map in module scope.

const _idCounter = (() => {
  let n = 5000; // start above fixture range to avoid collisions
  const map = new Map<string, number>();
  return (strId: string): number => {
    let existing = map.get(strId);
    if (existing === undefined) {
      existing = ++n;
      map.set(strId, existing);
    }
    return existing;
  };
})();

// Parallel map from numeric UI id → string gateway schedule_id for mutations.
const _scheduleIdMap = new Map<number, string>();
const _durableRunIdMap = new Map<number, string>();

// ---- Pure adapters ----

function adaptJob(raw: GatewayJob): Run {
  const numId = _idCounter(raw.job_id);
  // Map gateway status to UI status
  const statusMap: Record<string, Run["status"]> = {
    running: "working",
    active: "working",
    waiting: "on-watch",
    blocked: "blocked",
    done: "done",
  };
  const status: Run["status"] = statusMap[raw.status] ?? "on-watch";

  return {
    id: numId,
    title: raw.label || raw.kind || raw.job_id,
    status,
    progress: status === "working" ? 0.5 : status === "done" ? 1.0 : 0,
    spent: 0,
    budget: 1.0,
    meta: raw.kind,
    when: "running",
  };
}

function adaptJobFailure(raw: GatewayJobFailure): FailedTask {
  const numId = _idCounter(raw.job_id);
  const when = raw.timestamp
    ? new Date(raw.timestamp).toLocaleTimeString("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "unknown";

  return {
    id: numId,
    title: raw.label || raw.kind || raw.job_id,
    status: "blocked",
    when,
    cost: 0,
    error: raw.error ?? "Unknown error",
    owner: raw.kind ?? undefined,
  };
}

function humanizeSchedule(raw: GatewaySchedule): string {
  if (raw.kind === "cron" && raw.cron) {
    // Simple humanization for common cron patterns
    const parts = raw.cron.split(" ");
    if (parts.length >= 5) {
      const [min, hour, dom, month, dow] = parts;
      if (dom === "*" && month === "*") {
        const dayStr =
          dow === "*"
            ? "every day"
            : dow === "1-5"
            ? "weekdays"
            : dow === "1,2,3,4,5"
            ? "weekdays"
            : `day ${dow}`;
        const timeStr = hour !== "*" && min !== "*" ? ` at ${hour.padStart(2, "0")}:${min.padStart(2, "0")}` : "";
        return `${dayStr}${timeStr}`;
      }
    }
    return raw.cron;
  }
  if (raw.kind === "interval" && raw.interval_seconds != null) {
    const secs = raw.interval_seconds;
    if (secs < 60) return `every ${secs}s`;
    if (secs < 3600) return `every ${Math.round(secs / 60)}m`;
    if (secs < 86400) return `every ${Math.round(secs / 3600)}h`;
    return `every ${Math.round(secs / 86400)}d`;
  }
  return "scheduled";
}

function humanizeNextRun(nextRun: string | null | undefined): string {
  if (!nextRun) return "—";
  try {
    const d = new Date(nextRun);
    const now = Date.now();
    const diff = d.getTime() - now;
    if (diff < 0) return "overdue";
    if (diff < 60000) return "< 1 min";
    if (diff < 3600000) return `in ${Math.round(diff / 60000)} min`;
    if (diff < 86400000) return `in ${Math.round(diff / 3600000)}h`;
    return d.toLocaleDateString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    return nextRun;
  }
}

function humanizeLastRun(lastRun: string | null | undefined): string | undefined {
  if (!lastRun) return undefined;
  try {
    const d = new Date(lastRun);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.round(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.round(diff / 3600000)}h ago`;
    return d.toLocaleDateString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    return undefined;
  }
}

function adaptSchedule(raw: GatewaySchedule): Routine {
  const numId = _idCounter(raw.schedule_id);
  _scheduleIdMap.set(numId, raw.schedule_id);

  return {
    id: numId,
    title: raw.name || raw.task || raw.schedule_id,
    schedule: humanizeSchedule(raw),
    next: humanizeNextRun(raw.next_run),
    last: humanizeLastRun(raw.last_run),
    cost: 0,
    paused: !raw.enabled,
  };
}

function adaptDurableRun(raw: GatewayRunStateView): Run | null {
  const numId = _idCounter(raw.run_id);
  _durableRunIdMap.set(numId, raw.run_id);

  const statusMap: Record<string, Run["status"]> = {
    pending: "on-watch",
    running: "working",
    waiting: "blocked",
    blocked: "blocked",
    completed: "done",
  };

  const uiStatus = statusMap[raw.status];
  if (!uiStatus) return null;

  let when = "durable";
  try {
    when = new Date(raw.updated_at).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    when = raw.updated_at;
  }

  return {
    id: numId,
    title: `Run ${raw.run_id.slice(0, 8)}`,
    status: uiStatus,
    progress: uiStatus === "done" ? 1 : uiStatus === "working" ? 0.5 : 0,
    spent: 0,
    budget: 1.0,
    meta: `durable/${raw.status}`,
    owner: raw.wait_kind ?? "runtime",
    when,
  };
}

function adaptDurableFailure(raw: GatewayRunStateView): FailedTask | null {
  if (raw.status !== "failed" && raw.status !== "cancelled") return null;
  const numId = _idCounter(raw.run_id);
  _durableRunIdMap.set(numId, raw.run_id);

  let when = "unknown";
  try {
    when = new Date(raw.updated_at).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    when = raw.updated_at;
  }

  return {
    id: numId,
    title: `Run ${raw.run_id.slice(0, 8)}`,
    status: raw.status,
    when,
    cost: 0,
    error: raw.status === "cancelled" ? "Run cancelled" : "Durable run failed",
    owner: raw.wait_kind ?? "runtime",
    waitingOn: raw.wait_key ?? undefined,
  };
}

/** Adapt a completed durable run to the FinishedTask shape for the History tab. */
function adaptDurableFinished(raw: GatewayRunStateView): FinishedTask | null {
  if (raw.status !== "completed") return null;
  const numId = _idCounter(raw.run_id);
  _durableRunIdMap.set(numId, raw.run_id);

  let when = "unknown";
  try {
    when = new Date(raw.updated_at).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    when = raw.updated_at;
  }

  return {
    id: numId,
    title: `Run ${raw.run_id.slice(0, 8)}`,
    note: raw.wait_kind ? `resumed via ${raw.wait_kind}` : "durable run",
    when,
    cost: 0,
  };
}

// ---- Loader ----

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, seeded fixtures must NOT be
// shown, so on failure we clear the slice instead of leaving them in place.
let _hasEverSucceeded = false;

export async function loadWork(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const [rawJobs, rawFailed, rawSchedules, rawRuns] = await Promise.all([
      apiGet<GatewayJob[]>("/jobs/active"),
      apiGet<GatewayJobFailure[]>("/jobs/failed", { limit: 20 }),
      apiGet<GatewaySchedulesResponse>("/schedules"),
      apiGet<GatewayRunsResponse>("/runs", { limit: 100 }),
    ]);

    const runs: Run[] = (rawJobs ?? []).map(adaptJob);
    const failed: FailedTask[] = (rawFailed ?? []).map(adaptJobFailure);
    const routines: Routine[] = (rawSchedules?.schedules ?? []).map(adaptSchedule);

    const durableRuns = (rawRuns?.runs ?? []).map(adaptDurableRun).filter((r): r is Run => r !== null);
    const durableFailed =
      (rawRuns?.runs ?? [])
        .map(adaptDurableFailure)
        .filter((r): r is FailedTask => r !== null);
    // Completed durable runs populate the History tab's `finished` slice.
    const durableFinished =
      (rawRuns?.runs ?? [])
        .map(adaptDurableFinished)
        .filter((r): r is FinishedTask => r !== null);

    const seenRunIds = new Set(runs.map((r) => r.id));
    const mergedRuns = runs.concat(durableRuns.filter((r) => !seenRunIds.has(r.id)));
    const seenFailedIds = new Set(failed.map((f) => f.id));
    const mergedFailed = failed.concat(durableFailed.filter((f) => !seenFailedIds.has(f.id)));

    useStore.getState().hydrate({ runs: mergedRuns, failed: mergedFailed, routines, finished: durableFinished });
    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: clear seeded fixtures so we never present
      // fabricated data as if it were real gateway data.
      useStore.getState().hydrate({ runs: [], failed: [], routines: [], finished: [] });
    }
    // Reconnecting flag is now managed centrally by client.ts via the
    // registered callback — no per-domain setReconnecting calls needed here.
  } finally {
    useStore.getState().setLoaded("work");
  }
}

registerLoader("work", loadWork);

// ---- Mutation wrappers ----

/**
 * Toggle a routine's enabled state via PUT /schedules/{id}/enabled.
 * Applies optimistic store update immediately.
 */
export async function pauseRoutineLive(numericId: number): Promise<void> {
  // Optimistic: toggle in store (the store's pauseRoutine does this)
  useStore.getState().pauseRoutine(numericId);
  if (USE_MOCKS) return;

  const scheduleId = _scheduleIdMap.get(numericId);
  if (!scheduleId) return; // fixture or unknown id — store update was enough

  // Read the NEW paused state from store after the optimistic toggle
  const routine = useStore.getState().routines.find((r) => r.id === numericId);
  const enabled = routine ? !routine.paused : true;

  try {
    await apiSend<unknown>("PUT", `/schedules/${scheduleId}/enabled`, { enabled });
  } catch {
    // Revert the optimistic update on failure.
    // Network errors surface the reconnecting banner via client.ts callback.
    useStore.getState().pauseRoutine(numericId);
  }
}

/**
 * Delete a schedule via DELETE /schedules/{id}.
 * Removes from routines store optimistically.
 */
export async function deleteRoutineLive(numericId: number): Promise<void> {
  if (USE_MOCKS) {
    // Optimistic removal for mock mode
    useStore.getState().hydrate({
      routines: useStore.getState().routines.filter((r) => r.id !== numericId),
    });
    return;
  }

  const scheduleId = _scheduleIdMap.get(numericId);

  // Optimistic removal
  const previousRoutines = useStore.getState().routines;
  useStore.getState().hydrate({
    routines: previousRoutines.filter((r) => r.id !== numericId),
  });

  if (!scheduleId) return; // fixture — optimistic removal was enough

  try {
    await apiSend<unknown>("DELETE", `/schedules/${scheduleId}`);
  } catch {
    // Revert on failure.
    // Network errors surface the reconnecting banner via client.ts callback.
    useStore.getState().hydrate({ routines: previousRoutines });
  }
}

/** True when the UI item id corresponds to a durable run from GET /runs. */
export function isDurableRun(numericId: number): boolean {
  return _durableRunIdMap.has(numericId);
}

/**
 * Fetch one durable run by UI numeric id.
 * Returns null when the item is not durable or the request fails.
 */
export async function getDurableRunLive(numericId: number): Promise<GatewayRunStateView | null> {
  if (USE_MOCKS) return null;
  const runId = _durableRunIdMap.get(numericId);
  if (!runId) return null;
  try {
    return await apiGet<GatewayRunStateView>(`/runs/${encodeURIComponent(runId)}`);
  } catch {
    return null;
  }
}

/**
 * Wake a WAITING durable run.
 * Returns true when wake was requested, false when run is non-durable/not-waiting/failed.
 */
export async function wakeDurableRunLive(numericId: number): Promise<boolean> {
  if (USE_MOCKS) return false;
  const runId = _durableRunIdMap.get(numericId);
  if (!runId) return false;

  const current = await getDurableRunLive(numericId);
  if (!current || current.status !== "waiting") return false;

  try {
    await apiSend<{ status: string; run_id: string }>(
      "POST",
      `/runs/${encodeURIComponent(runId)}/wake`,
      { source: "web", result: {} }
    );
    return true;
  } catch {
    return false;
  }
}

/**
 * Cancel a durable run.
 * Returns true when backend accepted the cancel request.
 */
export async function cancelDurableRunLive(numericId: number): Promise<boolean> {
  if (USE_MOCKS) return false;
  const runId = _durableRunIdMap.get(numericId);
  if (!runId) return false;
  try {
    await apiSend<unknown>("DELETE", `/runs/${encodeURIComponent(runId)}`);
    return true;
  } catch {
    return false;
  }
}

/**
 * Force-trigger a routine (schedule) immediately via
 * POST /schedules/{id}/run-now.
 *
 * Applies the store's optimistic action (closes the detail panel + toast)
 * first, exactly like pauseRoutineLive/deleteRoutineLive. When the numeric id
 * doesn't map to a real gateway schedule (mock fixture, or live mode before
 * loadWork() ever populated the map), the optimistic action alone is the
 * whole behaviour — same fallback shape as pauseRoutineLive.
 *
 * Returns true when the gateway confirmed dispatch (`{ok: true}`), false
 * otherwise (fixture id, gateway unavailable, or the gateway rejected it —
 * e.g. no active session). Callers use the return value to show a live vs.
 * generic toast.
 */
export async function runRoutineNowLive(numericId: number): Promise<boolean> {
  useStore.getState().runRoutineNow(numericId);
  if (USE_MOCKS) return false;

  const scheduleId = _scheduleIdMap.get(numericId);
  if (!scheduleId) return false; // fixture or unknown id — optimistic update was enough

  try {
    const result = await apiSend<{ ok: boolean; schedule_id?: string }>(
      "POST",
      `/schedules/${encodeURIComponent(scheduleId)}/run-now`
    );
    return Boolean(result?.ok);
  } catch {
    return false;
  }
}
