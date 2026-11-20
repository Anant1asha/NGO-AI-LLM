"""Unit tests for Phase G44: SQLite Gzip Catalogue Rebuild & Offline PWA Cache Auditor."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g44_sqlite_catalogue_rebuild_and_pwa_cache_auditor import (
    run_phase_g44_cycle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG44SqliteAndPwaCache(unittest.TestCase):
    def test_g44_rebuilds_sqlite_gzip_and_certifies_pwa_cache_and_hub(self) -> None:
        manifest = run_phase_g44_cycle(REPO_ROOT)
        cat = manifest["sqlite_gzip_catalogue"]
        self.assertGreaterEqual(cat["chapters_count"], 13)
        self.assertGreaterEqual(cat["tln_nodes_count"], 39)
        self.assertGreaterEqual(cat["wm_entries_count"], 1129)
        self.assertEqual(cat["conn_entries_count"], 85)
        self.assertGreaterEqual(cat["vocabulary_rows_count"], 1190)
        self.assertTrue(cat["under_20mib"])

        hub = manifest["html5_hub_and_pwa_cache"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], 28)
        self.assertEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])

        sw = hub["sw_cache_manifest"]
        self.assertEqual(sw["certified_html5_modules_count"], 21)
        self.assertGreaterEqual(sw["total_assets"], 26)
        self.assertTrue(sw["under_20mib_ceiling"])


if __name__ == "__main__":
    unittest.main()
