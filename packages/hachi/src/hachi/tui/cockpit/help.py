"""HelpModal — keymap cheat-sheet overlay for the Hachi Cockpit.

Shows four groups of key bindings in a two-column grid, matching the
design's help keymap exactly.  Press ``?`` or ``escape`` to close.

Usage (from CockpitScreen)::

    self.app.push_screen(HelpModal())
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from hachi.tui.theme import BORDER_MUTED, FOREGROUND, MUTED, NAVY, SURFACE

_DIM = "#6E6A74"

# Keymap data: list of (group_title, [(key, description), ...])
_KEYMAP: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "global",
        [
            ("ctrl+k", "command palette"),
            ("ctrl+o", "toggle chat / cockpit"),
            ("ctrl+j", "session switcher"),
            ("ctrl+r", "refresh snapshot"),
            ("?", "this help"),
        ],
    ),
    (
        "go to  (g + letter)",
        [
            ("gc", "chat"),
            ("gd", "dashboard"),
            ("ga", "agents"),
            ("gt", "tasks"),
            ("gp", "approvals"),
            ("gg", "governance"),
            ("gm", "memory"),
            ("gk", "skills"),
            ("gl", "audit"),
            ("gr", "resources"),
            ("gn", "connections"),
            ("gs", "settings"),
        ],
    ),
    (
        "operator focus",
        [
            ("j / k", "move selection"),
            ("enter / i", "toggle inspector"),
            ("/", "filter"),
            ("esc", "close inspector"),
        ],
    ),
    (
        "chat focus",
        [
            ("enter", "send"),
            ("shift+enter", "newline"),
            ("esc", "interrupt"),
            ("a", "open approval"),
        ],
    ),
]


def _render_group(title: str, bindings: list[tuple[str, str]]) -> Text:
    """Render a single keymap group as a Rich Text block.

    Args:
        title: Group heading (displayed uppercase, muted).
        bindings: Ordered list of (key, description) pairs.

    Returns:
        Rich Text block with the heading and all key rows.
    """
    t = Text(no_wrap=False)
    t.append(f"  {title.upper()}\n", style=f"bold {_DIM}")
    for key, desc in bindings:
        t.append(f"  {key:<18}", style=f"bold {NAVY}")
        t.append(f"{desc}\n", style=FOREGROUND)
    return t


class HelpModal(ModalScreen[None]):
    """Keymap cheat-sheet modal.

    Two-column layout: left column has global + go-to groups;
    right column has operator-focus + chat-focus groups.
    Press ``?`` or ``escape`` to dismiss.
    """

    DEFAULT_CSS = f"""
    HelpModal {{
        align: center middle;
    }}

    HelpModal > Vertical {{
        width: 62;
        height: auto;
        max-height: 90vh;
        background: {SURFACE};
        border: tall {BORDER_MUTED};
        padding: 1 2;
    }}

    HelpModal Static.help-title {{
        color: {FOREGROUND};
        text-style: bold;
        margin-bottom: 1;
    }}

    HelpModal Static.help-col {{
        width: 1fr;
        color: {FOREGROUND};
    }}

    HelpModal Static.help-footer {{
        color: {MUTED};
        margin-top: 1;
        text-align: center;
    }}
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Yield the modal container with title, two columns, and footer."""
        with Vertical():
            yield Static("  keymap", classes="help-title")
            # Left column: global + go to
            left = Text(no_wrap=False)
            global_title, global_bindings = _KEYMAP[0]
            left.append_text(_render_group(global_title, global_bindings))
            left.append("\n")
            goto_title, goto_bindings = _KEYMAP[1]
            left.append_text(_render_group(goto_title, goto_bindings))
            yield Static(left, classes="help-col")
            # Right column: operator focus + chat focus
            right = Text(no_wrap=False)
            op_title, op_bindings = _KEYMAP[2]
            right.append_text(_render_group(op_title, op_bindings))
            right.append("\n")
            chat_title, chat_bindings = _KEYMAP[3]
            right.append_text(_render_group(chat_title, chat_bindings))
            yield Static(right, classes="help-col")
            yield Static("  esc · close", classes="help-footer")
