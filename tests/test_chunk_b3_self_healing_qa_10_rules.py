"""
Unit tests for AASHA AIOS V3 Chunk B3:
Automated `run_self_healing_qa_pass` (`max_attempts=2`) integration with 10 Critical QA Rules.
"""

import unittest
from pathlib import Path

from aasha.orchestrator.unified_e2e_pipeline import (
    SelfHealingCompilerRepairLoop,
    TEN_CRITICAL_QA_RULE_NAMES,
    audit_ten_critical_html_qa_rules,
    execute_chunk_b3_self_healing_qa_cycle,
    run_self_healing_html_qa_pass,
)


class TestChunkB3SelfHealingQAPass(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_b3_01_ten_critical_qa_rules_list_is_complete(self) -> None:
        self.assertEqual(len(TEN_CRITICAL_QA_RULE_NAMES), 10)

    def test_b3_02_production_fractions_html_passes_all_10_critical_qa_rules(self) -> None:
        html_path = (
            self.repo_root
            / "Aasha-AI"
            / "aasha-pipeline-with-master-json"
            / "examples"
            / "Fractions_Gamified_v5_3.html"
        )
        raw_html = html_path.read_text(encoding="utf-8")
        audit = audit_ten_critical_html_qa_rules(raw_html)
        self.assertTrue(audit["all_ten_rules_passed"])
        self.assertEqual(audit["rules_passed_count"], 10)

    def test_b3_03_audit_detects_all_fault_classes_in_unhealed_html(self) -> None:
        bad_html = (
            '<html><head><link rel="stylesheet" href="https://cdn.example.com/x.css"></head>'
            '<body><div draggable="true">{{UNBOUND_TOKEN}} The correct answer is 42</div>'
            '<script>alert("x"); confirm("y");</script></body></html>'
        )
        audit = audit_ten_critical_html_qa_rules(bad_html)
        self.assertFalse(audit["all_ten_rules_passed"])
        self.assertGreaterEqual(len(audit["violations"]), 6)

    def test_b3_04_self_healing_html_qa_pass_repairs_all_10_rules_within_2_attempts(self) -> None:
        bad_html = (
            '<html><head><link rel="stylesheet" href="https://cdn.example.com/x.css"></head>'
            '<body><div draggable="true">{{UNBOUND_TOKEN}} The correct answer is 42</div>'
            '<script>alert("x"); confirm("y");</script></body></html>'
        )
        res = run_self_healing_html_qa_pass(bad_html, max_attempts=2)
        self.assertTrue(res["all_ten_rules_passed"])
        self.assertEqual(res["rules_passed_count"], 10)
        self.assertLessEqual(res["attempts_used"], 2)
        self.assertGreaterEqual(res["repairs_applied_count"], 6)
        self.assertIn('data-tap-select="true"', res["healed_html"])
        self.assertNotIn('draggable="true"', res["healed_html"])
        self.assertNotIn("alert(", res["healed_html"])
        self.assertNotIn("confirm(", res["healed_html"])
        self.assertIn("_weCheckRendered", res["healed_html"])

    def test_b3_05_self_healing_html_qa_pass_enforces_max_attempts_bound(self) -> None:
        with self.assertRaises(ValueError):
            run_self_healing_html_qa_pass("<html></html>", max_attempts=0)
        with self.assertRaises(ValueError):
            run_self_healing_html_qa_pass("<html></html>", max_attempts=3)

    def test_b3_06_cleanroom_license_sanitization_removes_raw_gpl_headers(self) -> None:
        gpl_html = "<html><body>GNU GENERAL PUBLIC LICENSE GPL-3.0</body></html>"
        res = run_self_healing_html_qa_pass(gpl_html, max_attempts=2)
        self.assertTrue(res["all_ten_rules_passed"])
        self.assertNotIn("GPL-3.0", res["healed_html"])
        self.assertIn("CLEANROOM-EXTRACT-MIT", res["healed_html"])

    def test_b3_07_compiler_spec_self_healing_repairs_latex_and_spoilers(self) -> None:
        res = SelfHealingCompilerRepairLoop.run_self_healing_qa_pass({
            "formula": "$F = m \\cdot {a +*",
            "bilingual_glossary": {},
            "draft_hint": "The correct answer is 24.",
            "target_answer": 24.0,
            "student_attempt": 10.0,
        })
        self.assertTrue(res["self_healing_succeeded"])
        self.assertGreaterEqual(res["repairs_applied_count"], 4)

    def test_b3_08_execute_chunk_b3_cycle_end_to_end(self) -> None:
        summary = execute_chunk_b3_self_healing_qa_cycle(self.repo_root)
        self.assertEqual(summary["status"], "B3_SELF_HEALING_QA_10_RULES_VERIFIED")
        self.assertEqual(summary["production_bundle_rules_passed"], 10)
        self.assertTrue(summary["fault_injected_bundle_healed"])
        self.assertTrue(summary["compiler_spec_self_healing_succeeded"])


if __name__ == "__main__":
    unittest.main()
