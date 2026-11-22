// ============================================================
// Hachi Web App — Interactions domain loader (eval loop)
// Endpoints:
//   GET  /interactions?session_id=<optional>&limit=<int>  → InteractionListResponse
//   PUT  /interactions/{id}/rating  body {rating, notes?}  → {ok: boolean}
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { useStore } from "../../store/store";
import type { AgentInteraction } from "../types";

// ---- Gateway shapes (mirrors InteractionRecord in schema.d.ts) ----

interface GatewayInteractionRecord {
  id: string;
  session_id: string;
  turn_id?: string | null;
  ts: string;
  user_input?: string | null;
  agent_output?: string | null;
  tool_calls?: string[];
  memory_hits?: string[];
  model_used?: string | null;
  token_cost?: number | null;
  tokens?: number | null;
  rating?: string | null;
  notes?: string | null;
}

interface GatewayInteractionListResponse {
  interactions: GatewayInteractionRecord[];
}

// ---- Pure adapter ----

function humanizeTs(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    if (diffDays === 1) return "yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  } catch {
    return iso;
  }
}

function adaptRating(raw: string | null | undefined): "up" | "down" | null {
  if (raw === "up") return "up";
  if (raw === "down") return "down";
  return null;
}

function adapt(raw: GatewayInteractionRecord): AgentInteraction {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    turnId: raw.turn_id ?? null,
    ts: raw.ts,
    tsHuman: humanizeTs(raw.ts),
    userInput: raw.user_input ?? "",
    agentOutput: raw.agent_output ?? "",
    toolCalls: raw.tool_calls ?? [],
    memoryHits: raw.memory_hits ?? [],
    modelUsed: raw.model_used ?? "",
    tokenCost: raw.token_cost ?? null,
    tokens: raw.tokens ?? null,
    rating: adaptRating(raw.rating),
    notes: raw.notes ?? null,
  };
}

// ---- Loader ----

// Tracks whether this domain has ever received real data from the gateway.
// On the first live failure, clear seeded fixtures so fabricated data is
// never shown as real gateway data.
let _hasEverSucceeded = false;

export async function loadInteractions(): Promise<void> {
  return _loadInteractionsImpl();
}

async function _loadInteractionsImpl(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const raw = await apiGet<GatewayInteractionListResponse>("/interactions", { limit: 100 });
    const interactions: AgentInteraction[] = (raw.interactions ?? []).map(adapt);
    useStore.getState().hydrate({ interactions });
    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: clear seeded fixtures so we never present
      // fabricated interaction data as if it were real gateway data.
      useStore.getState().hydrate({ interactions: [] });
    }
  } finally {
    useStore.getState().setLoaded("review");
  }
}

// ---- Mutation ----

/**
 * PUT /interactions/{id}/rating then re-fetches to stay authoritative.
 *
 * In live mode: always round-trips to the gateway and reflects server truth
 * by calling loadInteractions() afterward — never optimistically mutates
 * local state alone.
 */
export async function rateInteraction(
  id: string,
  rating: "up" | "down",
  notes?: string
): Promise<void> {
  if (USE_MOCKS) {
    // In mock mode, mutate local state directly (no gateway available).
    const current = useStore.getState().interactions as AgentInteraction[];
    const updated = current.map((ix) =>
      ix.id === id ? { ...ix, rating, notes: notes ?? null } : ix
    );
    useStore.getState().hydrate({ interactions: updated });
    return;
  }
  try {
    await apiSend<{ ok: boolean }>("PUT", `/interactions/${id}/rating`, {
      rating,
      notes: notes ?? undefined,
    });
    useStore.getState().showToast("Rating saved", "success");
    // Re-fetch to reflect authoritative server state (not just local optimism).
    await loadInteractions();
  } catch {
    useStore.getState().showToast("Failed to save rating", "info");
  }
}

registerLoader("interactions", loadInteractions);
