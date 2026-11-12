"""Unit tests for Phase G34: 100% Phonetic LLE & 10-Chapter Gamified Upgrade."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g34_10chapter_gamified_upgrade import (
    run_phase_g34_cycle,
)


class TestPhaseG34TenChapterGamifiedUpgrade(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g34_01_phonetic_lle_100pct_and_all_10_chapters_certified(self) -> None:
        manifest = run_phase_g34_cycle(self.repo_root)
        self.assertEqual(manifest["phonetic_lle_closure"]["wm_with_phonetic_pct"], 100.0)
        self.assertEqual(manifest["g3_10chapter_pack_upgrade"]["chapters_upgraded"], 10)
        self.assertTrue(manifest["g3_10chapter_pack_upgrade"]["all_certified"])


if __name__ == "__main__":
    unittest.main()
