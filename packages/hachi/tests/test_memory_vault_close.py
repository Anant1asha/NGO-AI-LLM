"""Regression tests for H12 — MemoryVault close/race fix.

Previously, close() nulled collection refs under the RLock but did NOT set a
``_closed`` flag.  A call to any collection-access method immediately after
close() would fail with ``AttributeError: 'NoneType' object has no attribute
'upsert'`` (or similar) rather than a clear, deterministic error.

This test file un-skips the masking test that was removed from the test suite
and verifies that the H12 fix (``_closed`` flag + ``_assert_open`` checks)
makes post-close calls raise ``RuntimeError("MemoryVault is closed")`` rather
than crashing with AttributeError.

Contract chosen: RAISE RuntimeError.
Rationale: callers in the tools layer (memory_tools.py) already wrap tool
execution in try/except and return error strings to the LLM.  A clear
RuntimeError is distinguishable from a ChromaDB failure and lets callers give
a useful error message.  Returning empty results silently would mask bugs
where a vault is accidentally used after teardown.
"""

from __future__ import annotations

import pytest


def _require_chroma():
    """Skip the test if chromadb is not installed (CI base-install may lack it)."""
    pytest.importorskip("chromadb", reason="chromadb not installed — skipping MemoryVault test")


# ---------------------------------------------------------------------------
# H12 — close() sets _closed flag; subsequent access raises RuntimeError
# ---------------------------------------------------------------------------


class TestMemoryVaultCloseRace:
    """Post-close access raises RuntimeError, not AttributeError."""

    def test_closed_flag_false_before_close(self, tmp_path) -> None:
        """_closed must be False on a freshly constructed vault."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        assert vault._closed is False
        vault.close()

    def test_closed_flag_true_after_close(self, tmp_path) -> None:
        """_closed must be True immediately after close()."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()
        assert vault._closed is True

    def test_close_is_idempotent(self, tmp_path) -> None:
        """Calling close() twice must not raise."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()
        vault.close()  # Must not raise
        assert vault._closed is True

    def test_upsert_fact_after_close_raises_runtime_error(self, tmp_path) -> None:
        """upsert_fact() after close() raises RuntimeError, not AttributeError.

        This is the primary H12 regression guard: the old code would crash with
        ``AttributeError: 'NoneType' object has no attribute 'upsert'``.
        """
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()

        with pytest.raises(RuntimeError, match="MemoryVault is closed"):
            vault.upsert_fact("This should fail cleanly", category="workspace_state")

    def test_semantic_search_after_close_raises_runtime_error(self, tmp_path) -> None:
        """semantic_search() after close() raises RuntimeError, not AttributeError."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        # Prime with a fact before closing.
        vault.upsert_fact("some fact", category="workspace_state")
        vault.close()

        with pytest.raises(RuntimeError, match="MemoryVault is closed"):
            vault.semantic_search("some query")

    def test_upsert_user_fact_after_close_raises_runtime_error(self, tmp_path) -> None:
        """upsert_user_fact() after close() raises RuntimeError, not AttributeError."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()

        with pytest.raises(RuntimeError, match="MemoryVault is closed"):
            vault.upsert_user_fact("user prefers dark mode", category="preference")

    def test_search_user_profile_after_close_raises_runtime_error(self, tmp_path) -> None:
        """search_user_profile() after close() raises RuntimeError."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()

        with pytest.raises(RuntimeError, match="MemoryVault is closed"):
            vault.search_user_profile("preferences")

    def test_delete_fact_after_close_raises_runtime_error(self, tmp_path) -> None:
        """delete_fact() after close() raises RuntimeError (caught internally → False)."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        fact_id = vault.upsert_fact("deletable fact")
        vault.close()

        # delete_fact wraps the lock in try/except and returns False on failure —
        # RuntimeError is caught there.  The important thing is it does NOT crash
        # the process with AttributeError; returning False is the documented contract.
        result = vault.delete_fact(fact_id)
        assert result is False, (
            "delete_fact after close should return False (RuntimeError caught internally)"
        )

    def test_get_user_snapshot_after_close_raises_runtime_error(self, tmp_path) -> None:
        """get_user_snapshot() after close() raises RuntimeError."""
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()

        with pytest.raises(RuntimeError, match="MemoryVault is closed"):
            vault.get_user_snapshot()

    def test_no_attribute_error_after_close(self, tmp_path) -> None:
        """After close(), any collection-access call must NOT raise AttributeError.

        This is the exact failure mode reported in H12: NoneType.upsert AttributeError.
        We verify that calling upsert_fact raises RuntimeError (expected) rather than
        AttributeError (the old crash from nulled collection refs).
        """
        _require_chroma()
        from hachi.core.memory_vault import MemoryVault

        vault = MemoryVault(brain_dir=str(tmp_path))
        vault.close()

        try:
            vault.upsert_fact("post-close call")
        except RuntimeError:
            pass  # Expected — the new deterministic contract.
        except AttributeError as exc:
            pytest.fail(
                f"H12 regression: AttributeError raised after close() instead of "
                f"RuntimeError: {exc}"
            )
