"""
Unit tests for W0 Live Reconciliation, Free Windows-Offline Mirror, and Hydrogen<->Argon `/swarm` Auto-Switch Router.
"""

import json
import unittest
from pathlib import Path

from src.aasha.orchestrator.hydrogen_argon_swarm_router import (
    HydrogenArgonSwarmRouter,
    SpecialistFamily,
    SwarmRole,
    WorkerResult,
    WorkerTaskContract,
)
from src.aasha.orchestrator.w0_live_reconciliation import run_w0_live_reconciliation


class TestHydrogenArgonSwarmRouterAndW0(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_01_w0_live_reconciliation_and_free_windows_mirror(self) -> None:
        summary = run_w0_live_reconciliation(self.repo_root)
        self.assertEqual(summary["status"], "LIVE_VERIFIED")
        self.assertGreaterEqual(summary["manifests_reconciled"], 29)
        self.assertGreaterEqual(summary["test_suites_discovered"], 50)
        for fname in (
            "LIVE_ACCESS_AND_PLANE_STATUS.json",
            "REPOSITORY_COMMIT_AND_DIRTY_STATE.json",
            "G29_G30_STATE_RECONCILIATION.json",
            "AASHA_HISTORICAL_TASK_LEDGER.json",
            "aasha_operational_mirror.json",
        ):
            p = self.repo_root / fname
            self.assertTrue(p.is_file(), f"Missing W0 deliverable: {fname}")
        mirror = json.loads((self.repo_root / "aasha_operational_mirror.json").read_text(encoding="utf-8"))
        self.assertEqual(mirror["cost_usd"], 0.0)

    def test_02_swarm_auto_switch_hydrogen_argon_independent_qa(self) -> None:
        router = HydrogenArgonSwarmRouter(self.repo_root)
        mode = router.parse_command_mode("/plan /swarm /grill-me")
        self.assertTrue(mode["auto_switch_enabled"])
        self.assertEqual(mode["entry_role"], SwarmRole.HYDROGEN_ORCHESTRATE.value)

        contract = WorkerTaskContract(
            task_id="TASK-SWARM-TEST-01",
            goal="Verify isolated write & independent QA auto-switch",
            specialist=SpecialistFamily.OFFLINE_HTML5,
            allowed_paths=["AASHA_Visual_Mass_Harvest_Phase3/test_out.html"],
            acceptance_criteria=["0 QA violations"],
        )

        def argon_exec(c: WorkerTaskContract) -> WorkerResult:
            return WorkerResult(
                task_id=c.task_id,
                worker_id="argon_html5_worker",
                status="PASS",
                files_changed=["AASHA_Visual_Mass_Harvest_Phase3/test_out.html"],
                raw_evidence={"bytes": 1024},
            )

        def hydrogen_qa(c: WorkerTaskContract, res: WorkerResult) -> WorkerResult:
            return WorkerResult(
                task_id=c.task_id,
                worker_id="hydrogen_independent_qa_harness",
                status="PASS",
                files_changed=[],
                raw_evidence={"qa_passed": True},
            )

        out = router.run_bounded_cycle(contract, argon_exec, hydrogen_qa)
        self.assertEqual(out["final_state"], SwarmRole.CERTIFIED_CHECKPOINT.value)
        states = [t["to"] for t in out["transitions"]]
        self.assertEqual(
            states,
            [
                SwarmRole.ARGON_EXECUTE.value,
                SwarmRole.HYDROGEN_INDEPENDENT_QA.value,
                SwarmRole.CERTIFIED_CHECKPOINT.value,
            ],
        )

    def test_03_max_two_repairs_circuit_breaker_blocks_for_hil(self) -> None:
        router = HydrogenArgonSwarmRouter(self.repo_root)
        contract = WorkerTaskContract(
            task_id="TASK-SWARM-REPAIR-CAP",
            goal="Enforce max 2 repairs per defect class",
            specialist=SpecialistFamily.LLE_DICTIONARY,
            allowed_paths=["config/defaults.json"],
            acceptance_criteria=["60/40 EN/HI balance"],
        )

        def argon_exec(c: WorkerTaskContract) -> WorkerResult:
            return WorkerResult(c.task_id, "argon_lle_worker", "PASS", ["config/defaults.json"], {})

        def always_fail_qa(c: WorkerTaskContract, res: WorkerResult) -> WorkerResult:
            return WorkerResult(
                c.task_id,
                "hydrogen_independent_qa_harness",
                "FAIL",
                [],
                {"error": "LLE ratio drift"},
                defect_class="LLE_RATIO_DRIFT",
            )

        out = router.run_bounded_cycle(contract, argon_exec, always_fail_qa)
        self.assertEqual(out["final_state"], SwarmRole.BLOCKED_HIL.value)
        self.assertEqual(out["repair_attempts"]["LLE_RATIO_DRIFT"], 3)  # 2 repairs attempted, 3rd triggers BLOCKED_HIL

    def test_04_write_scope_contention_rejected(self) -> None:
        router = HydrogenArgonSwarmRouter(self.repo_root)
        c1 = WorkerTaskContract("T1", "g1", SpecialistFamily.BACKEND_SQLITE, ["aasha_operational.db"], ["ok"])
        c2 = WorkerTaskContract("T2", "g2", SpecialistFamily.OFFLINE_HTML5, ["aasha_operational.db"], ["ok"])
        with self.assertRaises(ValueError):
            router.validate_isolated_contracts([c1, c2])


if __name__ == "__main__":
    unittest.main()
