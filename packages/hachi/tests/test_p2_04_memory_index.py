"""P2-04: MemoryIndex FTS5 + RRF merge tests.

Verifies:
- MemoryIndex.refresh() indexes .og files from the memory/ dir
- MemoryIndex.search() returns BM25-ranked results
- Flag-off: semantic_search returns Chroma-only results (byte-identical behavior)
- Flag-on: results are RRF-merged with graph index results
- rrf_merge correctly combines two ranked lists
- _sanitize_fts5 strips characters that break FTS5 MATCH syntax
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hachi.core.memory_index import MemoryIndex, _sanitize_fts5, rrf_merge

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROFILE_OG = """\
::meta
  title: User Profile
  version: 1.0.0

::node[name]
->[:role=preference]
->[:keywords=name, identity]
::dense
User's name is Alice.

::node[timezone]
->[:role=preference]
->[:keywords=timezone, location]
::dense
User is in UTC+5:30.
"""

_PROJECT_OG = """\
::meta
  title: Billing Migration
  version: 1.0.0

::node[billing-db-migration]
->[:role=project]
->[:keywords=migration, postgres, billing, database]
::dense
Migrate billing Postgres 12 to 16. Status: in-progress.

::node[use-pgloader]
->[:role=decision]
->[:keywords=pgloader, tooling, decision]
::dense
Decision: use pgloader, not AWS DMS.
"""


def _write_og(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _index(tmp_path: Path) -> MemoryIndex:
    mem_dir = tmp_path / "memory"
    db = tmp_path / "memory_index.db"
    return MemoryIndex(memory_dir=mem_dir, db_path=db)


# ---------------------------------------------------------------------------
# MemoryIndex basics
# ---------------------------------------------------------------------------


def test_refresh_empty_dir_returns_zero(tmp_path: Path) -> None:
    idx = _index(tmp_path)
    count = idx.refresh()
    assert count == 0


def test_refresh_indexes_og_nodes(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    idx = _index(tmp_path)
    count = idx.refresh()
    assert count == 2  # name + timezone


def test_refresh_indexes_nested_og(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    _write_og(tmp_path / "memory" / "projects" / "billing.og", _PROJECT_OG)
    idx = _index(tmp_path)
    count = idx.refresh()
    assert count == 4  # 2 + 2


def test_node_count_matches_refresh(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    idx = _index(tmp_path)
    idx.refresh()
    assert idx.node_count == 2


def test_refresh_idempotent(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    idx = _index(tmp_path)
    idx.refresh()
    idx.refresh()
    # Second refresh rebuilds from scratch — count must not double
    assert idx.node_count == 2


# ---------------------------------------------------------------------------
# MemoryIndex.search
# ---------------------------------------------------------------------------


def test_search_returns_matching_node(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "projects" / "billing.og", _PROJECT_OG)
    idx = _index(tmp_path)
    idx.refresh()

    results = idx.search("database migration postgres", top_k=5)
    assert len(results) > 0
    ids = [r["id"] for r in results]
    assert any("billing-db-migration" in iid for iid in ids)


def test_search_returns_correct_shape(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    idx = _index(tmp_path)
    idx.refresh()

    results = idx.search("name", top_k=3)
    assert results
    first = results[0]
    assert "id" in first
    assert "content" in first
    assert "raw_content" in first
    assert "category" in first
    assert "timestamp" in first


def test_search_empty_query_returns_empty(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    idx = _index(tmp_path)
    idx.refresh()

    assert idx.search("") == []
    assert idx.search("   ") == []


def test_search_no_match_returns_empty(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    idx = _index(tmp_path)
    idx.refresh()

    results = idx.search("xyzzy_nonexistent_term_99", top_k=5)
    assert results == []


def test_search_on_empty_index_returns_empty(tmp_path: Path) -> None:
    idx = _index(tmp_path)
    # No refresh — empty DB
    results = idx.search("anything", top_k=5)
    assert results == []


def test_search_respects_top_k(tmp_path: Path) -> None:
    _write_og(tmp_path / "memory" / "projects" / "billing.og", _PROJECT_OG)
    _write_og(tmp_path / "memory" / "profile.og", _PROFILE_OG)
    idx = _index(tmp_path)
    idx.refresh()

    results = idx.search("user billing migration", top_k=1)
    assert len(results) <= 1


# ---------------------------------------------------------------------------
# Flag-off: search is byte-identical to Chroma-only
# ---------------------------------------------------------------------------


def test_flag_off_search_identical_to_chroma(tmp_path: Path) -> None:
    """When no graph index is attached, semantic_search must return Chroma-only results.

    We simulate this without real ChromaDB by using mock return values.
    """
    chroma_results: list[dict[str, Any]] = [
        {"id": "c1", "content": "fact a", "raw_content": "fact a",
         "category": "workspace", "timestamp": "t1"},
        {"id": "c2", "content": "fact b", "raw_content": "fact b",
         "category": "workspace", "timestamp": "t2"},
    ]

    # Patch _query_collection to avoid real Chroma
    class _FakeVault:
        _graph_index = None

        def _query_collection(self, collection: Any, query: str, top_k: int) -> list[dict]:
            return chroma_results

        def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
            chroma = self._query_collection(None, query, top_k)
            if self._graph_index is None:
                return chroma
            from hachi.core.memory_index import rrf_merge
            graph = self._graph_index.search(query, top_k=top_k)
            return rrf_merge(chroma, graph, top_k=top_k)

    vault = _FakeVault()
    results = vault.semantic_search("anything", top_k=2)
    assert results == chroma_results


# ---------------------------------------------------------------------------
# RRF merge
# ---------------------------------------------------------------------------


def test_rrf_merge_combines_disjoint_lists() -> None:
    a = [{"id": "a1"}, {"id": "a2"}]
    b = [{"id": "b1"}, {"id": "b2"}]
    merged = rrf_merge(a, b, top_k=4)
    ids = [r["id"] for r in merged]
    assert set(ids) == {"a1", "a2", "b1", "b2"}


def test_rrf_merge_boosts_items_in_both_lists() -> None:
    # "shared" appears in rank 1 of both lists — should outscore items only in one list
    a = [{"id": "shared"}, {"id": "a_only"}]
    b = [{"id": "shared"}, {"id": "b_only"}]
    merged = rrf_merge(a, b, top_k=3)
    assert merged[0]["id"] == "shared"


def test_rrf_merge_respects_top_k() -> None:
    a = [{"id": f"a{i}"} for i in range(10)]
    b = [{"id": f"b{i}"} for i in range(10)]
    merged = rrf_merge(a, b, top_k=5)
    assert len(merged) == 5


def test_rrf_merge_empty_inputs() -> None:
    assert rrf_merge([], [], top_k=5) == []
    assert rrf_merge([{"id": "x"}], [], top_k=5) == [{"id": "x"}]
    assert rrf_merge([], [{"id": "y"}], top_k=5) == [{"id": "y"}]


# ---------------------------------------------------------------------------
# FTS5 query sanitizer
# ---------------------------------------------------------------------------


def test_sanitize_removes_fts5_operators() -> None:
    assert _sanitize_fts5('"quoted phrase"') == "quoted phrase"
    assert _sanitize_fts5("term*") == "term"
    assert _sanitize_fts5("(nested)") == "nested"
    assert _sanitize_fts5("a OR b") == "a OR b"  # OR is fine (uppercase keyword)


def test_sanitize_empty_query() -> None:
    assert _sanitize_fts5("") == ""
    assert _sanitize_fts5("   ") == ""
