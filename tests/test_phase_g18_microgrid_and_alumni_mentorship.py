"""
Unit Tests for Phase G: Chunk G18 (Autonomous Offline Rural Renewable Micro-Grid Load Balancer,
Alumni-to-Sathi Peer Mentorship Ledger & 1,000,000-Learner Sovereign Impact Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g18_microgrid_and_alumni_mentorship import (
    AlumniToSathiPeerMentorshipLedger,
    OfflineRuralRenewableMicroGridLoadBalancer,
    OneMillionLearnerSovereignImpactSeal,
    execute_chunk_g18_microgrid_and_alumni_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g18_01_offline_rural_renewable_microgrid_load_balancer() -> None:
    balancer = OfflineRuralRenewableMicroGridLoadBalancer()
    grids = balancer.balance_centre_microgrids()
    assert len(grids) == 3
    assert round(sum(g.solar_generation_wh for g in grids), 2) == 7400.0
    assert round(sum(g.reserve_fraction for g in grids) / len(grids), 4) == 0.30
    assert all(g.zero_brownout_verified for g in grids)


def test_g18_02_alumni_to_sathi_peer_mentorship_ledger() -> None:
    records = AlumniToSathiPeerMentorshipLedger.audit_alumni_mentorship_cycles()
    assert len(records) == 3
    assert sum(r.mentees_count for r in records) == 45
    assert sum(r.seva_honorarium_tokens for r in records) == 540
    assert round(sum(r.mentee_mastery_delta for r in records) / len(records), 4) == 0.23
    assert all(r.zero_pii_verified for r in records)


def test_g18_03_one_million_learner_sovereign_seal_and_html5_qa() -> None:
    seal = OneMillionLearnerSovereignImpactSeal(REPO_ROOT)
    summary = seal.execute_chunk_g18_microgrid_and_alumni_cycle()
    assert summary["chunk_id"] == "G18"
    assert summary["one_million_learner_sovereign_seal"]["learners_certified"] == 1000000
    assert summary["one_million_learner_sovereign_seal"]["completed_chunks_count"] == 36
    assert summary["microgrid_alumni_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["microgrid_alumni_html_bundle"]["under_20mib_ceiling"] is True


def test_g18_04_end_to_end_chunk_g18_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g18_microgrid_and_alumni_sync(REPO_ROOT)
    assert summary["status"] == "G18_RENEWABLE_MICROGRID_ALUMNI_MENTORSHIP_AND_1M_LEARNER_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G19:")
