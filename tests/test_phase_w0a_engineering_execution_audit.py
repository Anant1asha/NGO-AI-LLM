"""Unit tests for Phase W0A Engineering Foundation & Code Execution Audit (MASTER_PROMPT_v7)."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_w0a_engineering_execution_audit import (
    run_w0a_engineering_capability_audit,
)


class TestPhaseW0AEngineeringExecutionAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_w0a_01_generates_all_4_v7_deliverables(self) -> None:
        res = run_w0a_engineering_capability_audit(self.repo_root)
        self.assertEqual(res["status"], "LIVE_VERIFIED")
        self.assertTrue(res["visual_contract_passed"])
        self.assertTrue(res["sec001_passed"])
        for fn in (
            "AASHA_ENGINEERING_EXECUTION_CAPABILITY_AUDIT.md",
            "AASHA_CODE_BUILD_TEST_DEBUG_PIPELINE_AUDIT.md",
            "AASHA_IMPLEMENTATION_VS_REPORTING_GAP_REGISTER.json",
            "AASHA_ENGINEERING_LOOP_REFERENCE_RUN.json",
        ):
            self.assertTrue((self.repo_root / fn).is_file(), f"Missing v7 deliverable {fn}")


if __name__ == "__main__":
    unittest.main()
