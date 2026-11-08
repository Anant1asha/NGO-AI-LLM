"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G4:
Autonomous Cross-Grade Knowledge Graph Distillation, Adaptive Student Mastery Twins
& Offline Teacher Co-Pilot HTML5 Pack.
"""

import json
import subprocess
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g4_knowledge_graph_and_teacher_copilot import (
    AdaptiveStudentMasteryTwinEngine,
    CrossGradeKnowledgeGraphDistiller,
    NEXT_FOCUS_UNIT_G5,
    OfflineTeacherCoPilotPackSynthesizer,
    execute_chunk_g4_knowledge_graph_and_teacher_copilot_sync,
)


class TestPhaseG4KnowledgeGraphAndTeacherCoPilot(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g4_01_cross_grade_dag_distills_all_10_chapters_and_is_cycle_free(self) -> None:
        dag = CrossGradeKnowledgeGraphDistiller.distill_cross_grade_dag()
        self.assertEqual(dag["total_chapters_in_graph"], 10)
        self.assertEqual(dag["total_prerequisite_edges"], 6)
        self.assertTrue(dag["dag_cycle_free_verified"])
        self.assertEqual(len(dag["knowledge_graph_sha256"]), 64)

    def test_g4_02_adaptive_student_mastery_twin_traces_root_cause_prerequisite(self) -> None:
        engine = AdaptiveStudentMasteryTwinEngine()
        diag = engine.diagnose_learner_gap(
            "STUDENT-RAW-ID-001",
            "NCERT-G08-MATH-CH08-COMPARING-QUANTITIES",
            0.62,
        )
        self.assertTrue(diag.anon_learner_hash.startswith("TWIN-"))
        self.assertNotIn("STUDENT-RAW-ID-001", diag.anon_learner_hash)
        self.assertEqual(
            diag.root_cause_prerequisite_chapter_id,
            "NCERT-G06-MATH-CH07-FRACTIONS",
        )
        self.assertGreaterEqual(diag.prerequisite_transfer_weight, 0.85)

    def test_g4_03_teacher_copilot_html5_passes_node_run_qa_js_harness(self) -> None:
        summary = execute_chunk_g4_knowledge_graph_and_teacher_copilot_sync(self.repo_root)
        html_path = self.repo_root / summary["teacher_copilot_bundle"]["html_rel_path"]
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

    def test_g4_04_execute_chunk_g4_writes_manifest_and_advances_to_g5(self) -> None:
        summary = execute_chunk_g4_knowledge_graph_and_teacher_copilot_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G4_CROSS_GRADE_DAG_MASTERY_TWINS_AND_TEACHER_COPILOT_VERIFIED",
        )
        self.assertEqual(
            summary["teacher_copilot_bundle"]["ten_critical_qa_rules_passed"],
            10,
        )
        self.assertTrue(summary["teacher_copilot_bundle"]["under_20mib_ceiling"])
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G5)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])


if __name__ == "__main__":
    unittest.main()
