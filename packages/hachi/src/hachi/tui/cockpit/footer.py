"""CockpitFooter — bottom key-hints band for the Hachi Cockpit.

Left side: hint string  ``<view>  ·  :cmd  ?help  ·  ⌃O altitude``
Right side: per-view key hints from nav.footer_keys(view_id) as
            ``key  label`` pairs (key in BRAND, label in dim).

Re-renders via ``set_view(view_id)`` — called by the screen on every view switch.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Static

from hachi.tui.cockpit.nav import footer_keys
from hachi.tui.theme import BORDER_MUTED, BRAND, SURFACE

_DIM = "#6E6A74"


class CockpitFooter(Static):
    """Bottom one-line band showing contextual key hints.

    Usage::

        footer = CockpitFooter()
        footer.set_view("agents")

    The screen calls ``set_view`` after every ``go(view_id)`` call.
    """

    DEFAULT_CSS = f"""
    CockpitFooter {{
        height: 1;
        width: 1fr;
        background: {SURFACE};
        border-top: tall {BORDER_MUTED};
        padding: 0 1;
    }}
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._view_id: str = "dashboard"

    def on_mount(self) -> None:
        self._render_footer()

    def set_view(self, view_id: str) -> None:
        """Update the footer for *view_id* and re-render."""
        self._view_id = view_id
        self._render_footer()

    def _render_footer(self) -> None:
        """Build and apply the footer Rich Text renderable."""
        view_id = self._view_id
        t = Text(no_wrap=True)

        # Left hint
        t.append(f"{view_id}", style=_DIM)
        t.append("  ·  :cmd  ?help  ·  ⌃O altitude", style=_DIM)

        # Spacer (terminal — use spaces)
        t.append("  " * 6)

        # Per-view key hints
        keys = footer_keys(view_id)
        for i, fk in enumerate(keys):
            t.append(fk.key, style=f"bold {BRAND}")
            t.append(f" {fk.label}", style=_DIM)
            if i < len(keys) - 1:
                t.append("  ", style="")

        self.update(t)
