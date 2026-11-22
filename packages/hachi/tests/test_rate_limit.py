"""Tests for the sliding-window rate limiter (injected clock — no sleeping)."""

from __future__ import annotations

from hachi.core.rate_limit import RateLimiter


def test_allows_up_to_max_then_blocks() -> None:
    rl = RateLimiter(max_requests=3, window_seconds=60)
    assert rl.allow("k", now=0.0)
    assert rl.allow("k", now=1.0)
    assert rl.allow("k", now=2.0)
    assert not rl.allow("k", now=2.5)  # 4th within the window is blocked


def test_window_expiry_frees_capacity() -> None:
    rl = RateLimiter(max_requests=2, window_seconds=10)
    assert rl.allow("k", now=0.0)
    assert rl.allow("k", now=1.0)
    assert not rl.allow("k", now=2.0)
    assert rl.allow("k", now=11.0)  # the t=0 event aged out of the window


def test_limits_are_per_key() -> None:
    rl = RateLimiter(max_requests=1, window_seconds=60)
    assert rl.allow("a", now=0.0)
    assert rl.allow("b", now=0.0)  # independent bucket
    assert not rl.allow("a", now=1.0)


def test_zero_disables_limiting() -> None:
    rl = RateLimiter(max_requests=0, window_seconds=60)
    assert all(rl.allow("k", now=float(i)) for i in range(100))
