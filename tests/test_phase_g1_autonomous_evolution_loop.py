"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G1:
Continuous Autonomous Post-MVP Production Evolution & Live Cohort Telemetry Loop.
"""

import json
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g_autonomous_evolution_loop import (
    AutonomousCurriculumEvolutionEngine,
    LiveCohortTelemetryIngestor,
    MASTERY_REMEDIATION_THRESHOLD,
    NEXT_FOCUS_UNIT_G2,
    execute_chunk_g1_autonomous_evolution_sync,
)


class TestPhaseG1AutonomousEvolutionLoop(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g1_01_zero_pii_telemetry_guard_blocks_student_pii(self) -> None:
        with self.assertRaises(ValueError):
            LiveCohortTelemetryIngestor.validate_zero_pii_telemetry(
                [{"centre_id": "C1", "student_name": "Test Student"}]
            )

    def test_g1_02_canonical_cohort_telemetry_sample_is_pii_free(self) -> None:
        records = LiveCohortTelemetryIngestor.build_canonical_cohort_telemetry_sample()
        self.assertEqual(len(records), 4)
        LiveCohortTelemetryIngestor.validate_zero_pii_telemetry([r.__dict__ for r in records])

    def test_g1_03_evolution_engine_detects_low_mastery_node_and_synthesizes_remedial_patch(self) -> None:
        engine = AutonomousCurriculumEvolutionEngine(self.repo_root)
        records = LiveCohortTelemetryIngestor.build_canonical_cohort_telemetry_sample()
        patches = engine.synthesize_remedial_patches(records, mastery_threshold=MASTERY_REMEDIATION_THRESHOLD)
        self.assertEqual(len(patches), 1)
        patch = patches[0]
        self.assertEqual(patch.node_id, "TLN-02")
        self.assertEqual(patch.misconception_targeted, "DENOMINATOR_ADDITION_MISCONCEPTION")
        self.assertTrue(patch.qa_ten_rules_passed)
        self.assertEqual(patch.english_ratio, 0.60)
        self.assertEqual(patch.hindi_ratio, 0.40)
        self.assertIn("$\\frac{1}{4} + \\frac{2}{4}$", patch.remedial_scaffold_bilingual)

    def test_g1_04_execute_chunk_g1_writes_manifest_and_advances_to_g2(self) -> None:
        summary = execute_chunk_g1_autonomous_evolution_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G1_AUTONOMOUS_EVOLUTION_AND_COHORT_TELEMETRY_VERIFIED",
        )
        self.assertTrue(summary["zero_pii_verified"])
        self.assertEqual(summary["remedial_patches_synthesized_count"], 1)
        self.assertEqual(summary["impact_ledger"]["eco_seva_actions_verified"], 60)
        self.assertEqual(summary["impact_ledger"]["jal_seva_liters_conserved"], 1890)
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G2)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])

        manifest_path = self.repo_root / "PHASE_G_TELEMETRY_EVOLUTION_MANIFEST.json"
        self.assertTrue(manifest_path.is_file())
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["chunk_id"], "G1")
        self.assertEqual(parsed["next_focus_unit"], NEXT_FOCUS_UNIT_G2)


if __name__ == "__main__":
    unittest.main()
