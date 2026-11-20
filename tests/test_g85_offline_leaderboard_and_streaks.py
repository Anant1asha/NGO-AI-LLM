import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g85_offline_leaderboard_and_streaks import (  # noqa: E402
    compute_offline_cohort_leaderboard_and_streaks,
)


class TestG85OfflineLeaderboardAndStreaks(unittest.TestCase):
    def test_ranks_students_and_awards_bilingual_wm_badges(self):
        rows = [
            {"studentId": "STU-A", "scorePct": 95, "wmTapHits": 15, "coinsAwarded": 15},
            {"studentId": "STU-A", "scorePct": 92, "wmTapHits": 15, "coinsAwarded": 15},
            {"studentId": "STU-A", "scorePct": 90, "wmTapHits": 10, "coinsAwarded": 15},
            {"studentId": "STU-B", "scorePct": 85, "wmTapHits": 10, "coinsAwarded": 15},
        ]
        res = compute_offline_cohort_leaderboard_and_streaks(rows)
        self.assertTrue(res["offline_only"])
        self.assertEqual(res["student_count"], 2)
        top = res["ranked_students"][0]
        self.assertEqual(top["studentId"], "STU-A")
        self.assertEqual(top["rank"], 1)
        self.assertIn("GOLD_CHALLENGER", top["badges"])
        self.assertIn("BILINGUAL_WM_MASTER", top["badges"])
        self.assertGreater(len(res["leaderboard_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
