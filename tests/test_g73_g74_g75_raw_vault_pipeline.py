import tempfile
import unittest
from pathlib import Path

from src.aasha.orchestrator.raw_vault_bundler import (
    bundle_js_to_iife_tag,
    encode_file_to_data_uri,
    scan_raw_source_vault,
)


class TestG73G74G75RawVaultPipeline(unittest.TestCase):
    def test_raw_vault_structure_and_iife_multimedia_bundling(self):
        repo_root = Path(__file__).resolve().parents[1]
        vault = scan_raw_source_vault(repo_root)
        self.assertTrue(vault["vault_exists"])
        self.assertTrue(vault["supports_3d_sprites_video_audio"])
        self.assertTrue((repo_root / "scripts" / "harvest_upstream_raw_assets.sh").is_file())

        tag = bundle_js_to_iife_tag("console.log('aasha 60fps');")
        self.assertTrue(tag.startswith('<script src="data:text/javascript;base64,'))

        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "piston.glb"
            glb.write_bytes(b"glTF\x02\x00\x00\x00")
            encoded = encode_file_to_data_uri(glb)
            self.assertEqual(encoded["mime"], "model/gltf-binary")
            self.assertTrue(encoded["data_uri"].startswith("data:model/gltf-binary;base64,"))


if __name__ == "__main__":
    unittest.main()
