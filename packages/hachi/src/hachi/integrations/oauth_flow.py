"""OAuth 2.0 authorization-code flow for the Hachi gateway.

This module implements the server-side OAuth 2.0 authorization-code flow
that the frontend's integration settings screen drives via browser popups.

Flow summary
------------
1. Frontend calls ``POST /integrations/{id}/oauth/start``
   → server generates a random ``state`` token, builds the provider's
     authorize URL, stores {state → connector_id} with a 10-minute TTL,
     returns ``{"authorization_url": "..."}`` to the frontend.

2. Frontend opens the URL in a popup window.  The user grants consent.
   Provider redirects the popup to ``GET /integrations/oauth/callback?code=...&state=...``.

3. Callback handler:
   - Validates ``state`` (CSRF defence) — rejects unknown / expired states.
   - Validates ``connector_id`` against the registry.
   - Exchanges ``code`` for tokens at the provider's ``token_url`` via ``httpx``.
   - Stores tokens via the existing ``SecretStore`` (keyring / encrypted-file).
   - Returns a tiny HTML page that postMessages to the opener and closes itself.

4. Frontend calls ``POST /integrations/{id}/disconnect``
   → revokes the token at the provider (best-effort) and deletes stored tokens.

Security
--------
- ``state`` is generated with ``secrets.token_urlsafe(32)`` — 256 bits of entropy.
- State is stored in a process-local dict with a 10-minute TTL.  Expired or
  unknown state → HTTP 400.  Each state is single-use (deleted on first use).
- Connector id is validated against the registry before any processing.
- Tokens are NEVER logged.  Only the connector id is reflected in HTML output.
- The callback HTML only emits a fixed postMessage payload — no query param
  values are interpolated into the HTML to prevent XSS.
- ``httpx`` is used for all HTTP calls (no ``requests``, no ``subprocess``).

Token storage
-------------
Tokens are serialised to JSON and stored under the key
    ``oauth2.<connector_id>``
using the existing ``SecretStore`` (``create_default_secret_store()``),
which tries the OS keyring (Windows Credential Manager / macOS Keychain /
Linux Secret Service) and falls back to Fernet-encrypted file storage.

Configuration
-------------
- ``HACHI_OAUTH_REDIRECT_BASE`` — base URL the gateway is reachable at for the
  OAuth redirect.  Default: ``http://localhost:8787``.  The provider's OAuth app
  must have ``<base>/integrations/oauth/callback`` registered as an allowed
  redirect URI.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
import urllib.parse
from typing import Any

import httpx

from hachi.core.credential_vault import CredentialVault
from hachi.core.secret_store import SecretStore, create_default_secret_store
from hachi.integrations.connector_registry import (
    OAUTH2_CLIENT_ID_ALIASES,
    ConnectorDef,
    get_connector,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# OAuth redirect base.  The callback path is always /integrations/oauth/callback.
_DEFAULT_REDIRECT_BASE = "http://localhost:8787"
_CALLBACK_PATH = "/integrations/oauth/callback"
_STATE_TTL_SECONDS = 600  # 10 minutes


def _redirect_base() -> str:
    """Return the configured redirect base URL (no trailing slash)."""
    base = os.environ.get("HACHI_OAUTH_REDIRECT_BASE", _DEFAULT_REDIRECT_BASE).rstrip("/")
    return base


def redirect_uri() -> str:
    """Return the full OAuth redirect URI the provider should redirect to."""
    return f"{_redirect_base()}{_CALLBACK_PATH}"


# ---------------------------------------------------------------------------
# State store (in-memory, single-process)
# ---------------------------------------------------------------------------


class _StateEntry:
    """A pending OAuth state entry with TTL."""

    __slots__ = ("connector_id", "expires_at")

    def __init__(self, connector_id: str, ttl: int = _STATE_TTL_SECONDS) -> None:
        self.connector_id = connector_id
        self.expires_at: float = time.monotonic() + ttl

    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at


class OAuthStateStore:
    """Thread-safe, in-memory store for pending OAuth state tokens.

    Each state is single-use and expires after ``_STATE_TTL_SECONDS`` seconds.
    A lightweight sweep removes stale entries on every ``create`` call so the
    dict doesn't grow unbounded (bounded by concurrent active OAuth flows * TTL).
    """

    def __init__(self) -> None:
        import threading

        self._states: dict[str, _StateEntry] = {}
        self._lock = threading.Lock()

    def create(self, connector_id: str) -> str:
        """Generate a new random state token and record it.

        Args:
            connector_id: The connector this state is associated with.

        Returns:
            The generated state string (URL-safe base64, 256-bit entropy).
        """
        state = secrets.token_urlsafe(32)
        with self._lock:
            # Sweep stale entries to keep memory bounded.
            self._states = {k: v for k, v in self._states.items() if v.is_valid()}
            self._states[state] = _StateEntry(connector_id)
        return state

    def consume(self, state: str) -> str | None:
        """Validate and consume a state token.

        If the state is unknown or expired, returns ``None``.
        On success the state is removed (single-use) and the connector id returned.

        Args:
            state: The state value from the OAuth callback query string.

        Returns:
            The connector id if valid, ``None`` otherwise.
        """
        with self._lock:
            entry = self._states.pop(state, None)
        if entry is None or not entry.is_valid():
            return None
        return entry.connector_id


# Module-level singleton used by the FastAPI routes.
_state_store = OAuthStateStore()


# ---------------------------------------------------------------------------
# Token storage
# ---------------------------------------------------------------------------

_TOKEN_KEY_PREFIX = "oauth2."


def _token_key(connector_id: str) -> str:
    return f"{_TOKEN_KEY_PREFIX}{connector_id}"


class OAuthTokenStore:
    """Read/write OAuth2 tokens from the app's existing SecretStore.

    Tokens are stored as JSON-serialised dicts containing at minimum:
      ``access_token``, ``token_type``, ``expires_at`` (Unix timestamp),
      and optionally ``refresh_token``, ``scope``.

    Never logs token values.
    """

    def __init__(self, secret_store: SecretStore | None = None) -> None:
        self._store = secret_store or create_default_secret_store()

    def load(self, connector_id: str) -> dict[str, Any] | None:
        """Return parsed token dict for connector, or None if absent/corrupt."""
        raw = self._store.get(_token_key(connector_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return None

    def save(self, connector_id: str, token_data: dict[str, Any]) -> None:
        """Persist token data for connector.  Never logs token values.

        Args:
            connector_id: Connector slug (e.g. ``"google"``).
            token_data: Parsed token response dict.
        """
        key = _token_key(connector_id)
        self._store.set(
            key,
            json.dumps(token_data),
            metadata={"name": key, "labels": {"provider": connector_id, "type": "oauth2"}},
        )

    def delete(self, connector_id: str) -> None:
        """Remove stored tokens for connector."""
        self._store.delete(_token_key(connector_id))

    def is_connected(self, connector_id: str) -> bool:
        """Return True iff a token is stored (does not validate expiry)."""
        return self.load(connector_id) is not None


# Module-level singleton.
_token_store = OAuthTokenStore()


# ---------------------------------------------------------------------------
# API-key credential storage (for apikey connectors)
# ---------------------------------------------------------------------------

_APIKEY_PREFIX = "apikey."


def _apikey_vault_key(connector_id: str, field_key: str) -> str:
    """Compute the vault storage key for a single apikey credential field.

    Convention: ``apikey.<connector_id>.<field_key>``
    This namespace is separate from OAuth2 tokens (``oauth2.*``) so the two
    never collide, even if a connector changes auth_type in the future.

    Args:
        connector_id: Connector slug (e.g. ``"telegram"``).
        field_key: Credential field key (e.g. ``"telegram_bot_token"``).

    Returns:
        Vault storage key string.
    """
    return f"{_APIKEY_PREFIX}{connector_id}.{field_key}"


def store_apikey_credential(connector_id: str, field_key: str, value: str) -> None:
    """Persist a single apikey credential field for a connector.

    Args:
        connector_id: Connector slug.
        field_key: The ``key`` from the connector's :attr:`credential_fields`.
        value: The credential value to store.  Must be non-empty.

    Raises:
        ValueError: If ``value`` is empty or ``field_key`` is blank.
    """
    if not field_key:
        raise ValueError("field_key must be non-empty")
    if not value:
        raise ValueError(f"Credential value for {field_key!r} must be non-empty")

    vault = CredentialVault()
    vault.set_token(_apikey_vault_key(connector_id, field_key), value)
    _log.debug("Stored apikey credential connector=%s field=%s", connector_id, field_key)


def get_apikey_credential(connector_id: str, field_key: str) -> str | None:
    """Retrieve a stored apikey credential field value.

    Args:
        connector_id: Connector slug.
        field_key: Credential field key.

    Returns:
        The stored value, or ``None`` if absent.
    """
    vault = CredentialVault()
    try:
        val = vault.get_token(_apikey_vault_key(connector_id, field_key))
        return str(val) if val is not None else None
    except Exception:
        return None


def clear_apikey_credentials(connector_id: str) -> None:
    """Remove all stored apikey credentials for a connector.

    Iterates over the connector's declared ``credential_fields`` and deletes
    each from the vault.  Missing keys are silently skipped.

    Args:
        connector_id: Connector slug.
    """
    connector = get_connector(connector_id)
    if connector is None:
        return

    vault = CredentialVault()
    for field in connector.credential_fields:
        vault_key = _apikey_vault_key(connector_id, field["key"])
        try:
            vault.delete_token(vault_key)
        except Exception:
            pass  # Already absent — no-op
    _log.info("Cleared apikey credentials for connector=%s", connector_id)


def _env_value_for_field(connector_id: str, field_key: str) -> str | None:
    """Check the conventional env var for a credential field.

    The convention (field_key uppercased) matches what :mod:`hachi.channels.whatsapp`
    and :mod:`hachi.channels.telegram_setup` read from ``os.environ``.

    Args:
        connector_id: Connector slug (unused but kept for future disambiguation).
        field_key: Credential field key.

    Returns:
        The env var value, or ``None`` if not set.
    """
    env_var = field_key.upper()
    return os.environ.get(env_var) or None


def _oauth2_credential_source(connector: ConnectorDef) -> str | None:
    """Return where the OAuth2 client-id credential was found.

    Checks the same resolution order as :meth:`ConnectorDef.client_id`:
    canonical env var first, then any registered legacy alias.

    Args:
        connector: The :class:`ConnectorDef` to inspect.

    Returns:
        ``"env"`` when a client id is found in any env var, ``None`` otherwise.
        (OAuth2 credentials never live in the vault — they come only from env.)
    """
    if connector.client_id_env and os.environ.get(connector.client_id_env):
        return "env"
    alias_pair = OAUTH2_CLIENT_ID_ALIASES.get(connector.id)
    if alias_pair and alias_pair[0] and os.environ.get(alias_pair[0]):
        return "env"
    return None


def _apikey_credential_source(connector_id: str) -> str | None:
    """Return where the first required apikey credential was found.

    Checks vault then env for each required field, in the same order as
    :func:`is_apikey_connector_configured`.

    Args:
        connector_id: Connector slug.

    Returns:
        ``"vault"`` when the first satisfied required field came from the vault,
        ``"env"`` when it came from an environment variable, ``None`` when no
        required field is satisfied (i.e. the connector is not configured).
    """
    connector = get_connector(connector_id)
    if connector is None or connector.auth_type != "apikey":
        return None
    required_keys = connector.required_credential_keys()
    if not required_keys:
        return None
    for field_key in required_keys:
        vault_val = get_apikey_credential(connector_id, field_key)
        if vault_val:
            return "vault"
        env_val = _env_value_for_field(connector_id, field_key)
        if env_val:
            return "env"
    return None


def is_apikey_connector_configured(connector_id: str) -> bool:
    """Return True iff all required (non-optional) credential fields are present.

    A field is considered present when:
    - Its value exists in the credential vault, OR
    - The conventional environment variable (field_key uppercased) is set.

    Args:
        connector_id: Connector slug.

    Returns:
        ``True`` when every required field has a value; ``False`` otherwise.
        Returns ``False`` for unknown connectors or connectors with no fields.
    """
    connector = get_connector(connector_id)
    if connector is None or connector.auth_type != "apikey":
        return False

    required_keys = connector.required_credential_keys()
    if not required_keys:
        # No required fields — consider it "configured" (e.g. legacy connectors).
        return True

    for field_key in required_keys:
        vault_val = get_apikey_credential(connector_id, field_key)
        env_val = _env_value_for_field(connector_id, field_key)
        if not (vault_val or env_val):
            return False
    return True


# ---------------------------------------------------------------------------
# OAuth flow helpers
# ---------------------------------------------------------------------------


def _build_authorize_url(connector: ConnectorDef, state: str) -> str:
    """Build the provider authorize URL with all required parameters.

    Args:
        connector: The :class:`ConnectorDef` for the provider.
        state: CSRF state token to embed in the URL.

    Returns:
        Full authorization URL string.
    """
    params: dict[str, str] = {
        "client_id": connector.client_id() or "",
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "state": state,
    }
    if connector.default_scopes:
        params["scope"] = " ".join(connector.default_scopes)
    if connector.needs_offline:
        params.setdefault("access_type", "offline")
    # Provider-specific extras (access_type, prompt, owner, …)
    params.update(connector.extra_auth_params)

    qs: str = str(urllib.parse.urlencode(params))
    return str(connector.authorize_url) + "?" + qs


def _exchange_code(
    connector: ConnectorDef,
    code: str,
) -> dict[str, Any]:
    """Exchange an authorization code for tokens at the provider's token endpoint.

    Uses ``httpx`` for the POST request.  Raises ``RuntimeError`` on failure,
    including provider-supplied error descriptions.

    SECURITY: never logs the response body; only logs connector id on error.

    Args:
        connector: The :class:`ConnectorDef` describing the provider.
        code: The authorization code from the callback.

    Returns:
        Parsed token response dict (access_token, token_type, etc.)

    Raises:
        RuntimeError: On HTTP error or non-JSON response.
    """
    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "client_id": connector.client_id() or "",
    }
    secret = connector.client_secret()
    if secret:
        payload["client_secret"] = secret

    # Notion uses HTTP Basic auth for token exchange instead of a form body.
    auth = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if connector.id == "notion":
        import base64

        cred = base64.b64encode(f"{connector.client_id() or ''}:{secret or ''}".encode()).decode()
        auth = None
        headers["Authorization"] = f"Basic {cred}"
        headers["Notion-Version"] = "2022-06-28"

    # GitHub requires Accept: application/json to get JSON back.
    if connector.id == "github":
        headers["Accept"] = "application/json"

    try:
        resp = httpx.post(connector.token_url, data=payload, headers=headers, auth=auth)
    except httpx.RequestError as exc:
        raise RuntimeError(f"Network error contacting {connector.id} token endpoint") from exc

    if not resp.is_success:
        detail = ""
        try:
            body = resp.json()
            err = body.get("error", "")
            desc = body.get("error_description", "")
            detail = f"{err}: {desc}".strip(": ") if (err or desc) else resp.text[:200]
        except Exception:
            detail = resp.text[:200]
        # Log only connector id and status — never log the response body wholesale.
        _log.error(
            "Token exchange failed for connector=%s status=%d", connector.id, resp.status_code
        )
        raise RuntimeError(
            f"Token exchange failed for {connector.name} (HTTP {resp.status_code}): {detail}"
        )

    try:
        data: dict[str, Any] = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"Token endpoint for {connector.name} returned non-JSON response"
        ) from exc

    # Normalise: compute expires_at from expires_in if present.
    if "expires_in" in data and "expires_at" not in data:
        data["expires_at"] = time.time() + int(data["expires_in"])

    return data


def _refresh_token(connector: ConnectorDef, token_data: dict[str, Any]) -> dict[str, Any]:
    """Attempt to refresh an expired access token using the refresh token.

    Returns an updated token dict (merged with old data to preserve refresh_token).
    Raises RuntimeError on failure.
    """
    refresh = token_data.get("refresh_token")
    if not refresh:
        raise RuntimeError(f"No refresh token stored for {connector.name}")

    payload: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": connector.client_id() or "",
    }
    secret = connector.client_secret()
    if secret:
        payload["client_secret"] = secret

    headers = {"Accept": "application/json"}
    try:
        resp = httpx.post(connector.token_url, data=payload, headers=headers)
    except httpx.RequestError as exc:
        raise RuntimeError(f"Network error refreshing {connector.name} token") from exc

    if not resp.is_success:
        _log.warning(
            "Token refresh failed for connector=%s status=%d", connector.id, resp.status_code
        )
        raise RuntimeError(f"Token refresh failed for {connector.name} (HTTP {resp.status_code})")

    try:
        new_data: dict[str, Any] = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Non-JSON response from {connector.name} token refresh") from exc

    # Merge: some providers omit the refresh_token in the refresh response.
    merged = {**token_data, **new_data}
    if "expires_in" in new_data:
        merged["expires_at"] = time.time() + int(new_data["expires_in"])
    return merged


def _revoke_token(connector: ConnectorDef, token_data: dict[str, Any]) -> None:
    """Attempt to revoke the access token at the provider.  Best-effort — errors are logged."""
    if not connector.revoke_url:
        return

    access_token = token_data.get("access_token", "")
    if not access_token:
        return

    try:
        if connector.id == "google":
            httpx.post(connector.revoke_url, params={"token": access_token})
        elif connector.id == "slack":
            httpx.post(
                connector.revoke_url,
                data={"token": access_token},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        elif connector.id == "discord":
            client_id = connector.client_id() or ""
            client_secret = connector.client_secret() or ""
            httpx.post(
                connector.revoke_url,
                data={"token": access_token},
                auth=(client_id, client_secret),
            )
    except Exception:
        # Revocation is best-effort — log but do not propagate.
        _log.debug("Token revocation failed for connector=%s (best-effort)", connector.id)


# ---------------------------------------------------------------------------
# Public OAuth flow API
# ---------------------------------------------------------------------------


def oauth_start(connector_id: str) -> dict[str, str]:
    """Begin the OAuth2 flow for the given connector.

    Validates that the connector exists and is configured (client creds in env),
    generates a CSRF state token, and returns the provider's authorize URL.

    Args:
        connector_id: Connector slug (e.g. ``"google"``).

    Returns:
        ``{"authorization_url": "<url>"}``

    Raises:
        ValueError: If the connector is unknown.
        LookupError: If the connector's client credentials are not in env
            (caller should return HTTP 409).
    """
    connector = get_connector(connector_id)
    if connector is None:
        raise ValueError(f"Unknown connector: {connector_id!r}")
    if connector.auth_type != "oauth2":
        raise ValueError(f"Connector {connector_id!r} does not use OAuth2")
    if not connector.is_configured():
        raise LookupError(
            f"OAuth2 client credentials for {connector.name!r} are not configured on this "
            f"machine. Set the env vars {connector.client_id_env!r} "
            f"(and optionally {connector.client_secret_env!r}) then restart the gateway."
        )
    state = _state_store.create(connector_id)
    url = _build_authorize_url(connector, state)
    return {"authorization_url": url}


def oauth_callback(code: str, state: str) -> tuple[str, bool, str]:
    """Handle the OAuth2 callback: validate state, exchange code, store tokens.

    Args:
        code: Authorization code from the provider.
        state: CSRF state token from the provider redirect.

    Returns:
        A ``(connector_id, ok, error_message)`` triple.
        ``ok=True`` means tokens were stored successfully.
        ``error_message`` is empty when ``ok=True``.
    """
    connector_id = _state_store.consume(state)
    if connector_id is None:
        return ("", False, "Invalid or expired state parameter. Please start the OAuth flow again.")

    connector = get_connector(connector_id)
    if connector is None:
        return (connector_id, False, f"Connector {connector_id!r} no longer registered.")

    try:
        token_data = _exchange_code(connector, code)
    except RuntimeError as exc:
        return (connector_id, False, str(exc))

    _token_store.save(connector_id, token_data)
    _log.info("OAuth2 tokens stored for connector=%s", connector_id)
    return (connector_id, True, "")


def oauth_disconnect(connector_id: str) -> dict[str, Any]:
    """Revoke and delete stored tokens for a connector.

    Args:
        connector_id: Connector slug.

    Returns:
        ``{"connected": False, "connector_id": "<id>"}``

    Raises:
        ValueError: If the connector is unknown.
    """
    connector = get_connector(connector_id)
    if connector is None:
        raise ValueError(f"Unknown connector: {connector_id!r}")

    # Best-effort revocation.
    token_data = _token_store.load(connector_id)
    if token_data is not None and connector.revoke_url:
        _revoke_token(connector, token_data)

    _token_store.delete(connector_id)
    _log.info("OAuth2 tokens deleted for connector=%s", connector_id)
    return {"connected": False, "connector_id": connector_id}


def connector_status(connector_id: str) -> dict[str, Any]:
    """Return status fields for a single connector.

    No network calls — only checks env vars and stored token/vault presence.

    For ``apikey`` connectors the ``configured`` flag is ``True`` when all
    required credential fields are present (vault or env).  The ``connected``
    flag mirrors ``configured`` for apikey connectors (no separate token state).

    For ``oauth2`` connectors, ``configured`` means client creds are in env and
    ``connected`` means a real token is stored.

    Also returns ``credential_fields`` from the registry so the UI can render
    the appropriate credential form without a separate registry lookup.

    The ``source`` field (contract C-CREDSOURCE) indicates where the satisfying
    credential was found:
    - ``"env"``   — satisfied by an environment variable (canonical or alias).
    - ``"vault"`` — satisfied by the credential vault (apikey connectors only).
    - ``null``    — connector is not configured / no credential found.

    Args:
        connector_id: Connector slug.

    Returns:
        Dict with ``auth_type``, ``configured``, ``connected``, ``status``,
        ``source``, and ``credential_fields``.
    """
    connector = get_connector(connector_id)
    if connector is None:
        return {
            "auth_type": "none",
            "configured": False,
            "connected": False,
            "status": "unknown",
            "source": None,
            "credential_fields": [],
        }

    # Bug 2: tri-state for connectors backed by an optional Python package.
    # Check package availability before credential presence so "unavailable"
    # (package missing) is distinct from "disconnected" (package present, no key).
    package_installed: bool | None = None
    if connector_id == "tavily":
        import importlib.util

        package_installed = importlib.util.find_spec("tavily") is not None

    if connector.auth_type == "oauth2":
        connected = _token_store.is_connected(connector_id)
        configured = connector.is_configured()
        status = "connected" if connected else ("configured" if configured else "disconnected")
        source: str | None = _oauth2_credential_source(connector) if configured else None
    elif connector.auth_type == "apikey":
        configured = is_apikey_connector_configured(connector_id)
        connected = configured  # apikey connectors are "connected" when all creds are present
        if package_installed is False:
            # Package not installed — override status so UI shows install guidance,
            # not a dead-end key-entry form.
            status = "unavailable"
            connected = False
        else:
            status = "connected" if configured else "disconnected"
        source = _apikey_credential_source(connector_id) if configured else None
    else:
        configured = False
        connected = False
        status = "disconnected"
        source = None

    result: dict[str, Any] = {
        "auth_type": connector.auth_type,
        "configured": configured,
        "connected": connected,
        "status": status,
        "source": source,
        "credential_fields": list(connector.credential_fields),
    }
    if package_installed is not None:
        result["package_installed"] = package_installed
    return result


def all_connector_statuses() -> list[dict[str, Any]]:
    """Return status dicts for all registered connectors.

    No network calls.  Fast enough for the integrations list endpoint.
    Includes ``credential_fields`` for each connector so the UI can render
    the appropriate credential form without a separate round-trip.
    """
    from hachi.integrations.connector_registry import list_connectors

    result: list[dict[str, Any]] = []
    for conn in list_connectors():
        base = connector_status(conn.id)
        result.append(
            {
                "id": conn.id,
                "name": conn.name,
                "category": conn.category,
                **base,
            }
        )
    return result


# ---------------------------------------------------------------------------
# HTML helpers for the callback page
# ---------------------------------------------------------------------------


def _callback_html_ok(connector_id: str) -> str:
    """Return the success HTML page.

    The connector_id is safe to embed — it is sourced from the server-side
    state store (not the query string) and must be a known registry slug.
    """
    # Escape just in case (should only ever be an alphanumeric slug).
    safe_id = connector_id.replace('"', "").replace("'", "").replace("<", "").replace(">", "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Connected</title></head>
<body style="font-family:sans-serif;text-align:center;margin-top:60px;">
<h2 style="color:#4CAF50;">Connected successfully!</h2>
<p>You can close this window and return to Hachi.</p>
<script>
try {{
  window.opener && window.opener.postMessage(
    {{ type: "hachi_oauth_done", id: "{safe_id}", ok: true }},
    "*"
  );
}} catch(_) {{}}
window.close();
</script>
</body>
</html>
"""


def _callback_html_error(connector_id: str, message: str) -> str:
    """Return the error HTML page.

    Neither connector_id nor message is interpolated raw — both are sanitised.
    The message is displayed to the user but NOT injected into the postMessage
    payload to avoid any reflected-XSS vector.
    """
    safe_id = connector_id.replace('"', "").replace("'", "").replace("<", "").replace(">", "")
    # Sanitise for HTML display only — escape <, >, &, "
    safe_msg = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Connection failed</title></head>
<body style="font-family:sans-serif;text-align:center;margin-top:60px;">
<h2 style="color:#F44336;">Connection failed</h2>
<p>{safe_msg}</p>
<p style="margin-top:24px;"><a href="javascript:window.close()">Close this window</a></p>
<script>
try {{
  window.opener && window.opener.postMessage(
    {{ type: "hachi_oauth_done", id: "{safe_id}", ok: false,
       message: "OAuth error — see Hachi integrations settings" }},
    "*"
  );
}} catch(_) {{}}
</script>
</body>
</html>
"""
