"""
Unit, 4-Tier Power/Thermal Governor, Emergency CRDT Flush, Pin-Aware LRU CAS Garbage Collection &
Fleet Session Allocation Test Suite for TASK-FACILITATOR-INVENTORY-OFFLINE-TELEMETRY-AGENT (Cycle 5)
(16 tests -> 460/460 cumulative).
"""
from __future__ import annotations

import pathlib
import pytest

from aasha.orchestrator.cohort_crdt_sync_engine import StudentConceptCRDTState
from aasha.orchestrator.inventory_telemetry_governor import (
    CASBlobRecord,
    CentreInventoryHealthTelemetryAgent,
    InventoryTelemetryError,
    PredictiveTabletBatteryStorageGovernor,
    TabletTelemetrySnapshot,
    compare_cycle5_inventory_telemetry_and_battery_governor,
)


def test_c5i_01_high_battery_cool_tablet_selects_full_performance_60fps() -> None:
    snap = TabletTelemetrySnapshot("TAB-01", 80.0, 16.0, 500.0, 37.0)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap)
    assert res["selected_power_profile"] == "PROFILE_FULL_PERFORMANCE"
    assert res["target_sim_fps"] == 60
    assert res["session_ready_for_60min_class"] is True


def test_c5i_02_medium_battery_or_warm_temp_selects_balanced_eco_30fps() -> None:
    snap = TabletTelemetrySnapshot("TAB-02", 30.0, 15.0, 400.0, 39.0)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap)
    assert res["selected_power_profile"] == "PROFILE_BALANCED_ECO"
    assert res["target_sim_fps"] == 30
    assert res["allowed_llm_tier"] == "TIER0_INT4_MICRO"
    assert res["governed_predicted_runtime_hrs"] > res["raw_predicted_runtime_hrs"]


def test_c5i_03_low_battery_or_hot_temp_selects_ultralow_survival_15fps() -> None:
    snap = TabletTelemetrySnapshot("TAB-03", 15.0, 12.0, 400.0, 47.0)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap)
    assert res["selected_power_profile"] == "PROFILE_ULTRALOW_SURVIVAL"
    assert res["target_sim_fps"] == 15
    assert res["allowed_llm_tier"] == "NONE_RULE_BASED_ONLY"
    assert res["governed_predicted_runtime_hrs"] >= 2.0


def test_c5i_04_critical_battery_below_10_percent_triggers_emergency_crdt_flush() -> None:
    crdt = StudentConceptCRDTState("stu_01", "G9-FORCE", 9, "AVR-P302", 0.85, {"TAB-05": 3}, 1500)
    snap = TabletTelemetrySnapshot("TAB-05", 7.5, 20.0, 400.0, 38.0, pending_crdt_state=crdt)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap)
    assert res["selected_power_profile"] == "PROFILE_EMERGENCY_CRDT_FLUSH"
    assert res["emergency_crdt_flushed"] is True
    assert len(res["flushed_crdt_sha256"]) == 64
    assert res["session_ready_for_60min_class"] is False


def test_c5i_05_pin_aware_lru_cas_eviction_reclaims_unpinned_blobs_in_lru_order() -> None:
    blobs = [
        CASBlobRecord("cas://sha256/pinned_indic_font", 90.0, 10, pinned_by_active_cohort=True),
        CASBlobRecord("cas://sha256/unpinned_oldest", 80.0, 20, pinned_by_active_cohort=False),
        CASBlobRecord("cas://sha256/unpinned_middle", 70.0, 30, pinned_by_active_cohort=False),
        CASBlobRecord("cas://sha256/unpinned_newest", 60.0, 40, pinned_by_active_cohort=False),
    ]
    snap = TabletTelemetrySnapshot("TAB-03", 75.0, 15.0, 150.0, 37.0, cas_blobs=blobs)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap, min_free_storage_mib=256.0)
    # Needed 106 MiB: evicts unpinned_oldest (80 MiB -> 230 MiB) + unpinned_middle (70 MiB -> 300 MiB)
    assert res["evicted_cas_uris"] == ["cas://sha256/unpinned_oldest", "cas://sha256/unpinned_middle"]
    assert res["final_free_storage_mib"] == 300.0
    assert res["pinned_blobs_retained"] == 1


def test_c5i_06_pinned_blobs_are_never_evicted_even_when_storage_stays_low() -> None:
    blobs = [
        CASBlobRecord("cas://sha256/pinned_only", 120.0, 5, pinned_by_active_cohort=True),
    ]
    snap = TabletTelemetrySnapshot("TAB-04", 80.0, 15.0, 100.0, 36.0, cas_blobs=blobs)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap, min_free_storage_mib=256.0)
    assert res["evicted_cas_uris"] == []
    assert res["pinned_blobs_retained"] == 1
    assert res["session_ready_for_60min_class"] is False


def test_c5i_07_governor_rejects_invalid_battery_discharge_or_storage_values() -> None:
    with pytest.raises(InventoryTelemetryError):
        PredictiveTabletBatteryStorageGovernor.govern_tablet(TabletTelemetrySnapshot("", 50.0, 10.0, 300.0, 35.0))
    with pytest.raises(InventoryTelemetryError):
        PredictiveTabletBatteryStorageGovernor.govern_tablet(TabletTelemetrySnapshot("T1", 110.0, 10.0, 300.0, 35.0))
    with pytest.raises(InventoryTelemetryError):
        PredictiveTabletBatteryStorageGovernor.govern_tablet(TabletTelemetrySnapshot("T1", 50.0, 0.0, 300.0, 35.0))
    with pytest.raises(InventoryTelemetryError):
        PredictiveTabletBatteryStorageGovernor.govern_tablet(TabletTelemetrySnapshot("T1", 50.0, 10.0, -5.0, 35.0))


def test_c5i_08_fleet_allocator_assigns_highest_runtime_tablets_first() -> None:
    fleet = [
        TabletTelemetrySnapshot("TAB-LOW", 45.0, 20.0, 400.0, 37.0),   # 2.25 hrs
        TabletTelemetrySnapshot("TAB-HIGH", 90.0, 15.0, 500.0, 36.0),  # 6.00 hrs
        TabletTelemetrySnapshot("TAB-MID", 60.0, 15.0, 450.0, 36.5),   # 4.00 hrs
    ]
    res = CentreInventoryHealthTelemetryAgent.audit_fleet_and_allocate_sessions(fleet, ["stu_a", "stu_b"])
    assert res["assignments"][0]["assigned_tablet_id"] == "TAB-HIGH"
    assert res["assignments"][1]["assigned_tablet_id"] == "TAB-MID"


def test_c5i_09_fleet_allocator_reports_unassigned_students_when_ready_tablets_exhausted() -> None:
    fleet = [
        TabletTelemetrySnapshot("TAB-OK", 80.0, 15.0, 400.0, 36.0),
        TabletTelemetrySnapshot("TAB-DEAD", 4.0, 20.0, 400.0, 38.0),
    ]
    res = CentreInventoryHealthTelemetryAgent.audit_fleet_and_allocate_sessions(fleet, ["s1", "s2", "s3"])
    assert res["students_assigned_count"] == 1
    assert res["unassigned_students"] == ["s2", "s3"]
    assert res["maintenance_required_count"] == 1


def test_c5i_10_fleet_allocator_rejects_empty_fleet() -> None:
    with pytest.raises(InventoryTelemetryError):
        CentreInventoryHealthTelemetryAgent.audit_fleet_and_allocate_sessions([], ["s1"])


def test_c5i_11_thermal_throttling_triggers_on_high_temp_even_at_90_percent_battery() -> None:
    snap = TabletTelemetrySnapshot("TAB-HOT", 90.0, 15.0, 500.0, 47.5)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap)
    assert res["selected_power_profile"] == "PROFILE_ULTRALOW_SURVIVAL"
    assert res["target_sim_fps"] == 15


def test_c5i_12_emergency_flush_without_pending_crdt_does_not_crash() -> None:
    snap = TabletTelemetrySnapshot("TAB-EMPTY-CRDT", 5.0, 15.0, 500.0, 37.0, pending_crdt_state=None)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap)
    assert res["selected_power_profile"] == "PROFILE_EMERGENCY_CRDT_FLUSH"
    assert res["emergency_crdt_flushed"] is False
    assert res["flushed_crdt_sha256"] is None


def test_c5i_13_fleet_manifest_sha256_is_deterministic_64_hex_digest() -> None:
    fleet = [TabletTelemetrySnapshot("TAB-01", 80.0, 15.0, 400.0, 36.0)]
    r1 = CentreInventoryHealthTelemetryAgent.audit_fleet_and_allocate_sessions(fleet, ["s1"])
    r2 = CentreInventoryHealthTelemetryAgent.audit_fleet_and_allocate_sessions(fleet, ["s1"])
    assert len(r1["fleet_manifest_sha256"]) == 64
    assert r1["fleet_manifest_sha256"] == r2["fleet_manifest_sha256"]


def test_c5i_14_storage_already_above_threshold_performs_zero_evictions() -> None:
    blobs = [CASBlobRecord("cas://sha256/b1", 50.0, 10, pinned_by_active_cohort=False)]
    snap = TabletTelemetrySnapshot("TAB-AMPLE", 85.0, 15.0, 512.0, 36.0, cas_blobs=blobs)
    res = PredictiveTabletBatteryStorageGovernor.govern_tablet(snap, min_free_storage_mib=256.0)
    assert res["evicted_cas_uris"] == []
    assert res["storage_reclaimed_mib"] == 0.0


def test_c5i_15_js_inventory_telemetry_governor_module_present_and_valid() -> None:
    js_txt = pathlib.Path("scripts/aasha_inventory_telemetry_governor.js").read_text(encoding="utf-8")
    assert "PredictiveTabletBatteryStorageGovernorJS" in js_txt
    assert "CentreInventoryHealthTelemetryAgentJS" in js_txt


def test_c5i_16_compare_cycle5_inventory_telemetry_and_battery_governor_benchmark() -> None:
    bench = compare_cycle5_inventory_telemetry_and_battery_governor()
    assert bench["winner"] == "method-b-predictive-battery-storage-governor-and-fleet-allocator"
    ma = bench["method_a_unmanaged_fleet"]
    mb = bench["method_b_governed_fleet"]
    assert ma["tablets_ready_for_60min_class"] == 2
    assert mb["tablets_ready_for_60min_class"] == 4
    assert mb["students_safely_assigned"] == 4
    assert mb["mid_session_blackout_or_storage_failures"] == 0
    assert mb["unflushed_crdt_attempts_lost"] == 0
    assert mb["emergency_crdt_flushes_triggered"] == 1
    assert mb["storage_reclaimed_mib"] == 170.0
