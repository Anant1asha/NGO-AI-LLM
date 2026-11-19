"""
G67: Compounding WM Auto-Save & Domain-Specific Pack Disbursement Engine
+ Learning-Side High-Fidelity 60fps WebGL2/Matter.js Simulator Default (replacing SVG-only default).
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_LEARN_SIM_ENGINE = "PixiJS_WebGL2_MatterJS_60fps_Interactive_Sim"

DOMAIN_SIM_ENGINES: Dict[str, Dict[str, str]] = {
    "science": {
        "engine": "PixiJS_WebGL2_MatterJS_60fps_Interactive_Sim",
        "visual_archetype": "PhET_MatterJS_Virtual_Lab_60fps",
        "fallback": "HTML5_Canvas2D_60fps",
    },
    "math": {
        "engine": "PixiJS_WebGL2_JSXGraph_60fps_Interactive_Sim",
        "visual_archetype": "KingsMath_JSXGraph_Manipulative_60fps",
        "fallback": "HTML5_Canvas2D_60fps",
    },
    "vocational": {
        "engine": "PixiJS_WebGL2_MatterJS_Rig_60fps_Sim",
        "visual_archetype": "NCVET_HandsOn_Rig_Simulator_60fps",
        "fallback": "HTML5_Canvas2D_60fps",
    },
    "social_science": {
        "engine": "PixiJS_WebGL2_ECharts_MapAtlas_60fps_Sim",
        "visual_archetype": "GeoGuess_QuestJS_Interactive_Story_60fps",
        "fallback": "HTML5_Canvas2D_60fps",
    },
}


def resolve_learning_simulator_engine(domain: str = "science", chapter_id: str = "") -> Dict[str, Any]:
    """Return high-fidelity 60fps WebGL2/Matter.js/JSXGraph simulator config (never SVG-only default)."""
    norm = (domain or "science").strip().lower()
    if "math" in norm or "MATH" in chapter_id.upper():
        key = "math"
    elif "plumb" in norm or "voc" in norm or "NCVET" in chapter_id.upper():
        key = "vocational"
    elif "geo" in norm or "hist" in norm or "civics" in norm or "social" in norm:
        key = "social_science"
    else:
        key = "science"
    spec = DOMAIN_SIM_ENGINES[key]
    return {
        "chapter_id": chapter_id,
        "domain": key,
        "default_simulator_engine": spec["engine"],
        "visual_archetype": spec["visual_archetype"],
        "svg_only_default_disabled": True,
        "target_hardware": "4GB_RAM_5G_SMARTPHONE_60FPS",
    }


def _ensure_wm_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wm_compounding_lexicon (
            word TEXT PRIMARY KEY,
            hindi_meaning TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT 'core',
            source_chapter_id TEXT NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def seed_compounding_wm_from_defaults(
    db_path: Path,
    defaults_v2_path: Path,
) -> int:
    """Seed SQLite compounding WM table from defaults_expanded_v2.json without overwriting newer entries."""
    v2 = json.loads(defaults_v2_path.read_text(encoding="utf-8"))
    wm: Dict[str, str] = v2.get("WM", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        _ensure_wm_table(conn)
        rows = [
            (str(w).strip().lower(), str(h).strip(), "core", "BASELINE_V2", 1, now_iso)
            for w, h in wm.items()
            if str(w).strip() and str(h).strip()
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO wm_compounding_lexicon
                (word, hindi_meaning, domain, source_chapter_id, usage_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM wm_compounding_lexicon").fetchone()[0]
    return int(count)


def autosave_and_disburse_chapter_wm(
    db_path: Path,
    defaults_v2_path: Path,
    chapter_id: str,
    domain: str,
    module_text: str,
    new_terms: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    1. Reuse all existing WM entries from the compounding store.
    2. Auto-save & expand with any newly discovered chapter words.
    3. Sync back to defaults_expanded_v2.json.
    4. Disburse Core Cumulative WM + Domain-Specific Pack (all module-context WM).
    """
    seed_compounding_wm_from_defaults(db_path, defaults_v2_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    norm_domain = (domain or "science").strip().lower()
    new_terms = new_terms or {}

    with sqlite3.connect(db_path) as conn:
        _ensure_wm_table(conn)
        existing_rows = conn.execute(
            "SELECT word, hindi_meaning, domain FROM wm_compounding_lexicon"
        ).fetchall()
        existing_map = {w: (h, d) for w, h, d in existing_rows}

        added_words: List[str] = []
        for raw_w, raw_h in new_terms.items():
            w = str(raw_w).strip().lower()
            h = str(raw_h).strip()
            if not w or not h:
                continue
            if w not in existing_map:
                conn.execute(
                    """
                    INSERT INTO wm_compounding_lexicon
                        (word, hindi_meaning, domain, source_chapter_id, usage_count, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (w, h, norm_domain, chapter_id, now_iso),
                )
                existing_map[w] = (h, norm_domain)
                added_words.append(w)
            else:
                conn.execute(
                    "UPDATE wm_compounding_lexicon SET usage_count = usage_count + 1, updated_at = ? WHERE word = ?",
                    (now_iso, w),
                )
        conn.commit()

        all_rows = conn.execute(
            "SELECT word, hindi_meaning, domain FROM wm_compounding_lexicon ORDER BY word ASC"
        ).fetchall()

    # Sync expanded cumulative WM back to defaults_expanded_v2.json
    v2 = json.loads(defaults_v2_path.read_text(encoding="utf-8"))
    cumulative_wm = {w: h for w, h, _ in all_rows}
    v2["WM"] = cumulative_wm
    v2["wm_count"] = len(cumulative_wm)
    defaults_v2_path.write_text(json.dumps(v2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Disbursement: Core Cumulative WM + Domain-Specific Pack (all module context WM)
    tokens = set(re.findall(r"[a-zA-Z]{2,}", (module_text or "").lower()))
    core_cumulative_wm = {w: h for w, h, d in all_rows if d == "core"}
    domain_specific_pack = {
        w: h for w, h, d in all_rows
        if d == norm_domain or w in tokens or w in new_terms
    }
    disbursed_wm = {**core_cumulative_wm, **domain_specific_pack}

    return {
        "chapter_id": chapter_id,
        "domain": norm_domain,
        "added_new_words_count": len(added_words),
        "added_new_words": added_words,
        "total_cumulative_wm_count": len(cumulative_wm),
        "core_cumulative_wm_count": len(core_cumulative_wm),
        "domain_specific_pack_count": len(domain_specific_pack),
        "disbursed_wm_count": len(disbursed_wm),
        "disbursed_wm": disbursed_wm,
        "learning_simulator": resolve_learning_simulator_engine(norm_domain, chapter_id),
    }
