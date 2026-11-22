# 10 — Proposed Target Architecture

> Phase 2 / Gate B. The centerpiece of the design set. Defines the new constructs, how
> they compose with the existing spine, and the phasing. Detailed contracts live in the
> per-domain docs (12–21). Evidence/seams are `file:line`.

## 1. Design tenets (applied, not recited)

1. **Keep the clean spine.** The provider-agnostic loop, the confined `anthropic` SDK, and
   the `ToolRegistry`/`BootDeps` seam stay. New capability arrives **through** them, not by
   editing them.
2. **One new seam per concern, reused everywhere.** A single `ModelRouter`, a single
   `EventBus`, a single resilience wrapper, a single durable run-store — not per-feature
   machinery.
3. **Capability over vendor.** Everything external (models, speech, search, embeddings)
   advertises *capabilities*; business logic asks for a capability and gets a resilient
   client. No vendor name in business logic.
4. **Additive and back-compat.** Every change is a superset of today's behavior; the
   current single-model, single-provider path becomes the *default route*.
5. **Build the seam, defer the machinery (§4a).** Contract + one impl + documented
   extension point. Replay/DLQ/multi-node/8-providers are seams, not builds.

## 2. The target, in one diagram

```
        ┌──────────────────────────── Surfaces ────────────────────────────┐
        │   CLI · TUI · Channels · Daemon · Web frontend  (REST/SSE only)   │
        └───────────────────────────────┬──────────────────────────────────┘
                                         │
                              Gateway (FastAPI control plane)
                                         │  boot_agent() — slimmed, factory-composed
        ┌────────────────────────────────┼────────────────────────────────────┐
        │                         AgentSession / ExecutionLoop                 │
        │            (unchanged spine: ReAct, TurnContext, ToolRegistry)       │
        └───┬───────────────┬───────────────┬───────────────┬──────────────┬──┘
            │               │               │               │              │
   ┌────────▼──────┐ ┌──────▼───────┐ ┌─────▼──────┐ ┌──────▼──────┐ ┌─────▼───────┐
   │  ModelRouter  │ │   EventBus   │ │ AgentRun-  │ │  Tool /     │ │ Observability│
   │  + Registry   │ │ (pub/sub)    │ │ time +     │ │ Capability  │ │  spine       │
   │  + Health     │ │              │ │ RunState   │ │ providers   │ │ (trace+cost) │
   └───┬───────────┘ └──────┬───────┘ └─────┬──────┘ └──────┬──────┘ └─────┬───────┘
       │ select(capability) │ publish/      │ persist/      │ Search/File/ │ spans+
       │ → ResilientClient  │ subscribe     │ resume        │ Voice/Vision │ events
   ┌───▼────────────────────▼───────────────▼───────────────▼──────────────▼───────┐
   │            ProviderRegistry  (LLM · Speech · Search · Embedding · Vision)       │
   │   each provider advertises capabilities → builds BaseLLMClient/SpeechClient/... │
   └────────────────────────────────────────────────────────────────────────────────┘
   ┌────────────────────────────────────────────────────────────────────────────────┐
   │  Durable substrate:  SQLiteJobQueue+JobRegistry · SessionStore · RunStateStore   │
   │                      MemoryVault/Index · FileStore · Scheduler                   │
   └────────────────────────────────────────────────────────────────────────────────┘
```

## 3. New core constructs (what we add)

### 3.1 Provider & routing layer (Initiatives B, I, and the spine of G/F)
- **`ModelDescriptor`** — value object: `id`, `provider`, `capabilities: set[Capability]`,
  `context_window`, `max_output`, `pricing`, `supports_tools/streaming/vision`. Replaces the
  scattered `MODEL_PRICING` (`cost.py:19`) + static lists (`cli/main.py:626`) as the single
  source of truth.
- **`ModelRegistry`** — id → `ModelDescriptor`; seeded from a bundled defaults table + config
  + best-effort provider discovery (`list_models()`, already on `BaseLLMClient`).
- **`ProviderRegistry`** — name → provider adapter; each adapter advertises which
  capabilities/models it serves and *builds clients*. Wraps today's `create_llm_client`
  (`llm.py:644`).
- **`CapabilityRouter` / `ModelRouter`** — `select(capability, constraints) →
  ResolvedModel(client, descriptor)`. Honors cost/context/health/user-prefs/policy; returns a
  **resilient** client with a fallback chain.
- **`ProviderHealth` + resilience wrapper** — `ResilientClient` decorates any
  `BaseLLMClient`/provider client with timeout+bounded-retry+circuit-breaker, recording
  latency/error-rate that feeds routing.
- Detailed in [13](13-provider-architecture.md), [14](14-capability-registry.md),
  [15](15-model-routing.md).

### 3.2 Event bus (Initiative C)
- **`EventBus`** — `publish(event)` / `subscribe(pattern, handler, *, mode=sync|async)`.
  Implemented **over** the existing emit funnel (`orchestrator.py:1484-1498`) so all current
  producers and the read-model/SSE consumers keep working unchanged; new reactive subscribers
  attach here. Async dispatch via the existing job queue.
- Detailed in [12](12-event-architecture.md).

### 3.3 Agent runtime & durable run-state (Initiative D)
- **`RunState`** — persisted record (`status`, `wait_condition`, `resume_cursor`,
  `payload`) in a new `runs` table, reusing `SessionStore`'s WAL/backup/migration pattern.
- **`WaitConditionRegistry`** — generalizes `PendingApprovalRegistry` (`approvals.py:121`) to
  durable file/event/webhook/tool/user waits with wake/resume.
- **`JobRegistry` activation** — turn the built-but-unwired durable job path (`queue.py:473`)
  on; reactive subscribers and resumable steps run as named handler jobs that survive restart.
- **Replace `core_suspend_workflow`** with a real suspend that writes `RunState=Waiting` +
  a `WaitCondition`, and a resume that re-enters the loop from the cursor.
- Detailed in [16](16-durable-execution.md).

### 3.4 Capability providers (Initiatives A, E, F, G)
- **`SearchProvider`**, **`StorageProvider`/`FileStore`**, **`SpeechProvider`**, and the
  **vision capability** are all *providers* registered in the `ProviderRegistry` and surfaced
  as tools via the existing `TOOL_SPECS` seam. They advertise capabilities and are selected by
  the router (e.g. `view_image` asks for a `vision` client; voice tools ask for `stt`/`tts`).
- Detailed in [17](17-search-platform.md), [18](18-attachment-platform.md),
  [19](19-voice-platform.md), [20](20-vision-platform.md).

### 3.5 Observability spine (Initiative H)
- A per-turn **root span** in `_chat_impl` (`orchestrator.py:1138`), OTel context propagated
  into the tool thread-pool, `session_id`/`turn_id`/`principal` stamped on every event and
  span, token/cost attached to `llm.generate` spans, and a config-driven exporter
  (console / OTLP / Langfuse). Injected via the `EventBus` subscriber seam and the existing
  `setup_tracing(exporter=…)` (`tracing.py:55`) — never littered through business logic.
- Detailed in [21](21-observability.md).

## 4. How the existing spine changes (minimal)

| Component | Change | Back-compat |
|---|---|---|
| `ExecutionLoop` (`loop.py`) | receives a `ModelRouter` (or a pre-resolved default client); asks the router for the `reasoning` client; wraps LLM calls in resilience | If handed a plain `BaseLLMClient`, behaves exactly as today (router optional) |
| `boot_agent` (`orchestrator.py:1453`) | constructs `ProviderRegistry`/`ModelRouter`/`EventBus`/`RunStateStore` via small factories; god-function shrinks as sub-steps extract | Same observable boot; new objects are additive |
| `ToolRegistry` (`loop.py:107`) | unchanged; tools gain access to the router/bus via `BootDeps` | Fully compatible |
| `create_llm_client` (`llm.py:644`) | becomes the per-provider builder the `ProviderRegistry` calls | Still callable directly |
| Config (`settings.py`) | new sections: `[routing]`, `[providers.*]` (activated), `[search]`, `[files]`, `[voice]`, `[observability]` | `extra="ignore"` + additive — old configs load |
| Gateway (`fastapi_app.py`) | new routes: `/files/*`, `/search/*` (optional), `/runs/*`; all with `response_model` | Additive; OpenAPI re-export |

The loop and turn model — the architectural heart — are **not** rearchitected. This is
deliberate: the spine is sound, so the design adds *around* it.

## 5. Domain composition (who calls whom)

```
ExecutionLoop ──asks──▶ ModelRouter ──selects──▶ ProviderRegistry ──builds──▶ ResilientClient ──▶ provider SDK
      │                     ▲                                                          │
      │                     └────────── ProviderHealth ◀──── records latency/errors ──┘
      ├──emits──▶ EventBus ──async──▶ JobQueue(JobRegistry) ──▶ reactive subscribers
      │                     └──sync──▶ read-model store · SSE · Observability sink
      └──suspends──▶ AgentRuntime ──writes──▶ RunStateStore + WaitConditionRegistry
                                   ◀──wakes── EventBus / Scheduler / approval resolve
Tools (Search/File/Voice/Vision) ──ask──▶ ModelRouter / ProviderRegistry  (by capability)
```

Dependency rule (enforced in [11](11-domain-boundaries.md)): **`core` defines the contracts;
providers and tools depend inward on `core`; the gateway wires them. No business logic imports
a vendor SDK** — only provider adapters do, and only inside the `ProviderRegistry`.

## 6. Phasing (the build order — detail in the rollout plan)

| Phase | Lands | Unlocks |
|---|---|---|
| **2.1 Foundation** | `ModelDescriptor`/`Registry`, `ProviderRegistry`, `ModelRouter`, resilience wrapper, default-route back-compat, de-lock sub-agent, centralize model defaults | B; resilience for all; prerequisite for G/I |
| **2.2 Event & Durable** | `EventBus` over the funnel; activate `JobRegistry`; `RunState`+`WaitCondition`; replace suspend | C, D; reactive agents |
| **2.3 Observability** | root span + correlation + exporter + cost-on-span | H; makes 2.1/2.2 debuggable |
| **2.4 Modalities** | `SearchProvider`+Tavily; `FileStore`+pipeline; `SpeechProvider`; vision auto-route | A, E, F, G |
| **2.5 Multi-provider depth** | health-aware routing, budget-aware selection, 2nd providers | I |

Each phase is independently reviewable and shippable behind config flags. Observability (2.3)
is intentionally early so the new subsystems are traceable as they land.

## 7. What this architecture deliberately does **not** add

Per §4a, and to be defended at Gate C: no external message broker, no event persistence/replay/
DLQ, no distributed/multi-node execution, no Postgres/S3, no real-time streaming voice, no
RAG index build, no provider-pricing automation, no per-tenant policy engine. Each has a named
seam in its design doc and a documented trigger condition for when to build it.

## 8. Open design decisions (resolved in the per-domain docs / ADRs)

- **Naming collision:** an existing `CapabilityRegistry` (feature toggles, `orchestrator.py:145`)
  vs the new model-capability concept → resolved in [14](14-capability-registry.md) (the new
  one is named to avoid collision).
- **Router placement:** does the loop hold a client or the router? → the loop holds the router
  but defaults to a single resolved client for the `reasoning` capability (back-compat) —
  [15](15-model-routing.md).
- **Async dispatch substrate:** the event bus's async mode reuses the job queue rather than
  spawning threads (honors the "no fire-and-forget threads" guardrail) — [12](12-event-architecture.md).
