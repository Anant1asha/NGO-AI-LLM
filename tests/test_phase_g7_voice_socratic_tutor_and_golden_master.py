"""
Unit tests for AASHA AIOS V3 Phase G — Chunk G7:
Autonomous Offline Voice-Guided Socratic Tutor, Low-Literacy Parent Progress Audio Report
& Final December 2026 MVP Golden Master Pack.
"""

import json
import subprocess
import unittest
from pathlib import Path

from aasha.orchestrator.phase_g7_voice_socratic_tutor_and_golden_master import (
    December2026MVPGoldenMasterCertifier,
    LowLiteracyParentAudioDigestCompiler,
    NEXT_FOCUS_UNIT_G8,
    OfflineVoiceGuidedSocraticTutor,
    execute_chunk_g7_voice_socratic_and_golden_master_sync,
)


class TestPhaseG7VoiceSocraticTutorAndGoldenMaster(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g7_01_voice_guided_socratic_tutor_is_spoiler_free_and_zero_drift(self) -> None:
        track = OfflineVoiceGuidedSocraticTutor.synthesize_voice_socratic_track()
        self.assertTrue(track.spoiler_free_verified)
        self.assertEqual(track.timing_drift_ms, 0.0)
        self.assertGreater(track.viseme_token_count, 5)
        self.assertEqual(len(track.webvtt_sha256), 64)

    def test_g7_02_low_literacy_parent_audio_digests_cover_all_9_indic_scripts(self) -> None:
        cards = LowLiteracyParentAudioDigestCompiler.compile_all_nine_script_parent_digests()
        self.assertEqual(len(cards), 9)
        self.assertEqual(
            [c.script_code for c in cards],
            ["bn", "gu", "hi", "kn", "ml", "or", "pa", "ta", "te"],
        )
        for c in cards:
            self.assertEqual(c.timing_drift_ms, 0.0)
            self.assertTrue(c.anon_family_id.startswith("FAMILY-ANON-"))

    def test_g7_03_golden_master_html5_passes_node_run_qa_js(self) -> None:
        summary = execute_chunk_g7_voice_socratic_and_golden_master_sync(self.repo_root)
        html_path = self.repo_root / summary["golden_master_html_bundle"]["html_rel_path"]
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

    def test_g7_04_execute_chunk_g7_certifies_25_chunks_and_advances_to_g8(self) -> None:
        summary = execute_chunk_g7_voice_socratic_and_golden_master_sync(self.repo_root)
        self.assertEqual(
            summary["status"],
            "G7_VOICE_SOCRATIC_TUTOR_PARENT_AUDIO_AND_DEC2026_GOLDEN_MASTER_CERTIFIED",
        )
        self.assertEqual(summary["completed_chunks_count"], 25)
        self.assertTrue(summary["parent_audio_digests_9_scripts"]["zero_drift_verified"])
        self.assertEqual(summary["next_focus_unit"], NEXT_FOCUS_UNIT_G8)
        self.assertTrue(summary["oracle_proof"]["passed"])
        self.assertTrue(summary["autonomous_authorization"]["authorized"])


if __name__ == "__main__":
    unittest.main()
