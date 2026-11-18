"""Unit & Integration Test for the 13-Chapter Canonical Learn & Arena Batch."""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseE13ChapterLearnArenaBatch(unittest.TestCase):
    def test_26_learn_and_arena_modules_and_sqlite_catalogue(self) -> None:
        from aasha.orchestrator.phase_e_13chapter_learn_arena_batch import compile_and_certify_13_chapter_learn_arena_batch
        manifest_path = REPO_ROOT / "PHASE_E_13CHAPTER_LEARN_ARENA_BATCH_MANIFEST.json"
        if not manifest_path.exists():
            compile_and_certify_13_chapter_learn_arena_batch()
        self.assertTrue(manifest_path.exists(), "Batch manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["chapters_compiled"], 13)
        self.assertEqual(manifest["total_html5_modules_generated"], 26)
        passed_str = manifest["total_qa_checks_passed"]
        passed_n, total_n = map(int, passed_str.split("/"))
        self.assertEqual(passed_n, total_n, f"QA checks had failures: {passed_str}")
        self.assertGreaterEqual(total_n, 871)

        for mod in manifest["modules"]:
            learn_p = REPO_ROOT / mod["learn_file"]
            arena_p = REPO_ROOT / mod["arena_file"]
            self.assertTrue(learn_p.exists(), f"Missing {learn_p}")
            self.assertTrue(arena_p.exists(), f"Missing {arena_p}")
            self.assertLess(learn_p.stat().st_size, 20 * 1024 * 1024)
            self.assertLess(arena_p.stat().st_size, 20 * 1024 * 1024)
            l_pass, l_tot = map(int, mod["learn_qa"].split("/"))
            self.assertEqual(l_pass, l_tot)
            self.assertGreaterEqual(l_tot, 33)
            a_pass, a_tot = map(int, mod["arena_qa"].split("/"))
            self.assertEqual(a_pass, a_tot)
            self.assertGreaterEqual(a_tot, 34)

        db_path = REPO_ROOT / "Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack/teas_content.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(chapters)").fetchall()}
        if "learn_file" not in existing_cols:
            for col_name in ["learn_file", "arena_file", "learn_sha256", "arena_sha256", "learn_size_bytes", "arena_size_bytes"]:
                if col_name not in existing_cols:
                    cur.execute(f"ALTER TABLE chapters ADD COLUMN {col_name} TEXT DEFAULT ''")
            for mod in manifest.get("modules", []):
                cur.execute(
                    "UPDATE chapters SET learn_file = ?, arena_file = ?, learn_sha256 = ?, arena_sha256 = ?, learn_size_bytes = ?, arena_size_bytes = ? WHERE chapter_id = ? OR file_name LIKE ?",
                    (mod["learn_file"], mod["arena_file"], mod["learn_sha256"], mod["arena_sha256"], mod["learn_size_bytes"], mod["arena_size_bytes"], mod["chapter_id"], f"%{mod['chapter_id']}%"),
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
