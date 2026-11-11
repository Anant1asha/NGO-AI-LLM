"""
Unit Tests for Phase G: Chunk G20 (Autonomous Offline Rural Soil-to-Market Supply-Chain Math
Simulator, Inter-Generational Village Oral-History Archive & 5,000,000-Learner December-2026 MVP Golden Master Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g20_supply_chain_and_oral_history_seal import (
    FiveMillionLearnerMvpGoldenMasterSeal,
    InterGenerationalVillageOralHistoryArchive,
    OfflineSoilToMarketSupplyChainSimulator,
    execute_chunk_g20_supply_chain_and_oral_history_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g20_01_offline_soil_to_market_supply_chain_simulator() -> None:
    sim = OfflineSoilToMarketSupplyChainSimulator()
    results = sim.simulate_supply_chains()
    assert len(results) == 3
    assert round(sum(r.harvest_quintals for r in results), 2) == 120.0
    assert round(sum(r.post_harvest_loss_reduced_pct for r in results) / len(results), 2) == 14.0
    assert sum(r.net_gain_seva_credits for r in results) == 900
    assert all(r.zero_pii_verified for r in results)


def test_g20_02_inter_generational_village_oral_history_archive() -> None:
    packs = InterGenerationalVillageOralHistoryArchive.build_oral_history_packs()
    assert len(packs) == 3
    assert sum(p.stories_archived for p in packs) == 75
    assert sum(p.tln_concepts_linked for p in packs) == 24
    assert round(sum(p.verification_score for p in packs) / len(packs), 4) == 0.96
    assert all(p.zero_pii_verified for p in packs)


def test_g20_03_five_million_learner_mvp_seal_and_html5_qa() -> None:
    seal = FiveMillionLearnerMvpGoldenMasterSeal(REPO_ROOT)
    summary = seal.execute_chunk_g20_supply_chain_and_oral_history_cycle()
    assert summary["chunk_id"] == "G20"
    assert summary["five_million_learner_mvp_golden_seal"]["learners_certified"] == 5000000
    assert summary["five_million_learner_mvp_golden_seal"]["completed_chunks_count"] == 38
    assert summary["supply_oral_history_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["supply_oral_history_html_bundle"]["under_20mib_ceiling"] is True


def test_g20_04_end_to_end_chunk_g20_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g20_supply_chain_and_oral_history_sync(REPO_ROOT)
    assert summary["status"] == "G20_SUPPLY_CHAIN_SIMULATOR_ORAL_HISTORY_AND_5M_LEARNER_MVP_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G21:")
