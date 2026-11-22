"""Connector registry: static metadata for all OAuth2 / API-key connectors.

Each entry drives:
  - The integrations list the frontend renders (GET /capabilities or GET /integrations).
  - The OAuth flow: authorize_url, token_url, scopes, env var names for client creds.
  - Status computation: ``configured`` (client creds present in env),
    ``connected`` (valid token stored), ``auth_type``.

Adding a new connector: add an entry to ``CONNECTORS`` — nothing else needs changing.

Env var naming convention for OAuth2 connectors (canonical):
    HACHI_OAUTH_{PROVIDER_UPPER}_CLIENT_ID
    HACHI_OAUTH_{PROVIDER_UPPER}_CLIENT_SECRET

Example for Google (canonical):
    HACHI_OAUTH_GOOGLE_CLIENT_ID=<your-client-id>
    HACHI_OAUTH_GOOGLE_CLIENT_SECRET=<your-client-secret>

Legacy / bare env aliases (see ``OAUTH2_CLIENT_ID_ALIASES`` below):
    GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
    SLACK_CLIENT_ID  / SLACK_CLIENT_SECRET
    DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET
    NOTION_CLIENT_ID / NOTION_CLIENT_SECRET

Either form is accepted.  Canonical names take precedence.  When either is set,
``is_configured()`` returns ``True`` and ``connector_status()`` reports
``source="env"``.

The ``redirect_uri`` registered in the provider's OAuth app must be:
    <HACHI_OAUTH_REDIRECT_BASE>/integrations/oauth/callback
    Default base: http://localhost:8787
    Full default: http://localhost:8787/integrations/oauth/callback

Env-var → connector → UI-state mapping
---------------------------------------
The table below documents every recognised env var and the resulting UI state.
A checkmark in "configured" means the connector shows "Ready to connect" in the
integrations panel.

OAuth2 connectors (client_id is the minimum requirement):

  Connector  | Canonical env var                       | Legacy alias
  -----------+-----------------------------------------+-----------------------------
  google     | HACHI_OAUTH_GOOGLE_CLIENT_ID            | GOOGLE_CLIENT_ID
  google     | HACHI_OAUTH_GOOGLE_CLIENT_SECRET        | GOOGLE_CLIENT_SECRET
  slack      | HACHI_OAUTH_SLACK_CLIENT_ID             | SLACK_CLIENT_ID
  slack      | HACHI_OAUTH_SLACK_CLIENT_SECRET         | SLACK_CLIENT_SECRET
  discord    | HACHI_OAUTH_DISCORD_CLIENT_ID           | DISCORD_CLIENT_ID
  discord    | HACHI_OAUTH_DISCORD_CLIENT_SECRET       | DISCORD_CLIENT_SECRET
  notion     | HACHI_OAUTH_NOTION_CLIENT_ID            | NOTION_CLIENT_ID
  notion     | HACHI_OAUTH_NOTION_CLIENT_SECRET        | NOTION_CLIENT_SECRET

NOTE: GitHub OAuth is intentionally absent from this registry.  The OAuth flow
itself (authorize → token) would work, but there is no hachi GitHub tool backend
to invoke after connecting — surfacing a "Connect GitHub" button with no callable
tools would be a dead UI affordance.  Add a GitHub entry here once a
``src/hachi/integrations/github/`` tool module exists (see DECISIONS.md P1-9).

API-key connectors (field_key.upper() is already the conventional env var):

  Connector  | Field key              | Env var
  -----------+------------------------+----------------------
  telegram   | telegram_bot_token     | TELEGRAM_BOT_TOKEN
  tavily     | tavily_api_key         | TAVILY_API_KEY
  whatsapp   | META_WHATSAPP_TOKEN    | META_WHATSAPP_TOKEN
  whatsapp   | META_WHATSAPP_PHONE_ID | META_WHATSAPP_PHONE_ID
"""

from __future__ import annotations

import os
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

AuthType = Literal["oauth2", "apikey", "none"]

# ---------------------------------------------------------------------------
# Legacy / bare env-var alias map for OAuth2 connectors
# ---------------------------------------------------------------------------

# Maps connector_id → (legacy_client_id_env, legacy_client_secret_env).
# When the canonical ``HACHI_OAUTH_<NAME>_*`` env vars are absent, resolution
# falls back to these aliases so that a plain ``.env`` with ``GOOGLE_CLIENT_ID``
# still satisfies ``is_configured()`` without any migration step.
#
# Keys must exactly match the ``id`` field of the corresponding :class:`ConnectorDef`.
# Values are 2-tuples of ``(client_id_env_alias, client_secret_env_alias)``.
# Set either element to ``""`` when no alias exists for that field.
OAUTH2_CLIENT_ID_ALIASES: dict[str, tuple[str, str]] = {
    "google": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
    "slack": ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"),
    "discord": ("DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET"),
    "notion": ("NOTION_CLIENT_ID", "NOTION_CLIENT_SECRET"),
}


class CredentialFieldSpec(dict[str, Any]):
    """A single credential field descriptor for apikey connectors.

    Keys:
        key: Storage key used in the vault (e.g. ``"telegram_bot_token"``).
        label: Human-readable label for the form field.
        secret: When ``True`` the UI renders a password input.
        placeholder: Example value shown as placeholder text.
        optional: When ``True`` the field is not required for ``configured`` status.
        help_text: Optional short description shown below the field.
    """


def _field(
    key: str,
    label: str,
    *,
    secret: bool = False,
    placeholder: str = "",
    optional: bool = False,
    help_text: str = "",
) -> CredentialFieldSpec:
    """Build a :class:`CredentialFieldSpec` dict."""
    spec: CredentialFieldSpec = CredentialFieldSpec(
        key=key,
        label=label,
        secret=secret,
        placeholder=placeholder,
        optional=optional,
        help_text=help_text,
    )
    return spec


class ConnectorDef:
    """Static definition of a third-party connector.

    Args:
        id: Slug identifier, unique across the registry (e.g. ``"google"``).
        name: Human-readable display name.
        category: Grouping hint for the UI (e.g. ``"productivity"``, ``"messaging"``).
        auth_type: Authentication mechanism — ``"oauth2"``, ``"apikey"``, or ``"none"``.
        authorize_url: OAuth2 authorization endpoint URL (``oauth2`` only).
        token_url: OAuth2 token exchange endpoint URL (``oauth2`` only).
        revoke_url: Optional OAuth2 token revocation endpoint.
        default_scopes: Default OAuth2 scopes requested during authorization.
        client_id_env: Name of the env var holding the OAuth2 client ID.
        client_secret_env: Name of the env var holding the OAuth2 client secret.
        needs_offline: Whether to request offline access (refresh token).
            Defaults to ``True`` for oauth2 connectors.
        extra_auth_params: Optional extra query params for the authorize URL
            (e.g. ``{"prompt": "select_account"}``).
        credential_fields: For ``apikey`` connectors — ordered list of field specs
            describing which credentials must be submitted via the UI / vault.
            Empty for ``oauth2`` / ``none`` connectors.
    """

    def __init__(
        self,
        *,
        id: str,
        name: str,
        category: str,
        auth_type: AuthType = "oauth2",
        authorize_url: str = "",
        token_url: str = "",
        revoke_url: str = "",
        default_scopes: list[str] | None = None,
        client_id_env: str = "",
        client_secret_env: str = "",
        needs_offline: bool = True,
        extra_auth_params: dict[str, str] | None = None,
        credential_fields: list[CredentialFieldSpec] | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.category = category
        self.auth_type: AuthType = auth_type
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.revoke_url = revoke_url
        self.default_scopes: list[str] = default_scopes or []
        self.client_id_env = client_id_env
        self.client_secret_env = client_secret_env
        self.needs_offline = needs_offline
        self.extra_auth_params: dict[str, str] = extra_auth_params or {}
        self.credential_fields: list[CredentialFieldSpec] = credential_fields or []

    def client_id(self) -> str | None:
        """Return the OAuth2 client ID from env, or None if not configured.

        Resolution order:
        1. Canonical env var (``client_id_env``, e.g. ``HACHI_OAUTH_GOOGLE_CLIENT_ID``).
        2. Legacy alias from :data:`OAUTH2_CLIENT_ID_ALIASES` (e.g. ``GOOGLE_CLIENT_ID``).
        """
        if self.client_id_env:
            val = os.environ.get(self.client_id_env) or None
            if val:
                return val
        alias_pair = OAUTH2_CLIENT_ID_ALIASES.get(self.id)
        if alias_pair:
            alias_env = alias_pair[0]
            if alias_env:
                return os.environ.get(alias_env) or None
        return None

    def client_secret(self) -> str | None:
        """Return the OAuth2 client secret from env, or None if not set.

        Resolution order:
        1. Canonical env var (``client_secret_env``, e.g. ``HACHI_OAUTH_GOOGLE_CLIENT_SECRET``).
        2. Legacy alias from :data:`OAUTH2_CLIENT_ID_ALIASES` (e.g. ``GOOGLE_CLIENT_SECRET``).
        """
        if self.client_secret_env:
            val = os.environ.get(self.client_secret_env) or None
            if val:
                return val
        alias_pair = OAUTH2_CLIENT_ID_ALIASES.get(self.id)
        if alias_pair:
            alias_env = alias_pair[1]
            if alias_env:
                return os.environ.get(alias_env) or None
        return None

    def is_configured(self) -> bool:
        """Return True iff the minimum client credentials are present in env.

        For oauth2 connectors the client_id is the minimum requirement
        (some providers allow public clients without a secret).  Both the
        canonical ``HACHI_OAUTH_<NAME>_CLIENT_ID`` env var and any legacy alias
        registered in :data:`OAUTH2_CLIENT_ID_ALIASES` are accepted.

        For non-oauth2 connectors always returns False (not applicable via OAuth
        flow).  Apikey connectors use :func:`is_apikey_connector_configured` in
        ``oauth_flow`` which checks the vault; this method only checks env for
        OAuth2.
        """
        if self.auth_type != "oauth2":
            return False
        return bool(self.client_id())

    def required_credential_keys(self) -> list[str]:
        """Return vault keys for all non-optional credential fields."""
        return [f["key"] for f in self.credential_fields if not f.get("optional", False)]

    def env_var_for_key(self, key: str) -> str | None:
        """Return the conventional env var name for a credential field key.

        Convention: field key uppercased.  E.g. ``telegram_bot_token`` → ``TELEGRAM_BOT_TOKEN``.
        """
        return key.upper() if key else None


# ---------------------------------------------------------------------------
# Connector definitions
# ---------------------------------------------------------------------------

CONNECTORS: list[ConnectorDef] = [
    # --- Google (Gmail / Calendar / Drive unified client) ---
    ConnectorDef(
        id="google",
        name="Google",
        category="productivity",
        auth_type="oauth2",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        revoke_url="https://oauth2.googleapis.com/revoke",
        default_scopes=[
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/drive",
        ],
        client_id_env="HACHI_OAUTH_GOOGLE_CLIENT_ID",
        client_secret_env="HACHI_OAUTH_GOOGLE_CLIENT_SECRET",
        needs_offline=True,
        extra_auth_params={"access_type": "offline", "prompt": "consent"},
    ),
    # --- Slack ---
    ConnectorDef(
        id="slack",
        name="Slack",
        category="messaging",
        auth_type="oauth2",
        authorize_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        revoke_url="https://slack.com/api/auth.revoke",
        default_scopes=[
            "channels:read",
            "channels:history",
            "chat:write",
            "users:read",
            "files:read",
        ],
        client_id_env="HACHI_OAUTH_SLACK_CLIENT_ID",
        client_secret_env="HACHI_OAUTH_SLACK_CLIENT_SECRET",
        needs_offline=False,  # Slack tokens don't expire; no refresh token needed
        extra_auth_params={},
    ),
    # --- Discord ---
    ConnectorDef(
        id="discord",
        name="Discord",
        category="messaging",
        auth_type="oauth2",
        authorize_url="https://discord.com/api/oauth2/authorize",
        token_url="https://discord.com/api/oauth2/token",
        revoke_url="https://discord.com/api/oauth2/token/revoke",
        default_scopes=["identify", "guilds", "messages.read"],
        client_id_env="HACHI_OAUTH_DISCORD_CLIENT_ID",
        client_secret_env="HACHI_OAUTH_DISCORD_CLIENT_SECRET",
        needs_offline=True,
    ),
    # --- Notion ---
    ConnectorDef(
        id="notion",
        name="Notion",
        category="productivity",
        auth_type="oauth2",
        authorize_url="https://api.notion.com/v1/oauth/authorize",
        token_url="https://api.notion.com/v1/oauth/token",
        revoke_url="",  # Notion does not have a revoke endpoint
        default_scopes=[],  # Notion uses owner/workspace, not scope strings
        client_id_env="HACHI_OAUTH_NOTION_CLIENT_ID",
        client_secret_env="HACHI_OAUTH_NOTION_CLIENT_SECRET",
        needs_offline=False,  # Notion tokens are long-lived
        extra_auth_params={"owner": "user"},
    ),
    # --- WhatsApp (Meta Business API) — not standard OAuth2; listed as apikey ---
    # Users must provision a permanent token via Meta Business Suite.
    # No OAuth2 flow is available for WhatsApp Business API.
    # Supports both Meta Cloud API (recommended) and Twilio sandbox paths.
    ConnectorDef(
        id="whatsapp",
        name="WhatsApp",
        category="messaging",
        auth_type="apikey",
        credential_fields=[
            # Meta Cloud API (recommended — permanent system-user token)
            _field(
                "META_WHATSAPP_TOKEN",
                "Meta Access Token",
                secret=True,
                placeholder="EAAxxxxxxxxxxxxxx",
                optional=False,
                help_text="System-user token from Meta Business Suite. Required for Meta Cloud API.",  # noqa: E501
            ),
            _field(
                "META_WHATSAPP_PHONE_ID",
                "Phone Number ID",
                secret=False,
                placeholder="123456789012345",
                optional=False,
                help_text="Sender phone-number ID from Meta for Developers dashboard.",
            ),
            # Twilio Sandbox path (optional — only needed if using Twilio instead of Meta)
            _field(
                "TWILIO_ACCOUNT_SID",
                "Twilio Account SID",
                secret=False,
                placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                optional=True,
                help_text="Only required if routing through Twilio instead of Meta Cloud API.",
            ),
            _field(
                "TWILIO_AUTH_TOKEN",
                "Twilio Auth Token",
                secret=True,
                placeholder="",
                optional=True,
                help_text="Twilio auth token. Only required for Twilio routing.",
            ),
            _field(
                "TWILIO_WHATSAPP_FROM",
                "Twilio WhatsApp From",
                secret=False,
                placeholder="whatsapp:+14155238886",
                optional=True,
                help_text="Twilio sandbox/production sender number, prefixed with 'whatsapp:'.",
            ),
        ],
    ),
    # --- Telegram (Bot API — long-polling, no public URL required) ---
    # Users create a bot via @BotFather and paste the bot token here.
    # The token is stored in the credential vault; the channel reads it at startup.
    ConnectorDef(
        id="telegram",
        name="Telegram",
        category="messaging",
        auth_type="apikey",
        credential_fields=[
            _field(
                "telegram_bot_token",
                "Bot Token",
                secret=True,
                placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                optional=False,
                help_text=(
                    "Create a bot with @BotFather on Telegram, then paste the token here. "
                    "Format: <digits>:<alphanumeric-string>"
                ),
            ),
        ],
    ),
    # --- Tavily (web search provider) ---
    # Users get an API key from tavily.com and paste it here. Stored under the
    # vault ref "tavily_api_key" / env TAVILY_API_KEY — exactly what the Tavily
    # search provider reads, so configuring it here takes effect.
    ConnectorDef(
        id="tavily",
        name="Tavily",
        category="search",
        auth_type="apikey",
        credential_fields=[
            _field(
                "tavily_api_key",
                "API Key",
                secret=True,
                placeholder="tvly-...",
                optional=False,
                help_text=(
                    "Get a key from tavily.com — Hachi uses it for live web search. "
                    "The key starts with 'tvly-'."
                ),
            ),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, ConnectorDef] = {c.id: c for c in CONNECTORS}


def get_connector(connector_id: str) -> ConnectorDef | None:
    """Look up a connector by id, returning None if not found.

    Args:
        connector_id: The connector slug (e.g. ``"google"``).

    Returns:
        The :class:`ConnectorDef` if found, ``None`` otherwise.
    """
    return _REGISTRY.get(connector_id)


def list_connectors() -> list[ConnectorDef]:
    """Return all registered connectors in definition order."""
    return list(CONNECTORS)


def oauth2_connectors() -> list[ConnectorDef]:
    """Return only OAuth2-capable connectors."""
    return [c for c in CONNECTORS if c.auth_type == "oauth2"]
