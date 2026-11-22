# Web UI ↔ Gateway wiring contract

This is the shared contract for wiring the Hachi web app to the real gateway.
The **foundation** (this file's siblings) is built and frozen. Each domain agent
wires ONE domain by adding files under `domains/` and editing its assigned
route — never touching another domain's files.

## Foundation you build on (do NOT edit these)

- `client.ts` — `apiGet<T>(path, params?, signal?)`, `apiSend<T>(method, path, body?, signal?)`,
  `USE_MOCKS`, `API_BASE`, `ApiError`, `DATA_GAPS`. Paths are gateway-relative and
  resolve under `/api` (dev proxy) → e.g. `apiGet("/approvals")`.
- `sse.ts` — `streamSSE(path, { onMessage, onOpen, onError, onClose }, { params, signal })`.
  Frames arrive as `{ id?, event, data }` where `data` is JSON text.
- `live.ts` — `registerLoader(name, fn)` + `bootstrapLiveData()`. Your domain module
  calls `registerLoader("<domain>", load<Domain>)` at top level so it self-registers.
- `store/store.ts` — `hydrate(patch: Partial<State>)` shallow-merges gateway-derived
  state; `setReconnecting(v)` flags offline. Read current state with
  `useStore.getState()`. The store already holds every UI type as fixtures.

## The loader pattern (every domain follows this)

```ts
// lib/data/domains/<x>.ts
import { apiGet, apiSend, USE_MOCKS } from "../client";
import { registerLoader } from "../live";
import { useStore } from "../../store/store";
import type { /* UI types */ } from "../types";

// 1. Raw gateway response shape (mirror the Python dataclass/dict exactly).
interface Gateway<X> { /* ... */ }

// 2. Pure adapter: gateway shape -> existing UI type.
function adapt(raw: Gateway<X>): UiType { /* ... */ }

// 3. Loader: fetch -> map -> hydrate. NEVER throws; degrades to fixtures.
export async function loadX(): Promise<void> {
  if (USE_MOCKS) return; // keep seeded fixtures
  try {
    const raw = await apiGet<Gateway<X>>("/x");
    useStore.getState().hydrate({ x: raw.items.map(adapt) });
    useStore.getState().setReconnecting(false);
  } catch {
    useStore.getState().setReconnecting(true); // leave fixtures in place
  }
}
registerLoader("x", loadX);

// 4. Mutation wrappers (optional): real call + optimistic store update.
export async function doThing(id: string) {
  useStore.getState().someOptimisticAction(id); // instant UI
  if (USE_MOCKS) return;
  try { await apiSend("POST", `/x/${id}`, { ... }); }
  catch { useStore.getState().setReconnecting(true); }
}
```

Then in your route, call the loader on mount and use the mutation wrappers:

```ts
useEffect(() => { void loadX(); }, []);
```

(`bootstrapLiveData()` already runs every registered loader once on app mount from
`__root.tsx`; the per-route `useEffect` is for refresh-on-navigate. Both are fine —
loaders are idempotent.)

## Hard rules

1. **Disjoint files.** Only create/edit the files listed in YOUR task. Do not edit
   `client.ts`, `sse.ts`, `live.ts`, `types.ts`, `fixtures.ts`, `__root.tsx`,
   `index.tsx`, or another domain's route/module.
   - Exception: the **chat/streaming** agent owns `store.ts` streaming actions.
   - If you need a NEW shared UI type, define it locally in your domain module, not in `types.ts`.
2. **Adapters are pure and total.** Tolerate missing/extra fields (`?? fallback`).
   Gateway omits null fields (`exclude_none=True`), so treat most fields optional.
3. **Never blank the UI.** On any fetch/SSE error: `setReconnecting(true)` and keep
   the fixtures. No thrown errors escape a loader.
4. **Preserve types.** `npm run typecheck` must pass for your files. Match the
   existing UI types in `types.ts` exactly — adapt the gateway shape TO them.
5. **No new deps.** Use `fetch` (via the client) only. No axios/react-query/etc.
6. Keep IDs stable for React keys. UI types often use numeric `id`; gateway uses
   string ids — keep the string in a side field and synthesize a stable numeric id
   (e.g. a hash) if the UI type demands `number`, or relax the local handling.

## Gateway endpoints + real response shapes

All paths below are passed to `apiGet`/`apiSend` verbatim (they resolve under `/api`).
Shapes are derived from `src/hachi/` — verify against source if unsure.

### Approvals — `routes/approvals.tsx`
- `GET /approvals` → `{ pending: PendingApproval[] }`
  - `PendingApproval = { request_id: string; operation: string; tool: string; target: string; reason: string; policy_summary: string }`
- `POST /approvals/{request_id}` body `{ action: "approve"|"deny"|"allow_once"; rationale?: string }` → `{ resolved: true }`
- `GET /permissions/audit?limit=50` → `PermissionAudit[]`
  - `PermissionAudit = { operation: string; tool: string; target: string; decision: string; reason: string }`
- Map to UI `Approval` (types.ts). Note the UI `Approval` has rich fields
  (icon/risk/expiresAt/totalMs) the gateway lacks — synthesize sensible defaults
  (risk from operation heuristics, no countdown / expiresAt:0). Map decisions
  allow→"allow_once", always→"approve", decline→"deny".

### Work: jobs + schedules — `routes/work.tsx`
- `GET /jobs/active` → `Job[]` where `Job = { job_id: string; kind: string; label: string; status: string }`
- `GET /jobs/failed?limit=20` → `JobFailure[]` where
  `JobFailure = { job_id; kind; label; attempt: number; error: string; duration_seconds: number; timestamp: string }`
- `GET /schedules` → `{ schedules: Schedule[] }` where
  `Schedule = { schedule_id; name; task; kind: "interval"|"cron"; interval_seconds?: number|null; cron?: string|null; timezone: string; condition_skill?: string|null; enabled: boolean; created_at: string; last_run?: string|null; next_run?: string|null }`
- `PUT /schedules/{schedule_id}/enabled` body `{ enabled: boolean }` → `{ ok, schedule_id, enabled }`
- `DELETE /schedules/{schedule_id}` → `{ ok, schedule_id }`
- Map jobs→UI `Run`/`FailedTask`, schedules→UI `Routine` (paused = !enabled,
  schedule = humanize cron/interval, next = next_run).

### Operator observability (NO route — hydrate store, components auto-render) — `domains/operator.ts` only
- `GET /subagents/reports?top_k=10` → `SubAgentReport[]` where
  `SubAgentReport = { role; status; duration_seconds: number; iterations: number; summary: string }` → UI `PackMember[]` (packRoster)
- `GET /runtime/events?limit=100` → `RuntimeEvent[]` where
  `RuntimeEvent = { name: string; payload: object; timestamp: string; sequence: number }`
  → derive UI `ActivityEvent[]` (events) and `ToolCall[]` (toolCalls from `tool.call.*` events).
- Do NOT edit a route. Just `registerLoader` + hydrate `packRoster`, `events`, `toolCalls`.

### Chat / sessions / streaming — `routes/conversation.tsx`, `routes/run.tsx`, `store.ts`
- Session lifecycle: `POST /sessions` body `{ client_id, surface, protocol_version: "1.0", capabilities: [] }`
  → `{ accepted, session_id, protocol_version, server_capabilities }`. Reuse one session id.
- Send: `POST /sessions/{session_id}/messages` body `{ prompt }` → `{ session_id, response }` (full turn, blocking).
- Stream: `GET /sessions/{session_id}/stream?after=<seq>` (SSE). Event types include
  `text.stream.delta` (payload `{ text }`), `tool.call.started`/`tool.call.completed`
  (payload `{ name, ... }`), `permission.requested`, `session.chat.completed`,
  `usage.updated` (payload `{ total_tokens, estimated_cost_usd }`).
- Replace the simulated `stream()` timers in `store.ts` (`startTask`/`sendMessage`,
  `stopStreaming`, `icAllow`/`icDeny`) with: create-session-once → POST message in
  background → open SSE → append `text.stream.delta` to the hachi message text;
  turn tool events into action cards; `usage.updated` → taskSpent/spent;
  `permission.requested` → inContext leash. Keep the mock path when `USE_MOCKS`.
- `GET /sessions?limit=10` → recent sessions (verify shape via `core/session_store.py`
  `get_recent_sessions`) → UI `Session[]`.
- Live run (`run.tsx`): if time permits, drive `runLines`/`runPack`/`runSteps` from the
  same SSE stream; otherwise leave the existing simulation and add a `// TODO(live-run)`.

### Settings / config / models — `routes/settings.tsx`
- `GET /config` → effective config (`model_dump`, null fields omitted). Top-level keys
  include `provider { kind, model, base_url?, api_key_ref?, api_key_env? }`,
  `permissions { tier: "sandbox"|"guided"|"unrestricted", ... }`,
  `memory { enable_session_history, enable_semantic_memory }`, `capabilities { ... }`.
  Verify exact shape via `hachi.core.config` model / `load_effective_config()`.
- `GET /models` → `Model[]` where `Model = { id; label; provider; recommended: boolean }`.
- `PUT /config/provider` body `{ provider: { kind?, model?, base_url?, api_key?, api_key_ref?, api_key_env? } }` → updated config.
  Send a NEW raw key as `api_key` (a secret): the gateway writes it to the OS secret store + process
  env and stores only the env-var name in config. `api_key_ref`/`api_key_env` are reference *names*,
  never raw secrets. A provider/credential change reboots the live session so it applies immediately.
- `POST /config/provider/validate` body `{ provider: {...} }` → `{ ok, errors[], warnings[] }`.
- `PUT /config/permissions` body `{ permissions: { tier } }` → updated config.
- `PUT /config/memory` body `{ memory: { enable_session_history?, enable_semantic_memory? } }` → updated config.
- Map config → UI `safety` (tier: sandbox→guarded, guided→standard, unrestricted→open),
  `provider`, `allowedFolders`/`allowedCommands` (from permissions if present, else keep fixtures),
  `askRules`/`opTools` (keep fixtures — no backing field). Models → provider model dropdown.

### Setup wizard — `components/overlays/SetupWizard.tsx`
- `GET /setup` → `{ state: OnboardingState, needs_setup: boolean, environment: object }`.
  Inspect `OnboardingState` via `hachi.core.onboarding` (`resume_state`).
- `POST /setup/apply` body `{ plan: {...} }` → `{ ok, plan, state }`.
- Map gateway setup state → the wizard's `setup` store slice; on finish call
  `/setup/apply`. Keep the mock flow when `USE_MOCKS`.

### Skills + Integrations/MCP — `routes/skills.tsx`, `routes/integrations.tsx`
- `GET /capabilities` → `Capability[]` where
  `Capability = { id: string; kind: "native_integration"; enabled: boolean; configured: boolean; secret_ref?: string|null }`.
  These are NATIVE INTEGRATIONS, not `.og` skills. So:
  - `integrations.tsx`: map capabilities → UI `Integration[]` (status from
    enabled/configured: configured&enabled→"connected", configured&!enabled→"degraded",
    else "none"). Also wire `GET /runtime/mcp/inventory` →
    `{ server_count, total_tool_count, servers: { name, status, tool_count, tools }[] }`
    → UI `McpServer[]`/`McpTool[]`.
  - `skills.tsx`: there is NO `.og` skill-list endpoint (DATA GAP "skills-og"). Keep the
    skills fixtures, but add a small visible "preview — not yet wired to the gateway"
    badge so the gap is honest. Do NOT fake it from `/capabilities`.

## Gap screens (leave on mock; add a visible "preview" badge if you own the route)
Memory (`memory.tsx`), OG explorer (`og.tsx`), Authoring (`authoring.tsx`),
Spend analytics, and the `.og` skill list have NO gateway endpoint. They stay on
fixtures. See `DATA_GAPS` in `client.ts`.

## Verify before you finish
Run `npm run typecheck` (from `frontend/`). Your files must compile clean. Do not
run `vite build` or start servers — the orchestrator does final integration.
Return a short summary: files created/edited, endpoints wired, and any gap/uncertainty.
