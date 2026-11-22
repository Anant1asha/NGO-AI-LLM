"""Tests for CockpitScreen auto-refresh, capability toggle, and authoring hooks.

Coverage
--------
Offline (CockpitData(None)):
  - _auto_refresh runs without error and skips re-populate when a modal screen
    is on top.
  - decide_top dispatches the approval decision and shows a toast.
  - toggle_capability on a capability row runs without error and shows a toast.
  - authoring_apply / authoring_revert run without error and show a toast.

Live (real gateway):
  - Capability toggle round-trips through the gateway: enabled flag flips on
    re-fetch via GatewayClient.

Run with::

    PYTHONPATH=src python -m pytest tests/test_cockpit_live_refresh.py -q

"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helper — probe whether a live gateway can start (used in skipif below)
# ---------------------------------------------------------------------------


def _can_start_live_gateway() -> bool:
    """Return True when the gateway can be started for live tests.

    Avoids importing heavy gateway deps at collection time by using a bare
    try/except; returns False if anything is missing or misconfigured.
    """
    try:
        from hachi.cli.main import (  # noqa: F401
            _resolve_gateway_auth_token,
            _start_gateway_server,
        )

        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _screen(pilot: Any) -> Any:  # type: ignore[no-untyped-def]
    return pilot.app.screen


# ---------------------------------------------------------------------------
# Offline tests
# ---------------------------------------------------------------------------


class TestAutoRefreshOffline:
    """_auto_refresh works in offline mode and respects the modal guard."""

    def test_auto_refresh_runs_without_error(self) -> None:
        """_auto_refresh should complete silently in offline mode."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                # Navigate to connections so the active view is a data view.
                await pilot.press("g")
                await pilot.press("n")
                await pilot.pause()
                screen = _screen(pilot)
                # Call directly — should not raise.
                screen._cockpit_auto_refresh()
                await pilot.pause()

        _run(_body())

    def test_auto_refresh_skips_populate_under_modal(self) -> None:
        """When a modal screen is on top, _auto_refresh must not call populate
        on the view (so it doesn't trample the modal's UI state).
        """

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                await pilot.press("g")
                await pilot.press("n")
                await pilot.pause()
                screen = _screen(pilot)

                # Push a fake modal so app.screen is no longer CockpitScreen.
                from textual.screen import Screen

                class _FakeModal(Screen[None]):  # type: ignore[misc]
                    def compose(self):  # type: ignore[no-untyped-def]
                        from textual.widgets import Static
                        yield Static("modal")

                pilot.app.push_screen(_FakeModal())
                await pilot.pause()

                # app.screen is now the modal, not CockpitScreen.
                assert pilot.app.screen is not screen

                # Track whether populate was called.
                called: list[bool] = []
                original_populate = screen._populate_current_view

                def _spy_populate() -> None:
                    called.append(True)
                    original_populate()

                screen._populate_current_view = _spy_populate  # type: ignore[method-assign]
                screen._cockpit_auto_refresh()
                await pilot.pause()

                # Under modal, populate must NOT have been called.
                assert called == [], "_auto_refresh should skip populate under modal"

        _run(_body())

    def test_auto_refresh_skips_populate_in_chat_view(self) -> None:
        """When the chat view is active, _auto_refresh must not re-populate it
        (chat owns its own SSE stream).
        """

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                await pilot.press("g")
                await pilot.press("c")
                await pilot.pause()
                screen = _screen(pilot)
                assert screen._current_view == "chat"

                called: list[bool] = []
                original_populate = screen._populate_current_view

                def _spy_populate() -> None:
                    called.append(True)
                    original_populate()

                screen._populate_current_view = _spy_populate  # type: ignore[method-assign]
                screen._cockpit_auto_refresh()
                await pilot.pause()

                assert called == [], "_auto_refresh should skip populate for chat view"

        _run(_body())


class TestDecideTopOffline:
    """decide_top dispatches approval decision and shows toast via screen."""

    def test_decide_top_allow_shows_toast(self) -> None:
        """Pressing y on approvals view calls decide_top + refreshes trust bar."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                await pilot.press("g")
                await pilot.press("p")
                await pilot.pause()
                screen = _screen(pilot)

                toasts: list[str] = []
                original_notify = screen.notify_toast

                def _spy_toast(text: str, **kwargs: Any) -> None:
                    toasts.append(text)
                    original_notify(text, **kwargs)

                screen.notify_toast = _spy_toast  # type: ignore[method-assign]
                screen._handle_decide_top(screen._active_view(), "allow")
                await pilot.pause()

                assert any("allow" in t.lower() for t in toasts), (
                    f"Expected a toast mentioning 'allow', got: {toasts}"
                )

        _run(_body())

    def test_decide_top_deny_shows_toast(self) -> None:
        """deny action also produces a toast."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                await pilot.press("g")
                await pilot.press("p")
                await pilot.pause()
                screen = _screen(pilot)

                toasts: list[str] = []
                original_notify = screen.notify_toast

                def _spy_toast(text: str, **kwargs: Any) -> None:
                    toasts.append(text)
                    original_notify(text, **kwargs)

                screen.notify_toast = _spy_toast  # type: ignore[method-assign]
                screen._handle_decide_top(screen._active_view(), "deny")
                await pilot.pause()

                assert any("den" in t.lower() for t in toasts), (
                    f"Expected a toast mentioning 'denied', got: {toasts}"
                )

        _run(_body())


class TestToggleCapabilityOffline:
    """toggle_capability runs without error in offline mode and shows a toast."""

    def test_toggle_capability_offline_no_crash(self) -> None:
        """toggle_capability on a placeholder capability row does not raise."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                await pilot.press("g")
                await pilot.press("n")
                await pilot.pause()
                screen = _screen(pilot)
                view = screen._active_view()
                assert view is not None, "connections view should be active"

                toasts: list[str] = []
                original_notify = screen.notify_toast

                def _spy_toast(text: str, **kwargs: Any) -> None:
                    toasts.append(text)
                    original_notify(text, **kwargs)

                screen.notify_toast = _spy_toast  # type: ignore[method-assign]
                # In offline mode, set_capability is a no-op — but should not crash.
                view.toggle_capability()  # type: ignore[union-attr]
                await pilot.pause()
                # At least one toast emitted (either "enabled/disabled" or "MCP server hint").
                assert len(toasts) > 0, "Expected at least one toast after toggle_capability"

        _run(_body())


class TestAuthoringActionsOffline:
    """authoring_apply / authoring_revert run without error and emit a toast."""

    def test_authoring_apply_offline_no_crash(self) -> None:
        """authoring_apply on governance view does not raise in offline mode."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                await pilot.press("g")
                await pilot.press("g")
                await pilot.pause()
                screen = _screen(pilot)
                view = screen._active_view()
                assert view is not None, "governance view should be active"

                toasts: list[str] = []
                original_notify = screen.notify_toast

                def _spy_toast(text: str, **kwargs: Any) -> None:
                    toasts.append(text)
                    original_notify(text, **kwargs)

                screen.notify_toast = _spy_toast  # type: ignore[method-assign]
                view.authoring_apply()  # type: ignore[union-attr]
                await pilot.pause()
                assert len(toasts) > 0, "Expected a toast after authoring_apply"

        _run(_body())

    def test_authoring_revert_offline_no_crash(self) -> None:
        """authoring_revert on governance view does not raise in offline mode."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            async with CockpitApp().run_test(headless=True) as pilot:
                await pilot.press("g")
                await pilot.press("g")
                await pilot.pause()
                screen = _screen(pilot)
                view = screen._active_view()
                assert view is not None, "governance view should be active"

                toasts: list[str] = []
                original_notify = screen.notify_toast

                def _spy_toast(text: str, **kwargs: Any) -> None:
                    toasts.append(text)
                    original_notify(text, **kwargs)

                screen.notify_toast = _spy_toast  # type: ignore[method-assign]
                view.authoring_revert()  # type: ignore[union-attr]
                await pilot.pause()
                assert len(toasts) > 0, "Expected a toast after authoring_revert"

        _run(_body())


# ---------------------------------------------------------------------------
# Live gateway test — capability toggle round-trip
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _can_start_live_gateway(),
    reason="Live gateway cannot start in this environment",
)
class TestCapabilityToggleLive:
    """Capability toggle round-trips through the real gateway."""

    def test_capability_toggle_round_trip(self) -> None:
        """Enable a capability via toggle_capability; re-fetch confirms the flip."""
        from hachi.cli.main import _resolve_gateway_auth_token, _start_gateway_server
        from hachi.client.gateway import GatewayClient
        from hachi.tui.cockpit.data import CockpitData

        server = None
        try:
            token = _resolve_gateway_auth_token("127.0.0.1")
            server, base_url, runtime = _start_gateway_server(
                host="127.0.0.1", port=0, attach_runtime=True
            )
            client = GatewayClient(base_url=base_url, token=token)
            data = CockpitData(client)

            caps = data.capabilities()
            if not caps:
                pytest.skip("No capabilities returned by gateway")

            # Pick first capability.
            cap = caps[0]
            initial_enabled = cap.enabled
            target_enabled = not initial_enabled

            # Toggle via data facade.
            data.set_capability(cap.id, target_enabled)

            # Re-fetch — the flag should have flipped.
            fresh_caps = data.capabilities()
            fresh_cap = next((c for c in fresh_caps if c.id == cap.id), None)
            assert fresh_cap is not None, f"Capability {cap.id!r} not found after re-fetch"
            assert fresh_cap.enabled == target_enabled, (
                f"Expected enabled={target_enabled} after toggle, "
                f"got {fresh_cap.enabled}"
            )

        finally:
            if server is not None:
                try:
                    server.stop()
                except Exception:
                    pass
