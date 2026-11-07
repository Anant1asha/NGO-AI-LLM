"""
Unit, 9-Script Phoneme Sync & Sub-20MiB Bundle Optimization Test Suite for
TASK-WB-OFFLINE-CHAPTER-COMPILATION (Cycle 3) (16 tests -> 316/316 cumulative).
"""
from __future__ import annotations

import pathlib
import pytest

from aasha.offline_synthesizer.phoneme_bundle_optimizer import (
    BundleCeilingExceededError,
    IndicPhonemeSyncCompiler,
    OFFLINE_BUNDLE_CEILING_BYTES,
    PhonemeSyncError,
    Sub20MiBBundleOptimizer,
    compare_wb_cycle3_phoneme_sync_and_bundle_optimizer,
)


def test_wbc3_01_detect_script_identifies_all_9_indic_scripts_and_english() -> None:
    samples = {
        "en": "Newton's Second Law",
        "hi": "बल और त्वरण",
        "bn": "বল এবং ত্বরণ",
        "pa": "ਬਲ ਅਤੇ ਪ੍ਰਵੇਗ",
        "gu": "બળ અને પ્રવેગ",
        "or": "ବଳ ଏବଂ ତ୍ୱରଣ",
        "ta": "விசை மற்றும் முடுக்கம்",
        "te": "బలం మరియు త్వరణం",
        "kn": "ಬಲ ಮತ್ತು ವೇಗೋತ್ಕರ್ಷ",
        "ml": "ബലവും ത്വരണവും",
    }
    for expected_lang, text in samples.items():
        assert IndicPhonemeSyncCompiler.detect_script(text) == expected_lang


def test_wbc3_02_verbalize_latex_math_expands_fractions_roots_and_operators_en() -> None:
    text = "Verify $F = m \\cdot a$ and $v = \\frac{d}{t} + \\sqrt{x}$."
    verbalized, count = IndicPhonemeSyncCompiler.verbalize_latex_math(text, prefer_hindi_math=False)
    assert count == 2
    assert "equals" in verbalized
    assert "times" in verbalized
    assert "divided by" in verbalized
    assert "square root of" in verbalized


def test_wbc3_03_verbalize_latex_math_expands_hindi_spoken_operators() -> None:
    text = "सूत्र $F = m \\cdot a$ और $\\frac{d}{t}$ देखें।"
    verbalized, count = IndicPhonemeSyncCompiler.verbalize_latex_math(text, prefer_hindi_math=True)
    assert count == 2
    assert "बराबर" in verbalized
    assert "गुणा" in verbalized
    assert "बटा" in verbalized


def test_wbc3_04_compile_sync_track_achieves_zero_drift_and_contiguous_cues() -> None:
    track = IndicPhonemeSyncCompiler.compile_sync_track(
        "The net force $F = m \\cdot a$ accelerates the mass.",
        words_per_minute=140,
        target_total_duration_ms=4500,
    )
    assert track["total_duration_ms"] == 4500
    assert track["timing_drift_ms"] == 0.0
    assert track["contiguous_intervals_verified"] is True
    assert track["cues"][0]["start_ms"] == 0
    assert track["cues"][-1]["end_ms"] == 4500


def test_wbc3_05_compile_sync_track_generates_valid_webvtt_with_visemes() -> None:
    track = IndicPhonemeSyncCompiler.compile_sync_track("बल और द्रव्यमान का नियम", target_total_duration_ms=2000)
    assert track["webvtt"].startswith("WEBVTT\n\n00:00:00.000 -->")
    assert "<v " in track["webvtt"]


def test_wbc3_06_compile_sync_track_rejects_empty_text_or_invalid_wpm() -> None:
    with pytest.raises(PhonemeSyncError):
        IndicPhonemeSyncCompiler.compile_sync_track("   ")
    with pytest.raises(PhonemeSyncError):
        IndicPhonemeSyncCompiler.compile_sync_track("Valid text", words_per_minute=0)


def test_wbc3_07_count_akshara_syllables_handles_indic_conjuncts_and_vowels() -> None:
    assert IndicPhonemeSyncCompiler.count_akshara_syllables("त्वरण") >= 2
    assert IndicPhonemeSyncCompiler.count_akshara_syllables("acceleration") >= 4


def test_wbc3_08_infer_viseme_maps_labial_round_spread_and_open_tokens() -> None:
    assert IndicPhonemeSyncCompiler.infer_viseme("mass") == "LABIAL_MM"
    assert IndicPhonemeSyncCompiler.infer_viseme("उर्जा") == "ROUND_OO"
    assert IndicPhonemeSyncCompiler.infer_viseme("इकाई") == "SPREAD_EE"


def test_wbc3_09_minify_asset_compresses_svg_and_json_losslessly() -> None:
    raw_svg = b"<!-- comment -->  <svg>   <g>   <circle r='5'/>   </g>  </svg>  "
    min_svg = Sub20MiBBundleOptimizer.minify_asset("svg", raw_svg)
    assert b"<!--" not in min_svg
    assert b"><" in min_svg
    assert len(min_svg) < len(raw_svg)

    raw_json = b'{\n  "b": 2,\n  "a": [1, 2, 3]\n}'
    min_json = Sub20MiBBundleOptimizer.minify_asset("json", raw_json)
    assert min_json == b'{"a":[1,2,3],"b":2}'


def test_wbc3_10_optimize_bundle_deduplicates_identical_assets_via_sha256_cas() -> None:
    shared_blob = b"<svg><rect width='100' height='100'/></svg>" * 500
    assets = [
        {"name": f"ch{i:02d}/shared.svg", "type": "svg", "content": shared_blob}
        for i in range(10)
    ]
    res = Sub20MiBBundleOptimizer.optimize_bundle(assets)
    assert res["unique_cas_blobs"] == 1
    assert res["duplicate_assets_eliminated"] == 9
    assert res["total_reduction_pct"] > 85.0


def test_wbc3_11_optimize_bundle_compresses_25mib_pack_under_20mib_ceiling() -> None:
    font_blob = b"FONT_DATA_BLOCK_" * 65536  # ~1 MiB
    assets = [
        {"name": f"ch{i:02d}/font.ttf", "type": "font", "content": font_blob}
        for i in range(25)  # 25 MiB raw > 20 MiB ceiling
    ]
    res = Sub20MiBBundleOptimizer.optimize_bundle(assets)
    assert res["raw_total_bytes"] > OFFLINE_BUNDLE_CEILING_BYTES
    assert res["within_20mib_ceiling"] is True
    assert res["optimized_total_bytes"] < OFFLINE_BUNDLE_CEILING_BYTES


def test_wbc3_12_optimize_bundle_triggers_adaptive_quantization_when_needed() -> None:
    # Create unique large buffers totaling 26 MiB so CAS dedup alone doesn't shrink below 20 MiB
    assets = [
        {"name": f"unique_{i}.bin", "type": "binary", "content": bytes([(i + j) % 251 for j in range(2_600_000)])}
        for i in range(10)
    ]
    res = Sub20MiBBundleOptimizer.optimize_bundle(assets)
    assert res["quantization_applied"] is True
    assert res["within_20mib_ceiling"] is True


def test_wbc3_13_optimize_bundle_raises_error_when_uncompressible_above_ceiling() -> None:
    # Enforce a tiny custom ceiling of 100 bytes on a 10 KB asset
    assets = [{"name": "huge.bin", "type": "binary", "content": b"X" * 10000}]
    with pytest.raises(BundleCeilingExceededError):
        Sub20MiBBundleOptimizer.optimize_bundle(assets, ceiling_bytes=100)


def test_wbc3_14_manifest_entries_contain_valid_sha256_cas_uris() -> None:
    assets = [{"name": "ch01/data.json", "type": "json", "content": b'{"ok": true}'}]
    res = Sub20MiBBundleOptimizer.optimize_bundle(assets)
    uri = res["manifest"][0]["cas_uri"]
    assert uri.startswith("cas://sha256/")
    assert len(uri.split("/")[-1]) == 64


def test_wbc3_15_js_phoneme_bundle_optimizer_module_present_and_valid() -> None:
    js_txt = pathlib.Path("scripts/aasha_phoneme_bundle_optimizer.js").read_text(encoding="utf-8")
    assert "IndicPhonemeSyncCompilerJS" in js_txt
    assert "Sub20MiBBundleOptimizerJS" in js_txt


def test_wbc3_16_compare_wb_cycle3_phoneme_sync_and_bundle_optimizer_benchmark() -> None:
    bench = compare_wb_cycle3_phoneme_sync_and_bundle_optimizer()
    assert bench["winner"] == "method-b-indic-phoneme-sync-and-sub20mib-cas-optimizer"
    ma = bench["method_a_unoptimized_pack"]
    mb = bench["method_b_phoneme_cas_optimized"]
    assert ma["within_20mib_ceiling"] is False
    assert mb["within_20mib_ceiling"] is True
    assert mb["indic_scripts_synced"] == 9
    assert mb["max_phoneme_timing_drift_ms"] == 0.0
