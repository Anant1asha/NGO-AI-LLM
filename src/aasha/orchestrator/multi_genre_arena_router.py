"""
G68: Multi-Genre Arena Theme Router & Game Engine Upgrade
Replaces the single #070b12 dark fighter-arena monoculture with domain-matched,
Experience-Registry-backed game genres, 60fps WebGL2/Matter.js/JSXGraph/ECharts engines,
and an offline Canvas2D finger-drawing scratchpad for 4GB+ RAM 5G smartphones.
"""
from __future__ import annotations

from typing import Any, Dict, List


MULTI_GENRE_THEME_CATALOG: List[Dict[str, Any]] = [
    {
        "genre_id": "GENRE-PHY-MATTERJS-LAB",
        "domain": "science",
        "foundation_ids": ["F04", "F07", "F08", "F21"],
        "avr_mechanics": ["AVR-P311", "AVR-P314", "AVR-P317", "AVR-P319"],
        "engine": "PixiJS_WebGL2_MatterJS_60fps",
        "theme_name": "Sunlit Virtual Physics Lab",
        "palette": {"bg": "#0f172a", "surface": "#1e293b", "accent": "#38bdf8", "highlight": "#fbbf24"},
        "gameplay_loop": "Manipulate live Matter.js physics variables, observe 60fps particle/force vectors, and solve target challenges",
        "includes_finger_scratchpad": True,
    },
    {
        "genre_id": "GENRE-MATH-MANIPULATIVE-PUZZLE",
        "domain": "math",
        "foundation_ids": ["F06", "F23", "F24", "F25", "F26", "F27"],
        "avr_mechanics": ["AVR-P301", "AVR-P302", "AVR-P303", "AVR-P309"],
        "engine": "PixiJS_WebGL2_JSXGraph_60fps",
        "theme_name": "Tactile Geometric Studio",
        "palette": {"bg": "#1e1b4b", "surface": "#312e81", "accent": "#a78bfa", "highlight": "#34d399"},
        "gameplay_loop": "Drag-and-fold JSXGraph/PixiJS fraction & geometry manipulatives with instant visual proof feedback",
        "includes_finger_scratchpad": True,
    },
    {
        "genre_id": "GENRE-CRICKET-STRATEGY-ARENA",
        "domain": "sports_stem",
        "foundation_ids": ["F02", "F19", "F20"],
        "avr_mechanics": ["AVR-P319", "AVR-P320"],
        "engine": "PixiJS_WebGL2_60fps_Sports_Arena",
        "theme_name": "Daylight Stadium Tactical Pitch",
        "palette": {"bg": "#064e3b", "surface": "#065f46", "accent": "#4ade80", "highlight": "#facc15"},
        "gameplay_loop": "Time projectile angles, run-rate ratios, and tactical decisions in an animated 60fps stadium",
        "includes_finger_scratchpad": True,
    },
    {
        "genre_id": "GENRE-ESCAPE-QUEST-ATLAS",
        "domain": "social_science",
        "foundation_ids": ["F01", "F09", "F10", "F12", "F13", "F14"],
        "avr_mechanics": ["AVR-P304", "AVR-P306", "AVR-P308", "AVR-P321"],
        "engine": "PixiJS_WebGL2_ECharts_MapAtlas_60fps",
        "theme_name": "Cartographer Expedition & Escape Room",
        "palette": {"bg": "#27272a", "surface": "#3f3f46", "accent": "#f97316", "highlight": "#fde047"},
        "gameplay_loop": "Unlock historical timeline rooms & interactive map nodes by solving bilingual clues",
        "includes_finger_scratchpad": True,
    },
    {
        "genre_id": "GENRE-VOCATIONAL-FINANCE-RIG",
        "domain": "vocational",
        "foundation_ids": ["F15", "F16", "F17", "F18"],
        "avr_mechanics": ["AVR-P305", "AVR-P315", "AVR-P316"],
        "engine": "PixiJS_WebGL2_MatterJS_Rig_60fps",
        "theme_name": "Workshop & Enterprise Control Deck",
        "palette": {"bg": "#172554", "surface": "#1e3a8a", "accent": "#22d3ee", "highlight": "#fb923c"},
        "gameplay_loop": "Assemble hydraulic/circuit rigs or balance micro-enterprise ledgers under realistic constraints",
        "includes_finger_scratchpad": True,
    },
]


def route_chapter_to_arena_genre(chapter_id: str, domain: str = "", prefer_variety_index: int = 0) -> Dict[str, Any]:
    """Route a chapter to a domain-matched, non-monoculture game genre & visual theme."""
    cid = (chapter_id or "").upper()
    dom = (domain or "").lower()
    if "CRICKET" in cid or "sports" in dom:
        chosen = MULTI_GENRE_THEME_CATALOG[2]
    elif "MATH" in cid or "FRAC" in cid or "POLY" in cid or "math" in dom:
        chosen = MULTI_GENRE_THEME_CATALOG[1]
    elif "PLUMB" in cid or "NCVET" in cid or "FIN" in cid or "voc" in dom:
        chosen = MULTI_GENRE_THEME_CATALOG[4]
    elif "PALAMPUR" in cid or "GEO" in cid or "HIST" in cid or "social" in dom:
        chosen = MULTI_GENRE_THEME_CATALOG[3]
    elif "SCI" in cid or "PHY" in cid or "CHEM" in cid or "science" in dom:
        chosen = MULTI_GENRE_THEME_CATALOG[0]
    else:
        chosen = MULTI_GENRE_THEME_CATALOG[prefer_variety_index % len(MULTI_GENRE_THEME_CATALOG)]

    return {
        "chapter_id": chapter_id,
        "single_theme_monoculture_disabled": True,
        "target_hardware": "4GB_RAM_5G_SMARTPHONE_60FPS",
        "max_child_html_bytes": 20971520,
        **chosen,
    }
