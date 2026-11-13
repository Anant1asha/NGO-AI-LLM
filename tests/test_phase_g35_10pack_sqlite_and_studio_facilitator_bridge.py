"""Unit tests for Phase G35: 10-Pack Dual-Output SQLite Catalogue & Facilitator Bridge."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g35_10pack_sqlite_and_studio_facilitator_bridge import (
    run_phase_g35_cycle,
)


class TestPhaseG35TenPackSQLiteAndFacilitatorBridge(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g35_01_10pack_sqlite_export_and_facilitator_bridge_certified(self) -> None:
        manifest = run_phase_g35_cycle(self.repo_root)

        sq = manifest["sqlite_10pack_catalogue"]
        self.assertEqual(sq["chapters_exported"], 10)
        self.assertEqual(sq["tln_nodes_exported"], 30)
        self.assertEqual(sq["wm_vocabulary_exported"], 1129)
        self.assertTrue(sq["under_20mib_ceiling"])

        br = manifest["facilitator_bridge"]
        self.assertEqual(br["hotspotClusters"], 2)
        self.assertTrue(br["dashboardValid"])
        self.assertTrue(br["flashcardValid"])
        self.assertTrue(br["signedPackValid"])

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], hub["qa_total"])
        self.assertGreaterEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
