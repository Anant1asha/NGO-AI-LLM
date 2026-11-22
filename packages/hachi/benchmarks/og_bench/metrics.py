"""ObjectGraph benchmark metrics (P2-03b/c).

Metrics implemented:
  M1 — Retrieval quality
    P@1   Precision at 1: fraction of queries where rank-1 result is correct.
    P@5   Precision at 5: fraction of queries with ≥1 correct result in top-5.
    R@5   Recall at 5: identical to P@5 when each query has ≥1 expected item.
    MRR   Mean Reciprocal Rank: mean of 1/(rank of first correct result).
    FPR   False-Positive Rate on N-queries: fraction returning any result.

  M2 — Token cost model
    Estimates billed tokens per query using Anthropic pricing (input/cache/output).
    Reports avg tokens_per_query and estimated $/1k-queries.

  M4 — Engine latency model
    Wall-clock time for engine ops (search + peek + resolve) per query.
    Reports avg_engine_ms, rtt_estimate_ms (N_passes × configurable RTT).

  M7 — Pass-depth distribution
    Fraction of queries resolved at Pass-1 / Pass-2 / Pass-3.
    Substantiates (or kills) the "most queries stop at Pass 2" claim.

All metrics are engine-only and deterministic (no LLM calls).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class M1Result:
    """M1 metric values + per-query details."""

    p_at_1: float = 0.0
    p_at_5: float = 0.0
    r_at_5: float = 0.0
    mrr: float = 0.0
    fpr_negative: float = 0.0
    n_queries: int = 0
    n_negative: int = 0
    misses: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)


def _reciprocal_rank(top_k: list[str], expected: list[str]) -> float:
    """Return 1/rank of the first hit, or 0 if no hit in the list."""
    for i, name in enumerate(top_k):
        if name in expected:
            return 1.0 / (i + 1)
    return 0.0


def compute_m1(
    engine: Any,
    probes: list[dict[str, Any]],
    query_types: tuple[str, ...] = ("K", "P", "I"),
    top_k: int = 5,
) -> M1Result:
    """Compute M1 metrics for the given probes against a SkillEngine instance.

    Args:
        engine:      Loaded SkillEngine (must have engine.search(query) → list[dict]).
        probes:      List of probe dicts with ``id``, ``type``, ``query``,
                     ``expected`` (list of skill name strings, empty for N-type).
        query_types: Which probe types to include in P@K / MRR calculations.
        top_k:       Number of results to consider (default 5).
    """
    positive_probes = [p for p in probes if p["type"] in query_types and p["expected"]]
    negative_probes = [p for p in probes if p["type"] == "N"]

    hits_at_1 = 0
    hits_at_5 = 0
    rr_sum = 0.0
    misses: list[str] = []

    for probe in positive_probes:
        results = engine.search(probe["query"])
        top_names = [r["name"] for r in results[:top_k]]
        expected = set(probe["expected"])

        # P@1
        if top_names and top_names[0] in expected:
            hits_at_1 += 1

        # P@5
        if any(n in expected for n in top_names):
            hits_at_5 += 1
        else:
            misses.append(
                f"MISS [{probe['id']}] {probe['query']!r} → "
                f"top5={top_names[:5]}, expected={sorted(expected)}"
            )

        # MRR
        rr_sum += _reciprocal_rank(top_names, list(expected))

    n_pos = len(positive_probes)
    p_at_1 = hits_at_1 / n_pos if n_pos else 0.0
    p_at_5 = hits_at_5 / n_pos if n_pos else 0.0
    r_at_5 = p_at_5  # single-relevant assumption
    mrr = rr_sum / n_pos if n_pos else 0.0

    false_positives: list[str] = []
    n_neg = len(negative_probes)
    fp_count = 0
    for probe in negative_probes:
        results = engine.search(probe["query"])
        if results:
            fp_count += 1
            false_positives.append(
                f"FP [{probe['id']}] {probe['query']!r} → matched {results[0]['name']!r}"
            )
    fpr = fp_count / n_neg if n_neg else 0.0

    return M1Result(
        p_at_1=round(p_at_1, 4),
        p_at_5=round(p_at_5, 4),
        r_at_5=round(r_at_5, 4),
        mrr=round(mrr, 4),
        fpr_negative=round(fpr, 4),
        n_queries=n_pos,
        n_negative=n_neg,
        misses=misses,
        false_positives=false_positives,
    )


def load_probes(probe_file: Path | None = None) -> list[dict[str, Any]]:
    """Load the frozen S-real probe set (or a custom file)."""
    if probe_file is None:
        probe_file = Path(__file__).parent / "s_real_probes.json"
    data = json.loads(probe_file.read_text(encoding="utf-8"))
    return list(data["probes"])


def pick_representative_query(engine: Any) -> str | None:
    """Pick a query that actually resolves to real Pass-3 content.

    C3 fix: the token-savings headline previously picked its "representative"
    query by raw index order (``keywords[0]`` of the first node) with no check
    that it actually loads. On the shipped corpus this could land on a bare
    name defined once per ``roles/*.og`` file (e.g. "identity") — a 6-way
    collision ``resolve_node`` refuses as ambiguous, returning an ``"Error: ..."``
    sentinel string. Measuring that error string's length as "savings" produced
    a dishonest headline number.

    Walks every indexed keyword (``engine._keyword_index``, the same source
    the naive ``keywords[0]`` pick used), searches each one, and returns the
    first keyword whose top search hit actually resolves to real content (not
    an ``"Error: ..."`` sentinel). Returns ``None`` if nothing qualifies.
    """
    for keyword in engine._keyword_index.keys():
        keyword = keyword.strip()
        if not keyword:
            continue
        results = engine.search(keyword)
        if not results:
            continue
        top_name = results[0].get("name")
        if not top_name:
            continue
        resolved = engine.resolve_node(top_name)
        if not resolved.startswith("Error:"):
            return keyword
    return None


# ---------------------------------------------------------------------------
# M7 — Pass-depth distribution
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class M7Result:
    """M7 pass-depth distribution across the probe set."""

    p1_rate: float = 0.0
    p2_rate: float = 0.0
    p3_rate: float = 0.0
    n_queries: int = 0
    pass1_total: int = 0
    pass2_total: int = 0
    pass3_total: int = 0


def compute_m7(
    engine: Any,
    probes: list[dict[str, Any]],
    query_types: tuple[str, ...] = ("K", "P", "I"),
    top_k: int = 5,
) -> M7Result:
    """Compute M7 pass-depth distribution.

    For each positive probe:
    - Pass 1 sufficient: correct skill is rank-1 in search() results.
    - Pass 2 sufficient: correct skill appears in top_k results (no resolve needed).
    - Pass 3 required: correct skill is NOT in top_k (agent would need full load of
      multiple nodes to find it, approximated as needing Pass 3).

    Also reads pass-depth counters from engine if available (``get_usage_counters``).
    """
    positive_probes = [p for p in probes if p["type"] in query_types and p["expected"]]
    n = len(positive_probes)
    if n == 0:
        return M7Result()

    p1_hits = 0
    p2_hits = 0
    p3_hits = 0

    reset = getattr(engine, "reset_usage_counters", None)
    if callable(reset):
        reset()

    for probe in positive_probes:
        results = engine.search(probe["query"])
        top_names = [r["name"] for r in results[:top_k]]
        expected = set(probe["expected"])

        if top_names and top_names[0] in expected:
            p1_hits += 1
        elif any(name in expected for name in top_names):
            p2_hits += 1
        else:
            p3_hits += 1

    # Also grab the engine's own counters for the full report
    counters = {}
    get_counters = getattr(engine, "get_usage_counters", None)
    if callable(get_counters):
        counters = get_counters()

    return M7Result(
        p1_rate=round(p1_hits / n, 4),
        p2_rate=round(p2_hits / n, 4),
        p3_rate=round(p3_hits / n, 4),
        n_queries=n,
        pass1_total=counters.get("pass1_search", p1_hits + p2_hits + p3_hits),
        pass2_total=counters.get("pass2_peek", 0),
        pass3_total=counters.get("pass3_resolve", 0),
    )


# ---------------------------------------------------------------------------
# M2 — Token cost model
# ---------------------------------------------------------------------------

# Anthropic Claude pricing (USD / 1M tokens) — 2026-06 figures.
_PRICE_INPUT = 3.00
_PRICE_CACHE_WRITE = 3.75
_PRICE_CACHE_READ = 0.30
_PRICE_OUTPUT = 15.00


@dataclass(slots=True)
class M2Result:
    """M2 token-cost estimate per query."""

    avg_tokens_pass1: float = 0.0
    avg_tokens_pass2: float = 0.0
    avg_tokens_pass3: float = 0.0
    avg_tokens_total: float = 0.0
    estimated_usd_per_1k_queries: float = 0.0
    n_queries: int = 0


def _tok(text: str) -> int:
    """Estimate token count — uses estimate_tokens if available, else len/4."""
    try:
        from hachi.og_engine.engine import estimate_tokens

        return estimate_tokens(text)
    except ImportError:
        return max(1, len(text) // 4)


def compute_m2(
    engine: Any,
    probes: list[dict[str, Any]],
    query_types: tuple[str, ...] = ("K", "P", "I"),
    top_k: int = 5,
) -> M2Result:
    """Compute M2 token-cost estimates over the probe set.

    For each positive probe, simulates the 3-pass cost:
    - Pass 1: search result JSON tokens (input to LLM for routing)
    - Pass 2: peek result JSON tokens (input to LLM for node selection)
    - Pass 3: resolve tokens for top candidate (input to LLM for skill use)

    Uses estimate_tokens() from the engine module; falls back to len/4.
    Applies Anthropic 2026-06 pricing to estimate $/1k queries.
    """
    import json as _json

    positive_probes = [p for p in probes if p["type"] in query_types and p["expected"]]
    n = len(positive_probes)
    if n == 0:
        return M2Result()

    tok_p1 = tok_p2 = tok_p3 = 0

    for probe in positive_probes:
        results = engine.search(probe["query"])
        candidates = [r["name"] for r in results[:top_k]]

        tok_p1 += _tok(_json.dumps(results[:top_k]))
        if candidates:
            peek_result = engine.peek(candidates)
            tok_p2 += _tok(_json.dumps(peek_result))
            top_candidate = candidates[0]
            resolve_result = engine.resolve_node(top_candidate)
            tok_p3 += _tok(resolve_result)

    avg_p1 = tok_p1 / n
    avg_p2 = tok_p2 / n
    avg_p3 = tok_p3 / n
    avg_total = avg_p1 + avg_p2 + avg_p3

    # Cost: treat all tokens as uncached input for a conservative upper bound.
    cost_per_query_usd = (avg_total / 1_000_000) * _PRICE_INPUT
    usd_per_1k = cost_per_query_usd * 1_000

    return M2Result(
        avg_tokens_pass1=round(avg_p1, 1),
        avg_tokens_pass2=round(avg_p2, 1),
        avg_tokens_pass3=round(avg_p3, 1),
        avg_tokens_total=round(avg_total, 1),
        estimated_usd_per_1k_queries=round(usd_per_1k, 4),
        n_queries=n,
    )


# ---------------------------------------------------------------------------
# M4 — Engine latency model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class M4Result:
    """M4 latency estimates per query."""

    avg_engine_ms: float = 0.0
    rtt_estimate_ms: float = 0.0
    total_estimate_ms: float = 0.0
    n_queries: int = 0
    rtt_per_pass_ms: float = 800.0


def compute_m4(
    engine: Any,
    probes: list[dict[str, Any]],
    query_types: tuple[str, ...] = ("K", "P", "I"),
    top_k: int = 5,
    rtt_per_pass_ms: float = 800.0,
) -> M4Result:
    """Compute M4 engine latency model over the probe set.

    Measures wall-clock time for search() + peek() + resolve_node() per probe.
    RTT estimate assumes one round-trip per pass to the LLM.

    Args:
        engine:           Loaded SkillEngine.
        probes:           Probe list from load_probes().
        query_types:      Which probe types to include.
        top_k:            Number of candidates considered per query.
        rtt_per_pass_ms:  Assumed LLM round-trip latency (ms). Default 800 ms.
    """
    positive_probes = [p for p in probes if p["type"] in query_types and p["expected"]]
    n = len(positive_probes)
    if n == 0:
        return M4Result(rtt_per_pass_ms=rtt_per_pass_ms)

    total_engine_ns = 0

    for probe in positive_probes:
        t0 = time.perf_counter_ns()

        results = engine.search(probe["query"])
        candidates = [r["name"] for r in results[:top_k]]
        if candidates:
            engine.peek(candidates)
            engine.resolve_node(candidates[0])

        total_engine_ns += time.perf_counter_ns() - t0

    avg_engine_ms = (total_engine_ns / n) / 1_000_000
    # 3 passes × RTT per pass
    rtt_estimate_ms = 3.0 * rtt_per_pass_ms

    return M4Result(
        avg_engine_ms=round(avg_engine_ms, 3),
        rtt_estimate_ms=round(rtt_estimate_ms, 1),
        total_estimate_ms=round(avg_engine_ms + rtt_estimate_ms, 1),
        n_queries=n,
        rtt_per_pass_ms=rtt_per_pass_ms,
    )
