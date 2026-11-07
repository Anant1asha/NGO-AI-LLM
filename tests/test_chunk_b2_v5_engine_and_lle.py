"""
Unit tests for AASHA AIOS V3 Chunk B2:
6-Agent v5-engine synthesis & 8-Layer LLE (60/40 English-Hindi dictionary injection
with 296 WM + 46 CONN dictionaries and math token insulation).
"""

import json
import tempfile
import unittest
from pathlib import Path

from aasha.orchestrator.method_b_orchestrator import (
    EightLayerLLEBilingualInjector,
    LLE_EIGHT_LAYERS,
    SixAgentV5EngineSynthesizer,
    V5_SIX_ENGINES,
    V5_SIX_SYNTHESIS_AGENTS,
    build_canonical_lle_dictionaries,
    execute_chunk_b2_v5_synthesis_and_lle_cycle,
    insulate_math_tokens,
    restore_math_tokens,
    write_canonical_lle_defaults_json,
)
from aasha.orchestrator.zero_approval_async_ide_bus import SourcePDFSha256LockAndTLNValidator


class TestChunkB2V5EngineAndLLE(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_b2_01_canonical_lle_dictionaries_have_exact_296_wm_and_46_conn(self) -> None:
        dicts = build_canonical_lle_dictionaries()
        self.assertEqual(dicts["wm_count"], 296)
        self.assertEqual(dicts["conn_count"], 46)
        self.assertEqual(len(dicts["WM"]), 296)
        self.assertEqual(len(dicts["CONN"]), 46)
        self.assertEqual(len(dicts["dictionary_sha256"]), 64)

    def test_b2_02_write_canonical_defaults_json_creates_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta = write_canonical_lle_defaults_json(tmp)
            self.assertEqual(meta["wm_count"], 296)
            self.assertEqual(meta["conn_count"], 46)
            defaults_file = Path(meta["defaults_json_path"])
            self.assertTrue(defaults_file.is_file())
            parsed = json.loads(defaults_file.read_text(encoding="utf-8"))
            self.assertEqual(parsed["wm_count"], 296)
            self.assertEqual(parsed["conn_count"], 46)

    def test_b2_03_math_token_insulation_and_restoration_roundtrip(self) -> None:
        raw = "Therefore, the fraction $\\frac{3}{4}$ plus $\\frac{1}{4}$ equals $1$."
        insulated, tmap = insulate_math_tokens(raw)
        self.assertEqual(len(tmap), 3)
        self.assertNotIn("\\frac{3}{4}", insulated)
        restored = restore_math_tokens(insulated, tmap)
        self.assertEqual(restored, raw)

    def test_b2_04_eight_layer_lle_injector_weaves_wm_and_conn_without_corrupting_math(self) -> None:
        injector = EightLayerLLEBilingualInjector()
        res = injector.weave_bilingual_segment(
            "Therefore, a fraction has a numerator and a denominator like $\\frac{2}{5}$."
        )
        self.assertTrue(res.ratio_compliant)
        self.assertEqual(res.english_ratio, 0.60)
        self.assertEqual(res.hindi_ratio, 0.40)
        self.assertEqual(res.math_tokens_preserved, 1)
        self.assertGreaterEqual(res.wm_terms_injected, 3)
        self.assertGreaterEqual(res.conn_terms_injected, 1)
        self.assertIn("$\\frac{2}{5}$", res.synthesized_text)
        self.assertEqual(tuple(res.layers_executed), LLE_EIGHT_LAYERS)

    def test_b2_05_six_agent_v5_synthesizer_executes_all_6_agents_and_6_engines(self) -> None:
        b1 = SourcePDFSha256LockAndTLNValidator(self.repo_root)
        spec = b1.build_canonical_chapter_spec()
        synth = SixAgentV5EngineSynthesizer(self.repo_root)
        manifest = synth.synthesize_v5_chapter_bundle(spec)
        self.assertEqual(manifest["chunk_id"], "B2")
        self.assertEqual(tuple(manifest["agents_executed"]), V5_SIX_SYNTHESIS_AGENTS)
        self.assertEqual(tuple(manifest["engines_populated"]), V5_SIX_ENGINES)
        self.assertEqual(len(manifest["synthesized_nodes"]), 4)
        self.assertEqual(manifest["external_url_count"], 0)
        self.assertTrue(manifest["under_20mib_ceiling"])

    def test_b2_06_synthesized_nodes_enforce_tap_select_and_forbid_draggable(self) -> None:
        b1 = SourcePDFSha256LockAndTLNValidator(self.repo_root)
        spec = b1.build_canonical_chapter_spec()
        synth = SixAgentV5EngineSynthesizer(self.repo_root)
        manifest = synth.synthesize_v5_chapter_bundle(spec)
        for node in manifest["synthesized_nodes"]:
            self.assertEqual(node["interaction_mode"], 'data-tap-select="true"')
            self.assertFalse(node["draggable_used"])

    def test_b2_07_synthesizer_rejects_invalid_node_bounds(self) -> None:
        synth = SixAgentV5EngineSynthesizer(self.repo_root)
        with self.assertRaises(ValueError):
            synth.synthesize_v5_chapter_bundle({"learning_nodes": [{"node_id": "N1"}]})

    def test_b2_08_execute_chunk_b2_cycle_writes_defaults_and_returns_verified_manifest(self) -> None:
        res = execute_chunk_b2_v5_synthesis_and_lle_cycle(self.repo_root)
        self.assertEqual(res["status"], "B2_SIX_AGENT_V5_AND_8LAYER_LLE_VERIFIED")
        self.assertEqual(res["wm_dictionary_count"], 296)
        self.assertEqual(res["conn_dictionary_count"], 46)
        self.assertEqual(len(res["synthesis_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
