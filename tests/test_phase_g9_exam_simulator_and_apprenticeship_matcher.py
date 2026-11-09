"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G9:
Autonomous Offline Exam-Board Readiness Simulator, Vocational Apprenticeship Matcher
& National Scale Telemetry Audit.
"""

import json
import subprocess
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g9_exam_simulator_and_apprenticeship_matcher import (
    NEXT_FOCUS_UNIT_G10,
    NationalScaleTelemetryAuditor,
    OfflineExamBoardReadinessSimulator,
    VocationalApprenticeshipMatcher,
    execute_chunk_g9_exam_simulator_and_apprenticeship_sync,
)


class TestPhaseG9ExamSimulatorAndApprenticeshipMatcher(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g9_01_exam_board_readiness_simulator_computes_bloom_weights_and_band(self) -> None:
        sim = OfflineExamBoardReadinessSimulator()
        res = sim.evaluate_board_exam_readiness(
            "ANON-STD-01",
            "CBSE-NCERT",
            10,
            {"REMEMBER": 0.90, "UNDERSTAND": 0.88, "APPLY": 0.85, "ANALYZE": 0.84},
        )
        self.assertEqual(res.readiness_band, "DISTINCTION_READY")
        self.assertGreaterEqual(res.composite_readiness_score, 0.85)
        self.assertIn("ANALYZE", res.bilingual_revision_plan)

    def test_g9_02_vocational_apprenticeship_matcher_pairs_qualified_learners(self) -> None:
        matches = VocationalApprenticeshipMatcher.match_verified_candidates()
        self.assertEqual(len(matches), 3)
        for m in matches:
            self.assertTrue(m.match_verified)
            self.assertGreaterEqual(m.teas_mastery_score, 0.80)
            self.assertGreater(m.stipend_seva_credits, 0)

    def test_g9_03_exam_apprenticeship_html5_passes_node_run_qa_js(self) -> None:
        summary = execute_chunk_g9_exam_simulator_and_apprenticeship_sync(self.repo_root)
        html_path = self.repo_root / summary["exam_apprenticeship_html_bundle"]["html_rel_path"]
        qa_script = self.repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "qa" / "run_qa.js"
        proc = subprocess.run(
            ["node", str(qa_script), str(html_path)],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        report = json.loads(proc.stdout.strip())
        self.assertTrue(report["passed"], f"run_qa.js failed: {report.get('failures')}")
        self.assertEqual(len(report["failures"]), 0)

    def test_g9_04_execute_chunk_g9_writes_manifest_and_advances_to_g10(self) -> None:
        summary = execute_chunk_g9_exam_simulator_and_apprenticeship_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G9_OFFLINE_EXAM_SIMULATOR_AND_VOCATIONAL_APPRENTICESHIP_MATCHER_VERIFIED",
        )
        self.assertEqual(summary["national_telemetry_audit"]["pii_leaks_detected"], 0)
        self.assertEqual(summary["national_telemetry_audit"]["paid_api_bleed_usd"], 0.0)
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G10)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])


if __name__ == "__main__":
    unittest.main()
