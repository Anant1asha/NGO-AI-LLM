import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.g92_teacher_copilot_lesson_prep import (
    generate_offline_lesson_prep_from_pdf,
)
from tests.test_core_pipeline_e2e_pdf_to_html5 import _build_minimal_valid_pdf


class TestG92TeacherCopilotLessonPrep(unittest.TestCase):
    def test_generates_30min_bilingual_lesson_prep_from_pdf(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            pdf_p = Path(tmp) / "ncert_g08_friction.pdf"
            pdf_p.write_bytes(
                _build_minimal_valid_pdf([
                    "Chapter 9: Friction",
                    "Friction opposes relative motion between surfaces in contact.",
                    "Lubricants reduce friction in bicycle chains and machinery.",
                ])
            )
            res = generate_offline_lesson_prep_from_pdf(repo_root, pdf_p, subject="science", grade=8)
            self.assertTrue(res["ok"])
            self.assertEqual(res["duration_minutes"], 30)
            self.assertEqual(len(res["segments"]), 4)
            self.assertIn("friction", res["key_terms"])
            self.assertTrue(res["zero_external_urls"])
            self.assertGreater(len(res["lesson_prep_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
