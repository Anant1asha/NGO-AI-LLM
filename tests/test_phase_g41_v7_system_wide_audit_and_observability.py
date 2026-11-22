"""Unit tests for Phase G41 (Waves W1-W2 of MASTER_PROMPT_v7: 27/27 Deliverables & Observability Hub)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g41_v7_system_wide_audit_and_observability import (
    run_phase_g41_cycle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG41V7SystemWideAudit(unittest.TestCase):
    def test_g41_generates_all_7_remaining_v7_deliverables_and_28_28_qa_hub(self) -> None:
        manifest = run_phase_g41_cycle(REPO_ROOT)
        self.assertEqual(manifest["phase"], "G41_V7_SYSTEM_WIDE_AUDIT_AND_OBSERVABILITY")
        self.assertEqual(len(manifest["v7_deliverables_generated"]), 7)
        for fname in manifest["v7_deliverables_generated"]:
            fpath = REPO_ROOT / fname
            self.assertTrue(fpath.exists(), f"Missing {fname}")
            data = json.loads(fpath.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "7.0.0")

        hub = manifest["html5_hub"]
        self.assertEqual(hub["swarm_state"], "CERTIFIED_CHECKPOINT")
        self.assertEqual(hub["qa_passed"], hub["qa_total"])
        self.assertGreaterEqual(hub["qa_passed"], 28)
        self.assertTrue(hub["under_20mib"])


if __name__ == "__main__":
    unittest.main()
