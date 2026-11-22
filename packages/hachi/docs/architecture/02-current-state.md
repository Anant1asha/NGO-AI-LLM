# 02 — Current State Assessment

> Phase 1 / Gate A. Baseline `main` @ `3d4fbe2`. Evidence is `file:line`.

This report inventories **existing capabilities**, the **abstractions that already
exist** (the good seams), the **abstractions that are missing**, and closes with a
**readiness scorecard for each of the nine backlog initiatives (A–I)** — the
centerpiece that sets up Gate B.

## 1. Existing capabilities (what Hachi can do today)

- Multi-turn ReAct agent loop with streaming, tool calling, sub-agent delegation,
  budget/iteration/wall-clock guards (`core/loop.py`).
- Provider-agnostic LLM access across Anthropic + any OpenAI-compatible endpoint
  (OpenAI, Ollama, OpenRouter, Groq, Together, DeepSeek, Gemini-via-compat) and an
  opt-in unofficial ChatGPT-web client (`core/llm.py`).
- Three-layer memory: in-context active history with deferred compaction, a SQLite
  session transcript, and a ChromaDB semantic vault with FTS5 fusion
  (`core/memory.py`, `core/session_store.py`, `core/memory_vault.py`).
- `.og` ObjectGraph skill system with 3-pass token-efficient traversal (`og_engine/`).
- 16 tool domains: OS/file, browser (Playwright), vision, voice, Google/Notion/Slack,
  scheduling, notifications, messaging, presentations, sandbox, config, delegation,
  workflow, memory, og (`tools/*.py`).
- A FastAPI gateway (56 routes + SSE) with bearer auth, session ownership, an
  OpenAI-compatible facade, inbound channel webhooks, and OAuth integrations
  (`gateway/fastapi_app.py`).
- Durable recurring schedules (cron/interval/once) that fire agent turns
  (`jobs/scheduler.py`).
- Robust web-safety primitives: SSRF validation with DNS pinning, per-hop redirect
  guarding, and unconditional untrusted-content framing
  (`core/net_guard.py`, `core/browser.py`, `core/untrusted_content.py`).
- Token-level cost tracking with multi-tier budget enforcement and a `/spend` surface
  (`core/cost.py`).

## 2. Abstractions that already exist (the good seams)

| Abstraction | Type | Location | Quality |
|---|---|---|---|
| `BaseLLMClient` | ABC + factory | `core/llm.py:106,644` | **Strong.** Loop is genuinely provider-agnostic; SDK confined to one file. |
| `MemoryProvider` | ABC + `resolve_provider()` factory | `core/memory_provider.py:31,259` | **Strong** for the upsert/search/delete surface; Chroma/InMemory/FTS5 backends swap via `memory.backend` config. |
| `SecretStore` | Protocol + composite | `core/secret_store.py:25,246` | **Strong.** Keyring / encrypted-file / composite, factory-selected. |
| `JobQueue` | ABC | `jobs/queue.py:119` | **Medium.** InMemory + SQLite backends; durable path exists but is **unwired** (report 03). |
| `ToolRegistry` | registry | `core/loop.py:107` | **Medium.** Clean `register()`, but name-keyed; capability/group lives in a separate hand-maintained table. |
| Runtime event taxonomy | typed constants + `adapt_event` | `core/runtime_events.py:16-56` | **Medium.** Good `<domain>.<noun>.<verb>` vocabulary + secret scrubbing; one-way only (no bus). |
| `ResolvedConfig` | pydantic schema + layered loader | `core/settings.py:125`, `config_loader.py:149` | **Strong.** Defaults → global → project → env → CLI precedence. |
| Voice STT/TTS | injectable HTTP clients | `core/voice.py:296,383` | **Medium-strong.** OpenAI-compatible, env-configured, injectable for tests. |
| SSRF / untrusted content | functions | `core/net_guard.py:73`, `core/untrusted_content.py:37` | **Strong.** DNS-pinned, per-hop, unconditional framing. |
| `CostTracker` | accumulator | `core/cost.py:68` | **Medium.** Per-call token capture + budget enforcement; single global bucket. |
| `ActionApprover` | strategy | `orchestrator.py:1529` | **Strong.** TUI/gateway/headless approver selection. |
| `PermissionGate` | wrapper | `core/permissions.py` | **Strong.** Declared roots / command allow-block lists enforced at call time. |

## 3. Abstractions that are MISSING

| Missing abstraction | Consequence | Initiative blocked |
|---|---|---|
| **Model registry** (capabilities · cost · context window · provider) | No source of truth for "which model can do vision / reasoning / long-context"; `core/models.py` is OG schemas, `cost.py` is pricing-only (5 families) | B, G, I |
| **Capability router** (`select(capability) → client`) | One model per session; vision/title/compaction/embeddings all use the session model or a fixed backend | B, G, I |
| **Provider health / failover / retry** | A single provider blip fails the turn; no backup, no backoff, no breaker | B, I, reliability |
| **Event bus** (publish/subscribe/async) | Nothing can react to an event; events fan out one-way to read-models only | C |
| **Agent run-state machine + durable run state** | In-flight runs vanish on restart; outcomes are magic strings; `core_suspend_workflow` lies | D |
| **Durable wait-conditions** (file/event/webhook/tool) | Only human-approval blocking exists, in-memory and non-durable | C, D |
| **File / blob store** | No upload→validate→store→extract→index pipeline; no gateway upload routes at all | E |
| **Search provider** | No web search; `browse_web` needs a user-supplied URL | A |
| **Vision auto-router** | `view_image` uses the session model; no fallback when it lacks vision | G |
| **End-to-end correlation id / per-turn root span** | Tool/usage/sub-agent events carry no `turn_id`; only 2 leaf spans exist; thread-pool loses OTel context | H |
| **Metrics subsystem** | No counters/latency/histograms anywhere | H |
| **Migration framework** | Only `SessionStore` has a hand-rolled `_migrate_schema`; other SQLite stores can't evolve | E, D, migration |
| **Storage interface for SQLite stores** | Session/index/checkpoint/schedule stores hard-bind to local SQLite/JSON | migration, multi-node |

## 4. Readiness scorecard — the nine initiatives (A–I)

Legend — **Greenfield**: little/no existing code. **Extend**: a real seam exists, gap is
additive. **Rework**: code exists but is mis-shaped or dishonest and must change.

### A — Search Platform → **Extend (mostly greenfield capability, strong infra)**
- **Exists:** `httpx`, `UniversalRestAdapter` (`.og ::api` → tools), Playwright browser
  (`core/browser.py`), SSRF + untrusted-content guards, `CredentialVault`, the
  `tools/*` + `TOOL_SPECS` registration seam.
- **Missing:** any web *search* (none found — `browse_web` requires a user URL,
  `tools/browser_tools.py:114`); a `SearchProvider` interface; Tavily/Firecrawl adapters;
  outbound caching/dedup/rate-limit/batching; HTTP connection pooling; result reranking.
- **Verdict:** clean greenfield tool family landing in `tools/search_tools.py` + a
  provider interface; reuses all the safety infra. Low architectural risk.

### B — Capability-Based Model Routing → **Rework (the central gap)**
- **Exists:** `BaseLLMClient` ABC + factory (clean); `ResolvedConfig.providers` named-
  provider map (`settings.py:130` — present but **inert**); `MODEL_PRICING` (`cost.py:19`);
  per-sub-agent `model=` override.
- **Missing:** model registry (capabilities/context/cost), routing engine, fallback/retry,
  provider health; and hardcoded `claude-haiku-4-5` sits in 6+ logic sites
  (`sub_agent.py:52`, `llm.py:208,649`, `orchestrator.py:1554`, `settings.py:34`, …).
- **Verdict:** highest-value, highest-effort initiative. A `ModelRouter`/`ProviderRegistry`
  seam slots between orchestrator boot and the loop. Must also fix the provider-locked
  sub-agent (`sub_agent.py:618`).

### C — Event-Driven Architecture → **Rework**
- **Exists:** typed event taxonomy + `adapt_event` (secret-scrubbed); a single emit
  funnel `relay_event`/`emit_runtime_event` (`orchestrator.py:1484-1498`); sequenced
  read-model store with cursor replay.
- **Missing:** a real pub/sub bus; async dispatch; persistence (log is memory-only,
  cap 2000 at `runtime_read_models.py:247`); dead-letter; any consumer that *reacts*;
  external-trigger events (`file.uploaded`, `message.received`, `search.completed`).
- **Verdict:** the emit funnel is a single, clean integration point — replace its body
  with `bus.publish(event)` and register read-model + SSE + reactive subscribers. Defer
  replay/DLQ machinery (Section 4a).

### D — Long-Running Agent Execution → **Rework (highest correctness risk)**
- **Exists:** durable `Scheduler` (the one restart-survivor); `PendingApprovalRegistry`
  (request → external resolve → wake shape); `SessionStore` (WAL, backup) for run-state;
  `SQLiteJobQueue` + `JobRegistry` durable path **already built**.
- **Missing / broken:** no agent state machine (synchronous loop, magic-string outcomes);
  **`core_suspend_workflow` is a verified no-op false-promise** (`workflow_tools.py:15-21`)
  that shipped skills depend on; durable job path is **unwired** (`queue.py:617-626` fails
  func-only jobs on restart); no durable wait-for-event/file/webhook.
- **Verdict:** must replace the suspend primitive with a real persisted run-state +
  wake/resume, built on the already-present `SQLiteJobQueue`/`JobRegistry`,
  `SessionStore`, and approval-registry shapes. Highest data-loss risk if left as-is.

### E — File Platform → **Greenfield**
- **Exists:** `read_file`/`write_file`/`list_files` (`tools/os_tools.py:634`, permission-
  gated); Google Docs/Drive integrations; `.pptx` generation; `CheckpointManager` (the
  only bytes-on-disk pattern, `core/checkpoints.py`); `paths.py` for locations; the
  `semantic_search` RRF fusion seam for future RAG (`memory_vault.py:785`).
- **Missing:** every upload→validation→virus-scan→storage→extraction→indexing stage; PDF/
  DOCX/XLSX/CSV parsers; any gateway upload route (no `UploadFile`/`FileResponse`/
  `multipart` anywhere); a `FileStore`/`StorageProvider` interface.
- **Verdict:** genuinely greenfield, but with good templates to copy (`MemoryProvider`
  ABC, `SecretStore` composite, `CheckpointManager` atomic-bytes). RAG seam already exists.

### F — Voice Platform → **Extend (best-positioned of the multimodal three)**
- **Exists:** 5 voice tools; `SpeechToText`/`TextToSpeech` are **injectable, OpenAI-
  compatible, env-configured** (`core/voice.py:296,383`) — already work against any
  compatible Whisper/TTS endpoint (Deepgram/Groq via compat); keyless local playback.
- **Missing:** a `SpeechProvider` interface for *native* ElevenLabs/Deepgram/Azure APIs;
  streaming/push-to-talk/conversation mode; a mic UI; a streaming gateway route.
- **Verdict:** the provider abstraction is half-built. Formalize `SpeechProvider`, keep
  the OpenAI-compat adapter as one impl, add streaming as a later slice.

### G — Vision Platform → **Rework**
- **Exists:** `view_image` (`tools/vision_tools.py:97`) with Pillow resize, SSRF-guarded
  URL fetch, provider-aware block formatting (Anthropic + OpenAI-compat).
- **Missing:** `supports_vision()` on `BaseLLMClient`; **auto-routing** — today an image
  is sent to the session model even if it lacks vision (`vision_tools.py:222-239`), which
  the API then rejects; no fall-through to a vision-capable model.
- **Verdict:** depends on Initiative B (needs a capability router to pick a vision model).
  The tool exists; the routing does not.

### H — Full Observability (Langfuse) → **Extend (seam clean, coverage thin)**
- **Exists:** an OTel wrapper (`core/tracing.py`) with an exporter-injection point
  (`setup_tracing(exporter=…)`); 2 leaf spans (`llm.generate`, `tool.call`); the redacting
  event bus; `turn_id`+`session_id` at the turn boundary (`orchestrator.py:1141,1181`);
  mature cost capture; the single `on_event` fan-out as a subscriber seam.
- **Missing:** a per-turn root span; thread-pool context propagation (tool spans detach);
  `turn_id`/`session_id` stamped on tool/usage/sub-agent events; cost-on-span attribution;
  any metrics; a user/principal identity dimension; default-on structured logging.
- **Verdict:** Langfuse attaches additively (exporter swap **or** event subscriber). The
  work is **coverage + correlation**, not the seam. Dormant-by-default today (`HACHI_TRACING`).

### I — Multi-Provider AI Ecosystem → **Rework (superset of B)**
- **Exists:** `BaseLLMClient` for LLMs; voice provider seam; the named-provider config
  schema (inert).
- **Missing:** a unifying `AIProvider`/capability-advertise model; cross-provider workflow
  composition (Deepgram STT → Claude reasoning → GPT/Gemini vision → ElevenLabs TTS);
  failover; health monitoring; budget-aware routing; the provider-locked sub-agent fix.
- **Verdict:** I is B generalized across modalities. Build B's registry/router first, then
  fold voice/vision/embeddings/STT/TTS providers under the same capability model.

## 5. Summary

| Initiative | Verdict | Primary gap |
|---|---|---|
| A Search | Extend | no search provider (infra is ready) |
| B Model Routing | **Rework** | no registry / router / failover; hardcoded names |
| C Events | Rework | one-way log, no bus, memory-only |
| D Long-running | **Rework** | no durable run state; suspend is a no-op |
| E Files | Greenfield | no upload/extract/index pipeline |
| F Voice | Extend | formalize `SpeechProvider`; add streaming |
| G Vision | Rework | no capability auto-router (needs B) |
| H Observability | Extend | correlation + coverage, not the seam |
| I Multi-provider | Rework | superset of B across modalities |

Five of nine have a real seam to extend; the four "rework" items (B, C, D, I) share a
common root — **the absence of capability-based routing and durable, event-driven
execution** — and B is the keystone that G and I depend on.
