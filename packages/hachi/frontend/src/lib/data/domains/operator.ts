// ============================================================
// Hachi Web App — Operator observability domain loader
// NO dedicated route — just hydrates the store. Existing components
// (ActivityLens in work.tsx, pack panel) auto-render.
//
// Endpoints:
//   GET /subagents/reports?top_k=10  → SubAgentReport[] → PackMember[]
//   GET /runtime/events?limit=100    → RuntimeEvent[]   → ActivityEvent[] + ToolCall[]
// ============================================================

import { apiGet, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { useStore } from "../../store/store";
import type { PackMember, ActivityEvent, ToolCall } from "../types";

// ---- Gateway shapes ----

interface GatewaySubAgentReport {
  role: string;
  status: string;
  duration_seconds: number;
  iterations: number;
  summary: string;
}

interface GatewayRuntimeEvent {
  name: string;
  payload: Record<string, unknown>;
  timestamp: string;
  sequence: number;
}

// ---- Pure adapters ----

function adaptSubAgentReport(raw: GatewaySubAgentReport): PackMember {
  const statusMap: Record<string, PackMember["status"]> = {
    running: "working",
    active: "working",
    working: "working",
    completed: "done",
    done: "done",
    success: "done",
    idle: "pending",
    pending: "pending",
    waiting: "pending",
  };

  return {
    role: raw.role ?? "agent",
    task: raw.summary ?? "—",
    status: statusMap[raw.status] ?? "pending",
    outcome: raw.summary ?? raw.status ?? "—",
    tokens: 0, // no token field in the gateway report
  };
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts ?? "—";
  }
}

function eventLevel(name: string): ActivityEvent["lvl"] {
  if (/error|fail/.test(name)) return "error";
  if (/warn/.test(name)) return "warn";
  if (/^tool\./.test(name)) return "info";
  return "muted";
}

function adaptRuntimeEvent(raw: GatewayRuntimeEvent): ActivityEvent {
  const payload = raw.payload ?? {};
  // Build a short description from common payload fields
  const detail =
    (payload.text as string | undefined) ??
    (payload.summary as string | undefined) ??
    (payload.name as string | undefined) ??
    (payload.detail as string | undefined) ??
    "";

  return {
    t: formatTimestamp(raw.timestamp),
    type: raw.name ?? "event",
    d: detail,
    lvl: eventLevel(raw.name ?? ""),
  };
}

// Pairs of started/completed tool events keyed by tool name + timestamp proximity.
// We derive ToolCall from tool.call.started events and fill in result from
// tool.call.completed events when available (best-effort matching by name).
interface StartedEntry {
  name: string;
  inp: string;
  ts: string;
  tsMs: number;
}

function adaptToolCalls(events: GatewayRuntimeEvent[]): ToolCall[] {
  const started: StartedEntry[] = [];
  const completed = new Map<string, GatewayRuntimeEvent>(); // keyed by tool name

  for (const ev of events) {
    if (ev.name === "tool.call.started") {
      const p = ev.payload ?? {};
      started.push({
        name: (p.name as string | undefined) ?? "unknown",
        inp: (p.input as string | undefined) ?? JSON.stringify(p),
        ts: ev.timestamp ?? "",
        tsMs: ev.timestamp ? new Date(ev.timestamp).getTime() : 0,
      });
    }
    if (ev.name === "tool.call.completed") {
      const p = ev.payload ?? {};
      const toolName = (p.name as string | undefined) ?? "";
      // Keep the latest completed event for each tool name
      completed.set(toolName, ev);
    }
  }

  return started.map((s) => {
    const comp = completed.get(s.name);
    const compPayload = comp?.payload ?? {};
    const out =
      (compPayload.result_preview as string | undefined) ??
      (compPayload.detail as string | undefined) ??
      "—";

    let dur = "—";
    if (comp?.timestamp && s.tsMs) {
      const compMs = new Date(comp.timestamp).getTime();
      const diffMs = compMs - s.tsMs;
      if (diffMs >= 0) {
        dur = diffMs < 1000 ? `${diffMs}ms` : `${(diffMs / 1000).toFixed(1)}s`;
      }
    }

    return {
      tool: s.name,
      inp: s.inp,
      out,
      dur,
      ts: formatTimestamp(s.ts),
    };
  });
}

// ---- Loader ----

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, seeded fixtures must NOT be
// shown, so on failure we clear the slice instead of leaving them in place.
let _hasEverSucceeded = false;

export async function loadOperator(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const [rawReports, rawEvents] = await Promise.all([
      apiGet<GatewaySubAgentReport[]>("/subagents/reports", { top_k: 10 }),
      apiGet<GatewayRuntimeEvent[]>("/runtime/events", { limit: 100 }),
    ]);

    const packRoster: PackMember[] = (rawReports ?? []).map(adaptSubAgentReport);
    const events: ActivityEvent[] = (rawEvents ?? []).map(adaptRuntimeEvent);
    const toolCalls: ToolCall[] = adaptToolCalls(rawEvents ?? []);

    useStore.getState().hydrate({ packRoster, events, toolCalls });
    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: clear seeded fixtures so we never present
      // fabricated data as if it were real gateway data.
      useStore.getState().hydrate({ packRoster: [], events: [], toolCalls: [] });
    }
    // Reconnecting flag is now managed centrally by client.ts via the
    // registered callback — no per-domain setReconnecting calls needed.
  }
}

registerLoader("operator", loadOperator);
