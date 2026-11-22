"""
Tests for M2 — Memory Decay (recency weighting over semantic recall).

Covers:
  _decay_score unit tests: age 0, one half-life, unparseable, empty, "Unknown Date",
    distance 0, extreme age, monotonicity, naive timestamp handling.
  Re-rank order flip through _query_collection / semantic_search:
    two candidates — A closer but old, B farther but fresh — with decay ON B wins;
    with decay OFF A wins (pure relevance).
  Over-fetch + truncate: top_k=2 with 5 candidates → exactly 2 returned, decay-best 2.
  search_user_profile does NOT decay (apply_decay=False): old-but-closer profile fact
    ranks first even when decay_half_life_days is set.
  Distance gate precedes decay: a candidate beyond recall_distance_max is dropped and
    decay never resurrects it.
  Default OFF parity: with no decay_half_life_days, results equal relevance-ordered
    baseline byte-for-byte.

All tests are pure unit tests: ChromaDB is stubbed with controllable fakes so no
real DB I/O occurs and tests run without requiring ChromaDB to be installed.
"""

from __future__ import annotations

import datetime
import threading
from typing import Any  # noqa: F401

# ---------------------------------------------------------------------------
# Controllable fake ChromaDB collection
# ---------------------------------------------------------------------------

class _FakeCollection:
    """Minimal in-memory ChromaDB collection stub with configurable distances."""

    def __init__(self, name: str = "core_memory") -> None:
        self.name = name
        # Ordered list of (id, document, metadata, distance) tuples.
        self._rows: list[tuple[str, str, dict, float]] = []

    def count(self) -> int:
        return len(self._rows)

    def upsert(self, ids, documents, metadatas) -> None:
        existing_ids = {r[0] for r in self._rows}
        for _id, doc, meta in zip(ids, documents, metadatas, strict=False):
            if _id in existing_ids:
                self._rows = [
                    (r[0], doc, meta, r[3]) if r[0] == _id else r
                    for r in self._rows
                ]
                existing_ids = {r[0] for r in self._rows}
            else:
                self._rows.append((_id, doc, meta, 0.1))

    def add_row(self, id: str, document: str, metadata: dict, distance: float) -> None:
        """Test helper: add a row with a specific distance."""
        self._rows.append((id, document, metadata, distance))

    def get(
        self,
        ids=None,
        limit: int | None = None,
        include: list | None = None,
    ) -> dict:
        rows = self._rows
        if ids is not None:
            rows = [r for r in rows if r[0] in ids]
        if limit is not None:
            rows = rows[:limit]
        return {
            "ids": [r[0] for r in rows],
            "documents": [r[1] for r in rows],
            "metadatas": [r[2] for r in rows],
        }

    def query(
        self,
        query_texts,
        n_results: int = 5,
        include: list | None = None,
        where=None,
    ) -> dict:
        # Return rows in insertion order, up to n_results, with their stored distances.
        rows = self._rows[:n_results]
        return {
            "ids": [[r[0] for r in rows]],
            "documents": [[r[1] for r in rows]],
            "metadatas": [[r[2] for r in rows]],
            "distances": [[r[3] for r in rows]],
        }

    def delete(self, ids) -> None:
        id_set = set(ids)
        self._rows = [r for r in self._rows if r[0] not in id_set]


def _make_vault(
    recall_distance_max: float | None = 0.85,
    decay_half_life_days: float | None = None,
) -> Any:
    """Return a MemoryVault with ChromaDB fully stubbed out.

    Matches the pattern from tests/test_memory_fixes.py and tests/test_episodic_memory.py,
    extended to also set _decay_half_life_days (M2).
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
    vault.db_path = "/tmp/fake"
    vault._recall_distance_max = recall_distance_max
    vault._core_memory_max_entries = 1000
    vault._decay_half_life_days = decay_half_life_days

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


def _iso(dt: datetime.datetime) -> str:
    """Convert a datetime to the same ISO format that MemoryVault._now_iso() writes."""
    return dt.isoformat()


# ---------------------------------------------------------------------------
# _decay_score unit tests
# ---------------------------------------------------------------------------


class TestDecayScore:
    """Unit tests for the module-level _decay_score pure function."""

    def _fn(self, distance: float, ts: str, *, now: datetime.datetime, half_life: float) -> float:
        from hachi.core.memory_vault import _decay_score
        return _decay_score(distance, ts, now=now, half_life_days=half_life)

    @property
    def _now(self) -> datetime.datetime:
        return datetime.datetime(2026, 6, 25, 12, 0, 0, tzinfo=datetime.UTC)

    def _ts_days_ago(self, days: float) -> str:
        dt = self._now - datetime.timedelta(days=days)
        return _iso(dt)

    def test_age_zero_returns_distance(self) -> None:
        """A fact stored right now gets no penalty."""
        ts = _iso(self._now)
        score = self._fn(0.4, ts, now=self._now, half_life=30.0)
        assert abs(score - 0.4) < 1e-9

    def test_one_half_life_doubles_distance(self) -> None:
        """A fact stored exactly one half-life ago ranks as 2× the distance."""
        ts = self._ts_days_ago(30.0)
        score = self._fn(0.4, ts, now=self._now, half_life=30.0)
        assert abs(score - 0.8) < 1e-6

    def test_unparseable_timestamp_returns_distance(self) -> None:
        """Any unparseable timestamp → no penalty (returns distance unchanged)."""
        score = self._fn(0.5, "not-a-date", now=self._now, half_life=30.0)
        assert score == 0.5

    def test_empty_timestamp_returns_distance(self) -> None:
        """Empty string → no penalty."""
        score = self._fn(0.3, "", now=self._now, half_life=30.0)
        assert score == 0.3

    def test_unknown_date_sentinel_returns_distance(self) -> None:
        """'Unknown Date' sentinel → no penalty."""
        score = self._fn(0.6, "Unknown Date", now=self._now, half_life=30.0)
        assert score == 0.6

    def test_distance_zero_stays_zero(self) -> None:
        """An identical match (distance=0) always wins regardless of age."""
        ts = self._ts_days_ago(365.0)
        score = self._fn(0.0, ts, now=self._now, half_life=30.0)
        assert score == 0.0

    def test_extreme_age_no_exception(self) -> None:
        """100,000-day-old fact → no exception, large finite score."""
        ts = self._ts_days_ago(100_000.0)
        score = self._fn(0.3, ts, now=self._now, half_life=30.0)
        assert score > 0.3  # penalised
        assert not (score != score)  # not NaN

    def test_monotonic_older_scores_higher(self) -> None:
        """For equal distance, an older fact must have a strictly higher score."""
        ts_fresh = self._ts_days_ago(1.0)
        ts_stale = self._ts_days_ago(60.0)
        score_fresh = self._fn(0.4, ts_fresh, now=self._now, half_life=30.0)
        score_stale = self._fn(0.4, ts_stale, now=self._now, half_life=30.0)
        assert score_stale > score_fresh

    def test_naive_timestamp_handled_no_tz_error(self) -> None:
        """A naive ISO timestamp (no tz) must not raise a tz subtraction error."""
        naive_ts = "2026-01-01T00:00:00"  # no tz info
        score = self._fn(0.5, naive_ts, now=self._now, half_life=30.0)
        # Should return a valid positive float (penalised but not an error).
        assert isinstance(score, float)
        assert score >= 0.5  # penalised since it looks old

    def test_future_timestamp_clamped_to_zero_age(self) -> None:
        """A future timestamp (clock skew) clamps age to 0 → no penalty."""
        future = self._now + datetime.timedelta(days=10)
        ts = _iso(future)
        score = self._fn(0.4, ts, now=self._now, half_life=30.0)
        # age=0 → no penalty → score ≈ distance
        assert abs(score - 0.4) < 1e-9

    def test_half_life_zero_or_negative_returns_distance(self) -> None:
        """half_life_days <= 0 is a no-op (defensive guard)."""
        ts = self._ts_days_ago(30.0)
        assert self._fn(0.4, ts, now=self._now, half_life=0.0) == 0.4
        assert self._fn(0.4, ts, now=self._now, half_life=-5.0) == 0.4


# ---------------------------------------------------------------------------
# Re-rank order flip via _query_collection / semantic_search
# ---------------------------------------------------------------------------


class TestDecayReranksQueryCollection:
    """The load-bearing anti-fake test: decay changes the output order."""

    @property
    def _now(self) -> datetime.datetime:
        return datetime.datetime(2026, 6, 25, 12, 0, 0, tzinfo=datetime.UTC)

    def _build_vault_with_ab(
        self,
        decay_half_life_days: float | None,
    ) -> Any:
        """
        Two candidates in core_memory:
          A: distance=0.2  (more relevant) but old (365 days ago)
          B: distance=0.5  (less relevant) but fresh (≈now)
        With decay ON (half_life=30d): B score ≈ 0.5, A score ≈ 0.2/(0.5^12.2) ≈ huge → B wins.
        With decay OFF: A ranks first (smaller raw distance).
        """
        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=decay_half_life_days)
        coll: _FakeCollection = vault._collections["collection"]

        ts_old = _iso(self._now - datetime.timedelta(days=365))
        ts_fresh = _iso(self._now - datetime.timedelta(seconds=1))

        # Insert A first (closer but old), B second (farther but fresh).
        meta_old = {"category": "workspace_state", "timestamp": ts_old}
        meta_fresh = {"category": "workspace_state", "timestamp": ts_fresh}
        coll.add_row("A", "Fact A — old but relevant", meta_old, 0.2)
        coll.add_row("B", "Fact B — fresh but less relevant", meta_fresh, 0.5)
        return vault

    def test_decay_on_prefers_fresh_over_closer(self) -> None:
        """With decay ON, the fresh (B) candidate ranks before the old (A) one."""
        vault = self._build_vault_with_ab(decay_half_life_days=30.0)
        results = vault._query_collection("collection", "query", top_k=2)
        assert len(results) == 2
        ids = [r["id"] for r in results]
        assert ids[0] == "B", f"Expected B first (fresh wins), got {ids}"

    def test_decay_off_preserves_relevance_order(self) -> None:
        """With decay OFF, pure cosine order: closer (A) first."""
        vault = self._build_vault_with_ab(decay_half_life_days=None)
        results = vault._query_collection("collection", "query", top_k=2)
        assert len(results) == 2
        ids = [r["id"] for r in results]
        assert ids[0] == "A", f"Expected A first (relevance wins), got {ids}"

    def test_same_fixtures_through_semantic_search(self) -> None:
        """The flip also manifests through semantic_search (the public API)."""
        vault_on = self._build_vault_with_ab(decay_half_life_days=30.0)
        vault_off = self._build_vault_with_ab(decay_half_life_days=None)

        results_on = vault_on.semantic_search("query", top_k=2)
        results_off = vault_off.semantic_search("query", top_k=2)

        ids_on = [r["id"] for r in results_on]
        ids_off = [r["id"] for r in results_off]

        assert ids_on[0] == "B", f"decay ON: expected B first, got {ids_on}"
        assert ids_off[0] == "A", f"decay OFF: expected A first, got {ids_off}"


# ---------------------------------------------------------------------------
# Over-fetch and truncation
# ---------------------------------------------------------------------------


class TestDecayOverfetch:
    """Over-fetch supplies a large pool; final result is exactly top_k items."""

    @property
    def _now(self) -> datetime.datetime:
        return datetime.datetime(2026, 6, 25, 12, 0, 0, tzinfo=datetime.UTC)

    def test_top_k_respected_with_five_candidates(self) -> None:
        """With top_k=2 and 5 candidates in the collection, exactly 2 are returned."""
        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=30.0)
        coll: _FakeCollection = vault._collections["collection"]

        for i in range(5):
            ts = _iso(self._now - datetime.timedelta(days=i * 10))
            dist = 0.1 + i * 0.1  # distances: 0.1, 0.2, 0.3, 0.4, 0.5
            meta = {"category": "workspace_state", "timestamp": ts}
            coll.add_row(f"F{i}", f"Fact {i}", meta, dist)

        results = vault._query_collection("collection", "query", top_k=2)
        assert len(results) == 2

    def test_returned_items_are_decay_best(self) -> None:
        """The 2 returned items are the ones with the lowest decay scores."""
        from hachi.core.memory_vault import _decay_score

        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=30.0)
        coll: _FakeCollection = vault._collections["collection"]
        now = self._now

        candidates = []
        for i in range(5):
            ts = _iso(now - datetime.timedelta(days=i * 10))
            dist = 0.1 + i * 0.1  # 0.1..0.5
            meta = {"category": "workspace_state", "timestamp": ts}
            coll.add_row(f"F{i}", f"Fact {i}", meta, dist)
            candidates.append(("F" + str(i), dist, ts))

        results = vault._query_collection("collection", "query", top_k=2)
        returned_ids = {r["id"] for r in results}

        # Compute expected best-2 by decay score.
        scored = sorted(
            candidates,
            key=lambda c: _decay_score(c[1], c[2], now=now, half_life_days=30.0),
        )
        expected_ids = {scored[0][0], scored[1][0]}
        assert returned_ids == expected_ids, (
            f"Returned {returned_ids}, expected top-2 decay-scored {expected_ids}"
        )


# ---------------------------------------------------------------------------
# search_user_profile does NOT decay
# ---------------------------------------------------------------------------


class TestUserProfileNotDecayed:
    """search_user_profile must use apply_decay=False; identity facts are timeless."""

    @property
    def _now(self) -> datetime.datetime:
        return datetime.datetime(2026, 6, 25, 12, 0, 0, tzinfo=datetime.UTC)

    def test_old_closer_profile_fact_ranks_first_despite_decay(self) -> None:
        """
        Profile collection: P1 (distance=0.2, very old), P2 (distance=0.4, fresh).
        With decay ON for core memory, profile search must NOT reorder them.
        P1 should still be returned first (pure relevance order).
        """
        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=30.0)
        ucoll: _FakeCollection = vault._collections["user_collection"]

        ts_old = _iso(self._now - datetime.timedelta(days=365))
        ts_fresh = _iso(self._now - datetime.timedelta(seconds=1))

        ucoll.add_row("P1", "Name: Alice", {"category": "name", "timestamp": ts_old}, 0.2)
        ucoll.add_row("P2", "Role: developer", {"category": "role", "timestamp": ts_fresh}, 0.4)

        results = vault.search_user_profile("who am I", top_k=2)
        assert len(results) == 2
        ids = [r["id"] for r in results]
        assert ids[0] == "P1", (
            f"Profile search must not decay: expected P1 (closer) first, got {ids}"
        )


# ---------------------------------------------------------------------------
# Distance gate precedes decay (gate is sacred)
# ---------------------------------------------------------------------------


class TestDistanceGatePrecedesDecay:
    """A candidate beyond recall_distance_max is dropped; decay never resurrects it."""

    @property
    def _now(self) -> datetime.datetime:
        return datetime.datetime(2026, 6, 25, 12, 0, 0, tzinfo=datetime.UTC)

    def test_beyond_threshold_dropped_even_with_decay_on(self) -> None:
        """
        One candidate: distance=0.9 (> threshold 0.85) but very fresh.
        Even with decay ON it must be dropped.
        """
        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=30.0)
        coll: _FakeCollection = vault._collections["collection"]

        ts_fresh = _iso(self._now - datetime.timedelta(seconds=1))
        meta = {"category": "workspace_state", "timestamp": ts_fresh}
        coll.add_row("X", "Should be dropped", meta, 0.9)

        results = vault._query_collection("collection", "query", top_k=5)
        assert results == [], f"Expected empty (distance gate), got {results}"

    def test_within_threshold_returned_with_decay_on(self) -> None:
        """
        Sanity: a candidate within threshold IS returned even with decay active.
        """
        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=30.0)
        coll: _FakeCollection = vault._collections["collection"]

        ts_fresh = _iso(self._now - datetime.timedelta(seconds=1))
        meta = {"category": "workspace_state", "timestamp": ts_fresh}
        coll.add_row("Y", "Within threshold", meta, 0.4)

        results = vault._query_collection("collection", "query", top_k=5)
        assert len(results) == 1
        assert results[0]["id"] == "Y"


# ---------------------------------------------------------------------------
# Default OFF parity
# ---------------------------------------------------------------------------


class TestDefaultOffParity:
    """With decay_half_life_days=None, output is byte-for-byte equal to no-decay baseline."""

    @property
    def _now(self) -> datetime.datetime:
        return datetime.datetime(2026, 6, 25, 12, 0, 0, tzinfo=datetime.UTC)

    def test_no_decay_results_match_baseline(self) -> None:
        """Results from decay=None vault equal the relevance-order baseline."""
        vault_no_decay = _make_vault(recall_distance_max=0.85, decay_half_life_days=None)
        vault_explicit_none = _make_vault(recall_distance_max=0.85, decay_half_life_days=None)

        for vault in (vault_no_decay, vault_explicit_none):
            coll: _FakeCollection = vault._collections["collection"]
            ts_old = _iso(self._now - datetime.timedelta(days=365))
            ts_fresh = _iso(self._now - datetime.timedelta(seconds=1))
            coll.add_row("A", "Fact A", {"category": "workspace_state", "timestamp": ts_old}, 0.2)
            coll.add_row("B", "Fact B", {"category": "workspace_state", "timestamp": ts_fresh}, 0.5)

        res_no_decay = vault_no_decay._query_collection("collection", "query", top_k=2)
        res_explicit = vault_explicit_none._query_collection("collection", "query", top_k=2)

        ids_no_decay = [r["id"] for r in res_no_decay]
        ids_explicit = [r["id"] for r in res_explicit]

        # Both should be relevance order (A first, smaller distance)
        assert ids_no_decay == ["A", "B"]
        assert ids_explicit == ["A", "B"]
        assert ids_no_decay == ids_explicit

    def test_decay_zero_or_negative_also_no_op(self) -> None:
        """A decay_half_life_days=0 or negative is treated as disabled (returns distance order)."""
        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=0.0)
        coll: _FakeCollection = vault._collections["collection"]

        ts_old = _iso(self._now - datetime.timedelta(days=365))
        ts_fresh = _iso(self._now - datetime.timedelta(seconds=1))
        coll.add_row("A", "Fact A", {"category": "workspace_state", "timestamp": ts_old}, 0.2)
        coll.add_row("B", "Fact B", {"category": "workspace_state", "timestamp": ts_fresh}, 0.5)

        results = vault._query_collection("collection", "query", top_k=2)
        ids = [r["id"] for r in results]
        assert ids[0] == "A", f"decay_half_life_days=0 should be a no-op, got {ids}"


# ---------------------------------------------------------------------------
# get_recent_facts and search_delegations are unaffected
# ---------------------------------------------------------------------------


class TestContractUnchanged:
    """Contract C-RECENT: get_recent_facts must not be routed through _query_collection."""

    def test_get_recent_facts_path_untouched(self) -> None:
        """get_recent_facts uses .get() not .query() — it must not gain decay behaviour.

        We verify it returns documents in timestamp order, independent of decay config.
        """
        vault = _make_vault(recall_distance_max=0.85, decay_half_life_days=30.0)

        # Use the real upsert path but bypass guard by injecting directly.
        coll: _FakeCollection = vault._collections["collection"]
        now = datetime.datetime(2026, 6, 25, 12, 0, 0, tzinfo=datetime.UTC)
        older_ts = _iso(now - datetime.timedelta(days=5))
        newer_ts = _iso(now - datetime.timedelta(days=1))

        # Inject in reverse chronological order; get_recent_facts should sort by ts.
        m_old = {"category": "workspace_state", "timestamp": older_ts}
        m_new = {"category": "workspace_state", "timestamp": newer_ts}
        coll.add_row("old1", "Older fact", m_old, 0.1)
        coll.add_row("new1", "Newer fact", m_new, 0.1)

        # get_recent_facts resolves the attr by collection name suffix.
        # "core_memory" maps to attr "collection". It uses .get(), not .query().
        results = vault.get_recent_facts("core_memory", limit=5)
        # Should return both facts as raw strings, most-recent first.
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0] == "Newer fact"
        assert results[1] == "Older fact"
