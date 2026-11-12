"""
Unit tests for Phase G29: Multi-Chapter Schoolbook TLN-to-HTML5 Batch Synthesis,
Dual-Output SQLite Catalogue Export & Fastify/SQLite Centre Server TEAS Store Redemption Sync.
"""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g28_swarm_clarity_aios_learning_gamified_orchestrator import (
    inspect_html5_qa_violations,
)
from src.aasha.orchestrator.phase_g29_multi_chapter_v5_and_centre_server_sync import (
    MultiChapterV5BatchAndCentreServerOrchestrator,
    run_phase_g29_multi_chapter_v5_and_centre_server_sync_cycle,
)


class TestPhaseG29MultiChapterV5AndCentreServerSync(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.orchestrator = MultiChapterV5BatchAndCentreServerOrchestrator(self.repo_root)

    def test_g29_01_multi_chapter_v5_batch_synthesis_5_ncert_chapters(self) -> None:
        batch = self.orchestrator.execute_multi_chapter_v5_batch_synthesis()

        self.assertEqual(batch["chapter_count"], 5)
        self.assertEqual(batch["total_tln_nodes"], 16)
        self.assertGreaterEqual(batch["total_math_tokens_preserved"], 16)
        self.assertEqual(batch["wm_dictionary_count"], 296)
        self.assertEqual(batch["conn_dictionary_count"], 46)

    def test_g29_02_dual_output_sqlite_catalogue_export(self) -> None:
        batch = self.orchestrator.execute_multi_chapter_v5_batch_synthesis()
        sqlite_cat = self.orchestrator.execute_dual_output_sqlite_catalogue_export(batch)

        self.assertEqual(sqlite_cat["chapters_exported"], 5)
        self.assertEqual(sqlite_cat["tln_nodes_exported"], 16)
        self.assertEqual(sqlite_cat["wm_vocabulary_exported"], 296)
        self.assertTrue(sqlite_cat["under_20mib_ceiling"])
        self.assertGreater(sqlite_cat["gzip_db_bytes"], 512)
        self.assertEqual(len(sqlite_cat["gzip_sha256"]), 64)

    def test_g29_03_centre_server_fastify_store_redemption_and_cohort_pack_sync(self) -> None:
        server_res = self.orchestrator.execute_centre_server_fastify_store_sync_verification()

        self.assertEqual(server_res["serverHealthStatus"], "ok")
        self.assertEqual(server_res["syncedQuizEvents"], 3)
        self.assertEqual(server_res["coinsAwarded"], 300)
        self.assertEqual(server_res["invalidPinStatusCode"], 403)
        self.assertEqual(server_res["validRedemptionStatus"], "redeemed")
        self.assertEqual(server_res["balanceAfterRedemption"], 50)
        self.assertEqual(server_res["restockedGeometryBoxQty"], 44)
        self.assertTrue(server_res["cohortPackLocalValid"])
        self.assertEqual(server_res["cohortPackServerStatus"], "ingested")
        self.assertEqual(server_res["cohortPackReconciledOrders"], 1)
        self.assertTrue(server_res["cohortPackIntegrityHash"].startswith("fnv1a32:"))
        self.assertTrue(server_res["snapshotLocalValid"])
        self.assertEqual(server_res["snapshotBackupStatus"], "backed_up")
        self.assertEqual(server_res["snapshotRestoredChaptersCount"], 3)

    def test_g29_04_end_to_end_cycle_and_html5_hub_generation(self) -> None:
        manifest = run_phase_g29_multi_chapter_v5_and_centre_server_sync_cycle(self.repo_root)

        self.assertEqual(manifest["phase"], "G29")
        self.assertEqual(manifest["verified_chunk_count"], 47)

        hub = manifest["html5_hub"]
        self.assertEqual(
            hub["file_name"],
            "Multi_Chapter_V5_Batch_Centre_Server_Store_Sync_Hub_v5.html",
        )
        self.assertTrue(hub["under_20mib_ceiling"])
        html_text = Path(hub["file_path"]).read_text(encoding="utf-8")
        self.assertEqual(len(inspect_html5_qa_violations(html_text)), 0)


if __name__ == "__main__":
    unittest.main()
