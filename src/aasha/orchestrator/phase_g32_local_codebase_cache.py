"""
Phase G32: Local Open-Source & AASHA Reusable Codebase Cache (`vendor_cache/` + `aasha_operational.db`)
Synced to Google Drive (`AASHA_OpenSource_Codebase_Cache`: 1B2Au3mwU-ZU1A1UTJtZfCVZrKdnV-2xI).

Allows any future Hydrogen/Argon agent to query `aasha_operational.db` (`codebase_sources` table)
or `CODEBASE_CACHE_INDEX.json` by tag/capability/license and immediately reuse, adapt, or bundle
verified local source files without re-searching or re-downloading.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DRIVE_CACHE_FOLDER_ID = "1B2Au3mwU-ZU1A1UTJtZfCVZrKdnV-2xI"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalCodebaseCacheManager:
    """Compounding local codebase cache backed by `aasha_operational.db` and `vendor_cache/`."""

    def __init__(self, repo_root: Path | str = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.db_path = self.repo_root / "aasha_operational.db"
        self.cache_dir = self.repo_root / "vendor_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS codebase_sources (
                    asset_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    license TEXT NOT NULL,
                    origin_url TEXT NOT NULL,
                    local_rel_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    tags TEXT NOT NULL,
                    drive_folder_id TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def register_source_file(
        self,
        asset_id: str,
        name: str,
        category: str,
        license_name: str,
        origin_url: str,
        source_path: Path,
        tags: List[str],
        copy_to_vendor_cache: bool = False,
    ) -> Dict[str, Any]:
        raw_bytes = source_path.read_bytes()
        sha = _sha256_bytes(raw_bytes)
        if copy_to_vendor_cache:
            dest = self.cache_dir / source_path.name
            dest.write_bytes(raw_bytes)
            rel_path = str(dest.relative_to(self.repo_root))
        else:
            rel_path = str(source_path.relative_to(self.repo_root))

        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO codebase_sources (
                    asset_id, name, category, license, origin_url,
                    local_rel_path, sha256, byte_size, tags, drive_folder_id, cached_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    local_rel_path=excluded.local_rel_path,
                    sha256=excluded.sha256,
                    byte_size=excluded.byte_size,
                    tags=excluded.tags,
                    cached_at=excluded.cached_at
                """,
                (
                    asset_id,
                    name,
                    category,
                    license_name,
                    origin_url,
                    rel_path,
                    sha,
                    len(raw_bytes),
                    ",".join(tags),
                    DRIVE_CACHE_FOLDER_ID,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "asset_id": asset_id,
            "name": name,
            "category": category,
            "license": license_name,
            "local_rel_path": rel_path,
            "sha256": sha,
            "byte_size": len(raw_bytes),
            "tags": tags,
        }

    def query_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.execute(
                "SELECT asset_id, name, category, license, local_rel_path, sha256, byte_size, tags FROM codebase_sources WHERE tags LIKE ?",
                (f"%{tag}%",),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()

    def build_and_export_local_cache(self) -> Dict[str, Any]:
        entries: List[Dict[str, Any]] = []

        # 1. Index all 21 Phase-3 interactive visual mechanics (HTML + JS)
        p3_res_dir = self.repo_root / "AASHA_Visual_Mass_Harvest_Phase3" / "resources"
        for html_file in sorted(p3_res_dir.glob("AVR-P3*.html")):
            avr_id = html_file.name.split("-")[0] + "-" + html_file.name.split("-")[1]
            entries.append(
                self.register_source_file(
                    asset_id=f"{avr_id}-HTML",
                    name=html_file.name,
                    category="interactive_visual_mechanic",
                    license_name="AASHA-Apache-2.0-Cleanroom",
                    origin_url="https://github.com/Anant1asha/NGO-AI-LLM",
                    source_path=html_file,
                    tags=["avr", "offline", "html5", "tactile", avr_id.lower()],
                    copy_to_vendor_cache=True,
                )
            )

        p3_test_dir = self.repo_root / "AASHA_Visual_Mass_Harvest_Phase3" / "tests"
        for js_file in sorted(p3_test_dir.glob("AVR-P3*.js")):
            avr_id = js_file.stem
            entries.append(
                self.register_source_file(
                    asset_id=f"{avr_id}-JS",
                    name=js_file.name,
                    category="interactive_visual_js",
                    license_name="AASHA-Apache-2.0-Cleanroom",
                    origin_url="https://github.com/Anant1asha/NGO-AI-LLM",
                    source_path=js_file,
                    tags=["avr", "js", "base64_ready", avr_id.lower()],
                    copy_to_vendor_cache=True,
                )
            )

        # 2. Index core AASHA templates, synthesizers, dictionaries, PWA & server modules
        core_assets = [
            (
                "CORE-V5-TEMPLATE",
                "v5-engine-template.html",
                "template_engine",
                "AASHA-Apache-2.0",
                self.repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "template" / "v5-engine-template.html",
                ["v5", "template", "html5", "offline"],
            ),
            (
                "CORE-LLE-V2",
                "defaults_expanded_v2.json",
                "lle_dictionary",
                "AASHA-Apache-2.0",
                self.repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "config" / "defaults_expanded_v2.json",
                ["lle", "hindi", "wm", "conn", "dictionary"],
            ),
            (
                "CORE-CODE-SYNTH",
                "code_synthesizer.py",
                "synthesis_agent",
                "AASHA-Apache-2.0",
                self.repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "src" / "aasha" / "synthesis" / "code_synthesizer.py",
                ["synthesizer", "3level", "assessment"],
            ),
            (
                "CORE-ASSET-BUNDLER",
                "bundler.py",
                "offline_bundler",
                "AASHA-Apache-2.0",
                self.repo_root / "Aasha-AI" / "aasha-pipeline-with-master-json" / "src" / "aasha" / "plugins" / "bundler.py",
                ["bundler", "base64", "offline"],
            ),
            (
                "CORE-PWA-SYNC",
                "sync.js",
                "student_pwa",
                "AASHA-Apache-2.0",
                self.repo_root / "Aasha-AI" / "aasha-student-pwa" / "src" / "sync.js",
                ["pwa", "teas", "sync", "misconception"],
            ),
            (
                "CORE-CENTRE-SERVER",
                "server.js",
                "centre_server",
                "AASHA-Apache-2.0",
                self.repo_root / "Aasha-AI" / "server" / "server.js",
                ["fastify", "sqlite", "centre_server", "store"],
            ),
        ]
        for aid, name, cat, lic, path, tags in core_assets:
            if path.is_file():
                entries.append(
                    self.register_source_file(
                        asset_id=aid,
                        name=name,
                        category=cat,
                        license_name=lic,
                        origin_url="https://github.com/Anant1asha/Aasha-AI",
                        source_path=path,
                        tags=tags,
                        copy_to_vendor_cache=True,
                    )
                )

        # 3. Create compressed tar.gz archive of vendor_cache/ for single-file Drive sync
        archive_path = self.repo_root / "aasha_codebase_cache_pack.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(self.cache_dir, arcname="vendor_cache")

        index_payload = {
            "schema_version": "1.0.0",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "drive_cache_folder_id": DRIVE_CACHE_FOLDER_ID,
            "total_cached_assets": len(entries),
            "archive_file": archive_path.name,
            "archive_bytes": archive_path.stat().st_size,
            "archive_sha256": _sha256_bytes(archive_path.read_bytes()),
            "assets": entries,
        }
        (self.repo_root / "CODEBASE_CACHE_INDEX.json").write_text(
            json.dumps(index_payload, indent=2) + "\n", encoding="utf-8"
        )
        return index_payload


if __name__ == "__main__":
    mgr = LocalCodebaseCacheManager(".")
    res = mgr.build_and_export_local_cache()
    print(json.dumps({
        "total_cached_assets": res["total_cached_assets"],
        "archive_file": res["archive_file"],
        "archive_bytes": res["archive_bytes"],
        "drive_cache_folder_id": res["drive_cache_folder_id"],
    }, indent=2))
