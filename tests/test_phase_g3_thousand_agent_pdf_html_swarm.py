"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G3:
1,080-Agent Hydro Infinity Swarm Orchestrator, Universal PDF-to-Child-HTML5 Master Factory,
and 10-Chapter NCERT + NCVET/PSSCIVE Production Batch Deployment Pack.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g3_thousand_agent_pdf_html_swarm import (
    CANONICAL_10_CHAPTER_CURRICULUM_SPECS,
    NEXT_FOCUS_UNIT_G4,
    SWARM_SIX_DIVISIONS,
    TenChapterProductionBatchPackager,
    ThousandAgentInfinitySwarmOrchestrator,
    UniversalPDFToChildHTML5MasterFactory,
    execute_chunk_g3_thousand_agent_swarm_and_10chapter_pack_sync,
)


class TestPhaseG3ThousandAgentSwarmAndPDFToHTMLFactory(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g3_01_thousand_agent_swarm_spawns_1080_hibernated_agents_with_zero_idle_ram(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            swarm = ThousandAgentInfinitySwarmOrchestrator(Path(tmp) / "swarm.db")
            res = swarm.dispatch_and_hibernate_swarm_pool()
            self.assertEqual(res["total_swarm_agents_spawned"], 1080)
            self.assertEqual(res["divisions_active"], 6)
            self.assertEqual(res["agents_per_division"], 180)
            self.assertEqual(res["agents_per_chapter"], 108)
            self.assertEqual(res["division_lead_coordinators_resumed"], 6)
            self.assertEqual(res["idle_resident_ram_bytes_per_hibernated_agent"], 0)
            self.assertFalse(res["human_intervention_required"])

    def test_g3_02_universal_pdf_to_child_html5_factory_produces_qa_certified_html(self) -> None:
        factory = UniversalPDFToChildHTML5MasterFactory(self.repo_root)
        html_str, cert, db_entry = factory.compile_pdf_to_child_html5(
            CANONICAL_10_CHAPTER_CURRICULUM_SPECS[0]
        )
        self.assertEqual(cert.chapter_id, "NCERT-G06-MATH-CH07-FRACTIONS")
        self.assertEqual(cert.ten_critical_qa_rules_passed, 10)
        self.assertTrue(cert.under_20mib_ceiling)
        self.assertTrue(cert.zero_external_urls)
        self.assertTrue(cert.tap_select_enforced)
        self.assertEqual(cert.tln_node_count, 4)
        self.assertIn("var NODES=", html_str)
        self.assertIn("data:image/svg+xml;base64,", html_str)

    def test_g3_03_generated_child_html5_passes_node_run_qa_js_harness(self) -> None:
        factory = UniversalPDFToChildHTML5MasterFactory(self.repo_root)
        _, cert, _ = factory.compile_pdf_to_child_html5(CANONICAL_10_CHAPTER_CURRICULUM_SPECS[0])
        html_path = self.repo_root / cert.html_rel_path
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

    def test_g3_04_ten_chapter_production_batch_compiles_all_10_chapters_and_40_nodes(self) -> None:
        summary = execute_chunk_g3_thousand_agent_swarm_and_10chapter_pack_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G3_1080_AGENT_SWARM_AND_10_CHAPTER_CHILD_HTML5_PACK_VERIFIED",
        )
        self.assertEqual(summary["chapters_compiled_count"], 10)
        self.assertEqual(summary["total_tln_nodes_compiled"], 40)
        self.assertTrue(summary["all_chapters_passed_10_critical_qa_rules"])
        self.assertTrue(summary["all_chapters_under_20mib_ceiling"])
        self.assertEqual(summary["dual_output_sqlite_teas_db"]["chapters_count"], 10)
        self.assertEqual(summary["dual_output_sqlite_teas_db"]["tln_nodes_count"], 40)
        self.assertEqual(summary["dual_output_sqlite_teas_db"]["teas_assessments_count"], 40)
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G4)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])


if __name__ == "__main__":
    unittest.main()
