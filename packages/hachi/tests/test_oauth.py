from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from hachi.core.oauth import OAuthCallbackHandler, OAuthManager


class _MemorySecretStore:
    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self._items.get(name)

    def set(self, name: str, value: str, metadata=None) -> None:
        self._items[name] = value

    def delete(self, name: str) -> None:
        self._items.pop(name, None)

    def list_metadata(self):
        return []

    def healthcheck(self):
        return {"status": "ok"}


def test_google_oauth_requires_client_id(monkeypatch) -> None:
    monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: None)

    with pytest.raises(RuntimeError, match="Missing GOOGLE_CLIENT_ID"):
        OAuthManager._require_google_client_id()


def test_oauth_callback_rejects_state_mismatch() -> None:
    handler = OAuthCallbackHandler.__new__(OAuthCallbackHandler)
    handler.path = "/?code=abc123&state=unexpected"
    handler.server = SimpleNamespace(oauth_state="expected", auth_code="should-be-cleared")
    handler.wfile = io.BytesIO()
    handler.send_response = lambda _status: None
    handler.send_header = lambda _name, _value: None
    handler.end_headers = lambda: None

    OAuthCallbackHandler.do_GET(handler)

    assert handler.server.auth_code is None
    body = handler.wfile.getvalue().decode("utf-8")
    assert "State validation failed" in body


def test_google_browser_flow_fails_when_callback_port_8080_is_in_use(monkeypatch) -> None:
    monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: "client-id")
    monkeypatch.setattr("hachi.core.oauth._google_client_secret", lambda: None)
    monkeypatch.delenv("HACHI_OAUTH_NONINTERACTIVE", raising=False)  # hermetic vs flag pollution
    monkeypatch.setattr(
        "hachi.core.oauth.HTTPServer",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("Address already in use")),
    )

    manager = OAuthManager(secret_store=_MemorySecretStore())

    with pytest.raises(OSError, match="Address already in use"):
        manager._run_google_browser_flow(["openid"])


def test_google_browser_flow_fails_closed_when_consent_is_cancelled(monkeypatch) -> None:
    class _FakeServer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.auth_code = None
            self.oauth_state = "test-state"
            self.server_address = ("127.0.0.1", 0)
            self.timeout = None

        def handle_request(self) -> None:
            self.auth_code = None

    monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: "client-id")
    monkeypatch.setattr("hachi.core.oauth._google_client_secret", lambda: None)
    monkeypatch.delenv("HACHI_OAUTH_NONINTERACTIVE", raising=False)  # hermetic vs flag pollution
    monkeypatch.setattr("hachi.core.oauth.HTTPServer", _FakeServer)
    monkeypatch.setattr("hachi.core.oauth.webbrowser.open", lambda *_a, **_k: True)

    manager = OAuthManager(secret_store=_MemorySecretStore())

    with pytest.raises(Exception, match="Authentication failed or was cancelled"):
        manager._run_google_browser_flow(["openid", "email"])


def test_google_token_refresh_failure_propagates(monkeypatch) -> None:
    class _FailingResponse:
        status_code = 400
        is_success = False
        text = '{"error": "invalid_grant"}'

        def json(self):
            return {"error": "invalid_grant", "error_description": "Token has been expired"}

    monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: "client-id")
    monkeypatch.setattr("hachi.core.oauth._google_client_secret", lambda: None)
    monkeypatch.setattr("hachi.core.oauth.httpx.post", lambda *_a, **_k: _FailingResponse())

    manager = OAuthManager(secret_store=_MemorySecretStore())

    # The real Google error (invalid_grant) is now surfaced instead of a generic 400.
    with pytest.raises(RuntimeError, match="invalid_grant: Token has been expired"):
        manager._refresh_google_token({"refresh_token": "r1", "scope": "openid"})


# ---------------------------------------------------------------------------
# Lazy credential resolution (regression): a value configured AFTER import, or
# living in a project .env, must be picked up — the module-level capture didn't.
# ---------------------------------------------------------------------------


def test_client_id_set_after_import_is_resolved(monkeypatch) -> None:
    # The original bug: GOOGLE_CLIENT_ID was captured once at import, so a value set
    # later (e.g. .env merged at CLI startup, or a different import order) was never seen
    # and every Google tool failed "Missing GOOGLE_CLIENT_ID". Resolution is now lazy.
    from hachi.core import oauth

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "configured-late-123")
    assert oauth._google_client_id() == "configured-late-123"
    assert OAuthManager._require_google_client_id() == "configured-late-123"


def test_env_var_takes_precedence_over_dotenv(monkeypatch, tmp_path) -> None:
    from hachi.core import oauth

    (tmp_path / ".env").write_text("GOOGLE_CLIENT_ID=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "from-environ")
    assert oauth._resolve_env("GOOGLE_CLIENT_ID") == "from-environ"


def test_resolve_falls_back_to_project_dotenv(monkeypatch, tmp_path) -> None:
    from hachi.core import oauth

    # Not in the process environment, but present in the project .env → still resolved.
    monkeypatch.delenv("HACHI_TEST_ONLY_KEY", raising=False)
    (tmp_path / ".env").write_text(
        '# a comment\nHACHI_TEST_ONLY_KEY="dotenv-value"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert oauth._resolve_env("HACHI_TEST_ONLY_KEY") == "dotenv-value"


def test_read_dotenv_value_ignores_comments_and_missing(tmp_path) -> None:
    from hachi.core import oauth

    p = tmp_path / ".env"
    p.write_text("# header\n\nFOO=bar\nBAZ = qux \n", encoding="utf-8")
    assert oauth._read_dotenv_value(p, "FOO") == "bar"
    assert oauth._read_dotenv_value(p, "BAZ") == "qux"
    assert oauth._read_dotenv_value(p, "MISSING") is None
    assert oauth._read_dotenv_value(tmp_path / "nope.env", "FOO") is None


def test_browser_flow_fails_fast_when_noninteractive(monkeypatch) -> None:
    # In a headless server (gateway/serve sets HACHI_OAUTH_NONINTERACTIVE), a first-time
    # Google auth must raise a clear "run hachi auth google" error immediately — never open
    # a browser or block on a local callback server.
    monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: "client-id")
    monkeypatch.setenv("HACHI_OAUTH_NONINTERACTIVE", "1")
    monkeypatch.setattr(
        "hachi.core.oauth.HTTPServer",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("server must not start")),
    )
    monkeypatch.setattr(
        "hachi.core.oauth.webbrowser.open",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("browser must not open")),
    )
    manager = OAuthManager(secret_store=_MemorySecretStore())
    with pytest.raises(RuntimeError, match="hachi google-auth"):
        manager._run_google_browser_flow(["openid"])


# ---------------------------------------------------------------------------
# BB-10 regressions: web-UI token key mismatch + wrong CLI command in error
# ---------------------------------------------------------------------------


def test_get_token_finds_web_ui_oauth2_prefix(monkeypatch) -> None:
    """OAuthManager.get_token("google") must find tokens stored by the web UI
    under the "oauth2." prefix, not only those stored under "oauth." prefix.

    Root cause: web UI writes "oauth2.google"; agent reads with _key() which
    returns "oauth.google" — the token was never found, forcing re-auth on
    every agent turn even after the user had authenticated via the web UI.
    """
    store = _MemorySecretStore()
    # Simulate what the web UI (oauth_flow.py, _TOKEN_KEY_PREFIX="oauth2.") stores:
    import json

    token_data = {"access_token": "ya29.web-ui-token", "scope": "openid email"}
    store.set("oauth2.google", json.dumps(token_data))

    manager = OAuthManager(secret_store=store)
    # Under the bug, this returned None; with the fix it returns the token.
    result = manager.get_token("google")
    assert result is not None, (
        "get_token('google') returned None even though the token was stored under "
        "'oauth2.google' (the web-UI key prefix). The agent must fall back to the "
        "'oauth2.' prefix when nothing is stored under 'oauth.'."
    )
    assert result["access_token"] == "ya29.web-ui-token"


def test_noninteractive_error_mentions_correct_cli_command(monkeypatch) -> None:
    """When HACHI_OAUTH_NONINTERACTIVE=1 and no saved token exists, the error
    message must direct the user to `hachi google-auth`, not `hachi auth google`
    (which does not exist as a CLI command).
    """
    monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: "client-id")
    monkeypatch.setenv("HACHI_OAUTH_NONINTERACTIVE", "1")
    monkeypatch.setattr(
        "hachi.core.oauth.HTTPServer",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("server must not start")),
    )
    monkeypatch.setattr(
        "hachi.core.oauth.webbrowser.open",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("browser must not open")),
    )
    manager = OAuthManager(secret_store=_MemorySecretStore())
    with pytest.raises(RuntimeError) as exc_info:
        manager._run_google_browser_flow(["openid"])
    msg = str(exc_info.value)
    assert "hachi google-auth" in msg, (
        f"Error message should reference 'hachi google-auth' (the real CLI command) "
        f"but got: {msg!r}"
    )
    assert "hachi auth google" not in msg, (
        f"Error message must NOT reference the non-existent 'hachi auth google' command, "
        f"but got: {msg!r}"
    )
