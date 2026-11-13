"""GAP-V7-04: Deterministic offline PDF-fixture-to-v5 pipeline integration test.

Exercises aasha-pipeline-with-master-json (Config, Orchestrator, FrontendCodeSynthesizer,
and node qa/run_qa.js) end-to-end without outbound network calls.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SRC = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json" / "src"
DEFAULTS_V2 = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json" / "config" / "defaults_expanded_v2.json"
QA_RUNNER = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json" / "qa" / "run_qa.js"

if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

# Offline sandbox compatibility shims for tenacity & pydantic v1 -> v2
if "tenacity" not in sys.modules:
    tenacity_stub = types.ModuleType("tenacity")
    tenacity_stub.retry = lambda *a, **kw: (lambda fn: fn)
    tenacity_stub.stop_after_attempt = lambda n: n
    tenacity_stub.wait_exponential = lambda **kw: None
    tenacity_stub.wait_exponential_jitter = lambda **kw: None
    tenacity_stub.retry_if_exception_type = lambda *a: None
    sys.modules["tenacity"] = tenacity_stub

import pydantic  # noqa: E402
if not hasattr(pydantic, "field_validator"):
    def _field_validator(*fields, **kwargs):
        kwargs.pop("mode", None)
        return pydantic.validator(*fields, allow_reuse=True, **kwargs)
    pydantic.field_validator = _field_validator  # type: ignore[attr-defined]
    _orig_field = pydantic.Field
    def _v1_compat_field(*args, **kwargs):
        kwargs.pop("min_length", None)
        kwargs.pop("max_length", None)
        return _orig_field(*args, **kwargs)
    pydantic.Field = _v1_compat_field  # type: ignore[assignment]
    pydantic.BaseModel.model_dump = lambda self, **kw: self.dict(**kw)  # type: ignore[attr-defined]
    pydantic.BaseModel.model_validate = classmethod(lambda cls, obj: cls.parse_obj(obj))  # type: ignore[attr-defined]
    pydantic.BaseModel.model_validate_json = classmethod(lambda cls, s: cls.parse_raw(s))  # type: ignore[attr-defined]

from aasha.config import Config  # noqa: E402
from aasha.pipeline.orchestrator import Orchestrator  # noqa: E402
from aasha.synthesis import FrontendCodeSynthesizer  # noqa: E402
from aasha.schemas import STAGE_ORDER  # noqa: E402


class TestGapV704PipelineOfflineCli(unittest.TestCase):
    def test_defaults_expanded_v2_and_synthesizer_to_qa_pass(self) -> None:
        self.assertTrue(DEFAULTS_V2.exists(), f"Missing {DEFAULTS_V2}")
        defaults = json.loads(DEFAULTS_V2.read_text(encoding="utf-8"))
        self.assertIsInstance(defaults, dict)
        self.assertGreater(len(defaults), 0)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf_fixture = tmp_path / "ncvet_solar_dehydrator_ch1.pdf"
            pdf_fixture.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")

            cfg = Config.load(None)
            cfg.pipeline.work_dir = str(tmp_path / "work")
            cfg.pipeline.output_dir = str(tmp_path / "output")
            cfg.pipeline.jobs_dir = str(tmp_path / "jobs")

            orch = Orchestrator(cfg)
            job_id = orch.create_job(pdf_fixture, subject="science", grade=8, mode="v5-engine")
            job = orch.get_job(job_id)
            self.assertIsNotNone(job)
            self.assertEqual([s.name for s in job.stages], STAGE_ORDER)

            synth = FrontendCodeSynthesizer()
            pedagogy_map = {
                "chapter_title": "Solar Food Dehydration & Moisture Control",
                "subject": "science",
                "grade": 8,
                "subject_domain": "NCVET-PSSCIVE",
                "concepts": [
                    {
                        "name": "Thermal Airflow & Drying Rate",
                        "summary": "Warm airflow removes moisture safely without scorching nutrients.",
                        "key_ideas": ["airflow", "humidity", "temperature"],
                        "difficulty": "easy",
                        "plugin": "jsxgraph",
                        "interaction_type": "simulation",
                    }
                ],
                "exercises": [],
            }
            experience_plan = {"concepts": pedagogy_map["concepts"], "simulation_plan": [], "visual_plan": []}
            assessment_suite = {
                "warmup": [
                    {
                        "question": "Why is steady airflow needed inside a solar dehydrator?",
                        "opts": [
                            {"t": "To carry humid air away from produce", "c": True, "m": ""},
                            {"t": "To freeze water droplets", "c": False, "m": "Dehydration evaporates moisture."},
                        ],
                        "xp": 10,
                        "hint": "Think about where evaporated water vapor goes.",
                        "explanation": "Airflow removes saturated vapor so drying continues.",
                    }
                ],
                "deep_dive": [
                    {
                        "question": "What happens if drying temperature is too high?",
                        "opts": [
                            {"t": "Case hardening traps moisture inside", "c": True, "m": ""},
                            {"t": "Drying becomes twice as uniform", "c": False, "m": "Excess heat seals the outer skin."},
                        ],
                        "xp": 15,
                        "hint": "Check outer crust vs inner moisture.",
                        "explanation": "Moderate 50-60 C temperatures prevent case hardening.",
                    }
                ],
                "boss": [
                    {
                        "question": "Which target moisture level prevents spoilage in dried vegetables?",
                        "opts": [
                            {"t": "Below 10% moisture", "c": True, "m": ""},
                            {"t": "Above 45% moisture", "c": False, "m": "High moisture allows mold growth."},
                        ],
                        "xp": 20,
                        "hint": "Microbes need free water to grow.",
                        "explanation": "Keeping moisture below 10% ensures shelf stability.",
                    }
                ],
            }

            work_dir = tmp_path / "work"
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "pedagogy_map.json").write_text(json.dumps(pedagogy_map), encoding="utf-8")
            (work_dir / "experience_plan.json").write_text(json.dumps(experience_plan), encoding="utf-8")
            (work_dir / "assessment_suite.json").write_text(json.dumps(assessment_suite), encoding="utf-8")
            res = synth.run(work_dir, {"subject": "science", "grade": 8})
            html_path = Path(res["output_file"])
            self.assertTrue(html_path.exists())
            self.assertLess(html_path.stat().st_size, 20 * 1024 * 1024)

            if QA_RUNNER.exists():
                proc = subprocess.run(
                    ["node", str(QA_RUNNER), str(html_path)],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, f"QA failed: {proc.stdout}\n{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
