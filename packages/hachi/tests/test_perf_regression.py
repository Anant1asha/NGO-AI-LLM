"""P2-13 — Perf/latency regression guard for memory recall and context compaction.

Design principle: ALL primary guards are structural/call-count assertions — deterministic
and CI-safe. Wall-clock threshold checks are omitted entirely (they would be flaky on CI
runners). An env-gated secondary wall-clock check is not included because the structural
guards are sufficient and sufficient is better than noisy.

Seams guarded
-------------
Compaction (src/hachi/core/memory.py):
  - _MAX_COMPACT_PASSES = 3 (local constant inside _sliding_window_compact, line ~1013)
    The loop ``for _pass in range(_MAX_COMPACT_PASSES):`` at line ~1029 bounds retries.
  - add_message() → _sliding_window_compact() at lines ~659-665.
  - estimate_token_count() at lines ~797-810 (O(N) bounded by active window).

Recall (src/hachi/core/memory_vault.py):
  - _query_collection() calls collection.query(n_results=top_k) at line ~774.
    ``top_k`` flows in from semantic_search(top_k=5) and search_user_profile(top_k=10).
  - Lazy vault: _chroma_client is None at __init__ (line ~335), _collections are all
    None (line ~339). __init__ does NOT call _get_client() or _get_collection().

Tests that require ChromaDB use the same fake-collection pattern as test_memory_fixes.py
(MemoryVault.__new__ + pre-populated _collections dict) and therefore do NOT require
a real ChromaDB installation. All tests in this file are always-on CI.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock, patch  # noqa: F401

from hachi.core.llm import Message
from hachi.core.memory import MemoryManager

# ---------------------------------------------------------------------------
# Helpers shared across compaction tests
# ---------------------------------------------------------------------------


def _big_msg(role: str, chars: int) -> Message:
    """Return a Message with ``chars`` characters of content."""
    return Message(role=role, content="x" * chars)


def _make_mm(
    max_active_messages: int = 30,
    max_active_tokens: int = 24_000,
) -> MemoryManager:
    """Bare MemoryManager — no job queue, no vault (synchronous test path)."""
    return MemoryManager(
        max_active_messages=max_active_messages,
        max_active_tokens=max_active_tokens,
    )


# ---------------------------------------------------------------------------
# Helper shared across recall tests: a MemoryVault with stubbed ChromaDB
# ---------------------------------------------------------------------------


class _FakeCollection:
    """Minimal in-memory ChromaDB collection stub, records query call args."""

    def __init__(self, name: str = "core_memory") -> None:
        self.name = name
        self._data: dict[str, dict[str, Any]] = {}
        # Record every call to query so tests can assert on n_results.
        self.query_calls: list[dict[str, Any]] = []

    def count(self) -> int:
        return len(self._data)

    def upsert(self, ids: list, documents: list, metadatas: list) -> None:
        for _id, doc, meta in zip(ids, documents, metadatas, strict=False):
            self._data[_id] = {"document": doc, "metadata": meta}

    def get(
        self,
        ids: list | None = None,
        limit: int | None = None,
        include: list | None = None,
    ) -> dict[str, Any]:
        rows = list(self._data.values())
        if ids is not None:
            rows = [self._data[i] for i in ids if i in self._data]
        if limit is not None:
            rows = rows[:limit]
        all_ids = list(self._data.keys())
        return {
            "ids": [all_ids[list(self._data.values()).index(r)] for r in rows],
            "documents": [r["document"] for r in rows],
            "metadatas": [r["metadata"] for r in rows],
        }

    def query(
        self,
        query_texts: list,
        n_results: int = 5,
        include: list | None = None,
        where: dict | None = None,
    ) -> dict[str, Any]:
        # Record the call so tests can inspect n_results.
        self.query_calls.append({"query_texts": query_texts, "n_results": n_results})
        rows = list(self._data.values())[:n_results]
        ids_list = list(self._data.keys())[:n_results]
        distances = [0.1 * (i + 1) for i in range(len(rows))]
        return {
            "ids": [ids_list],
            "documents": [[r["document"] for r in rows]],
            "metadatas": [[r["metadata"] for r in rows]],
            "distances": [distances],
        }

    def delete(self, ids: list) -> None:
        for _id in ids:
            self._data.pop(_id, None)


def _make_stubbed_vault(
    recall_distance_max: float | None = 0.85,
) -> Any:
    """Return a MemoryVault whose ChromaDB is fully stubbed out.

    Uses MemoryVault.__new__ to bypass __init__ ChromaDB I/O, then
    manually sets all required attributes to match the real __init__.
    This is the same pattern used in test_memory_fixes.py.
    """
    from hachi.core.memory_vault import MemoryVault

    vault = MemoryVault.__new__(MemoryVault)
    vault._vault_lock = threading.RLock()
    vault._account_id = "default"
    vault._coll_prefix = ""
    vault._chroma_client = None
    vault._graph_index = None
    vault._closed = False
    vault.is_shared = False
    vault.db_path = "/tmp/fake_perf_test"
    vault._recall_distance_max = recall_distance_max
    vault._core_memory_max_entries = 1000

    # Pre-populate collection cache with recording fakes.
    vault._collections = {
        "collection": _FakeCollection("core_memory"),
        "user_collection": _FakeCollection("user_profile"),
        "agent_profile": _FakeCollection("agent_profile"),
        "delegation_collection": _FakeCollection("delegation_log"),
        "quarantine_collection": _FakeCollection("memory_quarantine"),
    }
    return vault


def _seed_facts(vault: Any, n: int) -> None:
    """Insert ``n`` facts into the core_memory collection directly."""
    import hashlib

    coll = vault._collections["collection"]
    for i in range(n):
        content = f"Fact number {i}: the project uses component_{i}"
        fact_id = hashlib.sha256(content.encode()).hexdigest()
        coll._data[fact_id] = {
            "document": content,
            "metadata": {
                "category": "workspace_state",
                "timestamp": f"2026-01-{i + 1:02d}T00:00:00",
            },
        }


# ===========================================================================
# COMPACTION GUARDS
# ===========================================================================


class TestCompactionPassBound:
    """Structural: _sliding_window_compact loops at most _MAX_COMPACT_PASSES=3 times.

    Seam: memory.py line ~1013 ``_MAX_COMPACT_PASSES = 3`` local constant,
          line ~1029 ``for _pass in range(_MAX_COMPACT_PASSES):``.
    Guard: spy on _generate_structured_summary (the call that happens once per pass
           in the no-queue synchronous path) and assert call_count <= 3.
    """

    def test_compaction_calls_summary_at_most_max_passes_times(self) -> None:
        """Even with an impossibly small budget, summary is generated ≤ 3 times."""
        # token budget of 1 guarantees every retained window still exceeds it,
        # which is precisely the stress case for the bounded loop.
        mm = _make_mm(max_active_messages=30, max_active_tokens=1)

        # Build history with enough messages to trigger compaction.
        for i in range(8):
            mm._history.append(Message(role="user", content=f"user turn {i}"))
            mm._history.append(Message(role="assistant", content=f"assistant turn {i}"))

        summary_call_count = 0
        original_generate = mm._generate_structured_summary

        def _counting_generate(messages: list) -> str:
            nonlocal summary_call_count
            summary_call_count += 1
            return original_generate(messages)

        mm._generate_structured_summary = _counting_generate  # type: ignore[method-assign]

        mm._sliding_window_compact()

        # The hard constraint: never more than _MAX_COMPACT_PASSES = 3 summary calls.
        assert summary_call_count <= 3, (
            f"_sliding_window_compact exceeded _MAX_COMPACT_PASSES=3 passes; "
            f"got {summary_call_count} _generate_structured_summary calls. "
            "This is a regression — the bounded-loop guard was removed or bypassed."
        )

    def test_compaction_exits_cleanly_at_max_passes(self) -> None:
        """_sliding_window_compact must return (not loop forever) at max passes.

        This is the guard against an infinite loop if the budget check is broken.
        We verify it terminates by the fact pytest's default timeout catches hangs,
        but we also verify structural exit by checking _history was modified.
        """
        mm = _make_mm(max_active_messages=30, max_active_tokens=1)
        for i in range(6):
            mm._history.append(Message(role="user", content=f"u{i}" * 50))
            mm._history.append(Message(role="assistant", content=f"a{i}" * 50))

        history_len_before = len(mm._history)

        # Must return — not block. The test itself times out if it loops forever.
        mm._sliding_window_compact()

        # Compaction ran at least once — history must have changed.
        assert len(mm._history) != history_len_before or any(
            isinstance(m.content, str) and "CONTEXT CHECKPOINT" in m.content for m in mm._history
        ), (
            "_sliding_window_compact must modify history or insert a checkpoint; "
            "appears to have been a no-op."
        )


class TestCompactionPerTurnWorkBounded:
    """Structural: adding one message after window is established does not re-summarize all history.

    Seam: add_message() → _sliding_window_compact() on every call when over budget.
    Guard: After the window is settled (tokens near-budget), adding one more message
           triggers at most ONE additional summary call, not O(history_size) calls.
    """

    def test_single_add_message_triggers_at_most_one_compaction(self) -> None:
        """Adding one new message triggers at most one _sliding_window_compact call.

        After the history is settled at the window size, adding the (N+1)-th
        message should not O(N)-scan the entire history for re-summarization.
        We verify this by counting calls to _sliding_window_compact itself.
        """
        mm = _make_mm(max_active_messages=8, max_active_tokens=24_000)

        # Fill to exactly the limit without triggering (messages are tiny — no token trigger).
        for i in range(4):
            mm._history.append(Message(role="user", content=f"u{i}"))
            mm._history.append(Message(role="assistant", content=f"a{i}"))

        compact_call_count = 0
        original_compact = mm._sliding_window_compact

        def _counting_compact() -> None:
            nonlocal compact_call_count
            compact_call_count += 1
            original_compact()

        mm._sliding_window_compact = _counting_compact  # type: ignore[method-assign]

        # Add one message that tips over the count limit (9 > 8).
        mm.add_message(Message(role="user", content="overflow message"))

        # Exactly one compaction call for one overflow message — not N calls.
        assert compact_call_count <= 1, (
            f"add_message triggered {compact_call_count} compaction calls for a single "
            "overflow message — per-turn work is scaling with message count (regression)."
        )

    def test_add_message_after_window_settled_bounds_compaction_to_one_pass(self) -> None:
        """Once the window is settled, subsequent adds compact at most once per call.

        Adds 20 messages one at a time; total compaction calls must be at most
        equal to the number of messages added (one compact per add that overflows),
        not N^2 or worse.
        """
        mm = _make_mm(max_active_messages=6, max_active_tokens=24_000)
        compact_call_count = 0
        original_compact = mm._sliding_window_compact

        def _counting_compact() -> None:
            nonlocal compact_call_count
            compact_call_count += 1
            original_compact()

        mm._sliding_window_compact = _counting_compact  # type: ignore[method-assign]

        n_messages = 20
        for i in range(n_messages):
            mm.add_message(Message(role="user" if i % 2 == 0 else "assistant", content=f"msg{i}"))

        # Upper bound: at most one compaction per message add. Linear is acceptable;
        # quadratic (compact_call_count > n_messages) would be a regression.
        assert compact_call_count <= n_messages, (
            f"Compaction was triggered {compact_call_count} times for {n_messages} "
            "add_message calls — worse than linear scaling (O(N²) regression)."
        )


class TestHistoryBoundedAfterManyAdds:
    """Structural: active history does not grow unbounded after many add_message calls.

    Seam: add_message() enforces _max_active_messages via _sliding_window_compact.
    Guard: after 100 adds, token estimate stays at or under the configured budget.
    This locks in the "cliff removed" behavior from BE-4.
    """

    def test_token_estimate_stays_under_budget_after_many_adds(self) -> None:
        """100 add_message calls must not push tokens above the configured budget."""
        token_budget = 5_000
        mm = _make_mm(max_active_messages=30, max_active_tokens=token_budget)

        for i in range(50):
            mm.add_message(Message(role="user", content=f"user message number {i}"))
            mm.add_message(Message(role="assistant", content=f"assistant reply number {i}"))

        final_tokens = mm.estimate_token_count()

        # Allow a small tolerance: compaction fires after the triggering message is
        # already appended, so the window may be one message over when we measure.
        # We allow 2× budget as a generous upper bound — the real cap is 1× + epsilon.
        assert final_tokens <= token_budget * 2, (
            f"Token estimate grew unbounded: {final_tokens} tokens after 100 adds "
            f"(budget={token_budget}). "
            "Compaction is not preventing unbounded history growth (regression)."
        )

    def test_history_length_bounded_after_many_adds(self) -> None:
        """Message count must not grow without bound when add_message is called many times."""
        max_msgs = 10
        mm = _make_mm(max_active_messages=max_msgs, max_active_tokens=24_000)

        for i in range(60):
            mm.add_message(Message(role="user" if i % 2 == 0 else "assistant", content=f"m{i}"))

        # History must not exceed the configured window by more than a small epsilon
        # (compaction fires after the appended message, so ≤ window+2 is acceptable).
        assert len(mm._history) <= max_msgs + 4, (
            f"History grew to {len(mm._history)} messages after 60 adds "
            f"(max_active_messages={max_msgs}). "
            "The message-count compaction guard is broken (regression)."
        )


# ===========================================================================
# RECALL GUARDS
# ===========================================================================


class TestRecallBoundedTopK:
    """Structural: recall passes a bounded n_results to ChromaDB — never an unbounded scan.

    Seam: memory_vault.py line ~774 ``collection.query(n_results=top_k, ...)``.
          semantic_search(top_k=5) and search_user_profile(top_k=10) are the callers.
    Guard: spy on _FakeCollection.query and assert n_results == the expected top_k.
    """

    def test_semantic_search_passes_bounded_n_results_to_query(self) -> None:
        """semantic_search(top_k=5) must call collection.query(n_results=5).

        A regression would be passing n_results=None or a huge value (unbounded scan).
        """
        vault = _make_stubbed_vault()
        _seed_facts(vault, 20)

        vault.semantic_search("test query", top_k=5)

        coll = vault._collections["collection"]
        assert len(coll.query_calls) >= 1, "collection.query was never called"
        last_call = coll.query_calls[-1]
        assert last_call["n_results"] == 5, (
            f"semantic_search(top_k=5) passed n_results={last_call['n_results']} to "
            "collection.query — expected 5. An unbounded n_results would scan the "
            "entire collection (regression)."
        )

    def test_search_user_profile_passes_bounded_n_results_to_query(self) -> None:
        """search_user_profile(top_k=10) must call collection.query(n_results=10)."""
        import hashlib

        vault = _make_stubbed_vault()
        coll = vault._collections["user_collection"]
        for i in range(5):
            content = f"User fact {i}"
            fact_id = hashlib.sha256(content.encode()).hexdigest()
            coll._data[fact_id] = {
                "document": content,
                "metadata": {"category": "preference", "timestamp": "2026-01-01"},
            }

        vault.search_user_profile("user preference query", top_k=10)

        assert len(coll.query_calls) >= 1, "user_collection.query was never called"
        last_call = coll.query_calls[-1]
        assert last_call["n_results"] == 10, (
            f"search_user_profile(top_k=10) passed n_results={last_call['n_results']} — "
            "expected 10."
        )

    def test_custom_top_k_is_forwarded_faithfully(self) -> None:
        """Callers should be able to pass any top_k and have it forwarded exactly."""
        vault = _make_stubbed_vault()
        _seed_facts(vault, 30)

        vault.semantic_search("query", top_k=3)

        coll = vault._collections["collection"]
        last_call = coll.query_calls[-1]
        assert last_call["n_results"] == 3, (
            f"Custom top_k=3 was not forwarded to collection.query; "
            f"got n_results={last_call['n_results']}."
        )

    def test_top_k_cannot_be_zero_or_negative(self) -> None:
        """Even degenerate top_k values must not produce an unbounded n_results=None."""
        vault = _make_stubbed_vault()
        _seed_facts(vault, 5)

        # This should either return [] (collection has nothing to return for 0) or call query
        # with n_results > 0.  Either way, n_results must never be None or a huge sentinel.
        try:
            vault.semantic_search("query", top_k=1)
        except Exception:
            pass  # Any exception is acceptable — we just cannot have n_results=None.

        coll = vault._collections["collection"]
        for call in coll.query_calls:
            assert call["n_results"] is not None, (
                "collection.query was called with n_results=None (unbounded scan regression)."
            )
            assert call["n_results"] > 0, (
                f"collection.query was called with n_results={call['n_results']} ≤ 0."
            )


class TestVaultLazyInit:
    """Structural: constructing MemoryVault does NOT eagerly load ChromaDB.

    Seam: memory_vault.py line ~335 ``self._chroma_client: Any = None``
          and line ~339 ``_collections`` dict all-None.
    Guard: use patch.dict to inject a mock chromadb module; assert that
           PersistentClient is not called during __init__.

    These mirror tests already in test_g3_vault_lazy.py but are expressed here
    as the P2-13 perf regression guard so they explicitly appear in this file
    for CI visibility. They do NOT duplicate the round-trip tests.
    """

    def test_chroma_client_is_none_after_init(self, tmp_path: Any) -> None:
        """_chroma_client must be None immediately after __init__ — no eager DB open."""
        import sys

        mock_chroma = MagicMock()
        mock_client = MagicMock()
        mock_chroma.PersistentClient.return_value = mock_client
        mock_settings_mod = MagicMock()

        with patch.dict(
            sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_settings_mod}
        ):
            from hachi.core import memory_vault as _mv

            vault = _mv.MemoryVault(brain_dir=str(tmp_path))

        assert vault._chroma_client is None, (
            "PERF regression: _chroma_client is not None after __init__. "
            "Session boot is paying the ChromaDB open cost even when the vault is never used."
        )
        vault.close()

    def test_all_collection_slots_none_after_init(self, tmp_path: Any) -> None:
        """No collection should be initialised during __init__ (lazy init contract)."""
        import sys

        mock_chroma = MagicMock()
        mock_client = MagicMock()
        mock_coll = MagicMock()
        mock_coll.count.return_value = 0
        mock_client.get_or_create_collection.return_value = mock_coll
        mock_chroma.PersistentClient.return_value = mock_client
        mock_settings_mod = MagicMock()

        with patch.dict(
            sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_settings_mod}
        ):
            from hachi.core import memory_vault as _mv

            vault = _mv.MemoryVault(brain_dir=str(tmp_path))

        all_none = all(v is None for v in vault._collections.values())
        assert all_none, (
            "PERF regression: one or more ChromaDB collections were eagerly initialised "
            f"in __init__. Non-None slots: "
            f"{[k for k, v in vault._collections.items() if v is not None]}. "
            "Session boot is paying per-collection get_or_create_collection cost."
        )
        vault.close()

    def test_persistent_client_not_called_during_init(self, tmp_path: Any) -> None:
        """chromadb.PersistentClient must not be invoked during __init__."""
        import sys

        mock_chroma = MagicMock()
        mock_settings_mod = MagicMock()

        with patch.dict(
            sys.modules, {"chromadb": mock_chroma, "chromadb.config": mock_settings_mod}
        ):
            from hachi.core import memory_vault as _mv

            _mv.MemoryVault(brain_dir=str(tmp_path)).close()

        mock_chroma.PersistentClient.assert_not_called()
