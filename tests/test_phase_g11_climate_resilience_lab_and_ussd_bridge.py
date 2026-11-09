"""
Unit Tests for Phase G: Chunk G11 (Autonomous Rural Climate-Resilience Lab Simulator,
Vernacular Parent-Teacher SMS/USSD Offline Bridge & 5,000-Village Impact Ledger)
"""
from __future__ import annotations

import pathlib

from aasha.orchestrator.phase_g11_climate_resilience_lab_and_ussd_bridge import (
    FiveThousandVillageImpactLedger,
    RuralClimateResilienceLabSimulator,
    VernacularParentTeacherUssdSmsBridge,
    execute_chunk_g11_climate_lab_and_ussd_sync,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_g11_01_rural_climate_resilience_lab_simulator() -> None:
    sim = RuralClimateResilienceLabSimulator()
    results = sim.run_climate_lab_scenarios()
    assert len(results) == 3
    assert round(sum(r.harvested_rainwater_liters for r in results), 2) == 180640.0
    assert round(sum(r.water_saved_by_drip_liters for r in results), 2) == 81057.6
    assert round(sum(r.annual_co2_sequestered_kg for r in results), 2) == 1349.74


def test_g11_02_vernacular_parent_teacher_ussd_sms_bridge() -> None:
    packets = VernacularParentTeacherUssdSmsBridge.compile_nine_script_ussd_packets()
    assert len(packets) == 9
    assert all(p.within_140_byte_budget for p in packets)
    assert all(not p.pii_detected for p in packets)
    assert {p.lang_code for p in packets} == {"HI", "TA", "TE", "BN", "MR", "GU", "KN", "ML", "OR"}


def test_g11_03_five_thousand_village_ledger_and_html5_qa() -> None:
    ledger = FiveThousandVillageImpactLedger(REPO_ROOT)
    summary = ledger.execute_chunk_g11_climate_and_ussd_cycle()
    assert summary["chunk_id"] == "G11"
    assert summary["five_thousand_village_impact_ledger"]["villages_verified"] == 5000
    assert summary["five_thousand_village_impact_ledger"]["completed_chunks_count"] == 29
    assert summary["climate_ussd_html_bundle"]["ten_critical_qa_rules_passed"] == 10
    assert summary["climate_ussd_html_bundle"]["under_20mib_ceiling"] is True


def test_g11_04_end_to_end_chunk_g11_sync_and_oracle_proof() -> None:
    summary = execute_chunk_g11_climate_lab_and_ussd_sync(REPO_ROOT)
    assert summary["status"] == "G11_RURAL_CLIMATE_LAB_USSD_BRIDGE_AND_5000_VILLAGE_LEDGER_VERIFIED"
    assert summary["oracle_proof"]["passed"] is True
    assert summary["autonomous_authorization"]["authorized"] is True
    assert summary["autonomous_authorization"]["human_approval_required"] is False
    assert summary["next_focus_unit"].startswith("G12:")
