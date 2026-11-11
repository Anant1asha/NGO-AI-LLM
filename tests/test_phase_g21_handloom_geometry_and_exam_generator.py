"""
Unit Tests for Phase G: Chunk G21 (Autonomous Offline Rural Handicraft & Handloom Geometry
Simulator, Block-Level Offline Exam Paper Generator & 10,000,000-Learner Sovereign Bharat Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g21_handloom_geometry_and_exam_generator import (
    BlockLevelOfflineExamPaperGenerator,
    OfflineHandicraftHandloomGeometrySimulator,
    TenMillionLearnerSovereignBharatSeal,
    execute_chunk_g21_handloom_geometry_and_exam_gen_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g21_01_offline_handicraft_handloom_geometry_simulator() -> None:
    sim = OfflineHandicraftHandloomGeometrySimulator()
    results = sim.simulate_handloom_geometry()
    assert len(results) == 3
    assert sum(r.artisan_seva_credits for r in results) == 540
    assert round(sum(r.pattern_accuracy_score for r in results) / len(results), 4) == 0.96
    assert all(r.zero_pii_verified for r in results)


def test_g21_02_block_level_offline_exam_paper_generator() -> None:
    papers = BlockLevelOfflineExamPaperGenerator.generate_block_exam_papers()
    assert len(papers) == 3
    assert sum(p.questions_count for p in papers) == 90
    assert round(sum(p.bloom_balance_score for p in papers) / len(papers), 4) == 0.97
    assert all(p.answer_key_hash_locked for p in papers)


def test_g21_03_ten_million_learner_seal_and_html5_qa() -> None:
    seal = TenMillionLearnerSovereignBharatSeal(REPO_ROOT)
    summary = seal.execute_chunk_g21_handloom_and_exam_gen_cycle()
    assert summary["chunk_id"] == "G21"
    assert summary["ten_million_learner_sovereign_seal"]["learners_certified"] == 10000000
    assert summary["ten_million_learner_sovereign_seal"]["completed_chunks_count"] == 39
    assert summary["handloom_exam_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["handloom_exam_html_bundle"]["under_20mib_ceiling"] is True


def test_g21_04_end_to_end_chunk_g21_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g21_handloom_geometry_and_exam_gen_sync(REPO_ROOT)
    assert summary["status"] == "G21_HANDLOOM_GEOMETRY_SIMULATOR_BLOCK_EXAM_GEN_AND_10M_LEARNER_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G22:")
