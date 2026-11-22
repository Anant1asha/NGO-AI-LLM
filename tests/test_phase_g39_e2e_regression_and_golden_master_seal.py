"""Unit tests for Phase G39: End-to-End 17-Module QA Regression Gate & Golden Master Seal."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g39_e2e_regression_and_golden_master_seal import (
    run_phase_g39_cycle,
)


class TestPhaseG39E2ERegressionAndGoldenMaster(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g39_01_17_module_regression_matrix_and_golden_master_hub(self) -> None:
        manifest = run_phase_g39_cycle(self.repo_root)
        rm = manifest["regression_matrix"]
        self.assertGreaterEqual(rm["modules_audited"], 17)
        self.assertTrue(rm["all_passed_28_of_28"])
        self.assertGreaterEqual(rm["total_qa_checks_executed"], 476)

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], hub["qa_total"])
        self.assertGreaterEqual(hub["qa_passed"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
