"""
Unit tests for AASHA AIOS V3 Zero-Approval Autonomous Gate, Async Local IDE Bridge Bus,
Anti-Contradiction Grounding Oracle, and Chunk B1 (Source PDF SHA-256 Lock & TLN Validator).
"""

import json
import tempfile
import unittest
from pathlib import Path

from aasha.orchestrator.zero_approval_async_ide_bus import (
    AntiContradictionGroundingOracle,
    AsyncLocalIDEBridgeBus,
    AutonomousCryptographicProofGate,
    SourcePDFSha256LockAndTLNValidator,
    execute_zero_approval_async_ide_and_b1_cycle,
)


class TestZeroApprovalAsyncIDEBusAndB1(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_za_01_autonomous_gate_authorizes_without_human_approval(self) -> None:
        gate = AutonomousCryptographicProofGate()
        decision = gate.authorize_action(
            action_type="EXECUTE_CHUNK_B1_AND_AUTO_COMMIT",
            chunk_id="B1",
            plane_id="PLANE_2_COLAB_CLOUD",
            branch="aios/v2-bootstrap",
            sec001_clean=True,
            grounding_oracle_passed=True,
        )
        self.assertTrue(decision.authorized)
        self.assertFalse(decision.human_approval_required)
        self.assertEqual(decision.execution_policy, "AUTONOMOUS_ZERO_HIL_CRYPTO_PROOF")
        self.assertEqual(decision.blocked_reason, "NONE")
        self.assertEqual(len(decision.proof_token_sha256), 64)

    def test_za_02_autonomous_gate_blocks_protected_branch_autonomously(self) -> None:
        gate = AutonomousCryptographicProofGate()
        decision = gate.authorize_action(
            action_type="AUTO_PUSH",
            chunk_id="B1",
            plane_id="PLANE_3_LOCAL_PC",
            branch="main",
            sec001_clean=True,
            grounding_oracle_passed=True,
        )
        self.assertFalse(decision.authorized)
        self.assertFalse(decision.human_approval_required)
        self.assertEqual(decision.blocked_reason, "PROTECTED_BRANCH_VIOLATION:main")

    def test_za_03_autonomous_gate_blocks_secret_violation(self) -> None:
        gate = AutonomousCryptographicProofGate()
        decision = gate.authorize_action(
            action_type="AUTO_COMMIT",
            chunk_id="B1",
            plane_id="PLANE_3_LOCAL_PC",
            branch="aios/v2-bootstrap",
            sec001_clean=False,
            grounding_oracle_passed=True,
        )
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.blocked_reason, "SEC_001_SECRET_DETECTED")

    def test_za_04_autonomous_gate_blocks_unverified_claims(self) -> None:
        gate = AutonomousCryptographicProofGate()
        decision = gate.authorize_action(
            action_type="AUTO_COMMIT",
            chunk_id="B1",
            plane_id="PLANE_3_LOCAL_PC",
            branch="aios/v2-bootstrap",
            sec001_clean=True,
            grounding_oracle_passed=False,
        )
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.blocked_reason, "ANTI_CONTRADICTION_ORACLE_REJECTED")

    def test_za_05_grounding_oracle_passes_real_repo_files_and_invariants(self) -> None:
        oracle = AntiContradictionGroundingOracle(self.repo_root)
        proof = oracle.verify_claims(
            claimed_files=[
                "src/aasha/orchestrator/phase_a_foundation_hardening.py",
                "src/aasha/orchestrator/zero_approval_async_ide_bus.py",
                "scripts/aasha_zero_approval_async_ide_bus.js",
            ],
            invariants={
                "branch": "aios/v2-bootstrap",
                "tln_node_count": 4,
                "bundle_bytes": 4_194_304,
                "external_url_count": 0,
                "english_ratio": 0.60,
                "hindi_ratio": 0.40,
            },
        )
        self.assertTrue(proof.passed)
        self.assertEqual(proof.verified_files_count, 3)
        self.assertEqual(len(proof.hallucinated_missing_files), 0)
        self.assertEqual(len(proof.contradictions_detected), 0)

    def test_za_06_grounding_oracle_rejects_hallucinated_nonexistent_file(self) -> None:
        oracle = AntiContradictionGroundingOracle(self.repo_root)
        proof = oracle.verify_claims(
            claimed_files=["src/aasha/orchestrator/non_existent_hallucinated_module.py"],
            invariants={"branch": "aios/v2-bootstrap"},
        )
        self.assertFalse(proof.passed)
        self.assertIn(
            "src/aasha/orchestrator/non_existent_hallucinated_module.py",
            proof.hallucinated_missing_files,
        )

    def test_za_07_grounding_oracle_detects_invariant_contradictions(self) -> None:
        oracle = AntiContradictionGroundingOracle(self.repo_root)
        proof = oracle.verify_claims(
            claimed_files=["src/aasha/orchestrator/zero_approval_async_ide_bus.py"],
            invariants={
                "branch": "master",
                "tln_node_count": 7,
                "bundle_bytes": 25_000_000,
                "external_url_count": 2,
                "english_ratio": 0.80,
                "hindi_ratio": 0.20,
            },
        )
        self.assertFalse(proof.passed)
        self.assertGreaterEqual(len(proof.contradictions_detected), 4)

    def test_za_08_async_ide_bus_selects_non_conflicting_chunk_when_ide_dirty(self) -> None:
        bus = AsyncLocalIDEBridgeBus(self.repo_root)
        sel = bus.select_non_conflicting_chunk(
            completed_chunks=["A1", "A2", "A3"],
            ide_dirty_files=["src/aasha/orchestrator/zero_approval_async_ide_bus.py"],
        )
        self.assertEqual(sel["selected_chunk_id"], "B2")
        self.assertEqual(sel["selected_phase"], "PHASE_B_COMPILER_AND_LLE_PIPELINE")
        self.assertEqual(len(sel["skipped_due_to_ide_lease"]), 1)
        self.assertEqual(sel["skipped_due_to_ide_lease"][0]["chunk_id"], "B1")

    def test_za_09_async_ide_bus_selects_b1_when_ide_clean(self) -> None:
        bus = AsyncLocalIDEBridgeBus(self.repo_root)
        sel = bus.select_non_conflicting_chunk(
            completed_chunks=["A1", "A2", "A3"],
            ide_dirty_files=[],
        )
        self.assertEqual(sel["selected_chunk_id"], "B1")
        self.assertEqual(sel["selected_phase"], "PHASE_B_COMPILER_AND_LLE_PIPELINE")
        self.assertEqual(len(sel["skipped_due_to_ide_lease"]), 0)

    def test_za_10_crdt_join_semilattice_merges_legacy_pc_state_without_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            pc_legacy = {
                "schema_version": "1.0.0",
                "mode": "MODE_D_LOCAL_PC_ACTIVE",
                "git": {
                    "branch": "aios/v2-bootstrap",
                    "head_sha": "f5ba5b2b146ba5160778dace9dfb2d3b98193598",
                    "dirty_count": 0,
                    "dirty_files_sample": [],
                },
            }
            colab_v3 = {
                "schema_version": "3.0.0",
                "completed_chunks": ["A1", "A2", "A3"],
                "active_chunk_id": "B1",
                "lamport_epoch": 5,
                "vector_clock": {"plane_1_drive": 5, "plane_2_colab": 5, "plane_3_local_ide": 4},
            }
            (tmp_root / "PC_ANTIGRAVITY_STATE.json").write_text(json.dumps(pc_legacy), encoding="utf-8")
            (tmp_root / "COLAB_ANTIGRAVITY_STATE.json").write_text(json.dumps(colab_v3), encoding="utf-8")

            bus = AsyncLocalIDEBridgeBus(tmp_root)
            merged = bus.synchronize_ide_and_cloud_planes(
                 newly_completed_chunk="B1",
                git_head_sha="f5ba5b2b146ba5160778dace9dfb2d3b98193598",
                git_branch="aios/v2-bootstrap",
                active_writer_plane="PLANE_2_COLAB_CLOUD",
                oracle_digest="a" * 64,
                auth_proof_token="b" * 64,
            )
            self.assertEqual(merged["completed_chunks"], ["A1", "A2", "A3", "B1"])
            self.assertEqual(merged["active_chunk_id"], "B2")
            self.assertEqual(merged["lamport_epoch"], 6)
            self.assertTrue((tmp_root / "IDE_CLOUD_ASYNC_BUS.json").exists())
            self.assertTrue((tmp_root / ".serena" / "memories" / "active_chunk_context.md").exists())

            pc_after = json.loads((tmp_root / "PC_ANTIGRAVITY_STATE.json").read_text(encoding="utf-8"))
            colab_after = json.loads((tmp_root / "COLAB_ANTIGRAVITY_STATE.json").read_text(encoding="utf-8"))
            self.assertEqual(pc_after["cursor_lock_sha256"], colab_after["cursor_lock_sha256"])
            self.assertEqual(pc_after["completed_chunks"], ["A1", "A2", "A3", "B1"])

    def test_za_11_chunk_b1_source_pdf_sha256_lock_and_tln_validator_passes_canonical_spec(self) -> None:
        validator = SourcePDFSha256LockAndTLNValidator(self.repo_root)
        spec = validator.build_canonical_chapter_spec()
        result = validator.validate_chapter_spec(spec)
        self.assertTrue(result.valid)
        self.assertTrue(result.pdf_lock_verified)
        self.assertTrue(result.node_bounds_verified)
        self.assertTrue(result.golden_flow_verified)
        self.assertTrue(result.lle_ratio_verified)
        self.assertEqual(result.node_count, 4)

    def test_za_12_chunk_b1_rejects_fewer_than_3_or_more_than_5_tln_nodes(self) -> None:
        validator = SourcePDFSha256LockAndTLNValidator(self.repo_root)
        spec_too_few = validator.build_canonical_chapter_spec()
        spec_too_few["learning_nodes"] = spec_too_few["learning_nodes"][:2]
        res_few = validator.validate_chapter_spec(spec_too_few)
        self.assertFalse(res_few.valid)
        self.assertFalse(res_few.node_bounds_verified)

        spec_too_many = validator.build_canonical_chapter_spec()
        spec_too_many["learning_nodes"].append(dict(spec_too_many["learning_nodes"][0], node_id="TLN-05"))
        spec_too_many["learning_nodes"].append(dict(spec_too_many["learning_nodes"][0], node_id="TLN-06"))
        res_many = validator.validate_chapter_spec(spec_too_many)
        self.assertFalse(res_many.valid)
        self.assertFalse(res_many.node_bounds_verified)

    def test_za_13_chunk_b1_rejects_invalid_source_pdf_sha256(self) -> None:
        validator = SourcePDFSha256LockAndTLNValidator(self.repo_root)
        spec = validator.build_canonical_chapter_spec()
        spec["source_pdf_sha256"] = "not-a-sha256"
        res = validator.validate_chapter_spec(spec)
        self.assertFalse(res.valid)
        self.assertFalse(res.pdf_lock_verified)

    def test_za_14_chunk_b1_rejects_invalid_golden_flow(self) -> None:
        validator = SourcePDFSha256LockAndTLNValidator(self.repo_root)
        spec = validator.build_canonical_chapter_spec()
        spec["learning_nodes"][0]["golden_flow"] = ["HOOK", "SUMMARY"]
        res = validator.validate_chapter_spec(spec)
        self.assertFalse(res.valid)
        self.assertFalse(res.golden_flow_verified)

    def test_za_15_chunk_b1_rejects_drifted_lle_ratio(self) -> None:
        validator = SourcePDFSha256LockAndTLNValidator(self.repo_root)
        spec = validator.build_canonical_chapter_spec()
        spec["lle_balance"] = {"english_ratio": 0.90, "hindi_ratio": 0.10}
        res = validator.validate_chapter_spec(spec)
        self.assertFalse(res.valid)
        self.assertFalse(res.lle_ratio_verified)

    def test_za_16_full_zero_approval_async_ide_and_b1_cycle_end_to_end(self) -> None:
        summary = execute_zero_approval_async_ide_and_b1_cycle(
            repo_root=self.repo_root,
            git_head_sha="f5ba5b2b146ba5160778dace9dfb2d3b98193598",
            git_branch="aios/v2-bootstrap",
            active_writer_plane="PLANE_2_COLAB_CLOUD",
        )
        self.assertEqual(summary["status"], "ZERO_APPROVAL_ASYNC_IDE_AND_B1_VERIFIED")
        self.assertTrue(summary["autonomous_authorization"]["authorized"])
        self.assertFalse(summary["autonomous_authorization"]["human_approval_required"])
        self.assertTrue(summary["anti_contradiction_oracle"]["passed"])
        self.assertTrue(summary["chunk_b1_validation"]["valid"])
        self.assertIn("B1", summary["ide_cloud_sync"]["completed_chunks"])
        self.assertEqual(summary["ide_cloud_sync"]["active_chunk_id"], "B2")


if __name__ == "__main__":
    unittest.main()
