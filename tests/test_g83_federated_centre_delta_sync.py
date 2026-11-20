import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g83_federated_centre_delta_sync import (  # noqa: E402
    merge_federated_centre_deltas,
)


class TestG83FederatedCentreDeltaSync(unittest.TestCase):
    def test_crdt_high_water_mark_merge_across_centres(self):
        bundles = [
            {
                "centerId": "CENTER-UP-GN-01",
                "lamportEpoch": 10,
                "modules": [{"chapter_id": "SCI_CH08", "role": "learn", "size_bytes": 180000}],
                "customPdfMastery": [
                    {"studentId": "STU-1", "jobId": "J1", "chapterId": "SCI_CH08", "scorePct": 78, "wmTapHits": 15},
                ],
            },
            {
                "centerId": "CENTER-UP-LKO-02",
                "lamportEpoch": 14,
                "modules": [{"chapter_id": "SCI_CH08", "role": "learn", "size_bytes": 180000}],
                "customPdfMastery": [
                    {"studentId": "STU-1", "jobId": "J1", "chapterId": "SCI_CH08", "scorePct": 94, "wmTapHits": 28},
                    {"studentId": "STU-2", "jobId": "J2", "chapterId": "MATH_CH07", "scorePct": 86, "wmTapHits": 20},
                ],
            },
        ]
        res = merge_federated_centre_deltas(bundles)
        self.assertTrue(res["ok"])
        self.assertEqual(res["lamport_epoch"], 15)
        self.assertEqual(res["mastery_record_count"], 2)
        self.assertEqual(res["duplicate_records_skipped"], 1)
        self.assertTrue(res["within_20mib_child_cap"])
        stu1 = [r for r in res["merged_mastery"] if r["studentId"] == "STU-1"][0]
        self.assertEqual(stu1["scorePct"], 94.0)
        self.assertEqual(stu1["wmTapHits"], 28)

    def test_rejects_oversized_child_html(self):
        res = merge_federated_centre_deltas([
            {"centerId": "CENTER-BAD", "modules": [{"chapter_id": "BIG", "size_bytes": 20971521}]}
        ])
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "CHILD_HTML_EXCEEDS_20MIB_CAP")


if __name__ == "__main__":
    unittest.main()
