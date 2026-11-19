import json
import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.compounding_wm_engine import (
    autosave_and_disburse_chapter_wm,
    resolve_learning_simulator_engine,
)


class TestG67CompoundingWmEngine(unittest.TestCase):
    def test_learning_simulator_replaces_svg_only_default(self):
        sci = resolve_learning_simulator_engine("science", "NCERT-G08-SCI-CH08")
        self.assertTrue(sci["svg_only_default_disabled"])
        self.assertEqual(sci["default_simulator_engine"], "PixiJS_WebGL2_MatterJS_60fps_Interactive_Sim")

        math = resolve_learning_simulator_engine("math", "NCERT-G06-MATH-CH07")
        self.assertEqual(math["default_simulator_engine"], "PixiJS_WebGL2_JSXGraph_60fps_Interactive_Sim")

    def test_autosave_expands_wm_and_disburses_core_plus_domain_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            db_path = tmp_dir / "test_operational.db"
            defaults_path = tmp_dir / "defaults_expanded_v2.json"
            defaults_path.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "WM": {"force": "बल", "energy": "ऊर्जा"},
                        "CONN": {"and": "और"},
                    }
                ),
                encoding="utf-8",
            )

            res1 = autosave_and_disburse_chapter_wm(
                db_path=db_path,
                defaults_v2_path=defaults_path,
                chapter_id="NCERT-G08-SCI-CH08",
                domain="science",
                module_text="Force and pascal pressure on piston area",
                new_terms={"pascal": "पास्कल", "piston": "पिस्टन"},
            )
            self.assertEqual(res1["added_new_words_count"], 2)
            self.assertEqual(res1["total_cumulative_wm_count"], 4)
            self.assertIn("force", res1["disbursed_wm"])
            self.assertIn("pascal", res1["disbursed_wm"])

            # Chapter 2 reuses Chapter 1 words and expands further
            res2 = autosave_and_disburse_chapter_wm(
                db_path=db_path,
                defaults_v2_path=defaults_path,
                chapter_id="NCERT-G08-SCI-CH01",
                domain="science",
                module_text="Drip irrigation and pascal pressure in pipes",
                new_terms={"irrigation": "सिंचाई"},
            )
            self.assertEqual(res2["added_new_words_count"], 1)
            self.assertEqual(res2["total_cumulative_wm_count"], 5)
            self.assertIn("pascal", res2["disbursed_wm"])
            self.assertIn("irrigation", res2["disbursed_wm"])


if __name__ == "__main__":
    unittest.main()
