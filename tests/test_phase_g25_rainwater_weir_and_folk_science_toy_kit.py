"""
Unit tests for Phase G25: Autonomous Offline Rural Rainwater Harvesting & Check-Dam Hydraulic Weir Calculator,
Vernacular Folk-Science Toy & Low-Cost Lab Kit Compiler & 100,000,000-Learner Sovereign Post-Centennial Audit.
"""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g25_rainwater_weir_and_folk_science_toy_kit import (
    OfflineRainwaterHarvestingCheckDamWeirCalculator,
    VernacularFolkScienceToyLowCostLabKitCompiler,
    HundredMillionLearnerPostCentennialAuditSeal,
    run_phase_g25_rainwater_weir_and_folk_science_toy_kit_cycle,
)


class TestPhaseG25RainwaterWeirAndFolkScienceToyKit(unittest.TestCase):
    def test_g25_01_rainwater_harvesting_and_check_dam_weir_discharge(self) -> None:
        calc = OfflineRainwaterHarvestingCheckDamWeirCalculator()
        suite = calc.run_canonical_watershed_suite()
        dam = suite["primary_check_dam"]

        self.assertEqual(dam["check_dam_id"], "CHECKDAM-UP-GN-JAL-2501")
        self.assertAlmostEqual(dam["harvested_runoff_m3"], 1476.0, places=2)
        self.assertAlmostEqual(dam["harvested_runoff_liters"], 1476000.0, places=1)
        self.assertAlmostEqual(dam["weir_discharge_m3_s"], 1.7796, places=4)
        self.assertAlmostEqual(dam["dry_season_days_supported"], 123.0, places=2)
        self.assertEqual(dam["jal_seva_water_stewardship_points"], 2214)
        self.assertEqual(len(dam["hydraulics_sha256"]), 64)

    def test_g25_02_vernacular_folk_science_toy_kit_9_scripts(self) -> None:
        compiler = VernacularFolkScienceToyLowCostLabKitCompiler()
        report = compiler.run_canonical_folk_science_kit()

        self.assertEqual(report["toy_count"], 5)
        self.assertEqual(report["active_script_count"], 9)
        self.assertAlmostEqual(report["total_kit_cost_inr"], 42.0, places=2)
        self.assertAlmostEqual(report["mean_toy_cost_inr"], 8.4, places=2)
        self.assertTrue(report["all_toys_under_20_inr"])
        self.assertEqual(report["total_experiments_unlocked"], 17)
        self.assertEqual(len(report["kit_merkle_root"]), 64)

    def test_g25_03_hundred_million_learner_post_centennial_audit_seal(self) -> None:
        calc = OfflineRainwaterHarvestingCheckDamWeirCalculator()
        compiler = VernacularFolkScienceToyLowCostLabKitCompiler()
        seal_builder = HundredMillionLearnerPostCentennialAuditSeal()

        watershed = calc.run_canonical_watershed_suite()
        kit = compiler.run_canonical_folk_science_kit()
        seal = seal_builder.generate_audit_seal(watershed, kit)

        self.assertEqual(seal["verified_chunk_count"], 43)
        self.assertIn("G25", seal["verified_chunks"])
        self.assertEqual(seal["scaled_learner_capacity"], 100_000_000)
        self.assertEqual(seal["hydro_infinity_agents"], 1080)
        self.assertEqual(seal["idle_ram_bytes"], 0)
        self.assertEqual(seal["status"], "SOVEREIGN_100M_POST_CENTENNIAL_AUDIT_VERIFIED")
        self.assertEqual(len(seal["audit_seal_sha256"]), 64)

    def test_g25_04_end_to_end_cycle_and_html5_hub_generation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest = run_phase_g25_rainwater_weir_and_folk_science_toy_kit_cycle(repo_root)

        self.assertEqual(manifest["phase"], "G25")
        hub = manifest["html5_hub"]
        self.assertEqual(hub["file_name"], "Rainwater_Weir_Folk_Science_Toy_Kit_Hub_v5.html")
        self.assertTrue(hub["under_20mib_ceiling"])
        self.assertLess(hub["size_bytes"], 20_971_520)

        html_text = Path(hub["file_path"]).read_text(encoding="utf-8")
        self.assertIn('data-tap-select="true"', html_text)
        self.assertIn("var NODES =", html_text)
        self.assertIn("var WE =", html_text)
        self.assertIn("var WM =", html_text)
        self.assertIn("var CONN =", html_text)
        self.assertIn("_weCheckRendered", html_text)
        self.assertNotIn("http://", html_text)
        self.assertNotIn("https://", html_text)


if __name__ == "__main__":
    unittest.main()
