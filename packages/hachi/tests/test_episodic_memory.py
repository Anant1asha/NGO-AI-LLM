"""
Tests for M1 — Episodic Memory Store.

Covers:
  build_episode_summary: pure function, deterministic, no LLM.
  upsert_episode + search_episodic: round-trip with _FakeCollection pattern.
  Redaction invariant: secrets in episode summaries are redacted on recall.
  top_k=0 guard: search_episodic(top_k=0) returns [].
  Upsert idempotency: re-upserting the same session_id updates, no duplicate.
  search_delegations redaction: Part D regression.
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any

# ---------------------------------------------------------------------------
# Shared fake collection (mirrors tests/test_memory_fixes.py _FakeCollection)
# ---------------------------------------------------------------------------


class _FakeCollection:
    """Minimal in-memory ChromaDB collection stub."""

    def __init__(self, name: str = "core_memory") -> None:
        self.name = name
        self._data: dict[str, dict] = {}  # id → {document, metadata}

    def count(self) -> int:
        return len(self._data)

    def upsert(self, ids, documents, metadatas) -> None:
        for _id, doc, meta in zip(ids, documents, metadatas, strict=False):
            self._data[_id] = {"document": doc, "metadata": meta}

    def get(
        self,
        ids=None,
        limit: int | None = None,
        include: list | None = None,
    ) -> dict:
        rows = list(self._data.values())
        all_ids = list(self._data.keys())
        if ids is not None:
            filtered = [(i, self._data[i]) for i in ids if i in self._data]
            all_ids = [i for i, _ in filtered]
            rows = [v for _, v in filtered]
        if limit is not None:
            rows = rows[:limit]
            all_ids = all_ids[:limit]
        return {
            "ids": all_ids,
            "documents": [r["document"] for r in rows],
            "metadatas": [r["metadata"] for r in rows],
        }

    def query(
        self,
        query_texts,
        n_results: int = 5,
        include: list | None = None,
        where=None,
    ) -> dict:
        rows = list(self._data.values())[:n_results]
        ids_list = list(self._data.keys())[:n_results]
        distances = [0.1 * (i + 1) for i in range(len(rows))]
        return {
            "ids": [ids_list],
            "documents": [[r["document"] for r in rows]],
            "metadatas": [[r["metadata"] for r in rows]],
            "distances": [distances],
        }

    def delete(self, ids) -> None:
        for _id in ids:
            self._data.pop(_id, None)


def _make_vault_with_episodic(
    recall_distance_max: float | None = None,
    core_memory_max_entries: int = 1000,
) -> Any:
    """Return a MemoryVault with ChromaDB fully stubbed, including episodic_collection."""
    from hachi.core.memory_vault import MemoryVault

    vault = MemoryVault.__new__(MemoryVault)

    vault._vault_lock = threading.RLock()
    vault._account_id = "default"
    vault._coll_prefix = ""
    vault._chroma_client = None
    vault._graph_index = None
    vault._closed = False
    vault.is_shared = False
    vault.db_path = "/tmp/fake"
    vault._recall_distance_max = recall_distance_max
    vault._core_memory_max_entries = max(1, core_memory_max_entries)

    fake_core = _FakeCollection("core_memory")
    fake_user = _FakeCollection("user_profile")
    fake_agent = _FakeCollection("agent_profile")
    fake_deleg = _FakeCollection("delegation_log")
    fake_quar = _FakeCollection("memory_quarantine")
    fake_episodic = _FakeCollection("episodic_memory")

    vault._collections = {
        "collection": fake_core,
        "user_collection": fake_user,
        "agent_profile": fake_agent,
        "delegation_collection": fake_deleg,
        "quarantine_collection": fake_quar,
        "episodic_collection": fake_episodic,
    }
    return vault


# ---------------------------------------------------------------------------
# build_episode_summary — pure function tests
# ---------------------------------------------------------------------------


class TestBuildEpisodeSummary:
    """Pure function: deterministic, no LLM, no I/O."""

    def _fn(self, interactions, **kw):
        from hachi.core.memory import build_episode_summary

        return build_episode_summary(interactions, **kw)

    def test_empty_returns_empty_string(self) -> None:
        assert self._fn([]) == ""

    def test_single_turn_contains_user_input(self) -> None:
        interactions = [
            {
                "user_input": "What is the capital of France?",
                "agent_output": "Paris is the capital of France.",
                "tool_calls": [],
            }
        ]
        result = self._fn(interactions)
        assert "What is the capital of France?" in result
        assert "Paris is the capital of France." in result
        assert "1 turn" in result

    def test_multi_turn_counts_correctly(self) -> None:
        interactions = [
            {"user_input": f"Turn {i}", "agent_output": f"Response {i}", "tool_calls": []}
            for i in range(5)
        ]
        result = self._fn(interactions)
        assert "5 turn" in result
        assert "Turn 0" in result
        assert "Turn 4" in result

    def test_tool_calls_included(self) -> None:
        interactions = [
            {
                "user_input": "List files",
                "agent_output": "Here are the files.",
                "tool_calls": ["list_directory", "read_file"],
            }
        ]
        result = self._fn(interactions)
        assert "list_directory" in result
        assert "read_file" in result

    def test_respects_max_chars_cap(self) -> None:
        # Generate a large interaction to force truncation
        long_input = "A" * 200
        interactions = [
            {"user_input": long_input, "agent_output": long_input, "tool_calls": []}
            for _ in range(20)
        ]
        result = self._fn(interactions, max_chars=300)
        assert len(result) <= 320  # allow for the truncation note
        assert "truncated" in result

    def test_user_input_snippet_truncated(self) -> None:
        long_input = "X" * 300
        interactions = [{"user_input": long_input, "agent_output": "ok", "tool_calls": []}]
        result = self._fn(interactions)
        # Individual field is capped at 120 chars + ellipsis, total won't have 300 X's
        assert "X" * 121 not in result

    def test_sparse_fields_no_crash(self) -> None:
        # Missing keys should not crash
        interactions = [{"user_input": None, "agent_output": "", "tool_calls": None}]
        result = self._fn(interactions)
        assert isinstance(result, str)
        assert result != ""  # header line still present

    def test_empty_tool_calls_not_included(self) -> None:
        interactions = [
            {"user_input": "hi", "agent_output": "hello", "tool_calls": []}
        ]
        result = self._fn(interactions)
        assert "Tools:" not in result


# ---------------------------------------------------------------------------
# upsert_episode + search_episodic round-trip
# ---------------------------------------------------------------------------


class TestEpisodicRoundTrip:
    """upsert_episode → search_episodic with _FakeCollection stub."""

    def test_upsert_then_search_finds_episode(self) -> None:
        vault = _make_vault_with_episodic(recall_distance_max=None)
        vault.upsert_episode(
            session_id="sess-001",
            summary="User asked about Paris and France.",
            started_at="2026-06-25T10:00:00",
        )
        results = vault.search_episodic("Paris France", top_k=3)
        assert len(results) == 1
        assert "Paris" in results[0]["content"]

    def test_top_k_zero_returns_empty(self) -> None:
        vault = _make_vault_with_episodic()
        vault.upsert_episode(
            session_id="sess-002",
            summary="Some content here.",
            started_at="2026-06-25T10:00:00",
        )
        assert vault.search_episodic("content", top_k=0) == []

    def test_empty_collection_returns_empty(self) -> None:
        vault = _make_vault_with_episodic()
        assert vault.search_episodic("anything", top_k=3) == []

    def test_upsert_idempotent_same_session(self) -> None:
        """Re-upserting the same session_id must update, not duplicate."""
        vault = _make_vault_with_episodic(recall_distance_max=None)
        vault.upsert_episode(
            session_id="sess-003",
            summary="First version of the summary.",
            started_at="2026-06-25T10:00:00",
        )
        vault.upsert_episode(
            session_id="sess-003",
            summary="Updated summary with more detail.",
            started_at="2026-06-25T10:00:00",
        )
        episodic_coll = vault._collections["episodic_collection"]
        assert episodic_coll.count() == 1, "Re-upsert should not create a second entry"
        results = vault.search_episodic("summary", top_k=3)
        assert "Updated summary" in results[0]["content"]

    def test_redaction_applied_on_search(self) -> None:
        """A fake API key in a summary must be redacted in search results."""
        vault = _make_vault_with_episodic(recall_distance_max=None)
        secret_summary = "User shared their API key: sk-abcdefghijklmnopqrstuvwxyz123456"
        vault.upsert_episode(
            session_id="sess-004",
            summary=secret_summary,
            started_at="2026-06-25T10:00:00",
        )
        results = vault.search_episodic("API key", top_k=3)
        assert len(results) == 1
        # The raw sk-... token must NOT appear in results
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in results[0]["content"]
        assert "[REDACTED" in results[0]["content"]

    def test_keywords_stored_in_metadata(self) -> None:
        vault = _make_vault_with_episodic(recall_distance_max=None)
        vault.upsert_episode(
            session_id="sess-005",
            summary="A coding session about Python.",
            started_at="2026-06-25T10:00:00",
            keywords=["python", "coding"],
        )
        episodic_coll = vault._collections["episodic_collection"]
        entry_id = hashlib.sha256(b"episode:sess-005").hexdigest()
        raw = episodic_coll.get(ids=[entry_id])
        meta = raw["metadatas"][0]
        assert "python" in meta["keywords"]
        assert "coding" in meta["keywords"]

    def test_search_returns_same_shape_as_semantic_search(self) -> None:
        """search_episodic output dict shape must match semantic_search."""
        vault = _make_vault_with_episodic(recall_distance_max=None)
        vault.upsert_episode(
            session_id="sess-006",
            summary="User asked about file systems.",
            started_at="2026-06-25T09:00:00",
        )
        ep_results = vault.search_episodic("file system", top_k=3)
        # Both should return dicts with the same core keys
        assert ep_results  # non-empty
        for key in ("id", "content", "category", "timestamp"):
            assert key in ep_results[0], f"key {key!r} missing from episodic result"


# ---------------------------------------------------------------------------
# Part D regression: search_delegations must redact results
# ---------------------------------------------------------------------------


class TestSearchDelegationsRedaction:
    """Regression: search_delegations now applies _redact_results (Part D fix)."""

    def _make_vault_with_delegation(self) -> Any:
        vault = _make_vault_with_episodic(recall_distance_max=None)
        return vault

    def test_delegation_search_redacts_api_key(self) -> None:
        vault = self._make_vault_with_delegation()
        # Inject a delegation log entry directly with a fake secret
        deleg_coll = vault._collections["delegation_collection"]
        secret_doc = "[coder] [success] Wrote code with key sk-testtesttesttesttest1234567890"
        entry_id = hashlib.sha256(secret_doc.encode()).hexdigest()
        deleg_coll._data[entry_id] = {
            "document": secret_doc,
            "metadata": {
                "role": "coder",
                "status": "success",
                "duration": "1.0",
                "iterations": "3",
                "tokens": "100",
                "timestamp": "2026-06-25T10:00:00",
            },
        }
        results = vault.search_delegations("code key", top_k=3)
        assert len(results) == 1
        # The raw sk-... token must NOT appear in content
        assert "sk-testtesttesttesttest1234567890" not in results[0]["content"]
        assert "[REDACTED" in results[0]["content"]
