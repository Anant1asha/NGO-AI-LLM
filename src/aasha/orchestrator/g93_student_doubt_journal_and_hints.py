"""
G93: Offline Student Doubt Journal & Zero-Spoiler Socratic Peer Hint Card
Captures student doubts while studying offline at home without internet,
generates zero-spoiler bilingual (Hindi/English) Socratic hints, and stores
entries with SHA-256 verification for teacher follow-up.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def create_offline_doubt_entry_and_socratic_hint(
    student_id: str,
    chapter_id: str,
    doubt_text: str,
    bilingual_wm_terms: List[str] | None = None,
) -> Dict[str, Any]:
    clean_doubt = str(doubt_text or "").strip()
    if not clean_doubt:
        return {"ok": False, "error": "EMPTY_DOUBT_TEXT"}
    terms = bilingual_wm_terms or ["force (बल)", "area (क्षेत्रफल)"]
    hint_en = f"Re-check how {', '.join(terms[:2])} interact in {chapter_id} before picking your answer."
    hint_hi = f"उत्तर चुनने से पहले {chapter_id} में {', '.join(terms[:2])} के संबंध को फिर से देखें।"
    entry = {
        "ok": True,
        "schema_version": "aasha.student.doubt.journal.v1",
        "student_id": student_id,
        "chapter_id": chapter_id,
        "doubt_text": clean_doubt,
        "socratic_hint_en": hint_en,
        "socratic_hint_hi": hint_hi,
        "zero_spoiler": True,
        "offline_only": True,
        "zero_external_urls": "http://" not in clean_doubt.lower() and "https://" not in clean_doubt.lower(),
    }
    entry["doubt_sha256"] = hashlib.sha256(
        json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return entry
