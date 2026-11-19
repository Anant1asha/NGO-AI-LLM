import json
import re
import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.hydrogen_argon_swarm_router import (
    HydrogenArgonSwarmRouter,
    SpecialistFamily,
    SwarmRole,
    WorkerResult,
    WorkerTaskContract,
)


def _build_minimal_valid_pdf(text_lines: list[str]) -> bytes:
    """Create a valid single-page PDF containing arbitrary textbook lines."""
    stream_ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    for idx, line in enumerate(text_lines):
        esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if idx > 0:
            stream_ops.append("0 -18 Td")
        stream_ops.append(f"({esc}) Tj")
    stream_ops.append("ET")
    stream = "\n".join(stream_ops).encode("latin-1")

    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
    return bytes(out)


class _DeterministicMockLLM:
    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        if "content_map" in system_prompt or "concepts" in system_prompt.lower():
            return {
                "subject": "science",
                "grade": 8,
                "title": "Force and Pressure",
                "concepts": [
                    {"id": "c1", "title": "Pressure Formula", "summary": "Pressure equals Force divided by Area (P = F/A).", "key_terms": ["pressure", "force", "area", "pascal"]},
                    {"id": "c2", "title": "Atmospheric Barometer", "summary": "Air exerts atmospheric pressure measured by a barometer.", "key_terms": ["barometer", "atmosphere"]},
                ],
                "formulas": ["P = F / A"],
            }
        if "translations" in system_prompt:
            return {"translations": {"barometer": "बैरोमीटर (बैरोमीटर)"}}
        if "NODES" in system_prompt:
            return {
                "chapter": {"chapter_id": "NCERT-G08-SCI-CH08", "title": "Force and Pressure", "subject": "science", "grade": 8, "storage_key": "aasha_force_v5", "emoji": "🔬"},
                "BADGES": [{"id": "b1", "name": "Pressure Pro", "ic": "🔬", "desc": "Mastered P=F/A"}],
                "WE": {"we_1": {"title": "Calculate Pressure", "question": "Find P if F=100N, A=2m^2.", "steps": [{"text": "P = 100 / 2 = 50 Pa", "c": "green", "final": True}], "check": {"q": "What is P?", "opts": None}}},
                "SOLVE": {},
                "NODES": [{"title": "Force and Pressure", "emoji": "🔬", "steps": [{"t": "text", "title": "Pressure", "body": "Force over area measured by barometer in pascals."}, {"t": "quiz", "q": {"q": "SI unit of pressure?", "opts": None}}]}],
            }
        return {"assessments": []}


class TestCorePipelineE2EPdfToHtml5(unittest.TestCase):
    def test_unified_swarm_and_7agent_core_pipeline_fixes(self):
        repo_root = Path(__file__).resolve().parents[1]
        pipeline_root = repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json"

        import sys
        if str(pipeline_root / "src") not in sys.path:
            sys.path.insert(0, str(pipeline_root / "src"))

        from aasha.agents.ingest_agent import IngestAgent
        from aasha.agents.lle_agent import LLEAgent
        from aasha.agents.qa_agent import QAAgent
        from aasha.assemble.learn_arena_assembler import LearnArenaAssembler

        router = HydrogenArgonSwarmRouter(repo_root=repo_root)
        lle_contract = WorkerTaskContract(
            task_id="CORE-FIX-LLE",
            goal="Run LLEAgent with compounding WM auto-save & disbursement",
            specialist=SpecialistFamily.LLE_DICTIONARY,
            allowed_paths=[str(pipeline_root / "src/aasha/agents/lle_agent.py")],
            acceptance_criteria=["wm_baseline_count >= 1100"],
        )

        def _exec(task: WorkerTaskContract) -> WorkerResult:
            agent = LLEAgent(
                llm=_DeterministicMockLLM(),
                defaults_path=str(pipeline_root / "config" / "defaults.json"),
            )
            return WorkerResult(
                task_id=task.task_id,
                worker_id="argon-lle-worker",
                status="PASS" if len(agent._baseline_wm) >= 1100 else "FAIL",
                files_changed=list(task.allowed_paths),
                raw_evidence={"wm_baseline_count": len(agent._baseline_wm)},
            )

        def _qa(task: WorkerTaskContract, result: WorkerResult) -> WorkerResult:
            return WorkerResult(
                task_id=task.task_id,
                worker_id="hydrogen-independent-qa",
                status="PASS" if result.status == "PASS" else "FAIL",
                files_changed=[],
                raw_evidence={"certified": True},
            )

        router.run_bounded_cycle(lle_contract, argon_executor=_exec, independent_verifier=_qa)
        self.assertEqual(router.state, SwarmRole.CERTIFIED_CHECKPOINT)

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            pdf_path = work_dir / "source.pdf"
            pdf_path.write_bytes(
                _build_minimal_valid_pdf([
                    "Chapter 8: Force and Pressure",
                    "Force applied over contact area produces pressure.",
                    "SI unit of pressure is Pascal measured by barometer.",
                    "Q1. Calculate pressure when Force is 100 N and Area is 2 sq m.",
                ])
            )

            # Stage 1: Real PDF Ingestion (IngestAgent)
            ingest_res = IngestAgent().run(work_dir, {"pdf_path": str(pdf_path)})
            self.assertGreaterEqual(ingest_res["page_count"], 1)
            raw_extract = json.loads((work_dir / "raw_extract.json").read_text(encoding="utf-8"))
            self.assertIn("Force", raw_extract["pages"][0]["text"])

            # Stage 5: Compounding LLEAgent
            lle_agent = LLEAgent(
                llm=_DeterministicMockLLM(),
                defaults_path=str(pipeline_root / "config" / "defaults.json"),
            )
            sci_spec = {
                "chapter": {"chapter_id": "NCERT-G08-SCI-CH08", "title": "Force and Pressure", "subject": "science", "grade": 8},
                "WE": {},
                "NODES": [{"title": "Pressure", "emoji": "🔬", "steps": [{"t": "text", "title": "Pressure", "body": raw_extract["pages"][0]["text"]}]}],
            }
            math_spec = {
                "chapter": {"chapter_id": "NCERT-G06-MATH-CH07", "title": "Fractions", "subject": "math", "grade": 6},
                "WE": {},
                "NODES": [{"title": "Fractions", "emoji": "📐", "steps": [{"t": "text", "title": "Slices", "body": "Numerator over denominator."}]}],
            }
            (work_dir / "chapter_spec.json").write_text(json.dumps(sci_spec), encoding="utf-8")
            lle_res = lle_agent.run(work_dir, {})
            self.assertGreaterEqual(lle_res["wm_count"], 1100)
            lle_data = json.loads((work_dir / "lle.json").read_text(encoding="utf-8"))

            # Stage 6: Multi-Genre LearnArenaAssembler
            assembler = LearnArenaAssembler(
                learn_template_path=pipeline_root / "template" / "v5-engine-template.html",
                arena_template_path=pipeline_root / "template" / "aasha-arena-template.html",
                master_pack_path=pipeline_root / "config" / "lle_master_pack.json",
                defaults_path=pipeline_root / "config" / "defaults_expanded_v2.json",
            )
            sci_learn, sci_arena = assembler.assemble(sci_spec, lle_data)
            math_learn, math_arena = assembler.assemble(math_spec, lle_data)

            self.assertIn("Sunlit Virtual Physics Lab", sci_arena)
            self.assertIn("Tactile Geometric Studio", math_arena)
            self.assertIn("aasha-offline-scratchpad-learn", sci_learn)
            self.assertIn("aasha-offline-scratchpad-arena", math_arena)
            for html in (sci_learn, sci_arena, math_learn, math_arena):
                self.assertLessEqual(len(html.encode("utf-8")), 20_971_520)
                self.assertEqual(re.findall(r"\{\{[A-Z_]+_JSON\}\}", html), [])

            # Stage 7: Independent QAAgent check on assembled chapter.html
            (work_dir / "chapter.html").write_text(sci_learn, encoding="utf-8")
            qa_res = QAAgent().run(work_dir, {})
            self.assertGreaterEqual(qa_res["checks_passed"], 10)


if __name__ == "__main__":
    unittest.main()
