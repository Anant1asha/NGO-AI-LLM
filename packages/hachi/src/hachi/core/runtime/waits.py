"""WaitConditionRegistry — arms and resolves wait conditions for durable runs.

Generalises PendingApprovalRegistry to all WaitKind values.
resolve() is idempotent via a single-use key set (guards against double-wake).
USER kind delegates to the existing PendingApprovalRegistry so current approval
behavior is preserved.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from hachi.core.runtime.state import WaitCondition

logger = logging.getLogger(__name__)


class WaitConditionRegistry:
    """Process-wide store that maps wait keys to run_ids.

    Thread-safe.  ``resolve()`` is idempotent: a key can only wake one run once,
    so a double-wake (e.g., two event deliveries for the same pattern match) is
    silently dropped after the first.

    Note: USER kind uses the standard PendingApprovalRegistry pathway; this
    registry records the mapping so the gateway /runs/{id}/wake endpoint can also
    resolve USER waits without duplicating approval machinery.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key → run_id
        self._armed: dict[str, str] = {}
        # run_id → WaitCondition (for re-arm on restart)
        self._conditions: dict[str, WaitCondition] = {}
        # resolved keys (single-use guard)
        self._resolved: set[str] = set()

    def arm(self, run_id: str, wait: WaitCondition) -> None:
        """Record that *run_id* is waiting on *wait*.

        For EVENT waits, the key is the event pattern.  For TIME waits, it is the
        ISO-8601 timestamp.  For USER waits, it is the approval request_id.
        """
        with self._lock:
            self._armed[wait.key] = run_id
            self._conditions[run_id] = wait

    def resolve(self, key: str, result: dict[str, Any]) -> str | None:
        """Wake the run armed on *key* and return its run_id.

        Idempotent: returns None (and logs) if the key was already resolved or is
        not armed.

        Args:
            key:    The event pattern / approval id / ISO timestamp that fired.
            result: The payload to inject into the resumed run.

        Returns:
            The run_id to wake, or ``None`` if no run is armed on this key.
        """
        with self._lock:
            if key in self._resolved:
                logger.debug(
                    "WaitConditionRegistry: key %r already resolved — ignoring double-wake", key
                )
                return None
            run_id = self._armed.pop(key, None)
            if run_id is None:
                return None
            self._resolved.add(key)
            self._conditions.pop(run_id, None)
        return run_id

    def disarm(self, run_id: str) -> None:
        """Remove all wait conditions for *run_id* (called on cancel / failure)."""
        with self._lock:
            wait = self._conditions.pop(run_id, None)
            if wait is not None:
                self._armed.pop(wait.key, None)

    def list_armed(self) -> list[tuple[str, str]]:
        """Return ``[(key, run_id), ...]`` for all currently armed waits."""
        with self._lock:
            return list(self._armed.items())

    def get_condition(self, run_id: str) -> WaitCondition | None:
        """Return the WaitCondition for *run_id* if armed, else None."""
        with self._lock:
            return self._conditions.get(run_id)


# Process-wide singleton
_registry: WaitConditionRegistry | None = None
_registry_lock = threading.Lock()


def get_wait_registry() -> WaitConditionRegistry:
    """Return the process-wide :class:`WaitConditionRegistry` singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = WaitConditionRegistry()
    return _registry
