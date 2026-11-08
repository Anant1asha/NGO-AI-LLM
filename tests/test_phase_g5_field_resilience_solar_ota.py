"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G5:
Autonomous 100-School Multi-District Field Resilience, Solar-Battery Power Governor
& Zero-Downtime A/B Slot OTA Bundle Verifier.
"""

import json
import subprocess
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g5_field_resilience_solar_ota import (
    HundredSchoolMultiDistrictFieldSimulator,
    NEXT_FOCUS_UNIT_G6,
    SolarBatteryPowerGovernor,
    ZeroDowntimeOTABundleVerifier,
    execute_chunk_g5_field_resilience_and_ota_sync,
)


class TestPhaseG5FieldResilienceSolarOTA(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g5_01_solar_battery_power_governor_scales_fps_and_checkpoint_interval(self) -> None:
        full = SolarBatteryPowerGovernor.evaluate_power_policy(85.0, solar_charging_watts=20.0)
        self.assertEqual(full.power_mode, "FULL_PERFORMANCE")
        self.assertEqual(full.target_canvas_fps, 60)

        eco = SolarBatteryPowerGovernor.evaluate_power_policy(25.0, solar_charging_watts=2.0)
        self.assertEqual(eco.power_mode, "ECO_BALANCED_SOLAR")
        self.assertEqual(eco.target_canvas_fps, 30)
        self.assertGreaterEqual(eco.estimated_runtime_extension_pct, 40.0)

        surv = SolarBatteryPowerGovernor.evaluate_power_policy(10.0, solar_charging_watts=0.0)
        self.assertEqual(surv.power_mode, "CRITICAL_SURVIVAL_LOCK")
        self.assertEqual(surv.target_canvas_fps, 15)
        self.assertFalse(surv.p2p_mesh_gossip_enabled)
        self.assertEqual(surv.checkpoint_interval_sec, 5)

    def test_g5_02_zero_downtime_ab_slot_ota_commits_valid_and_rolls_back_corrupted(self) -> None:
        payload = b"VALID_OFFLINE_HTML5_PACK_BYTES"
        manifest = ZeroDowntimeOTABundleVerifier.sign_bundle_payload(payload, "v3.0.0-ota-test")
        ok_res = ZeroDowntimeOTABundleVerifier.verify_and_stage_ab_slot_update(payload, manifest)
        self.assertTrue(ok_res.atomic_switch_committed)
        self.assertFalse(ok_res.rollback_triggered)
        self.assertEqual(ok_res.active_slot, "SLOT_B_NEW_VERIFIED")

        bad_res = ZeroDowntimeOTABundleVerifier.verify_and_stage_ab_slot_update(payload + b"X", manifest)
        self.assertFalse(bad_res.atomic_switch_committed)
        self.assertTrue(bad_res.rollback_triggered)
        self.assertEqual(bad_res.active_slot, "SLOT_A_KNOWN_GOOD")

    def test_g5_03_field_resilience_console_html5_passes_node_run_qa_js(self) -> None:
        summary = execute_chunk_g5_field_resilience_and_ota_sync(self.repo_root)
        html_path = self.repo_root / summary["field_resilience_console_bundle"]["html_rel_path"]
        qa_script = self.repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "qa" / "run_qa.js"
        proc = subprocess.run(
            ["node", str(qa_script), str(html_path)],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        report = json.loads(proc.stdout.strip())
        self.assertTrue(report["passed"], f"run_qa.js failed: {report.get('failures')}")
        self.assertEqual(len(report["failures"]), 0)

    def test_g5_04_execute_chunk_g5_end_to_end_writes_manifest_and_advances_to_g6(self) -> None:
        summary = execute_chunk_g5_field_resilience_and_ota_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G5_100_SCHOOL_SOLAR_GOVERNOR_AND_ZERO_DOWNTIME_OTA_VERIFIED",
        )
        self.assertEqual(summary["field_simulation"]["schools_simulated"], 100)
        self.assertEqual(summary["field_simulation"]["concurrent_student_tablets_simulated"], 5000)
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G6)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])


if __name__ == "__main__":
    unittest.main()
