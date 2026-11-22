// ============================================================
// Tests for the stale-while-revalidate query cache (cache.ts).
//
// The `now` seam (_setNow) lets tests advance time without real timers.
// Each test calls _setNow() in beforeEach and restores it in afterEach so
// the clock is always deterministic and tests are independent.
// ============================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  loadCached,
  invalidate,
  invalidateAll,
  DEFAULT_TTL_MS,
  _setNow,
} from './cache'

// Vitest resets module state between test files but NOT between tests within
// a file.  We flush the internal cache map before every test so call-count
// assertions start from a clean slate.
beforeEach(() => {
  // Flush cached entries by invalidating everything (uses the public API).
  invalidateAll()
})

afterEach(() => {
  // Restore the real clock.
  _setNow(Date.now)
})

// ---- helpers ----

/** Create a vi.fn() that resolves immediately (simulates a domain loader). */
function makeLoader() {
  return vi.fn(async () => undefined as void)
}

/** Advance the fake clock by `ms` milliseconds from `base`. */
function advancedClock(base: number, ms: number): () => number {
  return () => base + ms
}

// ============================================================
// 1. First call runs the loader; second call within TTL does NOT.
// ============================================================

describe('loadCached — within-TTL dedup', () => {
  it('calls the loader on first invocation', async () => {
    const loader = makeLoader()
    await loadCached('test-key', loader)
    expect(loader).toHaveBeenCalledOnce()
  })

  it('does NOT call the loader again if called within the TTL', async () => {
    const base = 1_000_000
    _setNow(() => base) // freeze at base

    const loader = makeLoader()

    await loadCached('within-ttl', loader)
    expect(loader).toHaveBeenCalledOnce()

    // Advance by half the default TTL — still fresh.
    _setNow(advancedClock(base, DEFAULT_TTL_MS / 2))
    await loadCached('within-ttl', loader)

    expect(loader).toHaveBeenCalledOnce() // no second call
  })
})

// ============================================================
// 2. After TTL expiry, loadCached runs the loader again.
// ============================================================

describe('loadCached — after TTL expiry', () => {
  it('revalidates in the background after the TTL elapses', async () => {
    const base = 2_000_000
    _setNow(() => base)

    const loader = makeLoader()

    await loadCached('expired-key', loader, { ttlMs: 500 })
    expect(loader).toHaveBeenCalledOnce()

    // Advance past the TTL.
    _setNow(advancedClock(base, 501))
    await loadCached('expired-key', loader, { ttlMs: 500 })

    expect(loader).toHaveBeenCalledTimes(2)
  })

  it('stamps the new loadedAt after a successful revalidation', async () => {
    const base = 3_000_000
    _setNow(() => base)

    const loader = makeLoader()

    await loadCached('restamp', loader, { ttlMs: 500 })

    // Advance past TTL so a revalidation runs.
    const t1 = base + 600
    _setNow(() => t1)
    await loadCached('restamp', loader, { ttlMs: 500 })
    expect(loader).toHaveBeenCalledTimes(2)

    // Now advance LESS than TTL from t1 — should be fresh again.
    _setNow(advancedClock(t1, 100))
    await loadCached('restamp', loader, { ttlMs: 500 })
    expect(loader).toHaveBeenCalledTimes(2) // no third call
  })
})

// ============================================================
// 3. force: true bypasses the TTL.
// ============================================================

describe('loadCached — force option', () => {
  it('always calls the loader when force is true, even if fresh', async () => {
    const base = 4_000_000
    _setNow(() => base)

    const loader = makeLoader()

    await loadCached('force-key', loader)
    expect(loader).toHaveBeenCalledOnce()

    // Still within TTL, but force.
    _setNow(advancedClock(base, 1)) // 1 ms later — definitely fresh
    await loadCached('force-key', loader, { force: true })

    expect(loader).toHaveBeenCalledTimes(2)
  })
})

// ============================================================
// 4. invalidate(key) causes the next loadCached to refetch.
// ============================================================

describe('invalidate', () => {
  it('marks a key stale so the next loadCached refetches', async () => {
    const base = 5_000_000
    _setNow(() => base)

    const loader = makeLoader()

    await loadCached('inv-key', loader)
    expect(loader).toHaveBeenCalledOnce()

    // Within TTL — would normally be a no-op.
    _setNow(advancedClock(base, 1))
    await loadCached('inv-key', loader)
    expect(loader).toHaveBeenCalledOnce() // confirmed no-op

    // Now invalidate and call again (still within TTL period from original stamp).
    invalidate('inv-key')
    await loadCached('inv-key', loader)

    expect(loader).toHaveBeenCalledTimes(2) // must have refetched
  })

  it('only invalidates the specified key, not others', async () => {
    const base = 5_500_000
    _setNow(() => base)

    const loaderA = makeLoader()
    const loaderB = makeLoader()

    await loadCached('key-a', loaderA)
    await loadCached('key-b', loaderB)

    invalidate('key-a')

    _setNow(advancedClock(base, 1))
    await loadCached('key-a', loaderA)
    await loadCached('key-b', loaderB)

    expect(loaderA).toHaveBeenCalledTimes(2) // refetched
    expect(loaderB).toHaveBeenCalledOnce()   // still fresh
  })
})

// ============================================================
// 5. Concurrent calls share one in-flight loader (dedup).
//    A rejected loader does NOT stamp fresh (next call retries).
// ============================================================

describe('loadCached — concurrent dedup and rejection handling', () => {
  it('concurrent calls for the same key share one in-flight loader', async () => {
    const base = 6_000_000
    _setNow(() => base)

    let resolveLoader!: () => void
    const loaderPromise = new Promise<void>((res) => {
      resolveLoader = res
    })
    const loader = vi.fn(() => loaderPromise)

    // Fire two concurrent calls before the loader resolves.
    const p1 = loadCached('concurrent', loader)
    const p2 = loadCached('concurrent', loader)

    // Resolve the shared in-flight promise.
    resolveLoader()
    await Promise.all([p1, p2])

    // dedupe() ensures only ONE call to the loader function.
    expect(loader).toHaveBeenCalledOnce()
  })

  it('a rejected loader does NOT stamp fresh — next call retries', async () => {
    const base = 7_000_000
    _setNow(() => base)

    const loader = vi
      .fn()
      .mockRejectedValueOnce(new Error('network error'))
      .mockResolvedValue(undefined)

    // First call: loader rejects.
    // loadCached / dedupe wraps in a try-catch, but our loader throws through
    // dedupe.  dedupe removes the in-flight entry on settle regardless, so
    // subsequent calls will retry.
    //
    // NOTE: The rejection propagates to the awaiting caller here; in production
    // loaders swallow errors internally and always resolve — this test ensures
    // that even if a loader rejects, the cache entry is NOT stamped fresh.
    try {
      await loadCached('reject-key', loader)
    } catch {
      // expected — suppress so the test continues
    }

    // Key should NOT be fresh (no stamp on failure).
    // A second call should invoke the loader again.
    _setNow(advancedClock(base, 1))
    await loadCached('reject-key', loader)

    expect(loader).toHaveBeenCalledTimes(2)
  })
})

// ============================================================
// 6. invalidateAll() clears every key.
// ============================================================

describe('invalidateAll', () => {
  it('marks all keys stale so the next loadCached refetches each', async () => {
    const base = 8_000_000
    _setNow(() => base)

    const loaderA = makeLoader()
    const loaderB = makeLoader()

    await loadCached('all-a', loaderA)
    await loadCached('all-b', loaderB)

    invalidateAll()

    _setNow(advancedClock(base, 1))
    await loadCached('all-a', loaderA)
    await loadCached('all-b', loaderB)

    expect(loaderA).toHaveBeenCalledTimes(2)
    expect(loaderB).toHaveBeenCalledTimes(2)
  })
})

// ============================================================
// 7. Custom ttlMs per call.
// ============================================================

describe('loadCached — custom TTL', () => {
  it('respects a short custom TTL', async () => {
    const base = 9_000_000
    _setNow(() => base)

    const loader = makeLoader()

    await loadCached('short-ttl', loader, { ttlMs: 100 })
    expect(loader).toHaveBeenCalledOnce()

    // Within custom TTL.
    _setNow(advancedClock(base, 50))
    await loadCached('short-ttl', loader, { ttlMs: 100 })
    expect(loader).toHaveBeenCalledOnce()

    // Past custom TTL.
    _setNow(advancedClock(base, 101))
    await loadCached('short-ttl', loader, { ttlMs: 100 })
    expect(loader).toHaveBeenCalledTimes(2)
  })

  it('DEFAULT_TTL_MS is 30 000 ms', () => {
    expect(DEFAULT_TTL_MS).toBe(30_000)
  })
})
