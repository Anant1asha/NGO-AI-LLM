// ============================================================
// Hachi Web App — Memory domain loader
//
// Endpoints:
//   GET  /memory              → GatewayMemory → memGroups, blocked, proposed
//   GET  /memory/recall       → GatewayRecallHit[] → recall
//   POST /memory/facts        → add a fact; body: { group, text }; returns { id }
//   DELETE /memory/facts/{id} → delete a fact by content-hash id; returns { ok }
//
// Edit / update: the gateway has no PATCH/PUT endpoint for facts. "Save" is
// implemented as delete-then-add so the backend stays authoritative. The store
// optimistic update fires first; on network failure the page re-fetches from
// the server and surfacing the error via the reconnecting flag.
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { invalidate } from "../cache";
import { useStore } from "../../store/store";
import type { MemGroup, BlockedItem, ProposedChange, RecallHit } from "../types";

// ---- Gateway shapes ----

interface GatewayFact {
  id?: string;
  text?: string;
  source?: string;
}

interface GatewayMemGroup {
  id?: string;
  title?: string;
  facts?: GatewayFact[];
}

interface GatewayBlockedItem {
  id?: string;
  text?: string;
  reason?: string;
}

interface GatewayProposedChange {
  from?: string;
  to?: string;
}

interface GatewayMemory {
  groups?: GatewayMemGroup[];
  blocked?: GatewayBlockedItem[];
  proposed?: GatewayProposedChange | null;
}

interface GatewayRecallHit {
  fact?: string;
  score?: string | number;
  src?: string;
}

// ---- Pure adapters ----

function adaptFact(raw: GatewayFact): MemGroup["facts"][number] {
  return {
    id: raw.id ?? "",
    text: raw.text ?? "",
    source: raw.source ?? "",
  };
}

function adaptMemGroup(raw: GatewayMemGroup): MemGroup {
  return {
    id: raw.id ?? "",
    title: raw.title ?? "",
    facts: (raw.facts ?? []).map(adaptFact),
  };
}

function adaptBlockedItem(raw: GatewayBlockedItem): BlockedItem {
  return {
    id: raw.id ?? "",
    text: raw.text ?? "",
    reason: raw.reason ?? "",
  };
}

function adaptProposed(raw: GatewayProposedChange | null | undefined): ProposedChange | null {
  if (!raw) return null;
  return {
    from: raw.from ?? "",
    to: raw.to ?? "",
  };
}

function adaptRecallHit(raw: GatewayRecallHit): RecallHit {
  // score may be a number from the gateway but the UI type expects string
  const score =
    raw.score === undefined || raw.score === null
      ? ""
      : String(raw.score);
  return {
    fact: raw.fact ?? "",
    score,
    src: raw.src ?? "",
  };
}

// ---- Loaders ----

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, seeded fixtures must NOT be
// shown, so on failure we clear the slices instead of leaving them in place.
let _hasEverSucceeded = false;
// F3: in-flight guard — concurrent calls coalesce into the running promise so
// bootstrapLiveData + the on-navigate useEffect don't double-fetch on mount.
// Resets to null on completion so subsequent navigations get a fresh fetch.
let _inFlight: Promise<void> | null = null;

/** Load memory groups, blocked items, and proposed change from the gateway. */
export async function loadMemory(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  if (_inFlight) return _inFlight;
  _inFlight = (async () => {
    try {
      const raw = await apiGet<GatewayMemory>("/memory");
      useStore.getState().hydrate({
        memGroups: (raw.groups ?? []).map(adaptMemGroup),
        blocked: (raw.blocked ?? []).map(adaptBlockedItem),
        proposed: adaptProposed(raw.proposed),
      });
      _hasEverSucceeded = true;
    } catch {
      if (!_hasEverSucceeded) {
        // First-load failure: clear seeded fixtures so we never present
        // fabricated memory as if it were real gateway data.
        useStore.getState().hydrate({ memGroups: [], blocked: [], proposed: null });
      }
      // Reconnecting flag is now managed centrally by client.ts via the
      // registered callback — no per-domain setReconnecting calls needed here.
    } finally {
      useStore.getState().setLoaded("memory");
    }
  })().finally(() => { _inFlight = null; });
  return _inFlight;
}

/**
 * Run a semantic recall search against the gateway and hydrate the store's
 * `recall` slice with the results.
 */
export async function recallMemory(query: string): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const raw = await apiGet<GatewayRecallHit[]>("/memory/recall", {
      query,
      top_k: 8,
    });
    useStore.getState().hydrate({
      recall: (raw ?? []).map(adaptRecallHit),
    });
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: clear fixture recall hits so they don't appear real.
      useStore.getState().hydrate({ recall: [] });
    }
    // Reconnecting flag managed centrally by client.ts.
  }
}

registerLoader("memory", loadMemory);

// ============================================================
// Mutation wrappers — POST /memory/facts and DELETE /memory/facts/{id}
//
// Pattern (mirrors approvals.ts):
//   1. Optimistic store update (always, instant)
//   2. Network call (skipped when USE_MOCKS)
//   3. On success → refetch via loadMemory() to stay authoritative
//   4. On failure → setReconnecting(true) + revert the optimistic update by
//      calling loadMemory() which overwrites the local-only change with server state
// ============================================================

interface GatewayFactAddResponse {
  id?: string;
}

interface GatewayFactDeleteResponse {
  ok?: boolean;
}

/**
 * Add a new fact to the given vault group.
 *
 * Valid groups: "core_memory" | "user_profile" | "agent_profile"
 *
 * Unlike the old optimistic-only approach, this function POSTs immediately with
 * the real text (non-empty) so the backend can validate and persist it before
 * we re-hydrate the list. Throws an Error with a user-readable message on
 * failure so callers can surface it in the UI.
 *
 * In MOCK mode: skips the network call and resolves immediately.
 */
export async function addFact(groupId: string, text: string): Promise<void> {
  if (!text.trim()) throw new Error("Fact text cannot be empty");
  if (USE_MOCKS) return; // keep seeded fixtures, nothing to POST
  const raw = await apiSend<GatewayFactAddResponse>("POST", "/memory/facts", {
    group: groupId,
    text: text.trim(),
  });
  // Surface backend-level errors (e.g. BLOCKED: or LIMIT_REACHED ids)
  if (raw?.id && (raw.id.startsWith("BLOCKED:") || raw.id === "LIMIT_REACHED")) {
    throw new Error(raw.id === "LIMIT_REACHED" ? "Memory limit reached" : `Blocked: ${raw.id.slice(8)}`);
  }
  // Bust the cache so the next route visit refetches, then reload immediately.
  invalidate("memory");
  await loadMemory();
}

/**
 * Save (update) a fact. The gateway has no PATCH endpoint, so this is
 * implemented as DELETE existing + POST new text, preserving the group.
 * Optimistic update fires via the store's saveFact action before this call.
 *
 * For brand-new (locally-created) facts whose id starts with "fn" (the store's
 * temp-id prefix), the DELETE step is skipped because the fact does not exist
 * on the server yet — only the POST runs.
 *
 * In MOCK mode: delegates entirely to the store action (optimistic-only).
 */
export async function saveFact(
  groupId: string,
  factId: string,
  newText: string
): Promise<void> {
  if (USE_MOCKS) return; // store action already ran optimistically
  const isLocalTemp = factId.startsWith("fn");
  try {
    if (!isLocalTemp) {
      // Step 1: delete the old fact (by its server-side content-hash id)
      await apiSend<GatewayFactDeleteResponse>("DELETE", `/memory/facts/${factId}`);
    }
    // Step 2: add the updated (or new) text
    if (newText.trim()) {
      await apiSend<GatewayFactAddResponse>("POST", "/memory/facts", {
        group: groupId,
        text: newText.trim(),
      });
    }
    // Bust the cache so the next route visit refetches, then reload immediately.
    invalidate("memory");
    await loadMemory();
  } catch {
    // Network errors surface the reconnecting banner via client.ts callback.
    invalidate("memory");
    void loadMemory(); // best-effort revert to server state
  }
}

/**
 * Delete a fact permanently. Optimistic removal fires via the store's
 * delFact action before this call.
 *
 * In MOCK mode: delegates entirely to the store action (optimistic-only).
 */
export async function delFact(groupId: string, factId: string): Promise<void> {
  if (USE_MOCKS) return; // store action already ran optimistically
  try {
    await apiSend<GatewayFactDeleteResponse>("DELETE", `/memory/facts/${factId}`);
    // Bust the cache so the next route visit refetches, then reload immediately.
    invalidate("memory");
    await loadMemory();
  } catch {
    // Network errors surface the reconnecting banner via client.ts callback.
    invalidate("memory");
    void loadMemory(); // best-effort revert — puts the fact back if it still exists
  }
}
