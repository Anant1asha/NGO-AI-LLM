import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g93_student_doubt_journal_and_hints import (  # noqa: E402
    create_offline_doubt_entry_and_socratic_hint,
)


class TestG93StudentDoubtJournal(unittest.TestCase):
    def test_creates_zero_spoiler_bilingual_doubt_entry(self):
        res = create_offline_doubt_entry_and_socratic_hint(
            "STU-G93-01",
            "NCERT-G08-SCI-CH08",
            "Why does a sharp knife cut better than a blunt knife?",
            ["pressure (दाब)", "area (क्षेत्रफल)"],
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["zero_spoiler"])
        self.assertTrue(res["offline_only"])
        self.assertTrue(res["zero_external_urls"])
        self.assertIn("pressure", res["socratic_hint_en"])
        self.assertGreater(len(res["doubt_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
