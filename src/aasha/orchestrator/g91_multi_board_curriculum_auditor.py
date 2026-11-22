"""
G91: Production Multi-Board Curriculum Pack Expander & Auditor
Compiles and audits chapter PDFs across NCERT, UPMSP, CBSE, and NCVET boards
through the real 7-Agent PDF->HTML5 Pipeline, enforcing <= 20 MiB per child HTML,
0 external resource URLs, and compounding bilingual WM vocabulary.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from aasha.orchestrator.g77_pdf_job_worker_runner import (
    MAX_CHILD_HTML_BYTES,
    execute_pdf_job_through_7agent_pipeline,
)

EXTERNAL_RESOURCE_RE = re.compile(
    r'(?:src|href|action|data-src)\s*=\s*["\']https?://|fetch\(\s*["\']https?://|url\(\s*["\']?https?://',
    re.IGNORECASE,
)


def compile_and_audit_multi_board_pack(
    repo_root: Path,
    board_specs: List[Dict[str, Any]],
    output_dir: Path,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    boards_covered: List[str] = []
    entries: List[Dict[str, Any]] = []
    max_child_bytes = 0
    total_ext_urls = 0

    for spec in board_specs:
        board = str(spec.get("board", "NCERT")).upper()
        if board not in boards_covered:
            boards_covered.append(board)
        job_id = str(spec["job_id"])
        res = execute_pdf_job_through_7agent_pipeline(
            repo_root=repo_root,
            job_id=job_id,
            pdf_path=Path(spec["pdf_path"]),
            subject=str(spec.get("subject", "science")),
            grade=int(spec.get("grade", 8)),
            output_dir=output_dir / job_id,
        )
        for key in ("learn_html_path", "arena_html_path"):
            p = Path(res[key])
            txt = p.read_text(encoding="utf-8", errors="replace")
            total_ext_urls += len(EXTERNAL_RESOURCE_RE.findall(txt))
            sz = p.stat().st_size
            if sz > max_child_bytes:
                max_child_bytes = sz

        entries.append({
            "board": board,
            "job_id": job_id,
            "chapter_id": res["chapter_id"],
            "wm_count": res["wm_count"],
            "qa_checks_passed": res["qa_checks_passed"],
            "within_20mib_child_cap": res["within_20mib_child_cap"],
            "ok": res["ok"],
        })

    audit = {
        "ok": all(e["ok"] for e in entries) and max_child_bytes <= MAX_CHILD_HTML_BYTES and total_ext_urls == 0,
        "schema_version": "aasha.multi.board.audit.v1",
        "boards_covered": sorted(boards_covered),
        "chapters_compiled": len(entries),
        "max_child_html_bytes": max_child_bytes,
        "all_within_20mib_cap": max_child_bytes <= MAX_CHILD_HTML_BYTES,
        "zero_external_urls": total_ext_urls == 0,
        "entries": entries,
    }
    audit["multi_board_audit_sha256"] = hashlib.sha256(
        json.dumps(audit, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return audit
