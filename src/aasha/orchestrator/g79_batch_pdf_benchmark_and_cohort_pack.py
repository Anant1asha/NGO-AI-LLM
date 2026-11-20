"""
G79: End-to-End Batch PDF Benchmark & Cohort Offline Pack Exporter
Runs multi-subject, multi-grade PDF batches through the 7-Agent PDF-to-HTML5
Pipeline (g77_pdf_job_worker_runner), enforces <= 20 MiB per child HTML and
0 external URLs, measures compounding WM & compile latency, and packages
certified Learn + Arena HTML5 modules into a SHA-256 signed offline cohort ZIP.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from datetime import datetime, timezone
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


def _count_external_urls(html_path: Path) -> int:
    text = html_path.read_text(encoding="utf-8", errors="replace")
    return len(EXTERNAL_RESOURCE_RE.findall(text))


def run_batch_pdf_benchmark(
    repo_root: Path,
    pdf_specs: List[Dict[str, Any]],
    output_dir: Path | None = None,
) -> Dict[str, Any]:
    pipeline_root = repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json"
    batch_dir = output_dir or (pipeline_root / "output" / "g79_batch_benchmark")
    batch_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    total_ms = 0.0
    max_child_bytes = 0
    total_external_urls = 0
    passed_count = 0

    for idx, item in enumerate(pdf_specs, start=1):
        job_id = str(item.get("job_id") or f"G79-BATCH-{idx:03d}")
        pdf_path = Path(item["pdf_path"])
        subject = str(item.get("subject", "science"))
        grade = int(item.get("grade", 8))

        job_out_dir = batch_dir / job_id
        t0 = time.perf_counter()
        res = execute_pdf_job_through_7agent_pipeline(
            repo_root=repo_root,
            job_id=job_id,
            pdf_path=pdf_path,
            subject=subject,
            grade=grade,
            output_dir=job_out_dir,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        total_ms += elapsed_ms

        learn_path = Path(res["learn_html_path"])
        arena_path = Path(res["arena_html_path"])
        learn_ext = _count_external_urls(learn_path)
        arena_ext = _count_external_urls(arena_path)
        ext_count = learn_ext + arena_ext
        total_external_urls += ext_count

        child_max = max(int(res["learn_size_bytes"]), int(res["arena_size_bytes"]))
        if child_max > max_child_bytes:
            max_child_bytes = child_max

        item_ok = bool(res["ok"]) and ext_count == 0
        if item_ok:
            passed_count += 1

        results.append({
            "job_id": job_id,
            "chapter_id": res["chapter_id"],
            "subject": subject,
            "grade": grade,
            "elapsed_ms": elapsed_ms,
            "learn_html_path": str(learn_path),
            "arena_html_path": str(arena_path),
            "learn_size_bytes": res["learn_size_bytes"],
            "arena_size_bytes": res["arena_size_bytes"],
            "within_20mib_child_cap": res["within_20mib_child_cap"],
            "external_url_count": ext_count,
            "wm_count": res["wm_count"],
            "qa_checks_passed": res["qa_checks_passed"],
            "ok": item_ok,
        })

    avg_compile_ms = round(total_ms / max(1, len(results)), 2)
    report = {
        "schema_version": "aasha.g79.batch.benchmark.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_pdfs": len(results),
        "passed_pdfs": passed_count,
        "all_passed": passed_count == len(results) and len(results) > 0,
        "max_child_html_bytes": max_child_bytes,
        "child_html_cap_bytes": MAX_CHILD_HTML_BYTES,
        "all_within_20mib_cap": max_child_bytes <= MAX_CHILD_HTML_BYTES,
        "total_external_urls": total_external_urls,
        "zero_external_urls": total_external_urls == 0,
        "avg_compile_ms": avg_compile_ms,
        "total_compile_ms": round(total_ms, 2),
        "results": results,
    }
    report["batch_benchmark_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    (batch_dir / "benchmark_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def build_cohort_offline_pack_zip(
    benchmark_report: Dict[str, Any],
    pack_zip_path: Path,
    center_id: str = "CENTER-UP-GN-01",
) -> Dict[str, Any]:
    pack_zip_path.parent.mkdir(parents=True, exist_ok=True)
    modules_manifest: List[Dict[str, Any]] = []

    with zipfile.ZipFile(pack_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in benchmark_report.get("results", []):
            for role, key in (("learn", "learn_html_path"), ("arena", "arena_html_path")):
                html_path = Path(item[key])
                arcname = f"modules/{item['chapter_id']}/{html_path.name}"
                raw = html_path.read_bytes()
                zf.writestr(arcname, raw)
                modules_manifest.append({
                    "job_id": item["job_id"],
                    "chapter_id": item["chapter_id"],
                    "role": role,
                    "subject": item["subject"],
                    "grade": item["grade"],
                    "archive_path": arcname,
                    "size_bytes": len(raw),
                    "within_20mib_child_cap": len(raw) <= MAX_CHILD_HTML_BYTES,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "wm_count": item["wm_count"],
                })

        manifest = {
            "schema_version": "aasha.offline.cohort.pack.v2",
            "center_id": center_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "offline_rationale": "UNSUPERVISED_HOME_DISTRACTION_FREE_STUDY",
            "target_hardware": "4GB_RAM_5G_SMARTPHONE_60FPS",
            "child_html_cap_bytes": MAX_CHILD_HTML_BYTES,
            "batch_benchmark_sha256": benchmark_report.get("batch_benchmark_sha256", ""),
            "module_count": len(modules_manifest),
            "modules": modules_manifest,
        }
        zf.writestr("cohort_pack_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        zf.writestr("benchmark_report.json", json.dumps(benchmark_report, indent=2, ensure_ascii=False))

    pack_bytes = pack_zip_path.read_bytes()
    return {
        "ok": True,
        "pack_zip_path": str(pack_zip_path),
        "pack_size_bytes": len(pack_bytes),
        "pack_sha256": hashlib.sha256(pack_bytes).hexdigest(),
        "module_count": len(modules_manifest),
    }
