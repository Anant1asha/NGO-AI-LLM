import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g88_remedial_worksheet_print_qr import (  # noqa: E402
    build_printable_remedial_worksheet_pack,
)


class TestG88RemedialWorksheetPrintQr(unittest.TestCase):
    def test_generates_printable_offline_remedial_worksheet(self):
        rows = [
            {"studentId": "STU-1", "scorePct": 55},
            {"studentId": "STU-2", "scorePct": 92},
        ]
        res = build_printable_remedial_worksheet_pack("NCERT-G08-SCI-CH08", rows)
        self.assertTrue(res["ok"])
        self.assertEqual(res["students_flagged_count"], 1)
        self.assertTrue(res["within_20mib_cap"])
        self.assertTrue(res["zero_external_urls"])
        self.assertIn("@media print", res["printable_html"])
        self.assertGreater(len(res["worksheet_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
