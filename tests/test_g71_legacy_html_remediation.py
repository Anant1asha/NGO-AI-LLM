import unittest
from pathlib import Path

from src.aasha.orchestrator.g71_legacy_html_remediation import (
    remediate_legacy_output_html_modules,
)


class TestG71LegacyHtmlRemediation(unittest.TestCase):
    def test_all_output_html_modules_have_zero_ext_urls_and_high_wm(self):
        repo_root = Path(__file__).resolve().parents[1]
        res = remediate_legacy_output_html_modules(repo_root)
        self.assertTrue(res["ok"], f"Remediation failed: {res}")
        self.assertEqual(res["remaining_ext_url_files"], 0)
        self.assertEqual(res["remaining_low_wm_files"], 0)
        self.assertEqual(len(res["oversized_files"]), 0)


if __name__ == "__main__":
    unittest.main()
