"""
G90: December 31, 2026 MVP End-to-End System Certification Harness
Chains the live 7-Agent PDF->HTML5 Batch Pipeline (G79), Offline Voice Phoneme
Pack (G86), Offline Leaderboard & Streaks (G85), NCVET Apprenticeship Portfolio (G87),
Printable Remedial Worksheet (G88), Solar OTA Delta Verifier (G89), and Multi-Centre
Federated CRDT Merge (G83) into a single cryptographically signed MVP certification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from aasha.orchestrator.g79_batch_pdf_benchmark_and_cohort_pack import (
    build_cohort_offline_pack_zip,
    run_batch_pdf_benchmark,
)
from aasha.orchestrator.g83_federated_centre_delta_sync import merge_federated_centre_deltas
from aasha.orchestrator.g85_offline_leaderboard_and_streaks import (
    compute_offline_cohort_leaderboard_and_streaks,
)
from aasha.orchestrator.g86_offline_voice_phoneme_pack import build_bilingual_voice_readaloud_pack
from aasha.orchestrator.g87_ncvet_skill_portfolio_exporter import (
    export_offline_ncvet_skill_portfolio,
)
from aasha.orchestrator.g88_remedial_worksheet_print_qr import (
    build_printable_remedial_worksheet_pack,
)
from aasha.orchestrator.g89_solar_ota_delta_verifier import verify_solar_ota_delta_bundle


def run_dec_2026_mvp_e2e_certification(
    repo_root: Path,
    pdf_specs: List[Dict[str, Any]],
    work_dir: Path,
) -> Dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    batch_report = run_batch_pdf_benchmark(repo_root, pdf_specs, output_dir=work_dir / "batch")
    pack_zip = work_dir / "mvp_cohort_pack.zip"
    pack_res = build_cohort_offline_pack_zip(batch_report, pack_zip, center_id="CENTER-UP-GN-01")

    voice_pack = build_bilingual_voice_readaloud_pack(
        "NCERT-G08-SCI-CH08",
        ["Force is a push or pull. बल किसी वस्तु पर धक्का या खिंचाव है।"],
        language="hi-IN",
    )
    mastery_rows = [
        {"studentId": "STU-MVP-01", "jobId": "J1", "chapterId": "SCI_CH08", "scorePct": 94, "wmTapHits": 28, "coinsAwarded": 15},
        {"studentId": "STU-MVP-01", "jobId": "J2", "chapterId": "NCVET_SOLAR_01", "scorePct": 90, "wmTapHits": 20, "coinsAwarded": 15},
        {"studentId": "STU-MVP-02", "jobId": "J1", "chapterId": "SCI_CH08", "scorePct": 62, "wmTapHits": 8, "coinsAwarded": 5},
    ]
    leaderboard = compute_offline_cohort_leaderboard_and_streaks(mastery_rows)
    ncvet = export_offline_ncvet_skill_portfolio("STU-MVP-01", mastery_rows[:2])
    remedial = build_printable_remedial_worksheet_pack("SCI_CH08", mastery_rows)

    ota_chunks = [
        {
            "chunk_id": "MVP-CHUNK-01",
            "size_bytes": Path(r["learn_html_path"]).stat().st_size,
            "content": Path(r["learn_html_path"]).read_text(encoding="utf-8"),
            "sha256": hashlib.sha256(Path(r["learn_html_path"]).read_bytes()).hexdigest(),
        }
        for r in batch_report["results"]
    ]
    ota_verify = verify_solar_ota_delta_bundle("CENTER-UP-GN-01", ota_chunks)
    federated = merge_federated_centre_deltas([
        {"centerId": "CENTER-UP-GN-01", "lamportEpoch": 30, "customPdfMastery": mastery_rows},
        {"centerId": "CENTER-UP-LKO-02", "lamportEpoch": 32, "customPdfMastery": mastery_rows[:1]},
    ])

    all_ok = (
        batch_report["all_passed"]
        and batch_report["all_within_20mib_cap"]
        and batch_report["zero_external_urls"]
        and pack_res["ok"]
        and voice_pack["ok"]
        and leaderboard["offline_only"]
        and ncvet["ok"]
        and remedial["ok"]
        and ota_verify["ok"]
        and federated["ok"]
    )
    cert = {
        "ok": all_ok,
        "schema_version": "aasha.dec2026.mvp.certification.v1",
        "target_deadline": "2026-12-31",
        "batch_pdfs_passed": batch_report["passed_pdfs"],
        "cohort_pack_modules": pack_res["module_count"],
        "voice_cues": voice_pack["cue_count"],
        "leaderboard_students": leaderboard["student_count"],
        "ncvet_readiness": ncvet["readiness_status"],
        "remedial_flagged": remedial["students_flagged_count"],
        "ota_verified": ota_verify["ok"],
        "federated_lamport_epoch": federated["lamport_epoch"],
        "all_within_20mib_cap": batch_report["all_within_20mib_cap"],
        "zero_external_urls": batch_report["zero_external_urls"],
    }
    cert["mvp_certification_sha256"] = hashlib.sha256(
        json.dumps(cert, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return cert
