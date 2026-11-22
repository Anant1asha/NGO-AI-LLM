"""Tests for E8/T8.2 — loopback gate for NO_AUTH and hard-error on non-loopback without token.

Requirements verified:
(a) NO_AUTH=1 on a non-loopback host raises at startup (fastapi_app + CLI layer).
(b) NO_AUTH=1 on 127.0.0.1 is allowed (no error).
(c) Non-loopback bind with no token raises (CLI layer via _resolve_gateway_auth_token).
(d) Loopback bind with no env vars still boots and yields a usable token.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import _is_loopback_host, create_gateway_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOKEN = "test-e8-token-xyz"

_LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "::1"]
_NON_LOOPBACK_HOSTS = ["0.0.0.0", "10.0.0.1", "192.168.1.5", "0:0:0:0:0:0:0:0"]


# ---------------------------------------------------------------------------
# _is_loopback_host (fastapi_app helper)
# ---------------------------------------------------------------------------


class TestIsLoopbackHostFastapi:
    """Sanity-check the _is_loopback_host helper added to fastapi_app."""

    @pytest.mark.parametrize("host", _LOOPBACK_HOSTS)
    def test_loopback_addresses_return_true(self, host: str) -> None:
        assert _is_loopback_host(host) is True

    @pytest.mark.parametrize("host", _NON_LOOPBACK_HOSTS)
    def test_non_loopback_addresses_return_false(self, host: str) -> None:
        assert _is_loopback_host(host) is False

    def test_whitespace_is_stripped(self) -> None:
        assert _is_loopback_host("  127.0.0.1  ") is True

    def test_case_insensitive_localhost(self) -> None:
        assert _is_loopback_host("LOCALHOST") is True


# ---------------------------------------------------------------------------
# (a) NO_AUTH=1 on non-loopback raises at create_gateway_app (fastapi_app layer)
# ---------------------------------------------------------------------------


class TestNoAuthNonLoopbackFastapiLayer:
    """create_gateway_app raises ValueError when NO_AUTH=1 + non-loopback bind_host."""

    @pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.1", "192.168.1.1"])
    def test_no_auth_non_loopback_raises_value_error(
        self, host: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(a) NO_AUTH=1 with a non-loopback bind_host must raise ValueError."""
        monkeypatch.setenv("HACHI_GATEWAY_NO_AUTH", "1")
        cp = GatewayControlPlane()
        with pytest.raises(ValueError, match="HACHI_GATEWAY_NO_AUTH=1 is not permitted"):
            create_gateway_app(cp, auth_token=_TOKEN, bind_host=host)

    def test_no_auth_non_loopback_error_mentions_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Error message must include the offending host address."""
        monkeypatch.setenv("HACHI_GATEWAY_NO_AUTH", "1")
        cp = GatewayControlPlane()
        with pytest.raises(ValueError, match="0.0.0.0"):
            create_gateway_app(cp, auth_token=_TOKEN, bind_host="0.0.0.0")


# ---------------------------------------------------------------------------
# (b) NO_AUTH=1 on loopback is allowed (fastapi_app layer)
# ---------------------------------------------------------------------------


class TestNoAuthLoopbackAllowed:
    """create_gateway_app must NOT raise when NO_AUTH=1 + loopback bind_host."""

    @pytest.mark.parametrize("host", _LOOPBACK_HOSTS)
    def test_no_auth_loopback_does_not_raise(
        self, host: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(b) NO_AUTH=1 on a loopback address is permitted."""
        monkeypatch.setenv("HACHI_GATEWAY_NO_AUTH", "1")
        cp = GatewayControlPlane()
        # Must not raise.
        app = create_gateway_app(cp, auth_token=_TOKEN, bind_host=host)
        assert app is not None

    def test_no_auth_no_bind_host_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When bind_host is None (unit-test mode), NO_AUTH guard is skipped entirely."""
        monkeypatch.setenv("HACHI_GATEWAY_NO_AUTH", "1")
        cp = GatewayControlPlane()
        app = create_gateway_app(cp, auth_token=_TOKEN)
        assert app is not None


# ---------------------------------------------------------------------------
# Guard 2: non-loopback + no token raises (fastapi_app layer)
# ---------------------------------------------------------------------------


class TestNonLoopbackNoTokenFastapiLayer:
    """create_gateway_app raises ValueError for non-loopback bind_host without a token."""

    @pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.1"])
    def test_non_loopback_no_token_raises(
        self, host: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)
        cp = GatewayControlPlane()
        with pytest.raises(ValueError, match="without an auth token"):
            create_gateway_app(cp, auth_token=None, bind_host=host)

    def test_non_loopback_with_token_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)
        cp = GatewayControlPlane()
        app = create_gateway_app(cp, auth_token=_TOKEN, bind_host="0.0.0.0")
        assert app is not None

    def test_no_bind_host_no_token_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unit-test helpers call create_gateway_app without bind_host; must not error."""
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)
        cp = GatewayControlPlane()
        app = create_gateway_app(cp, auth_token=None)
        assert app is not None


# ---------------------------------------------------------------------------
# (a) NO_AUTH=1 on non-loopback raises at _start_gateway_server (CLI layer)
# ---------------------------------------------------------------------------


class TestNoAuthNonLoopbackCLILayer:
    """_start_gateway_server raises OSError when NO_AUTH=1 + non-loopback host."""

    @pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.1"])
    def test_no_auth_non_loopback_raises_at_startup(
        self, host: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(a) CLI startup guard raises before the server thread is created."""
        from hachi.cli.main import _start_gateway_server

        monkeypatch.setenv("HACHI_GATEWAY_NO_AUTH", "1")
        # Also set a token so the non-loopback token error doesn't fire first.
        monkeypatch.setenv("HACHI_GATEWAY_API_TOKEN", _TOKEN)

        with pytest.raises(OSError, match="HACHI_GATEWAY_NO_AUTH=1 is not permitted"):
            _start_gateway_server(host=host, port=0, attach_runtime=False)

    def test_no_auth_non_loopback_error_in_run_gateway(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OSError propagates from _start_gateway_server to _run_gateway_http_server."""
        from hachi.cli.main import _start_gateway_server

        monkeypatch.setenv("HACHI_GATEWAY_NO_AUTH", "1")
        monkeypatch.setenv("HACHI_GATEWAY_API_TOKEN", _TOKEN)

        with pytest.raises(OSError, match="not permitted"):
            _start_gateway_server(host="0.0.0.0", port=0)


# ---------------------------------------------------------------------------
# (b) NO_AUTH=1 on loopback passes CLI layer guard (server may fail to bind — that's OK)
# ---------------------------------------------------------------------------


class TestNoAuthLoopbackCLILayerAllowed:
    """_start_gateway_server must NOT raise the NO_AUTH guard for loopback hosts."""

    def test_no_auth_loopback_passes_no_auth_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(b) NO_AUTH=1 on 127.0.0.1 does not raise the NO_AUTH guard."""
        from hachi.cli.main import _start_gateway_server

        monkeypatch.setenv("HACHI_GATEWAY_NO_AUTH", "1")
        # Provide a token so the server can start cleanly; then stop it.
        monkeypatch.setenv("HACHI_GATEWAY_API_TOKEN", _TOKEN)

        server, base_url, runtime = _start_gateway_server(
            host="127.0.0.1", port=0, attach_runtime=False
        )
        try:
            assert base_url.startswith("http://127.0.0.1:")
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# (c) Non-loopback bind with no token raises at CLI layer
# ---------------------------------------------------------------------------


class TestNonLoopbackNoTokenCLILayer:
    """_resolve_gateway_auth_token raises OSError for non-loopback without explicit token."""

    @pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.1", "192.168.0.1"])
    def test_non_loopback_no_token_raises_oserror(
        self, host: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(c) non-loopback without HACHI_GATEWAY_API_TOKEN raises OSError."""
        from hachi.cli.main import _resolve_gateway_auth_token

        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN_FILE", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)

        with pytest.raises(OSError, match="HACHI_GATEWAY_API_TOKEN"):
            _resolve_gateway_auth_token(host)

    def test_non_loopback_with_explicit_token_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hachi.cli.main import _resolve_gateway_auth_token

        monkeypatch.setenv("HACHI_GATEWAY_API_TOKEN", "explicit-token-abc")
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)

        token = _resolve_gateway_auth_token("0.0.0.0")
        assert token == "explicit-token-abc"


# ---------------------------------------------------------------------------
# (d) Loopback bind with no env vars boots and yields a usable token
# ---------------------------------------------------------------------------


class TestLoopbackNoEnvBootsAndYieldsToken:
    """Loopback path auto-generates a token; in-process and test callers work unmodified."""

    def test_loopback_no_env_generates_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(d) 127.0.0.1 with no env vars returns a non-empty token."""
        from hachi.cli.main import _resolve_gateway_auth_token

        token_path = tmp_path / "gateway-token"
        monkeypatch.setattr("hachi.cli.main._default_gateway_token_path", lambda: token_path)
        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN_FILE", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)

        token = _resolve_gateway_auth_token("127.0.0.1")
        assert token  # non-empty
        assert token_path.exists()

    def test_loopback_start_gateway_server_no_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(d) _start_gateway_server on loopback with no env vars starts and yields token."""
        from hachi.cli.main import _start_gateway_server

        token_path = tmp_path / "gateway-token"
        monkeypatch.setattr("hachi.cli.main._default_gateway_token_path", lambda: token_path)
        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN_FILE", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)

        server, base_url, runtime = _start_gateway_server(
            host="127.0.0.1", port=0, attach_runtime=False
        )
        try:
            assert base_url.startswith("http://127.0.0.1:")
            # Token file must have been written by auto-generation.
            assert token_path.exists()
            persisted = token_path.read_text(encoding="utf-8").strip()
            assert persisted  # non-empty generated token
        finally:
            server.stop()

    @pytest.mark.parametrize("host", _LOOPBACK_HOSTS)
    def test_all_loopback_variants_resolve_token(
        self, host: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """(d) All three loopback addresses auto-generate a token without error."""
        from hachi.cli.main import _resolve_gateway_auth_token

        token_path = tmp_path / f"gateway-token-{host.replace(':', '-')}"
        monkeypatch.setattr("hachi.cli.main._default_gateway_token_path", lambda: token_path)
        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN_FILE", raising=False)
        monkeypatch.delenv("HACHI_GATEWAY_NO_AUTH", raising=False)

        token = _resolve_gateway_auth_token(host)
        assert token
