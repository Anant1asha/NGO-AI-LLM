"""
tests/test_phase_g3_thousand_agent_pdf_html_swarm.py
Unit tests for the 1,080-Agent Hydro Infinity Swarm Orchestrator & Universal PDF-to-Child-HTML5 Master Factory
"""

import os
import sys
import unittest
import asyncio

# Ensure src/ is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from aasha.orchestrator.phase_g3_thousand_agent_pdf_html_swarm import (
    ThousandAgentInfinitySwarmOrchestrator,
    UniversalPDFToChildHTML5MasterFactory,
    TenChapterProductionBatchPackager,
    TOTAL_AGENTS,
    AGENTS_PER_DIVISION,
    DIVISIONS,
    MAX_BUNDLE_BYTES
)

class TestThousandAgentSwarm(unittest.TestCase):
    def setUp(self):
        self.orchestrator = ThousandAgentInfinitySwarmOrchestrator()

    def test_01_swarm_topology_and_zero_idle_ram(self):
        """Verify 6 divisions x 180 stackless coroutines = 1,080 agents with 0 B idle RAM."""
        self.assertEqual(self.orchestrator.total_agent_count, 1080)
        self.assertEqual(self.orchestrator.total_idle_ram, 0)
        for div in DIVISIONS:
            div_agents = self.orchestrator.get_division_agents(div)
            self.assertEqual(len(div_agents), 180, f"Division {div} agent count mismatch")

    def test_02_tln_decomposition_and_bilingual_math_insulation(self):
        """Verify 3..5 TLN nodes, 8-stage flow, and math token insulation."""
        nodes = self.orchestrator._div1_decompose_tln("NCERT-G06-MATH-CH07")
        self.assertIn(len(nodes), [3, 4, 5])
        
        weaved = self.orchestrator._div2_weave_bilingual(nodes)
        formula_node = [n for n in weaved if n.formula_latex]
        self.assertTrue(len(formula_node) > 0)
        self.assertIn("__AASHA_MATH_0__", formula_node[0].formula_latex)

    def test_03_teas_socratic_and_anti_spoiler_audit(self):
        """Verify zero target-answer spoilers in distractor misconception feedback."""
        nodes = self.orchestrator._div1_decompose_tln("NCERT-G06-MATH-CH07")
        assessments = self.orchestrator._div4_audit_teas_socratic(nodes)
        self.assertEqual(len(assessments), len(nodes))
        for a in assessments:
            self.assertEqual(len(a.hints), 4, "Must have 4-tier progressive hints H1..H4")
            for opt in a.options:
                if not opt["is_correct"]:
                    self.assertNotIn("Option A", opt["m"])
                    self.assertNotIn("सही उत्तर", opt["m"])

    def test_04_universal_pdf_to_child_html5_compilation(self):
        """Verify 10 chapters compilation and batch packaging < 20 MiB ceiling."""
        factory = UniversalPDFToChildHTML5MasterFactory(output_dir="Aasha-AI/aasha-pipeline-with-master-json/output/g3_10chapter_pack")
        results = asyncio.run(factory.compile_all_ten_chapters())
        self.assertEqual(len(results), 10)
        
        packager = TenChapterProductionBatchPackager()
        manifest = packager.build_pack_manifest(results)
        self.assertTrue(manifest["under_ceiling"])
        self.assertLess(manifest["total_bytes"], MAX_BUNDLE_BYTES)
        print(f"Total 10 chapters size: {manifest['total_bytes']} bytes (Ceiling: {MAX_BUNDLE_BYTES} bytes)")

if __name__ == "__main__":
    unittest.main()
