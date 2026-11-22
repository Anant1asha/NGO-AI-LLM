# 26 — Backward Compatibility Plan

> Phase 2 / Gate B. Every behavior change in the design, its compatibility posture, and the one
> deliberate break (with justification). Default stance: **additive, zero-config-identical**.

## 1. Principle

With no new configuration, **the system behaves byte-for-byte as it does today**. New behavior is
opt-in via config. This is enforced by the default-route synthesis ([14](14-capability-registry.md) §5),
`extra="ignore"` config, additive events, and an unchanged `PROTOCOL_VERSION`.

## 2. Change ledger

| Change | Type | Posture / Guard |
|---|---|---|
| Capability model routing (B) | Additive | No `[routing]` → single session model for all caps (today). Opt-in only. |
| Resilience wrapper (timeout 600s→60s, retries) | Behavior change (improvement) | Default timeout *drops* (better); retries bounded; chaos-tested. A failing call now retries then fails — same terminal outcome, faster. |
| Sub-agent de-lock (`sub_agent.py:617`) | **Behavior change** | Delegation with `model=` now honors session provider instead of forcing Anthropic. *Justified:* the old behavior was a latent bug. Guard: Anthropic sessions unchanged; non-Anthropic sessions tested. |
| Vision auto-route (G) | Additive | Only routes when session model lacks vision **and** a vision candidate is configured; else today's fallback. |
| Cheaper title/compaction model | Additive | Opt-in via `[routing.capabilities]`; default keeps the session model. |
| Event bus (C) | Additive | Producers unchanged; legacy consumers become subscribers; identical SSE output (tested). |
| `core_suspend_workflow` (D) | **Deliberate change** | Was a no-op that **lied** about persistence. Now: fail-honest immediately, then real suspend/resume. See §3. |
| Durable jobs (`func`→`handler`) | Internal | Same observable behavior; jobs now survive restart. |
| New routes/events | Additive | Unknown event types ignored by old clients; `PROTOCOL_VERSION` unchanged. |
| Pricing → registry | Internal | Values migrate verbatim; pinned by test. |
| Model defaults centralized | Internal | Hardcoded `claude-haiku-4-5` sites read the registry default; same effective default. |

## 3. The one deliberate, approved break

`core_suspend_workflow` (`tools/workflow_tools.py:15`) changes from *silently doing nothing while
claiming success* to either **failing honestly** (interim) or **actually suspending and resuming**
(final). This is a correctness fix to a verified false-promise (Gate-A R2), not a regression.
Shipped skills that "pause until X" (`inbox_sentinel.og`, `morning_briefing.og`,
`dnd_coordinator.og`) move from silent-death to working — an improvement, gated by per-skill E2E
tests. **No deprecation cycle is warranted for removing a lie.**

## 4. Deprecations

None required. No public interface is removed. `BaseLLMClient`, `create_llm_client`, the
`ToolRegistry` seam, the existing voice tools, the gateway routes, and the config schema are all
preserved and extended. The existing feature-toggle `CapabilityRegistry` (`orchestrator.py:145`)
keeps its name; the new routing constructs are named to avoid collision
([14](14-capability-registry.md) §2).

## 5. Contract-preservation guards

- **Frontend transport:** the CI `frontend-contract` job + the new frontend-path-vs-OpenAPI check
  ([23](23-api-changes.md) §3) prevent silent route breaks.
- **Stored-shape contracts:** session rows, memory fact dicts (sha256 ids), job dicts, og/schedule
  shapes are extended additively only ([22](22-database-changes.md)).
- **Config:** old TOML loads unchanged (`extra="ignore"`); a precedence test locks behavior.
