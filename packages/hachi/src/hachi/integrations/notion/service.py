"""
Base Notion Service
Provides the core HTTP client wrapper and authentication headers for the Notion API.
"""

import httpx

from hachi.core.loop import ToolRegistry


class NotionService:
    """
    Base service for Notion API integrations.
    Handles authentication and provides a pre-configured HTTP client.
    """

    BASE_URL = "https://api.notion.com/v1"
    # 2025-09-03 dropped POST /v1/databases/{id}/query; pin to a version that still supports it.
    NOTION_VERSION = "2022-06-28"

    def __init__(self):
        from hachi.core.credential_vault import CredentialVault

        self._vault = CredentialVault()
        # Avoid interactive stdin prompts during TUI boot. We resolve lazily per call.
        # get_token raises ValueError when the key is absent; catch so a missing Notion
        # credential doesn't abort the entire tool-registry mount.
        try:
            self.api_key = self._vault.get_token("notion_api_key", prompt_if_missing=False)
        except ValueError:
            self.api_key = None

    def _ensure_api_key(self) -> None:
        if self.api_key:
            return
        try:
            self.api_key = self._vault.get_token("notion_api_key", prompt_if_missing=False)
        except ValueError:
            pass
        if not self.api_key:
            raise ValueError("Missing Notion API key. Run: hachi secrets --set notion_api_key")

    @property
    def headers(self) -> dict:
        """Returns the required headers for Notion API requests."""
        self._ensure_api_key()
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """Raise with the Notion API error body so the agent gets the actionable reason."""
        if response.is_success:
            return
        detail = ""
        try:
            body = response.json()
            code = body.get("code", "")
            message = body.get("message", "")
            detail = f"{code}: {message}" if code else message
        except Exception:
            detail = response.text.strip()
        raise RuntimeError(
            f"Notion API error {response.status_code}" + (f" — {detail}" if detail else "")
        )

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = httpx.get(url, headers=self.headers, params=params, timeout=30.0)
        self._raise_for_status(response)
        return response.json()

    def _post(self, endpoint: str, json_data: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = httpx.post(url, headers=self.headers, json=json_data or {}, timeout=30.0)
        self._raise_for_status(response)
        return response.json()

    def _patch(self, endpoint: str, json_data: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = httpx.patch(url, headers=self.headers, json=json_data or {}, timeout=30.0)
        self._raise_for_status(response)
        return response.json()

    def register_tools(self, registry: ToolRegistry) -> None:
        """To be implemented by subclasses to register their specific tools."""
        pass
