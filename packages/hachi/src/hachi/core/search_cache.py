"""In-memory search result cache with TTL and dedup (Initiative A — Search Platform).

:class:`SearchCache` is keyed on ``(provider_name, normalized_key, params_hash)``
and evicts entries after ``ttl_seconds``.  Identical in-session queries collapse
to a single provider call (dedup via same cache key).

The seam accepts a persistent backend later (e.g. SQLite or Redis) without
touching the call sites — swap the backing store, not the interface.

Design doc 17 §5.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_query(query: str) -> str:
    """Return a canonical form of *query* for cache keying.

    Lowercases and strips leading/trailing whitespace so trivially equivalent
    queries (different capitalisation, extra spaces) share a cache entry.
    """
    return " ".join(query.lower().split())


def _params_hash(params: dict[str, Any] | None) -> str:
    """Return a short hex hash of the extra params dict for the cache key."""
    if not params:
        return "default"
    serialised = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()[:16]


class _CacheEntry:
    """One cached result."""

    __slots__ = ("value", "stored_at")

    def __init__(self, value: Any, stored_at: float) -> None:
        self.value = value
        self.stored_at = stored_at


class SearchCache:
    """TTL'd in-memory cache for search and extract results.

    Provides dedup: identical ``(provider, normalized_key, params)`` tuples
    within one session collapse to the first result until TTL expiry.

    Thread-safe via a single ``threading.Lock`` (single-writer, single-reader
    per key; contention is low in practice).

    Args:
        ttl_seconds: Time-to-live per entry in seconds.  ``0`` or negative
                     disables the cache entirely (all lookups miss).
        max_entries:  Maximum number of entries before the oldest is evicted.
                      ``0`` = unlimited.
    """

    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, _CacheEntry] = {}
        self._insertion_order: list[str] = []  # for LRU-style eviction
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def make_search_key(
        provider: str,
        query: str,
        *,
        limit: int = 5,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Build a canonical cache key for a search call."""
        norm = _normalize_query(query)
        ph = _params_hash({"limit": limit, **(extra or {})})
        return f"search:{provider}:{norm}:{ph}"

    @staticmethod
    def make_extract_key(provider: str, url: str, *, extra: dict[str, Any] | None = None) -> str:
        """Build a canonical cache key for an extract call."""
        ph = _params_hash(extra)
        return f"extract:{provider}:{url.rstrip('/')}:{ph}"

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return the cached value or ``None`` if absent / expired.

        Args:
            key: A cache key produced by :meth:`make_search_key` or
                 :meth:`make_extract_key`.

        Returns:
            The cached value, or ``None`` on miss/expiry.
        """
        if self._ttl <= 0:
            return None

        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if now - entry.stored_at > self._ttl:
                # Expired — evict lazily.
                del self._store[key]
                try:
                    self._insertion_order.remove(key)
                except ValueError:
                    pass
                logger.debug("SearchCache: expired entry evicted for key=%r", key)
                return None
            return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key*.

        Args:
            key:   Cache key.
            value: The result to cache (any picklable value).
        """
        if self._ttl <= 0:
            return

        now = time.monotonic()
        with self._lock:
            if key not in self._store:
                self._insertion_order.append(key)
            self._store[key] = _CacheEntry(value=value, stored_at=now)
            # Evict oldest when over capacity.
            if self._max > 0 and len(self._store) > self._max:
                oldest = self._insertion_order.pop(0)
                self._store.pop(oldest, None)
                logger.debug("SearchCache: capacity eviction of key=%r", oldest)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry.

        Args:
            key: Cache key to remove.
        """
        with self._lock:
            self._store.pop(key, None)
            try:
                self._insertion_order.remove(key)
            except ValueError:
                pass

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._store.clear()
            self._insertion_order.clear()

    def size(self) -> int:
        """Return the current number of stored entries."""
        with self._lock:
            return len(self._store)
