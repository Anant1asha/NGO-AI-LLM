"""lease_manager.py — P4-01 multi-agent v2: write-target leases.

A tiny in-process lease table that prevents two concurrent delegations from
writing to the same file-path prefix or integration scope simultaneously.
Read access is never blocked.

Design (from 07-future-and-growth.md §2 point 3):
  - keyed by declared write-targets (path prefixes, integration scopes)
  - a delegation that claims 'gmail.send' or '~/work/billing/**' blocks
    a second claimant until release or expiry
  - per-session serialisation (R1) makes this sound

Usage::

    mgr = LeaseManager()
    ok, conflict = mgr.acquire("researcher", ["projects/billing", "drive.write"])
    if not ok:
        ...  # conflict tells you who holds it
    try:
        run_sub_agent(...)
    finally:
        mgr.release("researcher", ["projects/billing", "drive.write"])
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _LeaseEntry:
    """An active write-target lease held by a delegation."""

    role: str
    targets: list[str]
    acquired_at: float = field(default_factory=time.monotonic)
    ttl_seconds: float = 300.0  # 5 minutes default

    @property
    def expires_at(self) -> float:
        return self.acquired_at + self.ttl_seconds

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


class LeaseConflict(Exception):
    """Raised when a target is already held by another delegation.

    Attributes:
        target: The conflicting write-target.
        holder: The role that currently holds the lease.
    """

    def __init__(self, target: str, holder: str) -> None:
        self.target = target
        self.holder = holder
        super().__init__(f"Write-target '{target}' is already held by '{holder}'")


class LeaseManager:
    """Thread-safe in-process write-target lease registry.

    Each live ``AgentSession`` shares a single ``LeaseManager`` (created in
    ``boot_agent`` and passed down to the delegation tool factory).  The
    serialised chat lock (P1-01) ensures that at most one delegation is
    *starting* at any moment; the lease table prevents overlaps when parallel
    delegations are submitted in the same tool batch (P4-03).

    Targets are matched by **prefix**:  a lease on ``"projects/billing"``
    blocks any target that starts with ``"projects/billing"``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # target_prefix → LeaseEntry
        self._leases: dict[str, _LeaseEntry] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(
        self,
        role: str,
        targets: list[str],
        ttl_seconds: float = 300.0,
    ) -> tuple[bool, str | None]:
        """Attempt to acquire leases on all write-targets for *role*.

        Atomic: either all targets are acquired or none are (on conflict the
        caller gets back the conflicting target + current holder name).

        Args:
            role: The sub-agent role requesting the lease.
            targets: Declared write-target prefixes (e.g. ``["projects/billing"]``).
            ttl_seconds: How long the leases are valid before auto-expiry.

        Returns:
            ``(True, None)`` on success, ``(False, "<conflict_info>")`` on failure.
        """
        if not targets:
            return True, None

        with self._lock:
            self._expire_stale()
            # Check for conflicts before writing anything
            for target in targets:
                conflict = self._find_conflict(target)
                if conflict is not None:
                    return False, f"target '{target}' held by '{conflict.role}'"

            # No conflicts — stamp all targets
            entry = _LeaseEntry(role=role, targets=list(targets), ttl_seconds=ttl_seconds)
            for target in targets:
                self._leases[target] = entry

        return True, None

    def release(self, role: str, targets: list[str]) -> None:
        """Release leases held by *role* on the given targets.

        Silently ignores targets that are not held or were already expired/released.
        """
        with self._lock:
            for target in targets:
                entry = self._leases.get(target)
                if entry is not None and entry.role == role:
                    del self._leases[target]

    def held_by(self, role: str) -> list[str]:
        """Return all targets currently leased to *role*."""
        with self._lock:
            self._expire_stale()
            return [t for t, e in self._leases.items() if e.role == role]

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable snapshot of all active leases (for diagnostics)."""
        with self._lock:
            self._expire_stale()
            return [
                {
                    "role": e.role,
                    "targets": e.targets,
                    "expires_in_s": round(max(0.0, e.expires_at - time.monotonic()), 1),
                }
                for e in {id(e): e for e in self._leases.values()}.values()
            ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _expire_stale(self) -> None:
        """Remove leases past their TTL.  Must be called under ``self._lock``."""
        stale = [t for t, e in self._leases.items() if e.is_expired()]
        for t in stale:
            del self._leases[t]

    def _find_conflict(self, target: str) -> _LeaseEntry | None:
        """Return the first live lease that covers *target*, or None."""
        for held_target, entry in self._leases.items():
            # Prefix match: held "projects/billing" blocks "projects/billing/schema"
            if target.startswith(held_target) or held_target.startswith(target):
                return entry
        return None
