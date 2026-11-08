"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G6:
Autonomous National Open-Curriculum PDF Harvester, Multi-Board Textbook Adapter
(CBSE/State/NCVET) & Community Seva Impact Certifier.
"""

import dataclasses
import json
import subprocess
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g6_multiboard_harvester_and_seva_certifier import (
    CommunitySevaImpactCertifier,
    MultiBoardTextbookAdapter,
    NEXT_FOCUS_UNIT_G7,
    NationalOpenCurriculumPDFHarvester,
    SUPPORTED_CURRICULUM_BOARDS,
    execute_chunk_g6_multiboard_and_seva_certifier_sync,
)


class TestPhaseG6MultiBoardHarvesterAndSevaCertifier(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g6_01_national_harvester_locks_all_5_curriculum_boards(self) -> None:
        locks = NationalOpenCurriculumPDFHarvester.harvest_and_lock_all_boards()
        self.assertEqual(len(locks), 5)
        for lk in locks:
            self.assertEqual(lk.tln_node_count, 4)
            self.assertEqual(len(lk.source_pdf_sha256), 64)
            self.assertEqual(len(lk.tln_version_hash), 64)

    def test_g6_02_seva_impact_certifier_builds_tamper_evident_hash_chain(self) -> None:
        locks = NationalOpenCurriculumPDFHarvester.harvest_and_lock_all_boards()
        certs = CommunitySevaImpactCertifier.issue_hash_chained_seva_certificates(locks)
        self.assertEqual(len(certs), 5)
        self.assertTrue(CommunitySevaImpactCertifier.verify_seva_certificate_chain(certs))

        # Tamper with one certificate and verify detection
        tampered = list(certs)
        tampered[2] = dataclasses.replace(tampered[2], eco_seva_saplings_verified=99999)
        self.assertFalse(CommunitySevaImpactCertifier.verify_seva_certificate_chain(tampered))

    def test_g6_03_multiboard_seva_html5_passes_node_run_qa_js(self) -> None:
        summary = execute_chunk_g6_multiboard_and_seva_certifier_sync(self.repo_root)
        html_path = self.repo_root / summary["multiboard_seva_html_bundle"]["html_rel_path"]
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

    def test_g6_04_execute_chunk_g6_end_to_end_writes_manifest_and_advances_to_g7(self) -> None:
        summary = execute_chunk_g6_multiboard_and_seva_certifier_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G6_MULTIBOARD_HARVESTER_AND_SEVA_IMPACT_CERTIFIER_VERIFIED",
        )
        self.assertEqual(summary["boards_harvested_count"], 5)
        self.assertEqual(summary["total_multiboard_tln_nodes"], 20)
        self.assertTrue(summary["seva_impact_certification"]["hash_chain_integrity_verified"])
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G7)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])


if __name__ == "__main__":
    unittest.main()
