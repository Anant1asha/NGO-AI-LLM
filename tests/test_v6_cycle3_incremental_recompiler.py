"""
Unit, Incremental AST Subtree Invalidator, Byte-Identical Emission & Cross-Grade Mastery
Transfer Test Suite for TASK-V6-CANONICAL-IR-COMPILER (Cycle 3) (16 tests -> 348/348 cumulative).
"""
from __future__ import annotations

import copy
import pathlib
import pytest

from aasha.v6_compiler.incremental_ir_recompiler import (
    CrossGradeMasteryTransferMatrix,
    IncrementalASTDifferentialRecompiler,
    IncrementalIRCompilerError,
    V6ConceptASTNode,
    compare_v6_cycle3_incremental_recompiler_and_mastery_matrix,
)


def _sample_chain() -> list[V6ConceptASTNode]:
    return [
        V6ConceptASTNode("G6-M1", 6, "Ratios", "अनुपात", "$a : b$", "AVR-P301", []),
        V6ConceptASTNode("G7-M1", 7, "Proportions", "समानुपात", "$\\frac{a}{b} = \\frac{c}{d}$", "AVR-P302", ["G6-M1"]),
        V6ConceptASTNode("G8-M1", 8, "Linear Equations", "रैखिक समीकरण", "$a x + b = 0$", "AVR-P303", ["G7-M1"]),
        V6ConceptASTNode("G9-M1", 9, "Two-Variable Lines", "दो चर वाले समीकरण", "$y = m x + c$", "AVR-P304", ["G8-M1"]),
        V6ConceptASTNode("G10-M1", 10, "Quadratic Systems", "द्विघात समीकरण", "$a x^2 + b x + c = 0$", "AVR-P305", ["G9-M1"]),
    ]


def test_v6c3_01_cold_and_initial_incremental_build_produce_byte_identical_html() -> None:
    nodes = _sample_chain()
    cold = IncrementalASTDifferentialRecompiler.compile_cold_full(nodes)
    recompiler = IncrementalASTDifferentialRecompiler()
    inc = recompiler.compile_incremental(nodes)
    assert inc["bundle_sha256"] == cold["bundle_sha256"]
    assert inc["html_bundle"] == cold["html_bundle"]
    assert "<meta charset=\"UTF-8\">" in inc["html_bundle"]


def test_v6c3_02_second_incremental_build_without_edits_hits_100_percent_cache() -> None:
    nodes = _sample_chain()
    recompiler = IncrementalASTDifferentialRecompiler()
    recompiler.compile_incremental(nodes)
    inc2 = recompiler.compile_incremental(nodes)
    assert inc2["nodes_recompiled"] == 0
    assert inc2["nodes_cached"] == 5
    assert inc2["cache_hit_ratio_pct"] == 100.0


def test_v6c3_03_editing_leaf_node_recompiles_only_that_leaf_node() -> None:
    nodes = _sample_chain()
    recompiler = IncrementalASTDifferentialRecompiler()
    recompiler.compile_incremental(nodes)

    edited = copy.deepcopy(nodes)
    edited[-1].title_en = "Advanced Quadratic Systems"
    res = recompiler.compile_incremental(edited)
    assert res["recompiled_node_ids"] == ["G10-M1"]
    assert res["nodes_cached"] == 4
    assert res["cache_hit_ratio_pct"] == 80.0


def test_v6c3_04_editing_mid_chain_node_invalidates_only_downstream_cone() -> None:
    nodes = _sample_chain()
    recompiler = IncrementalASTDifferentialRecompiler()
    recompiler.compile_incremental(nodes)

    edited = copy.deepcopy(nodes)
    edited[3].formula_latex = "$A x + B y + C = 0$"  # G9-M1 mutated -> invalidates G9-M1 and G10-M1
    res = recompiler.compile_incremental(edited)
    assert res["recompiled_node_ids"] == ["G9-M1", "G10-M1"]
    assert res["cached_node_ids"] == ["G6-M1", "G7-M1", "G8-M1"]


def test_v6c3_05_incremental_edit_output_is_byte_identical_to_fresh_cold_build() -> None:
    nodes = _sample_chain()
    recompiler = IncrementalASTDifferentialRecompiler()
    recompiler.compile_incremental(nodes)

    edited = copy.deepcopy(nodes)
    edited[2].title_hi = "एक चर वाले रैखिक समीकरण"
    inc_res = recompiler.compile_incremental(edited)
    cold_res = IncrementalASTDifferentialRecompiler.compile_cold_full(edited)
    assert inc_res["bundle_sha256"] == cold_res["bundle_sha256"]
    assert inc_res["html_bundle"] == cold_res["html_bundle"]


def test_v6c3_06_recompiler_rejects_empty_node_list() -> None:
    with pytest.raises(IncrementalIRCompilerError):
        IncrementalASTDifferentialRecompiler.compile_cold_full([])


def test_v6c3_07_recompiler_rejects_unknown_dependency_reference() -> None:
    bad_nodes = [
        V6ConceptASTNode("G6-M1", 6, "Ratios", "अनुपात", "$a:b$", "AVR-P301", ["NON-EXISTENT-NODE"])
    ]
    with pytest.raises(IncrementalIRCompilerError):
        IncrementalASTDifferentialRecompiler.compile_cold_full(bad_nodes)


def test_v6c3_08_recompiler_rejects_cyclic_ast_dependency_graph() -> None:
    cyclic_nodes = [
        V6ConceptASTNode("N1", 6, "Node 1", "नोट 1", "$x$", "AVR-P301", ["N2"]),
        V6ConceptASTNode("N2", 7, "Node 2", "नोट 2", "$y$", "AVR-P302", ["N1"]),
    ]
    with pytest.raises(IncrementalIRCompilerError):
        IncrementalASTDifferentialRecompiler.compile_cold_full(cyclic_nodes)


def test_v6c3_09_node_signature_changes_when_parent_signature_changes() -> None:
    node = _sample_chain()[1]
    s1 = IncrementalASTDifferentialRecompiler.compute_node_signature(node, ["parent_sig_a"])
    s2 = IncrementalASTDifferentialRecompiler.compute_node_signature(node, ["parent_sig_b"])
    assert s1 != s2


def test_v6c3_10_mastery_transfer_propagates_weak_foundation_to_downstream_priors() -> None:
    nodes = _sample_chain()
    scores = {"G6-M1": 0.40, "G7-M1": 0.90, "G8-M1": 0.90, "G9-M1": 0.90, "G10-M1": 0.90}
    res = CrossGradeMasteryTransferMatrix.compute_transfer_matrix(nodes, scores, transfer_weight=0.65)
    # Because G6-M1 is 0.40, G7-M1 effective mastery is pulled down below 0.75
    assert res["effective_mastery"]["G7-M1"] < 0.75
    assert res["effective_mastery"]["G10-M1"] < 0.75


def test_v6c3_11_mastery_transfer_generates_grade_ordered_bridge_remediation_plan() -> None:
    nodes = _sample_chain()
    scores = {"G6-M1": 0.92, "G7-M1": 0.45, "G8-M1": 0.50, "G9-M1": 0.52, "G10-M1": 0.48}
    res = CrossGradeMasteryTransferMatrix.compute_transfer_matrix(nodes, scores)
    plan = res["bridge_remediation_plans"]["G10-M1"]
    grades_in_plan = [step["grade"] for step in plan]
    assert grades_in_plan == [7, 8, 9, 10]
    assert plan[0]["node_id"] == "G7-M1"


def test_v6c3_12_mastery_transfer_produces_zero_bottlenecks_when_all_grades_mastered() -> None:
    nodes = _sample_chain()
    scores = {n.node_id: 0.92 for n in nodes}
    res = CrossGradeMasteryTransferMatrix.compute_transfer_matrix(nodes, scores)
    assert res["bottleneck_count"] == 0
    assert res["bridge_remediation_plans"] == {}


def test_v6c3_13_mastery_transfer_clamps_out_of_range_scores_safely() -> None:
    nodes = _sample_chain()[:2]
    scores = {"G6-M1": 1.8, "G7-M1": -0.5}
    res = CrossGradeMasteryTransferMatrix.compute_transfer_matrix(nodes, scores)
    assert 0.0 <= res["effective_mastery"]["G6-M1"] <= 1.0
    assert 0.0 <= res["effective_mastery"]["G7-M1"] <= 1.0


def test_v6c3_14_grade_averages_computed_for_all_present_grades() -> None:
    nodes = _sample_chain()
    scores = {n.node_id: 0.85 for n in nodes}
    res = CrossGradeMasteryTransferMatrix.compute_transfer_matrix(nodes, scores)
    assert set(res["grade_averages"].keys()) == {"G6", "G7", "G8", "G9", "G10"}


def test_v6c3_15_js_incremental_recompiler_module_present_and_valid() -> None:
    js_txt = pathlib.Path("scripts/aasha_v6_incremental_recompiler.js").read_text(encoding="utf-8")
    assert "IncrementalASTDifferentialRecompilerJS" in js_txt
    assert "CrossGradeMasteryTransferMatrixJS" in js_txt


def test_v6c3_16_compare_v6_cycle3_incremental_recompiler_and_mastery_matrix_benchmark() -> None:
    bench = compare_v6_cycle3_incremental_recompiler_and_mastery_matrix()
    assert bench["winner"] == "method-b-incremental-ast-recompiler-and-cross-grade-mastery-matrix"
    mb = bench["method_b_incremental_ast_recompiler"]
    assert mb["cache_hit_ratio_pct"] == 90.0
    assert mb["nodes_recompiled_on_single_edit"] == 2
    assert mb["byte_identical_to_cold_build"] is True
    assert mb["cross_grade_root_cause_detected"] is True
    assert mb["g10_bridge_chain_length"] == 4
