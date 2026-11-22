"""GovernanceView — Permissions / governance editor (Wave-3 implementation).

Left rail: Permissions · Budgets · Approval Rules · Safety · Integrations
Content pane: selected section rendered as bordered static text.

Default pane (Permissions) shows filesystem/terminal/mcp posture from
config() + an "ungated tools" warning derived from capabilities() (risky+enabled).
Rail selection via j/k (move_selection hook).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

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
    from hachi.tui.cockpit.data import CockpitData

_RAIL_ITEMS = ["Permissions", "Budgets", "Approval Rules", "Safety", "Integrations"]


def _permissions_text(cfg: object, risky_ungated: list) -> Text:  # type: ignore[type-arg]
    """Render the Permissions pane content."""
    tier = getattr(cfg, "tier", "guided")
    safety = getattr(cfg, "safety", "standard")

    t = Text()
    t.append("permissions", style=f"bold {FOREGROUND}")
    t.append("  tier: ", style=MUTED)
    t.append(tier, style=NAVY)
    t.append("\n\n")

    # filesystem block
    t.append("filesystem ", style=FOREGROUND)
    t.append("write ", style=MUTED)
    t.append("✓", style=GREEN)
    t.append("  delete ", style=MUTED)
    t.append("✗", style=DANGER)
    t.append("  max 50 MB\n", style=MUTED)
    t.append("  allowed  ~/Desktop  ~/Downloads  ~/Documents\n", style=MUTED)
    t.append("  blocked  ~/.ssh  ~/.hachi  ~/Library  (always on)\n\n", style=MUTED)

    # terminal block
    t.append("terminal ", style=FOREGROUND)
    t.append("enabled ", style=MUTED)
    t.append("✓", style=GREEN)
    t.append("  timeout 120s\n", style=MUTED)
    t.append("  allowed  git npm pip ls cd cat ...\n", style=MUTED)
    t.append("  blocked  rm -rf  shutdown  format  reg delete  (always on)\n\n", style=MUTED)

    # mcp
    t.append("mcp fs ", style=FOREGROUND)
    t.append("enabled ", style=MUTED)
    t.append("✓\n\n", style=GREEN)

    # safety tier note
    t.append("safety posture: ", style=MUTED)
    safety_col = GREEN if safety == "guarded" else (AMBER if safety == "standard" else DANGER)
    t.append(safety, style=safety_col)
    t.append("\n\n")

    # ungated tools warning
    if risky_ungated:
        t.append("! ", style=DANGER)
        names = "  ·  ".join(c.name for c in risky_ungated[:6])
        n = len(risky_ungated)
        t.append(f"{n} integration tools run WITHOUT an approval gate:\n", style=DANGER)
        t.append(f"  {names}\n", style=MUTED)
        t.append("  [G] require approval for all of these  (recommended)\n", style=NAVY)
    else:
        t.append("All risky tools are gated ", style=GREEN)
        t.append("✓\n", style=GREEN)

    t.append("\n")
    t.append("  edits write ~/.hachi/device-permissions.og\n", style=MUTED)
    t.append("  changes apply next launch  [H] hot-reload now", style=AMBER)
    return t


def _budgets_text() -> Text:
    t = Text()
    t.append("budgets\n\n", style=f"bold {FOREGROUND}")
    t.append("  daily spend cap   ", style=MUTED)
    t.append("$5.00\n", style=GREEN)
    t.append("  per-task cap      ", style=MUTED)
    t.append("$1.00\n", style=GREEN)
    t.append("  token cap / turn  ", style=MUTED)
    t.append("32 000\n\n", style=MUTED)
    t.append("  Budget caps are enforced by the gateway before each LLM call.\n", style=MUTED)
    t.append("  [e] edit caps\n", style=NAVY)
    return t


def _approval_rules_text() -> Text:
    t = Text()
    t.append("approval rules\n\n", style=f"bold {FOREGROUND}")
    t.append("  tier: guided  — asks before each tool call\n\n", style=MUTED)
    t.append("  auto-allow  ", style=GREEN)
    t.append("read_file  list_dir  search_web\n", style=MUTED)
    t.append("  auto-deny   ", style=DANGER)
    t.append("shell(rm*)  delete_*  send_email\n", style=MUTED)
    t.append("  ask-first   ", style=AMBER)
    t.append("write_file  browse_web  network_*\n\n", style=MUTED)
    t.append("  [e] edit rules\n", style=NAVY)
    return t


def _safety_text() -> Text:
    t = Text()
    t.append("safety\n\n", style=f"bold {FOREGROUND}")
    t.append("  prompt guard      ", style=MUTED)
    t.append("enabled ✓\n", style=GREEN)
    t.append("  memory guard      ", style=MUTED)
    t.append("enabled ✓\n", style=GREEN)
    t.append("  tool call signing ", style=MUTED)
    t.append("enabled ✓\n", style=GREEN)
    t.append("  sub-agent sandbox ", style=MUTED)
    t.append("enabled ✓\n\n", style=GREEN)
    t.append("  [T] change tier\n", style=NAVY)
    return t


def _integrations_text(capabilities: list) -> Text:  # type: ignore[type-arg]
    t = Text()
    t.append("integrations\n\n", style=f"bold {FOREGROUND}")
    if not capabilities:
        t.append("  no integrations configured\n", style=MUTED)
        return t
    for cap in capabilities:
        if cap.status == "connected":
            status_col, status_glyph = GREEN, "✓"
        elif cap.status == "degraded":
            status_col, status_glyph = AMBER, "~"
        else:
            status_col, status_glyph = MUTED, "—"
        t.append(f"  {status_glyph} ", style=status_col)
        t.append(f"{cap.name:<20}", style=FOREGROUND if cap.configured else MUTED)
        t.append(f"  {cap.can[:34]}", style=MUTED)
        if cap.risky:
            t.append("  [risky]", style=AMBER)
        t.append("\n")
    return t


class GovernanceView(CockpitView):  # type: ignore[misc]
    """Permissions / governance editor with left-rail nav.

    Layout
    ------
    Left rail (180 cols): Permissions · Budgets · Approval Rules · Safety · Integrations
    Content pane: populated based on selected rail index.

    Data used
    ---------
    data.config()        -> ConfigSnapshot  (tier, safety, model)
    data.capabilities()  -> list[Capability]  (risky+enabled => ungated warning)

    Hooks
    -----
    move_selection(delta)  — j/k moves the rail selection and re-renders the pane.
    """

    view_id: ClassVar[str] = "governance"

    DEFAULT_CSS = f"""
    GovernanceView {{
        height: 1fr;
        width: 1fr;
        background: {SURFACE};
    }}
    #gov-rail {{
        width: 24;
        border-right: solid {BORDER_MUTED};
        padding: 1 0;
        height: 1fr;
    }}
    .gov-rail-item {{
        padding: 0 1;
        height: 1;
        color: {MUTED};
    }}
    .gov-rail-item-selected {{
        padding: 0 1;
        height: 1;
        color: {FOREGROUND};
        background: {BRAND};
    }}
    #gov-content {{
        padding: 1 2;
        overflow-y: auto;
        height: 1fr;
    }}
    """

    _selected: int = 0
    _data: CockpitData | None = None

    def compose(self) -> ComposeResult:  # noqa: D102
        with Horizontal():
            with Vertical(id="gov-rail"):
                for i, item in enumerate(_RAIL_ITEMS):
                    css = "gov-rail-item-selected" if i == 0 else "gov-rail-item"
                    yield Static(item, id=f"gov-rail-{i}", classes=css)
            with Vertical(id="gov-content"):
                yield Static("", id="gov-pane")

    def populate(self, data: CockpitData) -> None:
        """Build or refresh the governance view from *data*."""
        self._data = data
        self._render_rail()
        self._render_pane()

    def _render_rail(self) -> None:
        for i, item in enumerate(_RAIL_ITEMS):
            widget = self.query_one(f"#gov-rail-{i}", Static)
            if i == self._selected:
                t = Text()
                t.append(f"  {item}", style=f"bold {FOREGROUND}")
                widget.update(t)
                widget.set_classes("gov-rail-item-selected")
            else:
                t = Text()
                t.append(f"  {item}", style=MUTED)
                widget.update(t)
                widget.set_classes("gov-rail-item")

    def _render_pane(self) -> None:
        if self._data is None:
            return
        pane = self.query_one("#gov-pane", Static)
        cfg = self._data.config()
        caps = self._data.capabilities()

        if self._selected == 0:
            risky_ungated = [c for c in caps if c.risky and c.enabled]
            pane.update(_permissions_text(cfg, risky_ungated))
        elif self._selected == 1:
            pane.update(_budgets_text())
        elif self._selected == 2:
            pane.update(_approval_rules_text())
        elif self._selected == 3:
            pane.update(_safety_text())
        else:
            pane.update(_integrations_text(caps))

    def move_selection(self, delta: int) -> None:
        """Move the rail selection by *delta* (+1 = down, -1 = up) and refresh.

        Args:
            delta: direction — +1 moves down, -1 moves up.
        """
        self._selected = (self._selected + delta) % len(_RAIL_ITEMS)
        self._render_rail()
        self._render_pane()

    # ------------------------------------------------------------------
    # Authoring actions (keyed a/v from CockpitScreen.on_key)
    # ------------------------------------------------------------------

    def _first_dirty_target(self) -> str | None:
        """Return the name of the first authoring target, or None if none exist."""
        if self._data is None:
            return None
        targets = self._data.authoring_targets()
        if not targets:
            return None
        return str(targets[0].name)

    def authoring_apply(self) -> None:
        """Apply the pending patch for the first authoring target.

        After the call the view re-renders and a toast is shown on the screen.
        Gracefully no-ops when there is no target or no data.
        """
        if self._data is None:
            return
        name = self._first_dirty_target()
        if name is None:
            screen: Any = self.app.screen
            if hasattr(screen, "notify_toast"):
                screen.notify_toast("no authoring targets to apply", glyph="◈")
            return
        self._data.authoring_apply(name)
        self._render_pane()
        screen = self.app.screen
        if hasattr(screen, "notify_toast"):
            screen.notify_toast(f"{name} applied · re-indexed", glyph="✓")

    def authoring_revert(self) -> None:
        """Revert the first authoring target to disk.

        After the call the view re-renders and a toast is shown on the screen.
        Gracefully no-ops when there is no target or no data.
        """
        if self._data is None:
            return
        name = self._first_dirty_target()
        if name is None:
            screen: Any = self.app.screen
            if hasattr(screen, "notify_toast"):
                screen.notify_toast("no authoring targets to revert", glyph="◈")
            return
        self._data.authoring_revert(name)
        self._render_pane()
        screen = self.app.screen
        if hasattr(screen, "notify_toast"):
            screen.notify_toast(f"{name} reverted to disk", glyph="⟳")

    def change_tier(self) -> None:
        """Cycle the permission tier: sandbox → guided → unrestricted (key: T).

        Reads current tier from config, cycles to the next, and persists via
        PUT /config/permissions.  Re-renders the pane and shows a toast.
        Silently no-ops when offline or no data.
        """
        _TIERS = ["sandbox", "guided", "unrestricted"]
        if self._data is None:
            return
        cfg = self._data.config()
        current_tier = cfg.tier if cfg else "guided"
        try:
            idx = _TIERS.index(current_tier)
            next_idx = (idx + 1) % len(_TIERS)
        except ValueError:
            next_idx = 0
        next_tier = _TIERS[next_idx]
        self._data.change_tier(next_tier)
        # Re-render using freshly fetched config so the display reflects the change.
        self._render_pane()
        screen: Any = self.app.screen
        if hasattr(screen, "notify_toast"):
            screen.notify_toast(f"tier → {next_tier}", glyph="⟳")
