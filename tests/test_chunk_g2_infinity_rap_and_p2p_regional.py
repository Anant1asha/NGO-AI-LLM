"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G2:
Multi-Centre Offline P2P Mesh Delta Sync, 9-Indic-Script Regional Language Pack Expansion,
and Hydro Infinity RAP + Hibernating Continuation Store + Stacked-Worktree Sandbox Adapter.
"""

import json
import tempfile
import unittest
from pathlib import Path

from aasha.orchestrator.infinity_rap_worktree_and_g2_sync import (
    NEXT_FOCUS_UNIT_G3,
    NineIndicScriptRegionalPackager,
    PathConfinementViolationError,
    RAPEventMailbox,
    SQLiteContinuationStore,
    StackedWorktreeSandbox,
    execute_chunk_g2_infinity_rap_and_p2p_regional_sync,
)


class TestChunkG2InfinityRAPAndP2PRegionalSync(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g2_01_sqlite_continuation_store_hibernates_with_zero_resident_ram_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteContinuationStore(Path(tmp) / "cont.db")
            hib = store.hibernate_agent(
                agent_id="SUBAGENT_01",
                chunk_id="G2",
                waiting_on_rap_call_id="rap-001",
                conversation_history=[{"role": "user", "content": "start"}],
                continuation_state={"cursor": 1},
            )
            self.assertEqual(hib.status, "HIBERNATED_PURE_DATA")
            self.assertEqual(hib.resident_ram_bytes_while_hibernated, 0)

            resumed = store.resume_agent_on_synthetic_tool_call(
                agent_id="SUBAGENT_01",
                synthetic_tool_message={"role": "tool", "tool_call_id": "rap-001", "content": "ok"},
            )
            self.assertEqual(resumed.status, "RESUMED_ACTIVE")
            self.assertEqual(len(resumed.conversation_history), 2)
            self.assertEqual(resumed.continuation_state["last_resumed_call_id"], "rap-001")

    def test_g2_02_rap_event_mailbox_delivers_synthetic_tool_call_and_suppresses_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteContinuationStore(Path(tmp) / "cont.db")
            store.hibernate_agent(
                agent_id="SUBAGENT_02",
                chunk_id="G2",
                waiting_on_rap_call_id="rap-002",
                conversation_history=[{"role": "user", "content": "await tool"}],
                continuation_state={},
            )
            mailbox = RAPEventMailbox(store)
            first = mailbox.deliver_async_rap_event(
                agent_id="SUBAGENT_02",
                rap_call_id="rap-002",
                tool_name="playwright_harvest",
                source_plane="PLANE_2_COLAB_CLOUD",
                event_payload={"passed": 97},
            )
            self.assertTrue(first["delivered"])
            self.assertFalse(first["duplicate_suppressed"])
            self.assertTrue(first["synthetic_tool_call"]["synthetic_rap_event"])

            second = mailbox.deliver_async_rap_event(
                agent_id="SUBAGENT_02",
                rap_call_id="rap-002",
                tool_name="playwright_harvest",
                source_plane="PLANE_2_COLAB_CLOUD",
                event_payload={"passed": 97},
            )
            self.assertFalse(second["delivered"])
            self.assertTrue(second["duplicate_suppressed"])

    def test_g2_03_stacked_worktree_sandbox_blocks_path_traversal_and_out_of_lease_edits(self) -> None:
        sandbox = StackedWorktreeSandbox(
            workspace_root=self.repo_root,
            chunk_id="G2",
            allowed_relative_files=["src/aasha/orchestrator/infinity_rap_worktree_and_g2_sync.py"],
        )
        with self.assertRaises(PathConfinementViolationError):
            sandbox.validate_confined_path("../outside_repo.py")
        with self.assertRaises(PathConfinementViolationError):
            sandbox.validate_confined_path("/etc/passwd")
        with self.assertRaises(PathConfinementViolationError):
            sandbox.validate_confined_path("src/aasha/orchestrator/unleased_file.py")

        valid_path = sandbox.validate_confined_path(
            "src/aasha/orchestrator/infinity_rap_worktree_and_g2_sync.py"
        )
        self.assertTrue(str(valid_path).endswith("infinity_rap_worktree_and_g2_sync.py"))

    def test_g2_04_nine_indic_script_packager_compiles_all_9_scripts_with_zero_drift(self) -> None:
        res = NineIndicScriptRegionalPackager.compile_all_nine_regional_packs_and_p2p_sync(self.repo_root)
        self.assertEqual(res["scripts_compiled_count"], 9)
        self.assertEqual(
            res["scripts_compiled"],
            ["bn", "gu", "hi", "kn", "ml", "or", "pa", "ta", "te"],
        )
        self.assertTrue(res["zero_drift_all_scripts"])
        self.assertTrue(res["under_20mib_ceiling"])
        self.assertTrue(res["p2p_mesh_sync"]["merkle_root_match"])
        self.assertEqual(res["p2p_mesh_sync"]["delta_chunks_transferred"], 2)

    def test_g2_05_execute_chunk_g2_end_to_end_writes_manifests_and_advances_to_g3(self) -> None:
        summary = execute_chunk_g2_infinity_rap_and_p2p_regional_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G2_INFINITY_RAP_WORKTREE_AND_9_INDIC_P2P_VERIFIED",
        )
        self.assertEqual(
            summary["infinity_runtime_adaptation"]["hibernated_resident_ram_bytes"],
            0,
        )
        self.assertTrue(summary["infinity_runtime_adaptation"]["rap_synthetic_tool_call_delivered"])
        self.assertTrue(summary["infinity_runtime_adaptation"]["rap_duplicate_event_suppressed"])
        self.assertTrue(summary["infinity_runtime_adaptation"]["worktree_path_confinement_verified"])
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G3)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])

        rap_cfg = self.repo_root / ".agents" / "rap_servers.json"
        self.assertTrue(rap_cfg.is_file())
        parsed_cfg = json.loads(rap_cfg.read_text(encoding="utf-8"))
        self.assertEqual(parsed_cfg["license"], "Apache-2.0")


if __name__ == "__main__":
    unittest.main()
