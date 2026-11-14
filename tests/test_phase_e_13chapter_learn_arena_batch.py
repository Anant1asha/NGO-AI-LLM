"""Unit & Integration Test for the 13-Chapter Canonical Learn & Arena Batch."""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseE13ChapterLearnArenaBatch(unittest.TestCase):
    def test_26_learn_and_arena_modules_and_sqlite_catalogue(self) -> None:
        manifest_path = REPO_ROOT / "PHASE_E_13CHAPTER_LEARN_ARENA_BATCH_MANIFEST.json"
        self.assertTrue(manifest_path.exists(), "Batch manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["chapters_compiled"], 13)
        self.assertEqual(manifest["total_html5_modules_generated"], 26)
        self.assertEqual(manifest["total_qa_checks_passed"], "871/871")

        for mod in manifest["modules"]:
            learn_p = REPO_ROOT / mod["learn_file"]
            arena_p = REPO_ROOT / mod["arena_file"]
            self.assertTrue(learn_p.exists(), f"Missing {learn_p}")
            self.assertTrue(arena_p.exists(), f"Missing {arena_p}")
            self.assertLess(learn_p.stat().st_size, 20 * 1024 * 1024)
            self.assertLess(arena_p.stat().st_size, 20 * 1024 * 1024)
            self.assertEqual(mod["learn_qa"], "33/33")
            self.assertEqual(mod["arena_qa"], "34/34")

        db_path = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/teas_content.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT chapter_id, learn_file, arena_file, learn_size_bytes, arena_size_bytes FROM chapters WHERE learn_file != ''"
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 13)


if __name__ == "__main__":
    unittest.main()
