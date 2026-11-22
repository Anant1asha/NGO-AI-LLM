"""
Action Approval Gate

Tier-gated approval system for destructive actions.  Provides a stable
Protocol/ABC for approvers and three concrete implementations:

- ``PolicyApprover``   — no-human connected; allow at ``unrestricted``, deny otherwise.
- ``HandlerApprover``  — TUI path; delegates to an in-process callable.
- ``RegistryApprover`` — gateway/channel path; parks the request in
  ``PendingApprovalRegistry`` and blocks until the gateway endpoint resolves it.

Public API consumed by Agent B (gateway-auth):
    get_approval_registry() -> PendingApprovalRegistry
    registry.list_pending() -> list[dict]
    registry.resolve(request_id: str, decision: PermissionDecision) -> bool

Threading contract
------------------
``RegistryApprover.require()`` calls ``PendingApprovalRegistry.wait()``, which
calls ``threading.Event.wait(timeout=...)`` — a **synchronous blocking call**.

* **Gateway / FastAPI path** — ``fastapi_app.py`` dispatches every agent turn via
  ``anyio.to_thread.run_sync(...)``, so ``require()`` always runs inside an anyio
  worker thread.  The asyncio event loop is never blocked directly.

* **Remaining risk (REL-001)** — Under many concurrent unanswered approvals, each
  blocked ``require()`` call holds one worker thread for up to ``timeout`` seconds.
  The anyio default thread pool cap is 40.  Callers that can drive an async context
  should prefer :meth:`RegistryApprover.require_async` which awaits
  :meth:`PendingApprovalRegistry.wait_async` instead; ``wait_async`` uses
  ``anyio.to_thread.run_sync`` so it releases the calling coroutine (no loop
  stall) while still occupying exactly one worker thread, keeping the thread-count
  exposure identical — but allowing the asyncio scheduler to interleave other work
  freely.

* **Timeout / cleanup** — :meth:`PendingApprovalRegistry.wait` (and ``wait_async``)
  call :meth:`~PendingApprovalRegistry._cleanup` automatically on timeout so that
  a never-answered request cannot pin a thread slot indefinitely **and** cannot
  accumulate in ``_entries`` and leak memory.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Any, Protocol, cast, runtime_checkable

import anyio

from hachi.core.permissions import (
    PermissionDecision,
    PermissionRequest,
)

# ==========================================
# Protocol
# ==========================================


@runtime_checkable
class ActionApprover(Protocol):
    """Protocol for all action approvers.

    Concrete implementations must implement ``require``.  The return value is
    ``(approved, reason)`` where *reason* is shown to the user or logged.
    """

    def require(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Gate a single destructive action.

        Args:
            action:  Canonical action name, e.g. ``"send_email"``, ``"trash_file"``.
            summary: Short human-readable description of what would happen.
            detail:  Optional extended context for the approval UI.

        Returns:
            ``(True, reason)`` if the action is approved, ``(False, reason)`` if denied.
        """
        ...


# ==========================================
# Pending Approval Registry
# ==========================================


class _PendingEntry:
    """Internal entry tracking one pending approval request."""

    __slots__ = ("request", "event", "decision")

    def __init__(self, request: PermissionRequest) -> None:
        self.request = request
        self.event: threading.Event = threading.Event()
        self.decision: PermissionDecision | None = None


class PendingApprovalRegistry:
    """Process-wide store for non-interactive approval requests.

    Used by the gateway/API path when no TUI handler is connected.
    The gateway's ``/approvals`` REST endpoint reads ``list_pending()`` and
    calls ``resolve()`` to unblock the waiting tool call.

    This class is thread-safe.

    Threading contract
    ------------------
    :meth:`wait` is a **synchronous blocking call** (``threading.Event.wait``).
    It is safe to call from a worker thread (e.g. inside ``anyio.to_thread.run_sync``).
    Do **not** call it directly from an async context — use :meth:`wait_async` instead.

    :meth:`wait_async` offloads the blocking wait to an anyio worker thread via
    ``anyio.to_thread.run_sync``, releasing the event loop while waiting.

    Both :meth:`wait` and :meth:`wait_async` auto-clean up the entry on timeout
    so that a never-answered request cannot leak memory or pin a thread slot.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, _PendingEntry] = {}

    # ── Public API (stable — consumed by Agent B) ──

    def create(self, request: PermissionRequest) -> str:
        """Store *request* and return its ``request_id``.

        A :class:`threading.Event` is created for each entry so that
        :meth:`wait` can block until :meth:`resolve` is called.
        """
        entry = _PendingEntry(request)
        with self._lock:
            self._entries[request.request_id] = entry
        return cast(str, request.request_id)

    def list_pending(self) -> list[dict[str, Any]]:
        """Return all unresolved pending requests as serialisable dicts.

        Each dict contains:
            ``request_id``, ``operation``, ``tool``, ``target``,
            ``reason``, ``policy_summary``.
        """
        with self._lock:
            return [
                {
                    "request_id": e.request.request_id,
                    "operation": e.request.operation,
                    "tool": e.request.tool,
                    "target": e.request.target,
                    "reason": e.request.reason,
                    "policy_summary": e.request.policy_summary,
                }
                for e in self._entries.values()
                if not e.event.is_set()
            ]

    def resolve(self, request_id: str, decision: PermissionDecision) -> bool:
        """Record *decision* and unblock any thread waiting on *request_id*.

        Returns ``True`` if the entry existed and was resolved, ``False``
        if *request_id* is unknown.
        """
        with self._lock:
            entry = self._entries.get(request_id)
        if entry is None:
            return False
        entry.decision = decision
        entry.event.set()
        return True

    def wait(self, request_id: str, timeout: float) -> PermissionDecision:
        """Block until *request_id* is resolved or *timeout* seconds pass.

        This is a **synchronous blocking call** — run it from a worker thread,
        never directly from an async context.  Use :meth:`wait_async` instead
        when calling from a coroutine.

        On timeout the pending entry is **removed** (auto-cleanup) and a deny
        decision with rationale ``"approval timed out"`` is returned, so the
        tool can distinguish a timeout from an explicit user deny.

        On a successful signal the entry is **not** removed here — callers must
        call :meth:`_cleanup` after consuming the decision (``RegistryApprover``
        does this immediately after ``wait`` returns).

        Args:
            request_id: ID previously returned by :meth:`create`.
            timeout:    Maximum seconds to wait.

        Returns:
            The :class:`~hachi.core.permissions.PermissionDecision` recorded by
            :meth:`resolve`, or a synthetic deny on timeout / unknown ID.
        """
        with self._lock:
            entry = self._entries.get(request_id)
        if entry is None:
            return PermissionDecision(action="deny", rationale="unknown request_id")
        signalled = entry.event.wait(timeout=timeout)
        if not signalled:
            # Auto-cleanup on timeout so the entry does not leak.
            self._cleanup(request_id)
            return PermissionDecision(action="deny", rationale="approval timed out")
        decision = entry.decision
        assert decision is not None  # event is set only after assignment
        return decision

    async def wait_async(self, request_id: str, timeout: float) -> PermissionDecision:
        """Async variant of :meth:`wait` — safe to call from a coroutine.

        Offloads the blocking ``threading.Event.wait`` to an anyio worker thread
        via ``anyio.to_thread.run_sync``, releasing the event loop while waiting.
        This prevents the approval wait from ever stalling the asyncio scheduler,
        even if many concurrent approvals are pending simultaneously.

        The timeout and auto-cleanup behaviour are identical to :meth:`wait`.

        Args:
            request_id: ID previously returned by :meth:`create`.
            timeout:    Maximum seconds to wait.

        Returns:
            The :class:`~hachi.core.permissions.PermissionDecision` recorded by
            :meth:`resolve`, or a synthetic deny on timeout / unknown ID.
        """
        return await anyio.to_thread.run_sync(
            lambda: self.wait(request_id, timeout),
            abandon_on_cancel=True,
        )

    def _cleanup(self, request_id: str) -> None:
        """Remove a resolved or timed-out entry from the registry.

        Called internally after :meth:`wait` / :meth:`wait_async` return, and
        automatically on timeout so entries cannot accumulate indefinitely.
        """
        with self._lock:
            self._entries.pop(request_id, None)


# ── Module-level singleton ──

_registry: PendingApprovalRegistry | None = None
_registry_lock = threading.Lock()


def get_approval_registry() -> PendingApprovalRegistry:
    """Return the process-wide :class:`PendingApprovalRegistry` singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = PendingApprovalRegistry()
    return _registry


# ==========================================
# Concrete Approvers
# ==========================================


class PolicyApprover:
    """Tier-only approver used when no human approver is connected.

    - ``unrestricted`` tier  → auto-approve.
    - ``guided`` / ``sandbox`` → deny with an actionable message.
    """

    def __init__(self, tier: str) -> None:
        """
        Args:
            tier: The active permission tier (``"unrestricted"``, ``"guided"``,
                  ``"sandbox"``).
        """
        self._tier = tier

    def require(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Return ``(True, ...)`` only for ``unrestricted`` tier.

        Args:
            action:  Canonical action name.
            summary: Human-readable action summary.
            detail:  Optional extended context.
        """
        if self._tier == "unrestricted":
            return (True, "auto-approved (unrestricted tier)")
        return (
            False,
            "This action needs human approval. Connect the TUI or web companion to approve, "
            "or set tier=unrestricted in ~/.hachi/device-permissions.og.",
        )


class HandlerApprover:
    """TUI-path approver: delegates to an in-process callable.

    Builds a :class:`~hachi.core.permissions.PermissionRequest`, emits
    ``permission.requested`` / ``permission.decided`` events, then calls
    *handler* and maps the decision to a ``(bool, str)`` pair.
    """

    def __init__(
        self,
        handler: Callable[[PermissionRequest], PermissionDecision],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """
        Args:
            handler: Callable that presents the request to the user (e.g. TUI modal)
                     and returns a :class:`~hachi.core.permissions.PermissionDecision`.
            emit:    Event emitter accepting ``(event_name, payload_dict)``.
        """
        self._handler = handler
        self._emit = emit

    def require(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Call the TUI handler and return ``(approved, reason)``.

        Args:
            action:  Canonical action name.
            summary: Human-readable action summary.
            detail:  Optional extended context.
        """
        request = PermissionRequest(
            request_id=uuid.uuid4().hex,
            operation="action",
            tool=action,
            target=summary,
            reason=detail or summary,
            policy_summary=f"action:{action}",
        )

        self._emit(
            "permission.requested",
            {
                "request_id": request.request_id,
                "operation": request.operation,
                "tool": request.tool,
                "target": request.target,
                "reason": request.reason,
                "policy_summary": request.policy_summary,
            },
        )

        try:
            decision = self._handler(request)
        except Exception as exc:
            decision = PermissionDecision(action="deny", rationale=f"handler error: {exc}")

        self._emit(
            "permission.decided",
            {
                "request_id": request.request_id,
                "operation": request.operation,
                "tool": request.tool,
                "target": request.target,
                "decision": decision.action,
                "reason": decision.rationale or summary,
            },
        )

        if decision.action in ("approve", "allow_once"):
            return (True, decision.rationale or "approved")
        return (False, decision.rationale or "denied by operator")


class RegistryApprover:
    """Gateway/channel-path approver: parks the request in the registry and blocks.

    Creates a :class:`~hachi.core.permissions.PermissionRequest`, stores it
    in the :class:`PendingApprovalRegistry`, emits ``permission.requested``, then
    blocks on :meth:`~PendingApprovalRegistry.wait` until the gateway endpoint calls
    :meth:`~PendingApprovalRegistry.resolve` or the timeout expires.

    Threading contract
    ------------------
    :meth:`require` is **synchronous-blocking** — it must only be called from a
    worker thread (never directly from the asyncio event loop).  The FastAPI gateway
    routes all agent turns through ``anyio.to_thread.run_sync``, satisfying this
    constraint today.

    :meth:`require_async` is the **async-safe** alternative.  It drives the same
    registry flow but awaits :meth:`~PendingApprovalRegistry.wait_async`, which
    offloads the blocking event wait to an anyio worker thread without stalling the
    event loop.  Prefer ``require_async`` in any new async call-site.

    Both methods share identical timeout and cleanup behaviour: a timed-out request
    is auto-denied and removed from the registry so it cannot leak.
    """

    def __init__(
        self,
        registry: PendingApprovalRegistry,
        emit: Callable[[str, dict[str, Any]], None],
        timeout: float = 180.0,
    ) -> None:
        """
        Args:
            registry: The process-wide :class:`PendingApprovalRegistry`.
            emit:     Event emitter accepting ``(event_name, payload_dict)``.
            timeout:  Seconds to wait before treating the request as timed-out deny.
        """
        self._registry = registry
        self._emit = emit
        self._timeout = timeout

    # ── Internal helpers ──

    def _build_and_park(self, action: str, summary: str, detail: str) -> str:
        """Create a :class:`PermissionRequest`, store it, emit the event, return request_id."""
        request = PermissionRequest(
            request_id=uuid.uuid4().hex,
            operation="action",
            tool=action,
            target=summary,
            reason=detail or summary,
            policy_summary=f"action:{action}",
        )
        request_id = self._registry.create(request)
        self._emit(
            "permission.requested",
            {
                "request_id": request_id,
                "operation": request.operation,
                "tool": request.tool,
                "target": request.target,
                "reason": request.reason,
                "policy_summary": request.policy_summary,
            },
        )
        return request_id

    def _emit_decided(
        self, request_id: str, action: str, summary: str, decision: PermissionDecision
    ) -> None:
        """Emit the ``permission.decided`` event after a decision is known."""
        self._emit(
            "permission.decided",
            {
                "request_id": request_id,
                "operation": "action",
                "tool": action,
                "target": summary,
                "decision": decision.action,
                "reason": decision.rationale,
            },
        )

    def _decision_to_result(self, decision: PermissionDecision) -> tuple[bool, str]:
        """Convert a :class:`PermissionDecision` to the ``(approved, reason)`` tuple."""
        if decision.action in ("approve", "allow_once"):
            return (True, decision.rationale or "approved")
        return (False, decision.rationale or "denied")

    # ── Public API ──

    def require(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Park the request and **block** synchronously until resolved or timed out.

        **Call only from a worker thread** — never from an async context.
        Use :meth:`require_async` instead when awaiting from a coroutine.

        Args:
            action:  Canonical action name.
            summary: Human-readable action summary.
            detail:  Optional extended context.

        Returns:
            ``(True, reason)`` if approved; ``(False, reason)`` if denied or timed out.
        """
        request_id = self._build_and_park(action, summary, detail)
        decision = self._registry.wait(request_id, self._timeout)
        # _cleanup is called by wait() on timeout; call it here on the normal path.
        self._registry._cleanup(request_id)
        self._emit_decided(request_id, action, summary, decision)
        return self._decision_to_result(decision)

    async def require_async(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Park the request and **await** resolution without blocking the event loop.

        Async-safe alternative to :meth:`require`.  Offloads the blocking
        ``threading.Event.wait`` to an anyio worker thread via
        :meth:`~PendingApprovalRegistry.wait_async`, so the event loop remains
        free to handle other requests while waiting.

        Args:
            action:  Canonical action name.
            summary: Human-readable action summary.
            detail:  Optional extended context.

        Returns:
            ``(True, reason)`` if approved; ``(False, reason)`` if denied or timed out.
        """
        request_id = self._build_and_park(action, summary, detail)
        decision = await self._registry.wait_async(request_id, self._timeout)
        # _cleanup is called by wait_async() on timeout; call it here on the normal path.
        self._registry._cleanup(request_id)
        self._emit_decided(request_id, action, summary, decision)
        return self._decision_to_result(decision)
