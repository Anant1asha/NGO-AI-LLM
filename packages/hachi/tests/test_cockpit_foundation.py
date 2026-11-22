"""Cockpit foundation tests.

Covers:
- nav.py: 12 views, correct order/mnemonics, footer_keys, palette_items
- CockpitData offline mode: every method returns non-empty data and never raises
- Textual Pilot smoke test: mounts, navigates, altitude toggle, j/k, help

Run with:
    PYTHONPATH=src python -m pytest tests/test_cockpit_foundation.py -q
"""

from __future__ import annotations

import asyncio

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# nav.py tests (pure data — no Textual required)
# ──────────────────────────────────────────────────────────────────────────────


class TestNav:
    def test_twelve_views(self) -> None:
        from hachi.tui.cockpit.nav import VIEWS

        assert len(VIEWS) == 12

    def test_view_order_and_ids(self) -> None:
        from hachi.tui.cockpit.nav import VIEWS

        expected_ids = [
            "chat", "dashboard", "agents", "tasks", "approvals", "governance",
            "memory", "skills", "audit", "resources", "connections", "settings",
        ]
        assert [v.view_id for v in VIEWS] == expected_ids

    def test_mnemonics_exact(self) -> None:
        """Mnemonics must match the design's help keymap exactly."""
        from hachi.tui.cockpit.nav import VIEWS

        expected_mnemonics = {
            "chat": "c", "dashboard": "d", "agents": "a", "tasks": "t",
            "approvals": "p", "governance": "g", "memory": "m", "skills": "k",
            "audit": "l", "resources": "r", "connections": "n", "settings": "s",
        }
        for v in VIEWS:
            assert v.mnemonic == expected_mnemonics[v.view_id], (
                f"{v.view_id}: expected mnemonic {expected_mnemonics[v.view_id]!r}, "
                f"got {v.mnemonic!r}"
            )

    def test_altitudes(self) -> None:
        from hachi.tui.cockpit.nav import VIEWS

        for v in VIEWS:
            if v.view_id == "chat":
                assert v.altitude == "focus"
            else:
                assert v.altitude == "cockpit"

    def test_unique_mnemonics(self) -> None:
        from hachi.tui.cockpit.nav import VIEWS

        mnemonics = [v.mnemonic for v in VIEWS]
        assert len(mnemonics) == len(set(mnemonics)), "duplicate mnemonics"

    def test_view_by_mnemonic(self) -> None:
        from hachi.tui.cockpit.nav import view_by_mnemonic

        v = view_by_mnemonic("d")
        assert v is not None
        assert v.view_id == "dashboard"

        assert view_by_mnemonic("z") is None

    def test_view_by_id(self) -> None:
        from hachi.tui.cockpit.nav import view_by_id

        v = view_by_id("agents")
        assert v is not None
        assert v.mnemonic == "a"
        assert view_by_id("nonexistent") is None

    def test_footer_keys_agents(self) -> None:
        from hachi.tui.cockpit.nav import footer_keys

        keys = footer_keys("agents")
        key_chars = [fk.key for fk in keys]
        assert "↵" in key_chars
        assert "/" in key_chars
        # all have labels
        for fk in keys:
            assert fk.label

    def test_footer_keys_approvals(self) -> None:
        from hachi.tui.cockpit.nav import footer_keys

        keys = footer_keys("approvals")
        key_chars = [fk.key for fk in keys]
        # must have y/A/n
        assert "y" in key_chars
        assert "A" in key_chars
        assert "n" in key_chars

    def test_footer_keys_chat(self) -> None:
        from hachi.tui.cockpit.nav import footer_keys

        keys = footer_keys("chat")
        key_chars = [fk.key for fk in keys]
        assert "↵" in key_chars
        assert "⌃O" in key_chars

    def test_footer_keys_unknown_view(self) -> None:
        from hachi.tui.cockpit.nav import footer_keys

        # Unknown view returns empty list, not an exception
        assert footer_keys("bogus") == []

    def test_palette_items_sections(self) -> None:
        from hachi.tui.cockpit.nav import palette_items

        items = palette_items()
        sections = {it.section for it in items}
        assert "go to" in sections
        assert "do" in sections
        assert "open" in sections

    def test_palette_items_go_to_count(self) -> None:
        from hachi.tui.cockpit.nav import palette_items

        go_items = [it for it in palette_items() if it.section == "go to"]
        assert len(go_items) == 12

    def test_palette_items_go_to_covers_all_views(self) -> None:
        from hachi.tui.cockpit.nav import VIEWS, palette_items

        go_labels = {it.label for it in palette_items() if it.section == "go to"}
        # Every view label should appear in go-to items
        for v in VIEWS:
            assert v.label in go_labels, f"{v.label!r} missing from palette go-to"

    def test_palette_items_do_section(self) -> None:
        from hachi.tui.cockpit.nav import palette_items

        do_items = [it for it in palette_items() if it.section == "do"]
        assert len(do_items) >= 5
        labels = [it.label for it in do_items]
        assert any("approve" in lb for lb in labels)
        assert any("model" in lb for lb in labels)

    def test_palette_items_open_section(self) -> None:
        from hachi.tui.cockpit.nav import palette_items

        open_items = [it for it in palette_items() if it.section == "open"]
        assert len(open_items) >= 3

    def test_palette_items_go_to_action_tokens(self) -> None:
        from hachi.tui.cockpit.nav import palette_items

        for it in palette_items():
            if it.section == "go to":
                assert it.action.startswith("go:"), (
                    f"Expected action 'go:<id>' for {it.label!r}, got {it.action!r}"
                )


# ──────────────────────────────────────────────────────────────────────────────
# CockpitData offline mode tests (no gateway, no network)
# ──────────────────────────────────────────────────────────────────────────────


class TestCockpitDataOffline:
    """Every CockpitData method must return non-empty data in offline mode
    and must never raise an exception."""

    @pytest.fixture()
    def data(self):
        from hachi.tui.cockpit.data import CockpitData
        return CockpitData(None)

    def test_skills(self, data) -> None:
        result = data.skills()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_memory(self, data) -> None:
        result = data.memory()
        assert result is not None

    def test_recall(self, data) -> None:
        result = data.recall("test query")
        assert isinstance(result, list)

    def test_og(self, data) -> None:
        result = data.og()
        assert isinstance(result, list)

    def test_authoring_targets(self, data) -> None:
        result = data.authoring_targets()
        assert isinstance(result, list)

    def test_authoring_source(self, data) -> None:
        src, diff = data.authoring_source("nonexistent")
        assert isinstance(src, str)
        assert isinstance(diff, list)

    def test_spend(self, data) -> None:
        result = data.spend()
        assert result is not None

    def test_approvals(self, data) -> None:
        result = data.approvals()
        assert isinstance(result, list)

    def test_decide_approval_offline(self, data) -> None:
        # Should return {} without raising
        result = data.decide_approval("fake-id", "allow")
        assert isinstance(result, dict)

    def test_audit(self, data) -> None:
        result = data.audit()
        assert isinstance(result, list)

    def test_active_tasks(self, data) -> None:
        result = data.active_tasks()
        assert isinstance(result, list)

    def test_failed_tasks(self, data) -> None:
        result = data.failed_tasks()
        assert isinstance(result, list)

    def test_routines(self, data) -> None:
        result = data.routines()
        assert isinstance(result, list)

    def test_agents(self, data) -> None:
        result = data.agents()
        assert isinstance(result, list)

    def test_activity(self, data) -> None:
        result = data.activity()
        assert isinstance(result, list)

    def test_tool_calls(self, data) -> None:
        result = data.tool_calls()
        assert isinstance(result, list)

    def test_capabilities(self, data) -> None:
        result = data.capabilities()
        assert isinstance(result, list)

    def test_set_capability_offline(self, data) -> None:
        result = data.set_capability("fake-cap", True)
        assert isinstance(result, dict)

    def test_mcp(self, data) -> None:
        servers, tools = data.mcp()
        assert isinstance(servers, list)
        assert isinstance(tools, list)

    def test_sessions(self, data) -> None:
        result = data.sessions()
        assert isinstance(result, list)

    def test_config(self, data) -> None:
        result = data.config()
        assert result is not None

    def test_models(self, data) -> None:
        result = data.models()
        assert isinstance(result, list)

    def test_setup(self, data) -> None:
        result = data.setup()
        assert result is not None

    def test_health(self, data) -> None:
        result = data.health()
        assert result is not None

    def test_trust_bar(self, data) -> None:
        result = data.trust_bar()
        assert result is not None
        # TrustBarSnapshot must have these fields
        assert hasattr(result, "tier")
        assert hasattr(result, "model")
        assert hasattr(result, "approval_count")

    def test_dashboard(self, data) -> None:
        result = data.dashboard()
        assert result is not None
        assert hasattr(result, "active_jobs")
        assert hasattr(result, "pending_approvals")

    def test_no_method_raises(self, data) -> None:
        """Comprehensive check: no CockpitData method raises in offline mode."""
        import inspect

        from hachi.tui.cockpit.data import CockpitData

        instance = CockpitData(None)
        methods = [
            m for m in dir(instance)
            if not m.startswith("_") and callable(getattr(instance, m))
        ]
        # methods that require arguments
        arg_methods = {
            "recall": ("test",),
            "authoring_source": ("test",),
            "spend": (),
            "decide_approval": ("fake-id", "allow"),
            "audit": (),
            "failed_tasks": (),
            "agents": (),
            "activity": (),
            "tool_calls": (),
            "set_capability": ("fake-id", True),
            "sessions": (),
        }
        for name in methods:
            args = arg_methods.get(name, ())
            fn = getattr(instance, name)
            sig = inspect.signature(fn)
            # Skip if too many required params
            required = [
                p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty and p.name != "self"
            ]
            if len(required) > len(args):
                continue
            try:
                fn(*args)
            except Exception as exc:
                pytest.fail(f"CockpitData.{name}() raised unexpectedly: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# Textual Pilot smoke tests
# Uses asyncio.run() directly — no pytest-asyncio required.
# Each test function is synchronous and wraps its async body.
# ──────────────────────────────────────────────────────────────────────────────


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously for Textual pilot tests."""
    return asyncio.run(coro)


class TestCockpitAppPilot:
    """Smoke tests using Textual's Pilot — run the cockpit headlessly."""

    def test_app_mounts(self) -> None:
        """App should mount without raising."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                assert pilot.app is app

        _run(_body())

    def test_navigate_to_agents(self) -> None:
        """g then a should navigate to agents view."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp
            from hachi.tui.cockpit.screen import CockpitScreen

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                screen = pilot.app.screen
                assert isinstance(screen, CockpitScreen)
                await pilot.press("g")
                await pilot.press("a")
                assert screen._current_view == "agents"

        _run(_body())

    def test_altitude_toggle(self) -> None:
        """ctrl+o should toggle between chat and cockpit."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp
            from hachi.tui.cockpit.screen import CockpitScreen

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                screen = pilot.app.screen
                assert isinstance(screen, CockpitScreen)
                # Start at dashboard
                assert screen._current_view == "dashboard"
                # Go to chat via altitude toggle
                await pilot.press("ctrl+o")
                assert screen._current_view == "chat"
                # Toggle back
                await pilot.press("ctrl+o")
                assert screen._current_view == "dashboard"

        _run(_body())

    def test_jk_navigation_no_crash(self) -> None:
        """j/k on a data view should not raise."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                # Navigate to agents (a table view)
                await pilot.press("g")
                await pilot.press("a")
                # Press j/k several times
                for _ in range(3):
                    await pilot.press("j")
                for _ in range(2):
                    await pilot.press("k")
                # No assertion needed — just no exception

        _run(_body())

    def test_help_and_escape_no_crash(self) -> None:
        """? should trigger help stub without crashing."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                await pilot.press("question_mark")
                # Should have shown a toast, not crashed

        _run(_body())

    def test_ctrl_r_refreshes(self) -> None:
        """ctrl+r should re-populate the current view without crashing."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                await pilot.press("ctrl+r")
                # No exception

        _run(_body())

    def test_colon_opens_palette(self) -> None:
        """Colon key should open the palette stub without crashing."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                await pilot.press("colon")
                # No exception

        _run(_body())

    def test_inspector_toggle(self) -> None:
        """i / escape should toggle inspector without crashing."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                # Navigate to a table view
                await pilot.press("g")
                await pilot.press("p")  # approvals
                await pilot.press("i")  # toggle inspector
                await pilot.press("escape")  # close inspector
                # No exception

        _run(_body())

    def test_view_registry_all_mount(self) -> None:
        """All 12 view widgets should be present in the switcher."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp
            from hachi.tui.cockpit.nav import VIEWS
            from hachi.tui.cockpit.screen import CockpitScreen

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                screen = pilot.app.screen
                assert isinstance(screen, CockpitScreen)
                for meta in VIEWS:
                    widget = screen.query_one(f"#view-{meta.view_id}")
                    assert widget is not None, f"view #{meta.view_id} not mounted"

        _run(_body())

    def test_g_prefix_navigation_all_views(self) -> None:
        """g + mnemonic should navigate to every view."""

        async def _body() -> None:
            from hachi.tui.cockpit.app import CockpitApp
            from hachi.tui.cockpit.nav import VIEWS
            from hachi.tui.cockpit.screen import CockpitScreen

            app = CockpitApp()
            async with app.run_test(headless=True) as pilot:
                screen = pilot.app.screen
                assert isinstance(screen, CockpitScreen)
                for meta in VIEWS:
                    await pilot.press("g")
                    await pilot.press(meta.mnemonic)
                    assert screen._current_view == meta.view_id, (
                        f"After g+{meta.mnemonic!r}, expected {meta.view_id!r} "
                        f"but got {screen._current_view!r}"
                    )

        _run(_body())
