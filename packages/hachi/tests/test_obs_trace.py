"""Tests for core/obs/trace.py — TraceContext, bind(), current()."""

from __future__ import annotations

import threading

from hachi.core.obs.trace import TraceContext, bind, current


def _make_ctx(**kwargs) -> TraceContext:
    defaults = dict(trace_id="tr-1234", session_id="ses-abcd", principal="p", surface="cli")
    defaults.update(kwargs)
    return TraceContext(**defaults)


# ---------------------------------------------------------------------------
# Basic bind / current
# ---------------------------------------------------------------------------


def test_current_none_outside_bind():
    assert current() is None


def test_bind_sets_current():
    ctx = _make_ctx()
    with bind(ctx) as got:
        assert got is ctx
        assert current() is ctx


def test_current_restored_after_bind():
    ctx = _make_ctx()
    with bind(ctx):
        pass
    assert current() is None


def test_bind_nests_correctly():
    outer = _make_ctx(trace_id="outer")
    inner = _make_ctx(trace_id="inner")
    with bind(outer):
        assert current().trace_id == "outer"  # type: ignore[union-attr]
        with bind(inner):
            assert current().trace_id == "inner"  # type: ignore[union-attr]
        assert current().trace_id == "outer"  # type: ignore[union-attr]
    assert current() is None


# ---------------------------------------------------------------------------
# Thread isolation
# ---------------------------------------------------------------------------


def test_bind_is_thread_local():
    """contextvars are per-thread; the main thread's context is invisible to a worker."""
    ctx = _make_ctx()
    seen: list[TraceContext | None] = []

    def worker():
        seen.append(current())

    with bind(ctx):
        t = threading.Thread(target=worker)
        t.start()
        t.join()

    # The worker has no context (contextvars don't automatically inherit).
    assert seen[0] is None


def test_bind_inside_thread():
    """Workers can independently bind their own TraceContext."""
    ctx = _make_ctx(trace_id="worker-trace")
    results: list[TraceContext | None] = []

    def worker():
        with bind(ctx):
            results.append(current())

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert results[0] is ctx


# ---------------------------------------------------------------------------
# hash_principal
# ---------------------------------------------------------------------------


def test_hash_principal_is_stable():
    h1 = TraceContext.hash_principal("my-token")
    h2 = TraceContext.hash_principal("my-token")
    assert h1 == h2


def test_hash_principal_is_16_chars():
    h = TraceContext.hash_principal("abc")
    assert len(h) == 16


def test_hash_principal_is_hex():
    h = TraceContext.hash_principal("abc")
    int(h, 16)  # raises ValueError if not hex


def test_hash_principal_differs_for_different_inputs():
    assert TraceContext.hash_principal("a") != TraceContext.hash_principal("b")
