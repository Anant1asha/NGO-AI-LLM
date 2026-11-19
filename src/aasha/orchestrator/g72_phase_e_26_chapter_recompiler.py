"""
G72: Full 13-Chapter (26 Learn & Arena Child HTML5 Modules) Recompiler
Uses G70 Multi-Genre 60fps Matter.js/PixiJS/JSXGraph/ECharts Engine + G67 Compounding WM
Auto-Save & Domain-Specific Disbursement + G69 Finger-Drawing Scratchpad.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.aasha.orchestrator.g70_multi_genre_chapter_compiler import (
    compile_g70_multi_genre_chapter_pack,
)


PHASE_E_13_CHAPTER_SPECS: List[Dict[str, Any]] = [
    ("NCERT-G06-MATH-CH07", "math", "Fractions & Area Models", "भिन्न और क्षेत्रफल मॉडल", {"numerator": "अंश", "denominator": "हर"}),
    ("NCERT-G07-MATH-CH01", "math", "Integers & Number Line", "पूर्णांक और संख्या रेखा", {"integer": "पूर्णांक", "quotient": "भागफल"}),
    ("NCERT-G08-MATH-CH09", "math", "Algebraic Expressions", "बीजीय व्यंजक", {"polynomial": "बहुपद", "coefficient": "गुणांक"}),
    ("NCERT-G10-MATH-CH02", "math", "Polynomials & Roots", "बहुपद और शून्यक", {"parabola": "परवलय", "discriminant": "विविक्तकर"}),
    ("NCERT-G08-SCI-CH01", "science", "Crop Production & Drip Irrigation", "फसल उत्पादन और सिंचाई", {"irrigation": "सिंचाई", "compost": "खाद"}),
    ("NCERT-G08-SCI-CH08", "science", "Force & Pressure", "बल तथा दाब", {"pascal": "पास्कल", "piston": "पिस्टन"}),
    ("NCERT-G08-SCI-CH11", "science", "Chemical Effects of Current", "विद्युत धारा के रासायनिक प्रभाव", {"electrode": "इलेक्ट्रोड", "electrolyte": "विद्युत-अपघट्य"}),
    ("NCERT-G07-SCI-CH04", "science", "Heat Transfer & Conduction", "ऊष्मा स्थानांतरण", {"conduction": "चालन", "convection": "संवहन"}),
    ("NCERT-G09-SCI-CH09", "science", "Force & Laws of Motion", "बल तथा गति के नियम", {"inertia": "जड़त्व", "momentum": "संवेग"}),
    ("NCERT-G10-SCI-CH06", "science", "Life Processes & Circulation", "जैव प्रक्रम और परिसंचरण", {"hemoglobin": "हीमोग्लोबिन", "artery": "धमनी"}),
    ("NCERT-G09-SOC-PALAMPUR", "social_science", "Story of Village Palampur", "पालमपुर गाँव की कहानी", {"agrarian": "कृषि-प्रधान", "surplus": "अधिशेष"}),
    ("Class8_Science_Cricket", "sports_stem", "Cricket Kinematics & Run-Rate", "क्रिकेट गतिकी और रन-रेट", {"trajectory": "प्रक्षेप पथ", "kinematics": "गतिकी"}),
    ("NCVET-G09-PLUMB-CH01", "vocational", "Hydraulic Pipe Fitting Rig", "हाइड्रोलिक पाइप फिटिंग रिग", {"manifold": "मैनिफोल्ड", "flange": "फ्लैंज"}),
]


def recompile_26_phase_e_modules(repo_root: Path) -> Dict[str, Any]:
    specs: List[Dict[str, Any]] = []
    for cid, dom, t_en, t_hi, terms in PHASE_E_13_CHAPTER_SPECS:
        for mode in ("Learning", "Arena"):
            specs.append(
                {
                    "chapter_id": f"{cid}_{mode}",
                    "domain": dom,
                    "title_en": f"{t_en} ({mode} 60fps)",
                    "title_hi": f"{t_hi} ({mode})",
                    "module_text": f"{t_en} interactive 60fps simulation and bilingual LLE mastery for {cid}.",
                    "new_terms": terms,
                    "sim_mode": f"{dom}_{mode.lower()}_60fps",
                    "challenge_prompt": f"Explore and master {t_en} in {mode} mode at 60fps.",
                }
            )
    res = compile_g70_multi_genre_chapter_pack(
        repo_root=repo_root,
        output_subdir="Aasha-AI/aasha-pipeline-with-master-json/output/g72_26module_multi_genre_pack",
        chapter_specs=specs,
    )
    return {
        **res,
        "chapters_count": len(PHASE_E_13_CHAPTER_SPECS),
        "expected_modules_count": 26,
    }
