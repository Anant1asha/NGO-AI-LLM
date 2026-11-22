"""Tests for the action approval gate (core/approvals.py) and related hooks.

Covers:
  - PolicyApprover tier-gated behaviour.
  - PermissionGate.require_action tier-gated behaviour.
  - InteractivePermissionGate.require_action delegates to the TUI modal.
  - HandlerApprover maps approve → True, deny → False.
  - RegistryApprover: normal resolve path and timeout-deny path.
  - RegistryApprover.require_async: async-safe variant (REL-001).
  - PendingApprovalRegistry.wait_async: awaitable wait via anyio.
  - Timeout auto-cleanup: timed-out entry removed from registry (REL-001).
  - GoogleService.require_approval delegates to the client approver.
  - UC-PERM-002: UNC path rejection.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

from hachi.core.approvals import (
    HandlerApprover,
    PendingApprovalRegistry,
    PolicyApprover,
    RegistryApprover,
    get_approval_registry,
)
from hachi.core.permissions import (
    InteractivePermissionGate,
    PermissionDecision,
    PermissionGate,
    generate_permissions_og,
)

# ==========================================
# Helpers shared across tests
# ==========================================


def _make_gate(tmp_path: Path, tier: str = "guided") -> PermissionGate:
    """Write a minimal device-permissions.og and return a PermissionGate for it."""
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir(parents=True, exist_ok=True)
    permissions_file = tmp_path / "device-permissions.og"
    permissions_file.write_text(
        generate_permissions_og(tier, custom_paths=[str(allowed_dir)]),
        encoding="utf-8",
    )
    return PermissionGate(permissions_file)


def _noop_emit(name: str, payload: dict) -> None:  # noqa: ARG001
    pass


# ==========================================
# PolicyApprover
# ==========================================


class TestPolicyApprover:
    def test_unrestricted_tier_is_approved(self) -> None:
        approver = PolicyApprover("unrestricted")
        ok, reason = approver.require("send_email", "Send weekly digest")
        assert ok is True
        assert "unrestricted" in reason.lower()

    def test_guided_tier_is_denied(self) -> None:
        approver = PolicyApprover("guided")
        ok, reason = approver.require("trash_file", "Trash old backups")
        assert ok is False
        assert "human approval" in reason.lower()

    def test_sandbox_tier_is_denied(self) -> None:
        approver = PolicyApprover("sandbox")
        ok, reason = approver.require("delete_task", "Remove completed task")
        assert ok is False
        assert "human approval" in reason.lower()

    def test_deny_message_contains_actionable_hint(self) -> None:
        approver = PolicyApprover("guided")
        _, reason = approver.require("share_file", "Share report with team")
        assert "device-permissions.og" in reason or "tier=unrestricted" in reason


# ==========================================
# PermissionGate.require_action
# ==========================================


class TestPermissionGateRequireAction:
    def test_unrestricted_gate_allows(self, tmp_path: Path) -> None:
        gate = _make_gate(tmp_path, tier="unrestricted")
        result = gate.require_action("send_email", "Notify stakeholders")
        assert result.allowed is True
        assert "unrestricted" in result.reason.lower()

    def test_guided_gate_denies(self, tmp_path: Path) -> None:
        gate = _make_gate(tmp_path, tier="guided")
        result = gate.require_action("delete_contact", "Remove duplicate contact")
        assert result.allowed is False
        assert result.reason  # non-empty message

    def test_sandbox_gate_denies(self, tmp_path: Path) -> None:
        gate = _make_gate(tmp_path, tier="sandbox")
        result = gate.require_action("trash_file", "Move to trash")
        assert result.allowed is False


# ==========================================
# InteractivePermissionGate.require_action
# ==========================================


class TestInteractivePermissionGateRequireAction:
    def _make_interactive(
        self,
        tmp_path: Path,
        handler_action: str,
        rationale: str = "test",
    ) -> InteractivePermissionGate:
        base = _make_gate(tmp_path, tier="guided")
        return InteractivePermissionGate(
            base_gate=base,
            approval_handler=lambda _req: PermissionDecision(
                action=handler_action, rationale=rationale
            ),
            event_emitter=_noop_emit,
        )

    def test_approve_returns_allowed_true(self, tmp_path: Path) -> None:
        gate = self._make_interactive(tmp_path, "approve", "approved by test")
        result = gate.require_action("send_email", "Notify team", "Sending weekly report")
        assert result.allowed is True
        assert "approved" in result.reason.lower()

    def test_allow_once_returns_allowed_true(self, tmp_path: Path) -> None:
        gate = self._make_interactive(tmp_path, "allow_once", "one-time allow")
        result = gate.require_action("delete_event", "Delete cancelled meeting")
        assert result.allowed is True

    def test_deny_returns_allowed_false_with_rationale(self, tmp_path: Path) -> None:
        gate = self._make_interactive(tmp_path, "deny", "rejected by user")
        result = gate.require_action("trash_file", "Trash temp files")
        assert result.allowed is False
        assert "rejected by user" in result.reason

    def test_events_are_emitted(self, tmp_path: Path) -> None:
        events: list[tuple[str, dict]] = []
        base = _make_gate(tmp_path, tier="guided")
        gate = InteractivePermissionGate(
            base_gate=base,
            approval_handler=lambda _req: PermissionDecision(action="approve", rationale="ok"),
            event_emitter=lambda name, payload: events.append((name, payload)),
        )
        gate.require_action("share_file", "Share with partner")
        names = [e[0] for e in events]
        assert "permission.requested" in names
        assert "permission.decided" in names


# ==========================================
# HandlerApprover
# ==========================================


class TestHandlerApprover:
    def test_approve_maps_to_true(self) -> None:
        approver = HandlerApprover(
            handler=lambda _req: PermissionDecision(action="approve", rationale="approved"),
            emit=_noop_emit,
        )
        ok, reason = approver.require("send_email", "Send invoice")
        assert ok is True
        assert "approved" in reason.lower()

    def test_allow_once_maps_to_true(self) -> None:
        approver = HandlerApprover(
            handler=lambda _req: PermissionDecision(action="allow_once", rationale="once"),
            emit=_noop_emit,
        )
        ok, _ = approver.require("delete_task", "Remove task")
        assert ok is True

    def test_deny_maps_to_false(self) -> None:
        approver = HandlerApprover(
            handler=lambda _req: PermissionDecision(action="deny", rationale="not allowed"),
            emit=_noop_emit,
        )
        ok, reason = approver.require("trash_file", "Trash files")
        assert ok is False
        assert "not allowed" in reason

    def test_events_are_emitted_on_approve(self) -> None:
        events: list[str] = []
        approver = HandlerApprover(
            handler=lambda _req: PermissionDecision(action="approve"),
            emit=lambda name, _p: events.append(name),
        )
        approver.require("share_file", "Share doc")
        assert "permission.requested" in events
        assert "permission.decided" in events

    def test_handler_exception_produces_deny(self) -> None:
        def bad_handler(_req):
            raise RuntimeError("modal crashed")

        approver = HandlerApprover(handler=bad_handler, emit=_noop_emit)
        ok, reason = approver.require("delete_contact", "Delete contact")
        assert ok is False
        assert "handler error" in reason


# ==========================================
# RegistryApprover
# ==========================================


class TestRegistryApprover:
    def test_resolve_before_timeout_returns_approve(self) -> None:
        registry = PendingApprovalRegistry()
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=5.0)

        def _resolve_after_delay():
            # Let the approver create + park the request first.
            time.sleep(0.05)
            pending = registry.list_pending()
            assert pending, "Expected one pending entry"
            rid = pending[0]["request_id"]
            registry.resolve(rid, PermissionDecision(action="approve", rationale="gateway ok"))

        thread = threading.Thread(target=_resolve_after_delay, daemon=True)
        thread.start()

        ok, reason = approver.require("send_email", "Send email via gateway")
        thread.join(timeout=2.0)
        assert ok is True
        assert "approved" in reason.lower() or "gateway ok" in reason

    def test_resolve_deny_returns_false(self) -> None:
        registry = PendingApprovalRegistry()
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=5.0)

        def _resolve_after_delay():
            time.sleep(0.05)
            pending = registry.list_pending()
            assert pending
            rid = pending[0]["request_id"]
            registry.resolve(rid, PermissionDecision(action="deny", rationale="not permitted"))

        thread = threading.Thread(target=_resolve_after_delay, daemon=True)
        thread.start()

        ok, reason = approver.require("trash_file", "Trash via gateway")
        thread.join(timeout=2.0)
        assert ok is False
        assert "not permitted" in reason

    def test_timeout_returns_deny_with_timed_out_rationale(self) -> None:
        """UC-PERM-005: timeout-driven denial must be distinct from explicit user deny."""
        registry = PendingApprovalRegistry()
        # Very short timeout so the test doesn't block long.
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=0.05)

        ok, reason = approver.require("delete_event", "Delete meeting — nobody resolves")
        assert ok is False
        # The rationale MUST contain "timed out" to distinguish from explicit deny.
        assert "timed out" in reason

    def test_list_pending_returns_unresolved_requests(self) -> None:
        registry = PendingApprovalRegistry()
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=30.0)

        # Start the approver in a background thread (it will block).
        results: list[tuple[bool, str]] = []

        def _run():
            results.append(approver.require("delete_contact", "Delete John Doe"))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        # Give the thread time to park the request.
        time.sleep(0.05)

        pending = registry.list_pending()
        assert len(pending) == 1
        assert pending[0]["tool"] == "delete_contact"

        # Resolve so the thread exits cleanly.
        rid = pending[0]["request_id"]
        registry.resolve(rid, PermissionDecision(action="deny", rationale="cleanup"))
        thread.join(timeout=2.0)

    def test_resolve_returns_false_for_unknown_id(self) -> None:
        registry = PendingApprovalRegistry()
        result = registry.resolve("nonexistent-id", PermissionDecision(action="approve"))
        assert result is False


# ==========================================
# get_approval_registry singleton
# ==========================================


def test_get_approval_registry_returns_singleton() -> None:
    a = get_approval_registry()
    b = get_approval_registry()
    assert a is b


# ==========================================
# GoogleService.require_approval delegation
# ==========================================


class TestGoogleServiceRequireApproval:
    """Verify that GoogleService.require_approval delegates to the client approver."""

    def _make_service(self, client_mock: MagicMock):
        """Build a minimal concrete GoogleService with a fake client."""
        from hachi.integrations.google.service import GoogleService

        class _ConcreteService(GoogleService):
            @property
            def required_scopes(self) -> list[str]:
                return []

            def register_tools(self, registry) -> None:
                pass

        svc = _ConcreteService.__new__(_ConcreteService)
        svc.client = client_mock
        return svc

    def test_delegates_to_client_require_approval(self) -> None:
        client = MagicMock()
        client.require_approval.return_value = (True, "client approved")
        svc = self._make_service(client)

        ok, reason = svc.require_approval("send_email", "Send weekly digest", "detail here")
        assert ok is True
        assert reason == "client approved"
        client.require_approval.assert_called_once_with(
            "send_email", "Send weekly digest", "detail here"
        )

    def test_client_deny_propagates(self) -> None:
        client = MagicMock()
        client.require_approval.return_value = (False, "denied by policy")
        svc = self._make_service(client)

        ok, reason = svc.require_approval("trash_file", "Move to trash")
        assert ok is False
        assert "denied" in reason

    def test_no_approver_on_client_denies(self) -> None:
        """When no approver is wired to the client, destructive action is denied."""
        from hachi.integrations.google.client import GoogleHTTPClient

        # Build a minimal real client (no OAuth call needed for this path).
        client = GoogleHTTPClient.__new__(GoogleHTTPClient)
        client.approver = None  # explicitly no approver

        ok, reason = client.require_approval("send_email", "Send without approver")
        assert ok is False
        assert "No approver connected" in reason


# ==========================================
# UC-PERM-002: UNC path rejection
# ==========================================


class TestUNCPathRejection:
    """UNC network paths must be denied regardless of allowed_paths at any tier."""

    def test_unc_backslash_format_is_denied(self, tmp_path: Path) -> None:
        gate = _make_gate(tmp_path, tier="unrestricted")
        result = gate.check_path(r"\\server\share\file.txt", "read")
        assert result.allowed is False
        assert "UNC" in result.reason

    def test_unc_forward_slash_format_is_denied(self, tmp_path: Path) -> None:
        gate = _make_gate(tmp_path, tier="unrestricted")
        result = gate.check_path("//server/share/file.txt", "read")
        assert result.allowed is False
        assert "UNC" in result.reason

    def test_unc_is_denied_even_at_unrestricted_tier(self, tmp_path: Path) -> None:
        """Critical: unrestricted tier must NOT bypass UNC rejection."""
        gate = _make_gate(tmp_path, tier="unrestricted")
        result = gate.check_path(r"\\192.168.1.1\c$\Windows\System32", "read")
        assert result.allowed is False

    def test_local_path_is_not_misidentified_as_unc(self, tmp_path: Path) -> None:
        """Regression: a normal absolute path starting with one backslash is not UNC."""
        gate = _make_gate(tmp_path, tier="unrestricted")
        # A local path with a drive letter should not be treated as UNC.
        local = tmp_path / "allowed" / "doc.txt"
        local.write_text("ok", encoding="utf-8")
        result = gate.check_path(str(local), "read")
        assert result.allowed is True


# ==========================================
# REL-001: async-safe approval wait
# ==========================================


class TestRegistryApproverAsync:
    """REL-001: require_async / wait_async must not block the event loop."""

    def test_require_async_resolve_before_timeout_returns_approve(self) -> None:
        """Decision delivered before timeout → require_async returns True promptly."""
        registry = PendingApprovalRegistry()
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=5.0)

        async def _run() -> tuple[bool, str]:
            # Resolve the request from a background thread after a short delay.
            def _resolver():
                time.sleep(0.05)
                pending = registry.list_pending()
                assert pending, "Expected one pending entry"
                registry.resolve(
                    pending[0]["request_id"],
                    PermissionDecision(action="approve", rationale="async gateway ok"),
                )

            t = threading.Thread(target=_resolver, daemon=True)
            t.start()
            result = await approver.require_async("send_email", "Send via async gateway")
            t.join(timeout=2.0)
            return result

        ok, reason = asyncio.run(_run())
        assert ok is True
        assert "approved" in reason.lower() or "async gateway ok" in reason

    def test_require_async_timeout_auto_denies_and_cleans_up(self) -> None:
        """Timeout path: require_async denies, cleans up the registry entry (REL-001)."""
        registry = PendingApprovalRegistry()
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=0.05)

        async def _run() -> tuple[bool, str]:
            return await approver.require_async("delete_event", "Delete meeting — no resolver")

        ok, reason = asyncio.run(_run())
        assert ok is False
        assert "timed out" in reason
        # Entry must be removed from the registry after timeout.
        assert registry.list_pending() == []

    def test_two_concurrent_async_waits_complete_independently(self) -> None:
        """Two concurrent require_async calls both complete without blocking each other."""
        registry = PendingApprovalRegistry()
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=5.0)

        async def _run() -> list[tuple[bool, str]]:
            # Schedule two concurrent approval requests.
            async def _task(action: str, summary: str) -> tuple[bool, str]:
                return await approver.require_async(action, summary)

            task_a = asyncio.create_task(_task("send_email", "Send digest"))
            task_b = asyncio.create_task(_task("trash_file", "Trash temp"))

            # Give both tasks time to park their requests before resolving.
            await asyncio.sleep(0.05)

            pending = registry.list_pending()
            assert len(pending) == 2, f"Expected 2 pending, got {len(pending)}"
            for entry in pending:
                registry.resolve(
                    entry["request_id"],
                    PermissionDecision(action="approve", rationale="concurrent ok"),
                )

            return [await task_a, await task_b]

        results = asyncio.run(_run())
        assert all(ok for ok, _ in results), f"Expected both approved, got {results}"

    def test_sync_require_timeout_auto_cleans_up_entry(self) -> None:
        """Sync wait timeout auto-removes the entry so it cannot leak (REL-001)."""
        registry = PendingApprovalRegistry()
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=0.05)

        ok, reason = approver.require("delete_contact", "Delete — no resolver")
        assert ok is False
        assert "timed out" in reason
        # After timeout, the entry must be gone.
        assert registry.list_pending() == []
        # Internal _entries dict must also be empty.
        assert registry._entries == {}

    def test_wait_async_unknown_request_id_returns_deny(self) -> None:
        """wait_async with an unknown ID returns a deny immediately."""
        registry = PendingApprovalRegistry()

        async def _run() -> PermissionDecision:
            return await registry.wait_async("nonexistent-id", timeout=5.0)

        decision = asyncio.run(_run())
        assert decision.action == "deny"
        assert "unknown request_id" in (decision.rationale or "")
