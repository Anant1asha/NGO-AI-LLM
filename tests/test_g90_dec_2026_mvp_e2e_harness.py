import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.g90_dec_2026_mvp_e2e_harness import (
    run_dec_2026_mvp_e2e_certification,
)
from tests.test_core_pipeline_e2e_pdf_to_html5 import _build_minimal_valid_pdf


class TestG90Dec2026MvpE2EHarness(unittest.TestCase):
    def test_full_dec_2026_mvp_e2e_certification_chain(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            p1 = tmp_path / "ncert_g08_force.pdf"
            p2 = tmp_path / "ncvet_g09_solar.pdf"
            p1.write_bytes(_build_minimal_valid_pdf(["Force is a push or pull in pascals."]))
            p2.write_bytes(_build_minimal_valid_pdf(["Solar photovoltaic irrigation pump wiring."]))

            res = run_dec_2026_mvp_e2e_certification(
                repo_root=repo_root,
                pdf_specs=[
                    {"job_id": "MVP-SCI-1", "pdf_path": p1, "subject": "science", "grade": 8},
                    {"job_id": "MVP-VOC-2", "pdf_path": p2, "subject": "vocational", "grade": 9},
                ],
                work_dir=tmp_path / "mvp_out",
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["target_deadline"], "2026-12-31")
            self.assertEqual(res["batch_pdfs_passed"], 2)
            self.assertEqual(res["cohort_pack_modules"], 4)
            self.assertEqual(res["ncvet_readiness"], "APPRENTICE_READY")
            self.assertEqual(res["remedial_flagged"], 1)
            self.assertTrue(res["ota_verified"])
            self.assertTrue(res["all_within_20mib_cap"])
            self.assertTrue(res["zero_external_urls"])
            self.assertGreater(len(res["mvp_certification_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
