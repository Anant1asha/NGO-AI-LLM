"""Unit tests for Phase G36: NCVET/PSSCIVE Vocational Simulators & Offline OTA Delta-Packager."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g36_ncvet_vocational_and_ota_delta_packager import (
    run_phase_g36_cycle,
)


class TestPhaseG36NCVETVocationalAndOTADelta(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g36_01_ncvet_psscive_3_roles_certified_and_ota_delta_packed(self) -> None:
        manifest = run_phase_g36_cycle(self.repo_root)
        self.assertEqual(manifest["roles_compiled"], 3)
        self.assertTrue(manifest["all_certified"])
        ota = manifest["ota_delta_pack"]
        self.assertTrue(ota["under_20mib"])
        self.assertGreater(ota["gzip_bytes"], 200)


if __name__ == "__main__":
    unittest.main()
