"""
Unit, Zlib QR/UDP Frame Segmenter, XOR Parity FEC Packet-Drop Recovery, Out-of-Order
Reassembly, SHA-256 Tamper Guard & N-Peer Anti-Entropy Gossip Test Suite for
TASK-OFFLINE-P2P-MESH-SYNC-PROTOCOL (Cycle 6) (16 tests -> 492/492 cumulative).
"""
from __future__ import annotations

import copy
import pathlib
import pytest

from aasha.orchestrator.cohort_crdt_sync_engine import StudentConceptCRDTState
from aasha.orchestrator.offline_p2p_mesh_sync import (
    MeshChunkTamperError,
    MeshProtocolConfigError,
    OfflineQRAndMeshChunkEncoder,
    PeerToPeerMeshGossipSynchronizer,
    compare_cycle6_offline_p2p_mesh_and_qr_fec_sync,
)


def _sample_payload() -> dict:
    return {
        "centre_id": "AASHA-UP-NOIDA-01",
        "chapters": [
            {"id": f"NCERT-G9-CH{i:02d}", "mastery": 0.82, "title_hi": "बल तथा गति के नियम"}
            for i in range(1, 15)
        ],
    }


def test_c6m_01_encode_and_decode_roundtrip_reconstructs_exact_payload() -> None:
    payload = _sample_payload()
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_01", payload, chunk_size_bytes=64, stripe_k=4)
    dec = OfflineQRAndMeshChunkEncoder.decode_frames_to_payload(enc["frames"])
    assert dec["payload"] == payload
    assert dec["payload_sha256"] == enc["payload_sha256"]
    assert dec["fec_chunks_recovered_count"] == 0


def test_c6m_02_zlib_compression_reduces_json_payload_bytes_by_over_50_percent() -> None:
    payload = _sample_payload()
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_02", payload, chunk_size_bytes=128)
    assert enc["compression_savings_pct"] >= 50.0


def test_c6m_03_out_of_order_frame_arrival_reassembles_losslessly() -> None:
    payload = _sample_payload()
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_03", payload, chunk_size_bytes=64)
    reversed_frames = list(reversed(enc["frames"]))
    dec = OfflineQRAndMeshChunkEncoder.decode_frames_to_payload(reversed_frames)
    assert dec["payload"] == payload


def test_c6m_04_xor_fec_recovers_single_dropped_data_chunk_per_stripe() -> None:
    payload = _sample_payload()
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_04", payload, chunk_size_bytes=64, stripe_k=4)
    assert enc["total_data_chunks"] >= 2
    # Drop chunk_index 1
    lossy_frames = [f for f in enc["frames"] if not (f["frame_type"] == "DATA" and f["chunk_index"] == 1)]
    dec = OfflineQRAndMeshChunkEncoder.decode_frames_to_payload(lossy_frames)
    assert dec["payload"] == payload
    assert dec["fec_recovered_chunk_indices"] == [1]


def test_c6m_05_xor_fec_recovers_dropped_final_padded_chunk() -> None:
    payload = _sample_payload()
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_05", payload, chunk_size_bytes=64, stripe_k=4)
    last_idx = enc["total_data_chunks"] - 1
    lossy_frames = [f for f in enc["frames"] if not (f["frame_type"] == "DATA" and f["chunk_index"] == last_idx)]
    dec = OfflineQRAndMeshChunkEncoder.decode_frames_to_payload(lossy_frames)
    assert dec["payload"] == payload
    assert dec["fec_recovered_chunk_indices"] == [last_idx]


def test_c6m_06_dropping_two_chunks_in_same_stripe_raises_unrecoverable_error() -> None:
    payload = _sample_payload()
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_06", payload, chunk_size_bytes=48, stripe_k=4)
    assert enc["total_data_chunks"] >= 2
    # Drop both chunk 0 and chunk 1 from stripe 0
    too_lossy = [
        f for f in enc["frames"]
        if not (f["frame_type"] == "DATA" and f["chunk_index"] in (0, 1))
    ]
    with pytest.raises(MeshChunkTamperError):
        OfflineQRAndMeshChunkEncoder.decode_frames_to_payload(too_lossy)


def test_c6m_07_tampered_frame_data_or_sha256_raises_tamper_error() -> None:
    payload = _sample_payload()
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_07", payload, chunk_size_bytes=64)
    tampered = copy.deepcopy(enc["frames"])
    tampered[0]["chunk_sha256"] = "0" * 64
    with pytest.raises(MeshChunkTamperError):
        OfflineQRAndMeshChunkEncoder.decode_frames_to_payload(tampered)


def test_c6m_08_decode_rejects_empty_or_parity_only_frame_list() -> None:
    with pytest.raises(MeshChunkTamperError):
        OfflineQRAndMeshChunkEncoder.decode_frames_to_payload([])
    enc = OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("sess_08", {"a": 1}, chunk_size_bytes=64)
    parity_only = [f for f in enc["frames"] if f["frame_type"] == "PARITY"]
    with pytest.raises(MeshChunkTamperError):
        OfflineQRAndMeshChunkEncoder.decode_frames_to_payload(parity_only)


def test_c6m_09_encode_rejects_empty_session_id_or_small_chunk_size() -> None:
    with pytest.raises(MeshProtocolConfigError):
        OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("", {"a": 1})
    with pytest.raises(MeshProtocolConfigError):
        OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("s1", {"a": 1}, chunk_size_bytes=8)
    with pytest.raises(MeshProtocolConfigError):
        OfflineQRAndMeshChunkEncoder.encode_payload_to_frames("s1", {"a": 1}, stripe_k=1)


def test_c6m_10_p2p_mesh_gossip_converges_4_disjoint_tablets_in_2_rounds() -> None:
    peers = {
        "T1": [StudentConceptCRDTState("s1", "G9-M1", 9, "AVR-P301", 0.65, {"T1": 2}, 100)],
        "T2": [StudentConceptCRDTState("s2", "G9-M1", 9, "AVR-P301", 0.80, {"T2": 3}, 110)],
        "T3": [StudentConceptCRDTState("s3", "G8-M2", 8, "AVR-P302", 0.72, {"T3": 1}, 120)],
        "T4": [StudentConceptCRDTState("s1", "G9-M1", 9, "AVR-P301", 0.91, {"T4": 4}, 130)],
    }
    res = PeerToPeerMeshGossipSynchronizer.synchronize_mesh_peers(peers, simulated_drop_one_chunk_per_stripe=True)
    assert res["all_peers_converged"] is True
    assert res["peers_synchronized"] == 4
    assert res["gossip_rounds_executed"] == 2
    assert len(set(res["peer_digests"].values())) == 1


def test_c6m_11_p2p_mesh_gossip_transmits_zero_frames_when_already_in_sync() -> None:
    shared_state = [StudentConceptCRDTState("s1", "G9-M1", 9, "AVR-P301", 0.88, {"T1": 2}, 100)]
    peers = {"T1": copy.deepcopy(shared_state), "T2": copy.deepcopy(shared_state)}
    res = PeerToPeerMeshGossipSynchronizer.synchronize_mesh_peers(peers, simulated_drop_one_chunk_per_stripe=False)
    assert res["all_peers_converged"] is True
    assert res["total_frames_transmitted"] == 0


def test_c6m_12_p2p_mesh_gossip_rejects_fewer_than_2_peers() -> None:
    with pytest.raises(MeshProtocolConfigError):
        PeerToPeerMeshGossipSynchronizer.synchronize_mesh_peers({"T1": []})


def test_c6m_13_p2p_mesh_gossip_preserves_combined_gcounter_attempts_across_peers() -> None:
    peers = {
        "T1": [StudentConceptCRDTState("s1", "G9-M1", 9, "AVR-P301", 0.60, {"T1": 3}, 100)],
        "T2": [StudentConceptCRDTState("s1", "G9-M1", 9, "AVR-P301", 0.85, {"T2": 4}, 200)],
    }
    res = PeerToPeerMeshGossipSynchronizer.synchronize_mesh_peers(peers, simulated_drop_one_chunk_per_stripe=False)
    assert res["all_peers_converged"] is True
    assert res["total_frames_transmitted"] >= 2


def test_c6m_14_xor_buffers_is_self_inverse() -> None:
    b1 = b"AASHA_DATA_BLOCK_ONE"
    b2 = b"AASHA_DATA_BLOCK_TWO"
    parity = OfflineQRAndMeshChunkEncoder._xor_buffers([b1, b2], 32)
    recovered_b1 = OfflineQRAndMeshChunkEncoder._xor_buffers([b2, parity], 32)
    assert recovered_b1[:len(b1)] == b1


def test_c6m_15_js_offline_p2p_mesh_sync_module_present_and_valid() -> None:
    js_txt = pathlib.Path("/tmp/aasha_stage_pack/scripts/aasha_offline_p2p_mesh_sync.js").read_text(encoding="utf-8")
    assert "OfflineQRAndMeshChunkEncoderJS" in js_txt
    assert "PeerToPeerMeshGossipSynchronizerJS" in js_txt


def test_c6m_16_compare_cycle6_offline_p2p_mesh_and_qr_fec_sync_benchmark() -> None:
    bench = compare_cycle6_offline_p2p_mesh_and_qr_fec_sync()
    assert bench["winner"] == "method-b-zlib-qr-xor-fec-and-anti-entropy-gossip-synchronizer"
    mb = bench["method_b_qr_xor_fec_mesh_gossip"]
    assert mb["all_peers_converged_under_packet_loss"] is True
    assert mb["bandwidth_savings_pct"] >= 85.0
    assert mb["fec_dropped_packets_recovered"] >= 1
    assert mb["retransmissions_required"] == 0
