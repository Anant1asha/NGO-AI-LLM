"""Top-level Ecosystem Orchestrator bridging AIOS with the PDF -> Learn + Arena Pipeline.

Provides a single deterministic/LLM-capable entry point (`compile_pdf_to_learn_arena`)
that ingests any textbook PDF, synthesizes chapter_spec + LLE, compiles both
Aasha Learn (`*_Learning.html`) and Aasha Arena (`*_Arena.html`), runs `qa/run_qa.js`
with bounded self-healing repair, and exports `teas_content.db.gz`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ROOT = REPO_ROOT / "Aasha-AI" / "aasha-pipeline-with-master-json"
PIPELINE_SRC = PIPELINE_ROOT / "src"

if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))
if "aasha" in sys.modules and hasattr(sys.modules["aasha"], "__path__"):
    _pkg = str(PIPELINE_SRC / "aasha")
    if _pkg not in sys.modules["aasha"].__path__:
        sys.modules["aasha"].__path__.append(_pkg)


def compile_pdf_to_learn_arena(
    pdf_path: str | Path,
    subject: str = "math",
    grade: int = 8,
    provider: str = "offline",
    work_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    jobs_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Execute the full PDF -> Learn + Arena + SQLite + QA ecosystem pipeline."""
    from aasha.config import Config
    from aasha.pipeline.orchestrator import Orchestrator

    cfg = Config.load(None)
    cfg.pipeline.template_path = str(PIPELINE_ROOT / "template" / "v5-engine-template.html")
    cfg.pipeline.defaults_path = str(PIPELINE_ROOT / "config" / "defaults_expanded_v2.json")
    cfg.pipeline.schema_path = str(PIPELINE_ROOT / "schema" / "chapter_spec.schema.json")
    cfg.pipeline.qa_runner = str(PIPELINE_ROOT / "qa" / "run_qa.js")

    if work_dir:
        cfg.pipeline.work_dir = str(work_dir)
    if output_dir:
        cfg.pipeline.output_dir = str(output_dir)
    if jobs_dir:
        cfg.pipeline.jobs_dir = str(jobs_dir)

    orch = Orchestrator(cfg)
    job_id = orch.create_job(
        pdf_path=pdf_path,
        subject=subject,
        grade=grade,
        provider=provider,
        mode="learn-arena",
    )
    job = orch.run_pipeline(job_id)

    return {
        "job_id": job.id,
        "status": job.status,
        "error_stage": job.error_stage,
        "error_message": job.error_message,
        "outputs": job.outputs,
        "qa": job.qa,
        "work_dir": str(orch.get_job_work_dir(job.id)),
    }
