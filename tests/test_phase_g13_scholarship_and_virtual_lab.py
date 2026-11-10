"""
Unit Tests for Phase G: Chunk G13 (Autonomous Offline Rural Micro-Scholarship & Continuity
Predictor, Interactive Science Virtual Lab Kit & 25,000-Centre Block Federation Seal)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g13_scholarship_and_virtual_lab import (
    InteractiveScienceVirtualLabKit,
    OfflineRuralMicroScholarshipDisburser,
    TwentyFiveThousandCentreBlockFederationSeal,
    execute_chunk_g13_scholarship_and_virtual_lab_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g13_01_offline_rural_micro_scholarship_disburser() -> None:
    awards = OfflineRuralMicroScholarshipDisburser.evaluate_micro_scholarships()
    assert len(awards) == 3
    assert all(a.zero_pii_verified for a in awards)
    assert sum(a.scholarship_seva_tokens for a in awards) == 700
    assert round(sum(a.composite_continuity_index for a in awards) / len(awards), 4) == 0.8883


def test_g13_02_interactive_science_virtual_lab_kit() -> None:
    kit = InteractiveScienceVirtualLabKit()
    labs = kit.build_virtual_lab_experiments()
    assert len(labs) == 3
    assert round(sum(l.simulation_accuracy for l in labs) / len(labs), 4) == 0.992


def test_g13_03_twenty_five_thousand_centre_seal_and_html5_qa() -> None:
    seal = TwentyFiveThousandCentreBlockFederationSeal(REPO_ROOT)
    summary = seal.execute_chunk_g13_scholarship_and_vlab_cycle()
    assert summary["chunk_id"] == "G13"
    assert summary["twenty_five_thousand_centre_block_seal"]["centres_certified"] == 25000
    assert summary["twenty_five_thousand_centre_block_seal"]["completed_chunks_count"] == 31
    assert summary["scholarship_vlab_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["scholarship_vlab_html_bundle"]["under_20mib_ceiling"] is True


def test_g13_04_end_to_end_chunk_g13_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g13_scholarship_and_virtual_lab_sync(REPO_ROOT)
    assert summary["status"] == "G13_MICRO_SCHOLARSHIP_VIRTUAL_LAB_AND_25000_CENTRE_SEAL_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G14:")
