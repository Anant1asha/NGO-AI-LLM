"""
Unit, End-to-End 5-Stage Pipeline Integration & Self-Healing Compiler Repair Test Suite
for TASK-UNIFIED-E2E-PIPELINE-ORCHESTRATOR (Cycle 4) (16 tests -> 396/396 cumulative).
"""
from __future__ import annotations

import pathlib
import pytest

from aasha.orchestrator.unified_e2e_pipeline import (
    EndToEndPipelineError,
    SelfHealingCompilerRepairLoop,
    UnifiedEndToEndPipelineOrchestrator,
    compare_cycle4_unified_e2e_pipeline_and_self_healing,
)
from aasha.v6_compiler.incremental_ir_recompiler import V6ConceptASTNode


def test_c4_01_self_healing_repairs_unbalanced_latex_braces_and_dollars() -> None:
    fixed, repairs = SelfHealingCompilerRepairLoop.repair_latex_formula("$v = \\frac{d}{t")
    assert fixed == "$v = \\frac{d}{t}$"
    assert "MISSING_CLOSING_BRACES_APPENDED" in repairs
    assert "DOLLAR_MATH_DELIMITERS_BALANCED" in repairs


def test_c4_02_self_healing_repairs_consecutive_and_trailing_operators() -> None:
    fixed, repairs = SelfHealingCompilerRepairLoop.repair_latex_formula("$F = m +* a +$")
    assert "+*" not in fixed
    assert not fixed.endswith("+$")
    assert "CONSECUTIVE_OPERATORS_NORMALIZED" in repairs
    assert "TRAILING_OPERATOR_STRIPPED" in repairs


def test_c4_03_self_healing_populates_missing_bilingual_glossary_entries() -> None:
    glossary, repairs = SelfHealingCompilerRepairLoop.repair_bilingual_glossary(
        "$F = m \\cdot a$", {"F": {"en": "Force", "indic": "बल"}}
    )
    assert "m" in glossary and "a" in glossary
    assert len(repairs) == 2


def test_c4_04_self_healing_breaks_cross_grade_ast_dependency_cycles() -> None:
    nodes = [
        V6ConceptASTNode("G7-N1", 7, "Base", "आधार", "$x$", "AVR-P301", ["G9-N2"]),
        V6ConceptASTNode("G9-N2", 9, "Upper", "उच्च", "$y$", "AVR-P302", ["G7-N1"]),
    ]
    repaired, repairs = SelfHealingCompilerRepairLoop.repair_ast_dependency_cycles(nodes)
    assert repaired[0].depends_on == []
    assert repaired[1].depends_on == ["G7-N1"]
    assert any("REPAIRED_CYCLE_BACK_EDGE" in r for r in repairs)


def test_c4_05_self_healing_redacts_spoiler_leak_and_substitutes_socratic_hint() -> None:
    fixed_hint, repairs = SelfHealingCompilerRepairLoop.repair_spoiler_in_text(
        "The correct answer is 42.", target_answer=42.0, student_attempt=-42.0
    )
    assert "42" not in fixed_hint
    assert "Counterfactual check:" in fixed_hint
    assert len(repairs) == 1


def test_c4_06_self_healing_preserves_already_clean_hint_unchanged() -> None:
    clean = "Try adjusting the mass slider to observe acceleration."
    fixed_hint, repairs = SelfHealingCompilerRepairLoop.repair_spoiler_in_text(
        clean, target_answer=42.0, student_attempt=10.0
    )
    assert fixed_hint == clean
    assert repairs == []


def test_c4_07_run_self_healing_qa_pass_repairs_all_5_fault_classes_together() -> None:
    faulty_spec = {
        "formula": "$F = \\frac{m \\cdot a}{1",
        "bilingual_glossary": {},
        "ast_nodes": [
            V6ConceptASTNode("G8-A", 8, "A", "अ", "$x$", "AVR-P301", ["G10-B"]),
            V6ConceptASTNode("G10-B", 10, "B", "ब", "$y$", "AVR-P302", ["G8-A"]),
        ],
        "wfg_edges": [("w1", "w2"), ("w2", "w1")],
        "draft_hint": "The solution is 50.",
        "target_answer": 50.0,
        "student_attempt": -50.0,
    }
    res = SelfHealingCompilerRepairLoop.run_self_healing_qa_pass(faulty_spec)
    assert res["self_healing_succeeded"] is True
    assert res["repairs_applied_count"] >= 5


def test_c4_08_unified_e2e_pipeline_executes_clean_chapter_request_across_all_5_stages() -> None:
    orch = UnifiedEndToEndPipelineOrchestrator()
    res = orch.execute_full_pipeline(
        {
            "query": "NCERT Class 9 Force $F = m \\cdot a$",
            "formula": "$F = m \\cdot a$",
            "bilingual_glossary": {
                "F": {"en": "Force", "indic": "बल"},
                "m": {"en": "Mass", "indic": "द्रव्यमान"},
                "a": {"en": "Acceleration", "indic": "त्वरण"},
            },
            "draft_hint": "Increase mass to see how acceleration changes.",
            "target_answer": 24.0,
        },
        enable_self_healing=False,
    )
    assert res["pipeline_status"] == "SUCCESS"
    assert res["stage2_fork_join_consensus"]["byzantine_agents_quarantined"] == 1
    assert res["stage3_f27_simulation"]["verlet_energy_conserved"] is True
    assert res["stage5_wb_offline_packager"]["within_20mib_ceiling"] is True
    assert res["stage5_wb_offline_packager"]["phoneme_timing_drift_ms"] == 0.0


def test_c4_09_unified_e2e_pipeline_raises_on_unhealed_spoiler_when_self_healing_disabled() -> None:
    orch = UnifiedEndToEndPipelineOrchestrator()
    with pytest.raises(EndToEndPipelineError):
        orch.execute_full_pipeline(
            {
                "query": "Force",
                "formula": "$F = m \\cdot a$",
                "draft_hint": "The answer is 24.",
                "target_answer": 24.0,
            },
            enable_self_healing=False,
        )


def test_c4_10_unified_e2e_pipeline_self_heals_faulty_request_and_succeeds() -> None:
    orch = UnifiedEndToEndPipelineOrchestrator()
    res = orch.execute_full_pipeline(
        {
            "query": "Force",
            "formula": "$F = \\frac{m \\cdot a}{1",
            "draft_hint": "The answer is 24.",
            "target_answer": 24.0,
        },
        enable_self_healing=True,
    )
    assert res["pipeline_status"] == "SUCCESS"
    assert res["self_healing_report"]["repairs_applied_count"] >= 3


def test_c4_11_unified_e2e_pipeline_achieves_100_percent_v6_ast_cache_hit_on_repeat_run() -> None:
    orch = UnifiedEndToEndPipelineOrchestrator()
    req = {"query": "Force", "formula": "$F = m \\cdot a$", "target_answer": 24.0}
    r1 = orch.execute_full_pipeline(req)
    r2 = orch.execute_full_pipeline(req)
    assert r1["stage4_v6_ir_compiler"]["bundle_sha256"] == r2["stage4_v6_ir_compiler"]["bundle_sha256"]
    assert r2["stage4_v6_ir_compiler"]["cache_hit_ratio_pct"] == 100.0


def test_c4_12_unified_e2e_pipeline_generates_valid_merkle_root_in_stage5() -> None:
    orch = UnifiedEndToEndPipelineOrchestrator()
    res = orch.execute_full_pipeline({"query": "Force", "formula": "$F = m \\cdot a$"})
    assert len(res["stage5_wb_offline_packager"]["target_merkle_root"]) == 64


def test_c4_13_self_healing_handles_empty_formula_gracefully() -> None:
    fixed, repairs = SelfHealingCompilerRepairLoop.repair_latex_formula("   ")
    assert fixed == "$F = m \\cdot a$"
    assert "EMPTY_FORMULA_DEFAULTED" in repairs


def test_c4_14_self_healing_removes_self_dependency_and_unknown_node_refs() -> None:
    nodes = [
        V6ConceptASTNode("G6-N1", 6, "Ratios", "अनुपात", "$a:b$", "AVR-P301", ["G6-N1", "G99-UNKNOWN"])
    ]
    repaired, repairs = SelfHealingCompilerRepairLoop.repair_ast_dependency_cycles(nodes)
    assert repaired[0].depends_on == []
    assert len(repairs) == 2


def test_c4_15_js_unified_e2e_pipeline_module_present_and_valid() -> None:
    js_txt = pathlib.Path("scripts/aasha_unified_e2e_pipeline.js").read_text(encoding="utf-8")
    assert "SelfHealingCompilerRepairLoopJS" in js_txt
    assert "UnifiedEndToEndPipelineOrchestratorJS" in js_txt


def test_c4_16_compare_cycle4_unified_e2e_pipeline_and_self_healing_benchmark() -> None:
    bench = compare_cycle4_unified_e2e_pipeline_and_self_healing()
    assert bench["winner"] == "method-b-unified-5stage-e2e-orchestrator-with-self-healing-loop"
    mb = bench["method_b_unified_self_healing_pipeline"]
    assert mb["pipeline_completion_rate_pct"] == 100.0
    assert mb["repairs_applied_count"] >= 6
    assert mb["warm_ast_cache_hit_pct"] == 100.0
    assert mb["all_5_stages_verified"] is True
