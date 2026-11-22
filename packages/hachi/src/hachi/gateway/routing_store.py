"""RoutingConfigStore — process-level hot-reload store for routing config.

Holds the *current* RoutingSnapshot (immutable routing config bundle) and a
monotonic version counter.  Each session's ExecutionLoop checks the version at
its own turn boundary and pulls if the store is newer than its last-applied
version.

Read path: lock-free (cheap int + immutable reference read).
Write path (apply/rollback): guarded by _ROUTING_LOCK.

The store intentionally knows nothing about how to *build* a snapshot — that
lives in the gateway orchestration layer.  The store only stores, versions, and
audits.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from hachi.core.routing.snapshot import RoutingSnapshot

logger = logging.getLogger(__name__)

_ROUTING_LOCK = threading.Lock()


class RoutingConfigStore:
    """Process-level singleton (one per RoutingConfigStore instance; the gateway
    keeps the sole instance on ProcessSharedServices.routing_store).

    Thread-safety contract:
      - ``version`` and ``current_snapshot`` are safe to read without a lock
        (Python reference reads are atomic on CPython; GIL protects the int).
      - ``apply`` and ``rollback`` take ``_ROUTING_LOCK`` to keep the
        version counter and snapshot reference consistent with each other.
      - The audit file append is inside the lock; a missed flush only loses
        the record for a crash-concurrent write — the session state is not
        affected.
    """

    def __init__(self) -> None:
        self._current: RoutingSnapshot | None = None
        self._last_good: RoutingSnapshot | None = None
        self._version: int = 0
        self._audit_path: Path | None = None

    # ------------------------------------------------------------------
    # Readers (lock-free)
    # ------------------------------------------------------------------

    @property
    def version(self) -> int:
        """Current snapshot version (monotonically increasing)."""
        return self._version

    @property
    def current_snapshot(self) -> RoutingSnapshot | None:
        """The currently-active routing snapshot."""
        return self._current

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def init(self, snap: RoutingSnapshot, *, audit_path: Path | None = None) -> None:
        """Set the initial snapshot at process boot WITHOUT bumping the version.

        All sessions start with ``_applied_routing_version = 0``, so a version
        of 0 after ``init`` means every session is already current — no spurious
        swap at the first turn.

        Args:
            snap:       The boot-time routing snapshot.
            audit_path: Optional path to ``routing_audit.jsonl`` for durable
                        change records.  ``None`` disables auditing.
        """
        with _ROUTING_LOCK:
            self._current = snap
            self._last_good = snap
            self._audit_path = audit_path

    def apply(self, snap: RoutingSnapshot) -> RoutingSnapshot | None:
        """Atomically replace the current snapshot and bump the version.

        Each session's loop will notice the new version at its next turn
        boundary and call ``router.apply_snapshot(snap)`` to adopt it.

        Args:
            snap: The validated new snapshot to publish.

        Returns:
            The previous snapshot (useful for rollback); ``None`` when no
            previous snapshot existed.
        """
        with _ROUTING_LOCK:
            previous = self._current
            self._last_good = previous  # last-good ← what we're replacing
            self._current = snap
            self._version += 1
            self._append_audit("changed", snap)

        logger.info(
            "RoutingConfigStore: applied v%d source=%r default=%s",
            self._version,
            snap.source,
            snap.policy.default_model,
        )
        return previous

    def rollback(self) -> RoutingSnapshot | None:
        """Restore the last-known-good snapshot.

        Returns:
            The restored snapshot, or ``None`` when no prior snapshot exists.
        """
        with _ROUTING_LOCK:
            if self._last_good is None:
                return None
            self._current = self._last_good
            self._version += 1
            self._append_audit("rolled_back", self._last_good)

        logger.info("RoutingConfigStore: rolled back to v%d", self._version)
        return self._last_good

    def audit_records(self, limit: int = 50) -> list[dict[str, object]]:
        """Return the most recent *limit* audit records from disk.

        Returns an empty list when no audit path is configured or the file
        does not exist yet.

        Args:
            limit: Maximum number of records to return (newest first).
        """
        if self._audit_path is None or not self._audit_path.exists():
            return []
        try:
            lines = self._audit_path.read_text(encoding="utf-8").splitlines()
            records = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return records[-limit:][::-1]  # newest first
        except Exception:
            logger.debug("RoutingConfigStore.audit_records: read failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append_audit(self, event: str, snap: RoutingSnapshot) -> None:
        """Append one JSON line to the audit file (called under _ROUTING_LOCK)."""
        if self._audit_path is None:
            return
        record = {
            "event": event,
            "version": self._version,
            "source": snap.source,
            "default_model": snap.policy.default_model,
        }
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
                fh.flush()
        except Exception:
            logger.debug("RoutingConfigStore: audit write failed", exc_info=True)
