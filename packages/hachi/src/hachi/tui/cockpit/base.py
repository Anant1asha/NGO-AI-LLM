"""CockpitView — base class that every cockpit view widget implements.

Wave-3 agents: subclass this, set view_id, implement populate().
See method docstrings for the optional hook protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.widget import Widget

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData


class CockpitView(Widget):
    """Base class for all 12 cockpit view widgets.

    Contract for Wave-3 agents
    --------------------------
    1. Set the class attribute ``view_id`` to match the nav registry entry.
    2. Implement ``populate(data)``.  The screen calls this when switching to
       the view and when the user presses ⌃R (snapshot refresh).
    3. Optionally implement any of the hook methods below.  The screen
       dispatches to them via ``getattr`` / ``hasattr`` — missing hooks are
       silently ignored, so partial implementation is safe.

    Optional hooks (implement only those you need)
    -----------------------------------------------
    ``move_selection(delta: int) -> None``
        Called by j/k (or arrow keys) while this view is active.
        *delta* is +1 (down) or -1 (up).

    ``toggle_inspector() -> None``
        Called by Enter/i. The view should show/hide its inspector pane.

    ``on_filter() -> None``
        Called by /. The view should open its filter input.

    ``decide_top(action: str) -> None``
        Called by y/n/A on the approvals and dashboard views.
        *action* is one of: 'allow', 'deny', 'always'.

    ``activate_selected() -> None``
        Called by Enter when the screen wants to activate the selected row
        (e.g. trace an agent, open a session). Views that use CockpitTable
        may route this to CockpitTable.activate().

    Do NOT override on_key() — the screen owns the keyboard model.
    """

    # Subclasses MUST set this to a value that matches a VIEWS entry in nav.py.
    view_id: ClassVar[str] = ""

    DEFAULT_CSS = """
    CockpitView {
        height: 1fr;
        width: 1fr;
        background: $background;
    }
    """

    def populate(self, data: CockpitData) -> None:  # noqa: ARG002
        """Build or refresh the view content from *data*.

        Called by the screen on:
        - First switch to this view.
        - ⌃R (snapshot refresh) while this view is active.

        Wave-3 agents: replace the stub body here with real widgets.
        The method must be safe to call multiple times (idempotent or additive).
        """
        raise NotImplementedError(
            f"{type(self).__name__}.populate() must be implemented"
        )
