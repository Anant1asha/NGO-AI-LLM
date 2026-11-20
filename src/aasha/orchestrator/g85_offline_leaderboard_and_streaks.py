"""
G85: Offline Student Mastery Leaderboard & Bilingual Streak Badges
Ranks students offline by custom PDF module mastery, compounding bilingual WM tap hits,
and Aasha Coins, assigning deterministic streak badges (BRONZE_LEARNER, SILVER_SCHOLAR,
GOLD_CHALLENGER, BILINGUAL_WM_MASTER) with SHA-256 verification and zero external URLs.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def compute_offline_cohort_leaderboard_and_streaks(mastery_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_student: Dict[str, Dict[str, Any]] = {}
    for row in mastery_rows:
        sid = str(row.get("studentId") or row.get("student_id") or "").strip()
        if not sid:
            continue
        rec = by_student.setdefault(
            sid,
            {
                "studentId": sid,
                "modulesCompleted": 0,
                "totalScore": 0.0,
                "totalWmHits": 0,
                "totalCoins": 0,
            },
        )
        rec["modulesCompleted"] += 1
        rec["totalScore"] += float(row.get("scorePct") or row.get("score_pct") or 0.0)
        rec["totalWmHits"] += int(row.get("wmTapHits") or row.get("wm_tap_hits") or 0)
        rec["totalCoins"] += int(row.get("coinsAwarded") or row.get("coins_awarded") or 0)

    ranked: List[Dict[str, Any]] = []
    for sid, rec in by_student.items():
        mods = max(1, rec["modulesCompleted"])
        avg_score = round(rec["totalScore"] / mods, 1)
        wm_hits = rec["totalWmHits"]
        badges: List[str] = ["BRONZE_LEARNER"]
        if rec["modulesCompleted"] >= 2 or avg_score >= 80.0:
            badges.append("SILVER_SCHOLAR")
        if rec["modulesCompleted"] >= 3 and avg_score >= 90.0:
            badges.append("GOLD_CHALLENGER")
        if wm_hits >= 25:
            badges.append("BILINGUAL_WM_MASTER")
        composite_points = round(avg_score * rec["modulesCompleted"] + wm_hits * 2 + rec["totalCoins"], 1)
        ranked.append({
            "studentId": sid,
            "modulesCompleted": rec["modulesCompleted"],
            "avgScorePct": avg_score,
            "totalWmHits": wm_hits,
            "totalCoins": rec["totalCoins"],
            "compositePoints": composite_points,
            "badges": badges,
        })

    ranked.sort(key=lambda r: (-r["compositePoints"], -r["avgScorePct"], r["studentId"]))
    for idx, item in enumerate(ranked, start=1):
        item["rank"] = idx

    payload = {
        "schema_version": "aasha.offline.leaderboard.v1",
        "student_count": len(ranked),
        "ranked_students": ranked,
        "offline_only": True,
    }
    payload["leaderboard_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return payload
