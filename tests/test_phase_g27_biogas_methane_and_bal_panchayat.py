"""
Unit tests for Phase G27: Autonomous Offline Rural Biogas Digester Methane Stoichiometry & Calorific Enthalpy Lab,
Vernacular Bal-Panchayat Civic Budget Ledger, 1,080-Agent Hydro Infinity Swarm Dispatch &
100,000,000-Learner Sovereign Gram-Swaraj Seal.
"""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g27_biogas_methane_and_bal_panchayat import (
    HydroInfinity1080SwarmCoordinator,
    OfflineBiogasMethaneCalorificEnthalpyLab,
    VernacularBalPanchayatCivicBudgetLedger,
    HundredMillionLearnerGramSwarajSeal,
    run_phase_g27_biogas_methane_and_bal_panchayat_cycle,
)


class TestPhaseG27BiogasMethaneAndBalPanchayat(unittest.TestCase):
    def test_g27_01_hydro_infinity_1080_swarm_and_biogas_enthalpy_lab(self) -> None:
        swarm = HydroInfinity1080SwarmCoordinator().dispatch_full_swarm("G27")
        self.assertEqual(swarm["division_count"], 6)
        self.assertEqual(swarm["total_coroutine_agents"], 1080)
        self.assertEqual(swarm["total_idle_ram_bytes"], 0)
        self.assertEqual(swarm["total_rap_events_processed"], 2160)
        self.assertTrue(swarm["all_worktrees_isolated"])

        lab = OfflineBiogasMethaneCalorificEnthalpyLab()
        suite = lab.run_canonical_biogas_suite()
        dig = suite["primary_digester"]

        self.assertEqual(dig["digester_id"], "DIGESTER-UP-GN-GOBAR-2701")
        self.assertAlmostEqual(dig["dry_solids_kg_day"], 50.0, places=2)
        self.assertAlmostEqual(dig["volatile_solids_kg_day"], 40.0, places=2)
        self.assertAlmostEqual(dig["raw_biogas_m3_day"], 14.0, places=2)
        self.assertAlmostEqual(dig["pure_methane_m3_day"], 8.4, places=2)
        self.assertAlmostEqual(dig["gross_calorific_mj_day"], 300.72, places=2)
        self.assertAlmostEqual(dig["useful_cooking_enthalpy_mj_day"], 180.43, places=2)
        self.assertAlmostEqual(dig["lpg_equivalent_saved_kg_day"], 6.52, places=2)
        self.assertAlmostEqual(dig["bio_slurry_fertilizer_kg_day"], 44.0, places=2)
        self.assertEqual(len(dig["biogas_enthalpy_sha256"]), 64)

    def test_g27_02_vernacular_bal_panchayat_civic_budget_ledger_9_scripts(self) -> None:
        ledger_engine = VernacularBalPanchayatCivicBudgetLedger()
        report = ledger_engine.run_canonical_bal_panchayat_ledger()

        self.assertEqual(report["active_script_count"], 9)
        self.assertEqual(report["resolution_count"], 9)
        self.assertAlmostEqual(report["total_allocated_inr"], 45000.0, places=2)
        self.assertAlmostEqual(report["total_disbursed_inr"], 45000.0, places=2)
        self.assertAlmostEqual(report["audit_variance_inr"], 0.0, places=2)
        self.assertTrue(report["zero_variance_verified"])
        self.assertEqual(report["total_student_voters"], 540)
        self.assertEqual(len(report["tip_merkle_root"]), 64)

    def test_g27_03_hundred_million_learner_gram_swaraj_seal(self) -> None:
        swarm = HydroInfinity1080SwarmCoordinator().dispatch_full_swarm("G27")
        biogas = OfflineBiogasMethaneCalorificEnthalpyLab().run_canonical_biogas_suite()
        panchayat = VernacularBalPanchayatCivicBudgetLedger().run_canonical_bal_panchayat_ledger()
        seal = HundredMillionLearnerGramSwarajSeal().generate_gram_swaraj_seal(
            swarm, biogas, panchayat
        )

        self.assertEqual(seal["verified_chunk_count"], 45)
        self.assertIn("G27", seal["verified_chunks"])
        self.assertEqual(seal["scaled_learner_capacity"], 100_000_000)
        self.assertEqual(seal["hydro_infinity_agents"], 1080)
        self.assertEqual(seal["idle_ram_bytes"], 0)
        self.assertEqual(seal["status"], "SOVEREIGN_100M_GRAM_SWARAJ_SWARM_VERIFIED")
        self.assertEqual(len(seal["gram_swaraj_seal_sha256"]), 64)

    def test_g27_04_end_to_end_cycle_and_html5_hub_generation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest = run_phase_g27_biogas_methane_and_bal_panchayat_cycle(repo_root)

        self.assertEqual(manifest["phase"], "G27")
        hub = manifest["html5_hub"]
        self.assertEqual(hub["file_name"], "Biogas_Methane_Bal_Panchayat_Swarm_Hub_v5.html")
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
