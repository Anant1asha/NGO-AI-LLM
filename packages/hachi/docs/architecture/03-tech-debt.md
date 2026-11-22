# 03 — Technical Debt Assessment

> Phase 1 / Gate A. Baseline `main` @ `3d4fbe2`. Evidence is `file:line`.
> Items marked **[verified]** were re-read in source by the architect.

Debt is ranked by how directly it blocks the nine initiatives, not by abstract
cleanliness. Each item lists location, why it is debt, the initiative(s) it impedes, and
severity.

## D1 — `core_suspend_workflow` is a dishonest no-op  **[verified]** · Severity: High (correctness)
- **Where:** `tools/workflow_tools.py:15-21` raises `SuspendWorkflow`; the tool
  description (`:30-31`) promises *"Your state will be safely saved and you will
  automatically wake up when the event occurs."* The loop catches it and returns
  `[WORKFLOW SUSPENDED] {reason}`, ending the turn — there is no checkpoint, no saved
  continuation, no wake path.
- **Why debt:** shipped skills call it to "pause until X"
  (`default_skills/google/inbox_sentinel.og`, `morning_briefing.og`, `slack/dnd_coordinator.og`).
  They silently terminate instead of resuming. This is not missing-feature debt; it is
  *active misinformation* the model is told to trust.
- **Blocks:** D (long-running). Must be replaced before any durable-execution work.

## D2 — Provider-locked sub-agent delegation  **[verified]** · Severity: High
- **Where:** `core/sub_agent.py:617-630` — `_create_client(model)` returns
  `AnthropicClient(...)` unconditionally; `:591-592` calls it whenever an explicit
  `model=` is passed to `delegate_task`.
- **Why debt:** the *one* multi-model path in the system forces Anthropic regardless of
  session provider. A non-Anthropic user who delegates with a model override gets
  cross-provider behavior or an `ANTHROPIC_API_KEY` failure. Directly contradicts
  "provider-agnostic."
- **Blocks:** B, G, I.

## D3 — Background-job durability is built but inert  **[verified]** · Severity: High
- **Where:** `jobs/queue.py:617-626` deliberately marks func-only PENDING jobs `failed`
  on restart ("func-only job cannot run after restart"). The durable `handler_name` +
  `JobRegistry` path (`queue.py:473-491`) is **never instantiated**, and every production
  job is created with `func=` (live callable) — e.g. `core/memory.py:174`,
  `tools/memory_tools.py:63`, `orchestrator.py:1014,1068`.
- **Why debt:** the SQLite queue *advertises* restart survival but delivers none.
  Anything that assumes queued memory writes / titles survive a restart is wrong.
- **Blocks:** C, D, E (durable async is their foundation).

## D4 — No model registry; model names hardcoded in business logic · Severity: High
- **Where:** `core/models.py` is OG schemas, not a model registry. Hardcoded
  `claude-haiku-4-5` at `sub_agent.py:52`, `llm.py:208,649`, `orchestrator.py:1554`,
  `settings.py:34`; `gemini-2.0-flash`/`gpt-4o` fallbacks at `llm.py:681,710`. Pricing
  (`cost.py:19-25`) covers only 5 families; everything else defaults to `(1.0, 5.0)`.
- **Why debt:** violates "no model names in business logic"; every model rotation is a
  multi-site edit; cost-aware routing would mis-rank unpriced models.
- **Blocks:** B, I.

## D5 — `ResolvedConfig.providers` named-provider map is inert · Severity: Medium
- **Where:** `settings.py:130-132` defines a multi-provider map; only manual `/model`
  switching reads provider config — no routing layer consumes it.
- **Why debt:** the schema implies a capability the runtime doesn't honor; a latent
  half-feature that will confuse the Initiative-B design if not reconciled.
- **Blocks:** B, I.

## D6 — No resilience layer (retry / backoff / circuit-breaker) · Severity: High
- **Where:** a grep for `retry|backoff|tenacity|circuit` across `src/hachi/**` returns
  **zero** application-level matches. `rest_adapter.py` makes single-shot calls
  (timeout 15s, `:307`); `AnthropicClient` timeout defaults to `None` → **SDK default
  600s** (`llm.py:210,226`); `OpenAICompatibleClient` uses 60s (`llm.py:371`).
- **Why debt:** a transient 429/5xx fails the whole turn; a flapping provider can hang a
  request for ten minutes. "Multi-provider failover" has nothing to build on.
- **Blocks:** B, I, A (search providers rate-limit), reliability across the board.

## D7 — `boot_agent()` god-function · Severity: Medium
- **Where:** `orchestrator.py:1453-2138` (~685 lines): permission setup + provider
  creation + memory-graph wiring + spend-cap parsing + scheduler/worker startup in one
  procedure.
- **Why debt:** high change-risk surface; hard to unit-test in isolation; every new
  platform that needs boot-time wiring grows it further. The tool sub-step was already
  factored out (`TOOL_SPECS`); the rest has not.
- **Blocks:** maintainability of B, C, D, H (all add boot wiring).

## D8 — Stringly-typed tool taxonomy spread across 2–3 sites · Severity: Medium
- **Where:** a tool's identity (`ToolRegistry`, name-keyed, `loop.py:242`), its lazy-load
  group (`_GROUP_BY_TOOL_NAME`, `orchestrator.py:234`), and its core-visibility
  (`_CORE_TOOL_NAMES`, `:199`) live in three disjoint places. Adding a tool edits all
  three; a missed `classify` entry silently lands it in the wrong group.
- **Why debt:** no single source of truth pairs `(schema, handler, group, capability)`.
  Every initiative that ships tools (A, E, F) pays this tax.
- **Blocks:** A, E, F (maintainability).

## D9 — No migration framework · Severity: Medium-High
- **Where:** only `SessionStore._migrate_schema` (`session_store.py:108-129`) does
  introspect-then-`ALTER`. `jobs.db` and `memory_index.db` use bare
  `CREATE TABLE IF NOT EXISTS` (`queue.py:498`, `memory_index.py:25`) — a changed column
  never reaches an existing user DB.
- **Why debt:** any initiative that adds tables/columns (E file metadata, D run-state)
  inherits a silent-failure trap. There is no shared `apply_migrations()` helper.
- **Blocks:** D, E, migration safety.

## D10 — Two parallel error hierarchies; `HachiError.http_status` is dead at the edge · Severity: Medium
- **Where:** `core/errors.py:16` defines `HachiError` with an advisory `http_status`, but
  the gateway uses a separate `GatewayProtocolError`/`GatewayUnavailableError`
  (`control_plane.py:53,57`) and no handler maps `HachiError.http_status`
  (`fastapi_app.py:397-492`). A domain `ToolError(502)` surfaces as a generic 500. Two
  envelope shapes coexist (`{code,message,details}` vs raw `{detail}`).
- **Why debt:** error contracts are inconsistent; new error types won't get their intended
  status without also registering a handler.
- **Blocks:** API consistency for every new route.

## D11 — ~15 gateway routes escape the contract gate · Severity: Medium
- **Where:** routes returning bare `dict`/`Any` with no `response_model` — `/config`,
  `/skills`, `/memory`, `/spend`, `/og/graph`, `/integrations`, etc. — produce no
  `schema.d.ts` diff, so the CI `frontend-contract` job cannot catch breaking changes to
  them (the frontend reads these via hand-authored `types.ts`).
- **Why debt:** silent runtime breakage on payload changes; the very class of regression
  the audit history warns about.
- **Blocks:** safe API evolution for A, B, E, H (all add routes).

## D12 — Observability has no correlation spine · Severity: Medium (High for H)
- **Where:** only 2 leaf spans exist (`loop.py:355,737`), with no per-turn root span;
  tool spans run in a `ThreadPoolExecutor` (`loop.py:856`) that loses OTel context;
  `tool.call`/`usage`/sub-agent events carry no `turn_id`/`session_id`
  (`loop.py:775,829,882`); the transport envelope has no trace field
  (`control_plane.py:418`).
- **Why debt:** Langfuse-grade traces cannot be assembled across layers without first
  stamping ids and establishing nesting. No metrics exist at all.
- **Blocks:** H.

## D13 — Logging silent by default · Severity: Low-Medium
- **Where:** 36 modules use `getLogger(__name__)`, but the only handler/formatter setup is
  in the daemon (`daemon.py:113-138`). CLI/gateway/TUI runs have no root config → INFO/DEBUG
  fall to Python's `lastResort` (WARNING+ to stderr only). **(inferred)**
- **Why debt:** operationally near-blind outside the daemon; complicates diagnosing the
  new subsystems.
- **Blocks:** H, operability.

## D14 — Single global `CostTracker`; in/out split lost downstream · Severity: Low-Medium
- **Where:** one tracker at `orchestrator.py:1678` threaded into loop + all sub-agents;
  `/spend` reconstructs per-turn rows from `usage.updated` events and drops the
  input/output split (`cli/main.py:1163-1165`).
- **Why debt:** no per-agent/role/tool/provider cost attribution — exactly the dimension
  budget-aware routing (I) and Langfuse generations (H) need.
- **Blocks:** H, I (cost optimization).

## D15 — Minor / housekeeping · Severity: Low
- **Layering violation:** `core/onboarding.py:17 → gateway.workspace` — the lone upward edge.
- **Config frozen into handlers at boot:** tools close over `gate`/credentials at
  registration (`os_tools.py:634`), so live permission/limit changes need a reload;
  `ProcessSharedServices` fingerprint omits most config (`shared_services.py:52`),
  risking stale reuse. **(inferred runtime implication)**
- **Schema wider than write-path:** `ProviderKind` lists 7 kinds (`settings.py:8`) but
  `update_provider`/`validate_provider` accept only 3 (`cli/main.py:471,545`).
- **Possible `jobs.db` path inconsistency:** `queue.py` uses `appauthor="opengigantic"`
  vs `paths.py` `appauthor=False` — may resolve to a different Windows folder unless the
  orchestrator passes an explicit path. **(inferred — worth a one-line check)**
- **Dead `paths.tui_state_db`** (`paths.py:48`) — defined, zero consumers.
- **Event-name leaks:** `job.retry`, `budget_exceeded`, `llm_retry`, `session_time_limit`
  are raw literals outside `runtime_events.py` — a typed bus contract would miss them.
- **Non-atomic `device-permissions.og` writes** (`cli/main.py:1379`) vs crash-safe TOML.
- **`memory_index.db` lacks WAL** unlike the other two SQLite stores.

## Debt that is NOT present (worth recording)

- No circular package dependencies in the spine.
- The provider SDK boundary is clean (`anthropic` only in `llm.py`).
- Secrets are never written to config files (only env-var *names* are).
- SSRF/untrusted-content handling is thorough and consistently applied.
- Memory and secret stores already sit behind real interfaces.

## How debt maps to the initiatives

| Initiative | Gating debt |
|---|---|
| A Search | D6 (rate-limit/retry), D8 (tool taxonomy) |
| B Model Routing | **D4, D2, D5, D6** |
| C Events | **D3**, D12 (event ids), event-name leaks |
| D Long-running | **D1, D3**, D9 |
| E Files | D9, D8 |
| F Voice | D8 |
| G Vision | D2, D4 (needs B) |
| H Observability | **D12**, D13, D14 |
| I Multi-provider | **D2, D4, D6**, D14 |

The four "rework" initiatives are gated by a small, shared debt cluster — **D1–D6** —
which is where remediation leverage is highest.
