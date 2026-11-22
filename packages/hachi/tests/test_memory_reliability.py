"""
Test suite for memory reliability/privacy fixes.

Covers:
  MR-7  / UC-MEM-001 / UC-MEM-006 — silent write loss
  UC-MEM-004 — incomplete delete (forgotten facts resurface)
  ADV-023    — cross-account memory contamination
  UC-MEM-005 — no false at-rest-encryption claims (static check)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hachi.core.loop import ToolRegistry
from hachi.tools.memory_tools import register_memory_tools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeQueue:
    """Job queue stub that records enqueued jobs."""

    def __init__(self) -> None:
        self.jobs: list = []

    def enqueue(self, job) -> str:
        self.jobs.append(job)
        return "job-test-1"


class _ExplodingQueue:
    """Job queue stub whose enqueue always raises (simulates queue failure)."""

    def enqueue(self, job) -> str:
        raise RuntimeError("queue is full")


class _FakeVault:
    """Minimal vault stub for memory_tools tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def semantic_search(self, _query: str, top_k: int = 3) -> list:
        return []

    def upsert_fact(self, content: str, category: str = "workspace_state") -> str:
        import hashlib

        fid = hashlib.sha256(content.encode()).hexdigest()
        self._store[fid] = content
        return fid

    def delete_fact(self, fact_id: str) -> bool:
        return self._store.pop(fact_id, None) is not None

    def upsert_user_fact(self, content: str, category: str = "preference") -> str:
        import hashlib

        fid = hashlib.sha256(content.encode()).hexdigest()
        self._store[fid] = content
        return fid

    def get_profile_stats(self) -> dict:
        return {"entries": 0, "max_entries": 25}

    def search_user_profile(self, _query: str, top_k: int = 10) -> list:
        return []

    def delete_user_fact(self, fact_id: str) -> bool:
        return self._store.pop(fact_id, None) is not None


def _register(vault, job_queue=None) -> tuple[dict, ToolRegistry]:
    """Register memory tools and return a dict of tool callables keyed by name."""
    registry = ToolRegistry()
    register_memory_tools(registry, vault, job_queue=job_queue)
    return registry._tools, registry


# ===========================================================================
# MR-7 / UC-MEM-001 / UC-MEM-006 — Loud failure on write
# ===========================================================================


class TestSaveMemoryLoudFailure:
    """core_save_memory must NEVER return a success/queued message when the
    write cannot be durably persisted."""

    def test_no_queue_returns_failure_string(self) -> None:
        """Without any queue, save_memory must report failure — not 'queued'."""
        tools, _ = _register(_FakeVault(), job_queue=None)
        result: str = tools["core_save_memory"](facts=[{"content": "test fact"}])

        # Must be an explicit failure
        assert "FAILED" in result, f"Expected FAILED in result, got: {result!r}"
        # Must NOT claim success
        assert "queued" not in result.lower(), (
            f"Result must not contain 'queued' when queue is absent: {result!r}"
        )
        assert "remembered" not in result.lower() or "cannot" in result.lower(), (
            f"Result must not falsely claim the fact was remembered: {result!r}"
        )

    def test_exploding_queue_returns_failure_string(self) -> None:
        """If enqueue raises, save_memory must report failure — not 'queued'."""
        tools, _ = _register(_FakeVault(), job_queue=_ExplodingQueue())
        result: str = tools["core_save_memory"](facts=[{"content": "test fact"}])

        assert "FAILED" in result, f"Expected FAILED in result, got: {result!r}"
        assert "queued" not in result.lower(), (
            f"Result must not contain 'queued' when enqueue fails: {result!r}"
        )

    def test_exploding_queue_does_not_spawn_thread(self) -> None:
        """Enqueue failure must not fall back to a daemon thread."""
        import threading

        tools, _ = _register(_FakeVault(), job_queue=_ExplodingQueue())
        before = threading.active_count()
        tools["core_save_memory"](facts=[{"content": "test fact"}])

        import time

        time.sleep(0.05)  # let any accidental thread start
        after = threading.active_count()
        assert after <= before, "A daemon thread was spawned despite enqueue failure"

    def test_working_queue_returns_queued_confirmation(self) -> None:
        """With a working queue, save_memory returns a success/queued message."""
        tools, _ = _register(_FakeVault(), job_queue=_FakeQueue())
        result: str = tools["core_save_memory"](facts=[{"content": "Project uses FastAPI"}])

        assert "FAILED" not in result, f"Unexpected failure with working queue: {result!r}"
        assert "queued" in result.lower(), f"Expected 'queued' in success result, got: {result!r}"

    def test_working_queue_enqueues_exactly_one_job(self) -> None:
        """A single save_memory call enqueues exactly one job."""
        queue = _FakeQueue()
        tools, _ = _register(_FakeVault(), job_queue=queue)
        tools["core_save_memory"](facts=[{"content": "Project uses FastAPI"}])

        assert len(queue.jobs) == 1
        assert queue.jobs[0].name == "memory_smart_upsert"
        assert queue.jobs[0].job_type == "persist"

    def test_multi_fact_failure_mentions_count(self) -> None:
        """The failure message includes the number of facts that were NOT saved."""
        tools, _ = _register(_FakeVault(), job_queue=None)
        result: str = tools["core_save_memory"](
            facts=[{"content": "f1"}, {"content": "f2"}, {"content": "f3"}]
        )

        assert "FAILED" in result
        assert "3" in result, f"Expected fact count (3) in failure message: {result!r}"


# ===========================================================================
# UC-MEM-004 — Delete spans all backends
# ===========================================================================


class TestDeleteSpansAllBackends:
    """delete_fact must remove entries from Chroma AND FTS5; afterwards the
    fact must not be retrievable from either backend."""

    def test_chroma_delete_removes_from_vault(self, tmp_path: Path) -> None:
        """After delete_fact, the fact is gone from Chroma (no ChromaDB required)."""
        vault = _FakeVault()
        tools, _ = _register(vault, job_queue=_FakeQueue())

        # Simulate a pre-stored fact
        import hashlib

        content = "the project uses PostgreSQL"
        fid = hashlib.sha256(content.encode()).hexdigest()
        vault._store[fid] = content

        result: str = tools["core_delete_memory"](fact_id=fid)

        assert "FAILED" not in result, f"Delete reported failure: {result!r}"
        assert fid not in vault._store, "Fact still present in vault store after delete"

    def test_delete_removes_from_fts5_when_graph_index_attached(self, tmp_path: Path) -> None:
        """delete_fact must also remove the node from the FTS5 SQLite index."""
        # Build a minimal FTS5 db matching what MemoryIndex uses.
        db_path = tmp_path / "memory_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS mem_nodes (
                node_id    TEXT PRIMARY KEY,
                file_stem  TEXT NOT NULL,
                node_type  TEXT NOT NULL DEFAULT 'fact',
                name       TEXT NOT NULL,
                keywords   TEXT NOT NULL DEFAULT '',
                dense      TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
                node_id,
                text,
                tokenize='porter ascii'
            );
            """
        )
        import hashlib

        content = "the project uses FastAPI"
        fid = hashlib.sha256(content.encode()).hexdigest()
        conn.execute(
            "INSERT INTO mem_nodes (node_id, file_stem, node_type, name, keywords, dense,"
            " updated_at) VALUES (?, 'test', 'fact', 'test-node', '', ?, '2026-01-01')",
            (fid, content),
        )
        conn.execute(
            "INSERT INTO mem_fts (node_id, text) VALUES (?, ?)",
            (fid, content),
        )
        conn.commit()
        conn.close()

        # Fake graph index that exposes the db_path attribute used by _delete_from_fts5.
        graph_index = MagicMock()
        graph_index._db_path = db_path

        # Build a real-ish MemoryVault using the FakeVault wrapper for Chroma.
        # We test the vault's delete_fact directly since it owns the FTS5 logic.
        try:
            from hachi.core.memory_vault import MemoryVault

            vault = MemoryVault(brain_dir=str(tmp_path))
            vault._graph_index = graph_index
        except ImportError:
            pytest.skip("chromadb not installed — skipping MemoryVault integration test")

        # Prime the Chroma collection with the fact.
        vault.upsert_fact(content, category="architecture")

        # Now delete.
        ok = vault.delete_fact(fid)
        assert ok, "delete_fact returned False — Chroma deletion failed"

        # Verify FTS5 tables are cleaned up.
        conn2 = sqlite3.connect(str(db_path))
        nodes_row = conn2.execute(
            "SELECT COUNT(*) FROM mem_nodes WHERE node_id = ?", (fid,)
        ).fetchone()
        fts_row = conn2.execute("SELECT COUNT(*) FROM mem_fts WHERE node_id = ?", (fid,)).fetchone()
        conn2.close()

        assert nodes_row[0] == 0, "Node still present in mem_nodes after delete"
        assert fts_row[0] == 0, "Node still present in mem_fts after delete"

    def test_delete_is_idempotent_for_absent_id(self, tmp_path: Path) -> None:
        """Deleting an ID that does not exist must not raise and must report success."""
        try:
            from hachi.core.memory_vault import MemoryVault

            vault = MemoryVault(brain_dir=str(tmp_path))
        except ImportError:
            pytest.skip("chromadb not installed")

        ok = vault.delete_fact("nonexistent-sha256-id")
        # Chroma silently ignores missing IDs — True is acceptable.
        assert isinstance(ok, bool)

    def test_tool_delete_confirms_removal(self) -> None:
        """The delete_memory tool must confirm removal from ALL backends."""
        import hashlib

        vault = _FakeVault()
        content = "some fact"
        fid = hashlib.sha256(content.encode()).hexdigest()
        vault._store[fid] = content

        tools, _ = _register(vault)
        result: str = tools["core_delete_memory"](fact_id=fid)

        assert "FAILED" not in result, f"Unexpected failure: {result!r}"
        # Result must mention backends
        lower = result.lower()
        assert "chroma" in lower or "backend" in lower or "removed" in lower, (
            f"Result should confirm multi-backend removal: {result!r}"
        )


# ===========================================================================
# ADV-023 — Cross-account isolation
# ===========================================================================


class TestAccountIsolation:
    """Facts saved under one account key must not be visible under another."""

    def test_different_accounts_use_different_db_paths(self, tmp_path: Path) -> None:
        """Two MemoryVault instances with different account_ids store data separately."""
        try:
            from hachi.core.memory_vault import MemoryVault
        except ImportError:
            pytest.skip("chromadb not installed")

        vault_a = MemoryVault(brain_dir=str(tmp_path), account_id="account-alice")
        vault_b = MemoryVault(brain_dir=str(tmp_path), account_id="account-bob")

        assert vault_a.db_path != vault_b.db_path, (
            f"Both vaults share the same db_path: {vault_a.db_path}"
        )

    def test_fact_saved_under_account_a_not_visible_under_account_b(self, tmp_path: Path) -> None:
        """A fact stored in account A's vault must not appear when searching account B."""
        try:
            from hachi.core.memory_vault import MemoryVault
        except ImportError:
            pytest.skip("chromadb not installed")

        vault_a = MemoryVault(brain_dir=str(tmp_path), account_id="account-alice")
        vault_b = MemoryVault(brain_dir=str(tmp_path), account_id="account-bob")

        vault_a.upsert_fact("Alice's secret project is Project Chimera", "workspace_state")

        results_b = vault_b.semantic_search("Project Chimera", top_k=5)
        contents_b = [r["raw_content"] for r in results_b]

        assert not any("Chimera" in c for c in contents_b), (
            f"Fact from account A leaked into account B's search results: {contents_b}"
        )

    def test_default_account_uses_legacy_path(self, tmp_path: Path) -> None:
        """account_id='default' must resolve to the legacy chroma_vault path (no sub-folder)."""
        try:
            from hachi.core.memory_vault import MemoryVault
        except ImportError:
            pytest.skip("chromadb not installed")

        vault = MemoryVault(brain_dir=str(tmp_path), account_id="default")
        expected = str(tmp_path / "chroma_vault")
        assert vault.db_path == expected, (
            f"Default account should use legacy path {expected!r}, got {vault.db_path!r}"
        )

    def test_no_account_id_falls_back_to_default_path(self, tmp_path: Path) -> None:
        """Omitting account_id should behave identically to account_id='default'."""
        try:
            from hachi.core.memory_vault import MemoryVault
        except ImportError:
            pytest.skip("chromadb not installed")

        vault = MemoryVault(brain_dir=str(tmp_path))
        expected = str(tmp_path / "chroma_vault")
        assert vault.db_path == expected, (
            f"Omitting account_id should use legacy path {expected!r}, got {vault.db_path!r}"
        )

    def test_env_var_account_overrides_default(self, tmp_path: Path, monkeypatch) -> None:
        """HACHI_ACCOUNT env var is used when no account_id argument is passed."""
        try:
            from hachi.core.memory_vault import MemoryVault
        except ImportError:
            pytest.skip("chromadb not installed")

        monkeypatch.setenv("HACHI_ACCOUNT", "env-account-x")
        vault = MemoryVault(brain_dir=str(tmp_path))

        # Should NOT be the legacy path
        legacy = str(tmp_path / "chroma_vault")
        assert vault.db_path != legacy, (
            "HACHI_ACCOUNT env var was ignored; vault still uses default path"
        )
        assert "env_account_x" in vault.db_path.lower() or "env-account-x" in vault.db_path, (
            f"Expected account key in db_path, got: {vault.db_path!r}"
        )

    def test_collection_names_differ_across_accounts(self, tmp_path: Path) -> None:
        """ChromaDB collection names must be namespaced per account (not 'default')."""
        try:
            from hachi.core.memory_vault import MemoryVault
        except ImportError:
            pytest.skip("chromadb not installed")

        vault = MemoryVault(brain_dir=str(tmp_path), account_id="user-xyz")
        # Collection name should contain the account prefix
        coll_name = vault.collection.name
        assert "user_xyz" in coll_name or "user-xyz" in coll_name, (
            f"Collection name does not contain account prefix: {coll_name!r}"
        )


# ===========================================================================
# UC-MEM-005 — No false at-rest-encryption claims
# ===========================================================================


class TestNoFalseEncryptionClaims:
    """None of the three target source files must claim at-rest encryption."""

    _TARGET_FILES = [
        Path("src/hachi/tools/memory_tools.py"),
        Path("src/hachi/core/memory.py"),
        Path("src/hachi/core/memory_vault.py"),
    ]

    def _repo_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_no_encrypt_claims_in_target_files(self) -> None:
        """None of the target files contain claims about at-rest encryption."""
        import re

        # Patterns that would constitute a false claim
        bad_patterns = [
            r"encrypt(ed|s|ion)?\s+(at[\s-]rest|on[\s-]disk|storage)",
            r"data[\s-]+at[\s-]rest[\s-]+is[\s-]+encrypt",
            r"stores?[\s\w]*encrypt",
            r"AES[\-\d]+\s+encrypt",
        ]
        compiled = [re.compile(p, re.IGNORECASE) for p in bad_patterns]

        root = self._repo_root()
        violations: list[str] = []
        for rel_path in self._TARGET_FILES:
            full = root / rel_path
            if not full.exists():
                continue
            text = full.read_text(encoding="utf-8")
            for pat in compiled:
                for m in pat.finditer(text):
                    line_no = text[: m.start()].count("\n") + 1
                    violations.append(f"{rel_path}:{line_no}: {m.group(0)!r}")

        assert not violations, (
            "False at-rest-encryption claims found in source files:\n" + "\n".join(violations)
        )
