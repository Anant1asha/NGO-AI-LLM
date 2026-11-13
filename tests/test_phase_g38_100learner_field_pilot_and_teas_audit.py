"""Unit tests for Phase G38: 100-Learner Field Pilot & Double-Entry TEAS Ledger Audit."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g38_100learner_field_pilot_and_teas_audit import (
    run_phase_g38_cycle,
)


class TestPhaseG38FieldPilotAndTEASAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g38_01_100_learner_pilot_teas_conservation_and_hub_qa(self) -> None:
        manifest = run_phase_g38_cycle(self.repo_root)
        p = manifest["field_pilot_100_learners"]
        self.assertEqual(p["centres_count"], 4)
        self.assertEqual(p["learners_simulated"], 100)
        self.assertEqual(p["total_mastery_events"], 300)
        self.assertTrue(p["double_entry_conserved"])
        self.assertTrue(p["cohort_pack_verified"])

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], hub["qa_total"])
        self.assertGreaterEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
