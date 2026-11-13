"""Tests for Phase G40 Field Telemetry Sentinel & Teacher Authoring Template Pack."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g40_field_telemetry_and_authoring import (
    build_teacher_authoring_template_pack,
    run_field_telemetry_sentinel,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPhaseG40(unittest.TestCase):
    def test_sentinel_and_authoring_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "aasha_local.db"
            conn = sqlite3.connect(str(db_path))
            conn.executescript(
                """
                CREATE TABLE token_balances (student_id TEXT PRIMARY KEY, balance INTEGER, lifetime_earned INTEGER, updated_at TEXT);
                CREATE TABLE token_transactions (tx_id TEXT PRIMARY KEY, student_id TEXT, delta INTEGER, reason TEXT, chapter_id TEXT, created_at TEXT);
                CREATE TABLE redemptions (redemption_id TEXT PRIMARY KEY, student_id TEXT, item_id TEXT, cost_coins INTEGER, staff_pin_verified INTEGER, redeemed_at TEXT);
                CREATE TABLE mastery_events (id TEXT PRIMARY KEY, student_id TEXT, chapter_id TEXT, node_id TEXT, score INTEGER, passed INTEGER, recorded_at TEXT);
                INSERT INTO token_balances VALUES ('stu_1', 50, 100, '2026-11-13T00:00:00Z');
                INSERT INTO token_transactions VALUES ('tx_1', 'stu_1', 100, 'chapter_mastery_gold', 'ch1', '2026-11-13T00:00:00Z');
                INSERT INTO token_transactions VALUES ('tx_2', 'stu_1', -50, 'redeem:pencil', NULL, '2026-11-13T00:01:00Z');
                INSERT INTO redemptions VALUES ('red_1', 'stu_1', 'item_pencil_pack', 50, 1, '2026-11-13T00:01:00Z');
                INSERT INTO mastery_events VALUES ('ev_1', 'stu_1', 'ch2', 'node_ratio', 40, 0, '2026-11-13T00:02:00Z');
                """
            )
            conn.close()

            report = run_field_telemetry_sentinel(db_path, tmp_path / "sentinel_report.json")
            self.assertEqual(report["status"], "HEALTHY")
            self.assertTrue(report["coin_conservation_ok"])
            self.assertEqual(report["unverified_redemptions"], 0)
            self.assertEqual(len(report["misconception_hotspots"]), 1)

        tpl_path = REPO_ROOT / "Aasha-AI" / "experience_registry" / "teacher_authoring_template_v1.json"
        tpl = build_teacher_authoring_template_pack(tpl_path)
        self.assertEqual(tpl["template_id"], "aasha.teacher.authoring.v1")
        self.assertTrue(tpl["offline_policy"]["zero_external_urls"])
        self.assertTrue(tpl_path.exists())
        loaded = json.loads(tpl_path.read_text(encoding="utf-8"))
        self.assertIn("NCVET-PSSCIVE", loaded["curriculum_alignment"])


if __name__ == "__main__":
    unittest.main()
