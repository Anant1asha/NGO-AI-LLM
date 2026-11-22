import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g94_teacher_doubt_broadcast import (  # noqa: E402
    build_offline_teacher_doubt_broadcast,
)


class TestG94TeacherDoubtBroadcast(unittest.TestCase):
    def test_builds_bilingual_classroom_broadcast_offline(self):
        res = build_offline_teacher_doubt_broadcast(
            "SCI_CH08",
            [{"studentId": "STU-1", "doubtText": "Why does sharp knife cut better?"}],
            "Smaller contact area produces higher pressure for the same force.",
            "समान बल के लिए कम क्षेत्रफल पर अधिक दाब उत्पन्न होता है।",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["doubts_resolved_count"], 1)
        self.assertTrue(res["offline_only"])
        self.assertTrue(res["zero_external_urls"])
        self.assertGreater(len(res["broadcast_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
