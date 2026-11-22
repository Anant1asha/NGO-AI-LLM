"""Tests for credential auto-detection fixes (Issue 6a).

Covers:
  - OAuth2 ``is_configured()`` with canonical env var.
  - OAuth2 ``is_configured()`` with legacy bare alias (e.g. ``GOOGLE_CLIENT_ID``).
  - OAuth2 not configured when neither canonical nor alias is set.
  - ``connector_status()`` ``source`` field for OAuth2 canonical env var → ``"env"``.
  - ``connector_status()`` ``source`` field for OAuth2 legacy alias → ``"env"``.
  - ``connector_status()`` ``source`` is ``None`` when not configured.
  - Apikey connector (Telegram) configured via env → ``source="env"``, ``status="connected"``.
  - ``all_connector_statuses()`` passes ``source`` through for all connectors.
  - ``client_id()`` resolution order: canonical takes precedence over alias.
  - ``client_secret()`` resolution order: canonical takes precedence over alias.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from hachi.integrations.connector_registry import (
    OAUTH2_CLIENT_ID_ALIASES,
    get_connector,
)
from hachi.integrations.oauth_flow import (
    all_connector_statuses,
    connector_status,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CANONICAL_ID = "HACHI_OAUTH_GOOGLE_CLIENT_ID"
_CANONICAL_SECRET = "HACHI_OAUTH_GOOGLE_CLIENT_SECRET"
_ALIAS_ID = "GOOGLE_CLIENT_ID"
_ALIAS_SECRET = "GOOGLE_CLIENT_SECRET"
_FAKE_ID = "test-client-id.apps.googleusercontent.com"
_FAKE_SECRET = "test-client-secret"


def _clean_google_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all Google OAuth env vars so tests start from a clean state."""
    for var in (_CANONICAL_ID, _CANONICAL_SECRET, _ALIAS_ID, _ALIAS_SECRET):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# ConnectorDef.is_configured() — OAuth2 Google
# ---------------------------------------------------------------------------


class TestGoogleIsConfigured:
    def test_canonical_env_var_configures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HACHI_OAUTH_GOOGLE_CLIENT_ID present → is_configured() True."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_CANONICAL_ID, _FAKE_ID)
        connector = get_connector("google")
        assert connector is not None
        assert connector.is_configured() is True

    def test_legacy_alias_configures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only GOOGLE_CLIENT_ID set (no canonical) → is_configured() True via alias."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_ALIAS_ID, _FAKE_ID)
        connector = get_connector("google")
        assert connector is not None
        assert connector.is_configured() is True

    def test_neither_env_var_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Neither canonical nor alias set → is_configured() False."""
        _clean_google_env(monkeypatch)
        connector = get_connector("google")
        assert connector is not None
        assert connector.is_configured() is False

    def test_canonical_takes_precedence_over_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both are set, canonical value is returned by client_id()."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_CANONICAL_ID, "canonical-id")
        monkeypatch.setenv(_ALIAS_ID, "alias-id")
        connector = get_connector("google")
        assert connector is not None
        assert connector.client_id() == "canonical-id"

    def test_client_secret_alias_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GOOGLE_CLIENT_SECRET is resolved when canonical secret absent."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_ALIAS_SECRET, _FAKE_SECRET)
        connector = get_connector("google")
        assert connector is not None
        assert connector.client_secret() == _FAKE_SECRET

    def test_client_secret_canonical_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Canonical client secret wins over alias."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_CANONICAL_SECRET, "canonical-secret")
        monkeypatch.setenv(_ALIAS_SECRET, "alias-secret")
        connector = get_connector("google")
        assert connector is not None
        assert connector.client_secret() == "canonical-secret"


# ---------------------------------------------------------------------------
# connector_status() — source field for OAuth2
# ---------------------------------------------------------------------------


class TestConnectorStatusSourceOAuth2:
    """Tests for contract C-CREDSOURCE: the ``source`` field in connector_status."""

    def _patched_status(
        self, connector_id: str, *, token_connected: bool = False
    ) -> dict[str, Any]:
        """Call connector_status with the token store reporting no stored token."""
        with patch(
            "hachi.integrations.oauth_flow._token_store.is_connected",
            return_value=token_connected,
        ):
            return connector_status(connector_id)

    def test_source_env_with_canonical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Canonical env var present → source='env'."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_CANONICAL_ID, _FAKE_ID)
        status = self._patched_status("google")
        assert status["configured"] is True
        assert status["source"] == "env"

    def test_source_env_with_alias_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only legacy GOOGLE_CLIENT_ID set → source='env'."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_ALIAS_ID, _FAKE_ID)
        status = self._patched_status("google")
        assert status["configured"] is True
        assert status["source"] == "env"

    def test_source_null_when_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Neither env var set → source=None."""
        _clean_google_env(monkeypatch)
        status = self._patched_status("google")
        assert status["configured"] is False
        assert status["source"] is None

    def test_source_key_present_in_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """source key is always present in the status dict (even when None)."""
        _clean_google_env(monkeypatch)
        status = self._patched_status("google")
        assert "source" in status


# ---------------------------------------------------------------------------
# connector_status() — source field for apikey (Telegram)
# ---------------------------------------------------------------------------


class TestConnectorStatusSourceApikey:
    """Telegram connector: source reflects env vs vault."""

    _TOKEN_FIELD = "telegram_bot_token"
    _ENV_VAR = "TELEGRAM_BOT_TOKEN"
    _FAKE_TOKEN = "123456:ABCDEFGhijklm-xyz"

    def test_telegram_env_configured_source_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TELEGRAM_BOT_TOKEN in env → configured True, source='env', status='connected'."""
        monkeypatch.setenv(self._ENV_VAR, self._FAKE_TOKEN)
        # Patch vault to return nothing so the env path is exercised.
        with patch(
            "hachi.integrations.oauth_flow.get_apikey_credential",
            return_value=None,
        ):
            status = connector_status("telegram")
        assert status["configured"] is True
        assert status["connected"] is True
        assert status["status"] == "connected"
        assert status["source"] == "env"

    def test_telegram_vault_configured_source_vault(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Vault has the token → source='vault'."""
        monkeypatch.delenv(self._ENV_VAR, raising=False)
        with patch(
            "hachi.integrations.oauth_flow.get_apikey_credential",
            return_value=self._FAKE_TOKEN,
        ):
            status = connector_status("telegram")
        assert status["configured"] is True
        assert status["source"] == "vault"

    def test_telegram_not_configured_source_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Neither vault nor env → source=None."""
        monkeypatch.delenv(self._ENV_VAR, raising=False)
        with patch(
            "hachi.integrations.oauth_flow.get_apikey_credential",
            return_value=None,
        ):
            status = connector_status("telegram")
        assert status["configured"] is False
        assert status["source"] is None


# ---------------------------------------------------------------------------
# all_connector_statuses() — source field passed through
# ---------------------------------------------------------------------------


class TestAllConnectorStatusesSource:
    def test_source_key_in_every_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every connector dict in all_connector_statuses() has a 'source' key."""
        # Patch out vault and token store so this is pure env-check only.
        with (
            patch(
                "hachi.integrations.oauth_flow._token_store.is_connected",
                return_value=False,
            ),
            patch(
                "hachi.integrations.oauth_flow.get_apikey_credential",
                return_value=None,
            ),
        ):
            statuses = all_connector_statuses()
        assert len(statuses) > 0
        for entry in statuses:
            assert "source" in entry, f"Missing 'source' in status for {entry.get('id')}"

    def test_google_source_env_in_all_statuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When GOOGLE_CLIENT_ID is set, google entry in all_connector_statuses has source='env'."""
        _clean_google_env(monkeypatch)
        monkeypatch.setenv(_ALIAS_ID, _FAKE_ID)
        with (
            patch(
                "hachi.integrations.oauth_flow._token_store.is_connected",
                return_value=False,
            ),
            patch(
                "hachi.integrations.oauth_flow.get_apikey_credential",
                return_value=None,
            ),
        ):
            statuses = all_connector_statuses()
        google_entry = next((s for s in statuses if s["id"] == "google"), None)
        assert google_entry is not None
        assert google_entry["source"] == "env"
        assert google_entry["configured"] is True


# ---------------------------------------------------------------------------
# Alias map completeness
# ---------------------------------------------------------------------------


class TestAliasMapCompleteness:
    """Sanity-check that the alias map entries point to real env-var names."""

    def test_alias_map_entries_are_strings(self) -> None:
        """All alias map values are non-empty 2-tuples of strings."""
        for connector_id, (id_alias, secret_alias) in OAUTH2_CLIENT_ID_ALIASES.items():
            assert isinstance(id_alias, str), f"id alias for {connector_id!r} must be str"
            assert isinstance(secret_alias, str), f"secret alias for {connector_id!r} must be str"

    def test_google_alias_keys(self) -> None:
        """Google alias map has the expected names."""
        alias = OAUTH2_CLIENT_ID_ALIASES["google"]
        assert alias[0] == "GOOGLE_CLIENT_ID"
        assert alias[1] == "GOOGLE_CLIENT_SECRET"
