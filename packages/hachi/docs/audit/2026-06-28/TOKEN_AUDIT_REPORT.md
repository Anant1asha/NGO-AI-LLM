# Token Cost & Governance Audit — Hachi

**Date:** 2026-06-28 · **Branch:** `fix/web-gui-testing-batch` · **Method:** live measurement against the real `.env` keys + cross-check of the actual `sessions.db` ledger. Every number below is measured, not estimated.

---

## Executive summary — why "What is my name?" cost ~$0.06

It is **not** the naive context bloat the audit brief assumed — Hachi already implements prompt caching, selective memory recall, sliding-window history compaction, lazy tool groups, and cache-aware cost math. The real cause is **four compounding factors dominated by a routing misconfiguration the user could not see**:

1. **Wrong model via routing (the dominant lever).** The user's `settings.toml` had `routing.capabilities.reasoning = ["gpt-4o"]`, so **every chat turn was silently routed to `gpt-4o`** ($2.50/$10 per MTok) even though the configured provider model was `gpt-4.1-mini` and the routing default was `gpt-4o-mini`. The model answering the user was the *most expensive one in their config* — ~6× `gpt-4.1-mini`, ~16× `gpt-4o-mini`.
2. **~6,400 tokens of fixed context per turn.** Even a one-word reply shipped brain.og (2,527 tok) + 23 always-on tool schemas (3,856 tok) = **638× the 10-token user message**.
3. **Zero prompt caching on this path.** The user is on the OpenAI-compatible client, where Hachi's `cache_control` (Anthropic-only) does nothing and OpenAI's `cached_tokens` was never read — so the entire ~6.4K prefix was re-billed at full price every call.
4. **Multi-call fan-out per user turn.** One user message = a main reasoning call + a first-turn title call (+ background fact-extraction in production). Turns that touch memory/skills add ReAct iterations, each re-sending the full prefix.

**Validated against the real ledger:** the reported session (`bd4a3740…`, *"User Name Inquiry and Profile Update Offer"*) recorded **24,216 tokens / $0.0651** across 4 messages — exactly the ~$0.06. Daily spend was running **$1.13–$1.39/day** on mostly trivial testing.

**The displayed cost was accurate, not miscalculated** (gpt-4o is priced correctly). The surprise was that the cost was *real* and the model was *gpt-4o*. A separate latent bug *would* have inflated cost for Opus users (see Finding B).

---

## Phase results

| Phase | Result |
|---|---|
| **0 — Baseline** | Trivial turn: **gpt-4o, 5,958 input tok, $0.014965**. Bare message itself = **10 tok**. Hachi overhead = **638×**. |
| **1A/1B — Context autopsy** | Fixed system = **6,383 tok**: brain.og **2,527** (40%) + **23 tool schemas 3,856** (60%). Biggest tools: `delegate_task` 527, `save_skill` 520. |
| **1C — O(T²) growth** | History is windowed/compacted at ~30 messages — growth is bounded (already handled). |
| **2 — Object graph** | On a plain chat turn, only brain.og is injected (~2.5K). Skills are NOT injected by default (3-pass lazy). The `.og` is *not* the bloat. |
| **3 — Cache observability** | Was **zero**. Anthropic caching is implemented but inert here; OpenAI `cached_tokens` unparsed; no hit-rate surfaced. **Now instrumented.** |
| **4 — UI spend validation** | Ledger figure is **accurate** ($0.0651 real). Not inflated for OpenAI. **But** Opus-4 was mispriced 3× (would inflate Opus users). |
| **5 — Fixes** | 7 code fixes + 1 config change shipped (see `OPTIMIZATIONS_IMPLEMENTED.md`). |
| **6 — Industry benchmarks** | See `COST_ROADMAP.md` (Anthropic/OpenAI caching, condensers, compression). |
| **7 — Governance** | Boot-time cost-routing guard + durable tracking of background spend added. |

---

## Findings

### Confirmed root cause (per-turn cost)
- **F1 — Routing pinned chat to gpt-4o.** `routing.capabilities.reasoning/coding/... = ["gpt-4o"]` (imported-from-legacy config). Fixed in the user's config + guarded Hachi-side. **~16× input price.**
- **F2 — ~6.4K fixed context per turn.** brain.og + 23 tool schemas. Trimmed 4 rarely-used tools to lazy groups (−921 tok measured).
- **F3 — No caching on the OpenAI path.** `cached_tokens` unparsed + the volatile time header sat inside the (otherwise-stable) system message, truncating OpenAI's auto-cache prefix. Both fixed.
- **F4 — Multi-call fan-out.** Main call + title call (+ background extraction). Title routes to a cheap tier already; background extraction spend was untracked (Finding B3).

### Real bugs found (independent of the headline)
- **B1 — Opus-4 family mispriced 3×.** `cost.py` + `descriptor.py` priced `claude-opus-4*` at $15/$75 (legacy Claude-3-Opus rate) instead of $5/$25. Any Opus user saw 3× inflated cost. **Fixed (BB-27).**
- **B2 — OpenAI cached tokens unpriced + Anthropic discount assumed for all.** `cached_tokens` ignored, and `cost.record` hard-coded the 0.1× Anthropic cache multiplier for every provider (OpenAI cached input is ~0.5×). **Fixed (BB-28):** parse `cached_tokens`, honour per-model `cache_read_mult`.
- **B3 — Background fact-extraction spend was invisible.** `extract_facts` ran an LLM call with no cost tracker and never wrote the durable daily ledger — escaping `/spend` and the daily cap. **Fixed (BB-31).**
- **B4 — OpenAI auto-cache defeated by prompt structure.** Volatile time header appended to the system message changed the cacheable prefix every turn. **Fixed (BB-29).**

### Already-optimised (the brief's premise was wrong — do NOT "fix" these)
Anthropic `cache_control` markers (≤4 breakpoints: system + last tool + last 2 messages), selective semantic recall (not bulk memory load), sliding-window compaction (~30 msgs), lazy tool groups, and cache-aware cost math were all already present and correct.

---

## Before / after (measured)

| Metric | Before | After |
|---|---|---|
| Effective chat model | gpt-4o | **gpt-4o-mini** |
| Input tokens / trivial turn | 5,958 | **5,037** |
| **Cost / trivial turn (main call)** | **$0.014965** | **$0.00076** |
| Per-turn reduction | — | **~19.7×** |
| Reported $0.06 session, re-priced | $0.0651 | **~$0.0033 projected** |
| Cache observability | none | per-request `cache_metrics` event |
| Opus-4 displayed cost | 3× inflated | correct ($5/$25) |
| Background extraction spend | untracked | on the durable daily ledger |

See `COST_BASELINE.json` for the full machine-readable dataset and `OPTIMIZATIONS_IMPLEMENTED.md` for per-fix detail. Remaining opportunities are in `COST_ROADMAP.md`.
