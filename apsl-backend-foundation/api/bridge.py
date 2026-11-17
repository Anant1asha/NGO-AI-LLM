"""
apsl-backend-foundation/api/bridge.py
Chunk E2: apsl-backend-foundation & New_repo_web API bridge and NCVET/PSSCIVE qualification mapping.
"""
from __future__ import annotations
from typing import Any, Dict, List

NCVET_PSSCIVE_QUALIFICATION_MAP: Dict[str, Dict[str, Any]] = {
    "NCVET-NSQF-L3-IT-01": {
        "qp_code": "SSC/Q0101",
        "nsqf_level": 3,
        "sector": "IT-ITeS / Digital Literacy",
        "psscive_module": "Offline HTML5 Interactive Foundations",
        "teas_mastery_threshold": 0.80,
        "eco_seva_credits": 25,
    },
    "NCVET-NSQF-L4-AGRI-02": {
        "qp_code": "AGR/Q4301",
        "nsqf_level": 4,
        "sector": "Agriculture & Jal Seva",
        "psscive_module": "Precision Water & Soil Conservation",
        "teas_mastery_threshold": 0.80,
        "eco_seva_credits": 40,
    },
}


def map_chapter_to_ncvet_qualification(chapter_id: str, mastery_score: float = 0.85) -> Dict[str, Any]:
    qual_key = "NCVET-NSQF-L3-IT-01" if "MATH" in chapter_id or "CS" in chapter_id else "NCVET-NSQF-L4-AGRI-02"
    qual = NCVET_PSSCIVE_QUALIFICATION_MAP[qual_key]
    eligible = float(mastery_score) >= float(qual["teas_mastery_threshold"])
    return {
        "chapter_id": chapter_id,
        "qualification_id": qual_key,
        "qp_code": qual["qp_code"],
        "nsqf_level": qual["nsqf_level"],
        "psscive_module": qual["psscive_module"],
        "mastery_score": float(mastery_score),
        "ncvet_certified_eligible": eligible,
        "eco_seva_credits_awarded": qual["eco_seva_credits"] if eligible else 0,
    }
