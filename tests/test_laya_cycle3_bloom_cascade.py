"""
Unit, Semantic Bloom Filter & 4-Tier Quantized Model Cascade Test Suite for
TASK-LAYA-SYSTEM1-PREROUTER (Cycle 3) (16 tests -> 364/364 cumulative).
"""
from __future__ import annotations

import pathlib
import pytest

from aasha.laya_router.bloom_cascade_router import (
    AdaptiveQuantizedModelCascade,
    BloomCascadeConfigError,
    SemanticBloomFilterRouter,
    compare_laya_cycle3_bloom_filter_and_quantized_cascade,
)


def test_lc3_01_bloom_filter_has_zero_false_negatives_on_indexed_corpus() -> None:
    bf = SemanticBloomFilterRouter(num_bits=16384, num_hashes=5)
    words = ["newton", "त्वरण", "ত্বরণ", "ਪ੍ਰਵੇਗ", "પ્રਵੇગ", "ତ୍ୱରଣ", "முடுக்கம்", "త్వరణం", "ವೇಗೋತ್ಕರ್ಷ", "ത്വരണം"]
    bf.add_corpus(words)
    for w in words:
        assert bf.contains_token(w) is True


def test_lc3_02_bloom_filter_rejects_unindexed_tokens_with_low_fp_rate() -> None:
    bf = SemanticBloomFilterRouter(num_bits=16384, num_hashes=5)
    bf.add_corpus(["force mass acceleration velocity momentum"])
    unseen_hits = sum(1 for i in range(200) if bf.contains_token(f"unseen_token_xyz_{i}"))
    assert unseen_hits == 0
    assert bf.theoretical_false_positive_rate() < 0.001


def test_lc3_03_bloom_filter_query_match_ratio_identifies_canonical_queries() -> None:
    cascade = AdaptiveQuantizedModelCascade()
    info = cascade.bloom_router.query_match_ratio("NCERT Class 9 Force and Newton Law")
    assert info["is_canonical_hit"] is True
    assert info["match_ratio"] >= 0.80
    assert info["lookup_latency_ms"] < 5.0


def test_lc3_04_bloom_filter_handles_empty_query_gracefully() -> None:
    bf = SemanticBloomFilterRouter()
    res = bf.query_match_ratio("   ")
    assert res["token_count"] == 0
    assert res["is_canonical_hit"] is False


def test_lc3_05_bloom_filter_rejects_invalid_bit_or_hash_config() -> None:
    with pytest.raises(BloomCascadeConfigError):
        SemanticBloomFilterRouter(num_bits=16, num_hashes=5)
    with pytest.raises(BloomCascadeConfigError):
        SemanticBloomFilterRouter(num_bits=1024, num_hashes=0)


def test_lc3_06_cascade_routes_short_canonical_query_to_tier0_int4_micro() -> None:
    cascade = AdaptiveQuantizedModelCascade()
    res = cascade.route_query("NCERT Class 9 Force and Newton Law")
    assert res["selected_tier_index"] == 0
    assert res["precision"] == "INT4"
    assert res["cost_usd"] == 0.0


def test_lc3_07_cascade_routes_moderate_explanation_query_to_tier1_int8() -> None:
    cascade = AdaptiveQuantizedModelCascade()
    res = cascade.route_query("How do we compare different classroom examples of inertia in daily life?")
    assert res["selected_tier_index"] == 1
    assert res["precision"] == "INT8"
    assert res["cost_usd"] == 0.0


def test_lc3_08_cascade_routes_latex_formula_problem_to_tier2_fp16() -> None:
    cascade = AdaptiveQuantizedModelCascade()
    res = cascade.route_query("Solve $\\frac{d}{t} + \\sqrt{2 a s}$ for displacement.")
    assert res["selected_tier_index"] == 2
    assert res["precision"] == "FP16"
    assert res["cost_usd"] == 0.0


def test_lc3_09_cascade_routes_multi_keyword_proof_to_tier3_cloud_when_under_cap() -> None:
    cascade = AdaptiveQuantizedModelCascade(current_daily_spend_usd=0.10)
    res = cascade.route_query("Prove the theorem and give full derivation of the AST invariants.")
    assert res["selected_tier_index"] == 3
    assert res["precision"] == "CLOUD_API"
    assert res["spend_cap_clamped"] is False
    assert res["cumulative_daily_spend_usd"] == round(0.10 + 0.00045, 6)


def test_lc3_10_cascade_clamps_tier3_to_local_fp16_when_daily_spend_cap_reached() -> None:
    cascade = AdaptiveQuantizedModelCascade(current_daily_spend_usd=0.9998)
    res = cascade.route_query("Prove the theorem and give full derivation of the AST invariants.")
    assert res["spend_cap_clamped"] is True
    assert res["selected_tier_index"] == 2
    assert res["precision"] == "FP16"
    assert res["cost_usd"] == 0.0
    assert res["cumulative_daily_spend_usd"] <= 1.00


def test_lc3_11_cascade_respects_low_vram_device_constraint_by_selecting_int8_or_int4() -> None:
    # Device with only 2048 MiB VRAM cannot load Tier 2 FP16 (3800 MiB)
    cascade = AdaptiveQuantizedModelCascade(current_daily_spend_usd=1.00, available_vram_mib=2048)
    res = cascade.route_query("Prove the theorem and give full derivation of the AST invariants.")
    assert res["selected_tier_index"] == 1
    assert res["precision"] == "INT8"
    assert res["vram_required_mib"] <= 2048


def test_lc3_12_cascade_rejects_vram_below_512_mib_or_empty_query() -> None:
    with pytest.raises(BloomCascadeConfigError):
        AdaptiveQuantizedModelCascade(available_vram_mib=256)
    cascade = AdaptiveQuantizedModelCascade()
    with pytest.raises(BloomCascadeConfigError):
        cascade.route_query("   ")


def test_lc3_13_bloom_filter_supports_all_9_indic_unicode_scripts_in_default_seed() -> None:
    cascade = AdaptiveQuantizedModelCascade()
    for indic_word in ["त्वरण", "ত্বরণ", "ਪ੍ਰਵੇਗ", "પ્રਵੇગ", "ତ୍ୱରଣ", "முடுக்கம்", "త్వరణం", "ವೇಗೋತ್ಕರ್ಷ", "ത്വരണം"]:
        assert cascade.bloom_router.contains_token(indic_word) is True


def test_lc3_14_bloom_filter_is_case_insensitive() -> None:
    bf = SemanticBloomFilterRouter()
    bf.add_token("AVR-P305")
    assert bf.contains_token("avr-p305") is True
    assert bf.contains_token("AVR-P305") is True


def test_lc3_15_js_laya_bloom_cascade_module_present_and_valid() -> None:
    js_txt = pathlib.Path("/tmp/aasha_stage_pack/scripts/aasha_laya_bloom_cascade.js").read_text(encoding="utf-8")
    assert "SemanticBloomFilterRouterJS" in js_txt
    assert "AdaptiveQuantizedModelCascadeJS" in js_txt


def test_lc3_16_compare_laya_cycle3_bloom_filter_and_quantized_cascade_benchmark() -> None:
    bench = compare_laya_cycle3_bloom_filter_and_quantized_cascade()
    assert bench["winner"] == "method-b-semantic-bloom-filter-and-4tier-quantized-cascade"
    mb = bench["method_b_bloom_quantized_cascade"]
    assert mb["local_quantized_offload_pct"] == 95.0
    assert mb["latency_reduction_pct"] >= 85.0
    assert mb["cost_reduction_pct"] == 95.0
    assert mb["bloom_false_negative_rate_pct"] == 0.0
