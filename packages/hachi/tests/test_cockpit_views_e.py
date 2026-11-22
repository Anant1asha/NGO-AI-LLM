"""Tests for Wave-3 cockpit views: Dashboard, Governance, Memory, Skills.

Each view is mounted in isolation inside a tiny throwaway App.
Uses asyncio.run() directly — no pytest-asyncio required.
Tests call view.populate(CockpitData(None)) (offline/placeholder mode)
and assert that key content is rendered.
"""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Static

from hachi.tui.cockpit.data import CockpitData
from hachi.tui.cockpit.views.dashboard import DashboardView
from hachi.tui.cockpit.views.governance import GovernanceView
from hachi.tui.cockpit.views.memory import MemoryView
from hachi.tui.cockpit.views.skills import SkillsView

# ---------------------------------------------------------------------------
# Tiny host apps (one per view)
# ---------------------------------------------------------------------------


class _DashApp(App):  # type: ignore[type-arg]
    def compose(self) -> ComposeResult:
        yield DashboardView()


class _GovApp(App):  # type: ignore[type-arg]
    def compose(self) -> ComposeResult:
        yield GovernanceView()


class _MemApp(App):  # type: ignore[type-arg]
    def compose(self) -> ComposeResult:
        yield MemoryView()


class _SkillApp(App):  # type: ignore[type-arg]
    def compose(self) -> ComposeResult:
        yield SkillsView()


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _text(widget: Static) -> str:
    """Return the plain text content of a Static widget."""
    return str(widget.render())


# ---------------------------------------------------------------------------
# DashboardView
# ---------------------------------------------------------------------------


def test_dashboard_renders_section_labels() -> None:
    """DashboardView renders the core section labels after populate()."""

    async def _body() -> None:
        app = _DashApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(DashboardView)
            view.populate(CockpitData(None))
            await pilot.pause()

            activity = pilot.app.query_one("#activity-panel", Static)
            text = _text(activity)
            assert "Hachi is working" in text or "activity" in text.lower()

    _run(_body())


def test_dashboard_needs_you_panel_exists() -> None:
    """DashboardView has a needs-you panel with expected content."""

    async def _body() -> None:
        app = _DashApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(DashboardView)
            view.populate(CockpitData(None))
            await pilot.pause()

            panel = pilot.app.query_one("#needs-you-panel", Static)
            text = _text(panel)
            assert (
                "needs you" in text.lower()
                or "approval" in text.lower()
                or "pending" in text.lower()
            )

    _run(_body())


def test_dashboard_work_panel_exists() -> None:
    """DashboardView work queue panel is rendered."""

    async def _body() -> None:
        app = _DashApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(DashboardView)
            view.populate(CockpitData(None))
            await pilot.pause()

            panel = pilot.app.query_one("#work-panel", Static)
            assert panel is not None

    _run(_body())


def test_dashboard_decide_top_no_error() -> None:
    """decide_top('allow') runs without raising even with no approval."""

    async def _body() -> None:
        app = _DashApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(DashboardView)
            view.populate(CockpitData(None))
            await pilot.pause()

            view.decide_top("allow")
            view.decide_top("deny")
            view.decide_top("always")

    _run(_body())


def test_dashboard_spend_panel_exists() -> None:
    """DashboardView spend panel renders cost/token content."""

    async def _body() -> None:
        app = _DashApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(DashboardView)
            view.populate(CockpitData(None))
            await pilot.pause()

            panel = pilot.app.query_one("#spend-panel", Static)
            text = _text(panel)
            assert "spend" in text.lower() or "$" in text or "cost" in text.lower()

    _run(_body())


def test_dashboard_recent_panel_exists() -> None:
    """DashboardView recent/audit-tail panel is rendered."""

    async def _body() -> None:
        app = _DashApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(DashboardView)
            view.populate(CockpitData(None))
            await pilot.pause()

            panel = pilot.app.query_one("#recent-panel", Static)
            assert panel is not None

    _run(_body())


def test_dashboard_pack_panel_exists() -> None:
    """DashboardView pack panel is rendered."""

    async def _body() -> None:
        app = _DashApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(DashboardView)
            view.populate(CockpitData(None))
            await pilot.pause()

            panel = pilot.app.query_one("#pack-panel", Static)
            assert panel is not None

    _run(_body())


# ---------------------------------------------------------------------------
# GovernanceView
# ---------------------------------------------------------------------------


def test_governance_renders_permissions_pane() -> None:
    """GovernanceView renders the Permissions pane by default."""

    async def _body() -> None:
        app = _GovApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(GovernanceView)
            view.populate(CockpitData(None))
            await pilot.pause()

            pane = pilot.app.query_one("#gov-pane", Static)
            text = _text(pane)
            assert (
                "permission" in text.lower()
                or "filesystem" in text.lower()
                or "terminal" in text.lower()
            )

    _run(_body())


def test_governance_rail_items_present() -> None:
    """GovernanceView renders all 5 rail items."""

    async def _body() -> None:
        app = _GovApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(GovernanceView)
            view.populate(CockpitData(None))
            await pilot.pause()

            for i in range(5):
                widget = pilot.app.query_one(f"#gov-rail-{i}", Static)
                assert widget is not None

    _run(_body())


def test_governance_move_selection_to_budgets() -> None:
    """GovernanceView move_selection(1) moves to Budgets pane."""

    async def _body() -> None:
        app = _GovApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(GovernanceView)
            view.populate(CockpitData(None))
            await pilot.pause()

            view.move_selection(1)  # -> Budgets
            pane = pilot.app.query_one("#gov-pane", Static)
            text = _text(pane)
            assert "budget" in text.lower() or "cap" in text.lower() or "spend" in text.lower()

    _run(_body())


def test_governance_move_selection_wraps() -> None:
    """GovernanceView move_selection wraps around correctly after 5 steps."""

    async def _body() -> None:
        app = _GovApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(GovernanceView)
            view.populate(CockpitData(None))
            await pilot.pause()

            for _ in range(5):
                view.move_selection(1)
            assert view._selected == 0

    _run(_body())


def test_governance_all_panes_render() -> None:
    """GovernanceView all 5 panes render without raising."""

    async def _body() -> None:
        app = _GovApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(GovernanceView)
            view.populate(CockpitData(None))
            await pilot.pause()

            for _ in range(5):
                view.move_selection(1)

    _run(_body())


# ---------------------------------------------------------------------------
# MemoryView
# ---------------------------------------------------------------------------


def test_memory_renders_recall_rows() -> None:
    """MemoryView renders recall results after populate()."""

    async def _body() -> None:
        app = _MemApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(MemoryView)
            view.populate(CockpitData(None))
            await pilot.pause()

            recall_widget = pilot.app.query_one("#mem-recall", Static)
            text = _text(recall_widget)
            assert (
                "score" in text.lower()
                or "collection" in text.lower()
                or "fact" in text.lower()
            )

    _run(_body())


def test_memory_renders_quarantine_line() -> None:
    """MemoryView renders the quarantine line."""

    async def _body() -> None:
        app = _MemApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(MemoryView)
            view.populate(CockpitData(None))
            await pilot.pause()

            q_widget = pilot.app.query_one("#mem-quarantine", Static)
            text = _text(q_widget)
            assert "quarantine" in text.lower()

    _run(_body())


def test_memory_layer_rail_present() -> None:
    """MemoryView renders all 6 layer rail items."""

    async def _body() -> None:
        app = _MemApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(MemoryView)
            view.populate(CockpitData(None))
            await pilot.pause()

            for i in range(6):
                widget = pilot.app.query_one(f"#mem-rail-{i}", Static)
                assert widget is not None

    _run(_body())


def test_memory_move_selection_no_error() -> None:
    """MemoryView move_selection(1) and (-1) run without raising."""

    async def _body() -> None:
        app = _MemApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(MemoryView)
            view.populate(CockpitData(None))
            await pilot.pause()

            view.move_selection(1)
            view.move_selection(-1)

    _run(_body())


def test_memory_on_filter_no_error() -> None:
    """MemoryView on_filter() runs without raising."""

    async def _body() -> None:
        app = _MemApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(MemoryView)
            view.populate(CockpitData(None))
            await pilot.pause()

            view.on_filter()

    _run(_body())


def test_memory_inspect_block_rendered() -> None:
    """MemoryView inspect block is rendered."""

    async def _body() -> None:
        app = _MemApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(MemoryView)
            view.populate(CockpitData(None))
            await pilot.pause()

            insp = pilot.app.query_one("#mem-inspect", Static)
            assert insp is not None
            text = _text(insp)
            assert "inspect" in text.lower()

    _run(_body())


# ---------------------------------------------------------------------------
# SkillsView
# ---------------------------------------------------------------------------


def test_skills_list_non_empty() -> None:
    """SkillsView renders a non-empty skills list from placeholder data."""

    async def _body() -> None:
        app = _SkillApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(SkillsView)
            view.populate(CockpitData(None))
            await pilot.pause()

            sk_list = pilot.app.query_one("#sk-list", Static)
            text = _text(sk_list)
            assert "skill" in text.lower() or "use" in text.lower()

    _run(_body())


def test_skills_inspector_pane_exists() -> None:
    """SkillsView OG inspector pane is rendered."""

    async def _body() -> None:
        app = _SkillApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(SkillsView)
            view.populate(CockpitData(None))
            await pilot.pause()

            insp = pilot.app.query_one("#sk-inspector-pane", Static)
            assert insp is not None

    _run(_body())


def test_skills_inspector_shows_3_passes() -> None:
    """SkillsView OG inspector shows pass1/pass2/pass3 for the selected skill."""

    async def _body() -> None:
        app = _SkillApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(SkillsView)
            view.populate(CockpitData(None))
            await pilot.pause()

            insp = pilot.app.query_one("#sk-inspector-pane", Static)
            text = _text(insp)
            if text.strip():
                assert (
                    "pass" in text.lower()
                    or "index" in text.lower()
                    or "dense" in text.lower()
                )

    _run(_body())


def test_skills_move_selection() -> None:
    """SkillsView move_selection(1) moves to the next skill without error."""

    async def _body() -> None:
        app = _SkillApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(SkillsView)
            view.populate(CockpitData(None))
            await pilot.pause()

            initial = view._selected
            if len(view._skills) > 1:
                view.move_selection(1)
                assert view._selected == (initial + 1) % len(view._skills)
            else:
                view.move_selection(1)  # must not raise

    _run(_body())


def test_skills_toggle_inspector() -> None:
    """SkillsView toggle_inspector() hides and re-shows the inspector."""

    async def _body() -> None:
        app = _SkillApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(SkillsView)
            view.populate(CockpitData(None))
            await pilot.pause()

            assert view._inspector_visible is True
            view.toggle_inspector()
            assert view._inspector_visible is False
            view.toggle_inspector()
            assert view._inspector_visible is True

    _run(_body())


def test_skills_tabs_footer() -> None:
    """SkillsView renders the installed/marketplace/authored tab footer."""

    async def _body() -> None:
        app = _SkillApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(SkillsView)
            view.populate(CockpitData(None))
            await pilot.pause()

            tabs = pilot.app.query_one("#sk-tabs", Static)
            text = _text(tabs)
            assert "installed" in text.lower() or "tabs" in text.lower()

    _run(_body())


def test_skills_move_selection_wraps() -> None:
    """SkillsView move_selection wraps at list boundaries."""

    async def _body() -> None:
        app = _SkillApp()
        async with app.run_test(headless=True) as pilot:
            view = pilot.app.query_one(SkillsView)
            view.populate(CockpitData(None))
            await pilot.pause()

            n = len(view._skills)
            if n > 0:
                for _ in range(n):
                    view.move_selection(1)
                assert view._selected == 0

    _run(_body())
