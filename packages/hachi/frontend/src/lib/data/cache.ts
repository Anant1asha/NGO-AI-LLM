// ============================================================
// Hachi Web App — stale-while-revalidate query cache
//
// A thin TTL cache that governs WHEN domain loaders run.
// It does NOT store fetched data — that lives in the zustand store.
// The store keeps showing the previous slice while a background
// refetch is in flight (that IS stale-while-revalidate).
//
// Usage:
//   await loadCached("memory", loadMemory, { ttlMs: 30_000 })
//
// After a mutation that changes server state:
//   invalidate("memory")
// ============================================================

import { dedupe } from "./dedupe";

/** Default TTL: 30 seconds. Named export so tests can reference it. */
export const DEFAULT_TTL_MS = 30_000;

/** Per-key freshness record. */
interface CacheEntry {
  /** Timestamp of the last successful load (from `now()`). */
  loadedAt: number;
  /** TTL used when this entry was last stamped. */
  ttlMs: number;
}

/** Options for {@link loadCached}. */
export interface LoadCachedOptions {
  /** Override the default TTL for this key (ms). */
  ttlMs?: number;
  /** If true, bypass the cache and always run the loader. */
  force?: boolean;
}

// ---- Injectable clock seam for testability ----
//
// In tests: pass `{ now: () => fakeNow }` to `_setNow()` so you can
// advance time without real timers. In production the default is Date.now.

let _now: () => number = Date.now;

/**
 * Override the clock used by the cache.
 * Intended for tests only — call with `() => Date.now` to restore.
 *
 * @internal
 */
export function _setNow(fn: () => number): void {
  _now = fn;
}

// ---- Internal state ----

const _entries = new Map<string, CacheEntry>();

// ---- Public API ----

/**
 * Load a domain (via its loader) using stale-while-revalidate semantics.
 *
 * - **Fresh** (now − loadedAt < ttlMs, no `force`): no-op. The store already
 *   holds up-to-date data.
 * - **Stale or never loaded**: run the loader (concurrent calls for the same
 *   key share one in-flight Promise via `dedupe`). On success, stamp
 *   `loadedAt`. On rejection, do NOT stamp (next call will retry).
 *
 * The store keeps showing whatever data it currently holds while the
 * refetch runs — this is the "stale-while-revalidate" part.
 *
 * @param key    Stable identifier for the domain (e.g. `"memory"`).
 * @param loader The `load<Domain>()` function to call. Must not throw
 *               (domain loaders already swallow errors internally).
 * @param opts   Optional TTL and force-refresh knobs.
 */
export async function loadCached(
  key: string,
  loader: () => Promise<void>,
  opts?: LoadCachedOptions
): Promise<void> {
  const ttlMs = opts?.ttlMs ?? DEFAULT_TTL_MS;
  const force = opts?.force ?? false;

  const entry = _entries.get(key);
  const now = _now();

  // Already fresh and no explicit force → no-op.
  if (!force && entry !== undefined && now - entry.loadedAt < entry.ttlMs) {
    return;
  }

  // Stale, never loaded, or forced.  Run the loader (deduped).
  await dedupe(`cache:${key}`, async () => {
    await loader();
    // Stamp fresh only on success.  Loaders swallow errors internally so
    // they always resolve, but be defensive: the stamp runs unconditionally
    // here because a resolved Promise means the loader completed without
    // throwing (it may have degraded to fixtures, but that's its contract).
    _entries.set(key, { loadedAt: _now(), ttlMs });
  });
}

/**
 * Mark a cache key as stale so the next {@link loadCached} call refetches.
 *
 * Use this after a mutation that changes server state for the domain,
 * e.g. after adding a memory fact: `invalidate("memory")`.
 */
export function invalidate(key: string): void {
  _entries.delete(key);
}

/**
 * Mark ALL cache keys as stale.
 *
 * Use this on a global refresh or after a reconnect so every domain
 * refetches on the next route visit.
 */
export function invalidateAll(): void {
  _entries.clear();
}
