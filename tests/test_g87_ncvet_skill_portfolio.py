import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g87_ncvet_skill_portfolio_exporter import (  # noqa: E402
    export_offline_ncvet_skill_portfolio,
)


class TestG87NcvetSkillPortfolio(unittest.TestCase):
    def test_exports_nsqf_apprenticeship_portfolio_offline(self):
        rows = [
            {"chapterId": "NCVET-G09-SOLAR-01", "scorePct": 92, "wmTapHits": 25},
            {"chapterId": "NCVET-G09-PLUMB-01", "scorePct": 88, "wmTapHits": 20},
        ]
        res = export_offline_ncvet_skill_portfolio("STU-NCVET-01", rows)
        self.assertTrue(res["ok"])
        self.assertEqual(res["readiness_status"], "APPRENTICE_READY")
        self.assertEqual(res["modules_certified"], 2)
        self.assertGreater(res["nsqf_credits_earned"], 3.0)
        self.assertTrue(res["zero_external_urls"])
        self.assertGreater(len(res["portfolio_export_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
