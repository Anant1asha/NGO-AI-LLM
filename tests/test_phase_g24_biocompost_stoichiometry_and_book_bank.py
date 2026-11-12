"""
Unit tests for Phase G24: Autonomous Offline Rural Bio-Compost & Soil Microbiome Stoichiometry Lab,
Vernacular Peer-Led Library Book-Bank Ledger & 100,000,000-Learner Sovereign Centennial Seal.
"""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g24_biocompost_stoichiometry_and_book_bank import (
    OfflineBioCompostSoilMicrobiomeStoichiometryLab,
    VernacularPeerLedLibraryBookBankLedger,
    HundredMillionLearnerSovereignCentennialSeal,
    run_phase_g24_biocompost_stoichiometry_and_book_bank_cycle,
)


class TestPhaseG24BioCompostStoichiometryAndBookBank(unittest.TestCase):
    def test_g24_01_biocompost_stoichiometry_optimal_thermophilic_window(self) -> None:
        lab = OfflineBioCompostSoilMicrobiomeStoichiometryLab()
        suite = lab.run_canonical_village_compost_suite()
        pit = suite["primary_pit"]

        self.assertEqual(pit["pit_id"], "PIT-UP-GN-BIO-2401")
        self.assertEqual(pit["layer_count"], 3)
        self.assertEqual(pit["total_feedstock_mass_kg"], 200.0)
        self.assertEqual(pit["total_pit_mass_kg"], 235.0)
        self.assertTrue(25.0 <= pit["blended_cn_ratio"] <= 35.0)
        self.assertAlmostEqual(pit["blended_cn_ratio"], 30.83, places=2)
        self.assertTrue(50.0 <= pit["blended_moisture_pct"] <= 65.0)
        self.assertAlmostEqual(pit["blended_moisture_pct"], 56.55, places=2)
        self.assertAlmostEqual(pit["mature_humus_yield_kg"], 63.3, places=2)
        self.assertEqual(pit["thermophilic_phase_status"], "OPTIMAL_THERMOPHILIC_55C_65C")
        self.assertEqual(len(pit["stoichiometry_sha256"]), 64)

    def test_g24_02_vernacular_peer_led_book_bank_9_scripts(self) -> None:
        ledger_engine = VernacularPeerLedLibraryBookBankLedger()
        report = ledger_engine.run_canonical_book_bank_ledger()

        self.assertEqual(report["active_script_count"], 9)
        self.assertEqual(report["entry_count"], 9)
        self.assertEqual(report["total_books_loaned"], 280)
        self.assertEqual(report["on_time_returns"], 273)
        self.assertAlmostEqual(report["on_time_return_rate_pct"], 97.5, places=2)
        self.assertEqual(report["books_repaired_by_peers"], 38)
        self.assertEqual(report["total_steward_seva_points"], 1935)
        self.assertEqual(len(report["tip_merkle_root"]), 64)

    def test_g24_03_hundred_million_learner_sovereign_centennial_seal(self) -> None:
        lab = OfflineBioCompostSoilMicrobiomeStoichiometryLab()
        ledger_engine = VernacularPeerLedLibraryBookBankLedger()
        seal_builder = HundredMillionLearnerSovereignCentennialSeal()

        compost_suite = lab.run_canonical_village_compost_suite()
        book_bank = ledger_engine.run_canonical_book_bank_ledger()
        seal = seal_builder.generate_centennial_seal(compost_suite, book_bank)

        self.assertEqual(seal["verified_chunk_count"], 42)
        self.assertIn("G24", seal["verified_chunks"])
        self.assertEqual(seal["scaled_learner_capacity"], 100_000_000)
        self.assertEqual(seal["hydro_infinity_agents"], 1080)
        self.assertEqual(seal["idle_ram_bytes"], 0)
        self.assertEqual(seal["status"], "SOVEREIGN_100M_LEARNER_CENTENNIAL_READY")
        self.assertEqual(len(seal["centennial_seal_sha256"]), 64)

    def test_g24_04_end_to_end_cycle_and_html5_hub_generation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest = run_phase_g24_biocompost_stoichiometry_and_book_bank_cycle(repo_root)

        self.assertEqual(manifest["phase"], "G24")
        hub = manifest["html5_hub"]
        self.assertEqual(hub["file_name"], "BioCompost_Stoichiometry_Book_Bank_Hub_v5.html")
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
