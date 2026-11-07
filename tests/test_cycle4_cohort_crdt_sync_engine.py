"""
Unit, Algebraic Semilattice Laws (Commutativity, Idempotence, Associativity) & Facilitator
Diagnostic Pod Test Suite for TASK-CENTRE-COHORT-OFFLINE-SYNC-ENGINE (Cycle 4)
(16 tests -> 412/412 cumulative).
"""
from __future__ import annotations

import pathlib
import pytest

from aasha.orchestrator.cohort_crdt_sync_engine import (
    CohortCRDTProgressMerger,
    CohortCRDTSyncError,
    FacilitatorDiagnosticAggregator,
    StudentConceptCRDTState,
    compare_cycle4_cohort_crdt_sync_and_facilitator_diagnostics,
)


def _sample_states() -> tuple[StudentConceptCRDTState, StudentConceptCRDTState, StudentConceptCRDTState]:
    s1 = StudentConceptCRDTState("stu_1", "G9-M1", 9, "AVR-P301", 0.45, {"tab1": 2, "tab2": 1}, 100, {"SIGN_INVERSION"})
    s2 = StudentConceptCRDTState("stu_1", "G9-M1", 9, "AVR-P301", 0.78, {"tab1": 1, "tab2": 4}, 200, {"UNIT_SCALE_MISMATCH"})
    s3 = StudentConceptCRDTState("stu_1", "G9-M1", 9, "AVR-P301", 0.62, {"tab3": 3}, 150, {"OPERATOR_INVERSION_MUL_VS_DIV"})
    return s1, s2, s3


def test_crdt_01_merge_is_strictly_commutative() -> None:
    s1, s2, _ = _sample_states()
    ab = CohortCRDTProgressMerger.merge_two_states(s1, s2).to_dict()
    ba = CohortCRDTProgressMerger.merge_two_states(s2, s1).to_dict()
    assert ab == ba


def test_crdt_02_merge_is_strictly_idempotent() -> None:
    s1, _, _ = _sample_states()
    aa = CohortCRDTProgressMerger.merge_two_states(s1, s1).to_dict()
    assert aa == s1.to_dict()


def test_crdt_03_merge_is_strictly_associative() -> None:
    s1, s2, s3 = _sample_states()
    left = CohortCRDTProgressMerger.merge_two_states(
        CohortCRDTProgressMerger.merge_two_states(s1, s2), s3
    ).to_dict()
    right = CohortCRDTProgressMerger.merge_two_states(
        s1, CohortCRDTProgressMerger.merge_two_states(s2, s3)
    ).to_dict()
    assert left == right


def test_crdt_04_gcounter_accumulates_max_per_replica_without_double_counting() -> None:
    s1, s2, s3 = _sample_states()
    merged = CohortCRDTProgressMerger.merge_two_states(
        CohortCRDTProgressMerger.merge_two_states(s1, s2), s3
    )
    # tab1: max(2,1)=2, tab2: max(1,4)=4, tab3: 3 -> total = 9
    assert merged.replica_attempts == {"tab1": 2, "tab2": 4, "tab3": 3}
    assert merged.total_attempts == 9


def test_crdt_05_mastery_lattice_prevents_stale_packet_regression() -> None:
    high_mastery = StudentConceptCRDTState("stu_1", "G9-M1", 9, "AVR-P301", 0.88, {"tab1": 3}, 1000)
    stale_low = StudentConceptCRDTState("stu_1", "G9-M1", 9, "AVR-P301", 0.35, {"tab2": 1}, 2500)
    merged = CohortCRDTProgressMerger.merge_two_states(high_mastery, stale_low)
    assert merged.mastery_score == 0.88
    assert merged.hlc_timestamp_ms == 2500


def test_crdt_06_misconception_tags_form_monotonic_grow_only_set() -> None:
    s1, s2, s3 = _sample_states()
    merged = CohortCRDTProgressMerger.merge_two_states(
        CohortCRDTProgressMerger.merge_two_states(s1, s2), s3
    )
    assert merged.misconception_tags == {
        "SIGN_INVERSION",
        "UNIT_SCALE_MISMATCH",
        "OPERATOR_INVERSION_MUL_VS_DIV",
    }


def test_crdt_07_merge_rejects_mismatched_student_or_concept_keys() -> None:
    s1 = StudentConceptCRDTState("stu_1", "G9-M1", 9, "AVR-P301", 0.5)
    s2 = StudentConceptCRDTState("stu_2", "G9-M1", 9, "AVR-P301", 0.6)
    with pytest.raises(CohortCRDTSyncError):
        CohortCRDTProgressMerger.merge_two_states(s1, s2)


def test_crdt_08_merge_rejects_empty_identifiers_or_invalid_grade() -> None:
    bad_id = StudentConceptCRDTState("", "G9-M1", 9, "AVR-P301", 0.5)
    bad_grade = StudentConceptCRDTState("stu_1", "G9-M1", 99, "AVR-P301", 0.5)
    with pytest.raises(CohortCRDTSyncError):
        CohortCRDTProgressMerger.validate_state(bad_id)
    with pytest.raises(CohortCRDTSyncError):
        CohortCRDTProgressMerger.validate_state(bad_grade)


def test_crdt_09_merge_replica_batches_converges_to_identical_sha256_regardless_of_order() -> None:
    s1, s2, s3 = _sample_states()
    r_123 = CohortCRDTProgressMerger.merge_replica_batches([[s1], [s2], [s3]])
    r_312 = CohortCRDTProgressMerger.merge_replica_batches([[s3], [s1], [s2]])
    r_231 = CohortCRDTProgressMerger.merge_replica_batches([[s2], [s3], [s1]])
    assert r_123["convergence_sha256"] == r_312["convergence_sha256"] == r_231["convergence_sha256"]


def test_crdt_10_merge_replica_batches_clamps_out_of_bounds_mastery_scores() -> None:
    s_over = StudentConceptCRDTState("stu_1", "G9-M1", 9, "AVR-P301", 1.75, {"tab1": 1}, 100)
    res = CohortCRDTProgressMerger.merge_replica_batches([[s_over]])
    assert res["merged_states"][0]["mastery_score"] == 1.0


def test_crdt_11_merge_replica_batches_rejects_empty_batch_sequence() -> None:
    with pytest.raises(CohortCRDTSyncError):
        CohortCRDTProgressMerger.merge_replica_batches([])


def test_crdt_12_facilitator_aggregator_schedules_pods_sorted_by_grade_and_need() -> None:
    states = [
        StudentConceptCRDTState("s1", "G9-FORCE", 9, "AVR-P302", 0.45, {"t": 2}, 100, {"SIGN_INVERSION"}).to_dict(),
        StudentConceptCRDTState("s2", "G9-FORCE", 9, "AVR-P302", 0.50, {"t": 3}, 100, {"SIGN_INVERSION"}).to_dict(),
        StudentConceptCRDTState("s3", "G7-RATIO", 7, "AVR-P301", 0.40, {"t": 2}, 100, {"UNIT_SCALE_MISMATCH"}).to_dict(),
        StudentConceptCRDTState("s4", "G7-RATIO", 7, "AVR-P301", 0.42, {"t": 2}, 100, {"UNIT_SCALE_MISMATCH"}).to_dict(),
    ]
    plan = FacilitatorDiagnosticAggregator.generate_cohort_intervention_plan(states)
    assert plan["intervention_pods_scheduled"] == 2
    assert plan["pods"][0]["grade"] == 7
    assert plan["pods"][0]["dominant_misconception"] == "UNIT_SCALE_MISMATCH"
    assert plan["pods"][1]["grade"] == 9
    assert plan["pods"][1]["dominant_misconception"] == "SIGN_INVERSION"


def test_crdt_13_facilitator_aggregator_skips_pods_when_cohort_mastered() -> None:
    states = [
        StudentConceptCRDTState(f"s{i}", "G9-FORCE", 9, "AVR-P302", 0.90, {"t": 1}, 100).to_dict()
        for i in range(5)
    ]
    plan = FacilitatorDiagnosticAggregator.generate_cohort_intervention_plan(states)
    assert plan["intervention_pods_scheduled"] == 0
    assert plan["pods"] == []


def test_crdt_14_facilitator_aggregator_handles_empty_state_list() -> None:
    plan = FacilitatorDiagnosticAggregator.generate_cohort_intervention_plan([])
    assert plan["total_students"] == 0
    assert plan["intervention_pods_scheduled"] == 0


def test_crdt_15_js_cohort_crdt_sync_engine_module_present_and_valid() -> None:
    js_txt = pathlib.Path("/tmp/aasha_stage_pack/scripts/aasha_cohort_crdt_sync_engine.js").read_text(encoding="utf-8")
    assert "CohortCRDTProgressMergerJS" in js_txt
    assert "FacilitatorDiagnosticAggregatorJS" in js_txt


def test_crdt_16_compare_cycle4_cohort_crdt_sync_and_facilitator_diagnostics_benchmark() -> None:
    bench = compare_cycle4_cohort_crdt_sync_and_facilitator_diagnostics()
    assert bench["winner"] == "method-b-commutative-crdt-cohort-merger-and-facilitator-pod-planner"
    mb = bench["method_b_crdt_semilattice_merger"]
    assert mb["stu01_reported_mastery"] == 0.82
    assert mb["stu01_attempts_preserved"] == 6
    assert mb["offline_attempts_lost"] == 0
    assert mb["order_independent_convergence"] is True
    assert mb["intervention_pods_scheduled"] == 2
