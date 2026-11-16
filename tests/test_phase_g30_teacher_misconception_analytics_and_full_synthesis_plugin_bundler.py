"""
Unit tests for Phase G30: Teacher Cohort Misconception Hotspot Analytics (/api/teacher/misconception-analytics),
FrontendCodeSynthesizer 3-Level Assessment (Warmup/Deep-Dive/Boss) & Offline Plugin Base64 Bundler Verification.
"""

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [str(_REPO_ROOT), str(_REPO_ROOT / "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.aasha.orchestrator.phase_g28_swarm_clarity_aios_learning_gamified_orchestrator import (
    inspect_html5_qa_violations,
)
from src.aasha.orchestrator.phase_g30_teacher_misconception_analytics_and_full_synthesis_plugin_bundler import (
    TeacherMisconceptionAndFullSynthesisBundlerOrchestrator,
    run_phase_g30_teacher_misconception_and_full_synthesis_bundler_cycle,
)


class TestPhaseG30TeacherMisconceptionAndFullSynthesisBundler(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.orchestrator = TeacherMisconceptionAndFullSynthesisBundlerOrchestrator(self.repo_root)

    def test_g30_01_teacher_misconception_hotspot_analytics_pwa_and_sqlite(self) -> None:
        mc = self.orchestrator.execute_teacher_misconception_hotspot_analytics()

        self.assertEqual(mc["endpoint"], "/api/teacher/misconception-analytics")
        self.assertEqual(mc["status"], "ok")
        self.assertEqual(mc["total_events_analyzed"], 8)
        self.assertEqual(mc["failing_events_count"], 6)
        self.assertEqual(mc["hotspot_clusters_identified"], 3)
        self.assertEqual(mc["top_hotspot_chapter_id"], "NCERT-CLASS6-MATH-CH07-FRACTIONS")
        self.assertEqual(mc["top_hotspot_concept_code"], "G6_CH07_N4_LIKE_UNLIKE_ADD")
        self.assertEqual(mc["top_hotspot_struggling_count"], 3)
        self.assertAlmostEqual(mc["top_hotspot_avg_failed_score"], 45.0, places=1)
        self.assertTrue(mc["pwa_server_top_hotspot_aligned"])
        self.assertTrue(mc["dashboard_renders_section"])
        self.assertTrue(mc["flashcard_renders_deck"])
        self.assertTrue(mc["backup_renders_card"])

    def test_g30_02_frontend_code_synthesizer_3level_assessment_and_qa(self) -> None:
        synth = self.orchestrator.execute_frontend_code_synthesizer_3level_assessment()

        self.assertEqual(synth["synthesizer_agent"], "FrontendCodeSynthesizer")
        self.assertFalse(synth["requires_llm"])
        self.assertEqual(synth["concept_count"], 3)
        self.assertEqual(synth["warmup_count"], 2)
        self.assertEqual(synth["deep_dive_count"], 2)
        self.assertEqual(synth["boss_count"], 1)
        self.assertEqual(synth["total_assessment_count"], 5)
        self.assertEqual(synth["wm_dictionary_count"], 296)
        self.assertEqual(synth["conn_dictionary_count"], 46)
        self.assertTrue(synth["under_20mib_ceiling"])
        self.assertTrue(synth["self_healing_qa_passed"])
        self.assertEqual(synth["final_qa_violations"], 0)

    def test_g30_03_offline_plugin_base64_bundler_21_avr_mechanics(self) -> None:
        bundler = self.orchestrator.execute_offline_plugin_base64_bundler_verification()

        self.assertTrue(bundler["engine_verified"])
        if bundler.get("assets_present"):
            self.assertEqual(bundler["avr_mechanics_bundled"], 21)
            self.assertTrue(bundler["all_21_avr_mechanics_verified"])
            self.assertGreater(bundler["total_raw_js_bytes"], 15000)
            self.assertGreater(bundler["total_data_uri_chars"], 20000)
        else:
            self.assertEqual(bundler["status"], "SKIPPED_ASSETS_ABSENT")
            self.assertEqual(bundler["avr_mechanics_bundled"], 0)
            self.assertFalse(bundler["all_21_avr_mechanics_verified"])

        self.assertTrue(bundler["zero_external_cdn_urls"])
        self.assertTrue(bundler["under_20mib_ceiling"])
        self.assertEqual(len(bundler["bundle_merkle_sha256"]), 64)

    def test_g30_04_end_to_end_cycle_and_html5_hub_generation(self) -> None:
        manifest = run_phase_g30_teacher_misconception_and_full_synthesis_bundler_cycle(self.repo_root)

        self.assertEqual(manifest["phase"], "G30")
        self.assertEqual(manifest["verified_chunk_count"], 48)

        hub = manifest["html5_hub"]
        self.assertEqual(
            hub["file_name"],
            "Teacher_Misconception_Full_Synthesis_Plugin_Bundler_Hub_v5.html",
        )
        self.assertTrue(hub["under_20mib_ceiling"])
        html_text = Path(hub["file_path"]).read_text(encoding="utf-8")
        self.assertEqual(len(inspect_html5_qa_violations(html_text)), 0)


if __name__ == "__main__":
    unittest.main()
