import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g86_offline_voice_phoneme_pack import (  # noqa: E402
    build_bilingual_voice_readaloud_pack,
)


class TestG86OfflineVoicePhonemePack(unittest.TestCase):
    def test_compiles_bilingual_webvtt_phoneme_pack_offline(self):
        res = build_bilingual_voice_readaloud_pack(
            chapter_id="NCERT-G08-SCI-CH08",
            bilingual_lines=[
                "Force is a push or pull. बल किसी वस्तु पर धक्का या खिंचाव है।",
                "Pressure equals force divided by area. दाब बराबर बल बटा क्षेत्रफल।",
            ],
            language="hi-IN",
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["offline_only"])
        self.assertTrue(res["zero_external_urls"])
        self.assertTrue(res["within_20mib_cap"])
        self.assertGreater(res["cue_count"], 0)
        self.assertIn("WEBVTT", res["webvtt"])
        self.assertGreater(len(res["voice_pack_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
