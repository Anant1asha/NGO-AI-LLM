"""Focused SSRF security tests for E9/T9.1 (http_request) and E9/T9.2 (browse_web).

Covers:
  (a) http_request / UniversalRestAdapter blocks private/loopback/metadata IPs
      and delegates to net_guard (no duplicate logic).
  (b) browse_web aborts redirect hops that land on a private host via the
      BrowserController per-hop route handler.

All tests run without a real network or browser binary.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from hachi.core.browser import BrowserController, BrowserUnavailable
from hachi.core.loop import ToolRegistry
from hachi.core.net_guard import ValidationResult, validate_outbound_url
from hachi.tools.browser_tools import _make_browse_web

# ---------------------------------------------------------------------------
# (a) net_guard coverage — metadata and private IPs
# ---------------------------------------------------------------------------


class TestNetGuardSsrfCoverage:
    """Ensure net_guard catches the canonical SSRF target classes."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/latest/meta-data/",  # AWS/GCP/Azure cloud metadata
            "http://169.254.169.254/",  # link-local root
            "http://127.0.0.1/admin",  # loopback IPv4
            "http://[::1]/admin",  # loopback IPv6
            "http://10.0.0.1/internal",  # RFC-1918 class A
            "http://192.168.1.1/router",  # RFC-1918 class C
            "http://172.16.0.1/private",  # RFC-1918 class B
            "http://0.0.0.0/",  # unspecified
            "http://localhost/secret",  # localhost by name
        ],
    )
    def test_blocked_private_and_metadata_urls(self, url: str) -> None:
        ok, reason = validate_outbound_url(url)
        assert not ok, f"Expected {url!r} to be blocked; got ok=True"

    def test_cloud_metadata_is_link_local(self) -> None:
        """169.254.169.254 must be caught by the link-local check specifically."""
        import ipaddress

        addr = ipaddress.ip_address("169.254.169.254")
        assert addr.is_link_local, "AWS metadata IP must be link-local"

    def test_allow_private_bypasses_private_ip(self) -> None:
        ok, _ = validate_outbound_url("http://10.0.0.5/hook", allow_private=True)
        assert ok

    def test_public_ip_allowed(self) -> None:
        ok, reason = validate_outbound_url("http://1.1.1.1/")
        assert ok, reason


# ---------------------------------------------------------------------------
# (a) UniversalRestAdapter delegates to net_guard (no duplicate logic)
# ---------------------------------------------------------------------------


class TestRestAdapterSsrfDelegation:
    """UniversalRestAdapter._validate_outbound_url must go through net_guard.

    BB-53: an unset ``HACHI_REST_ALLOWLIST`` must fail CLOSED (deny all hosts),
    not fail open. These tests exercise net_guard's own IP/scheme checks, so
    they pass an explicit allowlist covering the host under test — this is the
    secure equivalent of "no allowlist configured" for a test that wants to
    reach net_guard rather than being short-circuited by the allowlist gate.
    """

    def _make_adapter(
        self, allow_private: bool = False, allowed_hosts: list[str] | None = None
    ) -> object:
        from hachi.core.rest_adapter import UniversalRestAdapter

        registry = ToolRegistry()
        adapter = UniversalRestAdapter(
            registry,
            allowed_hosts=allowed_hosts
            or ["1.1.1.1", "127.0.0.1", "169.254.169.254", "192.168.0.1", "10.0.0.5"],
        )
        adapter._allow_private_egress = allow_private
        return adapter

    def test_blocks_loopback(self) -> None:
        adapter = self._make_adapter()
        error, _ = adapter._validate_outbound_url("http://127.0.0.1/admin", includes_secret=False)
        assert error is not None
        assert (
            "127.0.0.1" in error
            or "non-public" in error
            or "loopback" in error.lower()
            or "private" in error.lower()
        )  # noqa: E501

    def test_blocks_metadata_endpoint(self) -> None:
        adapter = self._make_adapter()
        error, _ = adapter._validate_outbound_url(
            "http://169.254.169.254/latest/meta-data/", includes_secret=False
        )
        assert error is not None, "Cloud metadata endpoint must be blocked"

    def test_blocks_private_rfc1918(self) -> None:
        adapter = self._make_adapter()
        error, _ = adapter._validate_outbound_url("http://192.168.0.1/", includes_secret=False)
        assert error is not None

    def test_allow_private_bypasses(self) -> None:
        adapter = self._make_adapter(allow_private=True)
        error, _ = adapter._validate_outbound_url("http://10.0.0.5/hook", includes_secret=False)
        assert error is None, "allow_private=True must pass private addresses through"

    def test_public_url_passes(self) -> None:
        adapter = self._make_adapter()
        # Use a literal public IP to avoid real DNS lookup in tests.
        error, _ = adapter._validate_outbound_url("http://1.1.1.1/", includes_secret=False)
        assert error is None, f"Public IP should be allowed; got: {error}"

    def test_non_http_scheme_blocked(self) -> None:
        adapter = self._make_adapter()
        error, _ = adapter._validate_outbound_url("file:///etc/passwd", includes_secret=False)
        assert error is not None

    def test_net_guard_is_called(self) -> None:
        """_validate_outbound_url must invoke net_guard, not its own IP logic."""
        adapter = self._make_adapter()
        with patch(
            "hachi.core.rest_adapter._net_guard_validate",
            return_value=ValidationResult(ok=False, reason="mocked-block"),
        ) as mock_guard:
            error, _ = adapter._validate_outbound_url("http://1.1.1.1/", includes_secret=False)
        mock_guard.assert_called_once()
        assert error == "mocked-block"

    def test_allowlist_checked_before_net_guard(self) -> None:
        """When an allowlist is configured, a host not on it is rejected before net_guard."""
        from hachi.core.rest_adapter import UniversalRestAdapter

        registry = ToolRegistry()
        adapter = UniversalRestAdapter(registry, allowed_hosts=["api.allowed.com"])
        error, _ = adapter._validate_outbound_url("http://other-host.com/", includes_secret=False)
        assert error is not None
        assert "HACHI_REST_ALLOWLIST" in error

    def test_unset_allowlist_env_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """BB-53: with HACHI_REST_ALLOWLIST unset, requests to an arbitrary public host
        must be DENIED (fail closed), not permitted (fail open)."""
        from hachi.core.rest_adapter import UniversalRestAdapter

        monkeypatch.delenv("HACHI_REST_ALLOWLIST", raising=False)
        registry = ToolRegistry()
        adapter = UniversalRestAdapter(registry)
        assert adapter.allowed_hosts == []

        error, _ = adapter._validate_outbound_url(
            "http://arbitrary-public-host.example.com/", includes_secret=False
        )
        assert error is not None, (
            "An unset HACHI_REST_ALLOWLIST must deny outbound requests to any host, "
            "not silently allow them"
        )
        assert "HACHI_REST_ALLOWLIST" in error


# ---------------------------------------------------------------------------
# (b) BrowserController per-hop redirect guard (unit-tested without browser)
# ---------------------------------------------------------------------------


class TestBrowserPerHopSsrfGuard:
    """Unit-tests for the per-hop redirect route handler in BrowserController."""

    def _make_handler(self, allow_private: bool = False):
        return BrowserController._make_ssrf_route_handler(allow_private)

    # ---- helper to build a fake route/request pair ----

    @staticmethod
    def _fake_route(url: str):
        route = MagicMock()
        request = MagicMock()
        request.url = url
        return route, request

    def test_public_url_is_continued(self) -> None:
        handler = self._make_handler()
        route, request = self._fake_route("https://1.1.1.1/page")
        handler(route, request)
        route.continue_.assert_called_once()
        route.abort.assert_not_called()

    def test_private_ip_redirect_is_aborted(self) -> None:
        handler = self._make_handler(allow_private=False)
        route, request = self._fake_route("http://192.168.1.1/admin")
        handler(route, request)
        route.abort.assert_called_once_with("blockedbyclient")
        route.continue_.assert_not_called()

    def test_loopback_redirect_is_aborted(self) -> None:
        handler = self._make_handler(allow_private=False)
        route, request = self._fake_route("http://127.0.0.1/secret")
        handler(route, request)
        route.abort.assert_called_once_with("blockedbyclient")

    def test_metadata_redirect_is_aborted(self) -> None:
        handler = self._make_handler(allow_private=False)
        route, request = self._fake_route("http://169.254.169.254/latest/meta-data/")
        handler(route, request)
        route.abort.assert_called_once_with("blockedbyclient")

    def test_allow_private_permits_private_redirect(self) -> None:
        handler = self._make_handler(allow_private=True)
        route, request = self._fake_route("http://10.0.0.5/internal")
        handler(route, request)
        route.continue_.assert_called_once()
        route.abort.assert_not_called()

    def test_non_http_scheme_redirect_is_aborted(self) -> None:
        handler = self._make_handler(allow_private=False)
        route, request = self._fake_route("file:///etc/passwd")
        handler(route, request)
        route.abort.assert_called_once_with("blockedbyclient")

    def test_localhost_redirect_is_aborted(self) -> None:
        handler = self._make_handler(allow_private=False)
        # localhost resolves to loopback — net_guard must block it
        route, request = self._fake_route("http://localhost/admin")
        handler(route, request)
        route.abort.assert_called_once_with("blockedbyclient")


# ---------------------------------------------------------------------------
# (b) browse_web integration — redirect to private host is blocked
# ---------------------------------------------------------------------------


class FakeControllerWithRedirectSimulation:
    """FakeController that simulates a server-side redirect to a private address.

    On the first navigate() call it records the URL (simulating the initial hop),
    then raises ``BrowserUnavailable`` with a message that includes 'aborted' to
    represent what happens when Playwright's route handler calls route.abort().
    This lets us verify that the tool layer surfaces the abort correctly.
    """

    def __init__(self, redirect_target: str) -> None:
        self.redirect_target = redirect_target
        self.navigate_calls: list[str] = []

    def navigate(self, url: str, *, allow_private: bool = False) -> dict:
        self.navigate_calls.append(url)
        # Simulate the per-hop guard aborting the redirect hop.
        ok, reason = validate_outbound_url(self.redirect_target, allow_private=allow_private)
        if not ok:
            raise BrowserUnavailable(f"Navigation aborted: redirect to blocked address ({reason})")
        return {"url": url, "title": "Redirected"}

    def read(self, **_kwargs) -> dict:
        return {"url": self.redirect_target, "title": "Redirected", "text": "", "truncated": False}


def _gate(tier: str):
    return SimpleNamespace(tier=tier)


def test_browse_web_surfaces_aborted_private_redirect(monkeypatch) -> None:
    """When a navigation is aborted because a redirect hop lands on a private host,
    browse_web must surface the failure — never return private content."""
    # redirect target = cloud metadata endpoint
    ctrl = FakeControllerWithRedirectSimulation(redirect_target="http://169.254.169.254/meta")
    browse = _make_browse_web(ctrl, _gate("guided"))

    # Start at a legitimate public URL.
    out = browse("https://1.1.1.1/page")

    # The tool must NOT return page content from the private address.
    assert "169.254.169.254" not in out or "Browser unavailable" in out or "aborted" in out.lower()
    # Must surface the failure, not silently succeed.
    assert any(
        phrase in out for phrase in ("Browser unavailable", "aborted", "Blocked", "blocked")
    ), f"Expected failure message in output, got: {out!r}"


def test_browse_web_private_redirect_allow_private_succeeds(monkeypatch) -> None:
    """With allow_private=True the redirect to a private address should NOT be aborted."""
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")

    ctrl = FakeControllerWithRedirectSimulation(redirect_target="http://10.0.0.5/internal")
    browse = _make_browse_web(ctrl, _gate("guided"))

    # The initial URL must also pass net_guard — use a private address so both
    # the initial check and the redirect simulation use allow_private=True.
    out = browse("http://10.0.0.5/page")

    # Should NOT be blocked — allow_private lets it through.
    assert "Blocked URL" not in out
