"""Tavily search provider adapter (Initiative A — Search Platform).

This is the ONLY module that may import from the ``tavily`` SDK (domain-boundary
rule, doc 11 §3).  The import is lazy and guarded so the SDK is optional —
the provider degrades gracefully when ``tavily-python`` is not installed or when
no API key is configured.

Design doc 17 §3.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from hachi.core.providers.search import ExtractResult, SearchResult
from hachi.core.resilience import HealthRecorder, RetryPolicy, resilient_call
from hachi.core.routing.capability import Capability

logger = logging.getLogger(__name__)

_TAVILY_KEY_ENV = "TAVILY_API_KEY"
_TAVILY_KEY_REF = "tavily_api_key"
# BB-14: the integrations credential dialog stores the key namespaced as
# "apikey.tavily.tavily_api_key" (oauth_flow.store_apikey_credential), while
# `hachi set tavily_api_key=...` stores the bare name. The provider must check
# BOTH — this list mirrors ProviderRegistry.from_config's detection list, so a
# key saved via the UI both registers the provider AND resolves at call time
# (previously only the bare name was read here, so a UI-saved key registered the
# adapter but every search then failed to find the key → "No Tavily API key").
_TAVILY_KEY_REFS = ("apikey.tavily.tavily_api_key", "tavily_api_key")


def _resolve_api_key(secret_store: Any | None) -> str | None:
    """Resolve the Tavily API key lazily.

    Precedence:
    1. ``secret_store`` (CredentialVault / SecretStore) — both the UI-namespaced
       key and the bare name (see :data:`_TAVILY_KEY_REFS`).
    2. ``TAVILY_API_KEY`` environment variable.

    Returns ``None`` (never raises) when neither is set.
    """
    if secret_store is not None:
        for ref in _TAVILY_KEY_REFS:
            try:
                val: str | None = secret_store.get(ref)
            except Exception:
                val = None
            if val:
                return val
    env_val = os.environ.get(_TAVILY_KEY_ENV)
    return env_val if env_val else None


def _try_import_tavily() -> Any:
    """Return the ``tavily`` module or ``None`` if not installed."""
    try:
        import importlib

        return importlib.import_module("tavily")
    except ImportError:
        return None


class TavilySearchProvider:
    """Search + extract adapter backed by the Tavily API.

    The client is constructed lazily at first use — no network call at import
    or at boot.  If no API key is available, every method returns a clear
    "search not configured" error rather than raising.

    ``crawl`` raises :exc:`NotImplementedError` because Tavily is a
    search+extract API, not a crawl API; the registry capability list reflects
    this so the router never routes a crawl request here.

    Args:
        secret_store: Any object with a ``get(name) -> str | None`` method
                      (SecretStore or CredentialVault).  Used to resolve the
                      Tavily API key lazily.
        retry_policy: Retry/circuit-breaker policy.  Defaults to the
                      global :class:`~hachi.core.resilience.RetryPolicy`.
        provider_name: Registry key.  Defaults to ``"tavily"``.
    """

    def __init__(
        self,
        *,
        secret_store: Any | None = None,
        retry_policy: RetryPolicy | None = None,
        provider_name: str = "tavily",
    ) -> None:
        self._secret_store = secret_store
        self._policy = retry_policy or RetryPolicy()
        self._recorder = HealthRecorder(provider_name, self._policy)
        self.name: str = provider_name
        # Lazy — built on first use.
        self._client: Any | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Return (or build) the Tavily HTTP client.

        Raises:
            RuntimeError: When the SDK is not installed or no API key is set.
        """
        if self._client is not None:
            return self._client

        tavily_mod = _try_import_tavily()
        if tavily_mod is None:
            raise RuntimeError(
                "Search is not available: install 'hachi-og[search]' to enable Tavily search."
            )

        api_key = _resolve_api_key(self._secret_store)
        if not api_key:
            raise RuntimeError(
                "Search is not configured: set TAVILY_API_KEY or store the key via "
                "'hachi secrets --set tavily_api_key'."
            )

        try:
            self._client = tavily_mod.TavilyClient(api_key=api_key)
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize Tavily client: {exc}") from exc

        return self._client

    # ------------------------------------------------------------------
    # SearchProvider interface
    # ------------------------------------------------------------------

    def capabilities(self) -> set[Capability]:
        """Advertise ``{WEB_SEARCH}`` — no crawl capability."""
        return {Capability.WEB_SEARCH}

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Execute a Tavily web search.

        Uses :func:`~hachi.core.resilience.resilient_call` for timeout +
        bounded retry + circuit-breaker.

        Args:
            query: The search query string.
            limit: Maximum number of results (passed as ``max_results``).

        Returns:
            A list of :class:`~hachi.core.providers.search.SearchResult` objects.

        Raises:
            RuntimeError: When no API key / SDK is present.
        """
        client = self._get_client()

        def _call() -> list[SearchResult]:
            raw = client.search(query, max_results=limit, search_depth="basic")
            results: list[SearchResult] = []
            for item in raw.get("results", []):
                results.append(
                    SearchResult(
                        title=str(item.get("title") or ""),
                        url=str(item.get("url") or ""),
                        snippet=str(item.get("content") or ""),
                        score=float(item["score"]) if item.get("score") is not None else None,
                    )
                )
            return results

        return resilient_call(_call, self._policy, self._recorder)  # type: ignore[no-any-return]

    def extract(self, url: str) -> ExtractResult:
        """Fetch and extract readable content from *url* via Tavily.

        Args:
            url: The URL to fetch and extract.

        Returns:
            An :class:`~hachi.core.providers.search.ExtractResult`.

        Raises:
            RuntimeError: When no API key / SDK is present.
        """
        client = self._get_client()

        def _call() -> ExtractResult:
            raw = client.extract(urls=[url])
            # Tavily returns {"results": [{"url": ..., "raw_content": ..., "title": ...}], ...}
            results = raw.get("results") or []
            if results:
                item = results[0]
                return ExtractResult(
                    url=str(item.get("url") or url),
                    content=str(item.get("raw_content") or ""),
                    title=str(item.get("title")) if item.get("title") else None,
                )
            # Fallback: no results but no error
            return ExtractResult(url=url, content="", title=None)

        return resilient_call(_call, self._policy, self._recorder)

    def crawl(self, url: str, *, max_pages: int = 1) -> list[ExtractResult]:
        """Not implemented — Tavily is search+extract only.

        Raises:
            NotImplementedError: Always.  The router must never route crawl
                requests to this provider (capabilities() does not advertise it).
        """
        raise NotImplementedError(
            "TavilySearchProvider does not support crawl. "
            "Use extract() for single-page content extraction."
        )

    def health(self) -> Any:
        """Return the current circuit-breaker health snapshot."""
        return self._recorder.snapshot()
