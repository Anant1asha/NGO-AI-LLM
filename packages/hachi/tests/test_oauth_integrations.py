"""Tests for the OAuth 2.0 integration framework.

Covers:
  - Connector registry lookups and configuration checks.
  - oauth_start: configured vs not-configured → 409.
  - oauth_callback: bad state rejected, good state accepted (mock token exchange).
  - oauth_disconnect: tokens deleted, status updated.
  - Status fields in GET /integrations list.
  - GET /capabilities enriched with auth_type / connected fields.
  - POST /integrations/{id}/oauth/start route (200 vs 409).
  - GET /integrations/oauth/callback route (ok + error paths).
  - POST /integrations/{id}/disconnect route.

No real network calls are made — httpx is monkeypatched.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app
from hachi.integrations.connector_registry import get_connector, list_connectors
from hachi.integrations.oauth_flow import (
    OAuthStateStore,
    OAuthTokenStore,
    _callback_html_error,
    _callback_html_ok,
    all_connector_statuses,
    connector_status,
    oauth_callback,
    oauth_disconnect,
    oauth_start,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> TestClient:
    """Return a TestClient with a minimal GatewayControlPlane."""
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)
    return TestClient(app)


def _fake_token_response() -> dict[str, Any]:
    return {
        "access_token": "tok_TESTONLY",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "refresh_TESTONLY",
        "scope": "read write",
    }


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestConnectorRegistry:
    def test_all_connectors_have_ids(self) -> None:
        connectors = list_connectors()
        assert len(connectors) >= 4  # google, slack, discord, notion (github removed — no backend)
        ids = [c.id for c in connectors]
        assert "google" in ids
        assert "slack" in ids
        assert "discord" in ids
        assert "notion" in ids
        assert "whatsapp" in ids
        # GitHub OAuth registration removed: there is no github tool backend yet.
        # Adding it back as a dead UI affordance (connect with nothing to use) was
        # confusing. Re-add to CONNECTORS once src/hachi/integrations/github/ exists.
        assert "github" not in ids

    def test_get_connector_known(self) -> None:
        c = get_connector("google")
        assert c is not None
        assert c.name == "Google"
        assert c.auth_type == "oauth2"
        assert c.authorize_url.startswith("https://accounts.google.com")

    def test_get_connector_unknown(self) -> None:
        assert get_connector("notarealconnector") is None

    def test_whatsapp_is_apikey_not_oauth2(self) -> None:
        c = get_connector("whatsapp")
        assert c is not None
        assert c.auth_type == "apikey"

    def test_oauth2_connectors_have_urls(self) -> None:
        from hachi.integrations.connector_registry import oauth2_connectors

        for conn in oauth2_connectors():
            assert conn.authorize_url, f"{conn.id} missing authorize_url"
            assert conn.token_url, f"{conn.id} missing token_url"
            assert conn.client_id_env, f"{conn.id} missing client_id_env"

    def test_is_configured_false_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Ensure the env var is absent — including the legacy bare-name alias
        # (GOOGLE_CLIENT_ID) that is_configured() now also honours (Issue 6a).
        monkeypatch.delenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        c = get_connector("google")
        assert c is not None
        assert not c.is_configured()

    def test_is_configured_true_with_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "fake-client-id")
        c = get_connector("google")
        assert c is not None
        assert c.is_configured()

    def test_whatsapp_never_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WhatsApp is apikey — is_configured always False (no OAuth flow)."""
        c = get_connector("whatsapp")
        assert c is not None
        assert not c.is_configured()


# ---------------------------------------------------------------------------
# OAuthStateStore tests
# ---------------------------------------------------------------------------


class TestOAuthStateStore:
    def test_create_and_consume(self) -> None:
        store = OAuthStateStore()
        state = store.create("google")
        assert len(state) > 20
        result = store.consume(state)
        assert result == "google"

    def test_state_is_single_use(self) -> None:
        store = OAuthStateStore()
        state = store.create("slack")
        store.consume(state)
        assert store.consume(state) is None  # already consumed

    def test_unknown_state_returns_none(self) -> None:
        store = OAuthStateStore()
        assert store.consume("notastate") is None

    def test_expired_state_rejected(self) -> None:
        import time

        store = OAuthStateStore()
        # Create with 0 TTL → already expired.
        from hachi.integrations.oauth_flow import _StateEntry

        with store._lock:
            store._states["expiredstate"] = _StateEntry("google", ttl=0)
        # Sleep 1ms to ensure monotonic clock advances past expiry.
        time.sleep(0.001)
        assert store.consume("expiredstate") is None


# ---------------------------------------------------------------------------
# OAuthTokenStore tests
# ---------------------------------------------------------------------------


class TestOAuthTokenStore:
    def _make_store(self) -> tuple[OAuthTokenStore, MagicMock]:
        mock_secret_store = MagicMock()
        store = OAuthTokenStore(secret_store=mock_secret_store)
        return store, mock_secret_store

    def test_save_and_load(self) -> None:
        store, mock_ss = self._make_store()
        token_data = {"access_token": "abc", "expires_at": 9999999999.0}
        # Configure mock to return the JSON we save.
        saved_json: list[str] = []

        def fake_set(name: str, value: str, metadata: Any = None) -> None:
            saved_json.append(value)

        mock_ss.set.side_effect = fake_set
        mock_ss.get.side_effect = lambda name: saved_json[-1] if saved_json else None

        store.save("google", token_data)
        loaded = store.load("google")
        assert loaded is not None
        assert loaded["access_token"] == "abc"

    def test_load_returns_none_when_absent(self) -> None:
        store, mock_ss = self._make_store()
        mock_ss.get.return_value = None
        assert store.load("google") is None

    def test_delete_calls_store_delete(self) -> None:
        store, mock_ss = self._make_store()
        store.delete("google")
        mock_ss.delete.assert_called_once_with("oauth2.google")

    def test_is_connected_true(self) -> None:
        store, mock_ss = self._make_store()
        mock_ss.get.return_value = json.dumps({"access_token": "tok"})
        assert store.is_connected("google") is True

    def test_is_connected_false(self) -> None:
        store, mock_ss = self._make_store()
        mock_ss.get.return_value = None
        assert store.is_connected("google") is False


# ---------------------------------------------------------------------------
# oauth_start tests
# ---------------------------------------------------------------------------


class TestOAuthStart:
    def test_raises_value_error_for_unknown_connector(self) -> None:
        with pytest.raises(ValueError, match="Unknown connector"):
            oauth_start("notreal")

    def test_raises_value_error_for_non_oauth2(self) -> None:
        with pytest.raises(ValueError, match="does not use OAuth2"):
            oauth_start("whatsapp")

    def test_raises_lookup_error_when_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        with pytest.raises(LookupError, match="not configured"):
            oauth_start("google")

    def test_returns_authorization_url_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "test-cid")
        result = oauth_start("google")
        assert "authorization_url" in result
        assert "accounts.google.com" in result["authorization_url"]
        assert "test-cid" in result["authorization_url"]
        assert "state=" in result["authorization_url"]

    def test_state_includes_connector_in_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HACHI_OAUTH_SLACK_CLIENT_ID", "slack-cid")
        result = oauth_start("slack")
        url = result["authorization_url"]
        from urllib.parse import parse_qs, urlparse

        params = parse_qs(urlparse(url).query)
        state_val = params["state"][0]
        # Confirm the state was actually stored and maps back to slack.
        from hachi.integrations.oauth_flow import _state_store

        entry = _state_store._states.get(state_val)
        assert entry is not None
        assert entry.connector_id == "slack"


# ---------------------------------------------------------------------------
# oauth_callback tests
# ---------------------------------------------------------------------------


class TestOAuthCallback:
    def _setup_state(self, connector_id: str = "google") -> str:
        from hachi.integrations.oauth_flow import _state_store

        return _state_store.create(connector_id)

    def test_bad_state_returns_error(self) -> None:
        connector_id, ok, msg = oauth_callback("anycode", "badstate")
        assert not ok
        assert "Invalid or expired state" in msg

    def test_good_flow_stores_tokens(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_SECRET", "csecret")

        state = self._setup_state("google")

        fake_resp = MagicMock()
        fake_resp.is_success = True
        fake_resp.json.return_value = _fake_token_response()

        with (
            patch("hachi.integrations.oauth_flow.httpx.post", return_value=fake_resp),
            patch.object(OAuthTokenStore, "save"),
        ):
            connector_id, ok, msg = oauth_callback("authcode123", state)

        assert ok, f"Expected ok=True but got error: {msg}"
        assert connector_id == "google"
        assert msg == ""

    def test_token_exchange_failure_returns_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "cid")
        state = self._setup_state("google")

        fake_resp = MagicMock()
        fake_resp.is_success = False
        fake_resp.status_code = 400
        fake_resp.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Code expired",
        }
        fake_resp.text = "invalid_grant"

        with patch("hachi.integrations.oauth_flow.httpx.post", return_value=fake_resp):
            connector_id, ok, msg = oauth_callback("badcode", state)

        assert not ok
        assert connector_id == "google"
        assert "invalid_grant" in msg or "Token exchange failed" in msg

    def test_state_is_single_use(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "cid")
        state = self._setup_state("google")

        fake_resp = MagicMock()
        fake_resp.is_success = True
        fake_resp.json.return_value = _fake_token_response()

        with (
            patch("hachi.integrations.oauth_flow.httpx.post", return_value=fake_resp),
            patch.object(OAuthTokenStore, "save"),
        ):
            _, ok1, _ = oauth_callback("code1", state)
            _, ok2, _ = oauth_callback("code2", state)

        assert ok1
        assert not ok2  # state consumed on first use


# ---------------------------------------------------------------------------
# oauth_disconnect tests
# ---------------------------------------------------------------------------


class TestOAuthDisconnect:
    def test_raises_for_unknown_connector(self) -> None:
        with pytest.raises(ValueError, match="Unknown connector"):
            oauth_disconnect("notaconnector")

    def test_deletes_tokens_and_returns_disconnected(self) -> None:
        with (
            patch.object(OAuthTokenStore, "delete") as mock_delete,
            patch.object(OAuthTokenStore, "load", return_value=None),
        ):
            result = oauth_disconnect("google")

        assert result["connected"] is False
        mock_delete.assert_called_once()
        # First positional arg after self is the connector_id
        assert mock_delete.call_args[0][0] == "google"

    def test_revoke_is_called_when_token_exists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        token_data = {"access_token": "tok_REVOKE"}

        revoke_called: list[bool] = []

        def fake_revoke(url: str, **kwargs: Any) -> MagicMock:
            revoke_called.append(True)
            return MagicMock()

        with (
            patch.object(OAuthTokenStore, "load", return_value=token_data),
            patch.object(OAuthTokenStore, "delete"),
            patch("hachi.integrations.oauth_flow.httpx.post", side_effect=fake_revoke),
        ):
            oauth_disconnect("google")

        # Google has a revoke_url so revoke should be attempted.
        assert len(revoke_called) >= 1


# ---------------------------------------------------------------------------
# connector_status / all_connector_statuses tests
# ---------------------------------------------------------------------------


class TestConnectorStatus:
    def test_unknown_connector_returns_none_type(self) -> None:
        status = connector_status("doesnotexist")
        assert status["auth_type"] == "none"
        assert status["configured"] is False
        assert status["connected"] is False

    def test_google_not_connected_when_no_token(self) -> None:
        with patch.object(OAuthTokenStore, "is_connected", return_value=False):
            status = connector_status("google")
        assert status["connected"] is False

    def test_google_connected_when_token_present(self) -> None:
        with patch.object(OAuthTokenStore, "is_connected", return_value=True):
            status = connector_status("google")
        assert status["connected"] is True
        assert status["status"] == "connected"

    def test_all_statuses_returns_all_connectors(self) -> None:
        from hachi.integrations.connector_registry import list_connectors

        with patch.object(OAuthTokenStore, "is_connected", return_value=False):
            statuses = all_connector_statuses()

        expected_ids = {c.id for c in list_connectors()}
        returned_ids = {s["id"] for s in statuses}
        assert expected_ids == returned_ids

    def test_status_connected_when_connected(self) -> None:
        with patch.object(OAuthTokenStore, "is_connected", return_value=True):
            status = connector_status("slack")
        assert status["status"] == "connected"

    def test_status_configured_when_creds_present_but_no_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Test with notion (same pattern as github used to exercise — oauth2, no token).
        monkeypatch.setenv("HACHI_OAUTH_NOTION_CLIENT_ID", "some-id")
        with patch.object(OAuthTokenStore, "is_connected", return_value=False):
            status = connector_status("notion")
        assert status["status"] == "configured"
        assert status["configured"] is True
        assert status["connected"] is False


# ---------------------------------------------------------------------------
# FastAPI route tests
# ---------------------------------------------------------------------------


class TestIntegrationsRoutes:
    """Integration tests exercising the actual FastAPI routes via TestClient."""

    def _client(self) -> TestClient:
        cp = GatewayControlPlane()
        return TestClient(create_gateway_app(cp))

    def test_get_integrations_returns_list(self) -> None:
        with patch.object(OAuthTokenStore, "is_connected", return_value=False):
            resp = self._client().get("/integrations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        ids = [item["id"] for item in data]
        assert "google" in ids
        assert "slack" in ids

    def test_get_integrations_has_auth_type_field(self) -> None:
        with patch.object(OAuthTokenStore, "is_connected", return_value=False):
            resp = self._client().get("/integrations")
        item = next(i for i in resp.json() if i["id"] == "google")
        assert item["auth_type"] == "oauth2"
        assert "configured" in item
        assert "connected" in item
        assert "status" in item

    def test_post_oauth_start_409_when_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        resp = self._client().post("/integrations/google/oauth/start")
        assert resp.status_code == 409
        assert resp.json()["code"] == "credentials_not_configured"

    def test_post_oauth_start_404_for_unknown_connector(self) -> None:
        resp = self._client().post("/integrations/notarealconnector/oauth/start")
        assert resp.status_code == 404

    def test_post_oauth_start_200_when_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "test-id")
        resp = self._client().post("/integrations/google/oauth/start")
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data
        assert "accounts.google.com" in data["authorization_url"]

    def test_oauth_callback_bad_state_returns_400_html(self) -> None:
        resp = self._client().get("/integrations/oauth/callback?code=abc&state=badstate")
        assert resp.status_code == 400
        assert "text/html" in resp.headers["content-type"]
        assert "hachi_oauth_done" in resp.text
        # JS uses unquoted key: `ok: false`
        assert "ok: false" in resp.text

    def test_oauth_callback_missing_code_returns_400(self) -> None:
        resp = self._client().get("/integrations/oauth/callback?state=somestate")
        assert resp.status_code == 400

    def test_oauth_callback_success_html(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "cid")
        # Get a real state token.
        start_resp = self._client().post("/integrations/google/oauth/start")
        assert start_resp.status_code == 200
        from urllib.parse import parse_qs, urlparse

        url = start_resp.json()["authorization_url"]
        state = parse_qs(urlparse(url).query)["state"][0]

        fake_resp = MagicMock()
        fake_resp.is_success = True
        fake_resp.json.return_value = _fake_token_response()

        with (
            patch("hachi.integrations.oauth_flow.httpx.post", return_value=fake_resp),
            patch.object(OAuthTokenStore, "save"),
        ):
            cb_resp = self._client().get(
                f"/integrations/oauth/callback?code=authcode&state={state}"
            )

        assert cb_resp.status_code == 200
        assert "text/html" in cb_resp.headers["content-type"]
        assert "hachi_oauth_done" in cb_resp.text
        # JS uses unquoted key: `ok: true`
        assert "ok: true" in cb_resp.text

    def test_post_disconnect_404_for_unknown(self) -> None:
        resp = self._client().post("/integrations/notarealconnector/disconnect")
        assert resp.status_code == 404

    def test_post_disconnect_returns_disconnected(self) -> None:
        with (
            patch.object(OAuthTokenStore, "load", return_value=None),
            patch.object(OAuthTokenStore, "delete"),
            patch.object(OAuthTokenStore, "is_connected", return_value=False),
        ):
            resp = self._client().post("/integrations/google/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False


# ---------------------------------------------------------------------------
# Callback HTML XSS tests
# ---------------------------------------------------------------------------


class TestCallbackHtml:
    def test_ok_html_does_not_reflect_untrusted_input(self) -> None:
        """connector_id from state store is safe — but check escaping anyway."""
        html = _callback_html_ok("google")
        # connector_id should appear literally in the postMessage
        assert '"google"' in html
        # No script injection via connector_id (it's from our registry, not user input)
        assert "<script>" not in html.lower().replace("<script>", "SCRIPT")

    def test_error_html_escapes_message(self) -> None:
        """Error message must be HTML-escaped in the body, not rendered as raw HTML."""
        malicious_msg = '<script>alert("xss")</script>'
        html = _callback_html_error("google", malicious_msg)
        # The escaped form must appear in the page body
        assert "&lt;script&gt;" in html
        # The raw script tag must NOT appear in the visible body paragraph
        # (it may appear in our own <script> block but not injected into the <p>)
        body_section = html.split("<script>")[0]  # everything before our first <script> tag
        assert "<script>" not in body_section
        assert "hachi_oauth_done" in html

    def test_error_html_does_not_reflect_connector_id_unsanitized(self) -> None:
        """connector_id in HTML is safe-slug; test that quotes are stripped."""
        html = _callback_html_error('go"ogle><bad>', "oops")
        # The raw unsafe chars should not appear in the id embedding
        assert '"go"ogle' not in html
        assert "><bad>" not in html


# ---------------------------------------------------------------------------
# BB-11 regression: successful OAuth never enables capability in config
# ---------------------------------------------------------------------------


class TestOAuthAutoEnablesCapability:
    """BB-11: completing OAuth must auto-enable the capability so agent tools
    are registered on next startup.  Symptom: Integrations page showed
    "connected" but agent reported "Gmail is currently disabled" because
    capabilities.google.enabled defaulted to False and was never flipped."""

    def test_callback_success_calls_set_capability_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET /integrations/oauth/callback (success) must call
        control_plane.set_capability_enabled(connector_id, True).

        Under the bug, it did not — the capability flag stayed False even
        after the user authenticated via the web UI.
        """
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "cid")
        cp = GatewayControlPlane()

        with patch.object(cp, "set_capability_enabled") as mock_enable:
            client = TestClient(create_gateway_app(cp))
            # Obtain a real state token via the start route.
            start_resp = client.post("/integrations/google/oauth/start")
            assert start_resp.status_code == 200
            from urllib.parse import parse_qs, urlparse

            state = parse_qs(urlparse(start_resp.json()["authorization_url"]).query)["state"][0]

            fake_resp = MagicMock()
            fake_resp.is_success = True
            fake_resp.json.return_value = _fake_token_response()

            with (
                patch("hachi.integrations.oauth_flow.httpx.post", return_value=fake_resp),
                patch.object(OAuthTokenStore, "save"),
            ):
                cb_resp = client.get(f"/integrations/oauth/callback?code=authcode&state={state}")

        assert cb_resp.status_code == 200
        mock_enable.assert_called_once_with("google", True)

    def test_callback_failure_does_not_enable_capability(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed OAuth callback must NOT enable the capability."""
        monkeypatch.setenv("HACHI_OAUTH_GOOGLE_CLIENT_ID", "cid")
        cp = GatewayControlPlane()

        with patch.object(cp, "set_capability_enabled") as mock_enable:
            client = TestClient(create_gateway_app(cp))
            start_resp = client.post("/integrations/google/oauth/start")
            from urllib.parse import parse_qs, urlparse

            state = parse_qs(urlparse(start_resp.json()["authorization_url"]).query)["state"][0]

            fake_resp = MagicMock()
            fake_resp.is_success = False
            fake_resp.status_code = 400
            fake_resp.json.return_value = {"error": "access_denied"}
            fake_resp.text = "access_denied"

            with patch("hachi.integrations.oauth_flow.httpx.post", return_value=fake_resp):
                cb_resp = client.get(f"/integrations/oauth/callback?code=badcode&state={state}")

        assert cb_resp.status_code == 400
        mock_enable.assert_not_called()
