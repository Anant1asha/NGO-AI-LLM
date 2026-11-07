"""
Unit, Byzantine Quorum Consensus, Work-Stealing Deque & Wait-For Graph Deadlock Test Suite
for TASK-AIOS-FORK-JOIN-ORCHESTRATOR (Cycle 3) (16 tests -> 332/332 cumulative).
"""
from __future__ import annotations

import pathlib
import pytest

from aasha.orchestrator.consensus_work_stealing import (
    AgentCandidateVote,
    ConsensusQuorumFailureError,
    DeadlockCycleDetectedError,
    DeadlockFreeWorkStealingScheduler,
    MultiAgentConsensusVerifier,
    ScheduledWorkItem,
    compare_fork_join_cycle3_consensus_and_work_stealing,
)


def test_fjc3_01_canonical_fingerprint_is_key_order_independent() -> None:
    p1 = {"b": 2, "a": "$F = m \\cdot a$", "c": [1, 2]}
    p2 = {"a": "$F = m \\cdot a$", "c": [1, 2], "b": 2}
    assert MultiAgentConsensusVerifier.canonical_fingerprint(p1) == MultiAgentConsensusVerifier.canonical_fingerprint(p2)


def test_fjc3_02_extract_invariants_captures_formulas_and_standalone_numbers() -> None:
    payload = {"eq": "$v = u + a \\cdot t$", "mass_kg": 12.5, "steps": 3}
    inv = MultiAgentConsensusVerifier.extract_invariants(payload)
    assert "$v = u + a \\cdot t$" in inv["formulas"]
    assert "12.5" in inv["numbers"]
    assert "3" in inv["numbers"]


def test_fjc3_03_verify_quorum_reaches_consensus_and_quarantines_byzantine_agent() -> None:
    anchor = {"eq": "$F = m \\cdot a$", "force": 50}
    votes = [
        AgentCandidateVote("ag1", {"eq": "$F = m \\cdot a$", "force": 50}, 0.95),
        AgentCandidateVote("ag2", {"eq": "$F = m \\cdot a$", "force": 50}, 0.92),
        AgentCandidateVote("ag3_byzantine", {"eq": "$F = m / a$", "force": 999}, 0.85),
    ]
    res = MultiAgentConsensusVerifier.verify_quorum(votes, canonical_anchor=anchor)
    assert res["consensus_reached"] is True
    assert res["winning_vote_count"] == 2
    assert res["quarantined_count"] == 1
    assert res["quarantined_agents"][0]["agent_id"] == "ag3_byzantine"


def test_fjc3_04_verify_quorum_quarantines_minority_divergent_agent_without_anchor() -> None:
    votes = [
        AgentCandidateVote("ag1", {"node": "A", "val": 10}, 0.90),
        AgentCandidateVote("ag2", {"node": "A", "val": 10}, 0.88),
        AgentCandidateVote("ag3", {"node": "B", "val": 20}, 0.70),
    ]
    res = MultiAgentConsensusVerifier.verify_quorum(votes)
    assert res["consensus_reached"] is True
    assert res["winning_payload"]["node"] == "A"
    assert res["quarantined_count"] == 1
    assert res["quarantined_agents"][0]["reason"] == "MINORITY_DIVERGENCE"


def test_fjc3_05_verify_quorum_raises_when_below_minimum_quorum_ratio() -> None:
    votes = [
        AgentCandidateVote("ag1", {"v": 1}, 0.9),
        AgentCandidateVote("ag2", {"v": 2}, 0.9),
        AgentCandidateVote("ag3", {"v": 3}, 0.9),
    ]
    with pytest.raises(ConsensusQuorumFailureError):
        MultiAgentConsensusVerifier.verify_quorum(votes, min_quorum_ratio=0.60)


def test_fjc3_06_verify_quorum_rejects_empty_or_invalid_confidence_votes() -> None:
    with pytest.raises(ConsensusQuorumFailureError):
        MultiAgentConsensusVerifier.verify_quorum([])

    votes = [
        AgentCandidateVote("bad_empty", {}, 0.9),
        AgentCandidateVote("bad_conf", {"ok": 1}, 1.5),
    ]
    with pytest.raises(ConsensusQuorumFailureError):
        MultiAgentConsensusVerifier.verify_quorum(votes)


def test_fjc3_07_work_stealing_reduces_skewed_makespan_over_50_percent() -> None:
    sched = DeadlockFreeWorkStealingScheduler(num_workers=4)
    for i, c in enumerate([60.0, 50.0, 45.0, 35.0, 25.0, 15.0]):
        sched.push_task(0, ScheduledWorkItem(f"t_{i}", c, 0))
    for w in (1, 2, 3):
        sched.push_task(w, ScheduledWorkItem(f"l_{w}", 10.0, w))

    res = sched.rebalance_via_work_stealing()
    assert res["initial_makespan_ms"] == 230.0
    assert res["final_makespan_ms"] < 100.0
    assert res["makespan_reduction_pct"] >= 55.0
    assert res["steals_performed"] >= 4


def test_fjc3_08_work_stealing_preserves_total_task_count_and_total_work_ms() -> None:
    sched = DeadlockFreeWorkStealingScheduler(num_workers=3)
    for i in range(6):
        sched.push_task(0, ScheduledWorkItem(f"task_{i}", 20.0, 0))
    res = sched.rebalance_via_work_stealing()
    total_tasks = sum(len(d) for d in sched.deques)
    assert total_tasks == 6
    assert round(sum(res["worker_loads_ms"]), 2) == 120.0


def test_fjc3_09_work_stealing_is_noop_when_already_balanced() -> None:
    sched = DeadlockFreeWorkStealingScheduler(num_workers=2)
    sched.push_task(0, ScheduledWorkItem("t0", 30.0, 0))
    sched.push_task(1, ScheduledWorkItem("t1", 30.0, 1))
    res = sched.rebalance_via_work_stealing()
    assert res["steals_performed"] == 0
    assert res["final_makespan_ms"] == 30.0


def test_fjc3_10_scheduler_rejects_zero_or_negative_worker_count() -> None:
    with pytest.raises(ValueError):
        DeadlockFreeWorkStealingScheduler(num_workers=0)


def test_fjc3_11_wfg_deadlock_detector_passes_acyclic_lock_graph() -> None:
    edges = [("ag1", "ag2"), ("ag2", "ag3"), ("ag1", "ag3")]
    res = DeadlockFreeWorkStealingScheduler.detect_and_resolve_wfg_deadlocks(edges)
    assert res["deadlock_free"] is True
    assert res["cycles_detected_and_preempted"] == 0
    assert len(res["remaining_edges"]) == 3


def test_fjc3_12_wfg_deadlock_detector_preempts_single_and_multi_cycles() -> None:
    edges = [
        ("a", "b"),
        ("b", "c"),
        ("c", "a"),
        ("x", "y"),
        ("y", "x"),
    ]
    res = DeadlockFreeWorkStealingScheduler.detect_and_resolve_wfg_deadlocks(edges, auto_preempt=True)
    assert res["deadlock_free"] is True
    assert res["cycles_detected_and_preempted"] == 2
    # Verify remaining graph is strictly acyclic
    recheck = DeadlockFreeWorkStealingScheduler.detect_and_resolve_wfg_deadlocks(
        res["remaining_edges"], auto_preempt=False
    )
    assert recheck["cycles_detected_and_preempted"] == 0


def test_fjc3_13_wfg_deadlock_detector_raises_when_auto_preempt_disabled() -> None:
    edges = [("ag1", "ag2"), ("ag2", "ag1")]
    with pytest.raises(DeadlockCycleDetectedError):
        DeadlockFreeWorkStealingScheduler.detect_and_resolve_wfg_deadlocks(edges, auto_preempt=False)


def test_fjc3_14_stolen_tasks_update_assigned_worker_id() -> None:
    sched = DeadlockFreeWorkStealingScheduler(num_workers=2)
    sched.push_task(0, ScheduledWorkItem("t1", 40.0, 0))
    sched.push_task(0, ScheduledWorkItem("t2", 40.0, 0))
    sched.rebalance_via_work_stealing()
    assert sched.deques[1][0].assigned_worker_id == 1


def test_fjc3_15_js_consensus_work_stealing_module_present_and_valid() -> None:
    js_txt = pathlib.Path("scripts/aasha_consensus_work_stealing.js").read_text(encoding="utf-8")
    assert "MultiAgentConsensusVerifierJS" in js_txt
    assert "DeadlockFreeWorkStealingSchedulerJS" in js_txt


def test_fjc3_16_compare_fork_join_cycle3_consensus_and_work_stealing_benchmark() -> None:
    bench = compare_fork_join_cycle3_consensus_and_work_stealing()
    assert bench["winner"] == "method-b-byzantine-quorum-consensus-and-work-stealing-scheduler"
    mb = bench["method_b_consensus_work_stealing"]
    assert mb["makespan_reduction_pct"] >= 55.0
    assert mb["byzantine_agents_quarantined"] == 1
    assert mb["deadlock_cycles_preempted"] == 2
    assert mb["deadlock_free_verified"] is True
