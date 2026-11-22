"""LLM-callable web search and content extraction tools (Initiative A).

Registers three tools:

- ``web_search``   — query the web and return ranked result snippets.
- ``extract_url``  — fetch and extract readable content from a URL.

Each tool call follows the security pipeline:

1. Outbound rate-limit check (per-provider bucket, per-turn cap).
2. Cache lookup — identical in-session queries collapse to one provider call.
3. :func:`~hachi.core.net_guard.validate_outbound_url` for extract_url URLs
   (SSRF mitigation).
4. :func:`~hachi.core.resilience.resilient_call` wrapping — timeout + retry +
   circuit-breaker via the provider itself.
5. :func:`~hachi.core.untrusted_content.guard_untrusted` — every result is
   unconditionally framed as untrusted data before reaching the model.
6. Cache store.

Design doc 17 §4.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from hachi.core.net_guard import validate_outbound_url
from hachi.core.rate_limit import OutboundRateLimiter
from hachi.core.search_cache import SearchCache
from hachi.core.untrusted_content import guard_untrusted

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool JSON schemata
# ---------------------------------------------------------------------------

WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "name": "web_search",
    "description": (
        "Search the web for up-to-date information and return ranked result snippets. "
        "Use this to look up current facts, news, documentation, or anything that may "
        "have changed after the model's knowledge cut-off. Results are returned as a "
        "numbered list of title + URL + excerpt."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default 5, max 10).",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    },
}

EXTRACT_URL_SCHEMA: dict[str, Any] = {
    "name": "extract_url",
    "description": (
        "Fetch a specific URL and extract its readable content as plain text. "
        "Use this when you have an exact URL (e.g. from a web_search result) and want "
        "the full page body rather than a snippet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The http(s) URL to fetch and extract.",
            },
        },
        "required": ["url"],
    },
}


# ---------------------------------------------------------------------------
# Tool factories
# ---------------------------------------------------------------------------


def _make_web_search(
    provider: Any,
    cache: SearchCache,
    limiter: OutboundRateLimiter,
) -> Callable[[str, int], str]:
    """Return the ``web_search`` tool function."""

    def web_search(query: str, limit: int = 5) -> str:
        """Execute a web search and return formatted results."""
        limit = min(max(1, limit), 10)

        # 1. Outbound rate-limit check.
        if not limiter.allow(provider.name):
            return (
                "Rate limit exceeded: too many search calls this turn. "
                "Try again in the next turn or reduce the number of search queries."
            )

        # 2. Cache lookup.
        cache_key = SearchCache.make_search_key(provider.name, query, limit=limit)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("web_search: cache hit for query=%r", query)
            return str(cached)

        # 3. Execute search (resilient_call is inside the provider).
        try:
            results = provider.search(query, limit=limit)
        except Exception as exc:
            logger.warning("web_search: provider error: %s", exc)
            return f"Search failed: {exc}"

        # 4. Format result.
        if not results:
            formatted = "No results found."
        else:
            lines: list[str] = [f"Search results for: {query!r}\n"]
            for i, r in enumerate(results, 1):
                score_str = f" (score: {r.score:.2f})" if r.score is not None else ""
                lines.append(f"{i}. **{r.title}**{score_str}")
                lines.append(f"   {r.url}")
                lines.append(f"   {r.snippet}")
                lines.append("")
            formatted = "\n".join(lines).strip()

        # 5. Guard untrusted content.
        guarded: str
        guarded, _flagged = guard_untrusted(formatted, source=f"web search ({provider.name})")

        # 6. Cache store.
        cache.set(cache_key, guarded)

        return guarded

    return web_search


def _make_extract_url(
    provider: Any,
    cache: SearchCache,
    limiter: OutboundRateLimiter,
) -> Callable[[str], str]:
    """Return the ``extract_url`` tool function."""

    def extract_url(url: str) -> str:
        """Fetch and extract readable content from a URL."""
        # 1. Outbound rate-limit check.
        if not limiter.allow(provider.name):
            return (
                "Rate limit exceeded: too many extract calls this turn. "
                "Try again in the next turn."
            )

        # 2. Cache lookup.
        cache_key = SearchCache.make_extract_key(provider.name, url)
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("extract_url: cache hit for url=%r", url)
            return str(cached)

        # 3. SSRF check (before any network call).
        result = validate_outbound_url(url)
        if not result.ok:
            return f"Blocked URL: {result.reason}"

        # 4. Extract (resilient_call is inside the provider).
        try:
            extract = provider.extract(url)
        except Exception as exc:
            logger.warning("extract_url: provider error: %s", exc)
            return f"Extract failed: {exc}"

        body = extract.content or ""
        title_line = f"# {extract.title}\n" if extract.title else ""
        formatted = f"{title_line}<{extract.url}>\n\n{body}".strip()

        # 5. Guard untrusted content.
        guarded: str
        guarded, _flagged = guard_untrusted(formatted, source=url)

        # 6. Cache store.
        cache.set(cache_key, guarded)

        return guarded

    return extract_url


# ---------------------------------------------------------------------------
# Public registration entry point
# ---------------------------------------------------------------------------


def register_search_tools(
    registry: Any,
    provider: Any,
    cache: SearchCache | None = None,
    limiter: OutboundRateLimiter | None = None,
    *,
    gate: Any | None = None,
) -> None:
    """Register ``web_search`` and ``extract_url`` tools onto *registry*.

    Args:
        registry: A :class:`~hachi.core.loop.ToolRegistry` instance.
        provider: A :class:`~hachi.core.providers.search.SearchProvider`
                  implementation (e.g. ``TavilySearchProvider``).
        cache:    A :class:`~hachi.core.search_cache.SearchCache` instance.
                  Defaults to a 300-second TTL in-memory cache.
        limiter:  An :class:`~hachi.core.rate_limit.OutboundRateLimiter` instance.
                  Defaults to a 60-call-per-hour / 10-calls-per-turn limiter.
        gate:     Optional permission gate (currently unused; reserved for future
                  tier-based gating similar to browser_tools).
    """
    if cache is None:
        cache = SearchCache()
    if limiter is None:
        limiter = OutboundRateLimiter(max_per_window=60, window_seconds=3600, max_per_turn=10)

    registry.register(WEB_SEARCH_SCHEMA, _make_web_search(provider, cache, limiter))
    registry.register(EXTRACT_URL_SCHEMA, _make_extract_url(provider, cache, limiter))
    logger.info("search_tools: registered web_search + extract_url via provider=%r", provider.name)
