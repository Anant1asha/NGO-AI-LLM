"""Tests for `hachi google-auth`.

All OAuth and hub calls are mocked — no browser windows or API calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

_FAKE_HUB_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def _fake_hub() -> MagicMock:
    hub = MagicMock()
    svc1 = MagicMock()
    svc1.required_scopes = _FAKE_HUB_SCOPES[:1]
    svc2 = MagicMock()
    svc2.required_scopes = _FAKE_HUB_SCOPES[1:]
    hub._services = [svc1, svc2]
    return hub


def _fake_oauth(token: str = "tok_test") -> MagicMock:
    oauth = MagicMock()
    oauth.get_google_credentials.return_value = token
    return oauth


def _patches(*, oauth=None, hub=None):
    if oauth is None:
        oauth = _fake_oauth()
    if hub is None:
        hub = _fake_hub()
    return (
        patch("hachi.core.oauth.OAuthManager", return_value=oauth),
        patch("hachi.integrations.google.GoogleIntegrationHub", return_value=hub),
        patch("hachi.cli.main.create_default_secret_store", return_value=MagicMock()),
    )


class TestGoogleAuthNoCredentials:
    def test_exits_1_without_client_id(self, monkeypatch) -> None:
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        result = runner.invoke(app, ["google-auth"])
        assert result.exit_code == 1

    def test_explains_missing_client_id(self, monkeypatch) -> None:
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        result = runner.invoke(app, ["google-auth"])
        assert "GOOGLE_CLIENT_ID" in result.output

    def test_json_error_without_client_id(self, monkeypatch) -> None:
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        result = runner.invoke(app, ["google-auth", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["ok"] is False
        assert "GOOGLE_CLIENT_ID" in data["error"]


class TestGoogleAuthSuccess:
    def test_exits_0_on_success(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        p1, p2, p3 = _patches()
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth"])
        assert result.exit_code == 0

    def test_shows_success_message(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        p1, p2, p3 = _patches()
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth"])
        assert "authenticated" in result.output.lower() or "✓" in result.output

    def test_json_ok_true_on_success(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        p1, p2, p3 = _patches()
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "scopes_requested" in data
        assert data["scopes_requested"] == 2

    def test_collects_scopes_from_hub_services(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        oauth = _fake_oauth()
        p1, p2, p3 = _patches(oauth=oauth)
        with p1, p2, p3:
            runner.invoke(app, ["google-auth"])
        # Verify get_google_credentials was called with the aggregated scopes.
        call_args = oauth.get_google_credentials.call_args
        assert call_args is not None
        scopes_passed = call_args[0][0]  # first positional arg
        assert len(scopes_passed) == 2
        assert all(s in scopes_passed for s in _FAKE_HUB_SCOPES)


class TestGoogleAuthRevoke:
    def test_revoke_clears_token(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        oauth = _fake_oauth()
        p1, p2, p3 = _patches(oauth=oauth)
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth", "--revoke"])
        assert result.exit_code == 0
        oauth.save_token.assert_called_once_with("google", {})

    def test_revoke_json_output(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        p1, p2, p3 = _patches()
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth", "--revoke", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["revoked"] is True

    def test_revoke_shows_confirmation(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        p1, p2, p3 = _patches()
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth", "--revoke"])
        assert "cleared" in result.output.lower() or "revoke" in result.output.lower()


class TestGoogleAuthFailure:
    def test_auth_exception_exits_1(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        oauth = _fake_oauth()
        oauth.get_google_credentials.side_effect = RuntimeError("OAuth denied")
        p1, p2, p3 = _patches(oauth=oauth)
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth"])
        assert result.exit_code == 1

    def test_auth_exception_json_has_error(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
        oauth = _fake_oauth()
        oauth.get_google_credentials.side_effect = RuntimeError("OAuth denied")
        p1, p2, p3 = _patches(oauth=oauth)
        with p1, p2, p3:
            result = runner.invoke(app, ["google-auth", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["ok"] is False
        assert "OAuth denied" in data["error"]
