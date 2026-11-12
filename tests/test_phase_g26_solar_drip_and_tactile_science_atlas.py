"""
Unit tests for Phase G26: Autonomous Offline Rural Solar-Powered Drip Evapotranspiration & Crop-Coefficient Calculator,
Vernacular Tactile Science Diagram Atlas Compiler & 100,000,000-Learner Sovereign Continual Evolution Seal.
"""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g26_solar_drip_and_tactile_science_atlas import (
    OfflineSolarDripEvapotranspirationCropCalculator,
    VernacularTactileScienceDiagramAtlasCompiler,
    HundredMillionLearnerContinualEvolutionSeal,
    run_phase_g26_solar_drip_and_tactile_science_atlas_cycle,
)


class TestPhaseG26SolarDripAndTactileScienceAtlas(unittest.TestCase):
    def test_g26_01_solar_drip_evapotranspiration_and_water_savings(self) -> None:
        calc = OfflineSolarDripEvapotranspirationCropCalculator()
        suite = calc.run_canonical_solar_drip_suite()
        plot = suite["primary_plot"]

        self.assertEqual(plot["plot_id"], "PLOT-UP-GN-DRIP-2601")
        self.assertAlmostEqual(plot["crop_etc_mm_day"], 4.675, places=3)
        self.assertAlmostEqual(plot["net_drip_liters_day"], 3366.0, places=2)
        self.assertAlmostEqual(plot["gross_drip_liters_day"], 3740.0, places=2)
        self.assertAlmostEqual(plot["gross_flood_liters_day"], 10200.0, places=2)
        self.assertAlmostEqual(plot["daily_water_saved_liters"], 6460.0, places=2)
        self.assertAlmostEqual(plot["water_saving_pct"], 63.33, places=2)
        self.assertAlmostEqual(plot["solar_pump_energy_wh_day"], 297.25, places=2)
        self.assertEqual(len(plot["evapotranspiration_sha256"]), 64)

    def test_g26_02_vernacular_tactile_science_diagram_atlas_9_scripts(self) -> None:
        compiler = VernacularTactileScienceDiagramAtlasCompiler()
        atlas = compiler.run_canonical_tactile_science_atlas()

        self.assertEqual(atlas["plate_count"], 5)
        self.assertEqual(atlas["active_script_count"], 9)
        self.assertEqual(atlas["total_raised_nodes"], 66)
        self.assertEqual(atlas["total_braille_labels"], 44)
        self.assertAlmostEqual(atlas["total_atlas_cost_inr"], 62.0, places=2)
        self.assertAlmostEqual(atlas["mean_plate_cost_inr"], 12.4, places=2)
        self.assertTrue(atlas["all_plates_under_18_inr"])
        self.assertEqual(len(atlas["atlas_merkle_root"]), 64)

    def test_g26_03_hundred_million_learner_continual_evolution_seal(self) -> None:
        calc = OfflineSolarDripEvapotranspirationCropCalculator()
        compiler = VernacularTactileScienceDiagramAtlasCompiler()
        seal_builder = HundredMillionLearnerContinualEvolutionSeal()

        drip_suite = calc.run_canonical_solar_drip_suite()
        atlas = compiler.run_canonical_tactile_science_atlas()
        seal = seal_builder.generate_evolution_seal(drip_suite, atlas)

        self.assertEqual(seal["verified_chunk_count"], 44)
        self.assertIn("G26", seal["verified_chunks"])
        self.assertEqual(seal["scaled_learner_capacity"], 100_000_000)
        self.assertEqual(seal["hydro_infinity_agents"], 1080)
        self.assertEqual(seal["idle_ram_bytes"], 0)
        self.assertEqual(seal["status"], "SOVEREIGN_100M_CONTINUAL_EVOLUTION_VERIFIED")
        self.assertEqual(len(seal["evolution_seal_sha256"]), 64)

    def test_g26_04_end_to_end_cycle_and_html5_hub_generation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest = run_phase_g26_solar_drip_and_tactile_science_atlas_cycle(repo_root)

        self.assertEqual(manifest["phase"], "G26")
        hub = manifest["html5_hub"]
        self.assertEqual(hub["file_name"], "Solar_Drip_Tactile_Science_Atlas_Hub_v5.html")
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
