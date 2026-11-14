"""Unit tests for Phase G46: Parent Progress Card & Seva Certificate Signer."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g46_parent_progress_card_and_seva_certificate_signer import (
    run_phase_g46_cycle,
    sign_seva_certificate_and_parent_card,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG46ParentAndSevaCertificate(unittest.TestCase):
    def test_g46_signs_deterministic_seva_certificate_and_certifies_hub(self) -> None:
        c1 = sign_seva_certificate_and_parent_card("stu_01", 3, 150)
        c2 = sign_seva_certificate_and_parent_card("stu_01", 3, 150)
        self.assertEqual(c1["certificate_sha256"], c2["certificate_sha256"])
        self.assertIn("आशा प्रगति", c1["parent_sms_hi"])

        manifest = run_phase_g46_cycle(REPO_ROOT)
        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], 28)
        self.assertEqual(hub["qa_total"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
