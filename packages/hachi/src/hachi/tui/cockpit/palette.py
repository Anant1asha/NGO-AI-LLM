"""CommandPalette — command palette overlay for the Hachi Cockpit.

Centered modal (~60 wide) with a fuzzy-filtered list of all palette items
grouped by section (go to / do / open).  j/k and up/down move selection;
enter executes; escape closes.

Usage (from CockpitScreen)::

    self.app.push_screen(CommandPalette(self))
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from hachi.tui.cockpit.nav import PaletteItem, palette_items
from hachi.tui.theme import BORDER_MUTED, BRAND, FOREGROUND, MUTED, NAVY, SURFACE

if TYPE_CHECKING:
    from hachi.tui.cockpit.screen import CockpitScreen

_DIM = "#6E6A74"
_SELECTED_BG = "#2A2830"

# Section display order and labels
_SECTION_ORDER = ["go to", "do", "open"]


def _fuzzy_match(query: str, text: str) -> bool:
    """Return True if every character of *query* appears in *text* in order.

    Case-insensitive subsequence match (fuzzy, not substring).

    Args:
        query: The user's search string.
        text: The item label to match against.

    Returns:
        True if *query* is a (case-insensitive) subsequence of *text*.
    """
    if not query:
        return True
    q = query.lower()
    t = text.lower()
    qi = 0
    for ch in t:
        if ch == q[qi]:
            qi += 1
            if qi == len(q):
                return True
    return False


def _filter_items(query: str, items: list[PaletteItem]) -> list[PaletteItem]:
    """Return items whose label (or section) matches *query*.

    Args:
        query: User search input (empty = all items).
        items: Full palette item list.

    Returns:
        Filtered list preserving original order.
    """
    if not query:
        return items
    return [i for i in items if _fuzzy_match(query, i.label) or _fuzzy_match(query, i.section)]


def _render_item(item: PaletteItem, selected: bool) -> Text:
    """Render a single palette item row as Rich Text.

    Args:
        item: The palette item to render.
        selected: Whether this item is currently highlighted.

    Returns:
        Rich Text with label on the left and key hint on the right.
    """
    bg = f"on {_SELECTED_BG}" if selected else ""
    t = Text(no_wrap=True)
    label_style = f"bold {FOREGROUND} {bg}" if selected else f"{FOREGROUND} {bg}"
    key_style = f"bold {NAVY} {bg}"
    # Left-pad label, right-align key hint
    t.append(f"  {item.label:<38}", style=label_style)
    t.append(f"{item.key:>8}  ", style=key_style)
    return t


def _render_section_header(section: str) -> Text:
    """Render a section divider row."""
    t = Text(no_wrap=True)
    t.append(f"  {section.upper()}\n", style=f"bold {_DIM}")
    return t


class CommandPalette(ModalScreen[None]):
    """Fuzzy-filtered command palette overlay.

    Args:
        cockpit_screen: Reference to the CockpitScreen for dispatching actions.
    """

    DEFAULT_CSS = f"""
    CommandPalette {{
        align: center top;
    }}

    CommandPalette > Vertical#palette-box {{
        width: 62;
        height: auto;
        max-height: 80vh;
        background: {SURFACE};
        border: tall {BORDER_MUTED};
        margin-top: 4;
    }}

    CommandPalette Input#palette-input {{
        background: {SURFACE};
        border: tall {BORDER_MUTED};
        color: {FOREGROUND};
        height: 3;
        padding: 0 2;
    }}

    CommandPalette VerticalScroll#palette-list {{
        height: auto;
        max-height: 60vh;
        padding: 0;
    }}

    CommandPalette Static.palette-item {{
        height: 1;
        width: 1fr;
    }}

    CommandPalette Static.palette-hint {{
        color: {MUTED};
        padding: 0 2;
        height: 1;
    }}
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    def __init__(
        self,
        cockpit_screen: CockpitScreen,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._cockpit_screen = cockpit_screen
        self._all_items: list[PaletteItem] = palette_items()
        self._filtered: list[PaletteItem] = list(self._all_items)
        self._selected: int = 0

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Yield the palette box with input, list, and footer hint."""
        with Vertical(id="palette-box"):
            yield Input(
                placeholder="go to  do  open...",
                id="palette-input",
            )
            with VerticalScroll(id="palette-list"):
                yield Static("", id="palette-content")
            yield Static(
                "  enter · run   esc · close   j/k · move",
                classes="palette-hint",
            )

    def on_mount(self) -> None:
        """Focus the input and render the initial list."""
        self.query_one("#palette-input", Input).focus()
        self._rebuild_list()

    # ------------------------------------------------------------------
    # Input handler
    # ------------------------------------------------------------------

    @on(Input.Changed, "#palette-input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        """Filter the list when the query changes."""
        query = event.value.strip()
        self._filtered = _filter_items(query, self._all_items)
        self._selected = 0
        self._rebuild_list()

    # ------------------------------------------------------------------
    # Key handling (j/k/up/down/enter pass-through)
    # ------------------------------------------------------------------

    def on_key(self, event: object) -> None:
        """Handle navigation and selection keys inside the palette."""
        # event is textual Key event
        key = getattr(event, "key", "")
        if key in ("j", "down"):
            self._selected = min(self._selected + 1, len(self._filtered) - 1)
            self._rebuild_list()
            getattr(event, "prevent_default", lambda: None)()
        elif key in ("k", "up"):
            self._selected = max(self._selected - 1, 0)
            self._rebuild_list()
            getattr(event, "prevent_default", lambda: None)()
        elif key == "enter":
            self._execute_selected()
            getattr(event, "prevent_default", lambda: None)()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _rebuild_list(self) -> None:
        """Re-render the palette item list with current filter + selection."""
        content = self.query_one("#palette-content", Static)

        if not self._filtered:
            content.update(Text("  no matches", style=MUTED))
            return

        # Group by section while preserving order
        sections: dict[str, list[tuple[int, PaletteItem]]] = {s: [] for s in _SECTION_ORDER}
        global_idx = 0
        for item in self._filtered:
            sec = item.section if item.section in sections else "do"
            sections[sec].append((global_idx, item))
            global_idx += 1

        t = Text(no_wrap=False)
        for section in _SECTION_ORDER:
            group = sections[section]
            if not group:
                continue
            t.append_text(_render_section_header(section))
            for idx, item in group:
                selected = idx == self._selected
                t.append_text(_render_item(item, selected))
                t.append("\n")

        content.update(t)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_selected(self) -> None:
        """Execute the currently selected palette item and dismiss."""
        if not self._filtered:
            return
        self._selected = max(0, min(self._selected, len(self._filtered) - 1))
        item = self._filtered[self._selected]
        self.dismiss()
        self._dispatch_action(item)

    def _dispatch_action(self, item: PaletteItem) -> None:
        """Dispatch *item*'s action to the cockpit screen.

        Args:
            item: The selected PaletteItem whose ``action`` token to dispatch.
        """
        screen = self._cockpit_screen
        action = item.action

        if action.startswith("go:"):
            view_id = action[3:]
            screen.go(view_id)

        elif action == "do:approve_all":
            # Approve all pending approvals
            approvals = screen.cockpit_data.approvals()
            for ap in approvals:
                screen.cockpit_data.decide_approval(ap.id, "allow")
            screen.notify_toast(
                f"approved {len(approvals)} pending" if approvals else "no pending approvals",
                color=BRAND,
            )

        elif action == "do:gate_ungated":
            screen.notify_toast("require approval for ungated tools", color=NAVY)

        elif action == "do:switch_model":
            screen.notify_toast("switch model  (open settings)", color=NAVY)
            screen.go("settings")

        elif action == "do:compact_memory":
            screen.notify_toast("compact memory queued", color=NAVY)

        elif action == "do:export_audit":
            screen.notify_toast("export audit  (open audit)", color=NAVY)
            screen.go("audit")

        elif action == "open:session_latest":
            screen.go("chat")

        elif action == "open:skill_research":
            screen.go("skills")

        elif action == "open:memory_latest":
            screen.go("memory")

        else:
            # Unknown action — best-effort toast
            screen.notify_toast(f"palette: {item.label}", color=NAVY)
