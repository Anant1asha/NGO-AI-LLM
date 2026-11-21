import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.g91_multi_board_curriculum_auditor import (
    compile_and_audit_multi_board_pack,
)
from tests.test_core_pipeline_e2e_pdf_to_html5 import _build_minimal_valid_pdf


class TestG91MultiBoardCurriculumAuditor(unittest.TestCase):
    def test_compiles_and_audits_four_boards_offline(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            specs = []
            for idx, (board, subj, grade, line) in enumerate([
                ("NCERT", "science", 8, "Force and pressure in pascals."),
                ("UPMSP", "mathematics", 7, "Linear equations in one variable."),
                ("CBSE", "social", 9, "Village Palampur farming and non-farm activities."),
                ("NCVET", "vocational", 9, "Solar irrigation pump wiring and safety."),
            ], start=1):
                pdf_p = tmp_path / f"{board.lower()}_g{grade}_{subj}.pdf"
                pdf_p.write_bytes(_build_minimal_valid_pdf([f"{board} Grade {grade}: {line}"]))
                specs.append({"board": board, "job_id": f"G91-{board}-{idx}", "pdf_path": pdf_p, "subject": subj, "grade": grade})

            res = compile_and_audit_multi_board_pack(repo_root, specs, tmp_path / "out")
            self.assertTrue(res["ok"])
            self.assertEqual(res["chapters_compiled"], 4)
            self.assertEqual(res["boards_covered"], ["CBSE", "NCERT", "NCVET", "UPMSP"])
            self.assertTrue(res["all_within_20mib_cap"])
            self.assertTrue(res["zero_external_urls"])
            self.assertGreater(len(res["multi_board_audit_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
