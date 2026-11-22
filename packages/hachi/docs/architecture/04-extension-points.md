# 04 — Extension Point Analysis

> Phase 1 / Gate A. Baseline `main` @ `3d4fbe2`. Evidence is `file:line`.

This report catalogs the seams where new capability lands today, then maps each of the
nine initiatives to the seam(s) it should use. The intent (Section 4a of the brief) is to
**reuse existing seams, not invent new machinery** — most initiatives plug into something
that already exists.

## 1. The existing seams

### S1 — New tool family
- **Seam:** write `register_<domain>_tools(registry, …deps)` in `tools/<domain>_tools.py`
  (calling `registry.register(schema, handler, group=…)`, `loop.py:121`), then add a
  `ToolSpec(name=…, register_fn=lambda d: …)` to `TOOL_SPECS` (`orchestrator.py:1833`) and
  a classify entry in `_CORE_TOOL_NAMES` (`:199`) or `_GROUP_BY_TOOL_NAME` (`:234`).
- **Quality:** clean and proven (16 domains use it). Friction: 2–3 coordinated edit sites
  (debt D8). Default group fails safe (visible/callable).
- **Used by:** A (search), E (file ops), F (voice — already), plus any new capability tools.

### S2 — New LLM provider
- **Seam:** subclass `BaseLLMClient` (`llm.py:106`) or reuse `OpenAICompatibleClient`; add
  a `kind` branch to `create_llm_client()` (`llm.py:644`); extend the `ProviderKind`
  literal (`settings.py:8`); widen the write-path allow-sets (`cli/main.py:471,545`); add
  a `[providers.NAME]` TOML section consumed by `ResolvedConfig.providers` (`settings.py:130`).
- **Quality:** strong for the *client*; the `kind` if-ladder is not a registry (the
  natural target for Initiative B to replace with a `ProviderRegistry`).
- **Used by:** B, I.

### S3 — Runtime (hot) MCP tools
- **Seam:** `AgentSession.add_mcp_server_live()` (`orchestrator.py:678`) /
  `POST /runtime/mcp/register` (`fastapi_app.py:798`) — mounts an MCP server's tools into
  the live registry with no restart; command/transport allow-listed.
- **Quality:** strong. The fastest path to *external* capability with zero core changes.
- **Used by:** A and E *could* ship as MCP servers instead of native tools (a design
  option for Gate B).

### S4 — `.og`-declared REST API
- **Seam:** `UniversalRestAdapter.register_node_apis()` (`orchestrator.py:1908`,
  `core/rest_adapter.py`) turns an `.og` `::api` block into an LLM tool — zero Python,
  with SSRF validation + DNS pinning + untrusted-content framing applied automatically.
- **Quality:** strong for simple request/response APIs (e.g. a search provider with a
  plain REST endpoint could be declared this way for a prototype).
- **Used by:** A (prototype), E (remote extractors).

### S5 — Memory backend
- **Seam:** `MemoryProvider` ABC + `resolve_provider()` factory
  (`memory_provider.py:31,259`), selected by `memory.backend` config. RAG fusion via
  `semantic_search` + Reciprocal Rank Fusion (`memory_vault.py:785`, `memory_index.py:223`).
- **Quality:** strong for upsert/search/delete; `MemoryVault`'s richer surface (profiles,
  delegation, quarantine) is not in the interface (escape hatch: `.vault`).
- **Used by:** E (file-content RAG indexes through the RRF seam).

### S6 — Secret / credential storage
- **Seam:** `SecretStore` Protocol + composite + `create_default_secret_store()`
  (`secret_store.py:25,308`); `CredentialVault` for per-integration creds.
- **Quality:** strong.
- **Used by:** A, F, I (provider API keys).

### S7 — Event integration (the bus seam)
- **Seam:** the emit funnel `emit_runtime_event`/`relay_event` (`orchestrator.py:1484-1498`)
  is the **single** place every producer routes through (`loop.py` `on_event`,
  `AgentSession._event_emitter`). Replacing its body with `bus.publish(event)` and
  registering subscribers (read-model store, SSE pump, new reactive consumers) introduces
  a real bus by touching **one function**.
- **Quality:** excellent single-point seam; the event *taxonomy* (`runtime_events.py:16-56`)
  is reusable as the bus vocabulary.
- **Used by:** C, H (a Langfuse event-sink subscriber).

### S8 — Durable async work
- **Seam:** `SQLiteJobQueue` + `JobRegistry` (`queue.py:533,473`) — the durable
  `handler_name`+`payload` path **exists but is unwired**. Activating it (instantiate one
  `JobRegistry`, register named handlers, pass it to both `JobWorker`s at
  `orchestrator.py:425,2100`, convert `func=` jobs to `handler_name=`) yields a genuinely
  restart-durable substrate.
- **Quality:** the substrate is production-shaped (WAL, retry/backoff, recovery); it just
  needs wiring (debt D3).
- **Used by:** C (event → durable job), D (resumable steps), E (blob processing).

### S9 — Durable wait / resume
- **Seam:** `PendingApprovalRegistry` (`approvals.py:121-239`) already models
  request-parked → external `resolve()` → wake. Generalizing it to arbitrary
  `WaitCondition` records (file/event/webhook/tool) backed by SQLite instead of an
  in-memory dict + `threading.Event`, plus a re-entrant loop resume, is the durable
  wait-and-resume mechanism the brief wants.
- **Quality:** correct *shape*, wrong *durability* — the pattern is reusable, the storage
  is not.
- **Used by:** D, C.

### S10 — Persistent run / blob state location
- **Seam:** `paths.py` (`HachiPaths`, `:19-83`) is the single source of truth for on-disk
  locations — add `blobs_dir`/`runs_db` here. `SessionStore`'s WAL + backup +
  `_migrate_schema` (`session_store.py:108,537`) is the reusable durable-store template;
  `CheckpointManager` (`checkpoints.py`) is the atomic-bytes-on-disk template.
- **Quality:** good templates; needs the shared migration helper (debt D9).
- **Used by:** D (run-state table), E (blob store + metadata).

### S11 — Observability exporter
- **Seam:** `setup_tracing(exporter=…)` (`tracing.py:55-70`) accepts any OTel
  `SpanExporter` — a Langfuse/OTLP exporter captures existing spans with zero loop edits;
  `configure_from_env()` (`:76`, called `orchestrator.py:1479`) is where to add Langfuse
  init. The `on_event` fan-out (S7) is the alternative additive sink.
- **Quality:** seam is clean; coverage/correlation is the work (debt D12).
- **Used by:** H.

### S12 — New config section / route / error / approver
- **Config:** add a pydantic model + field on `ResolvedConfig` (`settings.py:125`);
  precedence is automatic via `_deep_merge`; add a `PUT /config/...` route (template:
  `update_limits`, `cli/main.py:1307`).
- **Route:** add a FastAPI handler on the matching `APIRouter` + a pass-through method on
  `GatewayControlPlane` (`control_plane.py`) + wire in `_build_gateway_control_plane`
  (`cli/main.py:1936`); add a `response_model` to stay in-contract (debt D11); re-export
  OpenAPI + regen frontend.
- **Error:** subclass `HachiError` (`errors.py:58`) — caveat: also register a handler to
  get the status (debt D10).
- **Approver:** implement the `ActionApprover` protocol; wire a branch at
  `orchestrator.py:1529`.
- **Used by:** all initiatives (config + routes), C/H (errors), D (approval surfaces).

### S13 — Capability registry (already present, under-used)
- **Seam:** `CapabilityRegistry` (`orchestrator.py:145`) + `PUT /capabilities/{id}/enabled`
  govern feature toggles today. This is a candidate host for *model*-capability metadata
  or a sibling to a new `ModelCapabilityRegistry`. **(inferred fit — to be decided at Gate B)**
- **Used by:** B, G, I.

## 2. Initiative → seam map

| Initiative | Primary seams | New construct required |
|---|---|---|
| **A — Search** | S1 (tool), S4 (`.og` prototype) or S3 (MCP), S6 (keys) | `SearchProvider` interface + Tavily/Firecrawl adapters; outbound cache/rate-limit |
| **B — Model Routing** | S2 (provider), S13 (capability), S12 (config) | `ModelRegistry` + `ModelRouter` (`select(capability)→client`); failover/retry policy |
| **C — Events** | **S7 (bus seam)**, S8 (durable jobs) | `EventBus` (publish/subscribe/async) over the emit funnel; reactive subscribers |
| **D — Long-running** | **S8 (durable jobs)**, **S9 (wait/resume)**, S10 (run-state) | `RunStateMachine` + durable `WaitCondition`; replace `core_suspend_workflow` |
| **E — Files** | S1 (tools), S5 (RAG), S10 (blob store) | `FileStore`/`StorageProvider` interface + extraction pipeline + upload routes |
| **F — Voice** | S1 (tools — exist), S2-style provider | formalize `SpeechProvider`; OpenAI-compat as one impl; streaming route later |
| **G — Vision** | S2 + S13 (needs B's router) | `supports_vision()` on `BaseLLMClient`; vision auto-route via the model router |
| **H — Observability** | **S11 (exporter)**, S7 (event sink), S12 | per-turn root span + context propagation + id stamping; metrics |
| **I — Multi-provider** | S2, S13, B's router | `AIProvider` capability model across modalities; health monitor; budget-aware routing |

## 3. Key observation

The two highest-leverage seams are **S7 (the single emit funnel)** and **S8 (the
already-built-but-unwired durable job queue)**. Together they de-risk the two hardest
initiatives (C and D): a real event bus is largely a refactor of one function, and durable
execution is largely *activating* infrastructure that already ships. Initiative B's
`ModelRegistry`/`ModelRouter` is the one genuinely new core construct, and G and I depend
on it — which argues for B leading the design sequence at Gate B.
