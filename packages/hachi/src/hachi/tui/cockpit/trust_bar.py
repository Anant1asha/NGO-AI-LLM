"""TrustBar — two-row top band widget for the Hachi Cockpit.

Row 1: mascot slot · hachi wordmark · tier badge · centered view label ·
        activity glyph · activity label
Row 2: state counters · approval signal (pulsing when pend) · spacer ·
        spend text · spend bar · model name (navy)

Re-renders via ``set_snapshot(snapshot, view_label, approval_count)`` — called
by the screen whenever the view changes or data is refreshed.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from hachi.client.models import TrustBarSnapshot
from hachi.tui.cockpit.mascot import Mascot
from hachi.tui.theme import (
    AMBER,
    BORDER_MUTED,
    BRAND,
    FOREGROUND,
    GREEN,
    MUTED,
    NAVY,
    SURFACE,
)

# Dim color used in design (not in theme.py constants but part of the palette)
_DIM = "#6E6A74"
# Running animation frame glyphs (design uses ◐◓◑◒)
_FRAMES = ["◐", "◓", "◑", "◒"]


def _bar(filled: int, total: int = 5) -> str:
    """Return a ▓░ spend bar string."""
    filled = max(0, min(total, filled))
    return "▓" * filled + "░" * (total - filled)


def _spend_bar_fill(cost: float, budget: float = 5.0) -> int:
    """Convert cost/budget ratio to a 0–5 fill level."""
    if budget <= 0:
        return 0
    ratio = cost / budget
    return round(ratio * 5)


def _tier_style(tier: str) -> tuple[str, str]:
    """Return (text_color, bg_color) for the tier badge."""
    if tier == "unrestricted":
        return ("#16151A", BRAND)
    return (NAVY, "transparent")


def _mascot_state(snapshot: TrustBarSnapshot) -> str:
    """Derive the mascot state from a TrustBarSnapshot.

    Priority: approval_count > 0 → 'blocked'; reconnecting → 'work';
    active_job_count > 0 → 'work'; else → 'watch'.

    Args:
        snapshot: The current TrustBarSnapshot.

    Returns:
        One of ``watch``, ``work``, ``done``, ``blocked``.
    """
    if snapshot.approval_count > 0:
        return "blocked"
    if snapshot.reconnecting:
        return "work"
    if snapshot.active_job_count > 0:
        return "work"
    return "watch"


class TrustBar(Widget):
    """Two-row top band showing hachi identity, trust state, and spend.

    Composes a ``Mascot`` widget in the mascot slot and a ``Static`` for the
    text content.  The mascot state is derived from each snapshot.

    Usage::

        trust_bar = TrustBar()
        trust_bar.set_snapshot(snapshot, view_label="dashboard")

    The widget re-renders synchronously on ``set_snapshot`` — call it from the
    screen's ``_refresh_trust_bar()`` method after any data change.
    """

    DEFAULT_CSS = f"""
    TrustBar {{
        height: 4;
        width: 1fr;
        background: {SURFACE};
        border-bottom: tall {BORDER_MUTED};
        padding: 0 1;
        color: {FOREGROUND};
        layout: horizontal;
    }}

    TrustBar Mascot {{
        width: 4;
        height: 2;
        margin: 1 1 0 0;
    }}

    TrustBar Static#tb-text {{
        width: 1fr;
        height: 4;
        color: {FOREGROUND};
    }}
    """

    # Internal state — updated by set_snapshot()
    _snapshot: TrustBarSnapshot | None = None
    _view_label: str = "dashboard"
    _approval_count: int = 0
    _frame: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        """Yield the mascot slot and the text content Static."""
        yield Mascot(id="tb-mascot")
        yield Static("", id="tb-text")

    def on_mount(self) -> None:
        """Start animation frame timer (≈300 ms / frame, 4 frames)."""
        self.set_interval(0.3, self._tick_frame)

    def _tick_frame(self) -> None:
        self._frame = (self._frame + 1) % 4
        self._render_content()

    def set_snapshot(
        self,
        snapshot: TrustBarSnapshot,
        view_label: str = "",
        approval_count: int | None = None,
    ) -> None:
        """Update the trust bar with new data and re-render.

        Args:
            snapshot: The TrustBarSnapshot from CockpitData.trust_bar().
            view_label: Human-readable name of the currently active view.
            approval_count: Override the approval count (defaults to snapshot value).
        """
        self._snapshot = snapshot
        self._view_label = view_label
        if approval_count is not None:
            self._approval_count = approval_count
        else:
            self._approval_count = snapshot.approval_count

        # Update mascot state
        try:
            mascot = self.query_one("#tb-mascot", Mascot)
            mascot.set_state(_mascot_state(snapshot))
        except Exception:
            pass  # Not yet mounted — on_mount will handle initial render

        self._render_content()

    def set_view_label(self, label: str) -> None:
        """Update only the centered view label (fast path on view switch)."""
        self._view_label = label
        self._render_content()

    def _render_content(self) -> None:
        """Build and apply the two-row Rich Text renderable to the text Static."""
        snap = self._snapshot
        t = Text(no_wrap=True)

        # ── Row 1 ──────────────────────────────────────────────────────────
        # wordmark
        t.append("hachi", style=f"bold {BRAND}")
        t.append(" ▸ ", style=_DIM)

        # tier badge
        if snap:
            tier = snap.tier or "guided"
            tier_fg, _tier_bg = _tier_style(tier)
            t.append(tier, style=f"bold {tier_fg}")
        else:
            t.append("guided", style=f"bold {NAVY}")

        # center view label (padded)
        center = f"  {self._view_label}  " if self._view_label else ""
        t.append(center, style=_DIM)

        # activity glyph (animated frame) + label
        frame_glyph = _FRAMES[self._frame % 4]
        t.append(frame_glyph, style=AMBER)
        if snap and snap.active_job_count > 0:
            t.append(f"  working · {snap.active_job_count} active", style=MUTED)
        else:
            t.append("  on watch", style=MUTED)

        t.append("\n")

        # ── Row 2 ──────────────────────────────────────────────────────────
        if snap:
            # State counters (only when count > 0)
            active = snap.active_job_count
            if active > 0:
                t.append(f"▶{active}", style=f"bold {AMBER}")
                t.append(" running  ", style=_DIM)

            # Approval signal — pulse only handled via frame animation color alternation
            if self._approval_count > 0:
                # Alternate opacity by showing different shade on even/odd frames
                ap_color = BRAND if self._frame % 2 == 0 else "#C44A36"
                t.append(f"⚠ {self._approval_count}", style=f"bold {ap_color}")
                t.append(" approval  ", style=f"bold {BRAND}")

            # Reconnecting indicator
            if snap.reconnecting:
                t.append("⟳ reconnecting  ", style=MUTED)

        # Spacer (Rich doesn't support flex; we insert blanks)
        t.append("  " * 4, style="")

        # Spend
        if snap:
            cost = snap.total_cost_usd
            budget = 5.0  # default budget display; Wave-3 can expose from config
            fill = _spend_bar_fill(cost, budget)
            t.append(f"${cost:.2f} / ${budget:.2f}  ", style=MUTED)
            t.append(_bar(fill), style=GREEN)

            # Model name — navy, dotted underline (terminal: use bold navy)
            model = snap.model or "—"
            t.append(f"  {model}", style=f"bold {NAVY}")

        try:
            text_widget = self.query_one("#tb-text", Static)
            text_widget.update(t)
        except Exception:
            pass  # Not yet mounted
