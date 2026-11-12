"""Unit tests for Phase G32: Local Open-Source & Reusable Codebase Cache."""

import unittest
from pathlib import Path

from src.aasha.orchestrator.phase_g32_local_codebase_cache import (
    LocalCodebaseCacheManager,
)


class TestPhaseG32LocalCodebaseCache(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_g32_01_local_codebase_cache_indexes_and_archives_assets(self) -> None:
        mgr = LocalCodebaseCacheManager(self.repo_root)
        res = mgr.build_and_export_local_cache()

        self.assertGreaterEqual(res["total_cached_assets"], 48)  # 21 AVR HTML + 21 AVR JS + 6 core assets
        self.assertTrue((self.repo_root / "aasha_codebase_cache_pack.tar.gz").is_file())
        self.assertTrue((self.repo_root / "CODEBASE_CACHE_INDEX.json").is_file())

        avr_hits = mgr.query_by_tag("avr")
        self.assertGreaterEqual(len(avr_hits), 42)
        lle_hits = mgr.query_by_tag("dictionary")
        self.assertGreaterEqual(len(lle_hits), 1)


if __name__ == "__main__":
    unittest.main()
