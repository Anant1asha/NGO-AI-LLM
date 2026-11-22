# 11 — Domain Boundaries

> Phase 2 / Gate B. Defines the domains, their contracts, ownership, and the import rules
> that keep the architecture decoupled. Enforceable by an import-linter rule (proposed in
> the testing strategy).

## 1. Layering (inward dependency only)

```
   Layer 4  Surfaces        cli · tui · channels · daemon · frontend
                                   │  (consume gateway only)
   Layer 3  Gateway         gateway/*  (HTTP, control plane, boot/wiring)
                                   │  (wires domains; may import core + tools + providers)
   Layer 2  Tools/Providers tools/* · providers/* · integrations/*
                                   │  (depend inward on core contracts only)
   Layer 1  Core            core/*  (contracts, loop, registries, stores)
                                   │
   Layer 0  Foundation      og_engine/* · jobs/* · paths · errors
```

**Rule:** a layer may import only from layers at or below it. The single existing violation
(`core/onboarding.py:17 → gateway`) is scheduled for inversion in Phase 2.1 (move
`install_optional_skill_pack` behind a `core` interface or relocate the call to the gateway).

## 2. Domains and their contracts

| Domain | Owns (package) | Public contract(s) | May import | Must NOT import |
|---|---|---|---|---|
| **Execution** | `core/loop.py`, `core/turn_context.py` | `ExecutionLoop`, `TurnContext`, `ToolRegistry` | provider/event/router *contracts* (typing only) | gateway, tools, vendor SDKs |
| **Providers** | `core/providers/*` (new), `core/llm.py` | `AIProvider`, `BaseLLMClient`, `SpeechProvider`, `SearchProvider`, `StorageProvider` | vendor SDKs (here only) | gateway, loop internals |
| **Routing** | `core/routing/*` (new) | `ModelDescriptor`, `ModelRegistry`, `ModelRouter`, `Capability` | provider contracts, `ProviderHealth` | gateway, tools |
| **Resilience** | `core/resilience.py` (new) | `ResilientClient`, `resilient_call`, `ProviderHealth` | provider contracts | gateway |
| **Events** | `core/runtime_events.py`, `core/event_bus.py` (new) | `EventBus`, `RuntimeEvent`, event constants | jobs (async dispatch) | gateway, tools |
| **Agent Runtime** | `core/runtime/*` (new) | `RunState`, `RunStateStore`, `WaitConditionRegistry`, `AgentRuntime` | events, jobs, session_store | gateway |
| **Memory** | `core/memory*.py`, `core/memory_vault.py` | `MemoryProvider`, `MemoryManager` | providers (embeddings cap) | gateway |
| **Persistence** | `core/session_store.py`, `core/migrations.py` (new), `jobs/queue.py` | `SessionStore`, `RunStateStore`, `JobQueue`, `apply_migrations` | foundation | gateway, tools |
| **Files** | `core/files/*` (new), `tools/file_*` | `FileStore`, `StorageProvider`, `ContentExtractor` | providers, memory (RAG) | gateway internals |
| **Tools** | `tools/*` | `register_<domain>_tools(registry, deps)` | core contracts via `BootDeps` | gateway internals, vendor SDKs (except via provider) |
| **Observability** | `core/tracing.py`, `core/cost.py`, `core/obs/*` (new) | `span`, `setup_tracing`, `CostTracker`, exporters | events (sink) | business logic (injected only) |
| **Gateway** | `gateway/*` | REST/SSE routes, `GatewayControlPlane` | everything below | — |
| **Skills (moat)** | `og_engine/*` | `SkillEngine`, parser | `core.paths` only | everything else |

## 3. The vendor-SDK boundary (hard rule)

Today `import anthropic` lives only in `core/llm.py`. The target **widens this boundary
explicitly**: every vendor SDK (`openai`-shaped via httpx, `elevenlabs`, `deepgram`, `tavily`,
`firecrawl`, embedding SDKs) is importable **only inside a provider adapter** under
`core/providers/*`. An import-linter contract enforces: no module outside `core/providers/*`
(and `core/llm.py`, grandfathered) imports a vendor SDK. This is the single most important
boundary for provider-agnosticism and is testable.

## 4. Contract ownership & change protocol

- **Contracts live in `core`** as ABCs/Protocols/pydantic models. Providers and tools *depend
  on* them; they do not define them.
- **A contract change is a reviewed event.** Changing `BaseLLMClient`, `EventBus`,
  `MemoryProvider`, `RunState`, or any gateway response model requires: (1) an ADR if it is
  hard to reverse, (2) the OpenAPI re-export + `generate:api` if it touches a route, (3)
  additive-only by default (new optional fields/methods with defaults), (4) a deprecation note
  if behavior changes.
- **Capabilities are an enum owned by Routing** (`core/routing`). Adding a capability is
  additive; removing one is a deprecation.

## 5. Cross-domain communication

- **Synchronous, typed calls** for request/response within a turn (loop→router→provider).
- **Events** for anything fan-out, cross-cutting, or reactive (observability sinks, reactive
  agents, durable-wait wakeups). Domains publish to the `EventBus`; they do not call each
  other's internals to notify.
- **Jobs** for deferred/durable work (memory writes, reactive handlers, blob processing).
  Domains enqueue named handler jobs; they do not spawn threads (existing guardrail).

This keeps the domains independently evolvable: a new provider, a new tool, a new reactive
subscriber, or a new exporter each plugs into a contract without editing another domain.

## 6. Why these boundaries (one line each)

- **Providers isolated** → swap vendors without touching logic (the core requirement).
- **Routing separate from providers** → selection policy evolves independently of adapters.
- **Events separate from observability** → tracing is a *subscriber*, not a dependency.
- **Runtime separate from execution** → durability is added without rewriting the loop.
- **Persistence owns migrations** → schema evolution is one shared, safe mechanism.
- **Skills stay isolated** → the `.og` moat keeps its near-zero coupling.
