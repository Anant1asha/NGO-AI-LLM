"""
G92: Offline Teacher Copilot Lesson Prep from Custom PDF
Uses IngestAgent to extract text from any teacher-uploaded chapter PDF and
synthesizes a 30-minute bilingual (Hindi/English) classroom lesson prep plan
with zero external URLs and SHA-256 verification.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def generate_offline_lesson_prep_from_pdf(
    repo_root: Path,
    pdf_path: Path,
    subject: str = "science",
    grade: int = 8,
) -> Dict[str, Any]:
    pipeline_src = repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "src"
    if str(pipeline_src) not in sys.path:
        sys.path.insert(0, str(pipeline_src))
    from aasha.agents.ingest_agent import IngestAgent

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        IngestAgent().run(work_dir, {"pdf_path": str(pdf_path)})
        raw_extract = json.loads((work_dir / "raw_extract.json").read_text(encoding="utf-8"))

    body_text = " ".join(p.get("text", "") for p in raw_extract.get("pages", [])).strip()
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", body_text)]
    key_terms: List[str] = []
    for w in words:
        if w not in key_terms:
            key_terms.append(w)
        if len(key_terms) >= 8:
            break

    chapter_id = re.sub(r"[^A-Za-z0-9_-]+", "_", pdf_path.stem).upper()
    plan = {
        "ok": True,
        "schema_version": "aasha.teacher.lesson.prep.v1",
        "chapter_id": chapter_id,
        "subject": subject.lower(),
        "grade": int(grade),
        "duration_minutes": 30,
        "segments": [
            {"minute": "0-5", "title": "Warm-Up Hook / प्रारंभिक चर्चा", "prompt": f"Ask students a real-world question on {pdf_path.stem.replace('_', ' ')}."},
            {"minute": "5-18", "title": "Core Concept & Bilingual WM / मुख्य अवधारणा", "terms": key_terms},
            {"minute": "18-26", "title": "Hands-On Activity / प्रायोगिक गतिविधि", "prompt": "Pair students to test the concept offline using classroom materials."},
            {"minute": "26-30", "title": "Exit Ticket / त्वरित जाँच", "prompt": "Complete 2 quick bilingual MCQs in Student PWA."},
        ],
        "key_terms": key_terms,
        "offline_only": True,
        "zero_external_urls": "http://" not in body_text.lower() and "https://" not in body_text.lower(),
    }
    plan["lesson_prep_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return plan
