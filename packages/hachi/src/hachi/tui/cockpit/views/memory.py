"""MemoryView — Memory vault browser with layer nav and recall search (Wave-3).

Left rail: Active (ctx) · Sessions · Vault core · Vault user · Vault agent · Quarantine
Main pane:
  - recall results table  (score / collection / fact / category)
  - inspect block for the selected fact
  - quarantine warning line
  - vault facts panel (when a vault layer is selected): shows facts with IDs

Keyboard hooks (routed from CockpitScreen.on_key):
  x  — delete the selected vault fact
  a  — open the add-fact modal (AddFactModal)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from hachi.tui.cockpit.base import CockpitView
from hachi.tui.theme import (
    AMBER,
    BORDER_MUTED,
    BRAND,
    DANGER,
    FOREGROUND,
    GREEN,
    MUTED,
    NAVY,
    SURFACE,
)

if TYPE_CHECKING:
    from hachi.client.models import Fact, RecallHit
    from hachi.tui.cockpit.data import CockpitData

_LAYERS = [
    "Active (ctx)",
    "Sessions",
    "Vault  core",
    "Vault  user",
    "Vault  agent",
    "Quarantine",
]

_DEFAULT_QUERY = "recent"


def _score_color(score_str: str) -> str:
    """Return a color based on the numeric score string."""
    try:
        s = float(score_str)
    except (ValueError, TypeError):
        s = -1.0
    if s >= 0.85:
        color = GREEN
    elif s >= 0.65:
        color = AMBER
    else:
        color = MUTED
    return str(color)


def _recall_table(hits: list[RecallHit], selected: int) -> Text:
    """Render the recall results as a bordered table."""
    t = Text()
    # header
    t.append("score  ", style=MUTED)
    t.append(f"{'collection':<20}", style=MUTED)
    t.append("fact", style=MUTED)
    t.append("\n")
    t.append("─" * 72 + "\n", style=BORDER_MUTED)
    for i, hit in enumerate(hits):
        sc_col = _score_color(hit.score)
        is_sel = i == selected
        bg = "on #2a2730" if is_sel else ""
        prefix = "| " if is_sel else "  "
        border_col = BRAND if is_sel else BORDER_MUTED
        t.append(prefix, style=border_col)
        t.append(f"{hit.score:<6}", style=sc_col)
        t.append(f"  {hit.src[:18]:<20}", style=MUTED)
        fact_style = FOREGROUND if is_sel else MUTED
        t.append(f"  {hit.fact[:42]}", style=f"{fact_style} {bg}".strip())
        t.append("\n")
    if not hits:
        t.append("  no results\n", style=MUTED)
    return t


def _inspect_block(hit: RecallHit | None) -> Text:
    """Render the inspect panel for a selected recall hit."""
    t = Text()
    t.append("inspect  ", style=MUTED)
    t.append("▸", style=BRAND)
    if hit is None:
        t.append("  select a row above\n", style=MUTED)
        return t
    t.append(f"  {hit.src}\n", style=MUTED)
    t.append("\n")
    t.append(hit.fact, style=FOREGROUND)
    t.append("\n\n")
    t.append("score: ", style=MUTED)
    t.append(hit.score, style=_score_color(hit.score))
    t.append("   collection: ", style=MUTED)
    t.append(hit.src, style=NAVY)
    t.append("\n")
    t.append("[e] edit   [x] delete   [y] copy   [→] show related", style=MUTED)
    return t


def _quarantine_line(blocked_count: int) -> Text:
    t = Text()
    if blocked_count > 0:
        t.append("! ", style=DANGER)
        t.append(f"quarantine: {blocked_count} writes blocked by MemoryGuard — ", style=DANGER)
        t.append("[Enter] review", style=NAVY)
    else:
        t.append("quarantine: clean", style=GREEN)
    return t


# Map rail index → (group_id used for facts, display label)
_VAULT_LAYER_MAP: dict[int, tuple[str, str]] = {
    2: ("core_memory", "Vault  core"),
    3: ("user_profile", "Vault  user"),
    4: ("agent_profile", "Vault  agent"),
}


def _vault_facts_text(
    facts: list[Any],
    selected: int,
    group_label: str,
) -> Text:
    """Render vault facts as a selectable table."""
    t = Text()
    t.append(f"{group_label}  ", style=MUTED)
    t.append(f"{len(facts)} facts", style=MUTED)
    t.append("    [x] delete selected  [a] add fact\n\n", style=NAVY)
    t.append("─" * 72 + "\n", style=BORDER_MUTED)
    for i, fact in enumerate(facts):
        is_sel = i == selected
        bg = "on #2a2730" if is_sel else ""
        prefix = "| " if is_sel else "  "
        border_col = BRAND if is_sel else BORDER_MUTED
        t.append(prefix, style=border_col)
        fact_text = str(fact.text)[:60]
        fact_style = FOREGROUND if is_sel else MUTED
        t.append(f"{fact_text}", style=f"{fact_style} {bg}".strip())
        src_short = str(fact.source)[:18]
        t.append(f"  [{src_short}]", style=MUTED)
        t.append("\n")
    if not facts:
        t.append("  no facts in this collection\n", style=MUTED)
    return t


class AddFactModal(ModalScreen[str | None]):
    """Modal screen to add a new memory fact.

    Pushes onto the app screen stack. Dismisses with the text string on submit,
    or None on cancel (Escape / Cancel button).
    """

    DEFAULT_CSS = f"""
    AddFactModal {{
        align: center middle;
    }}
    #add-fact-container {{
        width: 60;
        height: auto;
        background: {SURFACE};
        border: solid {BRAND};
        padding: 1 2;
    }}
    #add-fact-label {{
        height: auto;
        margin-bottom: 1;
    }}
    #add-fact-input {{
        width: 1fr;
        margin-bottom: 1;
    }}
    #add-fact-buttons {{
        height: 3;
        align-horizontal: right;
    }}
    """

    def __init__(self, group: str, group_label: str) -> None:
        super().__init__()
        self._group = group
        self._group_label = group_label

    def compose(self) -> ComposeResult:
        """Render the modal layout."""
        with Vertical(id="add-fact-container"):
            yield Label(
                f"Add fact to [{self._group_label}]",
                id="add-fact-label",
            )
            yield Input(placeholder="Enter fact text…", id="add-fact-input")
            with Horizontal(id="add-fact-buttons"):
                yield Button("Cancel", id="add-fact-cancel", variant="default")
                yield Button("Add", id="add-fact-submit", variant="primary")

    def on_mount(self) -> None:
        """Focus the input field on mount."""
        self.query_one("#add-fact-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle submit / cancel."""
        if event.button.id == "add-fact-submit":
            text = self.query_one("#add-fact-input", Input).value.strip()
            self.dismiss(text or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit on Enter in the input."""
        text = event.value.strip()
        self.dismiss(text or None)

    def on_key(self, event: Any) -> None:
        """Dismiss on Escape."""
        if event.key == "escape":
            self.dismiss(None)


class MemoryView(CockpitView):  # type: ignore[misc]
    """Memory vault browser with layer nav and recall search.

    Layout
    ------
    Left rail (184 cols): Active (ctx) · Sessions · Vault core/user/agent · Quarantine
    Right pane: recall results table → inspect block → quarantine line.

    Data used
    ---------
    data.memory()    -> MemorySnapshot  (groups, blocked, proposed)
    data.recall(q)   -> list[RecallHit]  (score, fact, src)

    Hooks
    -----
    move_selection(delta)  — j/k moves the selected recall row.
    on_filter()            — invoke recall / open a query input (logs intent; stub).
    """

    view_id: ClassVar[str] = "memory"

    DEFAULT_CSS = f"""
    MemoryView {{
        height: 1fr;
        width: 1fr;
        background: {SURFACE};
    }}
    #mem-rail {{
        width: 20;
        border-right: solid {BORDER_MUTED};
        padding: 1 0;
        height: 1fr;
    }}
    .mem-rail-item {{
        padding: 0 1;
        height: 1;
        color: {MUTED};
    }}
    .mem-rail-item-selected {{
        padding: 0 1;
        height: 1;
        color: {FOREGROUND};
        background: {BRAND};
    }}
    #mem-main {{
        padding: 1 2;
        overflow-y: auto;
        height: 1fr;
    }}
    #mem-recall {{
        height: auto;
    }}
    #mem-inspect {{
        border-top: solid {BORDER_MUTED};
        padding: 1 0;
        height: auto;
    }}
    #mem-vault-facts {{
        border-top: solid {BORDER_MUTED};
        padding: 1 0;
        height: auto;
    }}
    #mem-quarantine {{
        border-top: solid {BORDER_MUTED};
        padding: 1 0;
        height: 3;
    }}
    """

    _layer: int = 0
    _selected: int = 0
    _hits: list[RecallHit] = []
    _vault_facts: list[Fact] = []
    _vault_selected: int = 0
    _data: CockpitData | None = None

    def compose(self) -> ComposeResult:  # noqa: D102
        with Horizontal():
            with Vertical(id="mem-rail"):
                yield Static("layers\n", id="mem-rail-header")
                for i, item in enumerate(_LAYERS):
                    css = "mem-rail-item-selected" if i == 0 else "mem-rail-item"
                    yield Static(item, id=f"mem-rail-{i}", classes=css)
            with Vertical(id="mem-main"):
                yield Static("", id="mem-recall")
                yield Static("", id="mem-inspect")
                yield Static("", id="mem-vault-facts")
                yield Static("", id="mem-quarantine")

    def populate(self, data: CockpitData) -> None:
        """Build or refresh the memory view from *data*."""
        self._data = data
        snap = data.memory()
        self._hits = data.recall(_DEFAULT_QUERY)
        self._selected = min(self._selected, max(0, len(self._hits) - 1))

        self._update_vault_facts(snap)
        self._render_rail()
        self._render_recall()
        self._render_inspect()
        self._render_vault_facts()
        self._render_quarantine(len(snap.blocked))

    def _update_vault_facts(self, snap: Any) -> None:
        """Refresh _vault_facts from the memory snapshot for the active vault layer."""
        vault_info = _VAULT_LAYER_MAP.get(self._layer)
        if vault_info is None:
            self._vault_facts = []
            return
        group_id = vault_info[0]

        facts: list[Any] = []
        for group in snap.groups:
            if group.id == group_id:
                facts = list(group.facts)
                break
        self._vault_facts = facts
        self._vault_selected = min(self._vault_selected, max(0, len(facts) - 1))

    def _render_rail(self) -> None:
        header = self.query_one("#mem-rail-header", Static)
        h = Text()
        h.append("layers\n", style=MUTED)
        header.update(h)

        for i, item in enumerate(_LAYERS):
            widget = self.query_one(f"#mem-rail-{i}", Static)
            t = Text()
            if i == self._layer:
                t.append(f" {item}", style=f"bold {FOREGROUND}")
                widget.set_classes("mem-rail-item-selected")
            else:
                t.append(f" {item}", style=MUTED)
                widget.set_classes("mem-rail-item")
            widget.update(t)

    def _render_recall(self) -> None:
        header = Text()
        header.append("/  ", style=BRAND)
        header.append(f'"{_DEFAULT_QUERY}"', style=FOREGROUND)
        header.append(f"    {len(self._hits)} hits\n\n", style=MUTED)
        body = _recall_table(self._hits, self._selected)
        combined = Text()
        combined.append_text(header)
        combined.append_text(body)
        self.query_one("#mem-recall", Static).update(combined)

    def _render_inspect(self) -> None:
        hit = self._hits[self._selected] if self._hits else None
        self.query_one("#mem-inspect", Static).update(_inspect_block(hit))

    def _render_vault_facts(self) -> None:
        """Render the vault facts panel when a vault layer is active."""
        widget = self.query_one("#mem-vault-facts", Static)
        vault_info = _VAULT_LAYER_MAP.get(self._layer)
        if vault_info is None:
            widget.update(Text())
            return
        _group_id, group_label = vault_info
        widget.update(_vault_facts_text(self._vault_facts, self._vault_selected, group_label))

    def _render_quarantine(self, blocked_count: int) -> None:
        self.query_one("#mem-quarantine", Static).update(_quarantine_line(blocked_count))

    def move_selection(self, delta: int) -> None:
        """Move the recall row selection by *delta* (+1 = down, -1 = up).

        When a vault layer is active, moves the vault fact selection instead.

        Args:
            delta: direction — +1 moves down, -1 moves up.
        """
        if _VAULT_LAYER_MAP.get(self._layer) is not None:
            if not self._vault_facts:
                return
            self._vault_selected = (self._vault_selected + delta) % len(self._vault_facts)
            self._render_vault_facts()
            return
        if not self._hits:
            return
        self._selected = (self._selected + delta) % len(self._hits)
        self._render_recall()
        self._render_inspect()

    def on_filter(self) -> None:
        """Open the recall search input (hook — currently logs intent).

        The screen calls this when the user presses ``/`` while this view is active.
        A future iteration will mount an Input widget for the query string.
        """
        # Placeholder: in a future iteration mount an Input for the query.
        pass

    # ------------------------------------------------------------------
    # Action hooks (routed from CockpitScreen via _dispatch_optional)
    # ------------------------------------------------------------------

    def delete_selected(self) -> None:
        """Delete the currently selected vault fact (key: x).

        Only active when a vault layer is selected (core/user/agent).
        No-ops gracefully when no data, no facts, or offline.
        """
        if self._data is None:
            return
        vault_info = _VAULT_LAYER_MAP.get(self._layer)
        if vault_info is None:
            try:
                screen: Any = self.app.screen
                if hasattr(screen, "notify_toast"):
                    screen.notify_toast("select a vault layer (core/user/agent) first", glyph="◈")
            except Exception:
                pass
            return
        if not self._vault_facts:
            try:
                screen = self.app.screen
                if hasattr(screen, "notify_toast"):
                    screen.notify_toast("no facts to delete", glyph="◈")
            except Exception:
                pass
            return
        fact = self._vault_facts[self._vault_selected]
        result = self._data.delete_fact(str(fact.id))
        ok = bool(result.get("ok", False)) if result else False
        # Re-populate from gateway after deletion
        snap = self._data.memory()
        self._update_vault_facts(snap)
        self._render_vault_facts()
        self._render_quarantine(len(snap.blocked))
        screen = self.app.screen
        if hasattr(screen, "notify_toast"):
            if ok:
                screen.notify_toast("fact deleted", glyph="✓")
            else:
                screen.notify_toast("delete failed (offline or vault unavailable)", glyph="✗")

    def add_fact(self) -> None:
        """Open the add-fact modal (key: a).

        Only active when a vault layer is selected. On modal submit, writes the
        fact via data.add_fact, re-populates, and shows a toast.
        """
        if self._data is None:
            return
        vault_info = _VAULT_LAYER_MAP.get(self._layer)
        if vault_info is None:
            try:
                screen: Any = self.app.screen
                if hasattr(screen, "notify_toast"):
                    screen.notify_toast("select a vault layer (core/user/agent) first", glyph="◈")
            except Exception:
                pass
            return
        group_id, group_label = vault_info

        def _on_submit(text: str | None) -> None:
            if not text:
                return
            if self._data is None:
                return
            result = self._data.add_fact(group_id, text)
            fact_id = str(result.get("id", ""))
            snap = self._data.memory()
            self._update_vault_facts(snap)
            self._render_vault_facts()
            self._render_quarantine(len(snap.blocked))
            scr: Any = self.app.screen
            if hasattr(scr, "notify_toast"):
                if fact_id and not fact_id.startswith("BLOCKED") and fact_id != "LIMIT_REACHED":
                    scr.notify_toast(f"fact added [{fact_id[:12]}]", glyph="✓")
                elif fact_id.startswith("BLOCKED"):
                    scr.notify_toast("fact blocked by MemoryGuard", glyph="✗")
                elif fact_id == "LIMIT_REACHED":
                    scr.notify_toast("vault limit reached — curate first", glyph="◈")
                else:
                    scr.notify_toast("add failed (offline or vault unavailable)", glyph="✗")

        self.app.push_screen(AddFactModal(group_id, group_label), _on_submit)
