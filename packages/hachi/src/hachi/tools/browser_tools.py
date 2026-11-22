"""LLM-callable browser automation tools.

Exposes a small, powerful surface — ``browse_web`` (navigate + read), ``browser_act``
(click/fill/press/select), and ``browser_screenshot`` — backed by a persistent
:class:`~hachi.core.browser.BrowserController`. Outbound URLs are validated through
``net_guard`` (SSRF mitigation) and the whole capability is gated by permission tier
(disabled in ``sandbox``). Every failure is returned as a readable message rather than
raised, so the agent can recover or report it.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from hachi.core.browser import BrowserController, BrowserUnavailable
from hachi.core.loop import ToolRegistry
from hachi.core.net_guard import validate_outbound_url
from hachi.core.untrusted_content import guard_untrusted

# Browsing performs live web actions (form fills, clicks); keep it out of the
# locked-down sandbox tier. Guided + unrestricted may use it.
_BLOCKED_TIERS = {"sandbox"}


def _tier_blocked(gate: Any | None) -> str | None:
    """Return the blocking tier name if browsing is disallowed, else None."""
    if gate is None:
        return None
    tier = getattr(gate, "tier", None)
    return tier if tier in _BLOCKED_TIERS else None


def _allow_private() -> bool:
    return os.environ.get("HACHI_REST_ALLOW_PRIVATE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _make_browse_web(controller: BrowserController, gate: Any | None) -> Callable[[str], str]:
    def browse_web(url: str) -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: web browsing is disabled in '{tier}' tier."

        ok, reason = validate_outbound_url(url, allow_private=_allow_private())
        if not ok:
            return f"Blocked URL: {reason}"

        try:
            # Pass allow_private so the per-hop redirect guard in BrowserController
            # honours the same escape hatch as the initial URL check above.
            nav = controller.navigate(url, allow_private=_allow_private())
            page = controller.read()
        except BrowserUnavailable as exc:
            return f"Browser unavailable: {exc}"
        except Exception as exc:
            return f"Browse failed: {exc}"

        header = f"# {nav.get('title') or '(untitled)'}\n<{nav.get('url', url)}>\n\n"
        body: str = page.get("text", "")
        if page.get("truncated"):
            body += "\n\n[... page text truncated ...]"
        # Spotlight fetched web content: if it carries a prompt-injection, wrap it
        # so the model treats the page as untrusted data, not as instructions.
        guarded, _flagged = guard_untrusted(header + body, source=nav.get("url", url))
        return guarded

    return browse_web


def _make_browser_act(
    controller: BrowserController, gate: Any | None
) -> Callable[[str, str, str], str]:
    def browser_act(action: str, selector: str, value: str = "") -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: web browsing is disabled in '{tier}' tier."
        try:
            state = controller.act(action=action, selector=selector, value=value)
        except BrowserUnavailable as exc:
            return f"Browser unavailable: {exc}"
        except Exception as exc:
            return f"Action '{action}' on '{selector}' failed: {exc}"
        return (
            f"Did '{action}' on '{selector}'. Now at: {state.get('title')} "
            f"<{state.get('url')}>. Call browse_web's page reader or browser_act again."
        )

    return browser_act


def _make_browser_screenshot(
    controller: BrowserController, gate: Any | None
) -> Callable[[str, bool], str]:
    def browser_screenshot(path: str, full_page: bool = False) -> str:
        tier = _tier_blocked(gate)
        if tier is not None:
            return f"Permission Denied: web browsing is disabled in '{tier}' tier."
        try:
            result = controller.screenshot(path=path, full_page=full_page)
        except BrowserUnavailable as exc:
            return f"Browser unavailable: {exc}"
        except Exception as exc:
            return f"Screenshot failed: {exc}"
        return f"Saved screenshot to {result.get('path', path)}"

    return browser_screenshot


BROWSE_WEB_SCHEMA = {
    "name": "browse_web",
    "description": (
        "Open a web page in a real headless browser and return its visible text (JS-rendered, "
        "not just raw HTML). Use this for live research, reading docs, checking a site, or "
        "starting a multi-step web flow. The browser persists across calls, so after browse_web "
        "you can browser_act (click/fill) and read again. URLs must be http(s) and public."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The http(s) URL to open."},
        },
        "required": ["url"],
    },
}

BROWSER_ACT_SCHEMA = {
    "name": "browser_act",
    "description": (
        "Interact with the page currently open in the browser: click a button/link, fill a text "
        "field, press a key, or select a dropdown option. Use CSS selectors. Run browse_web first "
        "to open a page. After acting, call browse_web again (same URL) or read to see the result."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "fill", "press", "select"],
                "description": "click an element, fill a field, press a key, or select an option.",
            },
            "selector": {"type": "string", "description": "CSS selector of the target element."},
            "value": {
                "type": "string",
                "description": "Text to fill, key to press (default Enter), or option to select.",
            },
        },
        "required": ["action", "selector"],
    },
}

BROWSER_SCREENSHOT_SCHEMA = {
    "name": "browser_screenshot",
    "description": (
        "Capture a PNG screenshot of the page currently open in the browser and save it to a "
        "local path. Useful for visual confirmation or to attach for vision analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute file path to save the PNG."},
            "full_page": {
                "type": "boolean",
                "description": "Capture the full scrollable page (default just the viewport).",
            },
        },
        "required": ["path"],
    },
}


def register_browser_tools(
    registry: ToolRegistry,
    gate: Any | None = None,
    controller: BrowserController | None = None,
) -> BrowserController:
    """Register browser tools and return the controller (so callers can close it).

    Args:
        registry: The tool registry to mount onto.
        gate: Optional PermissionGate; browsing is blocked in the ``sandbox`` tier.
        controller: Inject a controller (tests pass a fake); a real one is created if omitted.
    """
    controller = controller or BrowserController()
    registry.register(BROWSE_WEB_SCHEMA, _make_browse_web(controller, gate))
    registry.register(BROWSER_ACT_SCHEMA, _make_browser_act(controller, gate))
    registry.register(BROWSER_SCREENSHOT_SCHEMA, _make_browser_screenshot(controller, gate))
    return controller
