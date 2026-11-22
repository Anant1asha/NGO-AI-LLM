// ============================================================
// Hachi Web App — live-data bootstrap (foundation)
//
// Each wired domain module (lib/data/domains/<x>.ts) self-registers a loader
// via registerLoader() at import time. bootstrapLiveData() runs them all on
// app mount (called from routes/__root.tsx). Domains hydrate the Zustand store
// via store.hydrate(); on failure they leave the seeded fixtures in place and
// flag store.reconnecting so the UI degrades gracefully instead of going blank.
//
// Integration note: the side-effecting imports at the bottom pull each domain
// module in so its registerLoader() runs. Add one import line per domain.
// ============================================================

export type Loader = () => Promise<void>;

const loaders: { name: string; fn: Loader }[] = [];

/** Register a domain loader. Idempotent per name. */
export function registerLoader(name: string, fn: Loader): void {
  if (loaders.some((l) => l.name === name)) return;
  loaders.push({ name, fn });
}

/** Run every registered loader concurrently; never throws. */
export async function bootstrapLiveData(): Promise<void> {
  await Promise.allSettled(loaders.map((l) => l.fn()));
}

export function registeredLoaderNames(): string[] {
  return loaders.map((l) => l.name);
}

// --- IMPORTANT: do NOT import domain modules here -----------------------------
// This module must have ZERO imports of domains/*. Each domain calls
// registerLoader() at import time, so importing them here creates a cycle
// (live -> domain -> live) where the domain runs registerLoader() before this
// module's `const loaders` has been initialized — a temporal-dead-zone throw
// ("Cannot access 'loaders' before initialization") that blanks the whole app.
// Eager registration lives in ./bootstrap.ts, which imports THIS module first.
