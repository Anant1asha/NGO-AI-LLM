"""
Base Slack Service
Provides the core HTTP client wrapper and authentication headers for the Slack Web API.

Token model
-----------
*Bot token* (``slack_bot_token``, prefix ``xoxb-``) — used for channel and chat operations.
*User token* (``slack_user_token``, prefix ``xoxp-``) — required for user-scoped APIs such
as ``search.messages``.  Both are loaded lazily so that a missing credential does not abort
TUI boot; each call site calls the appropriate ``_ensure_*`` helper before making the request.
"""

import httpx

from hachi.core.loop import ToolRegistry


class SlackService:
    """
    Base service for Slack API integrations.
    Handles authentication and provides a pre-configured HTTP client.

    Attributes
    ----------
    bot_token:
        The ``xoxb-`` bot token, used for most channel/chat endpoints.
    user_token:
        The ``xoxp-`` user OAuth token, required for user-scoped endpoints such as
        ``search.messages``.  May be ``None`` if the user has not configured it.
    """

    BASE_URL = "https://slack.com/api"

    def __init__(self):
        from hachi.core.credential_vault import CredentialVault

        self._vault = CredentialVault()
        # Avoid interactive stdin prompts during TUI boot. We resolve lazily per call.
        # get_token raises ValueError when the key is absent; swallow it so a missing credential
        # does not abort TUI boot or tool-registry mount.
        try:
            self.bot_token = self._vault.get_token("slack_bot_token", prompt_if_missing=False)
        except ValueError:
            self.bot_token = None
        # User token is optional — only needed for user-scoped endpoints (e.g. search.messages).
        try:
            self.user_token = self._vault.get_token("slack_user_token", prompt_if_missing=False)
        except ValueError:
            self.user_token = None

    def _ensure_token(self) -> None:
        """Ensure the bot token is available; raise with an actionable message if not."""
        if self.bot_token:
            return
        try:
            self.bot_token = self._vault.get_token("slack_bot_token", prompt_if_missing=False)
        except ValueError:
            pass
        if not self.bot_token:
            raise ValueError(
                "Missing Slack Bot Token. Run: hachi secrets --set slack_bot_token"
            )

    def _ensure_user_token(self) -> None:
        """Ensure the user token (xoxp-) is available; raise with an actionable message if not."""
        if self.user_token:
            return
        try:
            self.user_token = self._vault.get_token("slack_user_token", prompt_if_missing=False)
        except ValueError:
            pass
        if not self.user_token:
            raise ValueError(
                "This Slack API endpoint requires a user OAuth token (xoxp-). "
                "Run: hachi secrets --set slack_user_token"
            )

    @property
    def headers(self) -> dict:
        """Returns the bot-token headers for Slack API requests."""
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    @property
    def user_headers(self) -> dict:
        """Returns the user-token (xoxp-) headers for user-scoped Slack API requests."""
        self._ensure_user_token()
        return {
            "Authorization": f"Bearer {self.user_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _post(self, endpoint: str, json_data: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = httpx.post(url, headers=self.headers, json=json_data or {}, timeout=30.0)
        response.raise_for_status()

        data = response.json()
        if not data.get("ok"):
            error_msg = data.get("error", "Unknown Slack API error")
            needed = data.get("needed")
            provided = data.get("provided")
            detail = f" (needed={needed}, provided={provided})" if needed or provided else ""
            raise Exception(f"Slack API returned error: {error_msg}{detail}")

        return data

    def _post_multipart(self, endpoint: str, data: dict = None, files: dict = None) -> dict:
        self._ensure_token()
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        # Don't use standard headers because httpx must set the Content-Type to
        # multipart/form-data with boundary
        multipart_headers = {"Authorization": f"Bearer {self.bot_token}"}

        response = httpx.post(
            url, headers=multipart_headers, data=data or {}, files=files or {}, timeout=60.0
        )
        response.raise_for_status()

        resp_data = response.json()
        if not resp_data.get("ok"):
            error_msg = resp_data.get("error", "Unknown Slack API error")
            needed = resp_data.get("needed")
            provided = resp_data.get("provided")
            detail = f" (needed={needed}, provided={provided})" if needed or provided else ""
            raise Exception(f"Slack API returned error: {error_msg}{detail}")

        return resp_data

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = httpx.get(url, headers=self.headers, params=params, timeout=30.0)
        response.raise_for_status()

        data = response.json()
        if not data.get("ok"):
            error_msg = data.get("error", "Unknown Slack API error")
            needed = data.get("needed")
            provided = data.get("provided")
            detail = f" (needed={needed}, provided={provided})" if needed or provided else ""
            raise Exception(f"Slack API returned error: {error_msg}{detail}")

        return data

    def _get_as_user(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request authenticated with the user token (xoxp-) instead of the bot token.

        Use this for Slack API endpoints that require user-scoped OAuth (e.g. search.messages).
        Raises ValueError (via _ensure_user_token) if no user token has been configured.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = httpx.get(url, headers=self.user_headers, params=params, timeout=30.0)
        response.raise_for_status()

        data = response.json()
        if not data.get("ok"):
            error_msg = data.get("error", "Unknown Slack API error")
            needed = data.get("needed")
            provided = data.get("provided")
            detail = f" (needed={needed}, provided={provided})" if needed or provided else ""
            raise Exception(f"Slack API returned error: {error_msg}{detail}")

        return data

    def register_tools(self, registry: ToolRegistry) -> None:
        """To be implemented by subclasses to register their specific tools."""
        pass
