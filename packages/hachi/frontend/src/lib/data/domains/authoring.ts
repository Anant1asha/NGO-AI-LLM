// ============================================================
// Hachi Web App — Authoring domain loader
//
// Endpoints:
//   GET  /authoring/targets                             → GatewayTarget[] → AuthTarget[]
//   GET  /authoring/targets/{name}                      → { name, source }
//   POST /authoring/targets/{name}/generate  body{prompt} → { diff: DiffLine[] }
//   POST /authoring/targets/{name}/apply     body{}      → { ok, reindexed_ms }
//   POST /authoring/targets/{name}/revert    body{}      → { ok }
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { useStore } from "../../store/store";
import type { AuthTarget, DiffLine } from "../types";

// ---- Gateway shapes ----

interface GatewayTarget {
  name: string;
  path: string;
  kind: string;
  dirty: boolean;
}

interface GatewayTargetSource {
  name: string;
  source: string;
}

interface GatewayGenerateResponse {
  diff: Array<["" | "add" | "del", string]>;
}

/** Returned by generateAuthoring — callers hold this in local state. */
export interface GenerateResult {
  diff: DiffLine[];
  error?: string;
}

// ---- Pure adapters ----

function adaptTarget(raw: GatewayTarget): AuthTarget {
  const kindMap: Record<string, AuthTarget["kind"]> = {
    brain: "brain",
    skill: "skill",
    config: "config",
  };
  return {
    name: raw.name ?? "",
    path: raw.path ?? "",
    kind: kindMap[raw.kind] ?? "skill",
    dirty: raw.dirty ?? false,
  };
}

/** Convert a plain-text source string into DiffLine[] (each line is a neutral "" row). */
function sourceToLines(source: string): DiffLine[] {
  return source.split("\n").map((line): DiffLine => ["", line]);
}

// ---- Loader ----

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, seeded fixtures must NOT be
// shown, so on failure we clear the slices instead of leaving them in place.
let _hasEverSucceeded = false;

export async function loadAuthoring(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const raw = await apiGet<GatewayTarget[]>("/authoring/targets");
    useStore.getState().hydrate({ authTargets: (raw ?? []).map(adaptTarget) });
    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: clear seeded fixtures so we never present
      // fabricated authoring targets as if they were real gateway data.
      // Also clear authSource since it was seeded alongside the targets.
      useStore.getState().hydrate({ authTargets: [], authSource: [] });
    }
    // Reconnecting flag is now managed centrally by client.ts via the
    // registered callback — no per-domain setReconnecting calls needed here.
  }
}

registerLoader("authoring", loadAuthoring);

// ---- Source loader ----

/**
 * Fetch the source text for a named target, convert to DiffLine[], and return it.
 * Also hydrates the store's authSource so the editor reflects the loaded content.
 * Never throws — on error returns empty content and a non-null error message.
 *
 * HACHI-019: returns a `fetchError` field so callers can surface inline errors
 * rather than silently falling back to a generic placeholder.
 */
export async function loadAuthoringSource(
  name: string
): Promise<{ source: string; diff: DiffLine[]; fetchError?: string }> {
  if (USE_MOCKS) {
    // In mock mode return the existing store state so fixtures are untouched
    const existing = useStore.getState().authSource;
    return { source: existing.map((l) => l[1]).join("\n"), diff: [] };
  }

  // HACHI-019: only fetch when the name is in the live targets set.
  // This prevents 400 errors for stale/fixture targets like deep_research.og.
  const liveTargets = useStore.getState().authTargets;
  if (liveTargets.length > 0 && !liveTargets.some((t) => t.name === name)) {
    // Target is not in the live set — clear source and signal the caller.
    useStore.getState().hydrate({ authSource: [] });
    return {
      source: "",
      diff: [],
      fetchError: `"${name}" is not in the allowed target set.`,
    };
  }

  try {
    const raw = await apiGet<GatewayTargetSource>(
      "/authoring/targets/" + encodeURIComponent(name)
    );
    const source = raw.source ?? "";
    const diff: DiffLine[] = sourceToLines(source);
    // Hydrate the store so the viewer shows the loaded content immediately.
    // diff is always [] (no pending-patch pipeline yet); authSource holds source lines.
    useStore.getState().hydrate({ authSource: diff });
    return { source, diff: [] };
  } catch (err: unknown) {
    // Network errors surface the reconnecting banner via client.ts callback.
    const fetchError =
      err instanceof Error ? err.message : "Failed to load target source.";
    return { source: "", diff: [], fetchError };
  }
}

// ---- Mutation wrappers ----

/**
 * Call POST /authoring/targets/{name}/generate with a natural-language prompt.
 * Returns a GenerateResult with the diff lines. Never throws — errors are surfaced
 * as { diff: [], error: "<message>" } so callers can render inline error state.
 *
 * NOTE: The backend endpoint is under construction. Until it lands, a 404 (or any
 * other error) is caught and returned as an error result.
 */
export async function generateAuthoring(
  name: string,
  prompt: string
): Promise<GenerateResult> {
  if (USE_MOCKS) {
    // Synthetic diff for offline UI work
    return {
      diff: [
        ["", "node deep_research"],
        ["del", "  budget: dense=8 full=4"],
        ["add", "  budget: dense=12 full=6"],
        ["del", "  strategy: sequential"],
        ["add", "  strategy: adaptive"],
      ],
    };
  }
  try {
    const raw = await apiSend<GatewayGenerateResponse>(
      "POST",
      "/authoring/targets/" + encodeURIComponent(name) + "/generate",
      { prompt }
    );
    const diff: DiffLine[] = (raw?.diff ?? []).map(
      ([type, text]) => [type, text] as DiffLine
    );
    return { diff };
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Generate failed — try again.";
    return { diff: [], error: message };
  }
}

/**
 * Apply the pending patch for the named target.
 * In live mode: POSTs to the gateway first; only marks as applied on 2xx
 * (uses real reindexed_ms for the toast). On error shows an error toast
 * and does NOT flip authApplied so the user can retry.
 * In mock mode: applies optimistically as before.
 */
export async function applyAuthoring(name: string): Promise<void> {
  if (USE_MOCKS) {
    useStore.getState().applyPatch();
    return;
  }
  try {
    const resp = await apiSend<{ ok: boolean; reindexed_ms: number }>(
      "POST",
      "/authoring/targets/" + encodeURIComponent(name) + "/apply",
      {}
    );
    useStore.getState().applyPatch(resp?.reindexed_ms);
    // Refresh the targets list to pick up server-side state
    await loadAuthoring();
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Apply failed — please try again";
    useStore.getState().showToast(msg, "blocked");
    // Network errors surface the reconnecting banner via client.ts callback.
  }
}

// ---- Save / manual-edit wrapper ----

interface GatewaySaveSourceResponse {
  ok: boolean;
  message?: string;
}

/**
 * Save hand-edited source content for a named target.
 * CONTRACT-AUTHORING-SAVE: POST /authoring/targets/{name}/source  body { content }
 * Returns { ok: true } on success, or { ok: false, message } on validation failure.
 * Never throws — network errors are returned as { ok: false, message }.
 */
export async function saveAuthoringSource(
  name: string,
  content: string
): Promise<{ ok: boolean; message?: string }> {
  if (USE_MOCKS) {
    // In mock mode, update the store so the viewer reflects the edit immediately.
    const lines = content.split("\n").map((line): DiffLine => ["", line]);
    useStore.getState().hydrate({ authSource: lines });
    return { ok: true };
  }
  try {
    const resp = await apiSend<GatewaySaveSourceResponse>(
      "POST",
      "/authoring/targets/" + encodeURIComponent(name) + "/source",
      { content }
    );
    if (resp?.ok === false) {
      return { ok: false, message: resp.message ?? "Save rejected by gateway." };
    }
    // Reload the source from gateway so the viewer reflects the saved state.
    await loadAuthoringSource(name);
    return { ok: true };
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Save failed — please try again.";
    return { ok: false, message };
  }
}

/**
 * Revert the pending patch for the named target.
 * In live mode: POSTs to the gateway first; only restores dirty state on 2xx.
 * On error shows an error toast and leaves authApplied true so the user can retry.
 * In mock mode: reverts optimistically as before.
 */
export async function revertAuthoring(name: string): Promise<void> {
  if (USE_MOCKS) {
    useStore.getState().revertPatch();
    return;
  }
  try {
    await apiSend<{ ok: boolean }>(
      "POST",
      "/authoring/targets/" + encodeURIComponent(name) + "/revert",
      {}
    );
    useStore.getState().revertPatch();
    // Refresh target list
    await loadAuthoring();
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Revert failed — please try again";
    useStore.getState().showToast(msg, "blocked");
    // Network errors surface the reconnecting banner via client.ts callback.
  }
}
