// ============================================================
// Hachi Web App — live-data bootstrap entry
//
// Only the three domains that feed always-visible sidebar elements
// (budget/spend, session list, provider/leash) are loaded eagerly at
// boot. All other domains are loaded lazily when their route is first
// visited — each route calls its own `load<Domain>()` on mount
// (see lib/data/README.md, "The loader pattern").
//
// Imports `live.ts` FIRST so its loader registry (`const loaders`) is
// fully initialized, THEN imports the eager domain modules so each
// one's top-level registerLoader() runs against the ready registry.
// This ordering prevents the circular-import temporal-dead-zone that
// would otherwise throw "Cannot access 'loaders' before initialization".
//
// `__root.tsx` imports bootstrapLiveData from HERE (not from ./live).
// ============================================================

import { bootstrapLiveData, registeredLoaderNames } from "./live";

// ---- Eager domains (sidebar feeds only) ----
// These three run concurrently on every app mount:
//   - config.loadConfig   → provider + safety level (leash bar, settings)
//   - chat.loadSessions   → session list (sidebar)
//   - spend.loadSpend     → budget / spent (governance bar)
import "./domains/config";
import "./domains/chat";
import "./domains/spend";

// ---- Non-critical domains (lazy, per-route) ----
// These domain modules are NOT imported here and are NOT added to the
// bootstrap registry. Each owning route imports its domain module directly
// and calls `load<Domain>()` in a `useEffect(() => { ... }, [])` on mount
// (see lib/data/README.md, "The loader pattern"). Do not add
// registerLoader() calls for these here — they are self-contained.

export { bootstrapLiveData, registeredLoaderNames };
