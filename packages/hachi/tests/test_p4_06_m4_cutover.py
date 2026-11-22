"""P4-06: M4 cutover — FTS5-only path + Chroma→files exporter.

Tests:
  1. MemoryBackend literal accepts "fts5_only".
  2. resolve_provider("fts5_only") returns FTS5MemoryProvider.
  3. FTS5MemoryProvider.search() returns [] when no graph index attached.
  4. FTS5MemoryProvider.search() delegates to attached graph index.
  5. FTS5MemoryProvider.upsert() returns a valid string ID (fallback UUID).
  6. FTS5MemoryProvider.delete() always returns False (not supported).
  7. chroma_to_files() dry_run=True writes nothing to disk.
  8. chroma_to_files() exports facts from a mock Chroma vault.
  9. chroma_to_files() skips existing nodes (additive-only).
  10. ExportResult str representation is informative.
  11. _extract_keywords strips stopwords and returns ≤5 terms.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. MemoryBackend literal accepts "fts5_only"
# ---------------------------------------------------------------------------


def test_memory_backend_literal_fts5_only() -> None:
    from hachi.core.settings import MemorySettings

    s = MemorySettings(backend="fts5_only")
    assert s.backend == "fts5_only"


# ---------------------------------------------------------------------------
# 2. resolve_provider("fts5_only") returns FTS5MemoryProvider
# ---------------------------------------------------------------------------


def test_resolve_provider_fts5_only() -> None:
    from hachi.core.memory_provider import FTS5MemoryProvider, resolve_provider
    from hachi.core.settings import MemorySettings

    settings = MemorySettings(backend="fts5_only")
    provider = resolve_provider(settings)
    assert isinstance(provider, FTS5MemoryProvider)


# ---------------------------------------------------------------------------
# 3. FTS5MemoryProvider.search() returns [] when no index attached
# ---------------------------------------------------------------------------


def test_fts5_provider_search_no_index() -> None:
    from hachi.core.memory_provider import FTS5MemoryProvider

    provider = FTS5MemoryProvider()
    provider.initialize(brain_dir="/tmp/fake")
    results = provider.search("billing task", top_k=5)
    assert results == []


# ---------------------------------------------------------------------------
# 4. FTS5MemoryProvider.search() delegates to attached graph index
# ---------------------------------------------------------------------------


def test_fts5_provider_search_delegates() -> None:
    from hachi.core.memory_provider import FTS5MemoryProvider

    mock_index = MagicMock()
    mock_index.search.return_value = [
        {"id": "abc", "content": "billing task", "category": "task", "timestamp": ""}
    ]

    provider = FTS5MemoryProvider()
    provider.attach_graph_index(mock_index)
    results = provider.search("billing")

    mock_index.search.assert_called_once_with("billing", top_k=5)
    assert len(results) == 1
    assert results[0]["id"] == "abc"


# ---------------------------------------------------------------------------
# 5. FTS5MemoryProvider.upsert() returns a non-empty string (fallback UUID)
# ---------------------------------------------------------------------------


def test_fts5_provider_upsert_fallback_uuid() -> None:
    from hachi.core.memory_provider import FTS5MemoryProvider

    provider = FTS5MemoryProvider()
    fact_id = provider.upsert("billing migrate schema", category="task")
    assert isinstance(fact_id, str)
    assert len(fact_id) > 0


# ---------------------------------------------------------------------------
# 6. FTS5MemoryProvider.delete() always returns False
# ---------------------------------------------------------------------------


def test_fts5_provider_delete_returns_false() -> None:
    from hachi.core.memory_provider import FTS5MemoryProvider

    provider = FTS5MemoryProvider()
    assert provider.delete("any-id") is False


# ---------------------------------------------------------------------------
# 7. chroma_to_files() dry_run=True writes nothing to disk
# ---------------------------------------------------------------------------


def test_chroma_to_files_dry_run_writes_nothing(tmp_path: Path) -> None:
    from hachi.core.memory_exporter import chroma_to_files

    vault = _mock_vault_with_facts()
    result = chroma_to_files(vault, memory_dir=tmp_path, dry_run=True)

    # No files should have been written
    og_files = list(tmp_path.rglob("*.og"))
    assert og_files == [], f"Expected no files on dry_run, found {og_files}"
    # But exported count should be > 0 (we had facts)
    assert result.exported > 0


# ---------------------------------------------------------------------------
# 8. chroma_to_files() exports facts from a mock vault
# ---------------------------------------------------------------------------


def test_chroma_to_files_exports_facts(tmp_path: Path) -> None:
    from hachi.core.memory_exporter import chroma_to_files

    vault = _mock_vault_with_facts()
    result = chroma_to_files(vault, memory_dir=tmp_path, dry_run=False)

    assert result.exported >= 1
    assert result.errors == 0
    assert len(result.output_files) >= 1

    # Verify content was written
    export_og = tmp_path / "journal" / "chroma_export.og"
    assert export_og.exists()
    text = export_og.read_text(encoding="utf-8")
    assert "::node[" in text
    assert "::dense" in text


# ---------------------------------------------------------------------------
# 9. chroma_to_files() skips existing nodes (additive-only)
# ---------------------------------------------------------------------------


def test_chroma_to_files_skips_existing(tmp_path: Path) -> None:
    from hachi.core.memory_exporter import chroma_to_files

    vault = _mock_vault_with_facts()
    # First run
    result1 = chroma_to_files(vault, memory_dir=tmp_path, dry_run=False)
    # Second run — same facts already present
    result2 = chroma_to_files(vault, memory_dir=tmp_path, dry_run=False)

    assert result2.skipped_existing >= result1.exported
    assert result2.exported == 0, "No new facts should be exported on second run"


# ---------------------------------------------------------------------------
# 10. ExportResult str representation
# ---------------------------------------------------------------------------


def test_export_result_str() -> None:
    from hachi.core.memory_exporter import ExportResult

    r = ExportResult(exported=5, skipped_existing=2, errors=0, output_files=["a.og", "b.og"])
    s = str(r)
    assert "exported=5" in s
    assert "skipped=2" in s


# ---------------------------------------------------------------------------
# 11. _extract_keywords strips stopwords
# ---------------------------------------------------------------------------


def test_extract_keywords_strips_stopwords() -> None:
    from hachi.core.memory_exporter import _extract_keywords

    kw = _extract_keywords("the billing task is open and needs migration", max_kw=5)
    assert "the" not in kw
    assert "and" not in kw
    assert "is" not in kw
    assert len(kw) <= 5
    assert any(k in kw for k in ("billing", "task", "open", "needs", "migration"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_vault_with_facts():
    """Build a mock MemoryVault that returns two facts from core_memory."""
    vault = MagicMock()

    # core_memory returns 2 facts
    vault.collection.get.return_value = {
        "ids": ["aabbcc001122", "ddeeff334455"],
        "documents": ["Billing table needs schema migration", "Use pgloader for migration"],
        "metadatas": [
            {"category": "task", "timestamp": "2026-06-13T00:00:00Z"},
            {"category": "decision", "timestamp": "2026-06-13T00:01:00Z"},
        ],
    }
    # Other collections are empty
    vault.user_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    vault.agent_profile.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    vault.delegation_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    vault.quarantine_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    return vault
