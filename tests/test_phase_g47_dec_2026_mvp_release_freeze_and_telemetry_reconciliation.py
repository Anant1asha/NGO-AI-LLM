"""Unit tests for Phase G47: Dec 2026 MVP Release Freeze & Full Telemetry Reconciliation."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g47_dec_2026_mvp_release_freeze_and_telemetry_reconciliation import (
    run_phase_g47_cycle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG47ReleaseFreeze(unittest.TestCase):
    def test_g47_release_freeze_audits_23_modules_and_certifies_hub(self) -> None:
        manifest = run_phase_g47_cycle(REPO_ROOT)
        audit = manifest["release_freeze_audit"]
        self.assertEqual(audit["modules_audited"], 23)
        self.assertTrue(audit["all_passed_28_of_28"])
        self.assertTrue(audit["combined_under_20mib"])
        self.assertEqual(audit["sqlite_catalogue"]["chapters_count"], 13)
        self.assertGreaterEqual(audit["sqlite_catalogue"]["vocabulary_rows_count"], 1190)

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], 28)
        self.assertEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
