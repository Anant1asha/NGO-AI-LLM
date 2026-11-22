"""
G94: Offline Teacher Doubt Resolution & Classroom Broadcast
Aggregates resolved student doubts from the offline doubt journal and publishes
a bilingual (Hindi/English) classroom clarification broadcast with SHA-256
verification and zero external URLs.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def build_offline_teacher_doubt_broadcast(
    chapter_id: str,
    resolved_doubts: List[Dict[str, Any]],
    clarification_en: str,
    clarification_hi: str,
) -> Dict[str, Any]:
    clean_en = str(clarification_en or "").strip()
    clean_hi = str(clarification_hi or "").strip()
    if not clean_en or not clean_hi:
        return {"ok": False, "error": "BILINGUAL_CLARIFICATION_REQUIRED"}

    broadcast = {
        "ok": True,
        "schema_version": "aasha.teacher.doubt.broadcast.v1",
        "chapter_id": chapter_id,
        "doubts_resolved_count": len(resolved_doubts),
        "clarification_en": clean_en,
        "clarification_hi": clean_hi,
        "offline_only": True,
        "zero_external_urls": "http://" not in clean_en.lower() and "https://" not in clean_en.lower(),
    }
    broadcast["broadcast_sha256"] = hashlib.sha256(
        json.dumps(broadcast, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return broadcast
