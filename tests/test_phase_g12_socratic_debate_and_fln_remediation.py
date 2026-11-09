"""
Unit Tests for Phase G: Chunk G12 (Autonomous Offline Peer-to-Peer Socratic Debate Arena,
Foundational FLN Numeracy/Phonics Remediation Engine & 10,000-School District Readiness Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g12_socratic_debate_and_fln_remediation import (
    FoundationalFlnNumeracyPhonicsEngine,
    OfflinePeerToPeerSocraticDebateArena,
    TenThousandSchoolDistrictReadinessSeal,
    execute_chunk_g12_socratic_debate_and_fln_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g12_01_offline_peer_to_peer_socratic_debate_arena() -> None:
    arena = OfflinePeerToPeerSocraticDebateArena()
    debates = arena.evaluate_guild_debates()
    assert len(debates) == 3
    assert round(sum(d.composite_rigor_score for d in debates) / len(debates), 4) == 0.879
    assert sum(d.seva_debate_credits_awarded for d in debates) == 180


def test_g12_02_foundational_fln_numeracy_phonics_engine() -> None:
    engine = FoundationalFlnNumeracyPhonicsEngine()
    tracks = engine.run_fln_remediation_tracks()
    assert len(tracks) == 3
    assert all(t.remediation_verified for t in tracks)
    assert round(sum(t.mastery_gain for t in tracks) / len(tracks), 4) == 0.3467


def test_g12_03_ten_thousand_school_district_seal_and_html5_qa() -> None:
    seal = TenThousandSchoolDistrictReadinessSeal(REPO_ROOT)
    summary = seal.execute_chunk_g12_socratic_debate_and_fln_cycle()
    assert summary["chunk_id"] == "G12"
    assert summary["ten_thousand_school_district_seal"]["schools_certified"] == 10000
    assert summary["ten_thousand_school_district_seal"]["completed_chunks_count"] == 30
    assert summary["socratic_fln_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["socratic_fln_html_bundle"]["under_20mib_ceiling"] is True


def test_g12_04_end_to_end_chunk_g12_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g12_socratic_debate_and_fln_sync(REPO_ROOT)
    assert summary["status"] == "G12_SOCRATIC_DEBATE_ARENA_FLN_ENGINE_AND_10000_SCHOOL_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G13:")
