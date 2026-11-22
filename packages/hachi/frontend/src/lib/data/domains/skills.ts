// ============================================================
// Hachi Web App — Skills domain loader
// Endpoints:
//   GET  /skills          → GatewaySkill[]  → Skill[]
//   GET  /skills/kennel   → GatewayKennelItem[] → KennelItem[]
//   POST /skills/add      → install a kennel skill
// ============================================================

import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { useStore } from "../../store/store";
import type { Skill, KennelItem } from "../types";

// ---- Gateway shapes ----

/** Raw kennel entry from GET /skills/kennel */
interface GatewayKennelItem {
  id?: string;
  name?: string;
  description?: string;
  icon?: string;
  tags?: string[];
}

interface GatewaySkill {
  name: string;
  role: string;
  keyword_count: number;
  use_count: number;
  last_used: string | null;
}

// ---- Pure adapter ----

/** Returns a human-readable relative date string or "never". */
function humanizeLastUsed(isoDate: string | null | undefined): string {
  if (!isoDate) return "never";
  try {
    const d = new Date(isoDate);
    if (isNaN(d.getTime())) return "never";
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "today";
    if (diffDays === 1) return "yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
    return `${Math.floor(diffDays / 365)}y ago`;
  } catch {
    return "never";
  }
}

/** True when last_used is null OR more than 30 days ago. */
function isStale(isoDate: string | null | undefined): boolean {
  if (!isoDate) return true;
  try {
    const d = new Date(isoDate);
    if (isNaN(d.getTime())) return true;
    const diffMs = Date.now() - d.getTime();
    return diffMs > 30 * 24 * 60 * 60 * 1000;
  } catch {
    return true;
  }
}

/** Remove duplicate skills by name, keeping the first occurrence (highest use_count when pre-sorted). */
export function deduplicateSkillsByName<T extends { name?: string }>(skills: T[]): T[] {
  const seen = new Set<string>();
  return skills.filter((s) => {
    const k = s.name ?? "";
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function adapt(raw: GatewaySkill): Skill {
  const useCount = raw.use_count ?? 0;
  return {
    id: raw.name ?? "unknown",
    icon: "sparkles",
    name: raw.name ?? "unknown",
    desc: raw.role ? `role: ${raw.role}` : "skill",
    uses: `${useCount} times`,
    lastUsed: humanizeLastUsed(raw.last_used),
    stale: isStale(raw.last_used),
  };
}

// ---- Loader ----

// Tracks whether this domain has ever received real data from the gateway.
// In live mode: until the first successful fetch, seeded fixtures must NOT be
// shown, so on failure we clear the slice instead of leaving them in place.
let _hasEverSucceeded = false;

export async function loadSkills(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const raw = await apiGet<GatewaySkill[]>("/skills");
    useStore.getState().hydrate({ skills: deduplicateSkillsByName(raw ?? []).map(adapt) });
    _hasEverSucceeded = true;
  } catch {
    if (!_hasEverSucceeded) {
      // First-load failure: clear seeded fixtures so we never present
      // fabricated skill list as if it were real gateway data.
      useStore.getState().hydrate({ skills: [] });
    }
    // Reconnecting flag is now managed centrally by client.ts via the
    // registered callback — no per-domain setReconnecting calls needed here.
  }
}

registerLoader("skills", loadSkills);

// ---- Kennel loader ----

/** Adapt a raw kennel entry to the UI KennelItem shape. */
function adaptKennelItem(raw: GatewayKennelItem): KennelItem {
  return {
    id: raw.id ?? raw.name ?? "unknown",
    icon: raw.icon ?? "sparkles",
    name: raw.name ?? raw.id ?? "Unknown skill",
    desc: raw.description ?? "",
  };
}

// Tracks whether kennel data has ever been fetched successfully.
let _kennelEverSucceeded = false;

/**
 * Load the kennel catalogue from GET /skills/kennel and hydrate the store.
 * In mock mode keeps seeded fixtures. In live mode, clears fixtures on first
 * failure so fabricated kennel items are never presented as real.
 */
export async function loadKennel(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const raw = await apiGet<GatewayKennelItem[]>("/skills/kennel");
    useStore.getState().hydrate({ kennel: (raw ?? []).map(adaptKennelItem) });
    _kennelEverSucceeded = true;
  } catch {
    if (!_kennelEverSucceeded) {
      useStore.getState().hydrate({ kennel: [] });
    }
    // Reconnecting flag managed centrally by client.ts.
  }
}

registerLoader("kennel", loadKennel);

// ---- Skill add (kennel install) ----

/**
 * Install a skill from the kennel via POST /skills/add, then refresh both
 * the installed skills list and the kennel (gateway may remove it from kennel
 * once installed). On success shows a toast; on failure shows an error toast
 * and does NOT add the skill to the local list.
 *
 * In mock mode, delegates to the store's existing confirmKennel action.
 */
export async function addSkillLive(kennelId: string): Promise<void> {
  const { showToast, kennel, confirmKennel } = useStore.getState();

  if (USE_MOCKS) {
    confirmKennel();
    return;
  }

  const item = kennel.find((k) => k.id === kennelId);
  const label = item?.name ?? kennelId;

  try {
    await apiSend<unknown>("POST", "/skills/add", { kennel_id: kennelId });
    // Refresh installed skills + kennel from gateway
    await Promise.all([loadSkills(), loadKennel()]);
    showToast(`Added ${label} — it's ready to use`, "success");
    // Close consent overlay
    useStore.getState().hydrate({ kennelConsent: null, kennelBrowseOpen: false });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : `Failed to install ${label} — please try again`;
    showToast(msg, "blocked");
  }
}
