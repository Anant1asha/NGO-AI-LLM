"""End-to-End Integration Test for the PDF -> Aasha Learn + Aasha Arena Ecosystem Pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
QA_RUNNER = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json" / "qa" / "run_qa.js"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aasha.orchestrator.learn_arena_e2e_orchestrator import compile_pdf_to_learn_arena


def _make_minimal_pdf(path: Path, lines: list[str]) -> None:
    """Create a valid minimal PDF containing extractable text streams."""
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    for idx, ln in enumerate(lines):
        safe = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if idx == 0:
            text_ops.append(f"({safe}) Tj")
        else:
            text_ops.append(f"0 -18 Td ({safe}) Tj")
    text_ops.append("ET")
    stream_data = "\n".join(text_ops).encode("latin-1")

    objs = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n",
        f"4 0 obj<< /Length {len(stream_data)} >>stream\n".encode("latin-1") + stream_data + b"\nendstream\nendobj\n",
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for o in objs:
        offsets.append(len(out))
        out.extend(o)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(f"trailer<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
    path.write_bytes(bytes(out))


class TestLearnArenaE2EPipeline(unittest.TestCase):
    def test_pdf_to_learn_and_arena_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            pdf_path = tmp_p / "Class8_Linear_Equations.pdf"
            _make_minimal_pdf(
                pdf_path,
                [
                    "Linear Equations in One Variable",
                    "1.1 Balancing Both Sides",
                    "An equation is a balance scale where left hand side equals right hand side.",
                    "1.2 Solving Two-Step Equations",
                    "To isolate x, undo addition or subtraction first, then divide by the coefficient.",
                    "1.3 Word Problems and Verification",
                    "Always substitute the found value of x back into the original equation to verify.",
                    "Q1. Solve 2x + 5 = 15 for x.",
                    "Q2. If 3x - 4 = 11, what is the value of x?",
                ],
            )

            res = compile_pdf_to_learn_arena(
                pdf_path=pdf_path,
                subject="math",
                grade=8,
                provider="offline",
                work_dir=tmp_p / "work",
                output_dir=tmp_p / "out",
                jobs_dir=tmp_p / "jobs",
            )

            self.assertEqual(res["status"], "completed", f"Pipeline failed: {res}")
            outputs = res["outputs"]
            learn_html = Path(outputs["learn_html"])
            arena_html = Path(outputs["arena_html"])
            spec_json = Path(outputs["spec"])
            sqlite_gz = Path(outputs["sqlite_gz"])

            self.assertTrue(learn_html.exists(), "Missing Learning HTML")
            self.assertTrue(arena_html.exists(), "Missing Arena HTML")
            self.assertTrue(spec_json.exists(), "Missing Spec JSON")
            self.assertTrue(sqlite_gz.exists(), "Missing SQLite export")

            # Enforce < 20 MiB offline bundle ceiling
            self.assertLess(learn_html.stat().st_size, 20 * 1024 * 1024)
            self.assertLess(arena_html.stat().st_size, 20 * 1024 * 1024)

            # Verify both pass QA independently
            for mode, html_file in [("learn", learn_html), ("arena", arena_html)]:
                proc = subprocess.run(
                    ["node", str(QA_RUNNER), str(html_file), mode],
                    capture_output=True, text=True, check=True,
                )
                report = json.loads(proc.stdout)
                self.assertTrue(report["passed"], f"QA failed for {mode}: {report['failures']}")

            # Verify real chapter content is embedded (not dummy placeholder)
            learn_txt = learn_html.read_text(encoding="utf-8")
            arena_txt = arena_html.read_text(encoding="utf-8")
            self.assertIn("Linear Equations in One Variable", learn_txt)
            self.assertIn("Linear Equations in One Variable", arena_txt)
            self.assertIn("bootPixi", arena_txt)
            self.assertIn("bootCanvas2D", arena_txt)
            self.assertIn("const SLIDES =", learn_txt)
            self.assertIn("const QUESTIONS =", arena_txt)


if __name__ == "__main__":
    unittest.main()
