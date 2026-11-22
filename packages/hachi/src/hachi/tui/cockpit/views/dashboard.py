"""DashboardView — Cockpit home "Pulse" panel (Wave-3 implementation).

2-column grid of 6 bordered panels:
  activity · needs-you · the pack · spend today · work queue · recent (audit tail)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Grid
from textual.widgets import Static

from hachi.tui import art as _art
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
    from hachi.client.models import Approval
    from hachi.tui.cockpit.data import CockpitData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bar(filled: int, total: int = 10, filled_char: str = "▓", empty_char: str = "░") -> str:
    """Return a fixed-width block-bar string."""
    filled = max(0, min(filled, total))
    return filled_char * filled + empty_char * (total - filled)


def _needs_you_text(top: Approval | None) -> Text:
    """Build the needs-you panel body."""
    t = Text()
    if top is None:
        t.append("  no pending approvals", style=MUTED)
        return t
    t.append("  ! ", style=BRAND)
    t.append("agent wants  ", style=FOREGROUND)
    t.append(top.action or top.request, style=AMBER)
    t.append("\n  -> ", style=MUTED)
    t.append(", ".join(top.touches) if top.touches else top.scope, style=MUTED)
    t.append("\n  why: ", style=MUTED)
    t.append(top.why[:60], style=MUTED)
    t.append("\n  risk: ", style=MUTED)
    risk_col = DANGER if top.risk == "high" else (AMBER if top.risk == "medium" else GREEN)
    t.append(top.risk, style=risk_col)
    t.append("\n\n  [y approve]  ", style=f"bold {BRAND}")
    t.append("[n deny]", style=NAVY)
    return t


def _pack_text(agents: list) -> Text:  # type: ignore[type-arg]
    """Build the pack panel body (sub-agents)."""
    t = Text()
    if not agents:
        t.append("  no active agents", style=MUTED)
        return t
    for ag in agents[:5]:
        if ag.status == "working":
            status_col, glyph = AMBER, "◐"
        elif ag.status == "pending":
            status_col, glyph = NAVY, "⏰"
        else:
            status_col, glyph = GREEN, "✓"
        t.append(f"  {glyph} ", style=status_col)
        t.append(f"{ag.role:<16}", style=status_col)
        t.append(f"  {ag.task[:28]}", style=MUTED)
        t.append("\n")
    return t


def _spend_text(tb: object) -> Text:
    """Build the spend panel body from a TrustBarSnapshot."""
    t = Text()
    cost = getattr(tb, "total_cost_usd", 0.0)
    jobs = getattr(tb, "active_job_count", 0)
    approvals = getattr(tb, "approval_count", 0)
    model = getattr(tb, "model", "—")
    tier = getattr(tb, "tier", "—")

    t.append("  cost       ", style=MUTED)
    t.append(f"${cost:.4f}", style=GREEN)
    t.append("\n  tier       ", style=MUTED)
    t.append(tier, style=NAVY)
    t.append("\n  model      ", style=MUTED)
    t.append(model[:28], style=MUTED)
    t.append("\n  active     ", style=MUTED)
    t.append(str(jobs), style=AMBER)
    t.append("  jobs\n  pending    ", style=MUTED)
    t.append(str(approvals), style=BRAND if approvals > 0 else MUTED)
    t.append("  approvals\n", style=MUTED)
    t.append("  tokens  ", style=MUTED)
    t.append(_bar(5), style=NAVY)
    return t


def _work_queue_text(tasks: list) -> Text:  # type: ignore[type-arg]
    """Build the work queue panel body."""
    t = Text()
    if not tasks:
        t.append("  no active tasks", style=MUTED)
        return t
    glyphs: dict[str, tuple[str, str]] = {
        "working": ("▶", AMBER),
        "on-watch": ("⧖", NAVY),
        "blocked": ("⛔", DANGER),
        "done": ("✓", GREEN),
    }
    for task in tasks[:6]:
        glyph, col = glyphs.get(task.status, ("▶", MUTED))
        t.append(f"  {glyph} ", style=col)
        t.append(f"{task.title[:38]}", style=FOREGROUND if task.status == "working" else MUTED)
        t.append("\n")
    return t


def _recent_text(audit: list) -> Text:  # type: ignore[type-arg]
    """Build the recent/audit-tail panel body."""
    t = Text()
    for entry in audit[:6]:
        t.append(f"  {entry.ts}  ", style=MUTED)
        decision_col = (
            GREEN if entry.decision in ("allowed", "automatic")
            else DANGER if entry.decision == "declined"
            else MUTED
        )
        t.append(f"{entry.op[:20]:<22}", style=decision_col)
        t.append(f"{entry.target[:18]}", style=MUTED)
        t.append("\n")
    if not audit:
        t.append("  no audit entries", style=MUTED)
    return t


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


class DashboardView(CockpitView):  # type: ignore[misc]
    """Cockpit home — 2-column grid of 6 bordered panels (Pulse view).

    Layout
    ------
    Row 1: activity (loyal-loop motif + tool bar) | needs-you (top approval + y/n)
    Row 2: the pack (sub-agents)                 | spend today (cost/tokens/tier)
    Row 3: work queue (active tasks)             | recent (audit tail)

    Data used
    ---------
    data.dashboard() -> DashboardSnapshot (active_jobs, pending_approvals,
                                           recent_sessions, trust_bar)
    data.agents()    -> list[AgentRow]
    data.audit()     -> list[AuditEntry]

    Hooks
    -----
    decide_top(action)  — approve/deny the top pending approval via
                          data.decide_approval(top.id, action), then re-populates.
    """

    view_id: ClassVar[str] = "dashboard"

    DEFAULT_CSS = f"""
    DashboardView {{
        height: 1fr;
        width: 1fr;
        background: {SURFACE};
        overflow-y: auto;
        padding: 1 1;
    }}
    #dash-grid {{
        grid-size: 2 3;
        grid-gutter: 1 2;
        height: auto;
    }}
    .dash-panel {{
        border: solid {BORDER_MUTED};
        padding: 0 1 1 1;
        height: auto;
        min-height: 9;
    }}
    .dash-panel-brand {{
        border: solid {BRAND};
        padding: 0 1 1 1;
        height: auto;
        min-height: 9;
    }}
    """

    _top_approval: Approval | None = None
    _data: CockpitData | None = None

    def compose(self) -> ComposeResult:  # noqa: D102
        with Grid(id="dash-grid"):
            yield Static("", id="activity-panel", classes="dash-panel")
            yield Static("", id="needs-you-panel", classes="dash-panel-brand")
            yield Static("", id="pack-panel", classes="dash-panel")
            yield Static("", id="spend-panel", classes="dash-panel")
            yield Static("", id="work-panel", classes="dash-panel")
            yield Static("", id="recent-panel", classes="dash-panel")

    def populate(self, data: CockpitData) -> None:
        """Build or refresh all six dashboard panels from *data*."""
        self._data = data

        snap = data.dashboard()
        agents = data.agents()
        audit = data.audit(limit=6)

        tb = snap.trust_bar
        approvals = list(snap.pending_approvals)
        self._top_approval = approvals[0] if approvals else None

        # ── activity ────────────────────────────────────────────────────────
        act = Text()
        act.append("activity\n", style=MUTED)
        loop_line = _art.ouroboros(width=24, height=5)
        act.append_text(loop_line)
        act.append("\n")
        act.append("Hachi is working", style=f"bold {FOREGROUND}")
        act.append("\n  tools/turn  ", style=MUTED)
        act.append(_bar(5), style=AMBER)
        act.append("  5 / turn", style=MUTED)
        self.query_one("#activity-panel", Static).update(act)

        # ── needs you ───────────────────────────────────────────────────────
        ny = Text()
        label_col = BRAND if self._top_approval else MUTED
        ny.append("needs you\n", style=label_col)
        ny.append_text(_needs_you_text(self._top_approval))
        self.query_one("#needs-you-panel", Static).update(ny)

        # ── the pack ────────────────────────────────────────────────────────
        pack = Text()
        live = sum(1 for a in agents if a.status == "working")
        pack.append(f"the pack  ({live} live)\n", style=MUTED)
        pack.append_text(_pack_text(agents))
        self.query_one("#pack-panel", Static).update(pack)

        # ── spend ────────────────────────────────────────────────────────────
        spend = Text()
        spend.append("spend today\n", style=MUTED)
        spend.append_text(_spend_text(tb))
        self.query_one("#spend-panel", Static).update(spend)

        # ── work queue ───────────────────────────────────────────────────────
        work = Text()
        n_tasks = len(snap.active_jobs)
        work.append(f"work queue  ({n_tasks} active)\n", style=MUTED)
        work.append_text(_work_queue_text(list(snap.active_jobs)))
        self.query_one("#work-panel", Static).update(work)

        # ── recent (audit tail) ──────────────────────────────────────────────
        recent = Text()
        recent.append("recent  (audit tail)\n", style=MUTED)
        recent.append_text(_recent_text(audit))
        self.query_one("#recent-panel", Static).update(recent)

    def decide_top(self, action: str) -> None:
        """Approve or deny the top pending approval.

        Args:
            action: one of ``'allow'``, ``'deny'``, ``'always'``.
        """
        if self._top_approval is not None and self._data is not None:
            self._data.decide_approval(self._top_approval.id, action)
            self.populate(self._data)
