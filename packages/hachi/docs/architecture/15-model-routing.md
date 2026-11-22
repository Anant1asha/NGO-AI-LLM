# 15 — Model Routing Design

> Phase 2 / Gate B. Initiative **B** (the Routing Engine), foundation for **G** and **I**.
> Contract + one impl + seam. Seams are `file:line`.

## 1. Problem

One model per session, chosen statically (`orchestrator.py:1552`), threaded everywhere — main
loop, memory background jobs, vision, sub-agents. No way to route vision to a vision model when
the session model lacks it (the brief's headline G requirement), no failover, no cost/context
awareness. The single multi-model path is provider-locked (`sub_agent.py:617`).

## 2. Contract — `ModelRouter`

```python
# core/routing/router.py
class RouteConstraints(BaseModel):
    min_context: int | None = None
    needs_tools: bool = False
    needs_vision: bool = False
    max_input_cost_per_mtok: float | None = None
    prefer: Literal["cost", "quality", "balanced"] = "balanced"

class ResolvedModel(NamedTuple):
    client: BaseLLMClient          # ResilientClient wrapping primary + fallback chain
    descriptor: ModelDescriptor

class ModelRouter:
    def __init__(self, registry: ModelRegistry, policy: RoutingPolicy,
                 providers: ProviderRegistry, resilience: RetryPolicy): ...

    def select(self, capability: Capability,
               constraints: RouteConstraints | None = None) -> ResolvedModel:
        """Pick the best available model for a capability and return a resilient,
        failover-wrapped client. Pure/deterministic given health snapshot."""

    def default_client(self) -> BaseLLMClient:
        """The reasoning route for the configured default_model — the loop's primary."""
```

## 3. The routing algorithm (one impl, simple and explainable)

```
select(capability, constraints):
  1. candidates ← policy.candidates(capability)            # explicit config order, if any
     if empty: candidates ← registry.by_capability(capability)   # derive from registry
  2. resolve each id → ModelDescriptor via registry; drop unknowns
  3. filter by HARD constraints:
        context_window ≥ min_context
        supports_tools if needs_tools
        VISION ∈ capabilities if needs_vision
        pricing.input ≤ max_input_cost_per_mtok (skip if pricing None and no cost cap)
  4. drop models whose provider breaker is OPEN / unavailable (ProviderHealth)
  5. ORDER the survivors:
        explicit policy order wins; else by `prefer`:
          cost     → cheapest input+output
          quality  → bundled tier rank (opus > sonnet > haiku ...; declared in defaults)
          balanced → cost among those meeting a context/quality floor
  6. primary = survivors[0]; fallbacks = survivors[1:K]   # K bounded (default 2)
  7. build ResilientClient(primary, policy, recorder) with fallback chain → ResolvedModel
  8. if NO survivor: raise NoRouteError(capability, reason)  # explicit, observable
```

Determinism: given a `ProviderHealth` snapshot, `select()` is pure — same inputs, same route.
This keeps it testable and traceable (the chosen route + reason is emitted as a span attribute
and a `model.routed` event). **Stickiness (Gate-C amendment A12):** a route is resolved **once per
capability per turn** and reused, and the breaker has half-open hysteresis — so a flapping provider
cannot oscillate the model mid-task.

## 4. How consumers use it (and back-compat)

| Consumer | Today | Target |
|---|---|---|
| **Main loop** (`loop.py:305`) | holds one `client` | holds `router`; uses `router.default_client()` for `reasoning`. If constructed with a plain client (no router), behaves exactly as today. |
| **Vision** (`vision_tools.py:222`) | uses session model, fails if no vision | `router.select(VISION, RouteConstraints(needs_vision=True))` → folds the vision model's answer back into the turn. **This is the G fix.** |
| **Title / compaction** (`memory.py`) | session client | `router.select(TITLE_GENERATION)` / `select(COMPACTION)` → cheap model, lower cost |
| **Embeddings** (`memory_vault.py`) | Chroma default MiniLM | `router.select(EMBEDDINGS)` if a provider advertises it; else current default (unchanged) |
| **Sub-agent** (`sub_agent.py:617`) | hardwired `AnthropicClient` | `router.select(REASONING)` honoring session provider — **the D2 fix** |

**Back-compat guarantee:** with no `[routing]` config, every `select(...)` returns the single
configured `provider.model` (the `RoutingPolicy` fallback in [14](14-capability-registry.md) §5),
so behavior is byte-for-byte today's.

**One-line opt-in to the full benefit (Gate-C amendment A1).** Because the conservative default
neutralizes routing's marquee wins (vision auto-route, cheap title/compaction would otherwise never
activate), a single flag `[routing] auto = true` derives a **sensible default policy from the
registry** — cheapest capable model for `title_generation`/`compaction`, any vision-capable model
for `vision`, the session model for `reasoning` — so users get the benefit without hand-writing a
per-capability table. The conservative default stays the default; `auto` makes the upgrade trivial,
not invisible.

## 5. Failover & retry (composed, not duplicated)

Routing produces the **client**; resilience ([13](13-provider-architecture.md) §5) produces the
**robustness**. `ResolvedModel.client` is a `ResilientClient` whose chain is
`[primary, …fallbacks]`. Sequence on a call:

```
generate() → primary: timeout+retry(backoff) under breaker
   on terminal failure → record health, open breaker if threshold
   → fallback[0]: same wrapper → … → exhausted → raise ProviderError(chain, last_error)
each transition emits: span event + `provider.failover` runtime event (observability)
```

Retry policy and breaker thresholds are config (`[routing.resilience]`), defaulted sanely
(3 attempts, 60s timeout, breaker at 5 consecutive failures / 30s cooldown).

## 6. Wiring (boot)

```python
# gateway/orchestrator.py  (in/after the provider-build step ~:1663)
providers = ProviderRegistry.from_config(config, secret_store)
registry  = ModelRegistry.build(config, providers)
policy    = RoutingPolicy.from_config(config)              # back-compat synth if absent
router    = ModelRouter(registry, policy, providers, RetryPolicy.from_config(config))
# loop gets the router; default_client() preserves today's single-client path
loop = ExecutionLoop(llm_client=router.default_client(), router=router, ...)
```

`BootDeps` gains `router` so tools (vision/voice/search) resolve capabilities without new
plumbing. This is the natural extension of the existing wiring, and shrinks—not grows—the
hardcoded-model surface in `boot_agent`.

## 7. What it touches

`core/routing/router.py` (new); `core/loop.py:305` (optional `router=` param, default-compatible);
`gateway/orchestrator.py:1663` (construct + inject); `core/sub_agent.py:617` (route, don't
hardwire); `tools/vision_tools.py:222` (auto-route); `core/memory.py` (cheap title/compaction
route, optional). All additive; the loop's public behavior is unchanged when no router/policy is
configured.

## 8. What could break (and the guard)

- **Vision turns now succeed where they used to fail** (behavior improvement, but a change).
  *Guard:* E2E test — Haiku session + `view_image` with a configured vision candidate →
  routed to the vision model; with none configured → today's behavior (graceful text fallback,
  `vision_tools.py:235`).
- **Cheaper title/compaction model changes outputs slightly.** *Guard:* opt-in only; default
  keeps the session model; covered by snapshot tests on the compaction summary shape, not text.
- **NoRouteError is a new failure mode.** *Guard:* only reachable with explicit constraints that
  no model meets; surfaced as a clear error + event, never a silent hang.

## 9. Deferred (seam only, per §4a)

Latency- and quality-aware routing from live telemetry (descriptors carry no score today —
ADR-0001); user-preference learning; budget-aware *automatic* downgrade (the hook exists via
`max_input_cost_per_mtok`, but auto-policy is deferred); A/B and shadow routing. Each is a new
ordering strategy behind `select()` step 5 — no consumer change.
