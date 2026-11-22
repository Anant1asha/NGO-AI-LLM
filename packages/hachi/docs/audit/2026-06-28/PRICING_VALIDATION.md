# Pricing Validation Report — 2026-06-28 (Phase 2)

Research method: WebSearch + WebFetch against official provider pricing pages, cross-checked
against `src/hachi/data/model-registry.json` (as updated by Phase 1, commit `bf9eeb1`).

---

## 1. Existing Entries: 13 models verified

### Anthropic

Prices confirmed via Anthropic platform docs. BB-27 already corrected Opus from the old
Claude-3-Opus rate ($15/$75) to the current Opus-4 rate ($5/$25).

| Model id | JSON input | JSON output | Official | Delta | Action |
|---|---|---|---|---|---|
| `claude-opus-4` | $5.00/M | $25.00/M | $5.00/$25.00 | none | ✅ correct |
| `claude-opus-4-8` | $5.00/M | $25.00/M | $5.00/$25.00 | none | ✅ correct |
| `claude-sonnet-4` | $3.00/M | $15.00/M | $3.00/$15.00 | none | ✅ correct |
| `claude-sonnet-4-6` | $3.00/M | $15.00/M | $3.00/$15.00 | none | ✅ correct |
| `claude-haiku-4` | $1.00/M | $5.00/M | $1.00/$5.00 | none | ✅ correct |
| `claude-haiku-4-5` | $1.00/M | $5.00/M | $1.00/$5.00 | none | ✅ correct |

Cache multipliers verified: `cache_read_mult=0.1` (90% discount, Anthropic native caching) ✅

**Dated model ids:** Anthropic's public pricing page does not distinguish dated variants
(`claude-opus-4-8-20251101` vs `claude-opus-4-8`). The bundled registry uses the family prefix
`claude-opus-4-8`; the prefix-match in `pricing_for_model()` handles dated suffixes correctly.
No change needed.

---

### OpenAI — standard models

| Model id | JSON input | JSON output | Official | Delta | Action |
|---|---|---|---|---|---|
| `gpt-4o` | $2.50/M | $10.00/M | $2.50/$10.00 | none | ✅ correct |
| `gpt-4o-mini` | $0.15/M | $0.60/M | $0.15/$0.60 | none | ✅ correct |
| `gpt-4.1` | $2.00/M | $8.00/M | $2.00/$8.00 | none | ✅ correct |
| `gpt-4.1-mini` | $0.40/M | $1.60/M | $0.40/$1.60 | none | ✅ correct |

Cache multipliers: `cache_read_mult=0.5` (50% cached-input discount, OpenAI automatic prompt
caching) ✅. OpenAI does not charge a separate cache-write fee; `cache_write_mult=1.0` ✅.

---

### OpenAI — o-series (reasoning)

| Model id | JSON input | JSON output | Research | Delta | Action |
|---|---|---|---|---|---|
| `o3` | $10.00/M | $40.00/M | $2.00/$8.00 | −80% | ⚠️ FLAGGED |
| `o3-mini` | $1.10/M | $4.40/M | $0.55/$2.20 | −50% | ⚠️ FLAGGED |
| `o4-mini` | $1.10/M | $4.40/M | $1.10/$4.40 | none | ✅ confirmed |

**o3 and o3-mini — flagged, not changed:**
Web research returned $2/$8 for o3 and $0.55/$2.20 for o3-mini. OpenAI has made several
price cuts to the o-series throughout 2025. However, the research could not be independently
verified from a definitively authoritative source (the scrape may have reflected a cached or
wrong page). **No JSON change made.** A maintainer should manually confirm at
https://openai.com/api/pricing and update the JSON + add a BB entry if the price has dropped.

Action: open a follow-up ticket; add BB-32 when the correction is confirmed.

---

## 2. New providers added

### Google Gemini

No Gemini entries existed before this phase. Added three Gemini 2.5 entries reflecting the
official Gemini API pricing page (ai.google.dev/pricing):

| Model id | Input | Output | Cache read | Context |
|---|---|---|---|---|
| `gemini-2.5-pro` | $1.25/M | $10.00/M | 10% (0.1×) | 1 M tokens |
| `gemini-2.5-flash` | $0.30/M | $2.50/M | 10% (0.1×) | 1 M tokens |
| `gemini-2.5-flash-lite` | $0.10/M | $0.40/M | n/a | 1 M tokens |

Notes:
- Google uses implicit context caching (no explicit breakpoints); `cache_read_mult=0.1` is
  the approximate effective rate (cached reads ≈ 10% of normal input price).
- Flash-Lite does not support context caching; `supports_prompt_caching=false`.
- Gemini models are reachable via OpenAI-compatible endpoints (Gemini API, Vertex AI); no new
  provider adapter is required.
- Capabilities: 2.5 Pro and Flash have `VISION` (multimodal); Flash-Lite is text-only.
- Prices for long-context (>200K token) requests to 2.5 Pro are 2× per-token; our single
  `input_per_mtok` field stores the short-context rate. Flag for multi-tier pricing support.

---

### xAI / Grok

Added `grok-3` with **estimated** pricing. xAI's pricing page (x.ai/api) was not reliably
fetchable during this research pass; values below are best estimates from aggregated sources.

| Model id | Input | Output | Context | Status |
|---|---|---|---|---|
| `grok-3` | $3.00/M | $15.00/M (est.) | 131 072 | ⚠️ estimated |

**Needs manual verification** at https://x.ai/api before routing real traffic. If the price
differs, correct the JSON entry and add a BB entry.

---

## 3. Not added

### OpenRouter

OpenRouter is a routing platform, not a model provider. It passes through requests to
underlying providers (Anthropic, OpenAI, Google, etc.) with a ~5.5% platform fee on credit
purchases. Per-token costs match the underlying provider's rates.

Decision: no per-model entries added. Users who configure an OpenRouter API key set their
`provider.base_url` to the OpenRouter endpoint and use standard model IDs (e.g. `claude-opus-4-8`
or `openai/gpt-4o`). The existing registry entries serve pricing lookup regardless of
whether traffic routes through OpenRouter.

---

## 4. Pricing refresh process

1. Visit each provider's official pricing page (links below).
2. Diff the retrieved prices against `src/hachi/data/model-registry.json`.
3. For each delta: write a failing test asserting the correct price, fix the JSON, add a
   BB entry in `docs/bug-bank.md`, run `uv run python scripts/preflight.py --quick`.
4. Commit as `fix: correct <provider> pricing in model-registry.json`.

**Official sources:**
- Anthropic: https://www.anthropic.com/pricing
- OpenAI: https://openai.com/api/pricing
- Google Gemini: https://ai.google.dev/pricing
- xAI Grok: https://x.ai/api
- OpenRouter: https://openrouter.ai/pricing (pass-through; use underlying provider prices)

**Cadence:** quarterly or on any major model launch. The `test_all_json_entries_in_model_pricing`
and `TestPricingParity` tests catch structural issues but not price drift; drift requires a
human re-read of the official pages.

---

## 5. Open items

| # | Item | Priority |
|---|---|---|
| P1 | Manually verify o3 and o3-mini prices; correct + BB-32 if changed | High |
| P2 | Manually verify grok-3 pricing via x.ai/api | High |
| P3 | Decide multi-tier pricing support (Gemini long-context >200K) | Medium |
| P4 | Add `gemini-2.0-flash` (deprecate? overlap with 2.5 flash-lite) | Low |
| P5 | Add `grok-3-mini` once pricing is confirmed | Low |
