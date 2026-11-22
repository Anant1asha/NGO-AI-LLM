# 06 — Gap Analysis (Current vs Target)

> Phase 2 / Gate B. Builds on the Gate-A scorecard ([02](02-current-state.md)).
> Frames *what must be true* for each initiative, at **contract + one impl + seam** depth
> (§4a). Evidence is `file:line`.

## Reading guide

For each initiative: **Current** (what exists) → **Target** (the minimum that satisfies the
brief) → **Gap** (the delta we will design) → **Defer** (the machinery we explicitly will
*not* build yet, leaving a seam). The "Defer" column is as important as the others — it is
where scope discipline lives.

## Cross-cutting foundation (shared by B/C/D/G/H/I)

| Concern | Current | Target | Gap | Defer (seam only) |
|---|---|---|---|---|
| Model selection | one client/session, hardcoded names (`orchestrator.py:1554`) | capability→model routing with failover | `ModelRegistry` + `CapabilityRouter` + `ModelRouter` | quality scoring from live telemetry; A/B routing |
| Resilience | none (zero retry/breaker) | timeout+retry+breaker around every external call | one `ResilientClient`/`resilient_call` wrapper + `ProviderHealth` | adaptive backoff tuning; bulkheads |
| Events | one-way in-memory log (`orchestrator.py:1484`) | pub/sub bus, async dispatch | `EventBus` over the emit funnel | persistence, replay, DLQ, cross-process |
| Durable execution | none; suspend is a no-op (`workflow_tools.py:15`) | run-state survives restart; resumable waits | `RunState` store + `WaitCondition` + activate `JobRegistry` | distributed workers; saga/compensation |
| Observability | 2 leaf spans, no correlation (`tracing.py`) | end-to-end trace w/ correlation id | per-turn root span + id propagation + exporter | metrics backend; sampling strategy |
| Migrations | only SessionStore (`session_store.py:108`) | shared additive migration helper | `apply_migrations(conn, table, cols)` | down-migrations; framework (Alembic) |

## Per-initiative gap

### A — Search
- **Current:** `httpx`, SSRF + DNS-pin + untrusted-content guards, Playwright browser, `.og` REST adapter, `CredentialVault`. No web search.
- **Target:** request search/extract/crawl **by capability**; one provider (Tavily) live; cost controls (cache, dedup, rate-limit).
- **Gap:** `SearchProvider` interface, one adapter, `search`/`extract`/`crawl` tools, per-session result cache, outbound rate-limiter.
- **Defer:** Firecrawl/Exa/Brave adapters; deep-crawl pipelines; reranking; research orchestration.

### B — Model Routing  *(keystone)*
- **Current:** `BaseLLMClient` (clean) + `create_llm_client` if-ladder; `MODEL_PRICING` (5 families); inert `ResolvedConfig.providers`.
- **Target:** registry of models with capabilities/cost/context; capability router with fallback; no model names in business logic.
- **Gap:** `ModelDescriptor` + `ModelRegistry` + `CapabilityRouter` + `ModelRouter`; default-route back-compat; de-lock sub-agent (`sub_agent.py:618`); centralize model defaults.
- **Defer:** latency/quality-aware routing from live data; user-preference learning; per-tenant policy.

### C — Events
- **Current:** typed taxonomy + `adapt_event` + single emit funnel; sequenced read-model store.
- **Target:** components publish and **subscribe**; async dispatch; reactive consumers.
- **Gap:** `EventBus` (sync + async subscribers) wrapping the funnel; a few new event types (`file.uploaded`, `search.completed`, `message.received`).
- **Defer:** durable event log, replay, dead-letter, cross-process delivery.

### D — Long-running Execution
- **Current:** durable `Scheduler`; in-memory approval wait; `SQLiteJobQueue`+`JobRegistry` (unwired); magic-string outcomes.
- **Target:** explicit run-state (Pending/Running/Waiting/Blocked/Completed/Failed/Cancelled) that **survives restart**; `wait_for_user` + `wait_for_event` resumable.
- **Gap:** `RunState` persistence (new table), `WaitCondition` registry (generalize approvals), activate `JobRegistry`, replace `core_suspend_workflow` with real suspend/resume.
- **Defer:** wait_for_file/webhook beyond the two in shipped skills; distributed execution; compensation.

### E — File Platform
- **Current:** local read/write, Google Docs/Drive, pptx-gen, `CheckpointManager` (bytes-on-disk), RRF RAG seam. No upload pipeline.
- **Target:** upload→validate→(virus-scan hook)→store→extract→index for common types; provider-agnostic storage; agent availability.
- **Gap:** `FileStore`/`StorageProvider` interface + local impl; extraction registry (pdf/docx/csv/xlsx/txt); upload routes; virus-scan hook interface (no-op default).
- **Defer:** RAG index build; cloud/object storage; archive handling; streaming-chunk uploads beyond a size cap.

### F — Voice
- **Current:** 5 tools; injectable OpenAI-compatible STT/TTS (`voice.py:296,383`); keyless playback.
- **Target:** provider-agnostic `SpeechProvider` (STT/TTS); one impl; capability-routed.
- **Gap:** formalize `SpeechProvider`; register STT/TTS as capabilities in the router; keep OpenAI-compat as the impl.
- **Defer:** native ElevenLabs/Deepgram/Azure adapters; streaming, interruptions, conversation mode, mic UI.

### G — Vision
- **Current:** `view_image` provider-aware but uses the session model (`vision_tools.py:222`); no auto-route.
- **Target:** vision work never fails for lack of vision — auto-route to a vision-capable model.
- **Gap:** `supports_vision()`/capability on descriptors; `view_image` asks the `ModelRouter` for a vision client and folds the result back. **Depends on B.**
- **Defer:** dedicated vision pipelines (OCR, diagram parsing); multi-image reasoning depth.

### H — Observability
- **Current:** OTel wrapper (dormant), 2 leaf spans, mature cost capture, redacting event bus; no correlation.
- **Target:** trace User→Session→Agent→Tool→Event→Model→Provider→Response; injected, not littered; Langfuse-ready.
- **Gap:** per-turn root span; thread-context propagation; stamp `session_id`/`turn_id` on all events; cost-on-span; exporter config (Langfuse/OTLP); minimal counters.
- **Defer:** full metrics/SLO backend; sampling; multi-user principal modeling beyond a `principal` field.

### I — Multi-Provider Ecosystem
- **Current:** `BaseLLMClient`; voice provider seam; inert named-providers.
- **Target:** providers advertise capabilities; route by capability across modalities; failover + health + budget-aware.
- **Gap:** B's registry/router generalized to non-LLM providers (speech, search, embeddings); `ProviderHealth`; budget-aware selection.
- **Defer:** 8-provider matrix; pricing-feed automation; tier negotiation.

## The dependency spine of the gap

```
            ┌─────────────────────────────────────────────┐
   B  ──────┤  ModelRegistry + CapabilityRouter + Router   ├──────┐
            └─────────────────────────────────────────────┘      │ depended on by
 resilience ── ResilientClient + ProviderHealth ──────────────────┤  G (vision route)
            ┌─────────────────────────────────────────────┐      │  I (multi-provider)
   C/D ─────┤  EventBus  +  RunState/WaitCondition + Jobs   │      │  F (speech caps)
            └─────────────────────────────────────────────┘      │
   A/E/F/G/H ── platform providers + tools, on fixed contracts ───┘
```

**Conclusion:** the gap is dominated by **B (routing) and the C/D foundations**. Once those
contracts are fixed, A/E/F/G/H/I are additive provider+tool work that conforms to them. This
is why the design sequence leads with B and the event/durable foundation.
