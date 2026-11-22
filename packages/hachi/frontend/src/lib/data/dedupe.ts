// ============================================================
// Hachi Web App — in-flight request deduplication
//
// Wraps an async factory function so that concurrent callers share
// one in-flight Promise instead of firing duplicate network requests.
// The entry is removed from the map once the Promise settles, so
// subsequent calls start fresh.
//
// Usage:
//   const result = await dedupe("config", () => apiGet("/config"));
// ============================================================

const inflight = new Map<string, Promise<unknown>>();

/**
 * Deduplicate concurrent calls to `fn` under `key`.
 * If a call for `key` is already in-flight, returns the existing Promise.
 * Otherwise calls `fn`, stores the Promise, and removes it on settle.
 */
export function dedupe<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;
  const p = fn().finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}
