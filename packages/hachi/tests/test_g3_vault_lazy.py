"""G3-T2 / PERF-05 / HIGH-021 — lazy ChromaDB import and per-collection init.

Contract:
  1. Importing the module does NOT import chromadb at the top level.
  2. Constructing MemoryVault does NOT call get_or_create_collection.
  3. Constructing MemoryVault does NOT create a ChromaDB PersistentClient.
  4. Accessing a collection for the first time DOES create it (lazy init).
  5. A second access returns the memoised instance (no second DB call).
  6. Accessing one collection does NOT create the others.
  7. Write-then-read round-trip works correctly end-to-end.
  8. _closed / _assert_open semantics are fully preserved after the refactor.
  9. close() before any collection access is a cheap no-op (no client created).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_chromadb() -> tuple[MagicMock, MagicMock]:
    """Return (mock_chromadb_module, mock_client)."""
    mock_coll = MagicMock()
    mock_coll.count.return_value = 0

    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_coll

    mock_chroma = MagicMock()
    mock_chroma.PersistentClient.return_value = mock_client

    mock_settings_mod = MagicMock()
    mock_settings_mod.Settings.return_value = MagicMock()

    return mock_chroma, mock_client


# ---------------------------------------------------------------------------
# 1. Module import does NOT pull in chromadb
# ---------------------------------------------------------------------------

class TestModuleImportNoChromain:
    """chromadb must NOT appear in sys.modules merely from importing memory_vault."""

    def test_chromadb_not_in_sys_modules_after_import(self) -> None:
        """Importing hachi.core.memory_vault should not trigger 'import chromadb'."""
        # Remove memory_vault from sys.modules to get a fresh import, then check
        # whether 'chromadb' ends up in sys.modules.
        # We only validate the module-level top-of-file imports, not deferred ones.
        # Strategy: ensure chromadb is not already cached, then re-import and check.
        was_present_before = "chromadb" in sys.modules

        # If chromadb wasn't present before importing memory_vault, it must still
        # not be present after just importing the module (before any MemoryVault use).
        if was_present_before:
            # chromadb already loaded (e.g. by another test) — skip the presence check
            # but still verify the module can be imported without error.
            import hachi.core.memory_vault  # noqa: F401
            return

        # Temporarily remove chromadb from sys.modules to simulate a fresh environment.
        saved = {
            k: v
            for k, v in sys.modules.items()
            if k == "chromadb" or k.startswith("chromadb.")
        }
        for k in saved:
            del sys.modules[k]

        try:
            # Remove memory_vault from cache to force re-evaluation of top-level imports.
            mv_saved = {k: v for k, v in sys.modules.items() if "memory_vault" in k}
            for k in mv_saved:
                del sys.modules[k]

            import hachi.core.memory_vault  # noqa: F401

            # chromadb must NOT have been imported at module level.
            assert "chromadb" not in sys.modules, (
                "PERF-05 regression: 'import chromadb' is still at module top-level; "
                "it should be deferred until first collection access."
            )
        finally:
            # Restore whatever was there before.
            sys.modules.update(saved)
            sys.modules.update(mv_saved)


# ---------------------------------------------------------------------------
# 2 & 3. __init__ does NOT create client or collections
# ---------------------------------------------------------------------------

class TestInitIsLazy:
    """MemoryVault.__init__ must not touch ChromaDB at all."""

    def test_init_does_not_call_get_or_create_collection(self, tmp_path) -> None:
        """get_or_create_collection must NOT be called during __init__."""
        mock_chroma, mock_client = _make_mock_chromadb()

        with (
            patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}),
        ):
            from hachi.core import memory_vault as _mv
            vault = _mv.MemoryVault(brain_dir=str(tmp_path))

        mock_client.get_or_create_collection.assert_not_called()
        vault.close()

    def test_init_does_not_construct_persistent_client(self, tmp_path) -> None:
        """chromadb.PersistentClient must NOT be called during __init__."""
        mock_chroma, mock_client = _make_mock_chromadb()

        with patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}):
            from hachi.core import memory_vault as _mv
            _mv.MemoryVault(brain_dir=str(tmp_path)).close()

        mock_chroma.PersistentClient.assert_not_called()

    def test_chroma_client_is_none_after_init(self, tmp_path) -> None:
        """_chroma_client attribute must be None right after __init__."""
        mock_chroma, _ = _make_mock_chromadb()
        with patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}):
            from hachi.core import memory_vault as _mv
            vault = _mv.MemoryVault(brain_dir=str(tmp_path))

        assert vault._chroma_client is None
        vault.close()

    def test_all_collection_slots_are_none_after_init(self, tmp_path) -> None:
        """Every slot in _collections must be None right after __init__."""
        mock_chroma, _ = _make_mock_chromadb()
        with patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}):
            from hachi.core import memory_vault as _mv
            vault = _mv.MemoryVault(brain_dir=str(tmp_path))

        assert all(v is None for v in vault._collections.values()), (
            "PERF-05 regression: some collections were pre-created in __init__"
        )
        vault.close()


# ---------------------------------------------------------------------------
# 4. First access creates the collection
# ---------------------------------------------------------------------------

class TestFirstAccessCreatesCollection:
    """_get_collection(attr) must call get_or_create_collection on first access."""

    def test_first_access_triggers_get_or_create(self, tmp_path) -> None:
        """Accessing 'collection' for the first time calls get_or_create_collection."""
        mock_chroma, mock_client = _make_mock_chromadb()
        with patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}):
            from hachi.core import memory_vault as _mv
            vault = _mv.MemoryVault(brain_dir=str(tmp_path))
            # Trigger lazy init of 'collection' via _get_collection under the lock.
            with vault._vault_lock:
                vault._get_collection("collection")

        mock_client.get_or_create_collection.assert_called_once()
        vault.close()


# ---------------------------------------------------------------------------
# 5. Second access returns memoised instance
# ---------------------------------------------------------------------------

class TestMemoisation:
    """A second call to _get_collection must return the cached instance."""

    def test_second_access_no_extra_db_call(self, tmp_path) -> None:
        mock_chroma, mock_client = _make_mock_chromadb()
        with patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}):
            from hachi.core import memory_vault as _mv
            vault = _mv.MemoryVault(brain_dir=str(tmp_path))
            with vault._vault_lock:
                coll1 = vault._get_collection("collection")
                coll2 = vault._get_collection("collection")

        assert coll1 is coll2, "Second _get_collection call should return the cached object"
        assert mock_client.get_or_create_collection.call_count == 1, (
            "get_or_create_collection must be called exactly once per collection"
        )
        vault.close()


# ---------------------------------------------------------------------------
# 6. Accessing one collection does NOT create others
# ---------------------------------------------------------------------------

class TestIsolatedLazyInit:
    """Only the accessed collection should be initialised — others stay None."""

    def test_accessing_core_memory_does_not_create_user_profile(self, tmp_path) -> None:
        mock_chroma, mock_client = _make_mock_chromadb()
        with patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}):
            from hachi.core import memory_vault as _mv
            vault = _mv.MemoryVault(brain_dir=str(tmp_path))
            with vault._vault_lock:
                vault._get_collection("collection")  # touch only core_memory

        # Only one get_or_create_collection call should have happened.
        assert mock_client.get_or_create_collection.call_count == 1

        # user_collection, agent_profile, delegation_collection, quarantine_collection
        # must still be None.
        for attr in (
            "user_collection",
            "agent_profile",
            "delegation_collection",
            "quarantine_collection",
        ):
            assert vault._collections[attr] is None, (
                f"PERF-05: '{attr}' was eagerly created when only 'collection' was accessed"
            )

        vault.close()


# ---------------------------------------------------------------------------
# 7. Write-then-read round-trip (real ChromaDB, skipped when not installed)
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Functional smoke test: upsert then search returns the stored content."""

    def test_upsert_and_search_roundtrip(self, tmp_path) -> None:
        """Write a fact then retrieve it — verifies end-to-end lazy init works."""
        pytest = __import__("pytest")
        pytest.importorskip("chromadb", reason="chromadb not installed")

        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        try:
            fact_id = vault.upsert_fact("Hachi uses lazy ChromaDB init", category="workspace_state")
            assert not fact_id.startswith("BLOCKED"), f"Write was unexpectedly blocked: {fact_id}"

            results = vault.semantic_search("lazy ChromaDB", top_k=3)
            assert results, "Expected at least one result after upsert"
            texts = [r["raw_content"] for r in results]
            assert any("lazy ChromaDB" in t for t in texts), (
                f"Stored fact not found in search results: {texts}"
            )
        finally:
            vault.close()

    def test_user_profile_roundtrip(self, tmp_path) -> None:
        pytest = __import__("pytest")
        pytest.importorskip("chromadb", reason="chromadb not installed")

        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        try:
            fact_id = vault.upsert_user_fact("User prefers dark mode", category="preference")
            assert not fact_id.startswith("BLOCKED")

            snapshot = vault.get_user_snapshot()
            assert "dark mode" in snapshot, f"User fact missing from snapshot: {snapshot!r}"
        finally:
            vault.close()


# ---------------------------------------------------------------------------
# 8. _closed / _assert_open semantics preserved
# ---------------------------------------------------------------------------

class TestClosedSemantics:
    """close() and _assert_open must behave identically after the refactor."""

    def test_closed_false_on_fresh_vault(self, tmp_path) -> None:
        pytest = __import__("pytest")
        pytest.importorskip("chromadb", reason="chromadb not installed")
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        assert vault._closed is False
        vault.close()

    def test_closed_true_after_close(self, tmp_path) -> None:
        pytest = __import__("pytest")
        pytest.importorskip("chromadb", reason="chromadb not installed")
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()
        assert vault._closed is True

    def test_post_close_upsert_raises_runtime_error(self, tmp_path) -> None:
        pytest = __import__("pytest")
        pytest.importorskip("chromadb", reason="chromadb not installed")
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()

        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="MemoryVault is closed"):
            vault.upsert_fact("should fail")

    def test_post_close_search_raises_runtime_error(self, tmp_path) -> None:
        pytest = __import__("pytest")
        pytest.importorskip("chromadb", reason="chromadb not installed")
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.upsert_fact("pre-close fact")
        vault.close()

        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="MemoryVault is closed"):
            vault.semantic_search("pre-close fact")

    def test_close_is_idempotent(self, tmp_path) -> None:
        pytest = __import__("pytest")
        pytest.importorskip("chromadb", reason="chromadb not installed")
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()
        vault.close()  # must not raise
        assert vault._closed is True


# ---------------------------------------------------------------------------
# 9. close() before any collection access is a cheap no-op
# ---------------------------------------------------------------------------

class TestCloseBeforeAnyAccess:
    """Closing a vault that was never used must not touch ChromaDB at all."""

    def test_close_before_access_does_not_create_client(self, tmp_path) -> None:
        mock_chroma, mock_client = _make_mock_chromadb()
        with patch.dict(sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_chroma}):
            from hachi.core import memory_vault as _mv
            vault = _mv.MemoryVault(brain_dir=str(tmp_path))
            vault.close()

        mock_chroma.PersistentClient.assert_not_called()
        mock_client.get_or_create_collection.assert_not_called()
        assert vault._closed is True
