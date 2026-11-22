# Web UI ↔ Gateway: missing backend API contracts

Status as of 2026-06-17. The `frontend/` web app is wired to the gateway for the
domains that already have endpoints (approvals, jobs, schedules, sessions/chat
SSE, config, models, setup, capabilities, MCP inventory, subagent reports,
runtime events, permission audit). This document specifies the endpoints the web
UI still needs but the gateway does **not** yet expose. Until they exist, the
listed screens stay on seeded fixtures behind a visible "preview" flag
(`DATA_GAPS` in `frontend/src/lib/data/client.ts`).

## Conventions (match the existing gateway)

- **Where to add:** route in `src/hachi/gateway/fastapi_app.py` → method on
  `GatewayControlPlane` (`src/hachi/gateway/control_plane.py`) → handler on
  `_InProcessGatewayRuntime` (`src/hachi/cli/main.py`), wired in
  `_build_gateway_control_plane`.
- **JSON style:** `snake_case` keys; lists either returned bare (`[...]`) or under
  a single key envelope (`{"schedules": [...]}`) — both patterns already exist.
- **Auth:** all routes carry `protected_dependencies` (Bearer). Errors use the
  `ErrorResponse` `{code, message, details}` shape.
- **After adding/changing any route:** regenerate the contract:
  ```bash
  uv run hachi gateway-openapi --output openapi/hachi-openapi.json
  ```
- **Frontend side:** each item below names the `frontend/src/lib/data/domains/<x>.ts`
  loader to add (same loader pattern as the wired domains — see
  `frontend/src/lib/data/README.md`) plus the UI type it must adapt to
  (`frontend/src/lib/data/types.ts`).

Endpoints are ordered by value/effort. **#1 is nearly free — the data already exists.**

---

## 1. Skills catalogue (`.og` skill list) — HIGH VALUE, LOW EFFORT

The Skills screen (`routes/skills.tsx`) currently uses fixtures + a "preview"
badge because `/capabilities` returns native integrations, not `.og` skills. But
the data already exists: `OrchestrationContext.snapshot_skills()` returns
`SkillSnapshot(name, role, keyword_count, use_count, last_used)`
(`src/hachi/gateway/orchestrator.py:549`, `src/hachi/core/runtime_read_models.py`).
Only a route is missing.

**Proposed:**
```
GET /skills
→ 200  [ { "name": "deep_research", "role": "researcher",
           "keyword_count": 12, "use_count": 3,
           "last_used": "2026-06-16T09:00:00+00:00" | null }, ... ]
```
Wire `runtime.snapshot_skills()` through a `control_plane.skills()` method, same
shape as `subagent_reports`.

**Optional (kennel — installable skills + add/remove):** only if we want the web
UI to manage the skill set. Otherwise skip.
```
GET    /skills/available           → [ { "id", "icon", "name", "desc" } ]   # not-yet-installed
POST   /skills/{id}/install        → { "ok": true }
DELETE /skills/{id}                → { "ok": true }
```

**Frontend:** new `domains/skills.ts`; adapt `SkillSnapshot` → UI `Skill`
`{ id, icon, name, desc, uses, lastUsed, stale }` (`id=name`; `desc` from role;
`uses="${use_count} times"`; `stale` = `last_used` older than N days). Remove the
preview badge once live. Update `DATA_GAPS` (drop `"skills-og"`).

---

## 2. Memory facts — MEDIUM

The Memory screen (`routes/memory.tsx`) shows grouped facts, blocked items, a
proposed change, and recall hits. Backing store exists: `MemoryVault`
(`src/hachi/core/memory_vault.py`, collections `core_memory` / `user_profile` /
`agent_profile`) and `OrchestrationContext.query_memory_recall()` →
`MemoryRecallSnapshot(fact_id, content, category, timestamp)`
(`orchestrator.py:621`). Only read recall exists today; the rest is unmapped.

**Proposed (read):**
```
GET /memory
→ 200 {
  "groups": [
    { "id": "user_profile", "title": "About you",
      "facts": [ { "id": "<fact_id>", "text": "<content>", "source": "<category>" } ] }
  ],
  "blocked": [ { "id": "<id>", "text": "<content>", "reason": "<why blocked>" } ],
  "proposed": { "from": "<old text>", "to": "<new text>" } | null
}

GET /memory/recall?query=<q>&top_k=8
→ 200 [ { "fact": "<content>", "score": "0.82", "src": "<category>" } ]
```
`groups` maps each vault collection → a `MemGroup`. `blocked`/`proposed` can be
empty/`null` until a moderation pipeline produces them.

**Proposed (write) — only if facts are editable from the web:**
```
POST   /memory/facts            body { "group": "user_profile", "text": "..." }       → { "id": "..." }
PUT    /memory/facts/{fact_id}  body { "text": "..." }                                → { "ok": true }
DELETE /memory/facts/{fact_id}                                                        → { "ok": true }
POST   /memory/proposed/{decision}  decision ∈ approve|reject                         → { "ok": true }
```

**Frontend:** new `domains/memory.ts`; adapt to UI `MemGroup`/`Fact`/`BlockedItem`/
`ProposedChange`/`RecallHit` (`types.ts`). The store already has the optimistic
`addFact`/`saveFact`/`delFact`/`approveProposed`/`rejectProposed` actions to wrap.

---

## 3. ObjectGraph explorer — MEDIUM

The OG screen (`routes/og.tsx`) renders the `.og` skill graph with per-node token
counts at the three pass levels. Data source: the `og_engine` parser/indexer
(`src/hachi/og_engine/`). No endpoint exists.

**Proposed:**
```
GET /og/graph
→ 200 {
  "nodes": [
    { "id": "brain", "name": "brain", "kind": "root" | "skill" | "leaf",
      "index": 30, "dense": 220, "full": 1840,         # token cost per pass
      "deps": ["deep_research", "..."] }
  ]
}
```
`index`/`dense`/`full` are the Pass-1/2/3 token sizes the indexer already computes
(or can: count tokens of the `::index` / `::dense` / `::full` segments). `deps`
are the node's outgoing references.

**Frontend:** new `domains/og.ts`; adapt to UI `OgNode`
`{ id, name, kind, index, dense, full, deps }`. Drop `DATA_GAPS["og"]`.

---

## 4. Authoring (`.og` / config editor) — MEDIUM

The Authoring screen (`routes/authoring.tsx`) lists editable targets
(brain / skill / config files), shows source + a proposed diff, and applies or
reverts a patch. Data source: the workspace `.og` / config files on disk
(skill dir, `device-permissions.og`, global config). No endpoint exists.

**Proposed:**
```
GET  /authoring/targets
→ 200 [ { "name": "deep_research.og", "path": "skills/deep_research.og",
          "kind": "brain" | "skill" | "config", "dirty": false } ]

GET  /authoring/targets/{name}
→ 200 { "name": "...", "source": "<full file text>",
        "diff": [ ["", "unchanged line"], ["add", "added"], ["del", "removed"] ] }
        # diff is optional — present only when there is a pending proposed patch

POST /authoring/targets/{name}/apply    body { }   → { "ok": true, "reindexed_ms": 312 }
POST /authoring/targets/{name}/revert   body { }   → { "ok": true }
```
`diff` lines match the UI `DiffLine = ["" | "add" | "del", string]`. `apply` should
write the file and trigger a re-index (the screen shows "re-indexed in 0.3s").

**Security note:** this writes files inside the workspace. Gate writes behind the
existing `PermissionGate` roots and reject paths outside the workspace.

**Frontend:** new `domains/authoring.ts`; adapt to UI `AuthTarget` + `DiffLine`.
Drop `DATA_GAPS["authoring"]`.

---

## 5. Spend analytics — MEDIUM

The Work screen's spend panel uses per-turn token/cost rows, "tidy" (compaction)
events, and per-model totals. Data exists in pieces: `usage.updated` runtime
events carry `total_tokens` / `estimated_cost_usd`; `SessionStateSnapshot` carries
`total_tokens` / `estimated_cost_usd`; memory-compaction jobs emit events. No
aggregate endpoint exists.

**Proposed:**
```
GET /spend?session_id=<id>          # session_id optional → current/most-recent session
→ 200 {
  "turns":  [ { "n": 1, "inT": 1840, "out": 320, "cost": 0.04 } ],
  "tidies": [ { "ts": "14:32", "before": 22000, "after": 8000 } ],
  "models": [ { "name": "claude-sonnet-4-5", "tokens": 48210, "cost": 0.41,
                "color": "#..." } ]
}
```
`turns` from per-turn usage events; `tidies` from compaction job events; `models`
aggregated from usage by model. `color` can be assigned client-side if the
backend omits it.

**Frontend:** new `domains/spend.ts`; adapt to UI `SpendTurn`/`SpendTidy`/
`SpendModel`. Drop `DATA_GAPS["spend"]`.

---

## 6. Integration / capability toggle — SMALL

The Integrations screen (`routes/integrations.tsx`) reads real capabilities via
`GET /capabilities`, but its connect/disconnect buttons have no endpoint, so they
only update local state (`// TODO(no-endpoint)` in `domains/integrations.ts`).
`config.capabilities[id]` already has `enabled` / `configured` flags.

**Proposed:**
```
PUT /capabilities/{id}/enabled    body { "enabled": true }
→ 200 { "id": "gmail", "enabled": true, "configured": true }
```
(Mirror `PUT /schedules/{id}/enabled`. A full OAuth "connect" flow is a larger
feature; the enable/disable toggle is the minimum to make the buttons real.)

**Frontend:** replace the optimistic-only `connect/disconnect` wrappers in
`domains/integrations.ts` with calls to this route.

---

## 7. Chat permission decision from the web (in-context leash) — SMALL, CONTRACT CLARIFICATION

During a live chat turn the SSE stream emits `permission.requested`, and the web
shows an in-context "leash" (allow/deny). Today `allowLeashLive`/`denyLeashLive`
(`domains/chat.ts`) only clear the leash locally — they cannot actually resolve
the agent's pending permission, because **the `permission.requested` event payload
shape is not specified** and the web has no `request_id` to act on.

**Required contract:** the `permission.requested` runtime event payload MUST
include the approval-registry `request_id` (and ideally human fields), e.g.:
```
event: permission.requested
data: { "sequence": N, "event_type": "permission.requested",
        "payload": { "request_id": "<hex>", "operation": "gmail.send",
                     "tool": "gmail", "target": "priya@...",
                     "reason": "she's been waiting", "policy_summary": "..." },
        "time": "..." }
```
Then the web resolves it via the **existing** endpoint:
```
POST /approvals/{request_id}   body { "action": "allow_once" | "approve" | "deny" }
```
No new endpoint needed — just guarantee `request_id` is in the event payload.
(`domains/chat.ts handleSseMessage` currently reads `payload.request/action/why`
as a best-effort guess; align it once the real keys are fixed.)

---

## 8. Shape confirmations (no new endpoints — verify/lock these)

The following are already wired but adapted against **assumed** shapes. Confirm
them so the adapters can drop their defensive fallbacks:

- **`permission.requested` SSE payload** — see #7.
- **`GET /sessions` item shape** — `domains/chat.ts` assumes
  `{ id, started_at, ended_at, model, total_turns, title, total_tokens,
  total_cost_usd }` from `SessionStore.get_recent_sessions`
  (`src/hachi/core/session_store.py`). Confirm exact keys.
- **`GET /config` permissions sub-shape** — the Settings screen wires `safety`
  from `permissions.tier` only. If `permissions` also exposes filesystem roots and
  an allowed-command list, document those keys so `allowedFolders` /
  `allowedCommands` can be wired (currently kept as fixtures).
- **`GET /setup` `OnboardingState`** — `domains/setup.ts` maps `selected_tier`
  and the `apply_setup` plan schema best-effort; confirm the plan/answers schema
  `OnboardingService.apply_setup` expects.

---

## Optional future endpoint (not a current screen, but enables session resume)

```
GET /sessions/{session_id}/messages   → [ { "role": "user"|"assistant",
                                            "text": "...", "ts": "..." } ]
```
Would let the web Conversation screen reopen a past session with its transcript
instead of starting fresh. Backed by `SessionStore`.
