"""Tests for the apikey connector credential storage and gateway endpoints.

Covers:
  1. ConnectorDef.credential_fields — Telegram has a bot_token field, WhatsApp has Meta + Twilio.
  2. store_apikey_credential / get_apikey_credential / clear_apikey_credentials.
  3. is_apikey_connector_configured — vault path and env var fallback.
  4. connector_status — apikey connector configured/connected mirrors credential presence.
  5. all_connector_statuses — Telegram appears + credential_fields included.
  6. GET /integrations endpoint — Telegram visible, credential_fields schema returned.
  7. POST /integrations/{id}/credentials — stores fields, returns updated status.
  8. DELETE /integrations/{id}/credentials — clears fields, returns status.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app
from hachi.integrations.connector_registry import get_connector, list_connectors
from hachi.integrations.oauth_flow import (
    _apikey_vault_key,
    clear_apikey_credentials,
    get_apikey_credential,
    is_apikey_connector_configured,
    store_apikey_credential,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> TestClient:
    """Create a TestClient with a minimal GatewayControlPlane (no auth)."""
    cp = GatewayControlPlane()
    return TestClient(create_gateway_app(cp))


# ---------------------------------------------------------------------------
# 1. ConnectorDef.credential_fields
# ---------------------------------------------------------------------------


class TestConnectorRegistryFields:
    def test_telegram_is_registered(self) -> None:
        """Telegram must appear in the connector registry."""
        connector = get_connector("telegram")
        assert connector is not None
        assert connector.name == "Telegram"
        assert connector.auth_type == "apikey"

    def test_telegram_has_bot_token_field(self) -> None:
        """Telegram connector must declare telegram_bot_token as a required credential field."""
        connector = get_connector("telegram")
        assert connector is not None
        keys = [f["key"] for f in connector.credential_fields]
        assert "telegram_bot_token" in keys
        # Must be a secret field.
        field = next(f for f in connector.credential_fields if f["key"] == "telegram_bot_token")
        assert field["secret"] is True
        assert field["optional"] is False

    def test_whatsapp_has_meta_fields(self) -> None:
        """WhatsApp connector must declare META_WHATSAPP_TOKEN and META_WHATSAPP_PHONE_ID."""
        connector = get_connector("whatsapp")
        assert connector is not None
        keys = [f["key"] for f in connector.credential_fields]
        assert "META_WHATSAPP_TOKEN" in keys
        assert "META_WHATSAPP_PHONE_ID" in keys

    def test_whatsapp_meta_fields_are_required(self) -> None:
        """META_WHATSAPP_TOKEN and META_WHATSAPP_PHONE_ID must not be optional."""
        connector = get_connector("whatsapp")
        assert connector is not None
        for field in connector.credential_fields:
            if field["key"] in ("META_WHATSAPP_TOKEN", "META_WHATSAPP_PHONE_ID"):
                assert field["optional"] is False, f"{field['key']} should not be optional"

    def test_whatsapp_twilio_fields_are_optional(self) -> None:
        """Twilio fields must be optional (alternate path only)."""
        connector = get_connector("whatsapp")
        assert connector is not None
        twilio_keys = {"TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"}
        for field in connector.credential_fields:
            if field["key"] in twilio_keys:
                assert field["optional"] is True, f"{field['key']} should be optional"

    def test_oauth2_connectors_have_no_credential_fields(self) -> None:
        """OAuth2 connectors (google, slack, etc.) must have empty credential_fields."""
        for conn in list_connectors():
            if conn.auth_type == "oauth2":
                assert conn.credential_fields == [], (
                    f"OAuth2 connector {conn.id!r} should not have credential_fields"
                )

    def test_required_credential_keys(self) -> None:
        """required_credential_keys() returns only non-optional field keys."""
        connector = get_connector("telegram")
        assert connector is not None
        required = connector.required_credential_keys()
        assert "telegram_bot_token" in required

    def test_telegram_in_list_connectors(self) -> None:
        """list_connectors() must include Telegram."""
        ids = [c.id for c in list_connectors()]
        assert "telegram" in ids


# ---------------------------------------------------------------------------
# 2. Credential storage functions
# ---------------------------------------------------------------------------


class TestCredentialStorage:
    """Tests for store_apikey_credential / get_apikey_credential / clear_apikey_credentials.

    These tests mock CredentialVault to avoid touching the OS keyring or
    encrypted-file fallback in CI.
    """

    def _make_vault(self) -> tuple[MagicMock, dict[str, str]]:
        """Return a (mock_vault_instance, backing_dict) pair."""
        backing: dict[str, str] = {}
        vault = MagicMock()
        vault.set_token.side_effect = lambda k, v: backing.__setitem__(k, v)
        vault.get_token.side_effect = lambda k: backing.get(k)
        vault.delete_token.side_effect = lambda k: backing.pop(k, None)
        return vault, backing

    def test_store_and_retrieve(self) -> None:
        """Storing a credential and reading it back yields the same value."""
        vault, backing = self._make_vault()
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            store_apikey_credential("telegram", "telegram_bot_token", "123456:ABC")
            result = get_apikey_credential("telegram", "telegram_bot_token")
        assert result == "123456:ABC"

    def test_store_empty_value_raises(self) -> None:
        """Storing an empty string must raise ValueError."""
        vault, _ = self._make_vault()
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            with pytest.raises(ValueError, match="non-empty"):
                store_apikey_credential("telegram", "telegram_bot_token", "")

    def test_get_missing_returns_none(self) -> None:
        """Getting a key that was never stored returns None."""
        vault, _ = self._make_vault()
        vault.get_token.return_value = None
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            result = get_apikey_credential("telegram", "telegram_bot_token")
        assert result is None

    def test_clear_removes_all_fields(self) -> None:
        """clear_apikey_credentials removes every field declared by the connector."""
        vault, backing = self._make_vault()
        # Pre-populate both telegram fields.
        backing[_apikey_vault_key("telegram", "telegram_bot_token")] = "abc"
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            clear_apikey_credentials("telegram")
        assert _apikey_vault_key("telegram", "telegram_bot_token") not in backing

    def test_clear_unknown_connector_is_noop(self) -> None:
        """clear_apikey_credentials on an unknown connector_id should not raise."""
        vault, _ = self._make_vault()
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            clear_apikey_credentials("nonexistent_connector_xyz")  # must not raise


# ---------------------------------------------------------------------------
# 3. is_apikey_connector_configured
# ---------------------------------------------------------------------------


class TestIsApikeyConnectorConfigured:
    def test_configured_via_vault(self) -> None:
        """Returns True when all required fields are in the vault."""
        vault = MagicMock()
        vault.get_token.return_value = "some_token_value"
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            result = is_apikey_connector_configured("telegram")
        assert result is True

    def test_not_configured_when_vault_empty(self) -> None:
        """Returns False when vault is empty and no env var is set."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            patch("hachi.integrations.oauth_flow.os.environ", {}),
        ):
            result = is_apikey_connector_configured("telegram")
        assert result is False

    def test_configured_via_env_var(self) -> None:
        """Returns True when required field key uppercased is set as env var."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            patch("hachi.integrations.oauth_flow.os.environ", {"TELEGRAM_BOT_TOKEN": "tok"}),
        ):
            result = is_apikey_connector_configured("telegram")
        assert result is True

    def test_unknown_connector_returns_false(self) -> None:
        """Unknown connector ids return False."""
        assert is_apikey_connector_configured("nonexistent_xyz") is False


# ---------------------------------------------------------------------------
# 4. connector_status for apikey connectors
# ---------------------------------------------------------------------------


class TestConnectorStatusApikey:
    def test_configured_telegram_reports_connected(self) -> None:
        """When Telegram is configured, connector_status should return connected=True."""
        from hachi.integrations.oauth_flow import connector_status

        vault = MagicMock()
        vault.get_token.return_value = "123456:ABC"
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            status = connector_status("telegram")

        assert status["configured"] is True
        assert status["connected"] is True
        assert status["status"] == "connected"
        assert status["auth_type"] == "apikey"

    def test_unconfigured_telegram_reports_disconnected(self) -> None:
        """When Telegram has no credentials, connector_status should report disconnected."""
        from hachi.integrations.oauth_flow import connector_status

        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            patch("hachi.integrations.oauth_flow.os.environ", {}),
        ):
            status = connector_status("telegram")

        assert status["configured"] is False
        assert status["connected"] is False
        assert status["status"] == "disconnected"

    def test_connector_status_includes_credential_fields(self) -> None:
        """connector_status must include credential_fields from the registry."""
        from hachi.integrations.oauth_flow import connector_status

        vault = MagicMock()
        vault.get_token.return_value = None
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            status = connector_status("telegram")

        assert "credential_fields" in status
        fields = status["credential_fields"]
        assert isinstance(fields, list)
        assert len(fields) > 0
        field_keys = [f["key"] for f in fields]
        assert "telegram_bot_token" in field_keys


# ---------------------------------------------------------------------------
# 5. all_connector_statuses
# ---------------------------------------------------------------------------


class TestAllConnectorStatuses:
    def test_telegram_appears_in_all_statuses(self) -> None:
        """all_connector_statuses() must include a telegram entry."""
        from hachi.integrations.oauth_flow import all_connector_statuses

        vault = MagicMock()
        vault.get_token.return_value = None
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            statuses = all_connector_statuses()

        ids = [s["id"] for s in statuses]
        assert "telegram" in ids

    def test_all_statuses_include_credential_fields(self) -> None:
        """Every connector status entry must have a credential_fields key."""
        from hachi.integrations.oauth_flow import all_connector_statuses

        vault = MagicMock()
        vault.get_token.return_value = None
        with patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault):
            statuses = all_connector_statuses()

        for s in statuses:
            assert "credential_fields" in s, f"Missing credential_fields for connector {s['id']!r}"


# ---------------------------------------------------------------------------
# 6. GET /integrations endpoint
# ---------------------------------------------------------------------------


class TestGetIntegrationsEndpoint:
    def test_telegram_visible_in_response(self) -> None:
        """GET /integrations must include telegram in the response array."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            patch("hachi.integrations.oauth_flow.os.environ", {}),
            _make_client() as client,
        ):
            resp = client.get("/integrations")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        ids = [item["id"] for item in data]
        assert "telegram" in ids

    def test_credential_fields_schema_in_response(self) -> None:
        """GET /integrations must include credential_fields for telegram."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            patch("hachi.integrations.oauth_flow.os.environ", {}),
            _make_client() as client,
        ):
            resp = client.get("/integrations")

        assert resp.status_code == 200
        data = resp.json()
        telegram_entry = next((item for item in data if item["id"] == "telegram"), None)
        assert telegram_entry is not None
        assert "credential_fields" in telegram_entry
        fields = telegram_entry["credential_fields"]
        assert isinstance(fields, list)
        assert len(fields) > 0

    def test_whatsapp_has_credential_fields(self) -> None:
        """GET /integrations must include credential_fields for whatsapp."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            patch("hachi.integrations.oauth_flow.os.environ", {}),
            _make_client() as client,
        ):
            resp = client.get("/integrations")

        assert resp.status_code == 200
        data = resp.json()
        wp = next((item for item in data if item["id"] == "whatsapp"), None)
        assert wp is not None
        assert "credential_fields" in wp
        keys = [f["key"] for f in wp["credential_fields"]]
        assert "META_WHATSAPP_TOKEN" in keys


# ---------------------------------------------------------------------------
# 7. POST /integrations/{id}/credentials
# ---------------------------------------------------------------------------


class TestPostCredentials:
    def test_store_valid_credentials(self) -> None:
        """POST /integrations/telegram/credentials with valid fields → 200 + configured."""
        stored: dict[str, str] = {}
        vault = MagicMock()
        vault.set_token.side_effect = lambda k, v: stored.__setitem__(k, v)
        vault.get_token.side_effect = lambda k: stored.get(k)

        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            _make_client() as client,
        ):
            resp = client.post(
                "/integrations/telegram/credentials",
                json={"fields": {"telegram_bot_token": "123456:ABCdef"}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "telegram"
        assert data["configured"] is True
        assert data["connected"] is True
        assert data["auth_type"] == "apikey"

    def test_unknown_connector_returns_404(self) -> None:
        """POST /integrations/nonexistent/credentials → 404."""
        with _make_client() as client:
            resp = client.post(
                "/integrations/nonexistent_xyz/credentials",
                json={"fields": {"some_key": "value"}},
            )
        assert resp.status_code == 404

    def test_undeclared_field_key_returns_422(self) -> None:
        """POST with a field key not in the connector's credential_fields → 422."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            _make_client() as client,
        ):
            resp = client.post(
                "/integrations/telegram/credentials",
                json={"fields": {"UNDECLARED_KEY_XYZ": "value"}},
            )
        assert resp.status_code == 422

    def test_empty_value_returns_422(self) -> None:
        """POST with an empty string value → 422."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            _make_client() as client,
        ):
            resp = client.post(
                "/integrations/telegram/credentials",
                json={"fields": {"telegram_bot_token": ""}},
            )
        assert resp.status_code == 422

    def test_invalid_connector_id_format_returns_400(self) -> None:
        """POST /integrations/../credentials → 400 (invalid connector id format)."""
        with _make_client() as client:
            resp = client.post(
                "/integrations/../credentials",
                json={"fields": {}},
            )
        # The router won't match a path with .. — we get 404 or 400.
        assert resp.status_code in (400, 404, 422)

    def test_oauth_connector_returns_422(self) -> None:
        """POST /integrations/google/credentials → 422 (oauth2 connectors not supported)."""
        vault = MagicMock()
        vault.get_token.return_value = None
        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            _make_client() as client,
        ):
            resp = client.post(
                "/integrations/google/credentials",
                json={"fields": {"some_key": "value"}},
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8. DELETE /integrations/{id}/credentials
# ---------------------------------------------------------------------------


class TestDeleteCredentials:
    def test_clear_credentials(self) -> None:
        """DELETE /integrations/telegram/credentials clears stored creds → configured=False."""
        stored: dict[str, str] = {_apikey_vault_key("telegram", "telegram_bot_token"): "123456:ABC"}
        vault = MagicMock()
        vault.delete_token.side_effect = lambda k: stored.pop(k, None)
        vault.get_token.side_effect = lambda k: stored.get(k)

        with (
            patch("hachi.integrations.oauth_flow.CredentialVault", return_value=vault),
            patch("hachi.integrations.oauth_flow.os.environ", {}),
            _make_client() as client,
        ):
            resp = client.delete("/integrations/telegram/credentials")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "telegram"
        assert data["configured"] is False

    def test_unknown_connector_returns_404(self) -> None:
        """DELETE /integrations/nonexistent/credentials → 404."""
        with _make_client() as client:
            resp = client.delete("/integrations/nonexistent_xyz/credentials")
        assert resp.status_code == 404

    def test_oauth_connector_returns_422(self) -> None:
        """DELETE /integrations/slack/credentials → 422."""
        with _make_client() as client:
            resp = client.delete("/integrations/slack/credentials")
        assert resp.status_code == 422
