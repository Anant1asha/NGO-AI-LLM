"""
Unit Tests for Phase G: Chunk G19 (Autonomous Offline Rural Nutrition Math & Hygiene Lab,
Gram-Sabha Open Impact Audit Portal & 2,000,000-Learner Sovereign Bharat Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g19_nutrition_math_and_gram_sabha_portal import (
    GramSabhaOpenImpactAuditPortal,
    OfflineSchoolbookNutritionMathAndHygieneLab,
    TwoMillionLearnerSovereignBharatSeal,
    execute_chunk_g19_nutrition_and_gram_sabha_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g19_01_offline_schoolbook_nutrition_math_and_hygiene_lab() -> None:
    lab = OfflineSchoolbookNutritionMathAndHygieneLab()
    sims = lab.run_nutrition_and_hygiene_labs()
    assert len(sims) == 3
    assert sum(s.seva_garden_credits for s in sims) == 450
    assert round(sum(s.scientific_efficacy_ratio for s in sims) / len(sims), 4) == 0.95
    assert all(s.zero_pii_verified for s in sims)


def test_g19_02_gram_sabha_open_impact_audit_portal() -> None:
    cards = GramSabhaOpenImpactAuditPortal.generate_gram_sabha_scorecards()
    assert len(cards) == 3
    assert sum(c.verified_seva_projects for c in cards) == 1250
    assert sum(c.schoolbook_chapters_mastered for c in cards) == 11400
    assert all(c.public_merkle_proof_valid and c.zero_pii_verified for c in cards)


def test_g19_03_two_million_learner_seal_and_html5_qa() -> None:
    seal = TwoMillionLearnerSovereignBharatSeal(REPO_ROOT)
    summary = seal.execute_chunk_g19_nutrition_and_gram_sabha_cycle()
    assert summary["chunk_id"] == "G19"
    assert summary["two_million_learner_sovereign_seal"]["learners_certified"] == 2000000
    assert summary["two_million_learner_sovereign_seal"]["completed_chunks_count"] == 37
    assert summary["nutrition_gram_sabha_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["nutrition_gram_sabha_html_bundle"]["under_20mib_ceiling"] is True


def test_g19_04_end_to_end_chunk_g19_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g19_nutrition_and_gram_sabha_sync(REPO_ROOT)
    assert summary["status"] == "G19_NUTRITION_MATH_LAB_GRAM_SABHA_PORTAL_AND_2M_LEARNER_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G20:")
