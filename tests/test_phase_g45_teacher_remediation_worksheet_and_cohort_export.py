"""Unit tests for Phase G45: Offline Teacher Misconception Remediation Worksheet Generator & Hub."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g45_teacher_remediation_worksheet_and_cohort_export import (
    run_phase_g45_cycle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG45RemediationWorksheet(unittest.TestCase):
    def test_g45_generates_bilingual_remediation_worksheets_and_certifies_hub(self) -> None:
        manifest = run_phase_g45_cycle(REPO_ROOT)
        ws = manifest["remediation_worksheets"]
        self.assertEqual(ws["total_worksheets"], 3)
        self.assertTrue((REPO_ROOT / ws["rel_path"]).exists())

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], 28)
        self.assertEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
