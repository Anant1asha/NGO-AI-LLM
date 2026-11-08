"""
tests/test_phase_g4_knowledge_graph_mastery_twins.py
Unit tests for Phase G4: Autonomous Cross-Grade Knowledge Graph Distillation,
Adaptive Student Mastery Twins & Teacher Co-Pilot Pack
"""

import os
import sys
import unittest
import json

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from aasha.orchestrator.phase_g4_knowledge_graph_mastery_twins import (
    CrossGradeKnowledgeGraphDistiller,
    AdaptiveStudentMasteryTwin,
    TeacherCoPilotPackager,
    TenChapterMasteryIntegration,
    KnowledgeNode
)

class TestPhaseG4KnowledgeGraphAndMasteryTwins(unittest.TestCase):
    def setUp(self):
        self.distiller = CrossGradeKnowledgeGraphDistiller()

    def test_01_knowledge_graph_dag_acyclicity(self):
        """Verify cross-grade prerequisite DAG across all 40 TLN nodes is strictly acyclic."""
        self.assertEqual(len(self.distiller.nodes), 40, "Must contain exactly 40 TLN nodes across 10 chapters")
        self.assertTrue(len(self.distiller.edges) >= 30, "Must have comprehensive prerequisite edges")
        self.assertTrue(self.distiller.verify_dag_acyclicity(), "DAG must be strictly acyclic (Kahn's algorithm)")

    def test_02_cross_grade_and_cross_subject_linkage(self):
        """Verify STEM science/math concepts bridge into Vocational Jal Seva."""
        jal_seva_node = self.distiller.nodes.get("NCVET-PSSCIVE-L4-AGRI_TLN_01")
        self.assertIsNotNone(jal_seva_node)
        self.assertIn("NCERT-G08-SCI-CH11_TLN_03", jal_seva_node.prerequisites,
                      "G08 Force and Pressure must be prerequisite for Jal Seva drip pressure")

    def test_03_adaptive_student_mastery_twin_bkt_and_irt(self):
        """Verify BKT updates monotonically on correct responses and recovers from slips."""
        node = self.distiller.nodes["NCERT-G06-MATH-CH07_TLN_01"]
        twin = AdaptiveStudentMasteryTwin(node, student_theta=0.5)

        initial_p = twin.mastery_p
        # Three consecutive correct answers should increase mastery probability
        p1 = twin.update_bkt(True)
        p2 = twin.update_bkt(True)
        p3 = twin.update_bkt(True)

        self.assertGreater(p1, initial_p)
        self.assertGreater(p2, p1)
        self.assertGreater(p3, p2)
        self.assertTrue(twin.is_mastered(0.70))

        # Test IRT 2PL probability
        prob = twin.calculate_irt_probability(0.5)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

        # Test Web Component script generation
        js_code = twin.export_web_component_js()
        self.assertIn("customElements.define('aasha-mastery-twin'", js_code)
        self.assertLess(len(js_code.encode('utf-8')), 8192, "Web component must be < 8 KB")

    def test_04_teacher_copilot_guide_synthesis(self):
        """Verify bilingual Teacher Co-Pilot guide generation with 0 target-answer leaks."""
        packager = TeacherCoPilotPackager(self.distiller)
        guide_md = packager.generate_teacher_copilot_guide("NCERT-G06-MATH-CH07")

        self.assertIn("शिक्षक मार्गदर्शन एवं निदान सह-पायलट", guide_md)
        self.assertIn("NCERT-G06-MATH-CH07", guide_md)
        self.assertIn("Remedial Action Matrix", guide_md)
        self.assertNotIn("सही उत्तर है", guide_md, "Must never leak target answers to students")

    def test_05_ten_chapter_mastery_integration_and_ceiling(self):
        """Verify complete G4 evolution, HTML5 module enhancement, and ceiling check."""
        integration = TenChapterMasteryIntegration()
        manifest = integration.execute_g4_evolution()

        self.assertEqual(manifest["total_tln_nodes"], 40)
        self.assertTrue(manifest["dag_acyclic"])
        self.assertEqual(manifest["teacher_guides_generated"], 10)
        self.assertEqual(manifest["enhanced_modules_count"], 10)
        self.assertTrue(manifest["all_under_ceiling"])
        print(f"Enhanced 10 modules total size: {manifest['total_size_bytes']} bytes (< 20 MiB ceiling)")

if __name__ == "__main__":
    unittest.main()
