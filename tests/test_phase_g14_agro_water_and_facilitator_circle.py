"""
Unit Tests for Phase G: Chunk G14 (Autonomous Offline Rural Agro-Weather & Water-Quality
Field Kit, Vernacular Facilitator Peer-Mentoring Circle & 50,000-Centre National Golden Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g14_agro_water_and_facilitator_circle import (
    FiftyThousandCentreNationalGoldenSeal,
    OfflineRuralAgroWeatherWaterQualityKit,
    VernacularFacilitatorPeerMentoringCircle,
    execute_chunk_g14_agro_water_and_mentoring_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g14_01_offline_rural_agro_weather_water_quality_kit() -> None:
    kit = OfflineRuralAgroWeatherWaterQualityKit()
    readings = kit.evaluate_field_stations()
    assert len(readings) == 3
    assert all(r.bis_is10500_compliant for r in readings)
    assert round(sum(r.potability_index for r in readings) / len(readings), 4) == 0.656


def test_g14_02_vernacular_facilitator_peer_mentoring_circle() -> None:
    circle = VernacularFacilitatorPeerMentoringCircle()
    records = circle.run_facilitator_circles()
    assert len(records) == 3
    assert sum(c.facilitators_count for c in records) == 66
    assert sum(c.pedagogical_case_studies_shared for c in records) == 33
    assert round(sum(c.post_circle_efficacy_score for c in records) / len(records), 4) == 0.91


def test_g14_03_fifty_thousand_centre_golden_seal_and_html5_qa() -> None:
    seal = FiftyThousandCentreNationalGoldenSeal(REPO_ROOT)
    summary = seal.execute_chunk_g14_agro_water_and_mentoring_cycle()
    assert summary["chunk_id"] == "G14"
    assert summary["fifty_thousand_centre_national_golden_seal"]["centres_certified"] == 50000
    assert summary["fifty_thousand_centre_national_golden_seal"]["completed_chunks_count"] == 32
    assert summary["agro_water_mentoring_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["agro_water_mentoring_html_bundle"]["under_20mib_ceiling"] is True


def test_g14_04_end_to_end_chunk_g14_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g14_agro_water_and_mentoring_sync(REPO_ROOT)
    assert summary["status"] == "G14_AGRO_WATER_FIELD_KIT_PEER_CIRCLE_AND_50000_CENTRE_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G15:")
