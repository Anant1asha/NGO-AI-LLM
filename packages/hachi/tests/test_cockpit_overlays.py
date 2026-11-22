"""Tests for Hachi Cockpit overlay widgets.

Each overlay is mounted in a minimal throwaway App — no dependency on
the 12 cockpit views or CockpitScreen.  Tests are deterministic and
do not require a live gateway.

Pattern: synchronous test functions wrapping asyncio.run() — no pytest-asyncio
required (matches test_cockpit_foundation.py convention).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.widgets import Static

from hachi.client.gaps import placeholder_approvals
from hachi.client.models import Approval
from hachi.tui.cockpit.approval import ApprovalModal
from hachi.tui.cockpit.help import HelpModal
from hachi.tui.cockpit.mascot import Mascot
from hachi.tui.cockpit.palette import CommandPalette, _filter_items, _fuzzy_match

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _placeholder_approval() -> Approval:
    """Return the first placeholder approval for tests."""
    return placeholder_approvals()[0]


def _fake_screen() -> MagicMock:
    """Return a lightweight fake CockpitScreen for modal constructors."""
    screen = MagicMock()
    screen.cockpit_data.approvals.return_value = placeholder_approvals()
    screen.cockpit_data.decide_approval.return_value = {}
    return screen


# ---------------------------------------------------------------------------
# Mascot
# ---------------------------------------------------------------------------


class MascotApp(App[None]):
    """Minimal app that mounts a single Mascot widget."""

    def compose(self) -> ComposeResult:
        yield Mascot(id="mascot")


def test_mascot_default_state() -> None:
    """Mascot mounts with default 'watch' state."""

    async def _body() -> None:
        async with MascotApp().run_test(headless=True) as pilot:
            mascot = pilot.app.query_one("#mascot", Mascot)
            assert mascot.state == "watch"

    _run(_body())


def test_mascot_set_state_work() -> None:
    """set_state('work') changes state to 'work'."""

    async def _body() -> None:
        async with MascotApp().run_test(headless=True) as pilot:
            mascot = pilot.app.query_one("#mascot", Mascot)
            mascot.set_state("work")
            assert mascot.state == "work"

    _run(_body())


def test_mascot_set_state_done() -> None:
    """set_state('done') changes state to 'done'."""

    async def _body() -> None:
        async with MascotApp().run_test(headless=True) as pilot:
            mascot = pilot.app.query_one("#mascot", Mascot)
            mascot.set_state("done")
            assert mascot.state == "done"

    _run(_body())


def test_mascot_set_state_blocked() -> None:
    """set_state('blocked') changes state to 'blocked'."""

    async def _body() -> None:
        async with MascotApp().run_test(headless=True) as pilot:
            mascot = pilot.app.query_one("#mascot", Mascot)
            mascot.set_state("blocked")
            assert mascot.state == "blocked"

    _run(_body())


def test_mascot_unknown_state_falls_back_to_watch() -> None:
    """Unknown state string falls back to 'watch'."""

    async def _body() -> None:
        async with MascotApp().run_test(headless=True) as pilot:
            mascot = pilot.app.query_one("#mascot", Mascot)
            mascot.set_state("flying_saucer")
            assert mascot.state == "watch"

    _run(_body())


# ---------------------------------------------------------------------------
# HelpModal
# ---------------------------------------------------------------------------


class HelpApp(App[None]):
    """Minimal app that immediately pushes HelpModal."""

    def on_mount(self) -> None:
        self.push_screen(HelpModal())


def test_help_modal_mounts() -> None:
    """HelpModal mounts without error and is the active screen."""

    async def _body() -> None:
        async with HelpApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, HelpModal)

    _run(_body())


def test_help_modal_escape_closes() -> None:
    """Pressing escape dismisses HelpModal and returns to base screen."""

    async def _body() -> None:
        async with HelpApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, HelpModal)
            await pilot.press("escape")
            assert not isinstance(pilot.app.screen, HelpModal)

    _run(_body())


def test_help_modal_question_mark_closes() -> None:
    """Pressing '?' dismisses HelpModal."""

    async def _body() -> None:
        async with HelpApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, HelpModal)
            await pilot.press("question_mark")
            assert not isinstance(pilot.app.screen, HelpModal)

    _run(_body())


# ---------------------------------------------------------------------------
# ApprovalModal
# ---------------------------------------------------------------------------


class ApprovalApp(App[None]):
    """Minimal app that immediately pushes ApprovalModal with a placeholder."""

    def __init__(self) -> None:
        super().__init__()
        self.fake_screen = _fake_screen()
        self.approval = _placeholder_approval()

    def on_mount(self) -> None:
        self.push_screen(ApprovalModal(self.approval, self.fake_screen))


def test_approval_modal_mounts() -> None:
    """ApprovalModal mounts and is the active screen."""

    async def _body() -> None:
        async with ApprovalApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, ApprovalModal)

    _run(_body())


def test_approval_modal_press_y_allow() -> None:
    """Pressing 'y' calls decide_approval with 'allow' and pops the modal."""

    async def _body() -> None:
        app = ApprovalApp()
        async with app.run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, ApprovalModal)
            await pilot.press("y")
            assert not isinstance(pilot.app.screen, ApprovalModal)
            app.fake_screen.cockpit_data.decide_approval.assert_called_once_with(
                app.approval.id, "allow"
            )

    _run(_body())


def test_approval_modal_press_n_deny() -> None:
    """Pressing 'n' calls decide_approval with 'deny' and pops the modal."""

    async def _body() -> None:
        app = ApprovalApp()
        async with app.run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, ApprovalModal)
            await pilot.press("n")
            assert not isinstance(pilot.app.screen, ApprovalModal)
            app.fake_screen.cockpit_data.decide_approval.assert_called_once_with(
                app.approval.id, "deny"
            )

    _run(_body())


def test_approval_modal_escape_denies() -> None:
    """Pressing escape denies and pops the modal."""

    async def _body() -> None:
        app = ApprovalApp()
        async with app.run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, ApprovalModal)
            await pilot.press("escape")
            assert not isinstance(pilot.app.screen, ApprovalModal)
            app.fake_screen.cockpit_data.decide_approval.assert_called_once_with(
                app.approval.id, "deny"
            )

    _run(_body())


def test_approval_modal_shows_approval_info() -> None:
    """ApprovalModal renders the approval's op and action fields."""

    async def _body() -> None:
        app = ApprovalApp()
        async with app.run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, ApprovalModal)
            rendered = pilot.app.screen.query(Static)
            # In Textual 8.x, Static.visual is a Content object with .plain
            texts = " ".join(
                w.visual.plain if hasattr(w, "visual") and w.visual is not None else ""
                for w in rendered
            )
            assert app.approval.op in texts or app.approval.action in texts

    _run(_body())


# ---------------------------------------------------------------------------
# CommandPalette — fuzzy filter (pure unit, no Textual)
# ---------------------------------------------------------------------------


def test_fuzzy_match_empty_query_matches_all() -> None:
    """Empty query matches any text."""
    assert _fuzzy_match("", "anything") is True


def test_fuzzy_match_exact_substring() -> None:
    """Exact substring matches."""
    assert _fuzzy_match("chat", "go to chat") is True


def test_fuzzy_match_subsequence() -> None:
    """Non-contiguous subsequence matches."""
    assert _fuzzy_match("cht", "chat") is True


def test_fuzzy_match_case_insensitive() -> None:
    """Match is case-insensitive."""
    assert _fuzzy_match("CHAT", "chat") is True


def test_fuzzy_match_no_match() -> None:
    """Non-matching query returns False."""
    assert _fuzzy_match("xyz", "chat") is False


def test_filter_items_empty_query_returns_all() -> None:
    """Empty query returns all palette items."""
    from hachi.tui.cockpit.nav import palette_items

    all_items = palette_items()
    result = _filter_items("", all_items)
    assert len(result) == len(all_items)


def test_filter_items_narrows_list() -> None:
    """Filtering by 'chat' returns fewer items than full list."""
    from hachi.tui.cockpit.nav import palette_items

    all_items = palette_items()
    result = _filter_items("chat", all_items)
    assert 0 < len(result) < len(all_items)
    for item in result:
        assert _fuzzy_match("chat", item.label) or _fuzzy_match("chat", item.section)


def test_filter_items_no_match_returns_empty() -> None:
    """Query that matches nothing returns an empty list."""
    from hachi.tui.cockpit.nav import palette_items

    all_items = palette_items()
    result = _filter_items("zzzzzzzzzzzzzzz", all_items)
    assert result == []


# ---------------------------------------------------------------------------
# CommandPalette — Textual integration
# ---------------------------------------------------------------------------


class PaletteApp(App[None]):
    """Minimal app that immediately pushes CommandPalette with a mock screen."""

    def __init__(self) -> None:
        super().__init__()
        self.fake_screen = _fake_screen()

    def on_mount(self) -> None:
        self.push_screen(CommandPalette(self.fake_screen))


def test_palette_mounts() -> None:
    """CommandPalette mounts and is the active screen."""

    async def _body() -> None:
        async with PaletteApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, CommandPalette)

    _run(_body())


def test_palette_escape_closes() -> None:
    """Pressing escape dismisses CommandPalette."""

    async def _body() -> None:
        async with PaletteApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, CommandPalette)
            await pilot.press("escape")
            assert not isinstance(pilot.app.screen, CommandPalette)

    _run(_body())


def test_palette_filter_narrows_items() -> None:
    """Typing in the palette input narrows the filtered item list."""

    async def _body() -> None:
        async with PaletteApp().run_test(headless=True) as pilot:
            palette: CommandPalette = pilot.app.screen  # type: ignore[assignment]
            initial_count = len(palette._filtered)
            assert initial_count > 0
            await pilot.press("c", "h", "a", "t")
            await pilot.pause()
            assert len(palette._filtered) < initial_count

    _run(_body())


def test_palette_down_moves_selection_down() -> None:
    """Pressing down arrow moves the selection index down."""

    async def _body() -> None:
        async with PaletteApp().run_test(headless=True) as pilot:
            palette: CommandPalette = pilot.app.screen  # type: ignore[assignment]
            assert palette._selected == 0
            await pilot.press("down")
            await pilot.pause()
            assert palette._selected == 1

    _run(_body())


def test_palette_up_does_not_go_below_zero() -> None:
    """Pressing up arrow does not go below selection index 0."""

    async def _body() -> None:
        async with PaletteApp().run_test(headless=True) as pilot:
            palette: CommandPalette = pilot.app.screen  # type: ignore[assignment]
            await pilot.press("down")
            await pilot.pause()
            assert palette._selected == 1
            await pilot.press("up")
            await pilot.pause()
            assert palette._selected == 0

    _run(_body())


def test_palette_enter_dismisses() -> None:
    """Pressing enter executes the selection and dismisses the palette."""

    async def _body() -> None:
        async with PaletteApp().run_test(headless=True) as pilot:
            assert isinstance(pilot.app.screen, CommandPalette)
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(pilot.app.screen, CommandPalette)

    _run(_body())
