"""
Universal OAuth Manager for Hachi

This module handles zero-friction "Sign in with..." experiences for users.
It spins up a temporary local web server, opens the browser for the user to grant permission,
and securely stores the resulting OAuth tokens locally.

No API keys required from the user.
"""

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

from hachi.core.secret_store import SecretStore, create_default_secret_store


def _read_dotenv_value(path: Path, key: str) -> str | None:
    """Return the value of *key* from a simple ``KEY=VALUE`` .env file, or None."""
    try:
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'") or None
    except Exception:
        return None
    return None


def _resolve_env(name: str) -> str | None:
    """Resolve a credential env var **lazily, at call time**.

    Order: the process environment first, then a project ``.env`` (the current working
    directory, then the Hachi config dir). Resolving lazily — rather than capturing at
    import time — is what makes a value configured in ``.env`` actually take effect. The
    previous module-level ``os.environ.get(...)`` ran exactly once when this module was
    first imported, so a ``.env`` merged into the environment *afterward* (or one living in
    the config dir, or simply a different import order) was never seen — and every Google
    tool failed with "Missing GOOGLE_CLIENT_ID" despite being correctly configured.
    """
    val = os.environ.get(name)
    if val:
        return val
    candidates = [Path.cwd() / ".env"]
    try:
        from hachi.core.paths import get_hachi_paths

        candidates.append(get_hachi_paths().config_dir / ".env")
    except Exception:
        pass
    for path in candidates:
        val = _read_dotenv_value(path, name)
        if val:
            return val
    return None


def _google_client_id() -> str | None:
    """The configured Google OAuth client id (lazy). See :func:`_resolve_env`."""
    return _resolve_env("GOOGLE_CLIENT_ID")


def _google_client_secret() -> str | None:
    """The configured Google OAuth client secret (lazy; optional for Desktop clients)."""
    return _resolve_env("GOOGLE_CLIENT_SECRET")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Temporary local server to catch the OAuth redirect."""

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        expected_state = getattr(self.server, "oauth_state", None)
        received_state = params.get("state", [None])[0]

        if "code" in params and expected_state and expected_state == received_state:
            self.server.auth_code = params["code"][0]
            html = """
            <html><body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #4CAF50;">Authentication Successful!</h1>
                <p>You have successfully connected your account to Hachi.</p>
                <p>You can close this window and return to the terminal.</p>
            </body></html>
            """
            self.wfile.write(html.encode("utf-8"))
        elif "code" in params and expected_state and expected_state != received_state:
            self.server.auth_code = None
            html = """
            <html><body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #F44336;">Authentication Failed</h1>
                <p>State validation failed. Please try again.</p>
            </body></html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.server.auth_code = None
            html = """
            <html><body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                <h1 style="color: #F44336;">Authentication Failed</h1>
                <p>No authorization code received. Please try again.</p>
            </body></html>
            """
            self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress logging to keep the terminal clean
        pass


class OAuthManager:
    """Manages OAuth tokens and the browser-based authentication flow."""

    def __init__(self, secret_store: SecretStore | None = None):
        self._store = secret_store or create_default_secret_store()

    @staticmethod
    def _key(provider: str) -> str:
        return f"oauth.{provider}"

    @staticmethod
    def _require_google_client_id() -> str:
        client_id = _google_client_id()
        if not client_id:
            raise RuntimeError(
                "Missing GOOGLE_CLIENT_ID. Configure Google OAuth before using Google integrations."
            )
        return client_id

    @staticmethod
    def _exchange_token(payload: dict[str, str]) -> dict:
        """POST to Google's token endpoint, surfacing the real error on failure.

        Google returns the actual cause (``invalid_client``,
        ``redirect_uri_mismatch``, ``invalid_grant``, …) in the JSON body of a
        4xx response.  ``raise_for_status()`` discards that body, so we read it
        first and raise a message the user can act on.
        """
        response = httpx.post("https://oauth2.googleapis.com/token", data=payload)
        if response.is_success:
            return response.json()

        detail = ""
        try:
            body = response.json()
            err = body.get("error", "")
            desc = body.get("error_description", "")
            detail = f"{err}: {desc}".strip(": ") if (err or desc) else ""
        except Exception:
            detail = response.text.strip()

        hint = ""
        if "invalid_client" in detail:
            hint = (
                " — check GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET. If your OAuth client is a "
                '"Web application" type, GOOGLE_CLIENT_SECRET is required; for a "Desktop app" '
                "client it is optional."
            )
        elif "redirect_uri_mismatch" in detail:
            hint = (
                " — use a 'Desktop app' OAuth client (it allows loopback redirects on any "
                "port), or register the exact redirect URI in the Google Cloud console."
            )
        elif "invalid_grant" in detail:
            hint = " — the authorization code expired or was already used; re-run to retry."

        raise RuntimeError(
            f"Google token endpoint returned {response.status_code} "
            f"({detail or 'no error detail'}){hint}"
        )

    @staticmethod
    def _build_pkce() -> dict[str, str]:
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest())
            .decode("utf-8")
            .rstrip("=")
        )
        return {"verifier": verifier, "challenge": challenge, "method": "S256"}

    def get_token(self, provider: str) -> dict | None:
        """Load a saved token from secure storage.

        The agent stores tokens under the "oauth." prefix (via :meth:`_key`).
        The web UI (``integrations/oauth_flow.py``) stores them under the
        "oauth2." prefix.  Fall back to the web-UI prefix so that a session
        authenticated through the web UI is immediately visible to the agent
        without requiring a separate ``hachi google-auth`` run.
        """
        raw = self._store.get(self._key(provider))
        if not raw:
            # BB-10: web UI stores tokens under "oauth2.<provider>"; fall back
            # so web-authenticated sessions are visible to the agent.
            raw = self._store.get(f"oauth2.{provider}")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    def save_token(self, provider: str, token_data: dict):
        """Save a token to secure storage with metadata."""
        metadata = {
            "name": self._key(provider),
            "labels": {
                "provider": provider,
                "scope": str(token_data.get("scope", "")),
            },
        }
        self._store.set(self._key(provider), json.dumps(token_data), metadata=metadata)

    def get_google_credentials(self, scopes: list[str]) -> str:
        """
        Gets a valid Google access token.
        If none exists, it triggers the browser OAuth flow.
        If it's expired, it automatically refreshes it.
        """
        token_data = self.get_token("google")

        # Check if the requested scopes are a subset of the granted scopes
        granted_scopes = token_data.get("scope", "").split(" ") if token_data else []
        scopes_satisfied = all(scope in granted_scopes for scope in scopes)

        # If we have a token, it has all required scopes, and it's not expired
        # (with a 60s clock-skew buffer), return it.
        if token_data and scopes_satisfied and time.time() < token_data.get("expires_at", 0) - 60:
            return token_data["access_token"]

        # If we have a token, it has all scopes, but it's expired, refresh it.
        if token_data and scopes_satisfied and "refresh_token" in token_data:
            print("  [oauth] Refreshing Google token silently...")
            try:
                return self._refresh_google_token(token_data)
            except Exception as exc:
                # Refresh token revoked/expired (e.g. invalid_grant) — fall back to
                # the full browser flow instead of failing every Google tool call.
                print(f"  [oauth] Token refresh failed ({exc}); re-authenticating...")

        # Otherwise, we need to do the full browser flow (missing token or missing scopes)
        if token_data and not scopes_satisfied:
            print("  [oauth] Upgrading Google account permissions for new capabilities...")
        return self._run_google_browser_flow(scopes)

    def _run_google_browser_flow(self, scopes: list[str]) -> str:
        """Spins up local server, opens browser, gets code, trades for token."""
        # Fail fast in a non-interactive process (the gateway/serve server sets this flag):
        # there is no display to complete the consent, and blocking ~120s on a dead browser
        # redirect would stall a web turn. The one-time consent is done via `hachi google-auth`
        # in a terminal; the server then uses the saved token + silent refresh.
        if os.environ.get("HACHI_OAUTH_NONINTERACTIVE"):
            raise RuntimeError(
                "Google needs a one-time browser sign-in, but Hachi is running "
                "non-interactively (gateway/server). Run `hachi google-auth` once in a "
                "terminal to connect your account; the server will then use the saved token "
                "and refresh it automatically."
            )
        print("  [oauth] Connecting to Google...")
        print("  [oauth] A browser window will open to complete authentication.")

        client_id = self._require_google_client_id()
        pkce = self._build_pkce()
        state = secrets.token_urlsafe(24)

        # 1. Start local server on an ephemeral port to avoid conflicts
        server = HTTPServer(("127.0.0.1", 0), OAuthCallbackHandler)
        actual_port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{actual_port}/callback"
        server.auth_code = None
        server.oauth_state = state

        # 2. Open browser to Google Consent Screen
        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
            "&response_type=code"
            f"&scope={urllib.parse.quote(' '.join(scopes))}"
            "&access_type=offline"
            "&prompt=consent"
            f"&state={urllib.parse.quote(state)}"
            f"&code_challenge={urllib.parse.quote(pkce['challenge'])}"
            f"&code_challenge_method={pkce['method']}"
        )
        webbrowser.open(auth_url)

        # 3. Wait for the redirect — 2-minute timeout to avoid blocking forever
        server.timeout = 120
        server.handle_request()

        if server.auth_code is None:
            raise TimeoutError(
                "Authentication failed or was cancelled (timed out waiting for consent)."
            )

        # 4. Trade the code for the actual tokens
        print("  [oauth] Authorization received. Securing tokens...")
        token_payload = {
            "code": server.auth_code,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": pkce["verifier"],
        }
        client_secret = _google_client_secret()
        if client_secret:
            token_payload["client_secret"] = client_secret

        data = self._exchange_token(token_payload)

        # Calculate absolute expiration time
        data["expires_at"] = time.time() + data.get("expires_in", 3600)

        # 5. Save securely
        self.save_token("google", data)
        print("  [oauth] ✓ Google account connected successfully!")

        return data["access_token"]

    def _refresh_google_token(self, old_token_data: dict) -> str:
        """Trades a refresh token for a fresh access token."""
        refresh_token = old_token_data["refresh_token"]
        client_id = self._require_google_client_id()
        payload = {
            "client_id": client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        client_secret = _google_client_secret()
        if client_secret:
            payload["client_secret"] = client_secret

        data = self._exchange_token(payload)

        # Merge new data into old token to preserve scopes and other metadata
        for key, value in data.items():
            old_token_data[key] = value

        old_token_data["expires_at"] = time.time() + data.get("expires_in", 3600)
        self.save_token("google", old_token_data)

        return old_token_data["access_token"]
