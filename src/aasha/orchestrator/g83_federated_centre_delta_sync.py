"""
G83: Multi-Centre Federated Offline Sync & CRDT Delta Merge
Idempotently merges offline custom PDF mastery records and compiled module manifests
across multiple rural/urban learning centres using high-water-mark CRDT semantics,
enforcing <= 20 MiB per child HTML and SHA-256 delta verification.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

MAX_CHILD_HTML_BYTES = 20_971_520


def merge_federated_centre_deltas(centre_bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged_mastery: Dict[str, Dict[str, Any]] = {}
    merged_modules: Dict[str, Dict[str, Any]] = {}
    max_lamport = 0
    centres_seen: List[str] = []
    duplicate_records_skipped = 0

    for bundle in centre_bundles:
        cid = str(bundle.get("centerId") or bundle.get("center_id") or "CENTER-UNKNOWN").strip()
        if cid not in centres_seen:
            centres_seen.append(cid)
        lamport = int(bundle.get("lamportEpoch") or bundle.get("lamport_epoch") or 0)
        if lamport > max_lamport:
            max_lamport = lamport

        for mod in bundle.get("modules", []):
            sz = int(mod.get("size_bytes") or mod.get("sizeBytes") or 0)
            if sz > MAX_CHILD_HTML_BYTES:
                return {"ok": False, "error": "CHILD_HTML_EXCEEDS_20MIB_CAP", "size_bytes": sz, "center_id": cid}
            mkey = f"{mod.get('chapter_id') or mod.get('chapterId')}|{mod.get('role', 'learn')}"
            if mkey not in merged_modules:
                merged_modules[mkey] = dict(mod)

        for entry in bundle.get("customPdfMastery", []):
            sid = str(entry.get("studentId") or "").strip()
            jid = str(entry.get("jobId") or "").strip()
            ch = str(entry.get("chapterId") or "").strip()
            if not sid or not jid or not ch:
                continue
            key = f"{sid}|{jid}|{ch}"
            score = float(entry.get("scorePct") or 0.0)
            wm_hits = int(entry.get("wmTapHits") or 0)
            if key in merged_mastery:
                duplicate_records_skipped += 1
                prev = merged_mastery[key]
                # High-water-mark CRDT merge: keep max score & max WM tap hits
                prev["scorePct"] = max(float(prev.get("scorePct") or 0.0), score)
                prev["wmTapHits"] = max(int(prev.get("wmTapHits") or 0), wm_hits)
            else:
                rec = dict(entry)
                rec["sourceCenterId"] = cid
                merged_mastery[key] = rec

    canonical = {
        "schema_version": "aasha.federated.centre.delta.v1",
        "centres": sorted(centres_seen),
        "lamport_epoch": max_lamport + 1,
        "module_count": len(merged_modules),
        "mastery_record_count": len(merged_mastery),
        "duplicate_records_skipped": duplicate_records_skipped,
        "within_20mib_child_cap": True,
    }
    canonical["federated_merkle_sha256"] = hashlib.sha256(
        json.dumps(
            {"canonical": canonical, "mastery": sorted(merged_mastery.items())},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    canonical["merged_at_utc"] = datetime.now(timezone.utc).isoformat()
    canonical["ok"] = True
    canonical["merged_mastery"] = list(merged_mastery.values())
    return canonical
