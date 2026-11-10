"""
Unit Tests for Phase G: Chunk G15 (Autonomous Offline Rural Solar-Powered Library & Open-Textbook
Harvester, Inter-District STEM Innovation Fair Judge & 100,000-Centre Sovereign AIOS Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g15_solar_library_and_stem_fair import (
    HundredThousandCentreSovereignAiosSeal,
    InterDistrictStemInnovationFairJudge,
    OfflineSolarPoweredLibraryHarvester,
    execute_chunk_g15_solar_library_and_stem_fair_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g15_01_offline_solar_powered_library_harvester() -> None:
    packs = OfflineSolarPoweredLibraryHarvester.harvest_open_textbook_packs()
    assert len(packs) == 3
    assert sum(p.chapters_indexed for p in packs) == 300
    assert round(sum(p.compressed_size_mb for p in packs), 2) == 29.0
    assert round(sum(p.deduplication_ratio for p in packs) / len(packs), 4) == 0.74
    assert all(p.under_20mib_pack_ceiling and p.cc_by_sa_license_verified for p in packs)


def test_g15_02_inter_district_stem_innovation_fair_judge() -> None:
    judge = InterDistrictStemInnovationFairJudge()
    evals = judge.evaluate_stem_fair_prototypes()
    assert len(evals) == 3
    assert sum(e.innovation_seva_grant_tokens for e in evals) == 850
    assert round(sum(e.composite_fair_score for e in evals) / len(evals), 4) == 0.9042


def test_g15_03_hundred_thousand_centre_sovereign_seal_and_html5_qa() -> None:
    seal = HundredThousandCentreSovereignAiosSeal(REPO_ROOT)
    summary = seal.execute_chunk_g15_solar_library_and_stem_fair_cycle()
    assert summary["chunk_id"] == "G15"
    assert summary["hundred_thousand_centre_sovereign_seal"]["centres_certified"] == 100000
    assert summary["hundred_thousand_centre_sovereign_seal"]["completed_chunks_count"] == 33
    assert summary["solar_library_stem_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["solar_library_stem_html_bundle"]["under_20mib_ceiling"] is True


def test_g15_04_end_to_end_chunk_g15_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g15_solar_library_and_stem_fair_sync(REPO_ROOT)
    assert summary["status"] == "G15_SOLAR_LIBRARY_STEM_FAIR_AND_100000_CENTRE_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G16:")
