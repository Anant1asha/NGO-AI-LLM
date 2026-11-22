"""Tests for outbound URL SSRF validation (uses literal IPs — no real DNS)."""

from __future__ import annotations

import ipaddress

import pytest

from hachi.core.net_guard import ValidationResult, validate_outbound_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://evil/",
        "ftp://example.com/x",
        "http://127.0.0.1/admin",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/internal",
        "http://192.168.1.1/router",
        "http://[::1]/admin",
        "http://0.0.0.0/",
        "not-a-url",
    ],
)
def test_unsafe_urls_are_rejected(url: str) -> None:
    ok, _reason = validate_outbound_url(url)
    assert ok is False


@pytest.mark.parametrize("url", ["http://1.1.1.1/hook", "https://8.8.8.8/notify"])
def test_public_ip_urls_are_allowed(url: str) -> None:
    ok, reason = validate_outbound_url(url)
    assert ok is True, reason


def test_allow_private_bypass() -> None:
    # Explicit opt-in (e.g. a self-hosted internal webhook) skips the IP check.
    ok, _reason = validate_outbound_url("http://10.0.0.5/internal", allow_private=True)
    assert ok is True


# ---- P-04: CGNAT / overlay networks were neither "private" nor blocked ----


@pytest.mark.parametrize(
    "url",
    [
        # RFC 6598 shared address space — Tailscale hands these out.
        "http://100.64.0.1/",
        "http://100.64.0.0/",
        "http://100.100.100.100/",  # Tailscale MagicDNS
        "http://100.127.255.255/",  # last address of 100.64.0.0/10
        # IPv4-mapped IPv6 form of the same address. ipaddress reports the mapped
        # form as is_private=False, so a denylist of 100.64.0.0/10 misses it —
        # membership tests return False for ::ffff:100.64.0.1.
        "http://[::ffff:100.64.0.1]/",
    ],
)
def test_cgnat_and_overlay_addresses_are_rejected(url: str) -> None:
    """100.64.0.0/10 is neither is_private nor is_global — it must still be blocked."""
    ok, reason = validate_outbound_url(url)
    assert ok is False, f"{url} was allowed; CGNAT/overlay hosts must be rejected"
    assert "non-public" in reason or "blocked" in reason.lower()


@pytest.mark.parametrize(
    "url",
    [
        # Just outside 100.64.0.0/10 on both sides — ordinary public space.
        # A naive `startswith("100.")` rule would wrongly block these.
        "http://100.63.255.255/",
        "http://100.128.0.0/",
    ],
)
def test_public_neighbours_of_cgnat_are_allowed(url: str) -> None:
    ok, reason = validate_outbound_url(url)
    assert ok is True, f"{url} was blocked but is public; reason={reason}"


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://127.0.0.1/admin",
        "http://0.0.0.0/",
        "http://[::1]/admin",
        # NAT64 is_reserved=True even though is_global=True — a bare
        # `return addr.is_global` rewrites would regress this.
        "http://[64:ff9b::1.2.3.4]/",
    ],
)
def test_existing_rejections_survive_the_is_global_change(url: str) -> None:
    ok, _reason = validate_outbound_url(url)
    assert ok is False


@pytest.mark.parametrize("url", ["http://1.1.1.1/", "http://8.8.8.8/", "http://[2606:4700::1111]/"])
def test_genuinely_public_addresses_still_pass(url: str) -> None:
    ok, reason = validate_outbound_url(url)
    assert ok is True, reason


def test_allow_private_hatch_still_covers_cgnat() -> None:
    """The documented opt-in must keep working for self-hosted tailnet services."""
    ok, reason = validate_outbound_url("http://100.64.0.1/", allow_private=True)
    assert ok is True, reason


# ---- the gateway guard is a separate code path and must agree ----


def test_cgnat_is_neither_global_nor_private_on_this_python() -> None:
    """Pin the CPython premise the guard is written against.

    `net_guard` does not rely on `is_global` alone for 100.64.0.0/10 — there is
    an explicit range check — but the premise is worth asserting: if CPython ever
    reports `is_global is True` for CGNAT, this fails loudly instead of the
    guard's behaviour changing silently underneath us.
    """
    addr = ipaddress.ip_address("100.64.0.1")
    assert addr.is_global is False
    assert addr.is_private is False


_CORPUS = [
    "http://100.64.0.1/",
    "http://100.100.100.100/",
    "http://100.127.255.255/",
    "http://[::ffff:100.64.0.1]/",
    "http://100.63.255.255/",
    "http://100.128.0.0/",
    "http://1.1.1.1/",
    "http://8.8.8.8/",
    "http://169.254.169.254/",
    "http://10.0.0.5/",
    "http://127.0.0.1/",
    "http://0.0.0.0/",
    "http://[64:ff9b::1.2.3.4]/",
    "http://[2606:4700::1111]/",
]


def test_gateway_and_core_guards_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compare the two implementations directly rather than hardcoding expectations.

    The previous version of this test hardcoded nine booleans, so it could not
    detect divergence — it only re-stated its own table. The gateway now
    delegates to core, and this asserts that.
    """
    from hachi.gateway._net_guard import is_safe_outbound_url

    monkeypatch.delenv("HACHI_REST_ALLOW_PRIVATE", raising=False)
    for url in _CORPUS:
        # ValidationResult unpacks as (ok, reason) but is not indexable.
        core_ok, _reason = validate_outbound_url(url)
        gateway_ok = is_safe_outbound_url(url)
        assert gateway_ok == core_ok, (
            f"guards disagree for {url}: gateway={gateway_ok} core={core_ok}"
        )


def test_gateway_allow_private_hatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tailnet Ollama endpoint must remain reachable via the documented opt-in."""
    from hachi.gateway._net_guard import is_safe_outbound_url

    monkeypatch.delenv("HACHI_REST_ALLOW_PRIVATE", raising=False)
    assert is_safe_outbound_url("http://100.64.0.1:11434/") is False
    assert is_safe_outbound_url("http://100.64.0.1:11434/", allow_private=True) is True


def test_gateway_honours_rest_allow_private_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`HACHI_REST_ALLOW_PRIVATE` is honoured here, as the channel senders do."""
    from hachi.gateway._net_guard import is_safe_outbound_url

    for value in ("1", "true", "TRUE", "yes"):
        monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", value)
        assert is_safe_outbound_url("http://100.64.0.1:11434/") is True, value

    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "0")
    assert is_safe_outbound_url("http://100.64.0.1:11434/") is False


def test_gateway_guard_loopback_exemption_is_preserved() -> None:
    """Ollama on localhost must keep working — the documented allow_loopback case."""
    from hachi.gateway._net_guard import is_safe_outbound_url

    assert is_safe_outbound_url("http://127.0.0.1:11434/") is False
    assert is_safe_outbound_url("http://127.0.0.1:11434/", allow_loopback=True) is True


# ---- HIGH-001: ValidationResult carries resolved IPs for DNS pinning ----


def test_returns_validation_result_instance() -> None:
    """validate_outbound_url always returns a ValidationResult."""
    result = validate_outbound_url("http://1.1.1.1/hook")
    assert isinstance(result, ValidationResult)


def test_successful_validation_carries_resolved_ips() -> None:
    """A passing validation for a literal IP URL exposes that IP in resolved_ips."""
    result = validate_outbound_url("http://1.1.1.1/hook")
    assert result.ok is True
    # 1.1.1.1 is a literal IP — getaddrinfo returns it directly.
    assert "1.1.1.1" in result.resolved_ips


def test_failed_validation_has_empty_resolved_ips() -> None:
    result = validate_outbound_url("http://127.0.0.1/admin")
    assert result.ok is False
    assert len(result.resolved_ips) == 0


def test_allow_private_has_empty_resolved_ips() -> None:
    """allow_private skips DNS — no IPs to pin, callers handle their own context."""
    result = validate_outbound_url("http://10.0.0.5/internal", allow_private=True)
    assert result.ok is True
    assert len(result.resolved_ips) == 0


def test_two_tuple_unpacking_still_works() -> None:
    """Legacy ``ok, reason = validate_outbound_url(…)`` call sites keep working."""
    ok, reason = validate_outbound_url("http://127.0.0.1/")
    assert ok is False
    assert "non-public" in reason or "localhost" in reason or "not allowed" in reason

    ok2, reason2 = validate_outbound_url("http://1.1.1.1/")
    assert ok2 is True
    assert reason2 == "ok"
