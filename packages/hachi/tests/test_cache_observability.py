"""Per-request cache observability: hit-rate + fresh/cached/no-cache cost spread."""

from __future__ import annotations

from hachi.core.cache_observability import cache_call_metrics, format_cache_log
from hachi.core.cost import CostTracker
from hachi.core.llm import TokenUsage


def test_cache_call_metrics_hit_rate_and_cost_spread() -> None:
    # 1000 fresh + 9000 cache-read input on a $1/M model (0.1x read), 100 out @ $5/M.
    m = cache_call_metrics(
        model="claude-haiku-4-5",
        usage=TokenUsage(input_tokens=1000, cache_read_tokens=9000, output_tokens=100),
        input_price=1.0,
        output_price=5.0,
        cache_read_mult=0.1,
    )
    assert m.total_input_tokens == 10000
    assert m.cache_hit_rate == 0.9
    # actual: 1000*1 + 9000*1*0.1 + 100*5 = 1000 + 900 + 500 = 2400 -> $0.0024
    assert abs(m.cost_usd - 0.0024) < 1e-9
    # no-cache: 10000*1 + 100*5 = 10500 -> $0.0105
    assert abs(m.cost_if_no_cache_usd - 0.0105) < 1e-9
    # full-cache: 10000*1*0.1 + 100*5 = 1500 -> $0.0015
    assert abs(m.cost_if_fully_cached_usd - 0.0015) < 1e-9
    assert abs(m.savings_vs_no_cache_usd - (0.0105 - 0.0024)) < 1e-9


def test_cache_call_metrics_no_cache_zero_hit_rate() -> None:
    m = cache_call_metrics(
        model="gpt-4o",
        usage=TokenUsage(input_tokens=5000, output_tokens=10),
        input_price=2.5,
        output_price=10.0,
        cache_read_mult=0.5,
    )
    assert m.cache_hit_rate == 0.0
    assert m.cost_usd == m.cost_if_no_cache_usd  # nothing cached → no savings
    assert m.savings_vs_no_cache_usd == 0.0


def test_cost_tracker_cache_metrics_uses_resolved_pricing() -> None:
    from hachi.core.routing.registry import ModelRegistry

    tracker = CostTracker(registry=ModelRegistry.build(object(), None))
    d = tracker.cache_metrics("gpt-4o", TokenUsage(input_tokens=0, cache_read_tokens=1_000_000))
    # gpt-4o cache read mult 0.5: 1M * $2.5 * 0.5 = $1.25
    assert abs(float(d["cost_usd"]) - 1.25) < 1e-9
    assert d["cache_hit_rate"] == 1.0
    assert d["model"] == "gpt-4o"


def test_snapshot_includes_cache_hit_rate() -> None:
    tracker = CostTracker()
    tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=1000, cache_read_tokens=3000))
    d = tracker.snapshot().to_dict()
    assert d["cache_hit_rate"] == 0.75  # 3000 / 4000


def test_format_cache_log_is_one_line() -> None:
    m = cache_call_metrics(
        model="x", usage=TokenUsage(input_tokens=10), input_price=1.0, output_price=2.0
    )
    line = format_cache_log(m)
    assert "[cache]" in line and "hit_rate" in line and "\n" not in line
