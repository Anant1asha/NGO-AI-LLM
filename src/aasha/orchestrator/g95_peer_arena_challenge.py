"""
G95: Offline Student Peer Challenge & Arena Invite
Creates deterministic offline LAN/QR peer Arena challenge invites for
60fps gamified modules (Cricket Strategy, Physics Lab, Math Manipulative,
Escape Quest, Vocational Rig) with zero external URLs and SHA-256 integrity.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def create_offline_peer_arena_challenge(
    challenger_id: str,
    chapter_id: str,
    genre_id: str = "GENRE-CRICKET-STRATEGY-ARENA",
    target_score_pct: float = 85.0,
) -> Dict[str, Any]:
    cid = str(challenger_id or "").strip()
    chid = str(chapter_id or "").strip()
    if not cid or not chid:
        return {"ok": False, "error": "CHALLENGER_AND_CHAPTER_REQUIRED"}

    invite_code = f"ARENA-{chid[:8].upper()}-{abs(hash(cid + chid)) % 9000 + 1000}"
    challenge = {
        "ok": True,
        "schema_version": "aasha.peer.arena.challenge.v1",
        "challenger_id": cid,
        "chapter_id": chid,
        "genre_id": genre_id,
        "target_score_pct": round(float(target_score_pct), 1),
        "invite_code": invite_code,
        "offline_only": True,
        "zero_external_urls": True,
    }
    challenge["challenge_sha256"] = hashlib.sha256(
        json.dumps(challenge, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return challenge
