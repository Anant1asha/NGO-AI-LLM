// ============================================================
// Hachi Web App — Spend analytics domain loader
// NO dedicated route — just hydrates the store. Existing components
// (computeSpend / spend panel in work.tsx) auto-render from the slices.
//
// Endpoint:
//   GET /spend?session_id=<id>  (session_id optional — omit for current session)
//   → { turns:[{n,inT,out,cost}], tidies:[{ts,before,after}], models:[{name,tokens,cost,color}] }
// ============================================================

import { apiGet, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { dedupe } from "../dedupe";
import { useStore } from "../../store/store";
import type { SpendTurn, SpendTidy, SpendModel } from "../types";

// ---- Gateway shapes ----
// Field names intentionally mirror the UI types (gateway contract matches).

interface GatewaySpendTurn {
  n?: number;
  inT?: number;
  out?: number;
  cost?: number;
}

interface GatewaySpendTidy {
  ts?: string;
  before?: number;
  after?: number;
}

interface GatewaySpendModel {
  name?: string;
  tokens?: number;
  cost?: number;
  color?: string;
}

interface GatewaySpend {
  turns?: GatewaySpendTurn[];
  tidies?: GatewaySpendTidy[];
  models?: GatewaySpendModel[];
}

// ---- Color palette (assigned client-side when backend omits color) ----

const MODEL_COLORS = [
  "#C2703D",
  "#3D7AC2",
  "#5BA86A",
  "#A85B9E",
  "#C2A23D",
] as const;

function pickColor(index: number): string {
  return MODEL_COLORS[index % MODEL_COLORS.length];
}

// ---- Pure adapters ----

function adaptTurn(raw: GatewaySpendTurn): SpendTurn {
  return {
    n: raw.n ?? 0,
    inT: raw.inT ?? 0,
    out: raw.out ?? 0,
    cost: raw.cost ?? 0,
  };
}

function adaptTidy(raw: GatewaySpendTidy): SpendTidy {
  return {
    ts: raw.ts ?? "",
    before: raw.before ?? 0,
    after: raw.after ?? 0,
  };
}

function adaptModel(raw: GatewaySpendModel, index: number): SpendModel {
  // The durable-ledger sentinel is emitted when no active session is available;
  // show it with a readable name in the UI.
  const rawName = raw.name ?? "unknown";
  const displayName = rawName === "durable-ledger" ? "Historical (no active session)" : rawName;
  return {
    name: displayName,
    tokens: raw.tokens ?? 0,
    cost: raw.cost ?? 0,
    // Assign a palette color when the backend sends an empty or missing color.
    color: raw.color && raw.color.trim() !== "" ? raw.color : pickColor(index),
  };
}

// ---- Loader ----

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, seeded fixtures must NOT be
// shown, so on failure we clear the slices instead of leaving them in place.
let _hasEverSucceeded = false;

export async function loadSpend(): Promise<void> {
  return dedupe("spend", _loadSpendImpl);
}

async function _loadSpendImpl(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const raw = await apiGet<GatewaySpend>("/spend");
    const spendTurns: SpendTurn[] = (raw.turns ?? []).map(adaptTurn);
    const spendTidies: SpendTidy[] = (raw.tidies ?? []).map(adaptTidy);
    const spendModels: SpendModel[] = (raw.models ?? []).map(adaptModel);
    useStore.getState().hydrate({ spendTurns, spendTidies, spendModels });
    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: clear seeded fixtures so we never present
      // fabricated spend data as if it were real gateway data.
      useStore.getState().hydrate({ spendTurns: [], spendTidies: [], spendModels: [] });
    }
    // Reconnecting flag is now managed centrally by client.ts via the
    // registered callback — no per-domain setReconnecting calls needed here.
  }
}

registerLoader("spend", loadSpend);

// ============================================================
// Daily spend ledger — GET /spend/daily
// ============================================================

interface GatewayDailySpend {
  spent_usd: number;
  daily_cap_usd: number | null;
  task_cap_usd: number | null;
  date: string;
}

/**
 * Fetch today's accumulated spend from the gateway daily ledger and hydrate
 * the store's ``spent``, ``dailyCap``, ``budget``, and ``taskCap`` slices.
 *
 * Called from {@link loadConfig} on every page load so ``spent`` survives a
 * browser refresh.  The live SSE ``usage.updated`` path continues to bump
 * ``spent`` in real time during an active session; this is the persistent
 * restore path for between-session and post-reload state.
 *
 * Never throws — a network failure leaves the store at its prior value.
 */
export async function loadDailySpend(): Promise<void> {
  if (USE_MOCKS) return; // mock mode: fixtures are already seeded

  try {
    const data = await apiGet<GatewayDailySpend>("/spend/daily");

    const patch: Record<string, number> = {};

    if (typeof data.spent_usd === "number") {
      patch.spent = data.spent_usd;
    }
    if (typeof data.daily_cap_usd === "number" && data.daily_cap_usd > 0) {
      patch.dailyCap = data.daily_cap_usd;
      patch.budget = data.daily_cap_usd;
    }
    if (typeof data.task_cap_usd === "number" && data.task_cap_usd > 0) {
      patch.taskCap = data.task_cap_usd;
    }

    if (Object.keys(patch).length > 0) {
      useStore.getState().hydrate(patch);
    }
  } catch {
    // Network errors surface the reconnecting banner via client.ts callback.
    // Silently leave the store at its current value.
  }
}
