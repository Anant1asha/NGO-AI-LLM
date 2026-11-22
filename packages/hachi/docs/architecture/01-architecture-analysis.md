# 01 — Architecture Analysis

> Phase 1 / Gate A. Baseline `main` @ `3d4fbe2`. Evidence is `file:line`.
> Inferences are marked **(inferred)**.

## 1. System overview

Hachi is an autonomous agent engine whose runtime spine is:

```
CLI / TUI / Channels / Daemon
        │  (all consume the gateway, in-process or over REST)
        ▼
   Gateway (FastAPI control plane)  ──▶  Orchestrator.boot_agent()
        │                                       │  wires one AgentSession
        ▼                                       ▼
   AgentSession.chat()  ──▶  ExecutionLoop.run()  ──▶  ToolRegistry.execute()
                                   │                          │
                                   ▼                          ▼
                            BaseLLMClient                 tools/*  +  MCP  +  .og REST
                            (Anthropic / OpenAI-compat / unofficial)
```

The loop is intentionally narrow: it knows only a `BaseLLMClient`, a `ToolRegistry`, a
duck-typed `memory`, an optional `CostTracker`/`SkillEngine`, and an immutable
`TurnContext` (`core/loop.py:267-309`). It imports no provider SDK, no gateway, and no
tool by name. This is the codebase's strongest architectural property.

## 2. Core abstractions

| Abstraction | Symbol | Location | Role |
|---|---|---|---|
| Execution loop | `ExecutionLoop` | `core/loop.py:255` | ReAct loop; `run()` drives stream → tool dispatch → repeat |
| Tool registry | `ToolRegistry` | `core/loop.py:107` | name → callable + schemas + lazy-load groups (note: lives in `loop.py`, **not** `tools/__init__.py`) |
| Turn snapshot | `TurnContext` | `core/turn_context.py:24` | `@dataclass(frozen=True, slots=True)`; factory `build()` at `:64` |
| Session boot | `boot_agent()` | `gateway/orchestrator.py:1453` | the single wiring site (~685 lines) |
| Session facade | `AgentSession` | `gateway/orchestrator.py:386` | owns loop+memory+vault+mcp+gate; `chat()` at `:1106` |
| LLM contract | `BaseLLMClient` (ABC) | `core/llm.py:106` | `generate` / `generate_stream` / `list_models`; factory `create_llm_client()` at `:644` |
| Config schema | `ResolvedConfig` (pydantic) | `core/settings.py:125` | typed settings tree; loader `load_effective_config()` at `config_loader.py:149` |
| Tool DI bundle | `BootDeps` / `ToolSpec` / `ToolRegistrar` | `gateway/tool_registration.py:18 / 43 / 55` | declarative, topo-sorted tool registration |
| Process singletons | `ProcessSharedServices` | `gateway/shared_services.py:67` | shared SkillEngine / MCPManager / Vault / MemoryIndex |
| Skill engine | `SkillEngine` | `og_engine/engine.py:314` | `.og` 3-pass index/dense/full traversal |
| Control plane | `GatewayControlPlane` | `gateway/control_plane.py:65` | HTTP-agnostic command surface; `PROTOCOL_VERSION="1.0"` at `:14` |

## 3. Module graph & dependency direction

Top-level packages under `src/hachi/`: `core`, `gateway`, `tools`, `og_engine`, `jobs`,
`channels`, `integrations`, `cli`, `tui`, `client`, `sdk`, plus `daemon.py`.

```
cli / tui / channels / daemon  ──▶  gateway  ──▶  tools  ──▶  core
                                       │                        ▲
                                       ├──▶ og_engine ──────────┘  (imports only core.paths)
                                       └──▶ jobs ──▶ core
                            integrations ──▶ core  (mounted via gateway capability factories)
```

- **`core` is the stable base.** A grep for upward edges (`core → {gateway,tools,tui,cli}`)
  finds **exactly one**: `core/onboarding.py:17 → hachi.gateway.workspace.install_optional_skill_pack`.
  That is the only layering violation, and it is a leaf utility — easily inverted.
- **`og_engine` is nearly free-standing** — its sole `core` import is `core.paths`
  (`og_engine/engine.py:31`). Good isolation of the `.og` "moat."
- **`tools` depend up into `core` only** (e.g. `tools/os_tools.py` imports
  `ToolRegistry` from `core.loop`). Correct direction.
- **No circular package dependencies** in the spine. A potential
  `orchestrator ↔ shared_services` cycle is broken with a function-local import
  (`orchestrator.py:1576`).

## 4. Dependency injection / wiring model

There is **no DI container**. Wiring is manual construction inside `boot_agent()`,
combined with a declarative registration table for tools — a "poor-man's DI":

1. A `BootDeps` dataclass (`tool_registration.py:18`) is assembled by `_make_deps()`
   (`orchestrator.py:1813`), holding every constructed dependency (gate, skill_engine,
   vault, job_queue, scheduler, tool_registry, credential_vault, provider_kind, …).
2. A `TOOL_SPECS: list[ToolSpec]` manifest (`orchestrator.py:1833-1957`) maps each tool
   domain to a `register_fn: Callable[[BootDeps], Any]`.
3. `ToolRegistrar().install(TOOL_SPECS, deps)` (`orchestrator.py:1961`) topo-sorts by
   `after`/`last` constraints (Kahn's algorithm, `tool_registration.py:89`) and runs each.
   `delegation` is forced `last=True` (it needs the fully-populated parent registry);
   `config` declares `after={"mcp_tools"}`.

Everything else is **constructor injection**: `ExecutionLoop(llm_client=, registry=,
memory=, cost_tracker=, skill_engine=, …)` (`orchestrator.py:2049`); `AgentSession(loop,
skill_engine, memory, integrations, mcp_manager, gate, …)` (`:2064`). Strategy selection
is used for the approval surface — `HandlerApprover` (TUI) / `RegistryApprover` (gateway)
/ `PolicyApprover` (headless) chosen by context at `orchestrator.py:1529-1536`.

**(inferred)** The `BootDeps` + `TOOL_SPECS` + `ToolRegistrar` trio is the de-facto DI
mechanism and the intended seam for tool extension — it is the only place dependencies
and registrations are declared together, and its docstring explicitly invites test fakes.

## 5. Patterns in use

- **Registry** — `ToolRegistry` (`loop.py:107`), `CapabilityRegistry` (`orchestrator.py:145`),
  `PendingApprovalRegistry` (`approvals.py`), connector registry.
- **Abstract factory / strategy for providers** — `BaseLLMClient` ABC +
  `create_llm_client()` dispatch on a `kind` string (`llm.py:644-730`). One
  `OpenAICompatibleClient` serves OpenAI / OpenRouter / Groq / Together / DeepSeek /
  Gemini / Ollama via base-URL presets (`llm.py:633`).
- **Adapter** — `UniversalRestAdapter` (`.og`-declared REST → tools), MCP tool
  adaptation, OpenAI tool-schema adaptation (`llm.py:390`), runtime-event `adapt_event()`.
- **Declarative manifest + topo resolver** — `TOOL_SPECS` + `ToolRegistrar`.
- **Event-driven read models** — typed `RuntimeEvent` → `RuntimeReadModelStore`,
  consumed by TUI + gateway; the loop emits via a single injected `on_event` callback
  (`loop.py:309`).
- **Immutable value objects** — `TurnContext`, all `*Snapshot` read models.
- **Command / queue** — `jobs/queue.py` `Job` + `ResidentWorkerThread` for background
  memory/title/prefetch work.
- **Provider strategy for sub-systems** — `MemoryProvider` ABC (Chroma / InMemory /
  FTS5), `SecretStore` Protocol (keyring / encrypted-file / composite).

## 6. Integration points (where the system meets the outside)

| Surface | Mechanism | Location |
|---|---|---|
| LLM providers | `BaseLLMClient` subclasses behind `create_llm_client()` | `core/llm.py:106,644` |
| First-party tools | `register_<domain>_tools()` → `ToolRegistry` | `tools/*.py`, `orchestrator.py:1833` |
| External MCP tools | `MCPManager.register_tools()`, hot-mount `add_mcp_server_live()` | `orchestrator.py:678,1908` |
| `.og`-declared REST APIs | `UniversalRestAdapter.register_node_apis()` | `orchestrator.py:1908`; `core/rest_adapter.py` |
| Public control plane | 56 REST + 2 SSE routes via `create_gateway_app()` | `gateway/fastapi_app.py:296` |
| Inbound channels | `POST /channels/{channel}/inbound`, polling adapters | `fastapi_app.py:1142`; `channels/` |
| OAuth integrations | Google / Notion / Slack connectors | `integrations/`, `core/oauth.py` |
| OpenAI-compat facade | `POST /v1/chat/completions`, `GET /v1/models` | `fastapi_app.py:966` |
| Outbound HTTP | `httpx` + SSRF guard + DNS pinning | `core/net_guard.py:73`, `core/rest_adapter.py:286` |

## 7. Vendor-SDK boundary (clean)

`import anthropic` appears **only** in `core/llm.py:17`; the client is constructed only
at `llm.py:226` and called only at `:329`/`:347`. ChromaDB is isolated behind
`MemoryVault` / `memory_provider.py`. The loop and tools never touch a provider SDK
directly. This boundary is the foundation every provider-agnostic initiative builds on.

## 8. Global mutable state (4 instances, all guarded)

- `ProcessSharedServices._INSTANCES` dict, mutated under `_LOCK` (`shared_services.py:46,119`).
- `core/approvals.py:244` `_registry` singleton (double-checked lock).
- `core/memory_vault.py:174` module-level `_llm_client_instance`.
- `tools/notification_tools.py:27` `_SHARED_DIGEST_BUFFER`.

All are lock-guarded and carry test-reset hooks, but they couple session lifecycle to
process lifecycle and complicate isolation. Other module-level globals flagged by grep
are immutable lookup tables (themes, presets, role labels), not mutable state.

## 9. Domain ownership

| Domain | Owner package | Notes |
|---|---|---|
| Turn execution / ReAct | `core/loop.py`, `core/turn_context.py` | provider-agnostic |
| Provider/model selection | `core/llm.py`, `core/settings.py` | single client per session |
| Memory (3-layer) | `core/memory*.py`, `core/memory_vault.py` | provider seam present |
| Persistence | `core/session_store.py`, `jobs/queue.py`, `core/memory_index.py` | SQLite, direct calls |
| Background work | `jobs/queue.py`, `jobs/scheduler.py` | scheduler durable; queue not |
| Events / read models | `core/runtime_events.py`, `core/runtime_read_models.py` | one-way log |
| Permissions / approvals | `core/permissions.py`, `core/approvals.py` | gate + approver strategy |
| Skills (`.og`) | `og_engine/`, `core/og_pack.py`, `core/skill_packs.py` | the moat |
| Gateway API | `gateway/fastapi_app.py`, `gateway/control_plane.py` | OpenAPI-contracted |
| Observability/cost | `core/tracing.py`, `core/cost.py` | tracing dormant |
| Tools | `tools/*.py` | 16 domains |
| UI | `tui/`, `frontend/` (separate tree) | REST-only consumers |

## 10. Where complexity concentrates

`boot_agent()` (`orchestrator.py:1453-2138`, ~685 lines) is the one god-function: it mixes
permission setup, provider creation, memory-graph wiring, spend-cap parsing, and
scheduler/worker startup. The *tool* sub-step was already extracted into
`BootDeps`/`TOOL_SPECS`; the rest has not. `AgentSession` (~970 lines) is large but
cohesive (read-model + lifecycle facade). These are the natural first targets if the
wiring layer needs to grow to host new platforms — see report 03.
