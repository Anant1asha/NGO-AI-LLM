"""Unit tests for Phase W6 Independent System Certification & LLE Quality Audit."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_w6_independent_certification import (
    run_w6_independent_certification,
)


class TestPhaseW6IndependentCertification(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_w6_01_independent_certification_all_4_priorities(self) -> None:
        rep = run_w6_independent_certification(self.repo_root)

        p1 = rep["priority_1_w1_w5_verification"]
        self.assertEqual(p1["cached_assets_sha256_verified"], p1["cached_assets_total"])
        self.assertEqual(p1["assets_mismatched"], [])
        for fn, info in p1["def004_sanitized_replay"].items():
            self.assertTrue(info["zero_alert"], f"alert() still in {fn}")
            self.assertTrue(info["zero_confirm"], f"confirm() still in {fn}")

        p2 = rep["priority_2_lle_quality_audit"]
        self.assertEqual(p2["wm_empty_values"], 0)
        self.assertGreater(p2["wm_with_devanagari"], 1000)

        p3 = rep["priority_3_idempotency_check"]
        self.assertTrue(p3["zero_duplicates_confirmed"])

        p4 = rep["priority_4_qa_replay"]
        for path, qa in p4.items():
            self.assertTrue(qa["passed"], f"QA replay failed for {path}")


if __name__ == "__main__":
    unittest.main()
