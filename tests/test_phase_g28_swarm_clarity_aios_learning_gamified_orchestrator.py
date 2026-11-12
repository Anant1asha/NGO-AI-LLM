"""
Unit tests for Phase G28 (Swarm Clarity): AASHA AIOS Multi-Agent Swarm Orchestrator Loop
(DESIGN_LEARNING -> BUILD -> CODE -> TEST -> DEBUG -> FIX -> GAMIFIED_TEAS_ECOSYSTEM).
"""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g28_swarm_clarity_aios_learning_gamified_orchestrator import (
    SwarmClarityAIOSOrchestrator,
    inspect_html5_qa_violations,
    run_phase_g28_swarm_clarity_aios_orchestrator_cycle,
)


class TestPhaseG28SwarmClarityAIOSOrchestrator(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.orchestrator = SwarmClarityAIOSOrchestrator(self.repo_root)

    def test_g28_01_design_learning_stage_binds_real_registry_tln_and_lle(self) -> None:
        design = self.orchestrator.execute_design_learning_stage()

        self.assertEqual(design["stage"], "DESIGN_LEARNING")
        self.assertEqual(design["chapter_id"], "NCERT-CLASS6-MATH-CH07-FRACTIONS")
        self.assertEqual(design["tln_node_count"], 4)
        self.assertEqual(design["wm_dictionary_count"], 296)
        self.assertEqual(design["conn_dictionary_count"], 46)
        self.assertAlmostEqual(design["english_ratio"], 0.60, places=2)
        self.assertAlmostEqual(design["hindi_ratio"], 0.40, places=2)
        self.assertGreaterEqual(design["math_tokens_preserved"], 4)

        reg = design["ecosystem_registries"]
        self.assertEqual(reg["foundation_count"], 27)
        self.assertEqual(reg["phase3_avr_mechanic_count"], 21)

    def test_g28_02_build_stage_exports_real_dual_output_teas_sqlite_db(self) -> None:
        design = self.orchestrator.execute_design_learning_stage()
        sqlite_res = self.orchestrator.execute_dual_output_sqlite_build(design)

        self.assertEqual(sqlite_res["stage"], "BUILD_DUAL_OUTPUT_SQLITE")
        self.assertEqual(sqlite_res["chapters_stored"], 1)
        self.assertEqual(sqlite_res["tln_nodes_stored"], 4)
        self.assertEqual(sqlite_res["wm_vocabulary_stored"], 296)
        self.assertGreater(sqlite_res["sqlite_db_bytes"], 1024)
        self.assertGreater(sqlite_res["sqlite_gz_bytes"], 512)

    def test_g28_03_debug_and_fix_stage_heals_html5_and_compiler_faults(self) -> None:
        debug_fix = self.orchestrator.execute_debug_and_fix_self_healing_verification()

        html_heal = debug_fix["html5_self_healing"]
        self.assertEqual(html_heal["initial_violation_count"], 5)
        self.assertEqual(html_heal["final_violation_count"], 0)
        self.assertTrue(html_heal["passed"])
        self.assertTrue(debug_fix["e2e_ten_rule_html_healing_passed"])
        self.assertTrue(debug_fix["healed_html_uses_tap_select"])

        ast_heal = debug_fix["compiler_ast_self_healing"]
        self.assertTrue(ast_heal["passed"])
        self.assertGreaterEqual(ast_heal["total_faults_repaired"], 5)
        self.assertEqual(ast_heal["repaired_formula"], "$F = m \\cdot a$")

    def test_g28_04_gamified_teas_pwa_store_and_end_to_end_html5_hub(self) -> None:
        manifest = run_phase_g28_swarm_clarity_aios_orchestrator_cycle(self.repo_root)

        self.assertEqual(manifest["phase"], "G28")
        self.assertEqual(manifest["verified_chunk_count"], 46)

        pwa = manifest["gamified_teas_ecosystem_stage"]
        self.assertEqual(pwa["catalogSize"], 4)
        self.assertEqual(pwa["coinsBeforeRedemption"], 300)
        self.assertEqual(pwa["duplicateAwardedCoins"], 0)
        self.assertIn("first_step", pwa["unlockedBadgeIds"])
        self.assertIn("three_chapter_streak", pwa["unlockedBadgeIds"])
        self.assertIn("coin_saver", pwa["unlockedBadgeIds"])
        self.assertTrue(pwa["invalidPinBlocked"])
        self.assertTrue(pwa["validRedemptionOk"])
        self.assertEqual(pwa["redeemedItemId"], "item_geometry_box")
        self.assertEqual(pwa["coinsRemainingAfterRedemption"], 50)

        hub = manifest["html5_hub"]
        self.assertEqual(
            hub["file_name"], "AASHA_Swarm_Clarity_TLN_TEAS_Gamified_Engine_v5.html"
        )
        self.assertTrue(hub["under_20mib_ceiling"])
        html_text = Path(hub["file_path"]).read_text(encoding="utf-8")
        self.assertEqual(len(inspect_html5_qa_violations(html_text)), 0)


if __name__ == "__main__":
    unittest.main()
