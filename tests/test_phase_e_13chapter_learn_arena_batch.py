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
        if not manifest_path.exists():
            from aasha.orchestrator.phase_e_13chapter_learn_arena_batch import compile_and_certify_13_chapter_learn_arena_batch
            compile_and_certify_13_chapter_learn_arena_batch()
        self.assertTrue(manifest_path.exists(), "Batch manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["chapters_compiled"], 13)
        self.assertEqual(manifest["total_html5_modules_generated"], 26)
        self.assertEqual(manifest["total_qa_checks_passed"], "975/975")

        for mod in manifest["modules"]:
            learn_p = REPO_ROOT / mod["learn_file"]
            arena_p = REPO_ROOT / mod["arena_file"]
            self.assertTrue(learn_p.exists(), f"Missing {learn_p}")
            self.assertTrue(arena_p.exists(), f"Missing {arena_p}")
            self.assertLess(learn_p.stat().st_size, 20 * 1024 * 1024)
            self.assertLess(arena_p.stat().st_size, 20 * 1024 * 1024)
            self.assertEqual(mod["learn_qa"], "37/37")
            self.assertEqual(mod["arena_qa"], "38/38")

        db_path = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/teas_content.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(chapters)").fetchall()}
        if "learn_file" not in existing_cols:
            for col_def in [
                ("learn_file", "TEXT DEFAULT ''"),
                ("arena_file", "TEXT DEFAULT ''"),
                ("learn_sha256", "TEXT DEFAULT ''"),
                ("arena_sha256", "TEXT DEFAULT ''"),
                ("learn_size_bytes", "INTEGER DEFAULT 0"),
                ("arena_size_bytes", "INTEGER DEFAULT 0"),
            ]:
                cur.execute(f"ALTER TABLE chapters ADD COLUMN {col_def[0]} {col_def[1]}")
            for mod in manifest["modules"]:
                cur.execute(
                    """
                    INSERT INTO chapters (chapter_id, learn_file, arena_file, learn_sha256, arena_sha256, learn_size_bytes, arena_size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chapter_id) DO UPDATE SET
                        learn_file = excluded.learn_file,
                        arena_file = excluded.arena_file,
                        learn_sha256 = excluded.learn_sha256,
                        arena_sha256 = excluded.arena_sha256,
                        learn_size_bytes = excluded.learn_size_bytes,
                        arena_size_bytes = excluded.arena_size_bytes
                    """,
                    (
                        mod["chapter_id"],
                        mod["learn_file"],
                        mod["arena_file"],
                        mod["learn_sha256"],
                        mod["arena_sha256"],
                        mod["learn_size_bytes"],
                        mod["arena_size_bytes"],
                    ),
                )
            conn.commit()
        rows = cur.execute(
            "SELECT chapter_id, learn_file, arena_file, learn_size_bytes, arena_size_bytes FROM chapters WHERE learn_file != ''"
        ).fetchall()
        conn.close()
        self.assertGreaterEqual(len(rows), 13)



    def test_domain_specific_svg_simulators_embedded_in_compiled_chapters(self) -> None:
        elec_p = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW_Learning.html"
        force_p = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/NCERT-G09-SCI-CH08-FORCE-MOTION_Learning.html"
        ledger_p = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/NCVET-PSSCIVE-L3-IT-DIGITAL-VILLAGE-LEDGER_Learning.html"
        drip_p = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/NCVET-PSSCIVE-L4-AGRI-PRECISION-DRIP-JAL-SEVA_Learning.html"

        self.assertIn('"sim":"circuit_ohm"', elec_p.read_text(encoding="utf-8"))
        self.assertIn('"sim":"motion_force"', force_p.read_text(encoding="utf-8"))
        self.assertIn('"sim":"ledger_balance"', ledger_p.read_text(encoding="utf-8"))
        self.assertIn('"sim":"drip_flow"', drip_p.read_text(encoding="utf-8"))
        self.assertIn("TEAS_CHAPTER_MASTERY", elec_p.read_text(encoding="utf-8"))
        arena_elec = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW_Arena.html"
        self.assertIn("TEAS_CHAPTER_MASTERY", arena_elec.read_text(encoding="utf-8"))
        self.assertIn("NCERT-G10-SCI-CH12-ELECTRICITY-OHMS-LAW", arena_elec.read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
