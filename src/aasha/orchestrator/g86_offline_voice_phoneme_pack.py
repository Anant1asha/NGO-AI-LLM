"""
G86: Offline Voice Read-Aloud & Bilingual Phoneme Pack Integration
Reuses IndicPhonemeSyncCompiler from aasha.offline_synthesizer.phoneme_bundle_optimizer
to compile synchronized Hindi/English WebVTT phoneme/viseme cues for offline Student PWA
read-aloud without any external TTS API calls (0 external URLs, <= 20 MiB cap).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from aasha.offline_synthesizer.phoneme_bundle_optimizer import (
    OFFLINE_BUNDLE_CEILING_BYTES,
    IndicPhonemeSyncCompiler,
)


def build_bilingual_voice_readaloud_pack(
    chapter_id: str,
    bilingual_lines: List[str],
    language: str = "hi-IN",
) -> Dict[str, Any]:
    combined_text = " ".join(str(line).strip() for line in bilingual_lines if str(line).strip())
    sync_report = IndicPhonemeSyncCompiler.compile_sync_track(
        combined_text,
        words_per_minute=140,
        target_total_duration_ms=max(2400, len(combined_text.split()) * 420),
    )
    webvtt = str(sync_report.get("webvtt", "WEBVTT\n"))
    vtt_bytes = len(webvtt.encode("utf-8"))
    if vtt_bytes > OFFLINE_BUNDLE_CEILING_BYTES:
        return {"ok": False, "error": "VOICE_PACK_EXCEEDS_20MIB_CAP", "size_bytes": vtt_bytes}

    pack = {
        "ok": True,
        "schema_version": "aasha.offline.voice.phoneme.pack.v1",
        "chapter_id": chapter_id,
        "language": language,
        "cue_count": int(sync_report.get("cue_count") or len(sync_report.get("cues", [])) or webvtt.count("-->")),
        "timing_drift_ms": float(sync_report.get("timing_drift_ms", 0.0)),
        "webvtt": webvtt,
        "size_bytes": vtt_bytes,
        "within_20mib_cap": vtt_bytes <= OFFLINE_BUNDLE_CEILING_BYTES,
        "offline_only": True,
        "zero_external_urls": "http://" not in webvtt.lower() and "https://" not in webvtt.lower(),
    }
    pack["voice_pack_sha256"] = hashlib.sha256(
        json.dumps(pack, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return pack
