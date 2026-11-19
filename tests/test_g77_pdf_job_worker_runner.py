import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.g77_pdf_job_worker_runner import (
    execute_pdf_job_through_7agent_pipeline,
)
from tests.test_core_pipeline_e2e_pdf_to_html5 import _build_minimal_valid_pdf


class TestG77PdfJobWorkerRunner(unittest.TestCase):
    def test_execute_queued_pdf_job_produces_certified_learn_and_arena_html(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            pdf_path = tmp_dir / "NCERT_G08_Heat_Transfer.pdf"
            pdf_path.write_bytes(
                _build_minimal_valid_pdf([
                    "Chapter 4: Heat Transfer",
                    "Conduction, convection, and radiation transfer thermal energy.",
                    "A clinical thermometer measures temperature in Celsius.",
                ])
            )
            res = execute_pdf_job_through_7agent_pipeline(
                repo_root=repo_root,
                job_id="PDFJOB-G77-TEST-01",
                pdf_path=pdf_path,
                subject="science",
                grade=7,
                output_dir=tmp_dir / "out",
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["status"], "COMPILED_READY")
            self.assertTrue(res["within_20mib_child_cap"])
            self.assertGreaterEqual(res["wm_count"], 1100)
            self.assertGreaterEqual(res["qa_checks_passed"], 10)
            self.assertTrue(Path(res["learn_html_path"]).is_file())
            self.assertTrue(Path(res["arena_html_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
