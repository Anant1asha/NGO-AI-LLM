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


class _DeterministicMockLLM:
    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        return {"translations": {"barometer": "बैरोमीटर (बैरोमीटर)"}}


class TestCorePipelineE2EPdfToHtml5(unittest.TestCase):
    def test_unified_swarm_and_7agent_core_pipeline_fixes(self):
        repo_root = Path(__file__).resolve().parents[1]
        pipeline_root = repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json"

        import sys
        if str(pipeline_root / "src") not in sys.path:
            sys.path.insert(0, str(pipeline_root / "src"))

        from aasha.agents.lle_agent import LLEAgent
        from aasha.assemble.learn_arena_assembler import LearnArenaAssembler

        router = HydrogenArgonSwarmRouter(repo_root=repo_root)
        lle_contract = WorkerTaskContract(
            task_id="CORE-FIX-LLE",
            goal="Run LLEAgent with compounding WM auto-save & disbursement",
            specialist=SpecialistFamily.LLE_DICTIONARY,
            allowed_paths=[str(pipeline_root / "src/aasha/agents/lle_agent.py")],
            acceptance_criteria=["wm_baseline_count >= 1100"],
        )
        asm_contract = WorkerTaskContract(
            task_id="CORE-FIX-ASM",
            goal="Assemble multi-genre Learn & Arena HTML5 with Finger Scratchpad",
            specialist=SpecialistFamily.OFFLINE_HTML5,
            allowed_paths=[str(pipeline_root / "src/aasha/assemble/learn_arena_assembler.py")],
            acceptance_criteria=["assembler_ready == True"],
        )
        router.validate_isolated_contracts([lle_contract, asm_contract])

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

        swarm_out = router.run_bounded_cycle(lle_contract, argon_executor=_exec, independent_verifier=_qa)
        self.assertEqual(router.state, SwarmRole.CERTIFIED_CHECKPOINT)

        # Run LLEAgent + LearnArenaAssembler on Science & Math chapter specs
        lle_agent = LLEAgent(
            llm=_DeterministicMockLLM(),
            defaults_path=str(pipeline_root / "config" / "defaults.json"),
        )
        self.assertGreaterEqual(len(lle_agent._baseline_wm), 1100)

        assembler = LearnArenaAssembler(
            learn_template_path=pipeline_root / "template" / "v5-engine-template.html",
            arena_template_path=pipeline_root / "template" / "aasha-arena-template.html",
            master_pack_path=pipeline_root / "config" / "lle_master_pack.json",
            defaults_path=pipeline_root / "config" / "defaults_expanded_v2.json",
        )

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            sci_spec = {
                "chapter": {"chapter_id": "NCERT-G08-SCI-CH08", "title": "Force and Pressure", "subject": "science", "grade": 8},
                "WE": {},
                "NODES": [{"title": "Pressure", "emoji": "🔬", "steps": [{"t": "text", "title": "Pressure", "body": "Force over area measured by barometer."}]}],
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

            sci_learn, sci_arena = assembler.assemble(sci_spec, lle_data)
            math_learn, math_arena = assembler.assemble(math_spec, lle_data)

            self.assertIn("Sunlit Virtual Physics Lab", sci_arena)
            self.assertIn("Tactile Geometric Studio", math_arena)
            self.assertIn("aasha-offline-scratchpad-learn", sci_learn)
            self.assertIn("aasha-offline-scratchpad-arena", math_arena)
            for html in (sci_learn, sci_arena, math_learn, math_arena):
                self.assertLessEqual(len(html.encode("utf-8")), 20_971_520)
                self.assertEqual(re.findall(r"\{\{[A-Z_]+_JSON\}\}", html), [])


if __name__ == "__main__":
    unittest.main()
