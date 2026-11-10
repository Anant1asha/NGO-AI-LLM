"""
Unit Tests for Phase G: Chunk G16 (Autonomous Offline Rural Livelihood Micro-Coop Ledger,
Multi-Grade Bridge Classroom Scheduler & 250,000-Centre Sovereign Bharat Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g16_livelihood_coop_and_multigrade_scheduler import (
    MultiGradeBridgeClassroomScheduler,
    OfflineRuralLivelihoodMicroCoopLedger,
    TwoHundredFiftyThousandCentreSovereignBharatSeal,
    execute_chunk_g16_livelihood_and_multigrade_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g16_01_offline_rural_livelihood_micro_coop_ledger() -> None:
    ledger = OfflineRuralLivelihoodMicroCoopLedger()
    entries = ledger.audit_micro_coop_ledgers()
    assert len(entries) == 3
    assert sum(e.net_surplus_credits for e in entries) == 1100
    assert round(sum(e.surplus_margin_pct for e in entries) / len(entries), 2) == 65.0
    assert all(e.zero_pii_verified for e in entries)


def test_g16_02_multigrade_bridge_classroom_scheduler() -> None:
    schedules = MultiGradeBridgeClassroomScheduler.generate_multigrade_schedules()
    assert len(schedules) == 3
    assert sum(s.students_count for s in schedules) == 90
    assert round(sum(s.tablet_utilization_ratio for s in schedules) / len(schedules), 4) == 0.97
    assert round(sum(s.facilitator_focus_gain_pct for s in schedules) / len(schedules), 2) == 42.0
    assert all(s.conflict_free_verified for s in schedules)


def test_g16_03_two_hundred_fifty_thousand_centre_seal_and_html5_qa() -> None:
    seal = TwoHundredFiftyThousandCentreSovereignBharatSeal(REPO_ROOT)
    summary = seal.execute_chunk_g16_livelihood_and_multigrade_cycle()
    assert summary["chunk_id"] == "G16"
    assert summary["two_hundred_fifty_thousand_centre_sovereign_seal"]["centres_certified"] == 250000
    assert summary["two_hundred_fifty_thousand_centre_sovereign_seal"]["completed_chunks_count"] == 34
    assert summary["livelihood_multigrade_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["livelihood_multigrade_html_bundle"]["under_20mib_ceiling"] is True


def test_g16_04_end_to_end_chunk_g16_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g16_livelihood_and_multigrade_sync(REPO_ROOT)
    assert summary["status"] == "G16_LIVELIHOOD_COOP_MULTIGRADE_SCHEDULER_AND_250000_CENTRE_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G17:")
