"""
Unit & Cryptographic Merkle Test Suite for TASK-LAYA-SYSTEM1-PREROUTER (Cycle 2):
LayaContextCompressor & MerkleSnapshotDiffEngine (tests/test_laya_cycle2_merkle_compression.py).
"""

from __future__ import annotations

import pytest
from aasha.benchmark.compare_methods import (
    compare_laya_cycle2_context_compression_and_merkle_diff,
    compare_laya_system1_prerouter_vs_cloud_router,
)
from aasha.laya_router.laya_system1_prerouter import (
    LayaContextCompressor,
    LineageTamperError,
    MerkleSnapshotDiffEngine,
)


def test_lc2_01_context_compressor_removes_duplicate_boilerplate_lines() -> None:
    turns = [
        "Status: Polling gateway 127.0.0.1:20128/v1/models",
        "Status: Polling gateway 127.0.0.1:20128/v1/models",
        "Status: Polling gateway 127.0.0.1:20128/v1/models",
        "Action: Execute TASK-WB-OFFLINE-CHAPTER-COMPILATION",
    ]
    res = LayaContextCompressor.compress_turns(turns)
    assert res["duplicate_lines_removed"] == 2
    assert res["compression_ratio_pct"] > 30.0
    assert "TASK-WB-OFFLINE-CHAPTER-COMPILATION" in res["compressed_text"]


def test_lc2_02_context_compressor_preserves_100_percent_of_latex_math_tokens() -> None:
    turns = [
        "Boilerplate line " * 10,
        "Verify linear balance $2x + 5 = 17$ and fraction $\\frac{3}{4} + \\frac{1}{4} = 1$.",
    ]
    res = LayaContextCompressor.compress_turns(turns, max_chars=256)
    assert res["math_preservation_pct"] == 100.0
    assert "$2x + 5 = 17$" in res["compressed_text"]
    assert "\\frac{3}{4}" in res["compressed_text"]
    assert "__AASHA_MATH_" not in res["compressed_text"]


def test_lc2_03_context_compressor_preserves_critical_task_and_avr_identifiers() -> None:
    turns = [
        "Noise line A",
        "Bind AVR-P309-math-cartesian-distance-section-sim in FOCUS-UNIT-PHASE-H-026.",
        "Noise line B",
    ]
    res = LayaContextCompressor.compress_turns(turns, max_chars=120)
    assert "AVR-P309-math-cartesian-distance-section-sim" in res["compressed_text"]
    assert "FOCUS-UNIT-PHASE-H-026" in res["compressed_text"]


def test_lc2_04_context_compressor_handles_empty_turns_gracefully() -> None:
    res = LayaContextCompressor.compress_turns([])
    assert res["compressed_text"] == ""
    assert res["raw_bytes"] == 0
    assert res["math_preservation_pct"] == 100.0


def test_lc2_05_merkle_root_is_deterministic_and_key_order_independent() -> None:
    p1 = {"b": 2, "a": 1, "c": [1, 2, 3]}
    p2 = {"c": [1, 2, 3], "a": 1, "b": 2}
    r1 = MerkleSnapshotDiffEngine.compute_merkle_root(p1)
    r2 = MerkleSnapshotDiffEngine.compute_merkle_root(p2)
    assert len(r1) == 64
    assert r1 == r2


def test_lc2_06_merkle_root_changes_on_single_leaf_mutation() -> None:
    p1 = {"ch1": {"nodes": 3}, "ch2": {"nodes": 4}}
    p2 = {"ch1": {"nodes": 3}, "ch2": {"nodes": 5}}
    assert MerkleSnapshotDiffEngine.compute_merkle_root(p1) != MerkleSnapshotDiffEngine.compute_merkle_root(p2)


def test_lc2_07_merkle_root_handles_empty_and_odd_leaf_counts() -> None:
    r_empty = MerkleSnapshotDiffEngine.compute_merkle_root({})
    r_three = MerkleSnapshotDiffEngine.compute_merkle_root({"k1": 1, "k2": 2, "k3": 3})
    assert len(r_empty) == 64
    assert len(r_three) == 64


def test_lc2_08_compute_structural_delta_identifies_added_modified_and_deleted_keys() -> None:
    base = {"keep": 10, "mod": "old", "del": True}
    targ = {"keep": 10, "mod": "new", "add": [1, 2]}
    delta = MerkleSnapshotDiffEngine.compute_structural_delta(base, targ)
    assert delta["added"] == {"add": [1, 2]}
    assert delta["modified"] == {"mod": "new"}
    assert delta["deleted"] == ["del"]
    assert delta["unchanged_count"] == 1


def test_lc2_09_apply_structural_delta_reconstructs_target_losslessly() -> None:
    base = {f"k_{i}": {"val": i, "data": "x" * 50} for i in range(20)}
    targ = dict(base)
    targ["k_5"] = {"val": 500, "data": "updated"}
    targ["k_new"] = {"val": 999}
    del targ["k_0"]

    delta = MerkleSnapshotDiffEngine.compute_structural_delta(base, targ)
    reconstructed = MerkleSnapshotDiffEngine.apply_structural_delta(base, delta)
    assert reconstructed == targ


def test_lc2_10_structural_delta_achieves_over_75_percent_storage_savings_on_34_chapters() -> None:
    base = {f"ch_{i:02d}": {"title": f"Chapter {i}", "wm_count": 600, "nodes": [1, 2, 3]} for i in range(34)}
    targ = dict(base)
    targ["ch_33"] = {"title": "Chapter 33 Updated", "wm_count": 600, "nodes": [1, 2, 3, 4]}
    delta = MerkleSnapshotDiffEngine.compute_structural_delta(base, targ)
    assert delta["storage_savings_pct"] >= 75.0


def test_lc2_11_apply_structural_delta_rejects_tampered_base_payload() -> None:
    base = {"a": 1, "b": 2}
    targ = {"a": 1, "b": 3}
    delta = MerkleSnapshotDiffEngine.compute_structural_delta(base, targ)
    tampered_base = {"a": 999, "b": 2}
    with pytest.raises(LineageTamperError):
        MerkleSnapshotDiffEngine.apply_structural_delta(tampered_base, delta)


def test_lc2_12_apply_structural_delta_rejects_tampered_delta_modified_payload() -> None:
    base = {"a": 1, "b": 2}
    targ = {"a": 1, "b": 3}
    delta = MerkleSnapshotDiffEngine.compute_structural_delta(base, targ)
    delta["modified"]["b"] = 999
    with pytest.raises(LineageTamperError):
        MerkleSnapshotDiffEngine.apply_structural_delta(base, delta)


def test_lc2_13_apply_structural_delta_does_not_mutate_input_base_dict() -> None:
    base = {"a": {"nested": [1, 2]}, "b": 2}
    targ = {"a": {"nested": [1, 2, 3]}, "b": 2}
    delta = MerkleSnapshotDiffEngine.compute_structural_delta(base, targ)
    _ = MerkleSnapshotDiffEngine.apply_structural_delta(base, delta)
    assert base["a"]["nested"] == [1, 2]


def test_lc2_14_compare_laya_cycle2_context_compression_and_merkle_diff_benchmark() -> None:
    bench = compare_laya_cycle2_context_compression_and_merkle_diff()
    assert bench["winner"] == "method-b-laya-context-compressor-merkle-delta-lineage"
    mb = bench["method_b_compressed_merkle"]
    assert mb["math_preservation_pct"] == 100.0
    assert mb["lossless_reconstruction_verified"] is True
    assert mb["delta_storage_savings_pct"] >= 75.0


def test_lc2_15_ts_merkle_snapshot_diff_engine_present_in_test_version_manager() -> None:
    import pathlib
    ts_code = pathlib.Path("scripts/test_version_manager.ts").read_text(encoding="utf-8")
    assert "MerkleSnapshotDiffEngineTS" in ts_code
    assert "computeMerkleRoot" in ts_code


def test_lc2_16_combined_laya_cycle1_and_cycle2_benchmarks_pass() -> None:
    b1 = compare_laya_system1_prerouter_vs_cloud_router()
    b2 = compare_laya_cycle2_context_compression_and_merkle_diff()
    assert b1["method_b"]["routing_tokens_consumed"] == 0
    assert b2["method_b_compressed_merkle"]["lossless_reconstruction_verified"] is True
