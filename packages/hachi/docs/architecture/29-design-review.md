# 29 — Design Review & Justification (Gate C)

> Phase 3. The design is challenged against itself, **revised where the critique lands**, then
> justified. A design that cannot survive its own critique is not ready. Seams are `file:line`.

This document is adversarial first and reassuring second. Part 1 attacks the design; Part 2 lists
the **amendments actually made** in response (the design docs were edited); Part 3 is honest about
over-reach and what is deferred; Part 4 is the required justification; Part 5 is the residual risk
carried into implementation.

---

## Part 1 — Adversarial critique (real weaknesses)

Each finding has a **disposition**: ⟳ Revised (design changed), ⚖ Accepted-with-mitigation, or
⏸ Deferred-honestly.

### A1 — Capability routing is *off* by default, so its headline benefits don't ship ⟳
The back-compat guarantee ("zero config = identical behavior") means `RoutingPolicy` falls back to
the single session model for **every** capability ([14](14-capability-registry.md) §5). So the
two marquee wins — vision auto-route (G) and cheap title/compaction — **never activate** unless the
user hand-writes `[routing.capabilities]`, which most won't. The design preserves compatibility by
neutering its own value.
**Disposition ⟳:** add a one-line opt-in `[routing] auto = true` that derives a *sensible default
policy from the registry* (cheapest capable model for title/compaction; any vision-capable model
for vision; the session model for reasoning). Conservative default stays (zero-config identical);
the full benefit is one flag, not a per-capability table. Revised [15](15-model-routing.md) §4a,
[24](24-configuration-changes.md) §1.

### A2 — Mid-iteration resume is fragile and probably wrong ⟳
[16](16-durable-execution.md) had `resume_cursor` re-enter the loop *mid-turn*. But a turn's live
state is not a cursor — it's the message history, partial tool calls, and in-flight reasoning.
Reconstructing that exactly after a restart is error-prone and a rich source of double-execution
bugs.
**Disposition ⟳ (the most important revision):** suspend/resume operates at **turn granularity**,
not mid-iteration. `core_suspend_workflow` ends the current turn cleanly with `RunState=WAITING`;
on wake, a `resume_run` job **replays history into a fresh turn** (reusing the proven session-resume
machinery, `orchestrator.py:477`) with the wait-result injected as context. No mid-loop
checkpointing; idempotent by construction; matches how the Scheduler already fires fresh turns.
Revised [16](16-durable-execution.md) §2–§3 and [ADR-0004](adr/0004-durable-run-state-on-sqlite-job-substrate.md).

### A3 — `func=`→`handler=` conversion is not mechanical ⟳
Activating `JobRegistry` ([16](16-durable-execution.md) §5) assumed a near-mechanical conversion,
but the existing `func` jobs close over live services (the compaction job closes over the
`MemoryManager` + LLM client, `memory.py:851`). A named handler reconstructed from a serializable
payload has none of that.
**Disposition ⟳:** handlers receive a `JobContext` service-locator (session lookup, vault, router,
memory) so they rebuild context from `{session_id, …}` payloads. Without this, the conversion would
silently break background memory writes. Added to [16](16-durable-execution.md) §5.

### A4 — A waiting run can hang forever ⟳
`wait_for_event` with an event that never fires leaves a run `WAITING` indefinitely. `WaitCondition`
has `timeout_at`, but nothing enforced it.
**Disposition ⟳:** the durable `Scheduler` (`jobs/scheduler.py`, already ticking) sweeps `WAITING`
runs past `timeout_at` and wakes them with a timeout result (or fails them). Added to
[16](16-durable-execution.md) §4.

### A5 — The observability sink, as a sync subscriber, can stall the turn ⟳
[12](12-event-architecture.md)/[21](21-observability.md) registered the trace sink as a *sync*
subscriber. A slow exporter (Langfuse over the network) that doesn't throw still **blocks the turn
thread** — "log-and-continue on exception" doesn't help a slow-but-successful call.
**Disposition ⟳:** use OTel's `BatchSpanProcessor` (async, buffered export) so emission never
blocks the loop; the event→span sink only *enqueues*. Revised [21](21-observability.md) §2/§4.
Also: sync subscribers must not re-enter `publish()` (enqueue instead) — documented constraint in
[12](12-event-architecture.md) §7.

### A6 — One vendor = several adapter objects is confusing ⚖→⟳
The model/service split (ADR-0002) means OpenAI is an `AIProvider` *and* a `SpeechProvider` *and* an
`Embedder` — three objects, three credential resolutions.
**Disposition ⟳ (clarification):** one adapter **class** may implement multiple provider Protocols
(structural typing); `OpenAIProvider` implements all three and the `ProviderRegistry` indexes it
under every capability it advertises. One object, one credential resolution. Clarified
[13](13-provider-architecture.md) §3.

### A7 — The "clean vendor boundary" is already porous — don't overclaim ⟳
The import-linter contract ([11](11-domain-boundaries.md) §3) implied a pure boundary, but
`chromadb` lives in `memory_vault.py` (not `providers/`), and `core/llm.py`/`core/voice.py` import
vendor-shaped code too.
**Disposition ⟳ (honesty):** the contract governs **new** vendor SDKs and the new provider types;
`core/llm.py` and `core/voice.py` are grandfathered; **ChromaDB-behind-`MemoryProvider` is an
acknowledged exception**, and moving it under `providers/` is a deferred larger refactor, not part
of this program. Stating it as "pure" was wrong; revised [11](11-domain-boundaries.md) §3.

### A8 — Reactive agents (C) are partly ahead of demand ⏸
The `EventBus` is genuinely needed: D's wakeups and H's sink both require it. But the broader claim —
"agents react to arbitrary events to start *new* work" — has no concrete consumer today (shipped
skills use suspend/wait, not autonomous event reactions).
**Disposition ⏸:** build the bus (it pays for itself via D + H); ship `file.uploaded → auto-extract`
as the *one* reactive example (E needs it); mark general autonomous reactive agents as a **seam
pending a concrete skill**. Noted in [12](12-event-architecture.md) §8 and Part 3 below.

### A9 — The single-threaded job worker becomes a contention point ⚖
Activating `JobRegistry` routes memory writes, titles, reactive handlers, **and** run-resumes through
one worker (`limit=1`, `queue.py:336`). Under load these serialize; a user-facing resume could queue
behind a slow fact-extraction.
**Disposition ⚖:** for single-node/single-user the job volume is low, so one worker is acceptable
now. Make worker count **configurable (default 1)** and give resume/wake jobs a priority lane, as the
documented seam. Noted [16](16-durable-execution.md) §5 / [28](28-rollout-plan.md). Not building a
pool now (§4a).

### A10 — Boot complexity may rise before it falls ⚖
I claimed `boot_agent` "shrinks," but adding five subsystems to wire could grow it first.
**Disposition ⚖:** each subsystem ships a `from_config(...)` factory; `boot_agent` calls factories,
never inline construction. "Boot stays factory-composed" is an explicit Phase-4 review checkpoint
([28](28-rollout-plan.md) §4), not an aspiration.

### A11 — Undeclared user models are unroutable ⟳
A user's local Ollama model with no `ModelDescriptor` is excluded from `by_capability`, so it can't
serve even the default route.
**Disposition ⟳:** any model without a descriptor defaults to `{REASONING}` so it remains usable;
richer capabilities require a `model_override`. Clarified [14](14-capability-registry.md) §3.

### A12 — Routing could oscillate mid-task ⟳
Health-driven selection means a flapping breaker could switch providers between turns of one task,
yielding inconsistent behavior.
**Disposition ⟳:** resolution is **sticky per capability per turn** (resolve once, reuse), and the
breaker has hysteresis (half-open cooldown). Clarified [15](15-model-routing.md) §3.

### A13 — "Enterprise-grade" file platform is a stub by default ⏸
The virus-scan hook defaults to no-op ([18](18-attachment-platform.md) §4); out of the box there is
no scanning. Calling E "enterprise-grade" describes the *seam*, not the shipped state.
**Disposition ⏸ (honesty):** E is the least-mature initiative; we ship the *interface* (real
integration point) with a no-op default appropriate to a single-user local tool. "Enterprise-grade"
is the trajectory, not 2.4. Stated plainly in Part 3.

---

## Part 2 — Amendments adopted (design actually changed)

| # | Amendment | Docs revised |
|---|---|---|
| A1 | `[routing] auto=true` smart-default policy (one-line opt-in) | 15 §4a, 24 §1 |
| A2 | **Turn-granularity suspend/resume** (replay into a fresh turn; no mid-loop cursor) | 16 §2–3, ADR-0004 |
| A3 | `JobContext` service-locator for handler jobs | 16 §5 |
| A4 | Scheduler sweep enforces `wait` timeouts | 16 §4 |
| A5 | Async `BatchSpanProcessor`; no re-entrant publish | 21 §2/§4, 12 §7 |
| A6 | One adapter class implements multiple provider Protocols | 13 §3 |
| A7 | Honest import-boundary scope (ChromaDB exception named) | 11 §3 |
| A11 | Undeclared models default to `{REASONING}` | 14 §3 |
| A12 | Sticky per-turn routing + breaker hysteresis | 15 §3 |

A8/A9/A10/A13 are dispositioned as honest deferrals/mitigations (not silent).

---

## Part 3 — Where this is more than Hachi needs today (§4a honesty)

The backlog is nine platforms; a solo/early product does not need all of it now. What I am
**designing now but deliberately not building until a consumer exists** (each a documented seam):

- **General reactive agents (C):** build the bus; ship one reactive example; defer autonomous
  event-driven workflows (A8).
- **Modality platforms (A/E/F/G) are phased last (2.4)** and may never be built if demand doesn't
  appear — and that is an acceptable outcome. The *seam* (provider contracts) is the deliverable;
  the *adapters* are on-demand.
- **File platform security/scale (E):** interface now, real scanning + RAG-at-scale later (A13).
- **Streaming voice / conversation mode (F):** explicitly out of scope; batch tools suffice.
- **Worker concurrency, event persistence/replay/DLQ, multi-node storage, Postgres/S3, native
  vendor SDKs, automated pricing feeds:** all seams, no builds (A9; [05](05-risk-assessment.md)).

If forced to cut further, the **minimum viable** slice of this program is **2.1 (routing +
resilience) + the suspend-honesty fix + 2.3 (observability)** — those repay themselves immediately
by fixing verified bugs (the Anthropic-locked sub-agent, the lying suspend, the 600s timeout, the
blind tracing). Everything else is genuinely optional and demand-gated.

## Part 4 — Justification

**1. Correct.** Each construct fixes a *verified* defect or gap (re-read in source at Gate A), not a
hypothetical: the lying suspend (A2 fix is turn-granular and idempotent), the Anthropic-locked
delegation, the unwired durable jobs, the missing retries, the absent correlation id. Contracts are
typed and testable; routing is deterministic given a health snapshot; the one behavior change
(honest suspend) is a correctness fix with per-skill E2E gates.

**2. Scalable (for the stated target).** Single-node/single-user is the explicit target, and the
design meets it with headroom: capability routing spreads load across providers; resilience prevents
cascade; the job queue absorbs async work. The honest ceiling is the single worker (A9) and
in-process bus — both have documented swap-seams (configurable workers; the bus interface admits a
broker-backed impl) so a future hosted pivot is *bounded work at known layers*, not a rewrite.

**3. Maintainable.** New capability arrives via interfaces + a registry + config — not by editing
core logic. Domains have explicit boundaries ([11](11-domain-boundaries.md)) enforced by an
import-linter contract; the vendor boundary is a *test*, not a convention. Boot stays
factory-composed (A10 checkpoint). The stringly-typed tool taxonomy and god-boot-function (Gate-A
debt) are reduced, not grown.

**4. Extensible.** The whole program is "add an adapter / a policy / a subscriber": a provider is one
class + one registration; a capability candidate is one config line; a reactive behavior is one
`subscribe`; a wait kind is one `WaitCondition`; an exporter is one config value. Every "Deferred"
section names the exact seam for the next increment.

**5. Cost-efficient.** Routing enables the cheapest capable model per task (title/compaction → haiku)
and budget-aware constraints; caching/dedup/rate-limit bound search spend. Honestly, some features
*add* cost (vision auto-route's extra call; retries) — so the design *enables* savings rather than
guaranteeing them, and surfaces per-capability cost via the registry + observability so the operator
can tune. Net direction is favorable when `auto` routing is on.

**6. Minimizes regressions.** Default stance is additive + zero-config-identical
([26](26-backward-compatibility.md)); the one deliberate break is removing a lie. Guards: the
default-route synthesis, `extra="ignore"` config, the migration upgrade-from-snapshot test, the
frontend-path-vs-OpenAPI check, the import-linter contract, and per-finding regression tests
([27](27-testing-strategy.md)). The biggest risk (A2 resume) was redesigned specifically to *reuse
proven machinery* rather than invent fragile state reconstruction.

**7. Viable 3–5 years.** Capabilities outlive vendors: modeling the world as `Capability` +
`AIProvider` is the durable abstraction as models/providers churn. The provider/registry/router and
the durable-runtime substrate are the long-lived spine; modality adapters are leaf, replaceable work.
The conditional risk is a hosted/multi-tenant pivot (in-process bus, single worker, local SQLite) —
the seams reduce that cost to specific layers and the ADRs record exactly where the boundaries are,
so the decision (and its price) is explicit rather than discovered late.

## Part 5 — Residual risks carried into implementation

Honest list of what remains *after* the amendments (tracked, not hidden):

- **A2 resume semantics change behavior** (fresh-turn vs mid-thought). Mitigated by being the natural
  semantics for wait-for-X; covered by E2E gates — but skill authors must understand it.
- **A9 single worker** is a real throughput ceiling under unexpected load.
- **A7 ChromaDB sits outside the vendor boundary** until a later refactor.
- **Broad id-stamping (H)** touches many emit sites — wide, shallow regression surface.
- **Degenerate `principal`** (single bearer token) makes the trace's User layer trivial until auth
  grows.
- **Full chaos/contract test matrix** ([27](27-testing-strategy.md)) may exceed a small team's
  sustainable maintenance; prioritize the correctness gates first.

## Verdict

The design **survives its own critique as amended.** Nine of the thirteen attacks forced concrete
design changes (Part 2); the remainder are dispositioned as honest, seam-backed deferrals. The
architecture is correct, additive, extensible, and matched to Hachi's actual single-node scale with
explicit seams to grow. **Gate C: ready for Phase 4 implementation** — to begin with slice 2.1
(provider + routing + resilience) per the [rollout plan](28-rollout-plan.md), behind config, with
the gates in [27](27-testing-strategy.md).
