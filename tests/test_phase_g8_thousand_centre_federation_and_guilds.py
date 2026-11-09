"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G8:
Autonomous State-Wide 1,000-Centre Mesh Federation, Peer-Taught Micro-Guilds
& Zero-Touch Self-Evolving Textbook Factory.
"""

import json
import subprocess
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g8_thousand_centre_federation_and_guilds import (
    NEXT_FOCUS_UNIT_G9,
    PeerTaughtMicroGuildPairingEngine,
    StateWideThousandCentreMeshFederation,
    ZeroTouchSelfEvolvingTextbookFactory,
    execute_chunk_g8_thousand_centre_federation_and_guilds_sync,
)


class TestPhaseG8ThousandCentreFederationAndGuilds(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g8_01_statewide_federation_converges_1000_centres_and_50000_tablets(self) -> None:
        fed = StateWideThousandCentreMeshFederation.synchronize_thousand_centre_federation()
        self.assertEqual(fed["total_districts"], 20)
        self.assertEqual(fed["total_centres_federated"], 1000)
        self.assertEqual(fed["total_concurrent_tablets"], 50000)
        self.assertLessEqual(fed["max_gossip_hops"], 3)
        self.assertTrue(fed["all_1000_centres_converged"])

    def test_g8_02_peer_taught_micro_guilds_lift_mastery_with_zero_pii(self) -> None:
        engine = PeerTaughtMicroGuildPairingEngine()
        guilds = engine.form_canonical_micro_guilds()
        self.assertEqual(len(guilds), 3)
        for g in guilds:
            self.assertGreaterEqual(g.mentor_mastery, 0.85)
            self.assertGreater(g.post_guild_mean_mastery, g.pre_guild_mean_mastery)
            self.assertEqual(len(g.learner_anon_ids), 3)
            self.assertTrue(g.mentor_anon_id.startswith("SATHI-MENTOR-ANON-"))

    def test_g8_03_federation_html5_passes_node_run_qa_js(self) -> None:
        summary = execute_chunk_g8_thousand_centre_federation_and_guilds_sync(self.repo_root)
        html_path = self.repo_root / summary["federation_html_bundle"]["html_rel_path"]
        qa_script = self.repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "qa" / "run_qa.js"
        proc = subprocess.run(
            ["node", str(qa_script), str(html_path)],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        report = json.loads(proc.stdout.strip())
        self.assertTrue(report["passed"], f"run_qa.js failed: {report.get('failures')}")
        self.assertEqual(len(report["failures"]), 0)

    def test_g8_04_execute_chunk_g8_writes_manifest_and_advances_to_g9(self) -> None:
        summary = execute_chunk_g8_thousand_centre_federation_and_guilds_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G8_1000_CENTRE_FEDERATION_AND_PEER_MICRO_GUILDS_VERIFIED",
        )
        self.assertEqual(summary["statewide_federation"]["total_centres_federated"], 1000)
        self.assertGreater(
            summary["peer_micro_guilds"]["mean_post_guild_mastery"],
            summary["peer_micro_guilds"]["mean_pre_guild_mastery"],
        )
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G9)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])


if __name__ == "__main__":
    unittest.main()
