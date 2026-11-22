"""Search provider contract (Initiative A — Search Platform).

Defines the pydantic result types and SearchProvider Protocol used throughout
the search stack.  Concrete adapters live in sibling modules (e.g.
``tavily_provider.py``).

Design doc 17 §2 / Gate-C contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from hachi.core.routing.capability import Capability  # noqa: TCH001 (runtime use in Protocol)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    """One search hit returned by a :class:`SearchProvider`.

    Attributes:
        title:   Page title.
        url:     Canonical URL of the result.
        snippet: Text excerpt / description.
        score:   Optional relevance score (0.0–1.0); ``None`` when not provided.
    """

    model_config = ConfigDict(extra="ignore")

    title: str
    url: str
    snippet: str
    score: float | None = None


class ExtractResult(BaseModel):
    """Extracted readable content from a URL.

    Attributes:
        url:     The source URL.
        content: Extracted text body (Markdown or plain text).
        title:   Page title if available.
    """

    model_config = ConfigDict(extra="ignore")

    url: str
    content: str
    title: str | None = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SearchProvider(Protocol):
    """Vendor adapter for web search and content extraction (Initiative A).

    The agent selects providers by capability, not by name, so concrete
    implementations must advertise ``{WEB_SEARCH}`` in :meth:`capabilities`.

    ``crawl`` is optional — providers that do not support deep crawling MUST
    raise :exc:`NotImplementedError` and MUST NOT include a crawl capability
    in :meth:`capabilities` so the router never routes crawl requests to them.
    """

    name: str

    def capabilities(self) -> set[Capability]:
        """Return the set of capabilities this provider supports.

        At minimum a search provider must return ``{Capability.WEB_SEARCH}``.
        """
        ...

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Execute a web search and return ranked results.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            A list of :class:`SearchResult` objects.
        """
        ...

    def extract(self, url: str) -> ExtractResult:
        """Fetch and extract readable content from *url*.

        Args:
            url: The URL to fetch and extract.

        Returns:
            An :class:`ExtractResult` with the page body.
        """
        ...

    def crawl(self, url: str, *, max_pages: int = 1) -> list[ExtractResult]:
        """Crawl a site starting from *url*, following links.

        Args:
            url:       Starting URL.
            max_pages: Maximum number of pages to fetch.

        Returns:
            A list of :class:`ExtractResult` objects.

        Raises:
            NotImplementedError: When this provider does not support crawling.
        """
        ...

    def health(self) -> Any:
        """Return a health snapshot for this provider (optional)."""
        ...
