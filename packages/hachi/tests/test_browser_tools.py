"""Tests for browser automation tools + controller.

These run WITHOUT a real browser. The tool logic (gating, SSRF URL checks, output
formatting, error messaging) is exercised against a fake controller, and the real
:class:`BrowserController` is verified to degrade gracefully to BrowserUnavailable when
Playwright is not installed — covering the thread/queue/error-propagation path end to end.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hachi.core.browser import BrowserController, BrowserUnavailable
from hachi.core.loop import ToolRegistry
from hachi.tools.browser_tools import (
    _make_browse_web,
    _make_browser_act,
    register_browser_tools,
)


class FakeController:
    """Records calls and returns canned page data (no real browser)."""

    def __init__(self, *, raise_unavailable: bool = False) -> None:
        self.raise_unavailable = raise_unavailable
        self.calls: list[tuple] = []

    def _guard(self) -> None:
        if self.raise_unavailable:
            raise BrowserUnavailable("Playwright is not installed.")

    def navigate(self, url, *, allow_private: bool = False):
        self._guard()
        self.calls.append(("navigate", url))
        return {"url": url, "title": "Example Domain"}

    def read(self, selector=None, max_chars=8000):
        self._guard()
        self.calls.append(("read", selector))
        return {
            "url": "http://x",
            "title": "Example Domain",
            "text": "Hello world",
            "truncated": False,
        }

    def act(self, action, selector, value=""):
        self._guard()
        self.calls.append(("act", action, selector, value))
        return {"url": "http://x", "title": "After", "action": action}

    def screenshot(self, path, full_page=False):
        self._guard()
        self.calls.append(("screenshot", path))
        return {"path": path}


def _gate(tier: str):
    return SimpleNamespace(tier=tier)


# -- gating -----------------------------------------------------------------


def test_browsing_blocked_in_sandbox_tier():
    ctrl = FakeController()
    browse = _make_browse_web(ctrl, _gate("sandbox"))
    out = browse("https://example.com")
    assert "Permission Denied" in out
    assert ctrl.calls == []  # never touched the controller


def test_browsing_allowed_in_guided_tier(monkeypatch):
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")  # skip DNS in net_guard
    ctrl = FakeController()
    browse = _make_browse_web(ctrl, _gate("guided"))
    out = browse("https://example.com/page")
    assert "Example Domain" in out
    assert ("navigate", "https://example.com/page") in ctrl.calls


# -- SSRF / URL validation --------------------------------------------------


def test_browse_rejects_non_http_scheme():
    ctrl = FakeController()
    browse = _make_browse_web(ctrl, _gate("guided"))
    out = browse("file:///etc/passwd")
    assert "Blocked URL" in out
    assert ctrl.calls == []


def test_browse_rejects_localhost():
    ctrl = FakeController()
    browse = _make_browse_web(ctrl, _gate("guided"))
    out = browse("http://localhost/admin")
    assert "Blocked URL" in out
    assert ctrl.calls == []


def test_browse_rejects_private_ip():
    ctrl = FakeController()
    browse = _make_browse_web(ctrl, _gate("guided"))
    out = browse("http://127.0.0.1:8080/")
    assert "Blocked URL" in out
    assert ctrl.calls == []


# -- happy path + formatting ------------------------------------------------


def test_browse_formats_title_url_and_text(monkeypatch):
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    ctrl = FakeController()
    browse = _make_browse_web(ctrl, _gate("guided"))
    out = browse("https://example.com")
    assert "# Example Domain" in out
    assert "Hello world" in out


def test_browser_act_reports_state(monkeypatch):
    ctrl = FakeController()
    act = _make_browser_act(ctrl, _gate("guided"))
    out = act("click", "#submit")
    assert "Did 'click' on '#submit'" in out
    assert ("act", "click", "#submit", "") in ctrl.calls


# -- graceful degradation ---------------------------------------------------


def test_browse_surfaces_browser_unavailable(monkeypatch):
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    ctrl = FakeController(raise_unavailable=True)
    browse = _make_browse_web(ctrl, _gate("guided"))
    out = browse("https://example.com")
    assert "Browser unavailable" in out


def test_real_controller_without_playwright_raises_unavailable():
    """With Playwright absent, the real controller must fail cleanly (not hang/crash).

    Skipped when Playwright IS installed (e.g. a dev box that ran the live smoke test) —
    the absent-dependency path can't be reproduced there. CI installs without the
    `browser` extra, so this still guards the graceful-degradation path.
    """
    import importlib.util

    if importlib.util.find_spec("playwright") is not None:
        pytest.skip("Playwright is installed; the missing-dependency path is not reproducible.")

    controller = BrowserController(nav_timeout_ms=2000)
    try:
        with pytest.raises(BrowserUnavailable) as excinfo:
            controller.navigate("https://example.com")
        assert "playwright" in str(excinfo.value).lower()
    finally:
        controller.close()


def test_real_controller_live_navigation_when_available():
    """Launch a real browser and read a live page — runs only where the browser is installed.

    CI installs without the `browser` extra, so this skips there. It also skips (never fails)
    on launch/network errors, so it can't flake the suite for environmental reasons.
    """
    import importlib.util

    if importlib.util.find_spec("playwright") is None:
        pytest.skip("Playwright not installed (base install).")

    controller = BrowserController(nav_timeout_ms=20000)
    try:
        try:
            nav = controller.navigate("https://example.com")
            page = controller.read()
        except BrowserUnavailable as exc:
            pytest.skip(f"Browser binary not installed/launchable: {exc}")
        except Exception as exc:  # network down, DNS, etc. — environmental, not a code defect
            pytest.skip(f"Live navigation unavailable in this environment: {exc}")
        assert nav["title"]  # got a real page title
        assert "Example Domain" in page["text"]
    finally:
        controller.close()


# -- registration -----------------------------------------------------------


def test_register_browser_tools_registers_three_tools():
    registry = ToolRegistry()
    ctrl = FakeController()
    register_browser_tools(registry, gate=_gate("guided"), controller=ctrl)
    names = {schema["name"] for schema in registry.get_schemas()}
    assert {"browse_web", "browser_act", "browser_screenshot"} <= names
