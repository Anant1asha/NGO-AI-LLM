import unittest
from pathlib import Path

from src.aasha.orchestrator.g70_multi_genre_chapter_compiler import (
    compile_g70_multi_genre_chapter_pack,
)


class TestG70MultiGenreChapterCompiler(unittest.TestCase):
    def test_compile_five_distinct_multi_genre_60fps_child_html_modules(self):
        repo_root = Path(__file__).resolve().parents[1]
        res = compile_g70_multi_genre_chapter_pack(repo_root)
        self.assertTrue(res["ok"])
        self.assertEqual(res["compiled_count"], 5)
        self.assertEqual(res["distinct_themes_count"], 5)
        self.assertTrue(res["all_under_20mib_child_cap"])
        self.assertTrue(res["all_zero_external_urls"])
        for mod in res["modules"]:
            self.assertGreaterEqual(mod["disbursed_wm_count"], 1129)
            self.assertLessEqual(mod["size_bytes"], 20_971_520)
            self.assertTrue(mod["zero_external_urls"])


if __name__ == "__main__":
    unittest.main()
