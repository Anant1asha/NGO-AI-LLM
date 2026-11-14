"""Unit & Integration Tests for the 16-Stage Executive Engineering Loop & 3 Engineering Safeguards."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.aasha.orchestrator.sixteen_stage_executive_loop import (
    CANONICAL_16_STAGES,
    EXECUTIVE_ORCHESTRATION_ROSTER,
    REQUIRED_20_REPORT_FIELDS,
    Executive16StageLoopOrchestrator,
    TaskExecutionRequest,
)


class TestSixteenStageExecutiveLoop(unittest.TestCase):
    def test_full_feature_16_stages_and_20_field_report(self) -> None:
        orch = Executive16StageLoopOrchestrator(".")
        rep = orch.execute_16_stage_cycle()

        for field in REQUIRED_20_REPORT_FIELDS:
            self.assertIn(field, rep, f"Missing required report field: {field}")

        self.assertEqual(len(rep["STAGE_STATUS"]), 16)
        self.assertEqual(len(EXECUTIVE_ORCHESTRATION_ROSTER), 9)
        self.assertEqual(rep["CERTIFICATION"]["verdict"], "PASS")
        self.assertEqual(rep["CERTIFICATION"]["task_lifecycle_state"], "COMPLETE")
        self.assertTrue(rep["CERTIFICATION"]["independent_verification_enforced"])

    def test_safeguard_1_docs_only_marks_non_applicable_stages(self) -> None:
        orch = Executive16StageLoopOrchestrator(".")
        req = TaskExecutionRequest(
            objective_id="DOCS-UPDATE-01",
            title="Update README and architecture diagram",
            task_profile="DOCS_ONLY",
        )
        rep = orch.execute_16_stage_cycle(req)
        st = rep["STAGE_STATUS"]
        self.assertEqual(st["STAGE_05_RESEARCH_AND_RESOURCE_DISCOVERY"]["status"], "NOT_APPLICABLE")
        self.assertEqual(st["STAGE_08_INTEGRATE_AND_COMPLETE"]["status"], "NOT_APPLICABLE")
        self.assertEqual(st["STAGE_09_DEBUG_AND_DEFECT_REMEDIATION"]["status"], "NOT_APPLICABLE")
        self.assertEqual(st["STAGE_12_QUALITY_AND_PERFORMANCE_OPTIMIZATION"]["status"], "NOT_APPLICABLE")
        self.assertIn("Documentation-only", st["STAGE_12_QUALITY_AND_PERFORMANCE_OPTIMIZATION"]["reason"])

    def test_safeguard_2_blocks_developer_self_certification(self) -> None:
        orch = Executive16StageLoopOrchestrator(".")
        req = TaskExecutionRequest(
            objective_id="SELF-CERT-ATTEMPT",
            title="Attempt self-certification by builder",
            builder_agent_id="CHIEF_DEVELOPER",
            verifier_agent_id="CHIEF_DEVELOPER",
        )
        with self.assertRaises(PermissionError):
            orch.execute_16_stage_cycle(req)

    def test_safeguard_3_unfinished_feature_stays_in_progress_or_blocked(self) -> None:
        orch = Executive16StageLoopOrchestrator(".")
        # Case A: Tests pass, but integration is incomplete -> IN_PROGRESS / CONDITIONAL
        req_incomplete = TaskExecutionRequest(
            objective_id="PARTIAL-FEATURE-01",
            title="Partially wired feature",
            coding_complete=True,
            integration_complete=False,
            defects_remediated=True,
        )
        rep_inc = orch.execute_16_stage_cycle(req_incomplete)
        self.assertEqual(rep_inc["CERTIFICATION"]["task_lifecycle_state"], "IN_PROGRESS")
        self.assertEqual(rep_inc["CERTIFICATION"]["verdict"], "CONDITIONAL")

        # Case B: Repair attempts > 2 -> BLOCKED / BLOCK
        req_blocked = TaskExecutionRequest(
            objective_id="REPEATED-FAILURE-01",
            title="Unhealed defect after 3 repair attempts",
            repair_attempts_used=3,
        )
        rep_blk = orch.execute_16_stage_cycle(req_blocked)
        self.assertEqual(rep_blk["CERTIFICATION"]["task_lifecycle_state"], "BLOCKED")
        self.assertEqual(rep_blk["CERTIFICATION"]["verdict"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
