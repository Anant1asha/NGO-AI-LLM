"""CockpitTable — reusable selectable table widget for cockpit data views.

Used by: agents, tasks, approvals, audit, connections (the 'isTable' views in the design).

Public API (Wave-3 agent D)
---------------------------
Feed it via ``load(columns, rows, inspector_fields, inspector_actions, ...)`` then call
``move_selection(delta)``, ``toggle_inspector()``, and ``clear()`` from the view.

Data structures you must provide
---------------------------------
TableColumn  — defines a column (label, width, grow, align)
TableCell    — a single cell (text, color, align override)
TableRow     — a row (cells list + accent_color for the left selection border)
InspectorField — a label/value pair or divider in the inspector panel
InspectorAction — a button in the inspector panel
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from hachi.tui.theme import (
    BORDER_MUTED,
    BRAND,
    FOREGROUND,
    MUTED,
    SURFACE,
)

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

Align = Literal["left", "right", "center"]


@dataclass
class TableColumn:
    """Definition of a single table column.

    Attributes:
        label: Header text (shown in the column header row).
        width: Fixed character width (used when ``grow=False``).
        grow: If True the column expands to fill remaining width.
        align: Text alignment for cells in this column.
    """

    label: str
    width: int = 80
    grow: bool = False
    align: Align = "left"


@dataclass
class TableCell:
    """A single rendered cell.

    Attributes:
        text: The display text.
        color: Rich color string (e.g. ``"#E25A44"``). Defaults to MUTED.
        align: Overrides the column alignment for this cell only.
    """

    text: str
    color: str = MUTED
    align: Align | None = None


@dataclass
class TableRow:
    """A single data row.

    Attributes:
        cells: Ordered list of TableCell values; must match the column count.
        accent_color: Color of the 1-char left selection border when selected.
            Use the status color for the row (e.g. AMBER for running, DANGER for failed).
    """

    cells: list[TableCell]
    accent_color: str = BRAND


@dataclass
class InspectorField:
    """One entry in the inspector panel.

    Exactly one of ``divider``, ``row``, or ``line`` should be True.

    Attributes:
        divider: If True, render a horizontal separator line.
        row:  If True, render as ``label  value`` on one line.
        line: If True, render ``value`` spanning the full width.
        label: Used when ``row=True``.
        value: The display text (used for ``row`` and ``line``).
        color: Rich color for the value text.
    """

    divider: bool = False
    row: bool = False
    line: bool = False
    label: str = ""
    value: str = ""
    color: str = MUTED


@dataclass
class InspectorAction:
    """A button shown at the bottom of the inspector panel.

    Attributes:
        key: Keyboard shortcut hint shown inside ``[`` ``]``.
        label: Button label text.
        primary: If True, styled with BRAND background (primary call-to-action).
        action: Action token the view/screen can inspect (optional).
    """

    key: str
    label: str
    primary: bool = False
    action: str = ""


@dataclass
class TableTab:
    """A tab in the tabs row above the table (e.g. tasks lifecycle tabs).

    Attributes:
        label: Display text.
        active: Whether this tab is currently selected.
    """

    label: str
    active: bool = False


# ---------------------------------------------------------------------------
# Internal widget helpers
# ---------------------------------------------------------------------------

_DIM = "#6E6A74"
_SELECTED_BG = "rgba(255,255,255,0.05)"


def _pad_right(text: str, width: int) -> str:
    """Pad or truncate *text* to exactly *width* characters."""
    if len(text) >= width:
        return text[: width - 1] + "…" if width > 1 else text[:width]
    return text + " " * (width - len(text))


def _render_header(columns: list[TableColumn], total_width: int) -> Text:
    """Render the header row as a Rich Text object."""
    t = Text(no_wrap=True, overflow="ellipsis")
    grow_col_width = _grow_width(columns, total_width)
    for col in columns:
        w = grow_col_width if col.grow else col.width
        label = _pad_right(col.label, w)
        t.append(label, style=f"{_DIM}")
    return t


def _render_row(
    row: TableRow,
    columns: list[TableColumn],
    total_width: int,
    selected: bool,
) -> Text:
    """Render a data row as a Rich Text object."""
    t = Text(no_wrap=True, overflow="ellipsis")
    grow_col_width = _grow_width(columns, total_width)
    # Selection border is handled via CSS on the Static widget, not in text.
    for i, col in enumerate(columns):
        if i >= len(row.cells):
            break
        cell = row.cells[i]
        w = grow_col_width if col.grow else col.width
        raw = cell.text
        padded = _pad_right(raw, w)
        color = cell.color if not selected else FOREGROUND
        t.append(padded, style=color)
    return t


def _grow_width(columns: list[TableColumn], total_width: int) -> int:
    """Calculate the width allocated to grow columns."""
    fixed = sum(col.width for col in columns if not col.grow)
    grow_count = sum(1 for col in columns if col.grow)
    if grow_count == 0:
        return 0
    return max(8, (total_width - fixed) // grow_count)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------


class CockpitTable(Widget):
    """Reusable selectable table with an optional right-hand inspector panel.

    Usage from a view::

        class AgentsView(CockpitView):
            def compose(self) -> ComposeResult:
                yield CockpitTable(id="agents-table")

            def populate(self, data: CockpitData) -> None:
                rows_data = data.agents()
                columns = [
                    TableColumn("status", 96),
                    TableColumn("role",   120),
                    TableColumn("task",   grow=True),
                ]
                rows = [TableRow(cells=[...], accent_color=...) for a in rows_data]
                self.query_one(CockpitTable).load(columns, rows)

        # From view optional hooks:
        def move_selection(self, delta: int) -> None:
            self.query_one(CockpitTable).move_selection(delta)

        def toggle_inspector(self) -> None:
            self.query_one(CockpitTable).toggle_inspector()
    """

    DEFAULT_CSS = f"""
    CockpitTable {{
        height: 1fr;
        width: 1fr;
        layout: horizontal;
    }}

    CockpitTable > #ct-main {{
        height: 1fr;
        width: 1fr;
        layout: vertical;
        border-right: tall {BORDER_MUTED};
    }}

    CockpitTable > #ct-inspector {{
        width: 38;
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
        display: none;
    }}

    CockpitTable > #ct-inspector.visible {{
        display: block;
    }}

    CockpitTable #ct-tabs {{
        height: auto;
        padding: 0 1;
        border-bottom: tall {BORDER_MUTED};
    }}

    CockpitTable #ct-header {{
        height: 1;
        padding: 0 1;
        color: {_DIM};
        border-bottom: tall {BORDER_MUTED};
    }}

    CockpitTable #ct-rows {{
        height: 1fr;
        overflow-y: auto;
    }}

    CockpitTable .ct-row {{
        padding: 0 1;
        height: 1;
    }}

    CockpitTable .ct-row.selected {{
        background: {SURFACE};
    }}

    CockpitTable #ct-footer {{
        height: auto;
        padding: 0 1;
        border-top: tall {BORDER_MUTED};
        color: {_DIM};
        display: none;
    }}

    CockpitTable #ct-footer.visible {{
        display: block;
    }}
    """

    # Reactive: current selection index.
    _sel: reactive[int] = reactive(0)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._columns: list[TableColumn] = []
        self._rows: list[TableRow] = []
        self._tabs: list[TableTab] = []
        self._inspector_fields: list[InspectorField] = []
        self._inspector_actions: list[InspectorAction] = []
        self._inspector_title: str = "detail"
        self._inspector_visible: bool = True
        self._countdown: str = ""
        self._flag: str = ""
        self._empty_text: str = ""

    def compose(self) -> ComposeResult:
        """Compose the table layout."""
        with Widget(id="ct-main"):
            yield Static("", id="ct-tabs")
            yield Static("", id="ct-header")
            with Widget(id="ct-rows"):
                pass  # rows injected dynamically
            yield Static("", id="ct-footer")
        with Widget(id="ct-inspector"):
            yield Static("", id="ct-insp-content")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        columns: list[TableColumn],
        rows: list[TableRow],
        inspector_fields: list[InspectorField] | None = None,
        inspector_actions: list[InspectorAction] | None = None,
        inspector_title: str = "detail",
        tabs: list[TableTab] | None = None,
        countdown: str = "",
        flag: str = "",
        empty_text: str = "",
    ) -> None:
        """Load new data into the table and re-render.

        Args:
            columns: Column definitions (order matters).
            rows: Data rows to display.
            inspector_fields: Fields shown in the right inspector panel.
            inspector_actions: Action buttons in the inspector panel.
            inspector_title: Title line at the top of the inspector panel.
            tabs: Optional lifecycle tabs above the table (e.g. tasks view).
            countdown: Optional text shown in a bottom-left status line
                (e.g. the approvals auto-deny countdown).
            flag: Optional warning text shown in a bottom-left red line.
            empty_text: Text shown when rows is empty.
        """
        self._columns = columns
        self._rows = rows
        self._inspector_fields = inspector_fields or []
        self._inspector_actions = inspector_actions or []
        self._inspector_title = inspector_title
        self._tabs = tabs or []
        self._countdown = countdown
        self._flag = flag
        self._empty_text = empty_text
        # Clamp selection to new row count.
        self._sel = max(0, min(self._sel, len(rows) - 1)) if rows else 0
        self._render_all()

    def move_selection(self, delta: int) -> None:
        """Move the selection by *delta* rows (+1 down, -1 up)."""
        if not self._rows:
            return
        new = max(0, min(len(self._rows) - 1, self._sel + delta))
        self._sel = new
        self._render_rows()
        self._render_inspector()

    def toggle_inspector(self) -> None:
        """Show or hide the right-hand inspector panel."""
        self._inspector_visible = not self._inspector_visible
        insp = self.query_one("#ct-inspector")
        if self._inspector_visible:
            insp.add_class("visible")
        else:
            insp.remove_class("visible")

    def show_inspector(self, visible: bool = True) -> None:
        """Programmatically set inspector visibility."""
        self._inspector_visible = visible
        insp = self.query_one("#ct-inspector")
        if visible:
            insp.add_class("visible")
        else:
            insp.remove_class("visible")

    def clear(self) -> None:
        """Clear all data from the table."""
        self.load([], [])

    @property
    def selected_index(self) -> int:
        """The currently selected row index."""
        return self._sel

    @property
    def selected_row(self) -> TableRow | None:
        """The currently selected TableRow, or None if empty."""
        if self._rows and 0 <= self._sel < len(self._rows):
            return self._rows[self._sel]
        return None

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _render_all(self) -> None:
        """Re-render all sections."""
        self._render_tabs()
        self._render_header()
        self._render_rows()
        self._render_footer()
        self._render_inspector()

    def _render_tabs(self) -> None:
        if not self.is_attached:
            return
        tabs_widget = self.query_one("#ct-tabs", Static)
        if not self._tabs:
            tabs_widget.update("")
            return
        parts: list[tuple[str, str]] = []
        for tab in self._tabs:
            color = FOREGROUND if tab.active else _DIM
            parts.append((tab.label, color))
        t = Text()
        for i, (label, color) in enumerate(parts):
            t.append(label, style=color)
            if i < len(parts) - 1:
                t.append("  ·  ", style=_DIM)
        tabs_widget.update(t)

    def _render_header(self) -> None:
        if not self.is_attached:
            return
        header = self.query_one("#ct-header", Static)
        if not self._columns:
            header.update("")
            return
        # Use a fixed total width for offline/test mode; will be recalculated on resize.
        total = self.size.width or 80
        header.update(_render_header(self._columns, total))

    def _render_rows(self) -> None:
        if not self.is_attached:
            return
        rows_container = self.query_one("#ct-rows")
        rows_container.remove_children()

        if not self._rows:
            if self._empty_text:
                rows_container.mount(
                    Static(
                        Text(self._empty_text, style=f"bold {MUTED}"),
                        classes="ct-empty",
                    )
                )
            return

        total = self.size.width or 80
        for i, row in enumerate(self._rows):
            sel = i == self._sel
            rendered = _render_row(row, self._columns, total, sel)
            classes = "ct-row selected" if sel else "ct-row"
            w = Static(rendered, classes=classes)
            if sel:
                # Left accent border via inline styles (markup hack using leading colored char).
                accent_char = Text("▎", style=row.accent_color)
                accent_char.append_text(rendered)
                w.update(accent_char)
            rows_container.mount(w)

    def _render_footer(self) -> None:
        if not self.is_attached:
            return
        footer = self.query_one("#ct-footer", Static)
        text = self._flag or self._countdown
        if text:
            footer.add_class("visible")
            color = BRAND if self._flag else "#7C9BD1"
            footer.update(Text(text, style=color))
        else:
            footer.remove_class("visible")
            footer.update("")

    def _render_inspector(self) -> None:
        if not self.is_attached:
            return
        insp_widget = self.query_one("#ct-insp-content", Static)
        if not self._inspector_fields and not self._inspector_actions:
            insp_widget.update("")
            return

        t = Text()
        t.append(self._inspector_title + "\n", style=_DIM)
        t.append("\n")

        for f in self._inspector_fields:
            if f.divider:
                t.append("─" * 30 + "\n", style=BORDER_MUTED)
            elif f.row:
                label_padded = _pad_right(f.label, 8)
                t.append(label_padded, style=_DIM)
                t.append(f.value + "\n", style=f.color)
            elif f.line:
                t.append(f.value + "\n", style=f.color)

        if self._inspector_actions:
            t.append("\n")
            for act in self._inspector_actions:
                style = f"bold {BRAND}" if act.primary else MUTED
                t.append(f"[{act.key}] {act.label}\n", style=style)

        insp_widget.update(t)

    def on_resize(self) -> None:
        """Re-render on resize to recalculate grow column widths."""
        self._render_header()
        self._render_rows()

    def on_mount(self) -> None:
        """Initial render after mount."""
        self._render_all()
        if self._inspector_visible:
            self.query_one("#ct-inspector").add_class("visible")
