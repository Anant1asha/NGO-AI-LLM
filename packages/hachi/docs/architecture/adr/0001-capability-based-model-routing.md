# ADR-0001 — Capability-based model routing

- **Status:** Proposed (Gate B)
- **Date:** 2026-06-21
- **Deciders:** Principal Architect (pending Gate B/C approval)
- **Related:** [13](../13-provider-architecture.md), [14](../14-capability-registry.md), [15](../15-model-routing.md)

## Context

Hachi binds one statically-chosen model to a session and threads it everywhere
(`orchestrator.py:1552`). Model ids are hardcoded in business logic in 6+ sites
(`sub_agent.py:52`, `llm.py:208,649`, `settings.py:34`, …). There is no capability metadata,
no failover, no cost/context awareness, and the one multi-model path forces Anthropic
(`sub_agent.py:617`). Initiatives B, G (vision auto-route), and I (multi-provider) cannot be
built on this.

## Decision

Introduce a **`ModelRegistry`** (models → capabilities/cost/context), a config-driven
**`RoutingPolicy`** (capability → ordered candidate models), and a **`ModelRouter`** that
returns a *resilient, failover-wrapped* `BaseLLMClient` for a requested `Capability`. Business
logic asks for a **capability**, never a model name. Model ids live only in a bundled data
table and user config. The existing single-model path is preserved as the default route
(synthesized policy) so the upgrade is backward-compatible and invisible until configured.

## Alternatives considered

1. **Keep static selection, special-case vision.** Rejected — does not generalize; G/I still
   blocked; perpetuates hardcoded names.
2. **External routing library / gateway (LiteLLM-style proxy).** Rejected for now — adds an
   external dependency and a network hop, conflicts with the in-process single-node posture,
   and we already own `BaseLLMClient`. The `ModelRouter` interface does not preclude delegating
   to such a proxy later behind one provider adapter.
3. **Bake quality/latency scores into descriptors now.** Rejected — we have no telemetry;
   hardcoded scores would be fiction. Deferred until the observability spine (H) yields real
   latency/error data; the router's ordering step is the seam for it.
4. **One unified capability resolver for models and services (STT/TTS/search).** Rejected —
   `generate()` and `transcribe()`/`search()` have irreconcilable shapes. We unify the
   *vocabulary* (`Capability`), *health*, *resilience*, and *config*, but keep two typed
   resolvers (`ModelRouter` + `ProviderRegistry.get`). Callers still request by capability.

## Consequences

**Positive:** provider-agnostic by capability; vision never fails for lack of vision; cheap
models for title/compaction reduce cost; failover + bounded timeout replace the 600s hang;
model ids leave business logic; `/models` and pricing get one source of truth; G and I unblocked.

**Negative / cost:** a new core subsystem (registry/policy/router) and boot wiring; cost numbers
must be migrated verbatim and pinned by test; a new `NoRouteError` failure mode (only under
explicit constraints); slightly more moving parts at boot. Mitigated by the back-compat default
route (zero-config behavior identical to today) and incremental, flag-gated rollout.

**Reversibility:** medium. The router is additive and the loop accepts a plain client, so the
feature can be disabled by not configuring `[routing]`. Removing the registry entirely after
adoption would be costly — hence this ADR.
