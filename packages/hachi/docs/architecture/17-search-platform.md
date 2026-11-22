# 17 — Search Platform

> Phase 2 / Gate B. Initiative **A**. Builds on the provider/registry/resilience contracts
> ([13](13-provider-architecture.md)). Contract + one impl + seam. Seams are `file:line`.

## 1. Problem

No web search exists; `browse_web` (`tools/browser_tools.py:114`) needs a user-supplied URL.
The HTTP-safety infrastructure is strong (SSRF + DNS-pin + untrusted-content framing) but there
is no `SearchProvider`, no caching/dedup/rate-limit for outbound calls.

## 2. Contract

```python
# core/providers/search.py
class SearchResult(BaseModel):
    title: str; url: str; snippet: str; score: float | None = None

class ExtractResult(BaseModel):
    url: str; content: str; title: str | None = None

class SearchProvider(Protocol):
    name: str
    def capabilities(self) -> set[Capability]      # {WEB_SEARCH}
    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]: ...
    def extract(self, url: str) -> ExtractResult: ...
    def crawl(self, url: str, *, max_pages: int = 1) -> list[ExtractResult]: ...  # may NotImplemented
```

Selected by capability via `ProviderRegistry.get_search()` ([13](13-provider-architecture.md) §3),
wrapped by `resilient_call` (timeout+retry+breaker) and the outbound rate-limiter.

## 3. One implementation — Tavily

`TavilySearchProvider` (`core/providers/tavily_provider.py`) — the only new vendor import,
confined to `core/providers/*` per the [domain rule](11-domain-boundaries.md) §3. API key from
`CredentialVault`/`SecretStore`. `crawl` raises `NotImplementedError` (Tavily is search+extract);
`ProviderRegistry` reports the capability honestly so the router never offers crawl it can't do.

## 4. Tools (the agent-facing surface)

`tools/search_tools.py` (new) registers `web_search`, `extract_url`, (optionally `crawl`) via the
existing seam: `register_search_tools(registry, provider, cache, limiter)` + a `ToolSpec` in
`TOOL_SPECS` (`orchestrator.py:1833`) + a classify entry. Each tool:
1. rate-limit check (outbound) → 2. cache lookup → 3. `resilient_call(provider.search/extract)`
→ 4. **`guard_untrusted()`** the result (`untrusted_content.py:37`) → 5. cache store → return.

The agent requests search **by capability**; provider name never appears in skills or logic.

## 5. Cost controls (the brief's A requirement)

| Control | Design | Reuse |
|---|---|---|
| Caching | per-session `SearchCache` keyed on `(provider, normalized query/url, params)`, TTL'd | new `core/search_cache.py` (in-memory; the seam accepts a persistent backend later) |
| Dedup | same cache key collapses identical in-session queries/urls | same |
| Rate-limit | outbound `RateLimiter` per provider (the brief's gap — today's `RateLimiter` is inbound only) | extend `core/rate_limit.py:18` for outbound buckets |
| Batching | tool-level parallelism already exists (`loop.py:337`, 4 workers) | reuse |
| Cost visibility | record provider call count/cost into the session cost surface | extend `CostTracker` ([20](20-vision-platform.md) shares the attribution need) |

## 6. What it touches

`core/providers/search.py` + `tavily_provider.py` (new); `tools/search_tools.py` (new);
`core/search_cache.py` (new); `core/rate_limit.py:18` (outbound buckets);
`gateway/orchestrator.py:1833` (`ToolSpec` + `BootDeps` gains `search_provider`);
`core/settings.py` (`[search]` config — provider, limits, cache TTL). Optional gateway
`POST /search` is **deferred** (the tool surface is sufficient for the agent; a REST surface is
a later slice if the UI needs it).

## 7. What could break (and the guard)

- **New outbound network egress.** *Guard:* all calls go through `validate_outbound_url` +
  `resilient_call`; results are `guard_untrusted`-wrapped before reaching the model; an
  injection test asserts a malicious search result cannot issue instructions.
- **Cost surprise at volume.** *Guard:* outbound rate-limiter + cache on by default;
  `[search].max_calls_per_turn` cap.

## 8. Deferred (seam only, per §4a)

Firecrawl/Exa/Brave/SerpAPI adapters; deep-crawl pipelines; structured schema extraction;
result reranking; research orchestration; persistent cross-session cache; a `/search` REST route.
Each is "add an adapter / a strategy / a route" against the contract above.
