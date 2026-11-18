"""End-to-End Test for Phase G CLI, Flask Web App, and Aasha Studio PDF -> Learn & Arena Bridge."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json"
PIPELINE_SRC = PIPELINE_ROOT / "src"
SRC_ROOT = REPO_ROOT / "src"

for p in (str(PIPELINE_SRC), str(SRC_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
if "aasha" in sys.modules and hasattr(sys.modules["aasha"], "__path__"):
    _pkg = str(PIPELINE_SRC / "aasha")
    if _pkg not in sys.modules["aasha"].__path__:
        sys.modules["aasha"].__path__.append(_pkg)

from aasha.config import Config
from aasha.web.app import create_app
from tests.test_learn_arena_e2e_pipeline import _make_minimal_pdf


class TestPhaseGStudioWebCliLearnArenaBridge(unittest.TestCase):
    def test_cli_single_learn_arena_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp)
            pdf_path = tp / "Class7_Symmetry_Lab.pdf"
            _make_minimal_pdf(
                pdf_path,
                [
                    "Lines of Symmetry and Rotational Order",
                    "1.1 Mirror Symmetry in Polygons",
                    "A regular polygon of n sides has n lines of symmetry.",
                    "1.2 Rotational Symmetry and Angle of Rotation",
                    "Order of rotational symmetry equals 360 divided by the smallest angle of rotation.",
                    "1.3 Eco Seva Solar Panel Array Layout",
                    "Symmetric spacing prevents mutual shading between adjacent solar rows.",
                    "Q1. How many lines of symmetry does a regular hexagon have?",
                ],
            )
            cfg_yaml = tp / "config.yaml"
            cfg_yaml.write_text(
                f"""
pipeline:
  template_path: "{(PIPELINE_ROOT / 'template/v5-engine-template.html').as_posix()}"
  defaults_path: "{(PIPELINE_ROOT / 'config/defaults_expanded_v2.json').as_posix()}"
  schema_path: "{(PIPELINE_ROOT / 'schema/chapter_spec.schema.json').as_posix()}"
  qa_runner: "{(PIPELINE_ROOT / 'qa/run_qa.js').as_posix()}"
  work_dir: "{(tp / 'work').as_posix()}"
  output_dir: "{(tp / 'out').as_posix()}"
  jobs_dir: "{(tp / 'jobs').as_posix()}"
""",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aasha.cli",
                    "--pdf",
                    str(pdf_path),
                    "--subject",
                    "math",
                    "--grade",
                    "7",
                    "--provider",
                    "offline",
                    "--mode",
                    "learn-arena",
                    "--config",
                    str(cfg_yaml),
                ],
                env={**os.environ, "PYTHONPATH": os.pathsep.join([str(PIPELINE_SRC), str(SRC_ROOT)])},
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Status: PASS", proc.stdout)
            self.assertTrue((tp / "out" / "Class7_Symmetry_Lab_Learning.html").exists())
            self.assertTrue((tp / "out" / "Class7_Symmetry_Lab_Arena.html").exists())

    def test_flask_web_upload_and_dual_preview_download_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp)
            pdf_path = tp / "Class8_Sound_Waves.pdf"
            _make_minimal_pdf(
                pdf_path,
                [
                    "Sound Waves, Frequency and Amplitude",
                    "1.1 Vibrating Bodies Produce Sound",
                    "Sound travels through a medium as longitudinal compression waves.",
                    "1.2 Pitch and Loudness",
                    "Frequency (Hz) determines pitch while amplitude determines loudness (dB).",
                    "1.3 Audible Range and Noise Control",
                    "Human ears detect 20 Hz to 20,000 Hz; tree belts reduce community noise.",
                    "Q1. What is the unit of frequency?",
                ],
            )
            cfg = Config.load(None)
            cfg.pipeline.template_path = str(PIPELINE_ROOT / "template" / "v5-engine-template.html")
            cfg.pipeline.defaults_path = str(PIPELINE_ROOT / "config" / "defaults_expanded_v2.json")
            cfg.pipeline.schema_path = str(PIPELINE_ROOT / "schema" / "chapter_spec.schema.json")
            cfg.pipeline.qa_runner = str(PIPELINE_ROOT / "qa" / "run_qa.js")
            cfg.pipeline.work_dir = str(tp / "work")
            cfg.pipeline.output_dir = str(tp / "out")
            cfg.pipeline.jobs_dir = str(tp / "jobs")

            app = create_app(cfg)
            client = app.test_client()

            res = client.post(
                "/api/upload",
                data={
                    "pdf": (io.BytesIO(pdf_path.read_bytes()), "Class8_Sound_Waves.pdf"),
                    "subject": "science",
                    "grade": "8",
                    "provider": "offline",
                    "mode": "learn-arena",
                    "sync": "1",
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(res.status_code, 200)
            body = res.get_json()
            self.assertEqual(body["status"], "completed")
            job_id = body["job_id"]

            # Preview Learn & Arena
            prev_learn = client.get(f"/job/{job_id}/preview?mode=learn")
            self.assertEqual(prev_learn.status_code, 200)
            self.assertIn(b"const SLIDES =", prev_learn.data)
            prev_learn.close()

            prev_arena = client.get(f"/job/{job_id}/preview?mode=arena")
            self.assertEqual(prev_arena.status_code, 200)
            self.assertIn(b"bootPixi", prev_arena.data)
            prev_arena.close()

            # Download Learn & Arena
            dl_learn = client.get(f"/job/{job_id}/download/learn")
            self.assertEqual(dl_learn.status_code, 200)
            self.assertIn(b"Sound Waves", dl_learn.data)
            dl_learn.close()

            dl_arena = client.get(f"/job/{job_id}/download/arena")
            self.assertEqual(dl_arena.status_code, 200)
            self.assertIn(b"Sound Waves", dl_arena.data)
            dl_arena.close()

    def test_studio_dual_preview_workbench_contract(self) -> None:
        studio_tsx = (REPO_ROOT / "aasha-studio/apps/studio-ui/src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("renderStudioDualPreviewWorkbench", studio_tsx)
        self.assertIn("studio-preview-learn", studio_tsx)
        self.assertIn("studio-preview-arena", studio_tsx)


if __name__ == "__main__":
    unittest.main()
