"""CockpitApp — self-contained Textual host for the Hachi Cockpit.

Can be run independently (for development / testing) or imported by the main
HachiTextualApp integration (which happens later, by a separate agent).

Usage::

    # Offline / placeholder data
    app = CockpitApp()
    app.run()

    # Online mode (gateway at given URL)
    app = CockpitApp(base_url="http://127.0.0.1:8787", token="my-token")
    app.run()

    # Programmatic test
    async with CockpitApp().run_test() as pilot:
        await pilot.press("g", "d")  # navigate to dashboard
"""

from __future__ import annotations

from typing import Any

from textual.app import App

from hachi.tui.cockpit.data import CockpitData
from hachi.tui.cockpit.screen import CockpitScreen
from hachi.tui.theme import HACHI_THEME

# ---------------------------------------------------------------------------
# Shared CSS for the cockpit chrome.
# View agents can reference these class names in their own DEFAULT_CSS.
#
# Stable classes / IDs (do NOT rename — Wave-3 agents use these):
#   #cockpit-trust-bar   — the TrustBar band
#   #cockpit-switcher    — the ContentSwitcher holding all 12 view widgets
#   #cockpit-footer      — the CockpitFooter band
#   #view-<view_id>      — individual view widgets (e.g. #view-agents)
#   .ct-row              — a row in CockpitTable
#   .ct-row.selected     — selected row in CockpitTable
#   #ct-main             — table main pane
#   #ct-inspector        — table inspector panel
#   #ct-inspector.visible — inspector when shown
#   #ct-tabs             — table tabs row
#   #ct-header           — table column header row
#   #ct-rows             — scrollable rows container
#   #ct-footer           — table status/countdown footer
# ---------------------------------------------------------------------------

_COCKPIT_CSS = """
/* ── Canvas ─────────────────────────────────────────────────────── */
Screen {
    background: #16151A;
    color: #FBF7EF;
}

/* ── Trust bar ────────────────────────────────────────────────────── */
#cockpit-trust-bar {
    height: 4;
    background: #201E25;
    border-bottom: tall #322F38;
    padding: 0 1;
}

/* ── Content switcher (middle band) ──────────────────────────────── */
#cockpit-switcher {
    height: 1fr;
    width: 1fr;
    background: #16151A;
}

/* ── Footer ──────────────────────────────────────────────────────── */
#cockpit-footer {
    height: 1;
    background: #201E25;
    border-top: tall #322F38;
    padding: 0 1;
}

/* ── CockpitTable internals ──────────────────────────────────────── */
#ct-inspector {
    width: 38;
    border-left: tall #322F38;
    background: #201E25;
    overflow-y: auto;
    padding: 1 2;
    display: none;
}

#ct-inspector.visible {
    display: block;
}

#ct-header {
    height: 1;
    color: #6E6A74;
    border-bottom: tall #322F38;
    padding: 0 1;
}

#ct-rows {
    height: 1fr;
    overflow-y: auto;
}

.ct-row {
    height: 1;
    padding: 0 1;
}

.ct-row.selected {
    background: rgba(255, 255, 255, 0.04);
}

#ct-footer {
    height: 1;
    border-top: tall #322F38;
    padding: 0 1;
    display: none;
    color: #6E6A74;
}

#ct-footer.visible {
    display: block;
}
"""


class CockpitApp(App[None]):
    """Self-contained host app for the Hachi Cockpit.

    Attributes:
        cockpit_data: The CockpitData facade shared across all views.
            CockpitScreen reads this via ``self.app.cockpit_data``.
    """

    TITLE = "hachi cockpit"
    SUB_TITLE = "you hold the leash"

    CSS = _COCKPIT_CSS

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Create the CockpitApp.

        Args:
            base_url: Gateway base URL. If None, runs in offline/placeholder mode.
            token: Optional bearer token for the gateway.
        """
        super().__init__(**kwargs)

        # Build data facade
        client = None
        if base_url is not None:
            try:
                from hachi.client.gateway import GatewayClient
                client = GatewayClient(base_url=base_url, token=token)
            except Exception:
                client = None

        self.cockpit_data: CockpitData = CockpitData(client)

    def on_mount(self) -> None:
        """Register the hachi theme and push the cockpit screen."""
        self.register_theme(HACHI_THEME)
        self.theme = HACHI_THEME.name
        self.push_screen(CockpitScreen())
