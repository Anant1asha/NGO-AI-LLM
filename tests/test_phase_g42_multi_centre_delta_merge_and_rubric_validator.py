"""Unit tests for Phase G42: Multi-Centre SQLite Cohort Delta Merge & NCVET Teacher Rubric Validator."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g42_multi_centre_delta_merge_and_rubric_validator import (
    merge_multi_centre_cohort_deltas,
    validate_ncvet_teacher_rubric,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG42MultiCentreAndRubric(unittest.TestCase):
    def test_idempotent_multi_centre_delta_merge_and_rubric_validator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "multi_centre.db"
            deltas = [
                {
                    "delta_id": "DELTA-GN-01",
                    "centre_id": "CENTER-UP-GN-01",
                    "student_awards": [{"student_id": "stu_01", "coins": 100}, {"student_id": "stu_02", "coins": 50}],
                },
                {
                    "delta_id": "DELTA-UD-02",
                    "centre_id": "CENTER-RJ-UD-02",
                    "student_awards": [{"student_id": "stu_03", "coins": 100}],
                },
            ]
            first = merge_multi_centre_cohort_deltas(db_path, deltas)
            self.assertEqual(first["merged_centres"], 2)
            self.assertEqual(first["total_coins_minted"], 250)

            # Re-running same deltas must be 100% idempotent (0 duplicate minting)
            second = merge_multi_centre_cohort_deltas(db_path, deltas)
            self.assertEqual(second["merged_centres"], 0)
            self.assertEqual(second["total_coins_minted"], 0)

        tpl_path = REPO_ROOT / "Aasha-AI" / "experience_registry" / "teacher_authoring_template_v1.json"
        rubric = json.loads(tpl_path.read_text(encoding="utf-8"))
        val = validate_ncvet_teacher_rubric(rubric)
        self.assertTrue(val["valid"], f"Rubric validation failed: {val['errors']}")
        self.assertEqual(len(val["rubric_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
