"""ApprovalModal — leash dialog for pending approval requests.

Shows the approval details (agent, action, target, why, risk, policy) and
lets the operator decide: allow once, deny, or always allow host.

Design language: calm, non-alarming.  Copy theme: "you hold the leash."

Usage (from CockpitScreen)::

    approvals = self.cockpit_data.approvals()
    if approvals:
        self.app.push_screen(ApprovalModal(approvals[0], self))
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from hachi.client.models import Approval
from hachi.tui.theme import AMBER, BRAND, DANGER, FOREGROUND, MUTED, NAVY, SURFACE

if TYPE_CHECKING:
    from hachi.tui.cockpit.screen import CockpitScreen

_DIM = "#6E6A74"

# Map risk level to a display color
_RISK_COLOR: dict[str, str] = {
    "low": "#3F9D6B",   # GREEN
    "medium": AMBER,
    "high": DANGER,
}


def _risk_badge(risk: str) -> Text:
    """Return a colored risk badge Text fragment."""
    color = _RISK_COLOR.get(risk, MUTED)
    t = Text()
    t.append(f" {risk} ", style=f"bold {color}")
    return t


class ApprovalModal(ModalScreen[None]):
    """Leash dialog for a single pending approval request.

    Args:
        approval: The ``Approval`` model to display.
        cockpit_screen: Reference to the CockpitScreen (for decide + toast).

    Keys
    ----
    y   allow once (BRAND primary)
    n   deny
    A   always allow host
    esc deny and close
    """

    DEFAULT_CSS = f"""
    ApprovalModal {{
        align: center middle;
    }}

    ApprovalModal > Vertical#approval-box {{
        width: 56;
        height: auto;
        background: {SURFACE};
        border: tall {DANGER};
        padding: 1 2;
    }}

    ApprovalModal Static.ap-title {{
        color: {BRAND};
        text-style: bold;
        margin-bottom: 1;
    }}

    ApprovalModal Static.ap-field {{
        color: {FOREGROUND};
        margin-bottom: 0;
    }}

    ApprovalModal Static.ap-label {{
        color: {_DIM};
    }}

    ApprovalModal Static.ap-footer {{
        color: {MUTED};
        margin-top: 1;
        text-align: center;
    }}

    ApprovalModal Horizontal#ap-buttons {{
        height: 3;
        margin-top: 1;
        align: center middle;
    }}

    ApprovalModal Button {{
        margin: 0 1;
        min-width: 12;
    }}

    ApprovalModal Button#btn-allow {{
        background: {BRAND};
        color: {FOREGROUND};
    }}

    ApprovalModal Button#btn-deny {{
        background: {NAVY};
        color: {FOREGROUND};
    }}

    ApprovalModal Button#btn-always {{
        background: {_DIM};
        color: {FOREGROUND};
    }}
    """

    BINDINGS = [
        ("y", "allow_once", "Allow once"),
        ("n", "deny", "Deny"),
        ("A", "always_allow", "Always allow"),
        ("escape", "deny", "Deny"),
    ]

    def __init__(
        self,
        approval: Approval,
        cockpit_screen: CockpitScreen,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._approval = approval
        self._cockpit_screen = cockpit_screen

    def compose(self) -> ComposeResult:
        """Yield the approval dialog layout."""
        ap = self._approval
        with Vertical(id="approval-box"):
            yield Static("approval needed", classes="ap-title")

            # Action row
            action_text = Text(no_wrap=True)
            action_text.append(f"  {ap.op}  ", style=f"bold {FOREGROUND}")
            action_text.append(ap.action, style=FOREGROUND)
            yield Static(action_text, classes="ap-field")

            # Why row
            why_text = Text(no_wrap=False)
            why_text.append("  why  ", style=f"{_DIM}")
            why_text.append(ap.why, style=FOREGROUND)
            yield Static(why_text, classes="ap-field")

            # Risk + policy row
            rp_text = Text(no_wrap=True)
            rp_text.append("  risk  ", style=f"{_DIM}")
            rp_text.append_text(_risk_badge(ap.risk))
            rp_text.append("   policy  ", style=f"{_DIM}")
            rp_text.append(ap.policy, style=FOREGROUND)
            yield Static(rp_text, classes="ap-field")

            # Scope / touches row (if populated)
            if ap.touches:
                touches_str = "  ".join(ap.touches)
                scope_text = Text(no_wrap=False)
                scope_text.append("  touches  ", style=f"{_DIM}")
                scope_text.append(touches_str, style=MUTED)
                yield Static(scope_text, classes="ap-field")

            # Buttons
            with Horizontal(id="ap-buttons"):
                yield Button("n  deny", id="btn-deny", variant="default")
                yield Button("y  allow once", id="btn-allow", variant="default")
                yield Button("A  always allow", id="btn-always", variant="default")

            yield Static("  esc · deny   you hold the leash", classes="ap-footer")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch the correct action based on which button was pressed."""
        btn_id = event.button.id
        if btn_id == "btn-allow":
            self.action_allow_once()
        elif btn_id == "btn-deny":
            self.action_deny()
        elif btn_id == "btn-always":
            self.action_always_allow()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_allow_once(self) -> None:
        """Allow this request once and close."""
        self._decide("allow", "allowed once")

    def action_deny(self) -> None:
        """Deny this request and close."""
        self._decide("deny", "denied")

    def action_always_allow(self) -> None:
        """Always allow this host and close."""
        self._decide("always", "always allowed for this host")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _decide(self, action: str, toast_suffix: str) -> None:
        """Call decide_approval, pop the modal, and show a toast.

        Args:
            action: One of ``allow``, ``deny``, ``always``.
            toast_suffix: Appended to the toast message for feedback.
        """
        self._cockpit_screen.cockpit_data.decide_approval(self._approval.id, action)
        self.dismiss()
        self._cockpit_screen.notify_toast(
            f"{self._approval.op} {toast_suffix}",
            glyph="",
            color=BRAND if action != "deny" else NAVY,
        )
