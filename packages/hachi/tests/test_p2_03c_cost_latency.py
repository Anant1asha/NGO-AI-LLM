"""P2-03c: M2 token cost, M4 latency, M7 pass-depth metrics + engine counters.

Tests:
- SkillEngine pass-depth counters (get_usage_counters / reset_usage_counters)
- M7 pass-depth distribution from probe set
- M2 token cost model
- M4 engine latency model
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Engine pass-depth counter tests
# ---------------------------------------------------------------------------


def _loaded_engine():
    """Return a SkillEngine loaded with the shipped default skills."""
    from pathlib import Path

    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    skills_dir = Path(__file__).parent.parent / "src" / "hachi" / "default_skills"
    if skills_dir.exists():
        engine.load_directory(skills_dir)
    return engine


def test_engine_has_pass_depth_counters():
    engine = _loaded_engine()
    assert hasattr(engine, "_pass1_count")
    assert hasattr(engine, "_pass2_count")
    assert hasattr(engine, "_pass3_count")


def test_engine_search_increments_pass1():
    engine = _loaded_engine()
    engine.reset_usage_counters()
    engine.search("weather forecast")
    engine.search("currency exchange")
    assert engine._pass1_count == 2


def test_engine_peek_increments_pass2():
    engine = _loaded_engine()
    engine.reset_usage_counters()
    results = engine.search("weather")
    if results:
        engine.peek([results[0]["name"]])
    assert engine._pass2_count == 1


def test_engine_resolve_increments_pass3():
    engine = _loaded_engine()
    engine.reset_usage_counters()
    results = engine.search("weather")
    if results:
        engine.resolve_node(results[0]["name"])
    assert engine._pass3_count == 1


def test_get_usage_counters_returns_correct_keys():
    engine = _loaded_engine()
    engine.reset_usage_counters()
    engine.search("test")
    counters = engine.get_usage_counters()
    assert set(counters.keys()) == {"pass1_search", "pass2_peek", "pass3_resolve"}
    assert counters["pass1_search"] == 1
    assert counters["pass2_peek"] == 0
    assert counters["pass3_resolve"] == 0


def test_reset_usage_counters_zeroes_all():
    engine = _loaded_engine()
    engine.search("test")
    engine.reset_usage_counters()
    counters = engine.get_usage_counters()
    assert all(v == 0 for v in counters.values())


# ---------------------------------------------------------------------------
# M7 pass-depth distribution
# ---------------------------------------------------------------------------


def _mock_engine(search_map: dict[str, list[str]]) -> Any:
    """Stub engine whose search() returns controlled results."""
    engine = MagicMock()
    engine.search.side_effect = lambda q: [{"name": n} for n in search_map.get(q, [])]
    engine.get_usage_counters.return_value = {
        "pass1_search": 0,
        "pass2_peek": 0,
        "pass3_resolve": 0,
    }
    engine.reset_usage_counters = MagicMock()
    return engine


def _probes_kpn():
    return [
        {"id": "k001", "type": "K", "query": "currency", "expected": ["core_currency"]},
        {"id": "k002", "type": "K", "query": "weather", "expected": ["core_weather"]},
        {"id": "n001", "type": "N", "query": "nonsense xyz", "expected": []},
    ]


def test_m7_all_pass1():
    from benchmarks.og_bench.metrics import compute_m7

    engine = _mock_engine({"currency": ["core_currency"], "weather": ["core_weather"]})
    m7 = compute_m7(engine, _probes_kpn())
    assert m7.p1_rate == 1.0
    assert m7.p2_rate == 0.0
    assert m7.p3_rate == 0.0
    assert m7.n_queries == 2


def test_m7_pass2_when_not_rank1():
    from benchmarks.og_bench.metrics import compute_m7

    # currency shows up at rank 2, weather at rank 1
    engine = _mock_engine(
        {
            "currency": ["other_skill", "core_currency"],  # correct at rank 2 → pass2
            "weather": ["core_weather"],  # correct at rank 1 → pass1
        }
    )
    m7 = compute_m7(engine, _probes_kpn())
    assert m7.p1_rate == 0.5
    assert m7.p2_rate == 0.5
    assert m7.p3_rate == 0.0


def test_m7_pass3_when_not_in_top5():
    from benchmarks.og_bench.metrics import compute_m7

    # currency not found in results → pass3
    engine = _mock_engine({"currency": [], "weather": ["core_weather"]})
    m7 = compute_m7(engine, _probes_kpn())
    assert m7.p1_rate == 0.5
    assert m7.p3_rate == 0.5


def test_m7_empty_probes_returns_zero():
    from benchmarks.og_bench.metrics import compute_m7

    engine = _mock_engine({})
    m7 = compute_m7(engine, [])
    assert m7.n_queries == 0
    assert m7.p1_rate == 0.0


def test_m7_calls_reset_counters():
    from benchmarks.og_bench.metrics import compute_m7

    engine = _mock_engine({"currency": ["core_currency"]})
    compute_m7(engine, _probes_kpn())
    engine.reset_usage_counters.assert_called_once()


# ---------------------------------------------------------------------------
# M2 token cost model
# ---------------------------------------------------------------------------


def _mock_engine_m2(results: list[str]) -> Any:

    engine = MagicMock()
    engine.search.return_value = [{"name": n} for n in results]
    engine.peek.return_value = {n: {"dense": "short summary"} for n in results}
    engine.resolve_node.return_value = "full content " * 50  # ~50 tokens worth
    return engine


def test_m2_produces_positive_token_counts():
    from benchmarks.og_bench.metrics import compute_m2

    engine = _mock_engine_m2(["core_currency", "core_weather"])
    probes = [
        {"id": "k001", "type": "K", "query": "currency", "expected": ["core_currency"]},
    ]
    m2 = compute_m2(engine, probes)
    assert m2.n_queries == 1
    assert m2.avg_tokens_total > 0
    assert m2.estimated_usd_per_1k_queries > 0


def test_m2_empty_probes():
    from benchmarks.og_bench.metrics import compute_m2

    engine = _mock_engine_m2([])
    m2 = compute_m2(engine, [])
    assert m2.n_queries == 0
    assert m2.avg_tokens_total == 0.0


def test_m2_token_breakdown_sums_to_total():
    from benchmarks.og_bench.metrics import compute_m2

    engine = _mock_engine_m2(["core_currency"])
    probes = [
        {"id": "k001", "type": "K", "query": "currency", "expected": ["core_currency"]},
    ]
    m2 = compute_m2(engine, probes)
    expected_total = round(m2.avg_tokens_pass1 + m2.avg_tokens_pass2 + m2.avg_tokens_pass3, 1)
    assert abs(m2.avg_tokens_total - expected_total) < 1.0


# ---------------------------------------------------------------------------
# M4 latency model
# ---------------------------------------------------------------------------


def test_m4_produces_reasonable_latency():
    from benchmarks.og_bench.metrics import compute_m4

    engine = _mock_engine_m2(["core_currency"])
    probes = [
        {"id": "k001", "type": "K", "query": "currency", "expected": ["core_currency"]},
    ]
    m4 = compute_m4(engine, probes, rtt_per_pass_ms=800.0)
    assert m4.n_queries == 1
    assert m4.avg_engine_ms >= 0.0
    assert m4.rtt_estimate_ms == pytest.approx(2400.0, rel=0.01)
    assert m4.total_estimate_ms >= m4.rtt_estimate_ms


def test_m4_empty_probes():
    from benchmarks.og_bench.metrics import compute_m4

    engine = _mock_engine_m2([])
    m4 = compute_m4(engine, [])
    assert m4.n_queries == 0


def test_m4_rtt_model_is_3x_per_pass():
    from benchmarks.og_bench.metrics import compute_m4

    engine = _mock_engine_m2(["skill_a"])
    probes = [{"id": "k1", "type": "K", "query": "a", "expected": ["skill_a"]}]
    m4_500 = compute_m4(engine, probes, rtt_per_pass_ms=500.0)
    m4_800 = compute_m4(engine, probes, rtt_per_pass_ms=800.0)
    assert m4_500.rtt_estimate_ms == pytest.approx(1500.0, rel=0.01)
    assert m4_800.rtt_estimate_ms == pytest.approx(2400.0, rel=0.01)


import pytest  # noqa: E402 (needed for pytest.approx above)
