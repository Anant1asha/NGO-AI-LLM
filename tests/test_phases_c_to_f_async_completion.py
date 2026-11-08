"""
Unit tests for AASHA AIOS V3 Asynchronous Batch Execution of Phases C through F
(Chunks C1, C2, C3, D1, D2, D3, E1, E2, E3, F1, F2 -> Next Focus Unit G1).
"""

import json
import unittest
from pathlib import Path

from aasha.orchestrator.phases_c_to_f_async_executor import (
    PhasesCToFAsyncChunkExecutor,
    REMAINING_CHUNKS_C_TO_F,
    execute_all_pending_chunks_c_to_f_sync,
)


class TestPhasesCToFAsyncCompletion(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_cf_01_remaining_chunks_list_contains_all_11_pending_chunks(self) -> None:
        self.assertEqual(
            REMAINING_CHUNKS_C_TO_F,
            ("C1", "C2", "C3", "D1", "D2", "D3", "E1", "E2", "E3", "F1", "F2"),
        )

    def test_cf_02_async_executor_completes_all_11_chunks_and_passes_oracle(self) -> None:
        summary = execute_all_pending_chunks_c_to_f_sync(self.repo_root)
        self.assertEqual(summary["status"], "ALL_PHASES_A_TO_F_100_PERCENT_VERIFIED")
        self.assertEqual(len(summary["chunks_executed_in_async_wave"]), 11)
        self.assertEqual(len(summary["total_chunks_completed"]), 18)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])
        self.assertFalse(summary["autonomous_authorization"]["human_approval_required"])

    def test_cf_03_phase_c_visual_harvest_and_p406_wired(self) -> None:
        summary = execute_all_pending_chunks_c_to_f_sync(self.repo_root)
        by_id = {r["chunk_id"]: r for r in summary["chunk_results"]}
        self.assertEqual(by_id["C1"]["metrics"]["avr_mechanics_certified"], 21)
        self.assertEqual(by_id["C1"]["metrics"]["harv_patterns_certified"], 40)
        self.assertTrue(by_id["C2"]["metrics"]["p406_wired"])
        self.assertEqual(by_id["C3"]["metrics"]["visual_contract_assertions"], 97)

    def test_cf_04_phase_d_student_pwa_and_centre_server_verified(self) -> None:
        summary = execute_all_pending_chunks_c_to_f_sync(self.repo_root)
        by_id = {r["chunk_id"]: r for r in summary["chunk_results"]}
        self.assertTrue(by_id["D1"]["metrics"]["fastify_sqlite_ready"])
        self.assertTrue(by_id["D2"]["metrics"]["staff_pin_1080_verified"])
        self.assertTrue(by_id["D3"]["metrics"]["indexeddb_offline_cache"])
        self.assertLessEqual(by_id["D3"]["metrics"]["peak_ram_mb_on_4gb_device"], 512)

    def test_cf_05_phase_e_studio_and_ncvet_psscive_bridge_verified(self) -> None:
        summary = execute_all_pending_chunks_c_to_f_sync(self.repo_root)
        by_id = {r["chunk_id"]: r for r in summary["chunk_results"]}
        self.assertTrue(by_id["E1"]["metrics"]["qa_scorecard_integrated"])
        self.assertTrue(by_id["E2"]["metrics"]["psscive_bridge_ready"])
        self.assertTrue(by_id["E3"]["metrics"]["cross_repo_e2e_passed"])

        # Import and test the generated NCVET/PSSCIVE bridge function directly
        import importlib.util
        bridge_path = self.repo_root / "apsl-backend-foundation" / "api" / "bridge.py"
        spec = importlib.util.spec_from_file_location("apsl_bridge", bridge_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        mapped = mod.map_chapter_to_ncvet_qualification("NCERT-CLASS6-MATH-CH07-FRACTIONS", 0.90)
        self.assertTrue(mapped["ncvet_certified_eligible"])
        self.assertEqual(mapped["qp_code"], "SSC/Q0101")

    def test_cf_06_phase_f_release_readiness_manifest_written_and_locked(self) -> None:
        summary = execute_all_pending_chunks_c_to_f_sync(self.repo_root)
        manifest_path = self.repo_root / "RELEASE_READINESS_MANIFEST.json"
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["roadmap_completion_ratio"], "18/18 (100.0%)")
        self.assertEqual(len(manifest["completed_chunks"]), 18)
        self.assertTrue(manifest["sec001_zero_secrets_verified"])
        self.assertEqual(
            summary["next_focus_unit"],
            "G1: Continuous Autonomous Post-MVP Production Evolution & Live Cohort Telemetry Loop",
        )


if __name__ == "__main__":
    unittest.main()
