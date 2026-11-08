"""
Unit tests for AASHA AIOS V3 Chunk B4:
Offline base64 bundler (<20 MiB ceiling) and Dual-Output SQLite exporter (`teas_content.db.gz`).
"""

import tempfile
import unittest
from pathlib import Path

from aasha.offline_synthesizer.phoneme_bundle_optimizer import (
    BundleCeilingExceededError,
    DualOutputSQLiteExporter,
    OFFLINE_BUNDLE_CEILING_BYTES,
    OfflineBase64AssetBundler,
    execute_chunk_b4_bundler_and_sqlite_cycle,
)
from aasha.orchestrator.method_b_orchestrator import execute_chunk_b2_v5_synthesis_and_lle_cycle


class TestChunkB4OfflineBundlerAndSQLiteExporter(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_b4_01_base64_bundler_inlines_svg_and_enforces_zero_external_urls(self) -> None:
        html = (
            '<html><head><link href="https://cdn.example.com/a.css"></head>'
            '<body><img src="assets/frac.svg"></body></html>'
        )
        res = OfflineBase64AssetBundler.bundle_offline_html(
            raw_html=html,
            asset_map={"assets/frac.svg": b'<svg><!-- comment --><rect width="10" height="10"/></svg>'},
        )
        self.assertTrue(res["under_20mib_ceiling"])
        self.assertEqual(res["inlined_assets_count"], 1)
        self.assertEqual(res["external_urls_remaining"], 0)
        self.assertIn("data:image/svg+xml;base64,", res["bundled_html"])

    def test_b4_02_base64_bundler_raises_when_exceeding_ceiling(self) -> None:
        with self.assertRaises(BundleCeilingExceededError):
            OfflineBase64AssetBundler.bundle_offline_html(
                raw_html="<html><body>" + ("A" * 2048) + "</body></html>",
                ceiling_bytes=512,
            )

    def test_b4_03_20mib_ceiling_constant_is_exact(self) -> None:
        self.assertEqual(OFFLINE_BUNDLE_CEILING_BYTES, 20_971_520)

    def test_b4_04_dual_output_sqlite_exporter_creates_valid_gzipped_sqlite_db(self) -> None:
        b2_manifest = execute_chunk_b2_v5_synthesis_and_lle_cycle(self.repo_root)
        with tempfile.TemporaryDirectory() as tmp:
            gz_path = Path(tmp) / "teas_content.db.gz"
            exp = DualOutputSQLiteExporter.export_teas_sqlite_gz([b2_manifest], gz_path)
            self.assertEqual(exp["sqlite_integrity"], "ok")
            self.assertEqual(exp["chapters_exported"], 1)
            self.assertEqual(exp["tln_nodes_exported"], 4)
            self.assertEqual(exp["teas_assessments_exported"], 4)

            ver = DualOutputSQLiteExporter.verify_teas_sqlite_gz(gz_path)
            self.assertTrue(ver["valid"])
            self.assertEqual(ver["sqlite_integrity"], "ok")
            self.assertEqual(ver["tln_nodes_count"], 4)

    def test_b4_05_verify_teas_sqlite_gz_rejects_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            DualOutputSQLiteExporter.verify_teas_sqlite_gz("/nonexistent/teas_content.db.gz")

    def test_b4_06_execute_chunk_b4_cycle_end_to_end(self) -> None:
        res = execute_chunk_b4_bundler_and_sqlite_cycle(self.repo_root)
        self.assertEqual(res["status"], "B4_OFFLINE_BUNDLER_AND_SQLITE_EXPORTER_VERIFIED")
        self.assertTrue(res["under_20mib_ceiling"])
        self.assertEqual(res["external_urls_remaining"], 0)
        self.assertTrue(res["sqlite_verification"]["valid"])
        self.assertEqual(res["sqlite_verification"]["sqlite_integrity"], "ok")


if __name__ == "__main__":
    unittest.main()
