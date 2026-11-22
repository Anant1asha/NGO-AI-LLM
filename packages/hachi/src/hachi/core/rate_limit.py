"""A small in-memory sliding-window rate limiter.

Used to protect the externally-reachable surfaces (channel inbound webhook,
OpenAI-compatible endpoint) from abuse and from runaway cost — each inbound
message can boot/keep an agent session, so a flood is expensive.

Pure and thread-safe; ``allow`` accepts an injectable ``now`` so it is fully
unit-testable without sleeping.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Allow at most ``max_requests`` per ``window_seconds`` per key."""

    def __init__(self, max_requests: int, window_seconds: float):
        self._max = max_requests
        self._window = float(window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record a request for ``key`` and return whether it is within the limit."""
        if self._max <= 0:
            return True  # 0 or negative = disabled
        current = now if now is not None else time.monotonic()
        cutoff = current - self._window
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._max:
                return False
            bucket.append(current)
            return True


class OutboundRateLimiter:
    """Per-provider outbound rate limiter for search / extract calls.

    Tracks calls **per provider** within a sliding window.  The inbound
    :class:`RateLimiter` is unchanged; this is an independent class so the two
    concerns don't share state.

    Also supports a per-**turn** hard cap (``max_per_turn``): a separate counter
    that resets when :meth:`reset_turn` is called (typically at the start of each
    agent turn).

    Args:
        max_per_window:  Maximum calls allowed within ``window_seconds``.
                         ``0`` or negative = window limit disabled.
        window_seconds:  Sliding window duration in seconds.
        max_per_turn:    Maximum calls allowed per agent turn.
                         ``0`` or negative = turn cap disabled.
    """

    def __init__(
        self,
        max_per_window: int,
        window_seconds: float,
        max_per_turn: int = 0,
    ) -> None:
        self._window_limiter = RateLimiter(max_per_window, window_seconds)
        self._max_per_turn = max_per_turn
        self._turn_counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def allow(self, provider: str, now: float | None = None) -> bool:
        """Return ``True`` when the call is within all limits; ``False`` to block.

        Side-effect: records the call when allowed (updates both window and turn
        counters).

        Args:
            provider: Provider name used as the bucket key.
            now:      Injectable wall-clock time (for tests).

        Returns:
            ``True`` when both the sliding-window limit and the per-turn cap
            permit the call.
        """
        # Check turn cap first (cheap).
        if self._max_per_turn > 0:
            with self._lock:
                if self._turn_counts[provider] >= self._max_per_turn:
                    return False

        # Check sliding window (also records the call).
        if not self._window_limiter.allow(provider, now):
            return False

        # Increment turn counter (window already recorded the call).
        if self._max_per_turn > 0:
            with self._lock:
                self._turn_counts[provider] += 1

        return True

    def reset_turn(self, provider: str | None = None) -> None:
        """Reset the per-turn counter for *provider* (or all providers when ``None``).

        Call at the start of each agent turn.

        Args:
            provider: Provider to reset.  ``None`` resets all providers.
        """
        with self._lock:
            if provider is None:
                self._turn_counts.clear()
            else:
                self._turn_counts[provider] = 0

    def current_turn_count(self, provider: str) -> int:
        """Return the number of calls recorded for *provider* in the current turn.

        Args:
            provider: Provider name.

        Returns:
            Call count for this turn.
        """
        with self._lock:
            return self._turn_counts[provider]
