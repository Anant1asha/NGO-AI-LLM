"""
Tests for UserProfileStore, CorrectionLog, and the core_save_user_profile_structured tool.

Covers:
  T1 — set() + get() round-trips a fact under the correct P1-7 category.
  T2 — get() groups all four categories correctly (multi-fact, mixed categories).
  T3 — correct() records a CorrectionLog entry AND supersedes the old value
       (assert: new value present, correction logged, old value not silently gone).
  T4 — CorrectionLog is append-only and survives a fresh store instance (restart).
  T5 — export() includes profile + corrections.
  T6 — core_save_user_profile_structured tool calls through to the store.
  T7 — Legacy vault categories (pre-P1-7) are remapped on get().
  T8 — set() raises ValueError for invalid category.
  T9 — correct() with unknown old_value still logs the correction and writes the new fact.

All tests use a temp vault backed by an in-memory ChromaDB stub + a tmp_path SQLite
CorrectionLog so no real ChromaDB or sessions.db is touched.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from hachi.core.user_profile import (
    PROFILE_CATEGORIES,
    CorrectionLog,
    UserProfileStore,
    _resolve_read_category,
)

# ---------------------------------------------------------------------------
# Shared fake ChromaDB collection
# ---------------------------------------------------------------------------


class _FakeCollection:
    """Minimal in-memory ChromaDB collection stub compatible with MemoryVault internals."""

    def __init__(self, name: str = "user_profile") -> None:
        self.name = name
        # id → {document: str, metadata: dict}
        self._data: dict[str, dict[str, Any]] = {}

    def count(self) -> int:
        return len(self._data)

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        for doc_id, doc, meta in zip(ids, documents, metadatas, strict=False):
            self._data[doc_id] = {"document": doc, "metadata": meta}

    def get(
        self,
        ids: list[str] | None = None,
        limit: int | None = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        if ids is not None:
            items = [(k, v) for k, v in self._data.items() if k in ids]
        else:
            items = list(self._data.items())
        if limit is not None:
            items = items[:limit]
        return {
            "ids": [k for k, _ in items],
            "documents": [v["document"] for _, v in items],
            "metadatas": [v["metadata"] for _, v in items],
        }

    def delete(self, ids: list[str]) -> None:
        for doc_id in ids:
            self._data.pop(doc_id, None)

    def query(
        self,
        query_texts: list[str],
        n_results: int = 5,
        include: list[str] | None = None,
        where: dict | None = None,
    ) -> dict[str, Any]:
        items = list(self._data.items())[:n_results]
        distances = [0.1 * (i + 1) for i in range(len(items))]
        return {
            "ids": [[k for k, _ in items]],
            "documents": [[v["document"] for _, v in items]],
            "metadatas": [[v["metadata"] for _, v in items]],
            "distances": [distances],
        }


# ---------------------------------------------------------------------------
# Minimal fake MemoryVault that exposes only what UserProfileStore uses.
# ---------------------------------------------------------------------------


class _FakeVault:
    """Thin MemoryVault stub with just enough surface for UserProfileStore."""

    USER_PROFILE_MAX_ENTRIES = 25

    def __init__(self) -> None:
        self._ucoll = _FakeCollection("user_profile")
        self._vault_lock = threading.RLock()
        self._closed = False
        self._collections: dict[str, Any] = {
            "user_collection": self._ucoll,
        }

    def _assert_open(self) -> None:
        if self._closed:
            raise RuntimeError("MemoryVault is closed")

    def _get_collection(self, attr: str) -> _FakeCollection:
        return self._collections[attr]

    @staticmethod
    def _generate_id(content: str) -> str:
        import hashlib

        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _now_iso() -> str:
        import datetime

        return datetime.datetime.now(datetime.UTC).isoformat()

    def _guarded_write(self, collection_attr: str, content: str, category: str) -> str:
        """Minimal guarded write — no MemoryGuard in tests."""
        fact_id = self._generate_id(content)
        with self._vault_lock:
            self._assert_open()
            coll = self._get_collection(collection_attr)
            coll.upsert(
                ids=[fact_id],
                documents=[content],
                metadatas=[
                    {
                        "category": category,
                        "timestamp": self._now_iso(),
                        "trust_state": "accepted",
                        "wrapped_untrusted": "false",
                        "quarantine_ref": "",
                    }
                ],
            )
        return fact_id

    def delete_user_fact(self, fact_id: str) -> bool:
        try:
            with self._vault_lock:
                self._assert_open()
                self._get_collection("user_collection").delete(ids=[fact_id])
            return True
        except Exception:
            return False

    def get_profile_stats(self) -> dict[str, Any]:
        try:
            with self._vault_lock:
                count = self._get_collection("user_collection").count()
        except Exception:
            count = 0
        return {
            "entries": count,
            "max_entries": self.USER_PROFILE_MAX_ENTRIES,
            "remaining": max(0, self.USER_PROFILE_MAX_ENTRIES - count),
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_vault() -> _FakeVault:
    return _FakeVault()


@pytest.fixture
def correction_log(tmp_path: Path) -> CorrectionLog:
    db_path = tmp_path / "test_corrections.db"
    log = CorrectionLog(db_path=db_path)
    yield log
    log.close()


@pytest.fixture
def store(fake_vault: _FakeVault, correction_log: CorrectionLog) -> UserProfileStore:
    return UserProfileStore(vault=fake_vault, correction_log=correction_log)


# ---------------------------------------------------------------------------
# T1 — set() + get() round-trips a fact under the correct category
# ---------------------------------------------------------------------------


def test_set_and_get_round_trips_fact(store: UserProfileStore) -> None:
    """set() stores a fact; get() returns it grouped under the correct P1-7 category."""
    fact_id = store.set("preferences", "User prefers dark mode")
    assert fact_id and not fact_id.startswith("BLOCKED:"), f"unexpected result: {fact_id}"

    profile = store.get()
    prefs = profile["preferences"]
    assert any(e["content"] == "User prefers dark mode" for e in prefs), (
        f"fact not found in preferences: {prefs}"
    )


def test_set_identity_category(store: UserProfileStore) -> None:
    store.set("identity", "User's name is Aarav")
    profile = store.get()
    identity = profile["identity"]
    assert any(e["content"] == "User's name is Aarav" for e in identity)


def test_set_routines_category(store: UserProfileStore) -> None:
    store.set("routines", "User has a daily standup at 9 am")
    profile = store.get()
    routines = profile["routines"]
    assert any(e["content"] == "User has a daily standup at 9 am" for e in routines)


def test_set_knowledge_category(store: UserProfileStore) -> None:
    store.set("knowledge", "User is an expert in distributed systems")
    profile = store.get()
    knowledge = profile["knowledge"]
    assert any(e["content"] == "User is an expert in distributed systems" for e in knowledge)


# ---------------------------------------------------------------------------
# T2 — get() groups all four categories correctly
# ---------------------------------------------------------------------------


def test_get_groups_all_four_categories(store: UserProfileStore) -> None:
    """All four P1-7 categories are present as keys; facts land in the right bucket."""
    store.set("identity", "User's role is Staff Engineer")
    store.set("preferences", "User prefers Python over Java")
    store.set("routines", "User reviews PRs every Friday afternoon")
    store.set("knowledge", "User knows Kubernetes internals well")

    profile = store.get()

    # All four keys must be present even if empty.
    assert set(profile.keys()) == PROFILE_CATEGORIES

    assert any(e["content"] == "User's role is Staff Engineer" for e in profile["identity"])
    assert any(e["content"] == "User prefers Python over Java" for e in profile["preferences"])
    assert any(
        e["content"] == "User reviews PRs every Friday afternoon" for e in profile["routines"]
    )
    assert any(e["content"] == "User knows Kubernetes internals well" for e in profile["knowledge"])


def test_get_returns_empty_lists_for_unused_categories(store: UserProfileStore) -> None:
    """get() returns empty lists for all four categories when the vault is empty."""
    profile = store.get()
    assert set(profile.keys()) == PROFILE_CATEGORIES
    for cat, entries in profile.items():
        assert entries == [], f"expected empty list for {cat}, got {entries}"


# ---------------------------------------------------------------------------
# T3 — correct() records CorrectionLog AND supersedes old value
# ---------------------------------------------------------------------------


def test_correct_records_log_and_supersedes_old(store: UserProfileStore, tmp_path: Path) -> None:
    """correct() writes a CorrectionLog entry AND replaces the old fact in the vault."""
    # Write the original fact.
    store.set("preferences", "User prefers light mode")
    # Now correct it.
    result = store.correct(
        "User prefers light mode", "User prefers dark mode", reason="changed mind"
    )

    # (a) Correction was logged.
    assert result["logged"] is True
    assert result["correction_id"], "expected a non-empty correction_id"

    # (b) New value is present in the vault.
    profile = store.get()
    all_contents = [e["content"] for e in profile["preferences"]]
    assert "User prefers dark mode" in all_contents, f"new fact missing: {all_contents}"

    # (c) Old value is NOT silently gone — it is preserved in the CorrectionLog.
    log = store._log.get_all()
    assert any(entry["old_value"] == "User prefers light mode" for entry in log), (
        f"old value not in CorrectionLog: {log}"
    )

    # (d) Old value is removed from the live vault (superseded).
    assert "User prefers light mode" not in all_contents, (
        f"old fact still live in vault: {all_contents}"
    )


def test_correct_by_id(store: UserProfileStore) -> None:
    """correct() can locate the old fact by SHA-256 id returned from get()."""
    store.set("identity", "User's name is Bob")
    profile = store.get()
    old_id = profile["identity"][0]["id"]

    result = store.correct(old_id, "User's name is Robert", reason="full name preferred")
    assert result["logged"] is True
    assert result["old_fact_id"] == old_id

    updated = store.get()
    all_contents = [e["content"] for e in updated["identity"]]
    assert "User's name is Robert" in all_contents
    assert "User's name is Bob" not in all_contents


# ---------------------------------------------------------------------------
# T4 — CorrectionLog is append-only and survives restart
# ---------------------------------------------------------------------------


def test_correction_log_append_only_and_survives_restart(tmp_path: Path) -> None:
    """CorrectionLog entries persist across CorrectionLog instances (simulate restart)."""
    db_path = tmp_path / "corrections.db"

    # Write entries using the first instance.
    log1 = CorrectionLog(db_path=db_path)
    id1 = log1.append(
        category="preferences",
        old_value="old fact A",
        new_value="new fact A",
        reason="test reason 1",
    )
    id2 = log1.append(
        category="identity",
        old_value="old fact B",
        new_value="new fact B",
        reason="test reason 2",
    )
    log1.close()

    # Open a second instance (simulate restart).
    log2 = CorrectionLog(db_path=db_path)
    all_entries = log2.get_all()
    log2.close()

    ids_in_log = {e["id"] for e in all_entries}
    assert id1 in ids_in_log, f"entry {id1} missing after restart"
    assert id2 in ids_in_log, f"entry {id2} missing after restart"

    # Verify raw DB has no UPDATE/DELETE on our rows (append-only contract).
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT id, old_value FROM profile_corrections ORDER BY ts").fetchall()
    conn.close()
    raw_ids = [r[0] for r in rows]
    assert id1 in raw_ids
    assert id2 in raw_ids
    assert len(raw_ids) == 2, f"expected exactly 2 rows, got {raw_ids}"


def test_correction_log_multiple_appends_all_survive(tmp_path: Path) -> None:
    """Multiple corrections accumulate correctly; no row is lost or overwritten."""
    db_path = tmp_path / "corrections.db"
    log = CorrectionLog(db_path=db_path)
    ids = []
    for i in range(5):
        entry_id = log.append(
            category="knowledge",
            old_value=f"old {i}",
            new_value=f"new {i}",
            reason=f"reason {i}",
        )
        ids.append(entry_id)
    entries = log.get_all()
    log.close()

    found_ids = {e["id"] for e in entries}
    for expected_id in ids:
        assert expected_id in found_ids, f"{expected_id} missing from log"
    assert len(entries) == 5


# ---------------------------------------------------------------------------
# T5 — export() includes profile + corrections
# ---------------------------------------------------------------------------


def test_export_includes_profile_and_corrections(store: UserProfileStore) -> None:
    """export() returns both the structured profile and the full correction history."""
    store.set("identity", "User's name is Alice")
    store.correct("User's name is Alice", "User's name is Alicia", reason="legal name update")

    exported = store.export()

    assert "profile" in exported
    assert "corrections" in exported
    assert "stats" in exported

    # Profile should have the updated name.
    identity_facts = exported["profile"]["identity"]
    all_contents = [e["content"] for e in identity_facts]
    assert "User's name is Alicia" in all_contents, f"updated fact missing: {all_contents}"

    # Corrections should contain at least one entry.
    assert len(exported["corrections"]) >= 1
    correction = exported["corrections"][0]
    assert "old_value" in correction
    assert "new_value" in correction
    assert correction["old_value"] == "User's name is Alice"

    # Stats should be a dict with at least entries/max_entries.
    assert "entries" in exported["stats"]
    assert "max_entries" in exported["stats"]


# ---------------------------------------------------------------------------
# T6 — core_save_user_profile_structured tool calls through to the store
# ---------------------------------------------------------------------------


def test_tool_calls_through_to_store(fake_vault: _FakeVault, tmp_path: Path) -> None:
    """core_save_user_profile_structured calls UserProfileStore.set and stores the fact."""
    from hachi.core.loop import ToolRegistry
    from hachi.core.user_profile import CorrectionLog, UserProfileStore
    from hachi.tools.memory_tools import register_memory_tools

    log = CorrectionLog(db_path=tmp_path / "test.db")
    ps = UserProfileStore(vault=fake_vault, correction_log=log)
    registry = ToolRegistry()
    register_memory_tools(registry, fake_vault, profile_store=ps)

    assert "core_save_user_profile_structured" in registry._tools, "tool not registered"

    tool_fn = registry._tools["core_save_user_profile_structured"]
    result = tool_fn(category="preferences", value="User prefers vim keybindings")

    # Tool should report success.
    assert "saved" in result.lower() or "preferences" in result.lower(), (
        f"unexpected result: {result}"
    )

    # Verify the fact actually landed in the vault.
    profile = ps.get()
    prefs = profile["preferences"]
    assert any(e["content"] == "User prefers vim keybindings" for e in prefs), (
        f"fact not found in vault: {prefs}"
    )
    log.close()


def test_tool_with_invalid_category_returns_error(fake_vault: _FakeVault, tmp_path: Path) -> None:
    """core_save_user_profile_structured returns an error string for invalid categories."""
    from hachi.core.loop import ToolRegistry
    from hachi.core.user_profile import CorrectionLog, UserProfileStore
    from hachi.tools.memory_tools import register_memory_tools

    log = CorrectionLog(db_path=tmp_path / "test.db")
    ps = UserProfileStore(vault=fake_vault, correction_log=log)
    registry = ToolRegistry()
    register_memory_tools(registry, fake_vault, profile_store=ps)

    tool_fn = registry._tools["core_save_user_profile_structured"]
    result = tool_fn(category="invalid_cat", value="some fact")

    assert "invalid" in result.lower() or "category" in result.lower(), (
        f"expected validation error, got: {result}"
    )
    log.close()


def test_tool_auto_constructs_store_when_not_passed(fake_vault: _FakeVault) -> None:
    """register_memory_tools builds a UserProfileStore automatically when profile_store=None."""
    from hachi.core.loop import ToolRegistry
    from hachi.tools.memory_tools import register_memory_tools

    registry = ToolRegistry()
    register_memory_tools(registry, fake_vault)  # no profile_store

    assert "core_save_user_profile_structured" in registry._tools, (
        "tool must be present even when profile_store is not explicitly passed"
    )


# ---------------------------------------------------------------------------
# T7 — Legacy vault categories are remapped on get()
# ---------------------------------------------------------------------------


def test_legacy_vault_categories_remapped_on_get(fake_vault: _FakeVault, tmp_path: Path) -> None:
    """Entries written with old vault categories (name/role/preference/habit/…) remap correctly."""
    from hachi.core.user_profile import CorrectionLog, UserProfileStore

    log = CorrectionLog(db_path=tmp_path / "legacy.db")
    store = UserProfileStore(vault=fake_vault, correction_log=log)

    # Write directly into the vault with old-style categories (bypassing UserProfileStore.set).
    fake_vault._guarded_write("user_collection", "User's name is Carol", "name")
    fake_vault._guarded_write("user_collection", "User prefers spaces over tabs", "preference")
    fake_vault._guarded_write("user_collection", "User does daily yoga", "habit")
    fake_vault._guarded_write("user_collection", "User knows Rust", "role")

    profile = store.get()
    log.close()

    # "name" → "identity"
    identity_contents = [e["content"] for e in profile["identity"]]
    assert "User's name is Carol" in identity_contents, f"identity mismatch: {identity_contents}"

    # "preference" → "preferences"
    prefs_contents = [e["content"] for e in profile["preferences"]]
    assert "User prefers spaces over tabs" in prefs_contents, (
        f"preferences mismatch: {prefs_contents}"
    )

    # "habit" → "routines"
    routines_contents = [e["content"] for e in profile["routines"]]
    assert "User does daily yoga" in routines_contents, f"routines mismatch: {routines_contents}"

    # "role" → "identity" (role is person-identity not a P1-7 category)
    assert "User knows Rust" in identity_contents, f"role→identity mismatch: {identity_contents}"


# ---------------------------------------------------------------------------
# T8 — set() raises ValueError for invalid category
# ---------------------------------------------------------------------------


def test_set_raises_for_invalid_category(store: UserProfileStore) -> None:
    """set() raises ValueError when the category is not in PROFILE_CATEGORIES."""
    with pytest.raises(ValueError, match="Invalid profile category"):
        store.set("bogus_category", "some fact")


def test_set_raises_for_old_vault_category(store: UserProfileStore) -> None:
    """Old vault categories (e.g. 'preference') are not accepted by set()."""
    with pytest.raises(ValueError):
        store.set("preference", "some fact")


# ---------------------------------------------------------------------------
# T9 — correct() with unknown old_value still logs and writes new fact
# ---------------------------------------------------------------------------


def test_correct_unknown_old_value_still_logs_and_writes(store: UserProfileStore) -> None:
    """correct() with a value not in the vault logs the correction and writes the new fact."""
    result = store.correct(
        "nonexistent fact xyz",
        "User's timezone is UTC+5:30",
        reason="first capture",
    )

    # Correction should still be logged (logged=True).
    assert result["logged"] is True
    assert result["old_fact_id"] is None  # not found in vault

    # New fact should be in the vault.
    profile = store.get()
    all_contents = [e["content"] for cat_entries in profile.values() for e in cat_entries]
    assert "User's timezone is UTC+5:30" in all_contents, f"new fact not written: {all_contents}"

    # CorrectionLog should contain the attempt.
    log = store._log.get_all()
    assert any(e["old_value"] == "nonexistent fact xyz" for e in log), (
        f"correction not in log: {log}"
    )


# ---------------------------------------------------------------------------
# Category mapping unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("identity", "identity"),
        ("preferences", "preferences"),
        ("routines", "routines"),
        ("knowledge", "knowledge"),
        ("name", "identity"),
        ("role", "identity"),
        ("preference", "preferences"),
        ("style", "preferences"),
        ("timezone", "preferences"),
        ("habit", "routines"),
        ("relationship", "knowledge"),
        ("totally_unknown", "knowledge"),
    ],
)
def test_resolve_read_category(raw: str, expected: str) -> None:
    assert _resolve_read_category(raw) == expected
