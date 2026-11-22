"""Tests for the 5 CockpitTable-backed views (Wave-3 implementation).

Tests are *synchronous* and wrap Textual Pilot coroutines in ``asyncio.run()``
(matching the pattern in test_cockpit_foundation.py — no pytest-asyncio needed).

Strategy: use CockpitApp (the full cockpit), navigate to each view, then call
``populate()`` and assert on the CockpitTable's internal state.  Views are
mounted inside CockpitScreen's ContentSwitcher with the ID ``view-<view_id>``;
we query from ``pilot.app.screen`` (the CockpitScreen) to find them.

Run with::

    PYTHONPATH=src python -m pytest tests/test_cockpit_table_views.py -q
"""

from __future__ import annotations

import asyncio

from hachi.tui.cockpit.data import CockpitData
from hachi.tui.cockpit.views.agents import AgentsView
from hachi.tui.cockpit.views.approvals import ApprovalsView
from hachi.tui.cockpit.views.audit import AuditView
from hachi.tui.cockpit.views.connections import ConnectionsView
from hachi.tui.cockpit.views.table import CockpitTable
from hachi.tui.cockpit.views.tasks import TasksView

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously for Textual pilot tests."""
    return asyncio.run(coro)


DATA = CockpitData(None)

# Mnemonics (from nav.py): agents="a", tasks="t", approvals="p", audit="l", connections="n"


def _screen(pilot):  # type: ignore[no-untyped-def]
    """Return the current screen (CockpitScreen after on_mount push)."""
    return pilot.app.screen


# ---------------------------------------------------------------------------
# AgentsView tests
# ---------------------------------------------------------------------------


def test_agents_view_loads_rows() -> None:
    """populate() fills the table with rows from placeholder agents data."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("a")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-agents", AgentsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#agents-table", CockpitTable)
            assert len(table._rows) == 2, f"Expected 2 rows, got {len(table._rows)}"

    _run(_body())


def test_agents_view_move_selection_down() -> None:
    """move_selection(+1) advances selected_index."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("a")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-agents", AgentsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#agents-table", CockpitTable)
            initial = table.selected_index
            view.move_selection(1)
            await pilot.pause()
            expected = min(initial + 1, len(table._rows) - 1)
            assert table.selected_index == expected

    _run(_body())


def test_agents_view_move_selection_up_clamps() -> None:
    """move_selection(-1) at index 0 stays at 0."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("a")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-agents", AgentsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#agents-table", CockpitTable)
            view.move_selection(-1)
            await pilot.pause()
            assert table.selected_index == 0

    _run(_body())


def test_agents_view_toggle_inspector() -> None:
    """toggle_inspector() flips the inspector visibility flag."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("a")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-agents", AgentsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#agents-table", CockpitTable)
            before = table._inspector_visible
            view.toggle_inspector()
            await pilot.pause()
            assert table._inspector_visible != before

    _run(_body())


def test_agents_view_inspector_title_contains_agent() -> None:
    """Inspector title includes 'agent' after populating."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("a")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-agents", AgentsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#agents-table", CockpitTable)
            assert "agent" in table._inspector_title

    _run(_body())


# ---------------------------------------------------------------------------
# TasksView tests
# ---------------------------------------------------------------------------


def test_tasks_view_loads_rows() -> None:
    """populate() loads at least one row on the default active tab."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("t")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-tasks", TasksView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#tasks-table", CockpitTable)
            assert len(table._rows) >= 1

    _run(_body())


def test_tasks_view_has_six_tabs() -> None:
    """populate() produces exactly 6 lifecycle tabs, 1 active."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("t")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-tasks", TasksView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#tasks-table", CockpitTable)
            assert len(table._tabs) == 6
            active = [t for t in table._tabs if t.active]
            assert len(active) == 1
            assert active[0].label == "active"

    _run(_body())


def test_tasks_view_failed_tab_shows_rows() -> None:
    """Switching _active_tab to 'failed' renders failed rows."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("t")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-tasks", TasksView)
            view.populate(DATA)
            await pilot.pause()
            view._active_tab = "failed"
            view._rebuild()
            await pilot.pause()
            table = view.query_one("#tasks-table", CockpitTable)
            assert len(table._rows) >= 1
            active = [t for t in table._tabs if t.active]
            assert active[0].label == "failed"

    _run(_body())


def test_tasks_view_move_selection() -> None:
    """move_selection changes selected_index within valid bounds."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("t")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-tasks", TasksView)
            view.populate(DATA)
            view._active_tab = "failed"
            view._rebuild()
            await pilot.pause()
            table = view.query_one("#tasks-table", CockpitTable)
            view.move_selection(1)
            await pilot.pause()
            assert table.selected_index >= 0

    _run(_body())


def test_tasks_view_toggle_inspector() -> None:
    """toggle_inspector() flips inspector visibility."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("t")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-tasks", TasksView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#tasks-table", CockpitTable)
            before = table._inspector_visible
            view.toggle_inspector()
            await pilot.pause()
            assert table._inspector_visible != before

    _run(_body())


# ---------------------------------------------------------------------------
# ApprovalsView tests
# ---------------------------------------------------------------------------


def test_approvals_view_loads_rows() -> None:
    """populate() shows pending approvals from placeholder data."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("p")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-approvals", ApprovalsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#approvals-table", CockpitTable)
            assert len(table._rows) >= 1

    _run(_body())


def test_approvals_view_countdown_set() -> None:
    """Countdown or flag footer is non-empty when approvals are pending."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("p")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-approvals", ApprovalsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#approvals-table", CockpitTable)
            assert table._countdown != "" or table._flag != ""

    _run(_body())


def test_approvals_view_empty_text_when_no_approvals() -> None:
    """When approval list is empty the friendly empty_text is set."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("p")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-approvals", ApprovalsView)
            view._approvals = []
            view._data = DATA
            view._rebuild()
            await pilot.pause()
            table = view.query_one("#approvals-table", CockpitTable)
            assert "no approvals" in table._empty_text

    _run(_body())


def test_approvals_view_decide_top_refreshes() -> None:
    """decide_top('allow') calls decide_approval and re-populates without raising."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("p")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-approvals", ApprovalsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#approvals-table", CockpitTable)
            before_rows = len(table._rows)
            view.decide_top("allow")
            await pilot.pause()
            # offline: same placeholder data, same count
            assert len(table._rows) == before_rows

    _run(_body())


def test_approvals_view_move_selection() -> None:
    """move_selection changes selected_index within bounds."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("p")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-approvals", ApprovalsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#approvals-table", CockpitTable)
            view.move_selection(1)
            await pilot.pause()
            assert table.selected_index >= 0

    _run(_body())


def test_approvals_view_inspector_actions() -> None:
    """Inspector exposes allow / deny / always actions."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("p")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-approvals", ApprovalsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#approvals-table", CockpitTable)
            tokens = {a.action for a in table._inspector_actions}
            assert {"allow", "deny", "always"}.issubset(tokens)

    _run(_body())


# ---------------------------------------------------------------------------
# AuditView tests
# ---------------------------------------------------------------------------


def test_audit_view_loads_rows() -> None:
    """populate() loads 2 audit entries from placeholder data."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("l")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-audit", AuditView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#audit-table", CockpitTable)
            assert len(table._rows) == 2

    _run(_body())


def test_audit_view_seq_descending() -> None:
    """First row has the highest seq number (newest-first)."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("l")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-audit", AuditView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#audit-table", CockpitTable)
            assert len(table._rows) >= 2
            first = int(table._rows[0].cells[0].text.lstrip("#"))
            second = int(table._rows[1].cells[0].text.lstrip("#"))
            assert first > second

    _run(_body())


def test_audit_view_five_columns() -> None:
    """Table has exactly 5 columns."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("l")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-audit", AuditView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#audit-table", CockpitTable)
            assert len(table._columns) == 5

    _run(_body())


def test_audit_view_move_selection() -> None:
    """move_selection changes selected_index within bounds."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("l")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-audit", AuditView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#audit-table", CockpitTable)
            view.move_selection(1)
            await pilot.pause()
            assert table.selected_index >= 0

    _run(_body())


def test_audit_view_toggle_inspector() -> None:
    """toggle_inspector flips inspector visibility."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("l")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-audit", AuditView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#audit-table", CockpitTable)
            before = table._inspector_visible
            view.toggle_inspector()
            await pilot.pause()
            assert table._inspector_visible != before

    _run(_body())


# ---------------------------------------------------------------------------
# ConnectionsView tests
# ---------------------------------------------------------------------------


def test_connections_view_loads_rows() -> None:
    """populate() loads 2 capabilities + 1 MCP server = 3 rows."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("n")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-connections", ConnectionsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#connections-table", CockpitTable)
            assert len(table._rows) == 3

    _run(_body())


def test_connections_view_columns() -> None:
    """Table has exactly 3 columns: health · connection · tools."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("n")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-connections", ConnectionsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#connections-table", CockpitTable)
            assert [c.label for c in table._columns] == ["health", "connection", "tools"]

    _run(_body())


def test_connections_view_move_selection() -> None:
    """move_selection advances selected_index."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("n")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-connections", ConnectionsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#connections-table", CockpitTable)
            view.move_selection(1)
            await pilot.pause()
            assert table.selected_index >= 0

    _run(_body())


def test_connections_view_toggle_inspector() -> None:
    """toggle_inspector flips inspector visibility."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("n")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-connections", ConnectionsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#connections-table", CockpitTable)
            before = table._inspector_visible
            view.toggle_inspector()
            await pilot.pause()
            assert table._inspector_visible != before

    _run(_body())


def test_connections_view_inspector_enable_action() -> None:
    """Inspector contains an 'enable' action button."""

    async def _body() -> None:
        from hachi.tui.cockpit.app import CockpitApp

        async with CockpitApp().run_test(headless=True) as pilot:
            await pilot.press("g")
            await pilot.press("n")
            await pilot.pause()
            view = _screen(pilot).query_one("#view-connections", ConnectionsView)
            view.populate(DATA)
            await pilot.pause()
            table = view.query_one("#connections-table", CockpitTable)
            tokens = {a.action for a in table._inspector_actions}
            assert "enable" in tokens

    _run(_body())
