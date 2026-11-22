"""Per-request cache & cost observability.

Turns a single LLM call's :class:`~hachi.core.llm.TokenUsage` into a rich,
serialisable breakdown: how much input was fresh vs served from cache, the cache
hit-rate, the actual USD cost, and — crucially for governance — what the same
call *would* have cost with no cache and with a full cache. That spread makes the
value (or absence) of prompt caching visible per request instead of hidden inside
an aggregate spend number.

This is a pure module (no I/O, no globals) so it can be unit-tested and reused by
the execution loop, the gateway spend endpoints, and offline log analysis alike.

Wiring: :meth:`hachi.core.cost.CostTracker.cache_metrics` resolves per-model
pricing and calls :func:`cache_call_metrics`; the execution loop emits the result
as a ``cache_metrics`` runtime event after every generation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from hachi.core.llm import TokenUsage


@dataclass(frozen=True, slots=True)
class CacheCallMetrics:
    """Cache/cost breakdown for one LLM generation.

    Costs are USD. ``cache_hit_rate`` is the fraction of *input* tokens served from
    cache (0.0–1.0). ``cost_if_no_cache_usd`` prices every input token at the full
    rate; ``cost_if_fully_cached_usd`` prices the non-output input as if it had all
    been a cache read — the two bracket what caching can save on this call.
    """

    model: str
    fresh_input_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    output_tokens: int
    total_input_tokens: int
    cache_hit_rate: float
    cost_usd: float
    cost_if_no_cache_usd: float
    cost_if_fully_cached_usd: float
    savings_vs_no_cache_usd: float

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


def cache_call_metrics(
    *,
    model: str,
    usage: TokenUsage,
    input_price: float,
    output_price: float,
    cache_read_mult: float = 0.1,
    cache_write_mult: float = 1.25,
) -> CacheCallMetrics:
    """Compute the cache/cost breakdown for one call.

    Args:
        model: Model id (echoed into the result for log/telemetry grouping).
        usage: The call's token usage. ``input_tokens`` is the FRESH (non-cached)
            portion; ``cache_read_tokens`` / ``cache_creation_tokens`` are separate
            mutually-exclusive counters (Anthropic-style accounting, which the
            OpenAI path is normalised to as well).
        input_price: USD per 1M input tokens for *model*.
        output_price: USD per 1M output tokens for *model*.
        cache_read_mult: Cache-read price multiplier vs input (Anthropic ~0.1,
            OpenAI ~0.5).
        cache_write_mult: Cache-write price multiplier vs input (Anthropic ~1.25).

    Returns:
        A :class:`CacheCallMetrics`.
    """
    fresh = max(0, int(usage.input_tokens))
    cache_read = max(0, int(usage.cache_read_tokens))
    cache_creation = max(0, int(usage.cache_creation_tokens))
    output = max(0, int(usage.output_tokens))
    total_input = fresh + cache_read + cache_creation

    def _usd(
        in_tokens_at_full: float, cache_read_tokens: float, cache_write_tokens: float
    ) -> float:
        return (
            in_tokens_at_full * input_price
            + cache_read_tokens * input_price * cache_read_mult
            + cache_write_tokens * input_price * cache_write_mult
            + output * output_price
        ) / 1_000_000

    cost = _usd(fresh, cache_read, cache_creation)
    # If nothing had been cached: every input token billed fresh at the full rate.
    cost_no_cache = _usd(total_input, 0, 0)
    # If everything had been a warm cache read: all input priced at the read rate.
    cost_full_cache = _usd(0, total_input, 0)

    hit_rate = (cache_read / total_input) if total_input > 0 else 0.0

    return CacheCallMetrics(
        model=model,
        fresh_input_tokens=fresh,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
        output_tokens=output,
        total_input_tokens=total_input,
        cache_hit_rate=round(hit_rate, 4),
        cost_usd=round(cost, 6),
        cost_if_no_cache_usd=round(cost_no_cache, 6),
        cost_if_fully_cached_usd=round(cost_full_cache, 6),
        savings_vs_no_cache_usd=round(max(0.0, cost_no_cache - cost), 6),
    )


def format_cache_log(metrics: CacheCallMetrics) -> str:
    """One-line human-readable summary of a call's cache metrics (for logs)."""
    return (
        f"[cache] model={metrics.model} "
        f"in={metrics.total_input_tokens} "
        f"(fresh={metrics.fresh_input_tokens} read={metrics.cache_read_tokens} "
        f"write={metrics.cache_creation_tokens}) out={metrics.output_tokens} "
        f"hit_rate={metrics.cache_hit_rate:.0%} "
        f"cost=${metrics.cost_usd:.5f} "
        f"(no-cache=${metrics.cost_if_no_cache_usd:.5f}, "
        f"full-cache=${metrics.cost_if_fully_cached_usd:.5f}, "
        f"saved=${metrics.savings_vs_no_cache_usd:.5f})"
    )
