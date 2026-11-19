import unittest
from pathlib import Path

from src.aasha.orchestrator.g72_phase_e_26_chapter_recompiler import (
    recompile_26_phase_e_modules,
)


class TestG72PhaseE26ChapterRecompiler(unittest.TestCase):
    def test_recompile_all_26_modules_across_5_genres_under_20mib(self):
        repo_root = Path(__file__).resolve().parents[1]
        res = recompile_26_phase_e_modules(repo_root)
        self.assertTrue(res["ok"])
        self.assertEqual(res["compiled_count"], 26)
        self.assertEqual(res["distinct_themes_count"], 5)
        self.assertTrue(res["all_under_20mib_child_cap"])
        self.assertTrue(res["all_zero_external_urls"])


if __name__ == "__main__":
    unittest.main()
