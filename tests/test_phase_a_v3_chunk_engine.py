"""
Unit, 9Router Failover, Bounded 2-Worker Concurrency Lock, 4-Tier Persistent Memory Self-Heal,
3-Plane State Schema Lock & Zero-No-Op Commit Guard Test Suite for
AASHA-ARGON-SUPERADMIN-AUTONOMOUS-BUILDER-V3 Phase A (Chunks A1, A2, A3)
(16 tests -> 508/508 cumulative Python unit tests).
"""
from __future__ import annotations

import copy
import pathlib
import tempfile
import pytest

from aasha.orchestrator.phase_a_foundation_hardening import (
    ConcurrencyLockContentionError,
    NineRouterGatewayFailoverManager,
    PersistentFourTierMemoryHealthVerifier,
    REQUIRED_TARGET_BRANCH,
    StateSchemaLockError,
    UnifiedThreePlaneStateSchemaLock,
    ZeroNoOpCommitGuard,
    compare_phase_a_v3_foundation_and_router_hardening,
)


def test_pa_01_nominal_9router_route_selects_local_proxy_with_zero_cost() -> None:
    mgr = NineRouterGatewayFailoverManager(daily_spend_usd=0.0)
    res = mgr.select_active_route("coding", offline_mode=False)
    assert res["selected_provider"] == "9router_local"
    assert res["selected_tier"] == "TIER_1_9ROUTER_LOCAL_PROXY"
    assert res["cost_usd"] == 0.0
    assert res["allow_paid_gemini_fallback"] is False
    assert res["failover_hops"] == 0


def test_pa_02_failover_cascades_across_openrouter_groq_and_local_slm() -> None:
    mgr = NineRouterGatewayFailoverManager(daily_spend_usd=0.0)
    res1 = mgr.select_active_route("coding", simulated_down_providers=["9router_local"])
    assert res1["selected_provider"] == "openrouter_free"
    assert res1["failover_hops"] == 1

    res2 = mgr.select_active_route("coding", simulated_down_providers=["9router_local", "openrouter_free", "groq_free"])
    assert res2["selected_provider"] == "local_slm_int4"
    assert res2["selected_tier"] == "TIER_2_LOCAL_QUANTIZED_SLM"


def test_pa_03_circuit_breaker_trips_open_after_two_failures_and_recovers_on_success() -> None:
    mgr = NineRouterGatewayFailoverManager(failure_threshold=2)
    assert mgr.record_provider_failure("9router_local") == "CLOSED"
    assert mgr.record_provider_failure("9router_local") == "OPEN"
    res = mgr.select_active_route("coding")
    assert res["selected_provider"] == "openrouter_free"

    assert mgr.record_provider_success("9router_local") == "CLOSED"
    res_recovered = mgr.select_active_route("coding")
    assert res_recovered["selected_provider"] == "9router_local"


def test_pa_04_con008_spend_cap_and_offline_mode_clamp_to_tier0_deterministic() -> None:
    mgr_cap = NineRouterGatewayFailoverManager(daily_spend_usd=1.00)
    res_cap = mgr_cap.select_active_route("coding", offline_mode=False)
    assert res_cap["selected_provider"] == "tier0_deterministic"
    assert res_cap["con008_clamped"] is True

    mgr_off = NineRouterGatewayFailoverManager(daily_spend_usd=0.10)
    res_off = mgr_off.select_active_route("coding", offline_mode=True)
    assert res_off["selected_provider"] == "tier0_deterministic"
    assert res_off["offline_clamped"] is True


def test_pa_05_bounded_2_worker_concurrency_lock_enforces_rg001_and_evicts_stale_locks() -> None:
    mgr = NineRouterGatewayFailoverManager(max_concurrent_workers=2)
    l1 = mgr.acquire_worker_lock("worker_1", "A1", ttl_ms=1000, now_ms=1000)
    l2 = mgr.acquire_worker_lock("worker_2", "A2", ttl_ms=1000, now_ms=1000)
    assert l1["chunk_id"] == "A1"
    assert l2["chunk_id"] == "A2"

    # 3rd worker must be blocked while 2 workers hold active locks
    with pytest.raises(ConcurrencyLockContentionError):
        mgr.acquire_worker_lock("worker_3", "A3", ttl_ms=1000, now_ms=1500)

    # Duplicate lock on A1 by another worker must fail
    with pytest.raises(ConcurrencyLockContentionError):
        mgr.acquire_worker_lock("worker_2", "A1", ttl_ms=1000, now_ms=1500)

    # After TTL expiration (now_ms=2500 > 1000+1000), stale locks are evicted automatically
    l3 = mgr.acquire_worker_lock("worker_3", "A3", ttl_ms=1000, now_ms=2500)
    assert l3["stale_locks_evicted"] == 2
    assert mgr.release_worker_lock("worker_3", "A3") is True


def test_pa_06_persistent_four_tier_memory_verifier_self_heals_all_four_tiers() -> None:
    tmp_dir = pathlib.Path(tempfile.mkdtemp())
    report = PersistentFourTierMemoryHealthVerifier.verify_and_heal(tmp_dir)
    assert report["overall_status"] == "PRIMED_AND_HEALTHY"
    assert report["tiers_healthy_count"] == 4
    assert report["tiers"]["tier_1_serena"]["records"] == 7
    assert report["tiers"]["tier_2_mem0"]["records"] >= 2
    assert report["tiers"]["tier_3_sqlite"]["records"] >= 1
    assert report["tiers"]["tier_4_graphify"]["records"] >= 3
    assert len(report["memory_health_sha256"]) == 64


def test_pa_07_memory_verifier_recovers_corrupted_mem0_and_graphify_files() -> None:
    tmp_dir = pathlib.Path(tempfile.mkdtemp())
    (tmp_dir / ".scratch").mkdir(parents=True, exist_ok=True)
    (tmp_dir / ".scratch" / "mem0_store.json").write_text("{corrupted_json", encoding="utf-8")
    (tmp_dir / "graphify-out").mkdir(parents=True, exist_ok=True)
    (tmp_dir / "graphify-out" / "graph.json").write_text("not_json", encoding="utf-8")

    report = PersistentFourTierMemoryHealthVerifier.verify_and_heal(tmp_dir)
    assert report["overall_status"] == "PRIMED_AND_HEALTHY"
    assert any("mem0_store.json" in a for a in report["actions_taken"])
    assert any("graph.json" in a for a in report["actions_taken"])


def test_pa_08_unified_state_schema_lock_resolves_chunk_progression_order() -> None:
    p0, c0, _ = UnifiedThreePlaneStateSchemaLock.resolve_next_chunk([])
    assert (p0, c0) == ("PHASE_A_FOUNDATION_AND_ROUTER_HARDENING", "A1")

    p1, c1, _ = UnifiedThreePlaneStateSchemaLock.resolve_next_chunk(["A1"])
    assert (p1, c1) == ("PHASE_A_FOUNDATION_AND_ROUTER_HARDENING", "A2")

    p3, c3, _ = UnifiedThreePlaneStateSchemaLock.resolve_next_chunk(["A1", "A2", "A3"])
    assert (p3, c3) == ("PHASE_B_COMPILER_AND_LLE_PIPELINE", "B1")


def test_pa_09_unified_state_schema_lock_builds_identical_pc_and_colab_cursors() -> None:
    pc_state, colab_state, sha = UnifiedThreePlaneStateSchemaLock.build_synchronized_states(
        completed_chunks=["A1"],
        completed_chunk_id="A1",
        initialized_chunk_id="A1",
    )
    assert UnifiedThreePlaneStateSchemaLock.verify_pair_parity(pc_state, colab_state) is True
    assert pc_state["active_chunk_id"] == "A2"
    assert colab_state["active_chunk_id"] == "A2"
    assert pc_state["target_branch"] == REQUIRED_TARGET_BRANCH
    assert pc_state["cursor_lock_sha256"] == sha


def test_pa_10_state_schema_lock_rejects_main_or_master_target_branch() -> None:
    pc_state, _, _ = UnifiedThreePlaneStateSchemaLock.build_synchronized_states(completed_chunks=["A1"])
    bad_main = copy.deepcopy(pc_state)
    bad_main["target_branch"] = "main"
    with pytest.raises(StateSchemaLockError):
        UnifiedThreePlaneStateSchemaLock.validate_state_payload(bad_main)

    bad_master = copy.deepcopy(pc_state)
    bad_master["target_branch"] = "master"
    with pytest.raises(StateSchemaLockError):
        UnifiedThreePlaneStateSchemaLock.validate_state_payload(bad_master)


def test_pa_11_state_schema_lock_detects_pc_vs_colab_cursor_drift() -> None:
    pc_state, colab_state, _ = UnifiedThreePlaneStateSchemaLock.build_synchronized_states(completed_chunks=["A1"])
    drifted_colab = copy.deepcopy(colab_state)
    drifted_colab["active_chunk_id"] = "B1"
    with pytest.raises(StateSchemaLockError):
        UnifiedThreePlaneStateSchemaLock.verify_pair_parity(pc_state, drifted_colab)


def test_pa_12_zero_noop_commit_guard_blocks_report_and_timestamp_only_diffs() -> None:
    res = ZeroNoOpCommitGuard.evaluate_diff(
        staged_files=["CHANGELOG.md", "VERIFICATION_REPORT.md", "PC_ANTIGRAVITY_STATE.json", "COLAB_ANTIGRAVITY_STATE.json"],
        diff_text='+ "timestamp_utc": "2026-11-08T01:00:00Z"\n+ **Date**: 2026-11-08',
    )
    assert res["allow_commit"] is False
    assert res["reason"] == "ZERO_NO_OP_BLOCKED"
    assert res["functional_files_count"] == 0
    assert res["metadata_files_count"] == 4


def test_pa_13_zero_noop_commit_guard_allows_functional_code_and_test_edits() -> None:
    res = ZeroNoOpCommitGuard.evaluate_diff(
        staged_files=[
            "scripts/aasha_continuous_loop.mjs",
            "src/aasha/orchestrator/phase_a_foundation_hardening.py",
            "tests/test_phase_a_v3_chunk_engine.py",
            "CHANGELOG.md",
        ],
        diff_text='+ class NineRouterGatewayFailoverManager:\n+     pass',
    )
    assert res["allow_commit"] is True
    assert res["reason"] == "FUNCTIONAL_PROGRESS_VERIFIED"
    assert res["functional_files_count"] == 3
    assert res["metadata_files_count"] == 1
    assert len(res["functional_diff_sha256"]) == 64


def test_pa_14_zero_noop_commit_guard_blocks_functional_file_with_only_timestamp_comment() -> None:
    res = ZeroNoOpCommitGuard.evaluate_diff(
        staged_files=["scripts/aasha_continuous_loop.mjs"],
        diff_text='+ "timestamp_utc": "2026-11-08T01:00:00Z"',
    )
    assert res["allow_commit"] is False
    assert res["substantive_added_lines_count"] == 0


def test_pa_15_zero_noop_commit_guard_rejects_protected_branches() -> None:
    with pytest.raises(StateSchemaLockError):
        ZeroNoOpCommitGuard.evaluate_diff(
            staged_files=["scripts/aasha_continuous_loop.mjs"],
            diff_text="+ const x = 1;",
            target_branch="main",
        )


def test_pa_16_phase_a_benchmark_verifies_method_b_superiority() -> None:
    bm = compare_phase_a_v3_foundation_and_router_hardening()
    assert bm["winner"] == "method-b-v3-hybrid-3plane-chunk-engine-and-zero-noop-guard"
    assert bm["method_b_v3_chunk_engine"]["ninerouter_failover_survival_rate_pct"] == 100.0
    assert bm["method_b_v3_chunk_engine"]["three_plane_state_schema_parity"] is True
    assert bm["method_b_v3_chunk_engine"]["empty_noop_commits_blocked_out_of_5"] == 5
    assert bm["method_b_v3_chunk_engine"]["functional_commit_allowed"] is True
    assert bm["method_b_v3_chunk_engine"]["next_queued_chunk_after_phase_a"] == "B1"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ALL 16 PHASE A V3 CHUNK ENGINE TESTS PASSED!")
