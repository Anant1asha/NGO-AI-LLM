"""
G87: Offline NCVET Apprenticeship & Skill Portfolio Exporter
Aggregates student custom PDF vocational mastery and compounding bilingual WM
practice into an NSQF L3-L4 apprenticeship readiness portfolio with SHA-256
verification and zero external URLs.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def export_offline_ncvet_skill_portfolio(
    student_id: str,
    mastery_rows: List[Dict[str, Any]],
    target_trade: str = "Solar Pump Technician (NSQF L3-L4)",
) -> Dict[str, Any]:
    completed = [r for r in mastery_rows if float(r.get("scorePct") or r.get("score_pct") or 0) >= 70.0]
    avg_score = (
        round(sum(float(r.get("scorePct") or r.get("score_pct") or 0) for r in completed) / len(completed), 1)
        if completed
        else 0.0
    )
    total_wm = sum(int(r.get("wmTapHits") or r.get("wm_tap_hits") or 0) for r in mastery_rows)
    nsqf_credits = round(len(completed) * 1.5 + min(total_wm, 100) * 0.02, 2)
    readiness = "APPRENTICE_READY" if len(completed) >= 2 and avg_score >= 80.0 else "TRAINING_IN_PROGRESS"

    portfolio = {
        "ok": True,
        "schema_version": "aasha.ncvet.apprenticeship.export.v1",
        "student_id": student_id,
        "target_trade": target_trade,
        "modules_certified": len(completed),
        "avg_mastery_pct": avg_score,
        "bilingual_wm_taps": total_wm,
        "nsqf_credits_earned": nsqf_credits,
        "readiness_status": readiness,
        "offline_only": True,
        "zero_external_urls": True,
    }
    portfolio["portfolio_export_sha256"] = hashlib.sha256(
        json.dumps(portfolio, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return portfolio
