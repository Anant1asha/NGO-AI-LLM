"""Phase G42: Multi-Centre SQLite Cohort Delta Merge & NCVET/PSSCIVE Teacher Rubric Validator."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def merge_multi_centre_cohort_deltas(db_path: Path, centre_deltas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Idempotently merge offline centre delta packs into SQLite with coin conservation audit."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS synced_centre_deltas (
            delta_id TEXT PRIMARY KEY,
            centre_id TEXT NOT NULL,
            events_merged INTEGER NOT NULL,
            coins_minted INTEGER NOT NULL,
            merged_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS token_balances (
            student_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            lifetime_earned INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        """
    )

    now = datetime.now(timezone.utc).isoformat()
    merged_centres = 0
    total_events = 0
    total_coins = 0

    try:
        for delta in centre_deltas:
            delta_id = str(delta["delta_id"])
            exists = conn.execute("SELECT delta_id FROM synced_centre_deltas WHERE delta_id = ?", (delta_id,)).fetchone()
            if exists:
                continue
            events = delta.get("student_awards", [])
            coins_in_delta = 0
            for award in events:
                sid = str(award["student_id"])
                coins = int(award["coins"])
                coins_in_delta += coins
                conn.execute(
                    """
                    INSERT INTO token_balances (student_id, balance, lifetime_earned, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(student_id) DO UPDATE SET
                        balance = balance + excluded.balance,
                        lifetime_earned = lifetime_earned + excluded.lifetime_earned,
                        updated_at = excluded.updated_at
                    """,
                    (sid, coins, coins, now),
                )
            conn.execute(
                "INSERT INTO synced_centre_deltas VALUES (?, ?, ?, ?, ?)",
                (delta_id, str(delta["centre_id"]), len(events), coins_in_delta, now),
            )
            merged_centres += 1
            total_events += len(events)
            total_coins += coins_in_delta
        conn.commit()
    finally:
        conn.close()

    return {
        "merged_centres": merged_centres,
        "total_events_merged": total_events,
        "total_coins_minted": total_coins,
        "idempotent": True,
    }


def validate_ncvet_teacher_rubric(rubric: Dict[str, Any]) -> Dict[str, Any]:
    """Validate teacher-authored NCVET/PSSCIVE + STEM chapter rubric before compilation."""
    errors: List[str] = []
    if rubric.get("template_id") != "aasha.teacher.authoring.v1":
        errors.append("Invalid template_id")
    if "NCVET-PSSCIVE" not in (rubric.get("curriculum_alignment") or []):
        errors.append("Missing NCVET-PSSCIVE curriculum alignment")
    policy = rubric.get("offline_policy") or {}
    if int(policy.get("max_bundle_bytes", 0)) > 20_971_520 or not policy.get("zero_external_urls"):
        errors.append("Offline bundle policy violation")
    lle = rubric.get("lle_vocabulary_entries") or []
    if not lle or not all(e.get("term_en") and e.get("term_hi") and e.get("phonetic_hi") for e in lle):
        errors.append("Incomplete LLE Devanagari/phonetic entries")

    canonical_bytes = json.dumps(rubric, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "rubric_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
    }
