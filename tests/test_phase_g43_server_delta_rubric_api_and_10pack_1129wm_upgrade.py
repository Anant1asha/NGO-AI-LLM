"""Unit tests for Phase G43: Server Delta/Rubric Endpoints & 10-Chapter Pack 1,129 WM Upgrade."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g43_server_delta_rubric_api_and_10pack_1129wm_upgrade import (
    run_phase_g43_cycle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG43ServerAnd10PackUpgrade(unittest.TestCase):
    def test_g43_upgrades_all_10_chapters_to_1129_wm_and_certifies_hub(self) -> None:
        manifest = run_phase_g43_cycle(REPO_ROOT)
        pack = manifest["ten_chapter_pack_upgrade"]
        self.assertEqual(pack["modules_upgraded"], 10)
        self.assertEqual(pack["wm_entries_per_module"], 1129)
        self.assertEqual(pack["conn_entries_per_module"], 85)
        self.assertTrue(pack["all_passed_28_of_28"])

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], 28)
        self.assertEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
