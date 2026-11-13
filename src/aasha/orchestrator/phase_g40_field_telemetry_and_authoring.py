"""Phase G40: Continuous Field Telemetry Sentinel & Teacher Authoring Template Pack."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_field_telemetry_sentinel(db_path: Path, report_path: Path) -> dict[str, Any]:
    """Audit offline SQLite centre database for coin conservation, PIN checks, and mastery drop-offs."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        balances = conn.execute("SELECT student_id, balance, lifetime_earned FROM token_balances").fetchall()
        txs = conn.execute("SELECT student_id, SUM(delta) AS net_delta FROM token_transactions GROUP BY student_id").fetchall()
        unverified = conn.execute("SELECT COUNT(*) AS cnt FROM redemptions WHERE staff_pin_verified != 1").fetchone()["cnt"]
        hotspots = conn.execute(
            """
            SELECT chapter_id, COALESCE(node_id, 'general') AS node_id,
                   COUNT(*) AS fail_count, ROUND(AVG(score), 1) AS avg_score
            FROM mastery_events
            WHERE passed = 0 OR score < 60
            GROUP BY chapter_id, COALESCE(node_id, 'general')
            ORDER BY fail_count DESC
            """
        ).fetchall()
    finally:
        conn.close()

    tx_map = {row["student_id"]: int(row["net_delta"] or 0) for row in txs}
    conservation_drifts = []
    for row in balances:
        sid = row["student_id"]
        bal = int(row["balance"] or 0)
        expected = tx_map.get(sid, 0)
        if bal != expected:
            conservation_drifts.append({"student_id": sid, "balance": bal, "tx_net": expected})

    report = {
        "schema_version": "1.0.0",
        "phase": "G40_CONTINUOUS_FIELD_TELEMETRY_SENTINEL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "students_audited": len(balances),
        "coin_conservation_ok": len(conservation_drifts) == 0,
        "conservation_drifts": conservation_drifts,
        "unverified_redemptions": int(unverified),
        "misconception_hotspots": [dict(r) for r in hotspots],
        "status": "HEALTHY" if (len(conservation_drifts) == 0 and unverified == 0) else "ALERT",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def build_teacher_authoring_template_pack(output_path: Path) -> dict[str, Any]:
    """Generate bilingual NCVET/PSSCIVE + STEM offline teacher authoring template."""
    template = {
        "schema_version": "1.0.0",
        "template_id": "aasha.teacher.authoring.v1",
        "curriculum_alignment": ["NCVET-PSSCIVE", "STEM-Foundations"],
        "offline_policy": {
            "max_bundle_bytes": 20971520,
            "zero_external_urls": True,
            "staff_pin_required_for_redemption": True,
        },
        "chapter_metadata": {
            "chapter_id": "NCVET-PSSCIVE-TEMPLATE-01",
            "title_en": "Chapter Title (English)",
            "title_hi": "अध्याय शीर्षक (हिन्दी)",
            "grade_or_nsqf_level": 8,
            "preferred_lang": "hi",
        },
        "lle_vocabulary_entries": [
            {
                "term_en": "moisture",
                "term_hi": "नमी",
                "phonetic_hi": "na-mee",
                "context_en": "Controlled airflow removes surface moisture.",
                "context_hi": "नियंत्रित हवा का प्रवाह सतह की नमी को हटाता है।",
            }
        ],
        "assessments": {
            "warmup": [],
            "deep_dive": [],
            "mastery": [],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return template
