# ADR-0003 — Event bus implemented over the existing emit funnel

- **Status:** Proposed (Gate B)
- **Date:** 2026-06-21
- **Related:** [12](../12-event-architecture.md)

## Context

Events are a one-way in-memory log fanned out through a single funnel
(`orchestrator.py:1484-1498`) to a read-model store + one `on_event` callback. Initiative C
needs publish/subscribe with async dispatch and reactive agents. Every producer already routes
through this one funnel — a Gate-A finding.

## Decision

Introduce an in-process `EventBus` (`publish` / `subscribe(pattern, mode=sync|async)`) and
implement it **over** the existing funnel: the funnel calls `bus.publish()`; the current
read-model/SSE/observability consumers register as the first sync subscribers; reactive
subscribers attach as async subscribers dispatched through the **job queue** (not threads).
Reuse the existing dotted event taxonomy as the bus vocabulary.

## Alternatives considered

1. **External broker (Redis/NATS/Kafka).** Rejected — adds infrastructure and a network hop,
   contradicts the single-node/single-user posture, and provides durability/replay we have no
   consumer for yet. The bus interface does not preclude a broker-backed impl later.
2. **Threading for async subscribers.** Rejected — violates the "prefer queued background work
   over fire-and-forget threads" guardrail; loses durability/retry that the job queue provides.
3. **Persist the event log now (replay-ready).** Deferred — no consumer needs replay on one
   node; `publish()` is the seam to add persistence when one does.

## Consequences

**Positive:** reactive agents (C) with a one-function change at the funnel; producers unchanged;
async work is durable via the queue; the taxonomy becomes the typed contract (leaked literals
promoted). **Negative:** sync-subscriber discipline required (heavy work must be async); the
in-memory cap-2000 log limitation persists until persistence is added (documented seam).
**Reversibility:** high — the bus wraps the funnel additively.
