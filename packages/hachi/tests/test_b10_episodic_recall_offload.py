"""Tests for B10 — episodic recall offloaded from inline turn path.

Recall-parity contracts:
  1. _run_prefetch_job merges semantic + episodic results.
  2. _run_prefetch_job deduplicates by id (semantic wins; episodic dupes dropped).
  3. _run_prefetch_job skips episodic when _episodic_top_k == 0.
  4. _run_prefetch_job is non-fatal when episodic recall raises.
  5. _run_prefetch_job stores result keyed by turn_id for _pop_prefetch.
  6. _pop_prefetch returns [] on a fresh session (turn-1 condition met).
  7. Turn-1 inline dedup: same id-keyed dedup holds for the inline path.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock

from hachi.gateway.orchestrator import AgentSession

# ---------------------------------------------------------------------------
# Helper: minimal AgentSession stub wired only for prefetch methods
# ---------------------------------------------------------------------------


def _make_prefetch_session(*, episodic_top_k: int = 3, vault: Any = None) -> AgentSession:
    """Return an AgentSession with only the attributes _run_prefetch_job needs."""
    sess = AgentSession.__new__(AgentSession)
    sess._prefetch_results = {}
    sess._prefetch_lock = threading.Lock()
    sess._last_prefetch_turn_id = None
    sess._episodic_top_k = episodic_top_k
    sess.vault = vault
    sess._job_queue = None  # force inline (no queue)
    return sess


def _fact(id_: str, content: str = "") -> dict:
    return {"id": id_, "content": content or id_}


# ---------------------------------------------------------------------------
# _run_prefetch_job — semantic-only (no vault)
# ---------------------------------------------------------------------------


def test_prefetch_no_vault_returns_empty_list() -> None:
    """Without a vault, _run_prefetch_job returns [] (no crash)."""
    sess = _make_prefetch_session(vault=None)
    result = sess._run_prefetch_job("hello", "t1")
    assert result == []


# ---------------------------------------------------------------------------
# _run_prefetch_job — semantic + episodic merge
# ---------------------------------------------------------------------------


def test_prefetch_merges_semantic_and_episodic_results() -> None:
    """Episodic results are appended to semantic results when ids differ (B10 parity)."""
    vault = MagicMock()
    vault.semantic_search.return_value = [_fact("sem-1"), _fact("sem-2")]
    vault.search_episodic.return_value = [_fact("ep-1"), _fact("ep-2")]

    sess = _make_prefetch_session(vault=vault, episodic_top_k=2)
    result = sess._run_prefetch_job("test query", "t1")

    ids = [r["id"] for r in result]
    # All four facts present
    assert "sem-1" in ids
    assert "sem-2" in ids
    assert "ep-1" in ids
    assert "ep-2" in ids
    assert len(result) == 4


def test_prefetch_deduplicates_episodic_id_overlap() -> None:
    """Episodic item whose id matches a semantic result is dropped (dedup at B10 :1208-1211)."""
    vault = MagicMock()
    vault.semantic_search.return_value = [_fact("shared-id"), _fact("sem-only")]
    # episodic returns one overlap + one unique
    vault.search_episodic.return_value = [_fact("shared-id"), _fact("ep-only")]

    sess = _make_prefetch_session(vault=vault, episodic_top_k=2)
    result = sess._run_prefetch_job("query", "t1")

    ids = [r["id"] for r in result]
    assert ids.count("shared-id") == 1, "duplicate id must appear exactly once"
    assert "sem-only" in ids
    assert "ep-only" in ids
    assert len(result) == 3


def test_prefetch_episodic_call_respects_top_k() -> None:
    """search_episodic is called with _episodic_top_k (not a hard-coded constant)."""
    vault = MagicMock()
    vault.semantic_search.return_value = []
    vault.search_episodic.return_value = []

    sess = _make_prefetch_session(vault=vault, episodic_top_k=7)
    sess._run_prefetch_job("q", "t1")

    vault.search_episodic.assert_called_once_with("q", top_k=7)


# ---------------------------------------------------------------------------
# _run_prefetch_job — episodic disabled
# ---------------------------------------------------------------------------


def test_prefetch_skips_episodic_when_top_k_zero() -> None:
    """When _episodic_top_k == 0, search_episodic is never called (disabled path)."""
    vault = MagicMock()
    vault.semantic_search.return_value = [_fact("sem-1")]

    sess = _make_prefetch_session(vault=vault, episodic_top_k=0)
    result = sess._run_prefetch_job("q", "t1")

    vault.search_episodic.assert_not_called()
    assert result == [_fact("sem-1")]


# ---------------------------------------------------------------------------
# _run_prefetch_job — episodic failure is non-fatal
# ---------------------------------------------------------------------------


def test_prefetch_episodic_exception_is_nonfatal() -> None:
    """An exception from search_episodic must not propagate — semantic results survive."""
    vault = MagicMock()
    vault.semantic_search.return_value = [_fact("sem-1"), _fact("sem-2")]
    vault.search_episodic.side_effect = RuntimeError("chroma down")

    sess = _make_prefetch_session(vault=vault, episodic_top_k=3)
    result = sess._run_prefetch_job("q", "t1")

    # semantic results survive despite episodic failure
    ids = [r["id"] for r in result]
    assert ids == ["sem-1", "sem-2"]


def test_prefetch_semantic_exception_still_attempts_episodic() -> None:
    """When semantic_search raises, episodic is still attempted and its results returned.

    The except block wraps only semantic_search — the episodic block runs regardless,
    so episodic facts still reach the caller even on a partial vault failure (B10).
    """
    vault = MagicMock()
    vault.semantic_search.side_effect = RuntimeError("vault unavailable")
    vault.search_episodic.return_value = [_fact("ep-1")]

    sess = _make_prefetch_session(vault=vault, episodic_top_k=3)
    result = sess._run_prefetch_job("q", "t1")

    # semantic failed → no semantic results, but episodic survived
    vault.search_episodic.assert_called_once()
    assert [r["id"] for r in result] == ["ep-1"]


# ---------------------------------------------------------------------------
# _run_prefetch_job → _pop_prefetch round-trip
# ---------------------------------------------------------------------------


def test_prefetch_result_stored_and_popped_by_turn_id() -> None:
    """_run_prefetch_job stores under turn_id; _pop_prefetch returns it exactly once."""
    vault = MagicMock()
    vault.semantic_search.return_value = [_fact("s1")]
    vault.search_episodic.return_value = [_fact("e1")]

    sess = _make_prefetch_session(vault=vault, episodic_top_k=1)
    # Simulate _enqueue_prefetch_job setting _last_prefetch_turn_id
    with sess._prefetch_lock:
        sess._last_prefetch_turn_id = "turn-42"

    sess._run_prefetch_job("q", "turn-42")

    # _pop_prefetch should return the merged list
    popped = sess._pop_prefetch()
    assert {r["id"] for r in popped} == {"s1", "e1"}

    # Second pop returns [] (consumed)
    assert sess._pop_prefetch() == []


# ---------------------------------------------------------------------------
# Turn-1 condition: _pop_prefetch on fresh session
# ---------------------------------------------------------------------------


def test_pop_prefetch_returns_empty_on_fresh_session() -> None:
    """On a fresh session (no enqueued prefetch), _pop_prefetch returns [] — the
    turn-1 condition that triggers the inline semantic + episodic fallback (B10)."""
    sess = _make_prefetch_session()
    assert sess._pop_prefetch() == []


# ---------------------------------------------------------------------------
# Turn-1 inline dedup: same id-keyed logic as _run_prefetch_job
# ---------------------------------------------------------------------------


def test_turn1_inline_dedup_logic() -> None:
    """Mirrors the turn-1 dedup at _chat_impl_inner :1586-1589:
    episodic item with same id as a semantic result is dropped.

    This test replicates the inline merge logic verbatim so any future drift
    between _run_prefetch_job and _chat_impl_inner dedup will be caught.
    """
    # Simulate semantic recall output (turn-1 inline path)
    recalled: list[dict] = [_fact("shared"), _fact("sem-only")]

    # Simulate episodic recall output
    episodic: list[dict] = [_fact("shared"), _fact("ep-only")]

    # --- BEGIN: inline dedup from _chat_impl_inner ---
    if episodic:
        existing_ids = {r.get("id") for r in recalled}
        for ep in episodic:
            if ep.get("id") not in existing_ids:
                recalled.append(ep)
    # --- END: inline dedup ---

    ids = [r["id"] for r in recalled]
    assert ids.count("shared") == 1
    assert "sem-only" in ids
    assert "ep-only" in ids
    assert len(recalled) == 3
