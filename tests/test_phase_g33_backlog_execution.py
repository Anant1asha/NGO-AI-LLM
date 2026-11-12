"""Unit tests for Phase G33 (BACKLOG-01 Node-VM LLE, BACKLOG-02 G3 Fractions Upgrade) & DEF-005 Reconciler."""

import json
import unittest
from pathlib import Path

from scripts.reconcile_windows_mirror import reconcile_mirror_into_sqlite
from src.aasha.orchestrator.phase_g33_backlog_execution_and_chromium_qa import (
    run_phase_g33_cycle,
)


class TestPhaseG33BacklogAndDef005(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g33_01_node_vm_lle_harvest_and_g3_fractions_upgrade(self) -> None:
        manifest = run_phase_g33_cycle(self.repo_root)
        b1 = manifest["backlog_01_node_vm_lle"]
        b2 = manifest["backlog_02_g3_fractions_upgrade"]

        self.assertGreater(b1["wm_count"], 1100)
        self.assertGreaterEqual(b1["conn_count"], 85)
        self.assertEqual(b2["swarm_final_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(b2["qa_checks_passed"], b2["qa_checks_total"])
        self.assertTrue(b2["under_20mib_ceiling"])

    def test_g33_02_def005_idempotent_windows_mirror_reconcile(self) -> None:
        res = reconcile_mirror_into_sqlite(self.repo_root)
        self.assertEqual(res["status"], "RECONCILED_IDEMPOTENTLY")
        self.assertIn("lle_vocabulary", res["reconciled_tables"])


if __name__ == "__main__":
    unittest.main()
