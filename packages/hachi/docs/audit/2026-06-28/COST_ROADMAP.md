# Cost & Governance Roadmap — post-2026-06-28 audit

Prioritized backlog of what was **not** done in this pass (by ROI ÷ risk), plus what frontier labs do for the same problems. The dominant levers (model routing, caching correctness, observability) are already shipped; what remains is incremental.

## Industry benchmarks (Phase 6) — what others do for the same problems

| Technique | Who | Claimed reduction | Status in Hachi |
|---|---|---|---|
| Explicit prefix caching (`cache_control`) | Anthropic | ~90% on cached input, ~85% latency | **Done** (Anthropic path) |
| Automatic prefix caching | OpenAI | ~50% on cached prefix | **Now visible + correctly priced + not defeated by prompt order** (this audit) |
| Graph/selective memory instead of full history | Mem0 | ~90% fewer tokens | **Done** (selective semantic recall, not bulk load) |
| Summarizing condenser for old turns | OpenHands | ~2× cost reduction | **Partial** — sliding-window compaction exists; LLM-summary condenser is a roadmap item below |
| Prompt compression (keep high-information tokens) | LLMLingua-2 | 2×–5× compression | **Not done** (R4) |
| Tool-output/context compression | Headroom | 60–95% on tool outputs | **Partial** — REST response trimming exists; broader tool-output compression is R5 |

## P1 — high ROI, low risk

- **R1. Pre-warm / verify OpenAI auto-cache on multi-turn.** Now that the prefix is stable (BB-29) and `cached_tokens` is parsed (BB-28), measure real cache_hit_rate across a 5-turn session and confirm OpenAI returns `cached_tokens > 0` on turn 2+. If the prefix is < ~1024 tokens it won't cache — but Hachi's ~5K prefix is well above that. *Effort: measurement only.*
- **R2. Surface `cache_metrics` + `cost.routing_warning` in the web UI spend widget.** The data now flows as runtime events; the frontend spend section should render the per-request cache hit-rate and the routing-cost warning banner. *Effort: small FE change; no backend work.*
- **R3. Weekly cost regression test (Phase 7C).** A CI test that fails if the token count for a fixed set of ~10 standard queries grows > 10% between PRs. Guards the `_CORE_TOOL_NAMES` budget and brain.og size from silent creep (the existing `test_core_tool_set_size_guard` is a start). *Effort: small.*

## P2 — medium ROI

- **R4. Trim/compress brain.og + tool descriptions.** brain.og is ~2,527 tok and several tool schemas are 200–530 tok of verbose description. A tightened brain (dense blocks only on routine turns) + terser tool descriptions could cut another ~1–2K tok/turn. *Risk: tool-use quality; A/B before shipping.*
- **R5. Tool-output compression on the hot path.** REST/tool results can be large; an LLMLingua-style or structured-extract compressor before they re-enter context would cut multi-iteration turns. *Risk: medium; measure quality.*
- **R6. LLM-summarizing condenser for old turns.** Upgrade the sliding-window drop to a cheap-model summary of dropped turns (OpenHands pattern) so long sessions keep context without O(T) growth. *Risk: medium.*
- **R7. Add `cache_observability.py` to the mypy-strict gate.** New cost-critical module; bring it under strict typing (resolve the `asdict` `no-any-return` when added). *Effort: small.*

## P3 — needs a decision / dependency

- **R8. Response cache for identical (prompt → answer) within a TTL.** Deferred this pass to avoid a new dependency (e.g. Redis). A stdlib-only in-process LRU+TTL is viable for single-tenant. *Decision needed: scope + eviction; flagged, not built.*
- **R9. Per-request cost budget with mid-turn context trimming (Phase 7A).** Hard per-turn budget that trims context to fit before calling the LLM. Hachi already has per-turn/session/daily caps that *stop* a turn; trimming-to-fit is the next step. *Risk: behaviour change.*
- **R10. Cost attribution by feature/tag (Phase 7B).** Tag every LLM call with the feature that triggered it (chat / extraction / titling / compaction) for "which feature costs most" analytics. The per-model attribution already exists; add a feature dimension.

## Governance notes
- The daily ledger now includes background extraction spend (BB-31) and voice — `max_daily_cost_usd` is now enforced against the true total.
- The boot guard (BB-30) makes costly routing loud; consider promoting it to a one-time setup-wizard validation so the trap is caught before the first turn, not just logged at boot.
