// ============================================================
// Hachi Web App — config / settings domain
//
// Wires: GET /config, GET /models, PUT /config/provider,
//        POST /config/provider/validate, PUT /config/permissions,
//        PUT /config/memory
//
// Mapping:
//   permissions.tier sandbox  → safety "guarded"
//   permissions.tier guided   → safety "standard"
//   permissions.tier unrestricted → safety "open"
//   provider.kind → provider.name; provider.model → provider.model
//   key always stays "" (never surface secrets)
//   allowedFolders / allowedCommands → keep fixtures (no backing field)
//   askRules / opTools → keep fixtures (no backing field)
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { dedupe } from "../dedupe";
import { useStore } from "../../store/store";
import { loadDailySpend } from "./spend";
import type { SafetyLevel, Provider, AskRule } from "../types";

// ---- Local types mirroring the gateway Python dataclasses ----

interface GatewayProviderSettings {
  kind?: string;
  model?: string;
  base_url?: string | null;
  api_key_ref?: string | null;
  api_key_env?: string | null;
}

interface GatewayAskBeforeSettings {
  spend_over_threshold?: boolean;
  network_egress?: boolean;
  delete_files?: boolean;
}

interface GatewayPermissionsSettings {
  tier?: "sandbox" | "guided" | "unrestricted";
  ask_before?: GatewayAskBeforeSettings;
}

interface GatewayMemorySettings {
  enable_session_history?: boolean;
  enable_semantic_memory?: boolean;
}

interface GatewayLimitsSettings {
  per_task_cap_usd?: number | null;
  daily_cap_usd?: number | null;
}

interface GatewayConfig {
  provider?: GatewayProviderSettings;
  permissions?: GatewayPermissionsSettings;
  memory?: GatewayMemorySettings;
  limits?: GatewayLimitsSettings;
  // other keys exist (meta, agent, capabilities, channels) but are not mapped
  [key: string]: unknown;
}

interface GatewayModel {
  id: string;
  label: string;
  provider: string;
  recommended: boolean;
}

interface ValidateProviderResponse {
  ok: boolean;
  errors: string[];
  warnings: string[];
}

// Module-level model list (not stored in Zustand — avoids types.ts changes)
let _availableModels: GatewayModel[] = [];

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, seeded fixtures must NOT be
// shown, so on failure we clear the slice instead of leaving them in place.
let _hasEverSucceeded = false;

/** Returns the last fetched model list (empty until loadConfig resolves). */
export function getAvailableModels(): GatewayModel[] {
  return _availableModels;
}

// ---- Adapters ----

/** gateway tier → UI SafetyLevel */
function adaptTier(tier?: string): SafetyLevel {
  if (tier === "sandbox") return "guarded";
  if (tier === "unrestricted") return "open";
  return "standard"; // "guided" and fallback
}

/** UI SafetyLevel → gateway tier */
function safetyToTier(level: SafetyLevel): "sandbox" | "guided" | "unrestricted" {
  if (level === "guarded") return "sandbox";
  if (level === "open") return "unrestricted";
  return "guided"; // "standard"
}

// "Ask before…" rules. The gateway stores booleans keyed by rule id
// (permissions.ask_before); the human-readable labels live here on the client.
// Order here is the display order in Settings → Permissions & safety.
const ASK_RULE_LABELS: { id: keyof GatewayAskBeforeSettings; label: string }[] = [
  { id: "spend_over_threshold", label: "Before spending over the per-task cap on one task" },
  { id: "network_egress", label: "Before sending anything outside your machine" },
  { id: "delete_files", label: "Before deleting files" },
];

/** gateway permissions.ask_before → UI AskRule[] (defaults to "on" when absent) */
function adaptAskRules(raw?: GatewayAskBeforeSettings): AskRule[] {
  return ASK_RULE_LABELS.map(({ id, label }) => ({
    id,
    label,
    on: raw?.[id] ?? true,
  }));
}

/** gateway provider → UI Provider (never surface secrets) */
function adaptProvider(raw?: GatewayProviderSettings): Provider {
  return {
    name: raw?.kind ?? "anthropic",
    model: raw?.model ?? "claude-haiku-4-5",
    key: "", // intentionally blank — never expose secrets to the browser
  };
}

// ---- Loader ----

/**
 * Load effective config + models from the gateway and hydrate the store.
 * Never throws. On error: setReconnecting(true) and leave existing fixtures.
 */
export async function loadConfig(): Promise<void> {
  return dedupe("config", _loadConfigImpl);
}

async function _loadConfigImpl(): Promise<void> {
  if (USE_MOCKS) {
    // In mock mode, fixtures are already seeded — just mark config as loaded.
    useStore.getState().hydrate({ configLoaded: true });
    return;
  }

  // BB-15: /config and /models are fetched INDEPENDENTLY. /config is the source
  // of truth for the safety tier, provider, and caps and is a cheap local read
  // (~12ms). /models makes a LIVE external provider round-trip (measured ~1.6s)
  // and is flaky — a rate-limit, expired key, network blip, or a fetch aborted
  // on navigation will reject it. Previously both were in one Promise.all and a
  // /models failure dropped into the catch below, which reset safety to
  // "standard" — silently reverting the user's permission tier even though
  // /config had the correct value. Decoupling them means a /models failure can
  // only degrade the model dropdown, never the permission tier.
  try {
    const rawConfig = await apiGet<GatewayConfig>("/config");

    // Map config → store slice
    const safety = adaptTier(rawConfig?.permissions?.tier);
    const askRules = adaptAskRules(rawConfig?.permissions?.ask_before);
    const provider = adaptProvider(rawConfig?.provider);

    // Hydrate spend caps from gateway limits — fall back to current store values
    // when fields are absent/null so we never overwrite user-edited in-session values.
    const currentState = useStore.getState();
    const limitsRaw = rawConfig?.limits;
    const taskCap =
      typeof limitsRaw?.per_task_cap_usd === 'number' && limitsRaw.per_task_cap_usd > 0
        ? limitsRaw.per_task_cap_usd
        : currentState.taskCap;
    const dailyCap =
      typeof limitsRaw?.daily_cap_usd === 'number' && limitsRaw.daily_cap_usd > 0
        ? limitsRaw.daily_cap_usd
        : currentState.dailyCap;

    // `budget` is the denominator shown in the governance bar / home / settings
    // spend readouts. Keep it in lockstep with the persisted daily cap so the
    // value survives a refresh (previously only `dailyCap` was hydrated, leaving
    // `budget` at its 5.0 default → "of $5.00" instead of the saved cap).
    useStore
      .getState()
      .hydrate({ safety, askRules, provider, taskCap, dailyCap, budget: dailyCap, configLoaded: true });

    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: reset to safe defaults so we never present
      // the fixture provider/safety config as if it were real gateway data.
      useStore.getState().hydrate({
        safety: "standard",
        provider: { name: "anthropic", model: "claude-haiku-4-5", key: "" },
        configLoaded: true,
      });
    }
    // Reconnecting flag is now managed centrally by client.ts via the
    // registered callback — no per-domain setReconnecting calls needed here.
  }

  // Restore today's real accumulated spend from the daily ledger so the spend
  // bar reflects the correct value on every page load. Independent of /config
  // and /models — its own failure must not touch safety.
  try {
    await loadDailySpend();
  } catch {
    /* spend ledger unavailable — the bar degrades, the tier does not */
  }

  // Model list powers ONLY the provider/model dropdown. Fetched last and on its
  // own so its (slow, external) failure leaves every config-derived value intact.
  try {
    const rawModels = await apiGet<GatewayModel[]>("/models");
    _availableModels = Array.isArray(rawModels) ? rawModels : [];
  } catch {
    /* keep the previous model list; the dropdown degrades, not the tier */
  }
}

// Self-register so bootstrapLiveData() picks this up on app mount
registerLoader("config", loadConfig);

// ---- Mutation wrappers ----

/**
 * Update the safety level optimistically, then persist to the gateway.
 * On success, re-reads config from gateway so the store reflects the persisted
 * value (guards against a concurrent loadConfig() overwriting with stale data).
 * On failure, rolls back the optimistic update and shows a toast — the error
 * was previously swallowed silently, causing Open to revert to Standard on the
 * next page load because settings.toml was never updated.
 */
export async function setSafetyLive(level: SafetyLevel): Promise<void> {
  const previous = useStore.getState().safety;
  useStore.getState().setSafety(level);
  if (USE_MOCKS) {
    useStore.getState().showToast("Safety level updated", "success");
    return;
  }
  try {
    await apiSend<GatewayConfig>("PUT", "/config/permissions", {
      permissions: { tier: safetyToTier(level) },
    });
    // Re-read config to confirm the write landed and clear any stale dedupe
    // result from a concurrent loadConfig() that ran before the PUT committed.
    await loadConfig();
    useStore.getState().showToast("Safety level updated", "success");
  } catch {
    useStore.getState().setSafety(previous);
    useStore.getState().showToast(
      "Permissions not saved — is Hachi running?",
      "blocked",
    );
  }
}

/**
 * Toggle an "Ask before…" rule optimistically, then persist to the gateway.
 * The rule id IS the gateway ask_before key (see ASK_RULE_LABELS), so we send
 * only the single changed flag. Persisted to settings.toml so it survives reload.
 */
export async function setAskRuleLive(id: string, on: boolean): Promise<void> {
  const previousRules = useStore.getState().askRules;
  // Optimistic update — flip just this rule in the store.
  useStore.getState().hydrate({
    askRules: previousRules.map((r) => (r.id === id ? { ...r, on } : r)),
  });
  const ruleLabel = ASK_RULE_LABELS.find((r) => r.id === id)?.label ?? "rule";
  if (USE_MOCKS) {
    useStore.getState().showToast(`"${ruleLabel}" updated`, "success");
    return;
  }
  try {
    await apiSend<GatewayConfig>("PUT", "/config/permissions", {
      permissions: { ask_before: { [id]: on } },
    });
    useStore.getState().showToast(`"${ruleLabel}" updated`, "success");
  } catch {
    // Roll back the optimistic flip — a silently-failed write must not look saved.
    useStore.getState().hydrate({ askRules: previousRules });
    useStore.getState().showToast(
      `Could not update "${ruleLabel}" — is Hachi running?`,
      "blocked",
    );
  }
}

/**
 * Update the provider optimistically, then persist to the gateway.
 * Patch is a partial Provider (UI shape); we send only the diff.
 */
export async function setProviderLive(patch: Partial<Provider>): Promise<void> {
  // Optimistic update
  useStore.getState().setProvider(patch);
  if (USE_MOCKS) return;
  try {
    // Map UI fields → gateway fields (never send key — it's always "")
    const gwPatch: Partial<GatewayProviderSettings> = {};
    if (patch.name !== undefined) gwPatch.kind = patch.name;
    if (patch.model !== undefined) gwPatch.model = patch.model;
    await apiSend<GatewayConfig>("PUT", "/config/provider", {
      provider: gwPatch,
    });
  } catch {
    // Network errors surface the reconnecting banner via client.ts callback.
  }
}

/**
 * Persist the spend caps to the gateway via PUT /config/limits.
 *
 * Unlike the optimistic setters above (which swallow network errors), this
 * PROPAGATES failures: the Settings "Save" button needs to distinguish success
 * from failure to keep the unsaved indicator and show the right toast. Pass a
 * non-positive value (or null) to clear a cap. No-ops in mock mode.
 */
export async function setLimitsLive(
  perTaskCapUsd: number | null,
  dailyCapUsd: number | null
): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<GatewayConfig>("PUT", "/config/limits", {
    per_task_cap_usd: perTaskCapUsd,
    daily_cap_usd: dailyCapUsd,
  });
}

/**
 * Validate a proposed provider config without persisting.
 * Returns { ok, errors, warnings } — or a failed-safe fallback on error.
 */
export async function validateProvider(
  patch: Partial<Provider>
): Promise<ValidateProviderResponse> {
  if (USE_MOCKS) return { ok: true, errors: [], warnings: [] };
  try {
    const gwPatch: Partial<GatewayProviderSettings> = {};
    if (patch.name !== undefined) gwPatch.kind = patch.name;
    if (patch.model !== undefined) gwPatch.model = patch.model;
    return await apiSend<ValidateProviderResponse>(
      "POST",
      "/config/provider/validate",
      { provider: gwPatch }
    );
  } catch {
    // Network errors surface the reconnecting banner via client.ts callback.
    return { ok: false, errors: ["Could not reach gateway"], warnings: [] };
  }
}

/**
 * Add an allowed folder path and persist to the gateway.
 * Only adds to the UI list on 2xx; shows an error toast on failure.
 * In mock mode, delegates directly to the store action (no network call).
 */
export async function addFolderLive(path: string): Promise<void> {
  const { addFolderWithPath, showToast } = useStore.getState();
  if (USE_MOCKS) {
    addFolderWithPath(path);
    return;
  }
  try {
    await apiSend<unknown>("POST", "/config/permissions/folders", { path });
    addFolderWithPath(path);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Failed to add folder — please try again";
    showToast(msg, "blocked");
  }
}

/**
 * Add an allowed command and persist to the gateway.
 * Only adds to the UI list on 2xx; shows an error toast on failure.
 * In mock mode, delegates directly to the store action (no network call).
 */
export async function addCommandLive(command: string): Promise<void> {
  const { addCommandWithText, showToast } = useStore.getState();
  if (USE_MOCKS) {
    addCommandWithText(command);
    return;
  }
  try {
    await apiSend<unknown>("POST", "/config/permissions/commands", { command });
    addCommandWithText(command);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Failed to add command — please try again";
    showToast(msg, "blocked");
  }
}

/**
 * Remove an allowed folder path and persist to the gateway.
 * Only removes from the UI list on 2xx; shows an error toast on failure.
 */
export async function removeFolderLive(path: string): Promise<void> {
  const { removeFolder, showToast } = useStore.getState();
  if (USE_MOCKS) {
    removeFolder(path);
    return;
  }
  try {
    await apiSend<unknown>("DELETE", "/config/permissions/folders", { path });
    removeFolder(path);
  } catch {
    showToast("Could not update permissions — nothing was changed", "blocked");
  }
}

/**
 * Remove an allowed command and persist to the gateway.
 * Only removes from the UI list on 2xx; shows an error toast on failure.
 */
export async function removeCommandLive(command: string): Promise<void> {
  const { removeCommand, showToast } = useStore.getState();
  if (USE_MOCKS) {
    removeCommand(command);
    return;
  }
  try {
    await apiSend<unknown>("DELETE", "/config/permissions/commands", { command });
    removeCommand(command);
  } catch {
    showToast("Could not update permissions — nothing was changed", "blocked");
  }
}

/**
 * Toggle an operator tool's enabled state and persist to the gateway.
 * Reads current `on` value, sends PUT with the flipped boolean; only mutates
 * the store on 2xx.
 */
export async function toggleOpToolLive(id: string): Promise<void> {
  const { opTools, toggleOpTool, showToast } = useStore.getState();
  if (USE_MOCKS) {
    toggleOpTool(id);
    return;
  }
  const tool = opTools.find((t) => t.id === id);
  if (!tool) return;
  const enabled = !tool.on;
  try {
    await apiSend<unknown>("PUT", `/capabilities/${id}/enabled`, { enabled });
    toggleOpTool(id);
  } catch {
    showToast("Could not update permissions — nothing was changed", "blocked");
  }
}

/**
 * Toggle memory flags and persist to the gateway.
 */
export async function setMemoryLive(
  patch: Partial<{ enable_session_history: boolean; enable_semantic_memory: boolean }>
): Promise<void> {
  if (USE_MOCKS) return;
  try {
    await apiSend<GatewayConfig>("PUT", "/config/memory", { memory: patch });
  } catch {
    // Network errors surface the reconnecting banner via client.ts callback.
  }
}
