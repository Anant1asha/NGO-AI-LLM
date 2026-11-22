# Hachi Architecture Investigation — Phase 1 (Gate A)

> **Status:** Gates A & B passed; **Phase 3 (REVIEW) complete — Gate C ready** (2026-06-21). Phase 4 (implementation) pending go-ahead.
> **Scope:** Forward-looking architecture of Hachi against the nine platform initiatives
> (Search, Model Routing, Events, Long-running Agents, Files, Voice, Vision, Observability,
> Multi-provider).
> **Baseline:** `main` @ `3d4fbe2`. All claims carry `file:line` evidence.
> **Approved scope decisions:** B-first sequencing · contract+one-impl+seam per initiative ·
> Langfuse as config-driven opt-in (console default) · single-node/single-user target.

This is **assessment only**. No design decisions are made here — those belong to
Phase 2 (Gate B). The purpose of these reports is to establish, in durable form,
*what exists, how good the seams are, and what the gap is* before any architecture
is proposed.

## Method

Eight focused, **read-only** investigators ran in parallel over the codebase
(architecture spine; provider/model routing; events/jobs/long-running execution;
memory/storage/persistence; gateway API/config/reliability; search/HTTP/ingestion;
multimodal files/vision/voice; observability/cost). Their findings were synthesized
and the highest-leverage / most surprising claims were **re-verified directly in
source** by the architect (not accepted from the subagents):

- `core_suspend_workflow` is a no-op "false promise" — verified at `tools/workflow_tools.py:15-21`.
- Sub-agent delegation hardwires Anthropic — verified at `core/sub_agent.py:617-630`.
- Background-job durability is inert — verified at `jobs/queue.py:617-626`.

## Reports

| # | Report | What it answers |
|---|--------|-----------------|
| 01 | [Architecture Analysis](01-architecture-analysis.md) | The system as it is: modules, dependency graph, abstractions, DI/wiring, patterns, integration points. |
| 02 | [Current State Assessment](02-current-state.md) | Existing vs missing abstractions, and a **readiness scorecard for each of the nine initiatives (A–I)**. |
| 03 | [Technical Debt Assessment](03-tech-debt.md) | Coupling, duplication, false-promise code, and the debt that will block the initiatives. |
| 04 | [Extension Point Analysis](04-extension-points.md) | Every seam where new capability lands, mapped to the initiatives. |
| 05 | [Risk Assessment](05-risk-assessment.md) | Architectural / operational / security / reliability / performance / migration risks, each with severity · likelihood · mitigation. |

## Phase 2 — Design set (toward Gate B)

Locked numbering. ✅ done · ⏳ pending. Each doc states: the contract, one concrete
implementation, the extension point, what it touches, and what could break.

| # | Doc | Initiative | Status |
|---|-----|-----------|--------|
| 06 | [Gap Analysis](06-gap-analysis.md) | all | ✅ |
| 10 | [Target Architecture](10-target-architecture.md) | all | ✅ |
| 11 | [Domain Boundaries](11-domain-boundaries.md) | all | ✅ |
| 12 | [Event Architecture](12-event-architecture.md) | C | ✅ |
| 13 | [Provider Architecture](13-provider-architecture.md) | B, I | ✅ |
| 14 | [Model & Capability Registry](14-capability-registry.md) | B | ✅ |
| 15 | [Model Routing](15-model-routing.md) | B → G, I | ✅ |
| 16 | [Durable Execution & Agent Runtime](16-durable-execution.md) | D | ✅ |
| 17 | [Search Platform](17-search-platform.md) | A | ✅ |
| 18 | [File / Attachment Platform](18-attachment-platform.md) | E | ✅ |
| 19 | [Voice Platform](19-voice-platform.md) | F | ✅ |
| 20 | [Vision Platform](20-vision-platform.md) | G | ✅ |
| 21 | [Observability (Langfuse)](21-observability.md) | H | ✅ |
| 22 | [Database Changes](22-database-changes.md) | cross-cutting | ✅ |
| 23 | [API Changes](23-api-changes.md) | cross-cutting | ✅ |
| 24 | [Configuration Changes](24-configuration-changes.md) | cross-cutting | ✅ |
| 25 | [Migration Strategy](25-migration-strategy.md) | cross-cutting | ✅ |
| 26 | [Backward Compatibility](26-backward-compatibility.md) | cross-cutting | ✅ |
| 27 | [Testing Strategy](27-testing-strategy.md) | cross-cutting | ✅ |
| 28 | [Rollout Plan](28-rollout-plan.md) | cross-cutting | ✅ |

**ADRs:** [0001 — Capability-based model routing](adr/0001-capability-based-model-routing.md) ✅ ·
[0002 — `AIProvider` capability interface](adr/0002-aiprovider-capability-interface.md) ✅ ·
[0003 — Event bus over the emit funnel](adr/0003-event-bus-over-emit-funnel.md) ✅ ·
[0004 — Durable run-state on the SQLite job substrate](adr/0004-durable-run-state-on-sqlite-job-substrate.md) ✅ ·
[0005 — Observability correlation + injected exporter](adr/0005-observability-correlation-and-injected-exporter.md) ✅

**Phase 3 (REVIEW) is complete — [29 Design Review & Justification](29-design-review.md) is the
Gate-C artifact and the binding amendment overlay:** it challenges the design against itself, and
its 13 findings forced 9 concrete amendments (turn-granular resume, smart-default routing, async
span export, `JobContext`, wait-timeout sweep, honest vendor boundary, …). Where 29 amends a detail
in docs 06–28, **29 governs**; the material changes were also applied inline (docs 15, 16, 21,
ADR-0004).

**Gate C: the design survives its own critique as amended — ready for Phase 4** (implementation in
small, flag-gated, tested, backward-compatible slices per the [rollout plan](28-rollout-plan.md),
starting with slice 2.1).

## Headline

**The spine is genuinely well-factored.** The execution loop is provider-agnostic, the
`anthropic` SDK is confined to one file (`core/llm.py`), tools register through a
declarative manifest, memory and secrets sit behind real interfaces, and the module
graph has exactly one layering violation. Hachi is *not* a greenfield — several
initiatives (Voice, Vision, Search-infra, Events-taxonomy, Memory-provider) already
have partial seams.

**The gap is concentrated, not diffuse.** Four structural absences gate the ambitious
half of the backlog: (1) there is **no model registry or capability router** — one model
per session, hardcoded names in business logic, and the one multi-model path is
provider-locked; (2) there is **no event bus and no durable agent run-state** — events are
a one-way in-memory log, and `core_suspend_workflow` lies about persistence; (3) there is
**no resilience layer** — zero retry/backoff/circuit-breaking anywhere; (4) there is **no
end-to-end correlation id**, so Langfuse-grade tracing has no spine to hang on. None of
these require a rewrite — each has a clean, identified insertion seam.

**Scope note (carried into Gate B):** the brief asks for nine platforms; building all the
speculative machinery at once (replay, dead-letter queues, multi-region, eight providers,
real-time voice) would be over-reach for Hachi's current single-node, single-user posture.
The recommended posture is *contract + one implementation + a documented seam* per
initiative, phased — argued in report 05 and to be made concrete at Gate B.
