import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g79_batch_pdf_benchmark_and_cohort_pack import (  # noqa: E402
    build_cohort_offline_pack_zip,
    run_batch_pdf_benchmark,
)
from tests.test_core_pipeline_e2e_pdf_to_html5 import _build_minimal_valid_pdf  # noqa: E402


class TestG79BatchPdfBenchmarkAndCohortPack(unittest.TestCase):
    def test_batch_pdf_benchmark_and_offline_cohort_pack_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdfs = [
                {
                    "job_id": "G79-SCI-01",
                    "pdf_path": tmp_path / "ncert_g08_force_pressure.pdf",
                    "subject": "science",
                    "grade": 8,
                    "lines": [
                        "Class 8 Science: Force and Pressure",
                        "Force is a push or pull. Pressure equals force divided by area in pascals.",
                    ],
                },
                {
                    "job_id": "G79-MATH-02",
                    "pdf_path": tmp_path / "ncert_g07_linear_equations.pdf",
                    "subject": "mathematics",
                    "grade": 7,
                    "lines": [
                        "Class 7 Mathematics: Linear Equations",
                        "An equation balances two algebraic expressions with one variable and constant.",
                    ],
                },
                {
                    "job_id": "G79-VOC-03",
                    "pdf_path": tmp_path / "ncvet_g09_solar_pump_basics.pdf",
                    "subject": "vocational",
                    "grade": 9,
                    "lines": [
                        "NCVET Grade 9: Solar Water Pump Wiring",
                        "Photovoltaic panels convert sunlight into direct current to power farm irrigation pumps.",
                    ],
                },
            ]
            for p in pdfs:
                p["pdf_path"].write_bytes(_build_minimal_valid_pdf(p["lines"]))

            batch_out = tmp_path / "batch_out"
            report = run_batch_pdf_benchmark(REPO_ROOT, pdfs, output_dir=batch_out)

            self.assertTrue(report["all_passed"])
            self.assertEqual(report["total_pdfs"], 3)
            self.assertEqual(report["passed_pdfs"], 3)
            self.assertTrue(report["all_within_20mib_cap"])
            self.assertTrue(report["zero_external_urls"])
            self.assertGreater(len(report["batch_benchmark_sha256"]), 32)
            for item in report["results"]:
                self.assertGreaterEqual(item["qa_checks_passed"], 10)
                self.assertGreaterEqual(item["wm_count"], 1100)

            pack_zip = tmp_path / "cohort_pack_g79.zip"
            pack_res = build_cohort_offline_pack_zip(report, pack_zip, center_id="CENTER-UP-GN-01")
            self.assertTrue(pack_res["ok"])
            self.assertEqual(pack_res["module_count"], 6)
            self.assertTrue(pack_zip.exists())

            with zipfile.ZipFile(pack_zip, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("cohort_pack_manifest.json", names)
                self.assertIn("benchmark_report.json", names)
                manifest = json.loads(zf.read("cohort_pack_manifest.json").decode("utf-8"))
                self.assertEqual(manifest["schema_version"], "aasha.offline.cohort.pack.v2")
                self.assertEqual(manifest["module_count"], 6)
                self.assertTrue(all(m["within_20mib_child_cap"] for m in manifest["modules"]))


if __name__ == "__main__":
    unittest.main()
