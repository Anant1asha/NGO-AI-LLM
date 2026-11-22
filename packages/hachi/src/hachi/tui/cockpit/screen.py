"""CockpitScreen — the single Textual Screen for the Hachi Cockpit.

Implements the full keyboard model from the design's ``onKey`` handler:
- g-prefix navigation (0.9 s window)
- ctrl+k / : → command palette stub
- ctrl+o → altitude toggle (chat ↔ last cockpit view)
- ctrl+j → session switcher toast
- ctrl+r → snapshot refresh
- ? → help modal stub
- j/k / arrows → move_selection on active view
- enter/i → toggle_inspector
- escape → close inspector
- / → filter toast
- y/n/A → decide_top on approvals / dashboard views
- dashboard drill-down shortcuts a/p/t/r/l

Public methods (stable — Wave-3 must NOT rename these)
------------------------------------------------------
``go(view_id)``           Switch to a view by id.
``toggle_altitude()``     Toggle between chat and the last cockpit view.
``open_palette()``        Open the command palette overlay (stub → Wave-3 wires real modal).
``open_help()``           Open the help keymap overlay (stub → Wave-3 wires real modal).
``notify_toast(text, glyph, color)``  Show a Textual notify toast.

Wave-3 overlay agent: replace the notify stubs in ``open_palette`` and ``open_help``
with real modal pushes.  Signature must not change.

The screen reads ``self.app.cockpit_data`` if present; otherwise it constructs
``CockpitData(None)`` (offline mode).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import ContentSwitcher

from hachi.tui.cockpit.approval import ApprovalModal
from hachi.tui.cockpit.footer import CockpitFooter
from hachi.tui.cockpit.help import HelpModal
from hachi.tui.cockpit.nav import VIEWS, view_by_mnemonic
from hachi.tui.cockpit.palette import CommandPalette
from hachi.tui.cockpit.trust_bar import TrustBar
from hachi.tui.cockpit.views import VIEW_REGISTRY
from hachi.tui.theme import BRAND, NAVY

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

# Default starting view
_DEFAULT_VIEW = "dashboard"
# How long the g-prefix window stays open (seconds)
_G_PREFIX_TIMEOUT = 0.9


class CockpitScreen(Screen[None]):
    """The single cockpit surface.

    Layout
    ------
    TrustBar (top, height 4)
    ContentSwitcher (middle, 1fr — holds all 12 view widgets)
    CockpitFooter (bottom, height 1)
    """

    # Disable auto-focus on mount. The chat view's composer Input is the first
    # focusable widget in the ContentSwitcher; with auto-focus it would grab
    # focus and swallow the cockpit's navigation keys (g-prefix, j/k, …).
    # NOTE: "" disables auto-focus; None would *inherit* the App's AUTO_FOCUS
    # ("*") and still focus the Input. The composer is focused explicitly via
    # ChatView.activate_selected() when the user enters chat and presses Enter.
    AUTO_FOCUS = ""

    DEFAULT_CSS = """
    CockpitScreen {
        layout: vertical;
        background: #16151A;
    }

    CockpitScreen > ContentSwitcher {
        height: 1fr;
        width: 1fr;
        border: none;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._current_view: str = _DEFAULT_VIEW
        self._last_cockpit: str = _DEFAULT_VIEW
        self._g_prefix: bool = False
        self._g_timer: Timer | None = None
        self._inspector_open: bool = True

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Yield TrustBar → ContentSwitcher (all 12 views) → CockpitFooter."""
        yield TrustBar(id="cockpit-trust-bar")
        with ContentSwitcher(initial=_DEFAULT_VIEW, id="cockpit-switcher"):
            for meta in VIEWS:
                view_cls = VIEW_REGISTRY[meta.view_id]
                yield view_cls(id=f"view-{meta.view_id}")
        yield CockpitFooter(id="cockpit-footer")

    # ------------------------------------------------------------------
    # Mount — populate initial view
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate the initial view, seed the trust bar, and start auto-refresh."""
        self._refresh_trust_bar()
        self._populate_current_view()
        self._update_footer()
        self.set_interval(3.0, self._cockpit_auto_refresh)

    def _cockpit_auto_refresh(self) -> None:
        """Periodic background refresh (every 3 s).

        Always refreshes the trust bar.  Re-populates the active view only when:
        - This screen is on top of the app screen stack (no modal/overlay open).
        - The active view is NOT the chat view (chat owns its own SSE stream).
        """
        # Guard: skip if another screen (modal/overlay) is on top.
        if self.app.screen is not self:
            return

        self._refresh_trust_bar()

        if self._current_view != "chat":
            self._populate_current_view()

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    @property
    def cockpit_data(self) -> CockpitData:
        """Return CockpitData from the app, or construct an offline instance."""
        if hasattr(self.app, "cockpit_data"):
            # self.app is typed as App; cockpit_data is a custom attr we add in CockpitApp.
            app: Any = self.app
            return app.cockpit_data
        # Lazy offline fallback
        from hachi.tui.cockpit.data import CockpitData
        return CockpitData(None)

    # ------------------------------------------------------------------
    # Public navigation API
    # ------------------------------------------------------------------

    def go(self, view_id: str) -> None:
        """Switch to *view_id*.

        Updates the ContentSwitcher, TrustBar label, footer, and calls populate().
        """
        if view_id not in VIEW_REGISTRY:
            self.notify_toast(f"unknown view: {view_id}", glyph="✗", color=BRAND)
            return

        if view_id != "chat":
            self._last_cockpit = view_id
        self._current_view = view_id

        # Release focus on every switch so a previously-focused composer (chat)
        # doesn't keep swallowing keys from a now-hidden pane. The chat composer
        # re-focuses only on demand via ChatView.activate_selected().
        self.set_focus(None)

        # Switch the content pane
        switcher = self.query_one("#cockpit-switcher", ContentSwitcher)
        switcher.current = f"view-{view_id}"

        # Update chrome
        self._refresh_trust_bar()
        self._update_footer()
        self._populate_current_view()

    def toggle_altitude(self) -> None:
        """Toggle between chat (focus) and the last cockpit view."""
        if self._current_view == "chat":
            self.go(self._last_cockpit)
        else:
            self.go("chat")

    def open_palette(self) -> None:
        """Open the command palette overlay.

        Signature is stable; do not change it.
        """
        self.app.push_screen(CommandPalette(self))

    def open_help(self) -> None:
        """Open the help keymap overlay.

        Signature is stable; do not change it.
        """
        self.app.push_screen(HelpModal())

    def open_approval_modal(self) -> None:
        """Open the approval detail modal for the top pending approval.

        Signature is stable; do not change it.
        """
        approvals = self.cockpit_data.approvals()
        if approvals:
            self.app.push_screen(ApprovalModal(approvals[0], self))
        else:
            self.notify_toast("no approvals waiting — Hachi is resting", color=NAVY)

    def notify_toast(self, text: str, glyph: str = "", color: str = NAVY) -> None:
        """Show a Textual notify toast.

        Args:
            text: Toast message text.
            glyph: Optional leading icon (ignored in Textual notify but kept for
                   API parity with the design model).
            color: Not used by Textual's notify; reserved for future overlay toasts.
        """
        prefix = f"{glyph} " if glyph else ""
        self.app.notify(f"{prefix}{text}")

    # ------------------------------------------------------------------
    # Keyboard model (mirrors design's onKey exactly)
    # ------------------------------------------------------------------

    def on_key(self, event: Any) -> None:
        """Handle the full keyboard model from the design prototype."""
        key = event.key

        # g-prefix armed — next letter routes to a view
        if self._g_prefix:
            if self._g_timer is not None:
                self._g_timer.stop()
                self._g_timer = None
            self._g_prefix = False
            meta = view_by_mnemonic(key)
            if meta is not None:
                self.go(meta.view_id)
            event.prevent_default()
            return

        # ctrl chords
        if event.is_printable is False or key.startswith("ctrl+"):
            ctrl_char = key.replace("ctrl+", "")
            if ctrl_char == "k":
                self.open_palette()
                event.prevent_default()
                return
            if ctrl_char == "o":
                self.toggle_altitude()
                event.prevent_default()
                return
            if ctrl_char == "j":
                self.notify_toast("session switcher", glyph="⌃J", color=NAVY)
                event.prevent_default()
                return
            if ctrl_char == "r":
                self.notify_toast("snapshot refreshed", glyph="⟳", color=NAVY)
                self._populate_current_view()
                event.prevent_default()
                return

        # g-prefix arm
        if key == "g":
            self._g_prefix = True
            self._g_timer = self.set_timer(_G_PREFIX_TIMEOUT, self._clear_g_prefix)
            event.prevent_default()
            return

        # Command palette via colon
        if key == "colon":
            self.open_palette()
            event.prevent_default()
            return

        # Help
        if key == "question_mark":
            self.open_help()
            event.prevent_default()
            return

        view = self._current_view

        # Chat focus keys
        if view == "chat":
            if key == "enter":
                active = self._active_view()
                if active is not None and hasattr(active, "activate_selected"):
                    active.activate_selected()
                event.prevent_default()
                return
            if key == "a":
                self.open_approval_modal()
                event.prevent_default()
                return
            return  # other keys pass through in chat

        # Cockpit data views
        active = self._active_view()

        if key in ("j", "down"):
            self._dispatch_optional(active, "move_selection", 1)
            event.prevent_default()
            return

        if key in ("k", "up"):
            self._dispatch_optional(active, "move_selection", -1)
            event.prevent_default()
            return

        if key in ("enter", "i"):
            self._dispatch_optional(active, "toggle_inspector")
            self._inspector_open = not self._inspector_open
            event.prevent_default()
            return

        if key == "escape":
            # Close inspector
            self._inspector_open = False
            self._dispatch_optional(active, "toggle_inspector")
            event.prevent_default()
            return

        if key == "slash":
            self.notify_toast(f"filter {view}", glyph="/", color=NAVY)
            self._dispatch_optional(active, "on_filter")
            event.prevent_default()
            return

        # Approval-specific shortcuts
        if view == "approvals":
            if key == "y":
                self._handle_decide_top(active, "allow")
                event.prevent_default()
                return
            if key == "n":
                self._handle_decide_top(active, "deny")
                event.prevent_default()
                return
            if key == "A":
                self._handle_decide_top(active, "always")
                event.prevent_default()
                return

        # Connections-specific shortcuts
        # e — toggle enable/disable the selected capability (mirrors the inspector
        #     "enable / configure" primary action label in the design).
        if view == "connections":
            if key == "e":
                self._dispatch_optional(active, "toggle_capability")
                event.prevent_default()
                return

        # Governance-specific shortcuts
        # a — apply the selected authoring target's pending patch
        # v — revert the selected authoring target to disk
        # T — cycle permission tier (sandbox → guided → unrestricted)
        # (H = hot-reload listed in design footer for governance; a/v/T are unambiguous
        #  and not already claimed in that view)
        if view == "governance":
            if key == "a":
                self._dispatch_optional(active, "authoring_apply")
                event.prevent_default()
                return
            if key == "v":
                self._dispatch_optional(active, "authoring_revert")
                event.prevent_default()
                return
            if key == "T":
                self._dispatch_optional(active, "change_tier")
                event.prevent_default()
                return

        # Memory-specific shortcuts
        # x — delete the selected vault fact
        # a — open the add-fact modal
        if view == "memory":
            if key == "x":
                self._dispatch_optional(active, "delete_selected")
                event.prevent_default()
                return
            if key == "a":
                self._dispatch_optional(active, "add_fact")
                event.prevent_default()
                return

        # Settings-specific shortcuts
        # m — cycle to the next available model
        if view == "settings":
            if key == "m":
                self._dispatch_optional(active, "switch_model")
                event.prevent_default()
                return

        # Dashboard-specific shortcuts
        if view == "dashboard":
            if key == "y":
                self._handle_decide_top(active, "allow")
                event.prevent_default()
                return
            if key == "n":
                self._handle_decide_top(active, "deny")
                event.prevent_default()
                return
            dash_map = {"a": "approvals", "p": "approvals", "t": "tasks",
                        "r": "resources", "l": "audit"}
            if key in dash_map:
                self.go(dash_map[key])
                event.prevent_default()
                return

    def _clear_g_prefix(self) -> None:
        """Timer callback — clear the g-prefix window after timeout."""
        self._g_prefix = False
        self._g_timer = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _active_view(self) -> Widget | None:
        """Return the currently active CockpitView widget, or None."""
        try:
            return self.query_one(f"#view-{self._current_view}")
        except Exception:
            return None

    def _dispatch_optional(
        self, widget: Widget | None, method: str, *args: Any
    ) -> None:
        """Call *method* on *widget* if it exists, silently skipping if absent."""
        if widget is None:
            return
        fn = getattr(widget, method, None)
        if callable(fn):
            fn(*args)

    def _populate_current_view(self) -> None:
        """Call populate() on the currently active view."""
        active = self._active_view()
        if active is not None and hasattr(active, "populate"):
            try:
                active.populate(self.cockpit_data)
            except Exception as exc:
                self.notify_toast(f"populate error: {exc}", glyph="✗", color=BRAND)

    def _refresh_trust_bar(self) -> None:
        """Fetch trust_bar data and update the TrustBar widget."""
        try:
            snap = self.cockpit_data.trust_bar()
            tb = self.query_one("#cockpit-trust-bar", TrustBar)
            tb.set_snapshot(snap, view_label=self._current_view)
        except Exception as exc:
            self.notify_toast(f"trust bar error: {exc}", glyph="✗", color=BRAND)

    def _update_footer(self) -> None:
        """Update the footer for the current view."""
        try:
            footer = self.query_one("#cockpit-footer", CockpitFooter)
            footer.set_view(self._current_view)
        except Exception:
            pass

    def _handle_decide_top(self, active: Widget | None, action: str) -> None:
        """Dispatch *decide_top(action)* then refresh the trust bar + show a toast.

        Keeps the post-action cycle (decide → re-fetch → toast) in one place so
        both the approvals view and the dashboard view share identical behaviour.

        Args:
            active: The currently active CockpitView widget (may be None).
            action: One of 'allow', 'deny', 'always'.
        """
        self._dispatch_optional(active, "decide_top", action)
        self._refresh_trust_bar()
        _labels = {"allow": "allowed", "deny": "denied", "always": "always allowed"}
        label = _labels.get(action, action)
        self.notify_toast(f"{label} · Hachi resumed", color=NAVY)
