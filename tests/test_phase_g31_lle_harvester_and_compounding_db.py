"""
Unit tests for Phase G31: Expanded LLE Harvest, Compounding Local DB, Open-Source Registry & Swarm Synthesis.
"""

import sqlite3
import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g31_lle_harvester_and_compounding_db import (
    run_phase_g31_cycle,
)


class TestPhaseG31LLEHarvestAndCompoundingDB(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g31_01_expanded_lle_harvest_and_compounding_db_grows(self) -> None:
        manifest = run_phase_g31_cycle(self.repo_root)

        self.assertEqual(manifest["phase"], "G31")
        self.assertGreater(manifest["lle_harvest"]["wm_count"], 296)
        self.assertGreaterEqual(manifest["lle_harvest"]["conn_count"], 46)

        db_info = manifest["compounding_db"]
        self.assertEqual(db_info["wm_rows_stored"], manifest["lle_harvest"]["wm_count"])
        self.assertEqual(db_info["conn_rows_stored"], manifest["lle_harvest"]["conn_count"])
        self.assertEqual(db_info["reusable_mechanics_stored"], 5)
        self.assertEqual(db_info["open_source_foundations_stored"], 7)
        self.assertGreaterEqual(db_info["build_cache_records"], 1)

        # Verify SQLite file directly
        conn = sqlite3.connect(str(self.repo_root / "aasha_operational.db"))
        try:
            cnt = conn.execute("SELECT COUNT(*) FROM lle_vocabulary").fetchone()[0]
            self.assertGreater(cnt, 342)
        finally:
            conn.close()

    def test_g31_02_hydrogen_argon_swarm_synthesized_module_passes_28_qa(self) -> None:
        manifest = run_phase_g31_cycle(self.repo_root)
        mod = manifest["swarm_synthesized_module"]

        self.assertEqual(mod["swarm_final_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(mod["qa_checks_passed"], mod["qa_checks_total"])
        self.assertGreaterEqual(mod["qa_checks_total"], 28)
        self.assertTrue(mod["under_20mib_ceiling"])


if __name__ == "__main__":
    unittest.main()
