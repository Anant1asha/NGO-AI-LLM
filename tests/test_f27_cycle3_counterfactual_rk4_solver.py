"""
Unit & Unified 15-Loop Consolidation Test Suite for TASK-F27-AASHA-SIM-BENCHMARK (Cycle 3)
and Master 15-Loop Consolidation (16 tests -> 380/380 cumulative).
"""
from __future__ import annotations

import pytest

from aasha.f27_sim.counterfactual_rk4_solver import (
    CounterfactualHintSynthesizer,
    PhysicsSolverConfigError,
    TypedArrayPhysicsSolver,
    compare_f27_cycle3_counterfactual_hints_and_typedarray_solver,
)
from aasha.laya_router.bloom_cascade_router import compare_laya_cycle3_bloom_filter_and_quantized_cascade
from aasha.laya_router.laya_system1_prerouter import compare_laya_routing_efficiency
from aasha.offline_synthesizer.phoneme_bundle_optimizer import compare_wb_cycle3_phoneme_sync_and_bundle_optimizer
from aasha.orchestrator.consensus_work_stealing import compare_fork_join_cycle3_consensus_and_work_stealing
from aasha.v6_compiler.incremental_ir_recompiler import compare_v6_cycle3_incremental_recompiler_and_mastery_matrix
from aasha.f27_sim.f27_sim_benchmark import compare_f27_cycle2_sim_stress_and_ast_validation


def test_f27c3_01_diagnose_sign_inversion_error_without_spoiler() -> None:
    res = CounterfactualHintSynthesizer.diagnose_and_synthesize_hint(-25.0, 25.0, "F", "N")
    assert res["error_archetype"] == "SIGN_INVERSION"
    assert res["spoiler_free"] is True
    assert "25" not in res["hint_en"]


def test_f27c3_02_diagnose_unit_scale_mismatch_1000x_without_spoiler() -> None:
    res = CounterfactualHintSynthesizer.diagnose_and_synthesize_hint(45000.0, 45.0, "m", "kg")
    assert res["error_archetype"] == "UNIT_SCALE_MISMATCH"
    assert res["spoiler_free"] is True
    assert " 45 " not in res["hint_en"]


def test_f27c3_03_diagnose_operator_inversion_multiply_vs_divide() -> None:
    res = CounterfactualHintSynthesizer.diagnose_and_synthesize_hint(
        80.0, 5.0, "a", "m/s^2", operand_a=20.0, operand_b=4.0
    )
    assert res["error_archetype"] == "OPERATOR_INVERSION_MUL_VS_DIV"
    assert res["spoiler_free"] is True


def test_f27c3_04_diagnose_magnitude_overshoot_and_undershoot() -> None:
    over = CounterfactualHintSynthesizer.diagnose_and_synthesize_hint(90.0, 50.0, "F", "N")
    under = CounterfactualHintSynthesizer.diagnose_and_synthesize_hint(15.0, 50.0, "F", "N")
    assert over["error_archetype"] == "MAGNITUDE_OVERSHOOT"
    assert under["error_archetype"] == "MAGNITUDE_UNDERSHOOT"
    assert over["spoiler_free"] is True and under["spoiler_free"] is True


def test_f27c3_05_counterfactual_hint_contains_both_english_and_hindi_guidance() -> None:
    res = CounterfactualHintSynthesizer.diagnose_and_synthesize_hint(-12.0, 12.0, "v", "m/s")
    assert "Counterfactual check:" in res["hint_en"]
    assert "प्रति-तथ्यात्मक जाँच:" in res["hint_hi"]


def test_f27c3_06_counterfactual_hint_rejects_nan_or_infinite_inputs() -> None:
    with pytest.raises(PhysicsSolverConfigError):
        CounterfactualHintSynthesizer.diagnose_and_synthesize_hint(float("nan"), 10.0)


def test_f27c3_07_typedarray_verlet_conserves_energy_on_undamped_oscillator() -> None:
    res = TypedArrayPhysicsSolver.integrate_harmonic_verlet(
        mass_kg=2.0, spring_k=20.0, damping_c=0.0, x0=1.5, v0=0.0, dt=0.001, steps=1000
    )
    assert res["energy_conserved"] is True
    assert res["relative_energy_drift"] < 1e-5
    assert res["within_10ms_budget"] is True


def test_f27c3_08_typedarray_verlet_dissipates_energy_when_damping_positive() -> None:
    res = TypedArrayPhysicsSolver.integrate_harmonic_verlet(
        mass_kg=1.0, spring_k=10.0, damping_c=0.8, x0=1.0, v0=0.0, dt=0.002, steps=1000
    )
    assert res["final_energy_j"] < res["initial_energy_j"]
    assert res["energy_conserved"] is True


def test_f27c3_09_typedarray_verlet_rejects_invalid_mass_or_dt() -> None:
    with pytest.raises(PhysicsSolverConfigError):
        TypedArrayPhysicsSolver.integrate_harmonic_verlet(mass_kg=0.0)
    with pytest.raises(PhysicsSolverConfigError):
        TypedArrayPhysicsSolver.integrate_harmonic_verlet(dt=-0.01)


def test_f27c3_10_compare_f27_cycle3_benchmark_verifies_verlet_beats_euler() -> None:
    bench = compare_f27_cycle3_counterfactual_hints_and_typedarray_solver()
    assert bench["winner"] == "method-b-counterfactual-hint-synthesizer-and-typedarray-verlet-solver"
    assert bench["method_a_euler_dict_loop"]["energy_conserved"] is False
    assert bench["method_b_typedarray_verlet_and_socratic_hints"]["energy_conserved"] is True
    assert bench["method_b_typedarray_verlet_and_socratic_hints"]["counterfactual_archetypes_diagnosed"] == 5
    assert bench["method_b_typedarray_verlet_and_socratic_hints"]["spoiler_free_rate_pct"] == 100.0


def test_f27c3_11_unified_track1_wb_cycle3_integration_check() -> None:
    wb3 = compare_wb_cycle3_phoneme_sync_and_bundle_optimizer()
    assert wb3["method_b_phoneme_cas_optimized"]["within_20mib_ceiling"] is True
    assert wb3["method_b_phoneme_cas_optimized"]["indic_scripts_synced"] == 9


def test_f27c3_12_unified_track2_fork_join_cycle3_integration_check() -> None:
    fj3 = compare_fork_join_cycle3_consensus_and_work_stealing()
    assert fj3["method_b_consensus_work_stealing"]["deadlock_free_verified"] is True
    assert fj3["method_b_consensus_work_stealing"]["byzantine_agents_quarantined"] == 1


def test_f27c3_13_unified_track3_v6_compiler_cycle3_integration_check() -> None:
    v6c3 = compare_v6_cycle3_incremental_recompiler_and_mastery_matrix()
    assert v6c3["method_b_incremental_ast_recompiler"]["byte_identical_to_cold_build"] is True
    assert v6c3["method_b_incremental_ast_recompiler"]["cache_hit_ratio_pct"] == 90.0


def test_f27c3_14_unified_track4_laya_router_cycles_integration_check() -> None:
    lc1 = compare_laya_routing_efficiency()
    lc3 = compare_laya_cycle3_bloom_filter_and_quantized_cascade()
    assert lc1["method_b_laya_system1_prerouter"]["spend_cap_breaches"] == 0
    assert lc3["method_b_bloom_quantized_cascade"]["local_quantized_offload_pct"] == 95.0


def test_f27c3_15_unified_track5_f27_sim_cycles_2_and_3_integration_check() -> None:
    f27c2 = compare_f27_cycle2_sim_stress_and_ast_validation()
    f27c3 = compare_f27_cycle3_counterfactual_hints_and_typedarray_solver()
    assert f27c2["method_b_ast_validated_sim"]["finite_states_verified"] == 500
    assert f27c3["method_b_typedarray_verlet_and_socratic_hints"]["energy_conserved"] is True


def test_f27c3_16_all_5_tracks_across_cycles_1_to_3_pass_simultaneously() -> None:
    # Master end-to-end assertion across all 5 tracks
    assert compare_wb_cycle3_phoneme_sync_and_bundle_optimizer()["method_b_phoneme_cas_optimized"]["max_phoneme_timing_drift_ms"] == 0.0
    assert compare_fork_join_cycle3_consensus_and_work_stealing()["method_b_consensus_work_stealing"]["makespan_reduction_pct"] >= 65.0
    assert compare_v6_cycle3_incremental_recompiler_and_mastery_matrix()["method_b_incremental_ast_recompiler"]["g10_bridge_chain_length"] == 4
    assert compare_laya_cycle3_bloom_filter_and_quantized_cascade()["method_b_bloom_quantized_cascade"]["bloom_false_negative_rate_pct"] == 0.0
    assert compare_f27_cycle3_counterfactual_hints_and_typedarray_solver()["method_b_typedarray_verlet_and_socratic_hints"]["spoiler_free_rate_pct"] == 100.0
