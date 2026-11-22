// ============================================================
// Hachi Web App — setup / onboarding domain
//
// Endpoints:
//   GET  /setup        → { state: OnboardingState, needs_setup: boolean, environment: object }
//   POST /setup/apply  → { ok, plan, state }
//
// Wires the wizard's setup store slice (key, safety, google, channel, routine)
// to the real gateway. The wizard's optimistic control flow (step navigation,
// toggles) is left intact in store.ts. This module only:
//   1. Loads real onboarding state on mount and hydrates the slice
//   2. Posts the collected plan on Finish
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { dedupe } from "../dedupe";
import { useStore } from "../../store/store";
import type { SafetyLevel } from "../types";

// ---- gateway shapes (mirror Python dataclasses exactly) ----

/** OnboardingState from hachi.core.onboarding */
interface GatewayOnboardingState {
  setup_version?: number;
  selected_tier?: string | null;
  completed_steps?: string[];
  last_seen_release?: string | null;
  migration_markers?: Record<string, string>;
}

interface GatewaySetupResponse {
  state: GatewayOnboardingState;
  needs_setup: boolean;
  environment: {
    anthropic_env?: boolean;
    openai_env?: boolean;
    groq_env?: boolean;
    together_env?: boolean;
    deepseek_env?: boolean;
    openrouter_env?: boolean;
    gemini_env?: boolean;
    ollama_cli?: boolean;
    project_dir?: string | null;
  };
}

interface GatewayApplyResponse {
  ok: boolean;
  plan: {
    tier: string;
    steps: string[];
    answers: Record<string, unknown>;
    enable_memory: boolean;
    show_integrations: boolean;
    show_advanced: boolean;
  };
  state: GatewayOnboardingState;
}

// ---- plan schema for POST /setup/apply ----

/**
 * Map wizard SafetyLevel → gateway permission_tier.
 * guarded  → sandbox   (ask before almost everything)
 * standard → guided    (ask before risky actions)
 * open     → unrestricted (full access)
 */
function safetyToPermissionTier(safety: SafetyLevel): string {
  switch (safety) {
    case "guarded": return "sandbox";
    case "open":    return "unrestricted";
    default:        return "guided";
  }
}

/** Build the plan payload that apply_setup expects from the wizard's answers. */
interface WizardAnswers {
  key: string;
  safety: SafetyLevel;
  routine: boolean;
  google: boolean;
  channel: boolean;
}

function buildApplyPlan(answers: WizardAnswers): Record<string, unknown> {
  const permissionTier = safetyToPermissionTier(answers.safety);

  // Provider block: always anthropic (the only provider the wizard exposes).
  // api_key_env is the conventional env-var name the gateway resolves the key
  // from; the raw key itself is sent separately as `api_key` (below).
  const provider: Record<string, string> = {
    kind: "anthropic",
    model: "claude-haiku-4-5",
    api_key_env: "ANTHROPIC_API_KEY",
  };
  // If the user typed a non-empty key, send the RAW secret as `api_key`. The
  // gateway persists it to the OS secret store + process env under
  // ANTHROPIC_API_KEY and records only the env-var name in config — the raw key
  // never lands in a config file. (Sending it as `api_key_ref` was the old bug:
  // that field is a reference *name*, not a secret, so the key was dropped.)
  const rawKey = answers.key.trim();
  if (rawKey) {
    provider.api_key = rawKey;
  }

  // Integrations block: only include google if the user connected it.
  // "channel" (Slack/WhatsApp) has no capability id in the gateway config —
  // it's purely a UX toggle with no backend analog yet, so we omit it.
  const integrations: Record<string, { enabled: boolean }> = {};
  if (answers.google) {
    integrations["gmail"] = { enabled: true };
  }

  return {
    tier: "lightning",
    steps: ["welcome", "provider", "safety", "finish"],
    answers: {
      provider,
      permission_tier: permissionTier,
      ...(Object.keys(integrations).length > 0 ? { integrations } : {}),
    },
    enable_memory: true,
    show_integrations: false,
    show_advanced: false,
  };
}

// ---- loader ----

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, the setup slice should not
// be pre-populated from seeded fixture defaults.
let _hasEverSucceeded = false;

/**
 * Load onboarding state from the gateway and hydrate the setup slice.
 *
 * Conservative approach: only sets field values the wizard doesn't already
 * derive from its own defaults. Does NOT force the modal open — only sets
 * a marker so consumers can check `needs_setup` if they choose to act on it.
 *
 * Safety level mapping (reverse of safetyToPermissionTier):
 *   sandbox       → guarded
 *   guided        → standard
 *   unrestricted  → open
 *
 * In live mode, on first-load failure the setup slice is left at its
 * structural defaults (no content from fixtures). After a successful first
 * fetch, subsequent failures preserve the last known real gateway state.
 */
export function loadSetup(): Promise<void> {
  return dedupe("setup", _loadSetupImpl);
}

async function _loadSetupImpl(): Promise<void> {
  if (USE_MOCKS) return;

  try {
    const raw = await apiGet<GatewaySetupResponse>("/setup");

    const store = useStore.getState();
    const currentSetup = store.setup;

    // The UI safety level (Guarded/Standard/Open) is owned SOLELY by the config
    // domain, which reads it from permissions.tier — the authoritative device
    // permission setting (loadConfig → adaptTier). This loader must NOT derive
    // safety from selected_tier: selected_tier is the *onboarding wizard* tier
    // (lightning/recommended/enhanced/power), a different axis entirely. Mapping
    // it to a safety level here (e.g. lightning→standard) clobbered the correct
    // value hydrated by loadConfig on every boot — that is why picking "Open"
    // reverted to "Standard". We only carry over the wizard tier (for the
    // Settings tier picker) and leave safety untouched.
    const WIZARD_TIERS = ["lightning", "recommended", "enhanced", "power"] as const;
    const rawTier = raw.state?.selected_tier ?? currentSetup.tier ?? "lightning";
    const selectedTier = (WIZARD_TIERS as readonly string[]).includes(rawTier)
      ? (rawTier as (typeof WIZARD_TIERS)[number])
      : "lightning";

    // Determine if an API key is already set in the environment.
    const keyAlreadySet = Boolean(raw.environment?.anthropic_env);

    store.hydrate({
      setup: {
        ...currentSetup,
        keyAlreadySet,
        tier: selectedTier,
      },
    });

    _hasEverSucceeded = true;
  } catch {
    // The setup slice has no data arrays to clear — it's a wizard form shape.
    // On first-load failure we leave the slice at its structural defaults
    // (open: false, step: 0, key: "", safety: "standard", …) which were set
    // by domainDefaults() and are benign empty-form values, not misleading
    // fixture data. After first success, last-known-good gateway state is kept.
    // Reconnecting flag is managed centrally by client.ts via the registered callback.
  }
}

registerLoader("setup", loadSetup);

// ============================================================
// API-key validation
// ============================================================

/**
 * Client-side format check for Anthropic API keys.
 *
 * Rules (as of 2026):
 *   - Must start with "sk-ant-"
 *   - Total length ≥ 100 characters (real keys are ~108 chars)
 *
 * Returns a precise error string, or null when the format looks plausible.
 */
export function checkKeyFormat(key: string): string | null {
  const trimmed = key.trim();
  if (!trimmed.startsWith("sk-ant-")) {
    return "Anthropic keys start with sk-ant- — check that you copied the full key.";
  }
  if (trimmed.length < 100) {
    return `Key looks too short (${trimmed.length} chars) — Anthropic keys are ~108 characters.`;
  }
  return null; // format looks plausible
}

export type KeyValidationResult =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "format-error"; message: string }
  | { status: "valid" }
  | { status: "invalid"; message: string }
  | { status: "network-error"; message: string };

/**
 * Validate an Anthropic API key:
 *   1. Client-side format check (prefix + length).
 *   2. If format passes, POST to /config/provider/validate for a real round-trip.
 *
 * The gateway endpoint (POST /config/provider/validate) is implemented server-side
 * in src/hachi/gateway/fastapi_app.py (post_provider_validate → control_plane.validate_provider).
 * It may return HTTP 503 if the validate_provider handler was not injected at gateway
 * startup, in which case we surface a network-error rather than claiming the key is valid.
 *
 * In mock mode: returns "valid" immediately (format check only, same behaviour as before).
 *
 * The returned promise NEVER rejects; all error states are encoded in KeyValidationResult.
 */
export async function validateKey(key: string): Promise<KeyValidationResult> {
  const formatError = checkKeyFormat(key);
  if (formatError) {
    return { status: "format-error", message: formatError };
  }

  // Mock mode: skip the network call, trust the format check.
  if (USE_MOCKS) {
    return { status: "valid" };
  }

  try {
    // POST /config/provider/validate — body mirrors ProviderRequest schema.
    // We send only `api_key`; the gateway inspects it without persisting.
    await apiSend<unknown>("POST", "/config/provider/validate", {
      provider: {
        kind: "anthropic",
        api_key: key.trim(),
      },
    });
    return { status: "valid" };
  } catch (err: unknown) {
    // Distinguish a clear 401/400 "key rejected" from a 503/network failure.
    // apiSend throws an Error whose message contains the HTTP status text.
    const msg = err instanceof Error ? err.message : String(err);
    const lower = msg.toLowerCase();
    if (
      lower.includes("401") ||
      lower.includes("unauthorized") ||
      lower.includes("invalid") ||
      lower.includes("forbidden")
    ) {
      return { status: "invalid", message: "The gateway rejected this key — double-check it and try again." };
    }
    // 503 means the validate handler wasn't wired at startup; still show the issue clearly.
    return { status: "network-error", message: "Could not reach the gateway to validate (format check passed)." };
  }
}

// ---- mutation wrapper ----

/**
 * POST /setup/apply — call on the final wizard step (Finish).
 *
 * In mock mode: short-circuits immediately (returns a mock-ok result).
 * In live mode: builds the plan from wizard answers and posts it.
 *
 * Errors are caught and surfaced via setReconnecting(true); they do NOT
 * throw so the wizard's optimistic close flow still runs.
 *
 * Returns the gateway response (or null on error / mock).
 */
export async function applySetup(answers: WizardAnswers): Promise<GatewayApplyResponse | null> {
  if (USE_MOCKS) {
    // Short-circuit: let the optimistic store flow handle everything.
    return null;
  }

  const plan = buildApplyPlan(answers);

  try {
    const result = await apiSend<GatewayApplyResponse>("POST", "/setup/apply", { plan });
    return result;
  } catch {
    // Non-fatal: the wizard already optimistically updated the store.
    // Network errors surface the reconnecting banner via client.ts callback.
    return null;
  }
}

/**
 * Persist a single provider API key (with optional name/model) via the
 * provider-only step of POST /setup/apply. Used by the Settings "edit provider"
 * flow, which only needs to store/rotate the key — not run the full wizard.
 *
 * Unlike applySetup, this PROPAGATES errors so the Settings screen can keep the
 * editor open and surface a save-failed toast. No-ops in mock mode.
 */
export async function applyProviderKey(input: {
  kind: string;
  model: string;
  apiKey: string;
}): Promise<void> {
  if (USE_MOCKS) return;
  await apiSend<GatewayApplyResponse>("POST", "/setup/apply", {
    plan: {
      tier: "lightning",
      steps: ["provider"],
      answers: {
        provider: {
          kind: input.kind,
          model: input.model,
          api_key: input.apiKey,
          api_key_env: "ANTHROPIC_API_KEY",
        },
      },
      enable_memory: false,
      show_integrations: false,
      show_advanced: false,
    },
  });
}

// ---- setup tier (Settings picker) ----

export type WizardTier = "lightning" | "recommended" | "enhanced" | "power";

// Mirror of hachi.core.onboarding.TIER_STEP_PLANS. The gateway appends these to
// completed_steps and records selected_tier = tier; enhanced/power flip
// show_integrations on so the integrations step + connectors become available.
const TIER_STEP_PLANS: Record<WizardTier, string[]> = {
  lightning: ["welcome", "provider", "safety", "finish"],
  recommended: ["welcome", "provider", "safety", "memory", "finish"],
  enhanced: ["welcome", "provider", "safety", "memory", "integrations", "finish"],
  power: ["welcome", "provider", "safety", "memory", "integrations", "advanced", "finish"],
};

/**
 * Persist a setup-tier change from Settings WITHOUT re-running the wizard.
 *
 * Sends a minimal plan: only `tier` (+ its step plan) with an EMPTY `answers`
 * object. apply_setup mutates the provider, permission tier, memory flags, and
 * integrations only when the matching answer keys are present (see
 * onboarding.apply_setup), so this leaves all of them untouched and simply
 * records selected_tier = tier. The store is updated optimistically first so the
 * picker reflects the choice immediately even before the round-trip completes.
 */
export async function setTierLive(tier: WizardTier): Promise<void> {
  const store = useStore.getState();
  const previousTier = store.setup.tier;
  store.hydrate({ setup: { ...store.setup, tier } });
  if (USE_MOCKS) {
    store.showToast("Setup tier updated", "success");
    return;
  }
  try {
    await apiSend<GatewayApplyResponse>("POST", "/setup/apply", {
      plan: {
        tier,
        steps: TIER_STEP_PLANS[tier],
        answers: {},
        enable_memory: true,
        show_integrations: tier === "enhanced" || tier === "power",
        show_advanced: tier === "power",
      },
    });
    store.showToast("Setup tier updated", "success");
  } catch {
    // Roll back the optimistic tier change — a silently-failed apply must not look saved.
    store.hydrate({ setup: { ...store.setup, tier: previousTier } });
    store.showToast("Could not update setup tier — is Hachi running?", "blocked");
  }
}
