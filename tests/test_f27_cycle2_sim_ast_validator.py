"""
Unit & Adversarial Simulation Stress-Test Suite for TASK-F27-AASHA-SIM-BENCHMARK (Cycle 2):
BilingualFormulaASTValidator & MultiChapterSimStressTester (16 tests -> 300/300 cumulative).
"""
from __future__ import annotations

import math
import pathlib
import pytest

from aasha.f27_sim.f27_sim_benchmark import (
    BilingualFormulaASTValidator,
    FormulaASTValidationError,
    LTruthAntiSpoilerVerifier,
    MultiChapterSimStressTester,
    compare_f27_cycle2_sim_stress_and_ast_validation,
    compare_f27_sim_anti_spoiler_vs_naive,
)


def test_f27c2_01_valid_latex_fraction_and_sqrt_formula_passes() -> None:
    res = BilingualFormulaASTValidator.validate_formula_and_bindings(
        "$v = \\frac{d}{t} + \\sqrt{2 \\cdot a \\cdot s}$"
    )
    assert res["valid"] is True
    assert len(res["latex_commands_verified"]) == 2
    assert set(res["variables"]) == {"v", "d", "t", "a", "s"}


def test_f27c2_02_unbalanced_dollar_delimiter_raises_error() -> None:
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$F = m \\cdot a")


def test_f27c2_03_unbalanced_curly_braces_in_frac_raises_error() -> None:
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$v = \\frac{d}{t$")


def test_f27c2_04_empty_numerator_or_denominator_in_frac_raises_error() -> None:
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$v = \\frac{}{t}$")


def test_f27c2_05_static_division_by_zero_in_frac_or_slash_raises_error() -> None:
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$x = \\frac{5}{0}$")
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$x = a / 0$")


def test_f27c2_06_invalid_consecutive_or_trailing_operators_raise_error() -> None:
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$F = m +* a$")
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$F = m * a +$")


def test_f27c2_07_si_dimensional_homogeneity_passes_valid_physics_equations() -> None:
    r1 = BilingualFormulaASTValidator.validate_formula_and_bindings("$F = m \\cdot a$")
    r2 = BilingualFormulaASTValidator.validate_formula_and_bindings("$v = u + a \\cdot t$")
    r3 = BilingualFormulaASTValidator.validate_formula_and_bindings("$V = I \\cdot R$")
    assert r1["dimensional_check"]["dimensionally_homogeneous"] is True
    assert r2["dimensional_check"]["dimensionally_homogeneous"] is True
    assert r3["dimensional_check"]["dimensionally_homogeneous"] is True


def test_f27c2_08_si_dimensional_mismatch_raises_error() -> None:
    # Force (M*L/T^2) cannot equal Current * Resistance (Voltage)
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings("$F = I \\cdot R$")


def test_f27c2_09_bilingual_glossary_binding_verifies_english_and_indic_scripts() -> None:
    glossary = {
        "F": {"en": "Force", "indic": "बल (Devanagari)"},
        "m": {"en": "Mass", "indic": "ভর (Bengali)"},
        "a": {"en": "Acceleration", "indic": "முடுக்கம் (Tamil)"},
    }
    res = BilingualFormulaASTValidator.validate_formula_and_bindings(
        "$F = m \\cdot a$",
        bilingual_glossary=glossary,
    )
    assert res["bilingual_bindings_complete"] is True
    assert set(res["indic_scripts_detected"]) == {"bn", "hi", "ta"}


def test_f27c2_10_missing_bilingual_glossary_binding_raises_error() -> None:
    incomplete_glossary = {
        "F": {"en": "Force", "indic": "बल"},
        "m": {"en": "Mass", "indic": "द्रव्यमान"},
        # 'a' is missing!
    }
    with pytest.raises(FormulaASTValidationError):
        BilingualFormulaASTValidator.validate_formula_and_bindings(
            "$F = m \\cdot a$",
            bilingual_glossary=incomplete_glossary,
        )


def test_f27c2_11_safe_divide_clamps_zero_nan_and_inf_denominators() -> None:
    val_zero, guarded_zero = MultiChapterSimStressTester.safe_divide(10.0, 0.0)
    val_nan, guarded_nan = MultiChapterSimStressTester.safe_divide(10.0, float("nan"))
    val_inf, guarded_inf = MultiChapterSimStressTester.safe_divide(10.0, float("inf"))
    assert guarded_zero is True and math.isfinite(val_zero)
    assert guarded_nan is True and math.isfinite(val_nan)
    assert guarded_inf is True and math.isfinite(val_inf)


def test_f27c2_12_full_500_state_multi_chapter_sweep_produces_zero_nan_or_inf() -> None:
    sweep = MultiChapterSimStressTester.run_full_500_state_sweep()
    assert sweep["archetypes_tested"] == 20
    assert sweep["vectors_per_archetype"] == 25
    assert sweep["total_states_executed"] == 500
    assert sweep["finite_states_verified"] == 500
    assert sweep["nan_or_inf_failures"] == 0
    assert sweep["division_by_zero_traps_clamped"] == 80  # 4 zero-c vectors (i=0,10,12,24) x 20 archetypes


def test_f27c2_13_full_500_state_sweep_meets_60fps_frame_budget_and_zero_spoilers() -> None:
    sweep = MultiChapterSimStressTester.run_full_500_state_sweep()
    assert sweep["p99_frame_latency_ms"] <= 16.67
    assert sweep["within_60fps_budget_rate_pct"] == 100.0
    assert sweep["spoiler_leaks_detected"] == 0


def test_f27c2_14_ltruth_anti_spoiler_blocks_exact_target_answer_and_allows_decimals() -> None:
    leak_res = LTruthAntiSpoilerVerifier.verify_payload("Hint: The value is 42.", target_answer="42")
    clean_res = LTruthAntiSpoilerVerifier.verify_payload("Step 1: Use 42.5 N of force.", target_answer="42")
    assert leak_res["spoiler_free"] is False
    assert clean_res["spoiler_free"] is True


def test_f27c2_15_js_gamified_assessment_adapter_contains_ast_and_stress_classes() -> None:
    js_txt = pathlib.Path("/tmp/aasha_stage_pack/scripts/aasha_gamified_assessment_adapter.js").read_text(encoding="utf-8")
    assert "BilingualFormulaASTValidatorJS" in js_txt
    assert "MultiChapterSimStressTesterJS" in js_txt


def test_f27c2_16_compare_f27_cycle1_and_cycle2_benchmarks_pass() -> None:
    b1 = compare_f27_sim_anti_spoiler_vs_naive()
    b2 = compare_f27_cycle2_sim_stress_and_ast_validation()
    assert b1["method_b_f27_verified_sim"]["spoiler_leaks"] == 0
    assert b2["winner"] == "method-b-bilingual-ast-validator-and-500-state-stress-tester"
    assert b2["method_b_ast_validated_sim"]["finite_states_verified"] == 500
    assert b2["method_b_ast_validated_sim"]["nan_or_inf_crashes"] == 0
