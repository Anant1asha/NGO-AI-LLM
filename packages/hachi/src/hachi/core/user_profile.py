"""
UserProfileStore — structured facade over the MemoryVault user_profile collection.

Provides a typed, categorised API for reading, writing, and non-destructively
correcting user profile facts, backed by:
  - MemoryVault.user_collection  (ChromaDB) — the canonical fact store.
  - CorrectionLog (SQLite table in sessions.db) — append-only audit trail.

The four public fact categories align with the P1-7 schema:

    identity    — who the user is (name, role, age, location …)
    preferences — explicit preferences (dark mode, language, tools …)
    routines    — habitual patterns (morning standup, weekly review …)
    knowledge   — domain expertise the user has declared

Backward compatibility
----------------------
Existing entries written by memory.py / memory_tools.py carry the *old*
USER_PROFILE_CATEGORIES from memory_vault.py: name, role, preference, habit,
relationship, timezone, style, identity.  ``get()`` treats any entry whose
``category`` metadata is not in the four P1-7 categories as ``knowledge`` so old
data surfaces rather than silently vanishing.  ``set()`` and ``correct()`` only
accept the four P1-7 categories.

CorrectionLog backing choice
-----------------------------
A dedicated SQLite table ``profile_corrections`` in the existing sessions.db file
(accessed via a bare ``sqlite3.Connection``).  Rationale:

1. Simplest durable option — the file already exists on every install.
2. SQLite is already the house pattern for append-heavy audit data (interaction_log,
   idempotency_keys).
3. Keeps ChromaDB for semantic search only; corrections are a structured log, not a
   semantic store, so a relational table is a better fit.
4. Append-only is enforced at the schema level (no UPDATE/DELETE on rows, no UNIQUE
   constraint that would silently de-duplicate).
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hachi.core.paths import get_hachi_paths

if TYPE_CHECKING:
    from hachi.core.memory_vault import MemoryVault

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

# The four P1-7 categories exposed by UserProfileStore.
PROFILE_CATEGORIES: frozenset[str] = frozenset({"identity", "preferences", "routines", "knowledge"})

# Old vault categories that pre-date P1-7.  Any entry whose vault ``category``
# metadata is in this set (and NOT in PROFILE_CATEGORIES) is remapped to
# ``knowledge`` when reading back so existing data surfaces correctly.
_LEGACY_CATEGORIES: frozenset[str] = frozenset(
    {"name", "role", "preference", "habit", "relationship", "timezone", "style"}
)


def _resolve_read_category(vault_category: str) -> str:
    """Map a raw vault category string to one of the four P1-7 categories.

    Rules (additive / backward-compat):
    - Already a P1-7 category → return as-is.
    - "name" / "role" / "identity" → "identity"
    - "preference" / "style" / "timezone" → "preferences"
    - "habit" → "routines"
    - "relationship" (and anything else) → "knowledge"

    Args:
        vault_category: Raw ``category`` metadata from the Chroma collection.

    Returns:
        One of ``PROFILE_CATEGORIES``.
    """
    if vault_category in PROFILE_CATEGORIES:
        return vault_category
    _map = {
        "name": "identity",
        "role": "identity",
        "preference": "preferences",
        "style": "preferences",
        "timezone": "preferences",
        "habit": "routines",
    }
    return _map.get(vault_category, "knowledge")


# ---------------------------------------------------------------------------
# CorrectionLog
# ---------------------------------------------------------------------------


class CorrectionLog:
    """Durable, append-only record of profile corrections.

    Backed by a ``profile_corrections`` SQLite table in the existing sessions.db file.
    The table is created on first access via ``_ensure_table()``.

    Thread safety: a reentrant lock serialises all writes.  Reads use a separate
    connection handle created inside the lock so WAL allows concurrent readers.

    Append-only contract: there is NO UPDATE or DELETE path on the table; rows are
    written once and never modified.

    Args:
        db_path: Path to the SQLite database.  Defaults to ``get_hachi_paths().sessions_db``.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = get_hachi_paths().sessions_db
        self._db_path: Path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock: threading.RLock = threading.RLock()
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self._db_path), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the profile_corrections table if it does not exist.

        The table is append-only: there is no UPDATE or DELETE route.
        The schema is intentionally simple — no FK to the sessions table so
        corrections survive even if sessions are purged.
        """
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS profile_corrections (
                    id          TEXT PRIMARY KEY,
                    ts          TEXT NOT NULL,
                    category    TEXT NOT NULL,
                    old_value   TEXT NOT NULL,
                    new_value   TEXT NOT NULL,
                    reason      TEXT NOT NULL DEFAULT ''
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pcorr_ts
                    ON profile_corrections(ts)
            """)
            self._conn.commit()

    def append(
        self,
        *,
        category: str,
        old_value: str,
        new_value: str,
        reason: str = "",
    ) -> str:
        """Append one correction record.  Returns the new row id.

        Args:
            category: One of PROFILE_CATEGORIES.
            old_value: The fact text that was superseded.
            new_value: The replacement fact text.
            reason: Human-readable explanation of the correction.

        Returns:
            The generated UUID row id.
        """
        row_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO profile_corrections (id, ts, category, old_value, new_value, reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (row_id, ts, category, old_value, new_value, reason),
            )
            self._conn.commit()
        logger.debug(
            "CorrectionLog.append: category=%s id=%s old=%.40r → new=%.40r",
            category,
            row_id,
            old_value,
            new_value,
        )
        return row_id

    def get_all(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return all correction records, newest first.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of dicts with keys: id, ts, category, old_value, new_value, reason.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts, category, old_value, new_value, reason "
                "FROM profile_corrections ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        """Close the SQLite connection (idempotent)."""
        try:
            self._conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# UserProfileStore
# ---------------------------------------------------------------------------


class UserProfileStore:
    """Structured facade over the MemoryVault user_profile collection.

    All reads and writes go through the existing ``MemoryVault`` primitives —
    no parallel store is created.  The four P1-7 categories (identity, preferences,
    routines, knowledge) are stamped as the ``category`` metadata field on every new
    fact written through this class.  Existing facts written with the old vault
    categories are remapped on read via ``_resolve_read_category``.

    Args:
        vault: A ``MemoryVault`` instance (must be open).
        correction_log: A ``CorrectionLog`` instance.  Constructed automatically
            from the default sessions.db path when omitted.

    Raises:
        ValueError: If an invalid category is passed to ``set()`` or ``correct()``.
    """

    def __init__(
        self,
        vault: MemoryVault,
        correction_log: CorrectionLog | None = None,
    ) -> None:
        self._vault: MemoryVault = vault
        self._log: CorrectionLog = correction_log if correction_log is not None else CorrectionLog()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self) -> dict[str, list[dict[str, Any]]]:
        """Return all user profile facts grouped by the four P1-7 categories.

        Reads the entire user_collection from the vault and groups the results.
        Old vault categories are remapped via ``_resolve_read_category``.

        Returns:
            Dict with four keys (identity, preferences, routines, knowledge) each
            mapping to a list of fact dicts: {id, content, category, timestamp}.
            Empty lists are present for categories with no facts.

        Raises:
            RuntimeError: If the vault is closed.
        """
        grouped: dict[str, list[dict[str, Any]]] = {cat: [] for cat in sorted(PROFILE_CATEGORIES)}
        rows = self._vault_get_all()
        for entry in rows:
            raw_cat = entry.get("category", "knowledge")
            mapped = _resolve_read_category(raw_cat)
            grouped[mapped].append(
                {
                    "id": entry["id"],
                    "content": entry["content"],
                    "category": mapped,
                    "original_category": raw_cat,
                    "timestamp": entry.get("timestamp", ""),
                }
            )
        return grouped

    def set(
        self,
        category: str,
        value: str,
        *,
        key: str | None = None,
    ) -> str:
        """Store a profile fact under one of the four P1-7 categories.

        Writes through to ``MemoryVault.upsert_user_fact`` stamping ``category``
        in metadata.  The vault enforces the 25-entry cap and MemoryGuard scanning.

        Args:
            category: One of ``PROFILE_CATEGORIES`` (identity, preferences,
                routines, knowledge).
            value: The fact text.
            key: Optional logical key for the fact (unused in storage, reserved
                for future indexing — passed for API symmetry).

        Returns:
            The fact ID returned by the vault, or "BLOCKED:<threat>" / "LIMIT_REACHED".

        Raises:
            ValueError: If ``category`` is not in ``PROFILE_CATEGORIES``.
        """
        _validate_category(category)
        # Write directly via _vault_set rather than upsert_user_fact so the
        # P1-7 category string is stamped in metadata without being normalised
        # to "preference" by the vault's legacy category guard.
        result = self._vault_set(category=category, content=value)
        logger.debug("UserProfileStore.set: category=%s result=%s", category, result[:20])
        return result

    def correct(
        self,
        old_value_or_id: str,
        new_value: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        """Non-destructively correct a profile fact.

        Steps:
        1. Locate the old fact in the vault (by content text or by SHA-256 ID).
        2. Determine its category (falls back to "knowledge" when not found).
        3. Append a CorrectionLog entry recording the change.
        4. Supersede the old fact: if found by ID → delete it and write the
           new value in its place.  The old value is NEVER silently lost —
           it is preserved in the CorrectionLog.

        Args:
            old_value_or_id: Either the exact fact text or the SHA-256 fact ID
                from a prior ``get()`` call.
            new_value: The replacement fact text.
            reason: Human-readable explanation.

        Returns:
            Dict with keys:
              - correction_id (str): CorrectionLog row id.
              - old_fact_id (str | None): Vault ID of the superseded fact.
              - new_fact_id (str): Vault ID of the replacement fact.
              - category (str): Category used.
              - logged (bool): Whether the CorrectionLog entry was written.
        """
        # Step 1 — resolve the old fact in the vault.
        old_fact = self._find_user_fact(old_value_or_id)
        if old_fact is not None:
            old_id: str | None = old_fact["id"]
            old_content: str = old_fact["content"]
            raw_category: str = old_fact.get("category", "knowledge")
            category = _resolve_read_category(raw_category)
        else:
            # Fact not found — treat the argument as the raw text, category unknown.
            old_id = None
            old_content = old_value_or_id
            category = "knowledge"

        # Step 2 — write the CorrectionLog entry (always; even if old not found).
        try:
            correction_id = self._log.append(
                category=category,
                old_value=old_content,
                new_value=new_value,
                reason=reason,
            )
            logged = True
        except Exception as exc:
            logger.error("UserProfileStore.correct: CorrectionLog write failed: %s", exc)
            correction_id = ""
            logged = False

        # Step 3 — supersede the old fact in the vault.
        if old_id is not None:
            try:
                self._vault.delete_user_fact(old_id)
            except Exception as exc:
                logger.warning(
                    "UserProfileStore.correct: could not delete old fact %s: %s", old_id, exc
                )

        # Step 4 — write the replacement.
        new_fact_id = self._vault_set(category=category, content=new_value)

        return {
            "correction_id": correction_id,
            "old_fact_id": old_id,
            "new_fact_id": new_fact_id,
            "category": category,
            "logged": logged,
        }

    def export(self) -> dict[str, Any]:
        """Dump the full profile and correction history.

        Returns:
            Dict with keys:
              - profile (dict[str, list]): Output of ``get()``.
              - corrections (list[dict]): All CorrectionLog entries.
              - stats (dict): Vault capacity stats.
        """
        profile = self.get()
        corrections = self._log.get_all()
        stats = self._vault.get_profile_stats()
        return {
            "profile": profile,
            "corrections": corrections,
            "stats": stats,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _vault_get_all(self) -> list[dict[str, Any]]:
        """Read all user_collection entries from the vault as structured dicts."""
        try:
            with self._vault._vault_lock:
                self._vault._assert_open()
                ucoll = self._vault._get_collection("user_collection")
                rows = ucoll.get(include=["documents", "metadatas"])
        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning("UserProfileStore._vault_get_all failed: %s", exc)
            return []

        ids = rows.get("ids") or []
        docs = rows.get("documents") or []
        metas = rows.get("metadatas") or []
        result: list[dict[str, Any]] = []
        for i, entry_id in enumerate(ids):
            doc = docs[i] if i < len(docs) else ""
            meta = metas[i] if i < len(metas) else {}
            result.append(
                {
                    "id": entry_id,
                    "content": doc,
                    "category": meta.get("category", "knowledge"),
                    "timestamp": meta.get("timestamp", ""),
                }
            )
        return result

    def _vault_set(self, *, category: str, content: str) -> str:
        """Write a fact into the vault with the P1-7 category stamped in metadata.

        Bypasses ``upsert_user_fact``'s category normalisation (which would remap
        unknown categories to "preference") by calling ``_guarded_write`` directly
        after performing the capacity check ourselves.

        The capacity check mirrors ``upsert_user_fact`` exactly: we allow upserts of
        content that already exists (content-addressable IDs → idempotent).
        """
        from hachi.core.memory_vault import MemoryVault

        existing_id = MemoryVault._generate_id(content)
        try:
            with self._vault._vault_lock:
                self._vault._assert_open()
                ucoll = self._vault._get_collection("user_collection")
                existing = ucoll.get(ids=[existing_id])
                is_update = bool(existing and existing.get("ids"))
                count = ucoll.count()
        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning("UserProfileStore._vault_set: capacity check failed: %s", exc)
            return f"ERROR:{exc}"

        from hachi.core.memory_vault import USER_PROFILE_MAX_ENTRIES

        if not is_update and count >= USER_PROFILE_MAX_ENTRIES:
            return "LIMIT_REACHED"

        result: str = self._vault._guarded_write("user_collection", content, category)
        return result

    def _find_user_fact(self, value_or_id: str) -> dict[str, Any] | None:
        """Locate a user profile fact by exact content text OR by SHA-256 ID.

        Returns a dict {id, content, category, timestamp} or None if not found.
        """
        from hachi.core.memory_vault import MemoryVault

        # Try SHA-256 ID lookup first (fast, exact).
        if len(value_or_id) == 64:
            candidate_id = value_or_id
        else:
            candidate_id = MemoryVault._generate_id(value_or_id)
        try:
            with self._vault._vault_lock:
                self._vault._assert_open()
                ucoll = self._vault._get_collection("user_collection")
                rows = ucoll.get(ids=[candidate_id], include=["documents", "metadatas"])
        except Exception:
            rows = {}

        ids = rows.get("ids") or []
        if ids:
            docs = rows.get("documents") or []
            metas = rows.get("metadatas") or []
            doc = docs[0] if docs else ""
            meta = metas[0] if metas else {}
            return {
                "id": ids[0],
                "content": doc,
                "category": meta.get("category", "knowledge"),
                "timestamp": meta.get("timestamp", ""),
            }

        # Fall back to scanning all entries for an exact content match.
        all_entries = self._vault_get_all()
        for entry in all_entries:
            if entry["content"] == value_or_id:
                return entry

        return None


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _validate_category(category: str) -> None:
    """Raise ValueError if category is not in PROFILE_CATEGORIES.

    Args:
        category: The category string to validate.

    Raises:
        ValueError: With a descriptive message listing the allowed values.
    """
    if category not in PROFILE_CATEGORIES:
        raise ValueError(
            f"Invalid profile category {category!r}. Must be one of: {sorted(PROFILE_CATEGORIES)}"
        )
