"""
Unit Tests for Phase G: Chunk G17 (Autonomous Offline Rural Disaster-Resilience & First-Aid
Simulator, Inter-State Vernacular Glossary Harmonizer & 500,000-Centre Sovereign Bharat Golden Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g17_disaster_resilience_and_glossary_harmonizer import (
    FiveHundredThousandCentreSovereignGoldenSeal,
    InterStateVernacularGlossaryHarmonizer,
    OfflineRuralDisasterResilienceFirstAidSimulator,
    execute_chunk_g17_disaster_resilience_and_glossary_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g17_01_offline_rural_disaster_resilience_first_aid_simulator() -> None:
    sim = OfflineRuralDisasterResilienceFirstAidSimulator()
    drills = sim.run_disaster_resilience_drills()
    assert len(drills) == 3
    assert sum(d.seva_resilience_credits for d in drills) == 450
    assert round(sum(d.composite_preparedness_score for d in drills) / len(drills), 4) == 0.9217


def test_g17_02_inter_state_vernacular_glossary_harmonizer() -> None:
    entries = InterStateVernacularGlossaryHarmonizer.harmonize_nine_script_glossary()
    assert len(entries) == 3
    assert sum(e.scripts_count for e in entries) == 27
    assert round(sum(e.semantic_equivalence_score for e in entries) / len(entries), 4) == 0.995
    assert all(e.bijection_verified for e in entries)


def test_g17_03_five_hundred_thousand_centre_seal_and_html5_qa() -> None:
    seal = FiveHundredThousandCentreSovereignGoldenSeal(REPO_ROOT)
    summary = seal.execute_chunk_g17_disaster_resilience_and_glossary_cycle()
    assert summary["chunk_id"] == "G17"
    assert summary["five_hundred_thousand_centre_sovereign_seal"]["centres_certified"] == 500000
    assert summary["five_hundred_thousand_centre_sovereign_seal"]["completed_chunks_count"] == 35
    assert summary["disaster_glossary_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["disaster_glossary_html_bundle"]["under_20mib_ceiling"] is True


def test_g17_04_end_to_end_chunk_g17_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g17_disaster_resilience_and_glossary_sync(REPO_ROOT)
    assert summary["status"] == "G17_DISASTER_RESILIENCE_SIMULATOR_GLOSSARY_AND_500000_CENTRE_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G18:")
