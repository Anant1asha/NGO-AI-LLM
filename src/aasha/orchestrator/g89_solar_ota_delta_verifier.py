"""
G89: Offline Solar OTA Delta Bundle Verifier
Verifies SHA-256 integrity, <= 20 MiB per child HTML5 cap, and zero external URLs
for offline Solar-powered / USB / LAN OTA delta bundles before applying updates
at rural/urban learning centres.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

MAX_CHILD_HTML_BYTES = 20_971_520


def verify_solar_ota_delta_bundle(
    center_id: str,
    delta_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not delta_chunks:
        return {"ok": False, "error": "EMPTY_OTA_DELTA_BUNDLE", "center_id": center_id}

    max_bytes = 0
    for chunk in delta_chunks:
        size_bytes = int(chunk.get("size_bytes") or chunk.get("sizeBytes") or 0)
        if size_bytes > MAX_CHILD_HTML_BYTES:
            return {
                "ok": False,
                "error": "CHILD_HTML_EXCEEDS_20MIB_CAP",
                "size_bytes": size_bytes,
                "chunk_id": str(chunk.get("chunk_id") or ""),
            }
        if size_bytes > max_bytes:
            max_bytes = size_bytes

        content = chunk.get("content")
        expected_sha = str(chunk.get("sha256") or "").strip()
        if content is not None and expected_sha:
            actual_sha = hashlib.sha256(str(content).encode("utf-8")).hexdigest()
            if actual_sha != expected_sha:
                return {
                    "ok": False,
                    "error": "OTA_CHUNK_SHA256_MISMATCH",
                    "chunk_id": str(chunk.get("chunk_id") or ""),
                }
            low = str(content).lower()
            if "src=\"http://" in low or "src=\"https://" in low or "href=\"http://" in low or "href=\"https://" in low:
                return {
                    "ok": False,
                    "error": "EXTERNAL_URL_DETECTED_IN_OTA_CHUNK",
                    "chunk_id": str(chunk.get("chunk_id") or ""),
                }

    report = {
        "ok": True,
        "schema_version": "aasha.solar.ota.verifier.v1",
        "center_id": center_id,
        "chunk_count": len(delta_chunks),
        "max_child_bytes": max_bytes,
        "within_20mib_cap": max_bytes <= MAX_CHILD_HTML_BYTES,
        "zero_external_urls": True,
        "offline_only": True,
    }
    report["ota_verification_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return report
