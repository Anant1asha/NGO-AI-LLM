"""
Unit Tests for Phase G: Chunk G23 (Autonomous Offline Rural Groundwater & Aquifer Darcy-Flow
Simulator, Vernacular Braille-Tactile Math Board Compiler & 50,000,000-Learner Sovereign Bharat Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g23_aquifer_darcy_and_tactile_math import (
    FiftyMillionLearnerSovereignBharatSeal,
    OfflineGroundwaterAquiferDarcyFlowSimulator,
    VernacularBrailleTactileMathBoardCompiler,
    execute_chunk_g23_aquifer_darcy_and_tactile_math_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g23_01_offline_groundwater_aquifer_darcy_flow_simulator() -> None:
    sim = OfflineGroundwaterAquiferDarcyFlowSimulator()
    results = sim.simulate_aquifer_recharge()
    assert len(results) == 3
    assert round(sum(r.darcy_flow_m3_day for r in results), 2) == 45.0
    assert round(sum(r.water_table_rise_m for r in results) / len(results), 4) == 1.8
    assert sum(r.jal_seva_recharge_credits for r in results) == 720
    assert all(r.zero_pii_verified for r in results)


def test_g23_02_vernacular_braille_tactile_math_board_compiler() -> None:
    boards = VernacularBrailleTactileMathBoardCompiler.compile_tactile_math_boards()
    assert len(boards) == 3
    assert sum(b.tactile_pegs_count for b in boards) == 208
    assert sum(b.braille_cells_encoded for b in boards) == 216
    assert round(sum(b.tactile_precision_score for b in boards) / len(boards), 4) == 0.98
    assert all(b.frugal_cost_inr <= 25.0 and b.zero_pii_verified for b in boards)


def test_g23_03_fifty_million_learner_seal_and_html5_qa() -> None:
    seal = FiftyMillionLearnerSovereignBharatSeal(REPO_ROOT)
    summary = seal.execute_chunk_g23_aquifer_and_tactile_math_cycle()
    assert summary["chunk_id"] == "G23"
    assert summary["fifty_million_learner_sovereign_seal"]["learners_certified"] == 50000000
    assert summary["fifty_million_learner_sovereign_seal"]["completed_chunks_count"] == 41
    assert summary["aquifer_tactile_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["aquifer_tactile_html_bundle"]["under_20mib_ceiling"] is True


def test_g23_04_end_to_end_chunk_g23_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g23_aquifer_darcy_and_tactile_math_sync(REPO_ROOT)
    assert summary["status"] == "G23_AQUIFER_DARCY_SIMULATOR_TACTILE_MATH_AND_50M_LEARNER_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G24:")
