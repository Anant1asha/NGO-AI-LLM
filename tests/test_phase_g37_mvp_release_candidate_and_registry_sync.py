"""Unit tests for Phase G37: Experience Registry Sync, DOM Smoke Gate & MVP Release Candidate."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g37_mvp_release_candidate_and_registry_sync import (
    run_phase_g37_cycle,
)


class TestPhaseG37MVPReleaseCandidateAndRegistrySync(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g37_01_registry_13_chapters_21_avr_and_rc_hub_certified(self) -> None:
        manifest = run_phase_g37_cycle(self.repo_root)
        reg = manifest["experience_registry_sync"]
        self.assertEqual(reg["certified_chapters_count"], 13)
        self.assertTrue(reg["all_13_chapters_qa_passed"])
        self.assertEqual(reg["certified_avr_count"], 21)

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], hub["qa_total"])
        self.assertGreaterEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
