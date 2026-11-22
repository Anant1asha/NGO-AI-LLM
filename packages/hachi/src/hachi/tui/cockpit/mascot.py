"""Mascot — compact terminal-friendly state indicator for the TrustBar.

Renders a tiny 2-row half-block "face" that changes color by state.
Kept to <=4 columns so it fits within the TrustBar band.

States
------
``watch``   NAVY — calm, on watch
``work``    AMBER — active, processing
``done``    GREEN — task completed
``blocked`` DANGER — approval required

Usage::

    m = Mascot()
    m.set_state("blocked")
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from hachi.tui.theme import AMBER, DANGER, GREEN, NAVY

# Top and bottom half-block chars for the 2-row "face"
_TOP = "▀"  # upper half block ▀
_BOT = "▄"  # lower half block ▄

# (color, top-glyphs, bot-glyphs) per state
_PATTERNS: dict[str, tuple[str, str, str]] = {
    "watch":   (NAVY,   f"{_TOP}{_TOP}", f"{_BOT}{_BOT}"),
    "work":    (AMBER,  f"{_TOP}{_TOP}", f"{_BOT}{_BOT}"),
    "done":    (GREEN,  f"{_TOP}{_TOP}", f"{_BOT}{_BOT}"),
    "blocked": (DANGER, f"{_TOP}{_TOP}", f"{_BOT}{_BOT}"),
}

_DEFAULT_STATE = "watch"


def _build_text(state: str) -> Text:
    """Build the Rich Text renderable for *state*.

    Args:
        state: One of ``watch``, ``work``, ``done``, ``blocked``.

    Returns:
        A two-line Rich Text with colored glyphs.
    """
    color, top_glyphs, bot_glyphs = _PATTERNS.get(state, _PATTERNS[_DEFAULT_STATE])
    t = Text(no_wrap=True)
    t.append(top_glyphs, style=f"bold {color}")
    t.append("\n")
    t.append(bot_glyphs, style=f"bold {color}")
    return t


class Mascot(Static):
    """Compact 2-row half-block mascot for the TrustBar.

    Color changes by state; glyphs stay constant.
    Fits in <=4 terminal cells wide.

    Constructed with the initial 'watch' renderable so Textual 8.x never
    sees a None visual during the first layout pass.
    """

    DEFAULT_CSS = """
    Mascot {
        width: 4;
        height: 2;
    }
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        # Pass initial renderable to Static so visual is never None at render time
        initial = _build_text(_DEFAULT_STATE)
        super().__init__(initial, *args, **kwargs)  # type: ignore[arg-type]
        self._state: str = _DEFAULT_STATE

    def set_state(self, state: str) -> None:
        """Switch the mascot to *state*.

        Args:
            state: One of ``watch``, ``work``, ``done``, ``blocked``.
                   Unknown values fall back to ``watch``.
        """
        self._state = state if state in _PATTERNS else _DEFAULT_STATE
        self.update(_build_text(self._state))

    @property
    def state(self) -> str:
        """Return the current mascot state string."""
        return self._state
