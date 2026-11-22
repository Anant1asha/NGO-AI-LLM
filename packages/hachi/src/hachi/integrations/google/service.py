"""
Google Service Interface

Defines the strict base class contract for all Google Workspace plugins.
Every module (Gmail, Drive, Docs) must inherit from this class to ensure
seamless mounting into the LLM ToolRegistry.
"""

from abc import ABC, abstractmethod

from hachi.core.loop import ToolRegistry
from hachi.integrations.google.client import GoogleHTTPClient


class GoogleService(ABC):
    """
    Abstract base class for a Google Workspace integration module.
    """

    def __init__(self, client: GoogleHTTPClient):
        """
        Injects the shared HTTP client so all services share the same OAuth token.
        """
        self.client = client

    @property
    @abstractmethod
    def required_scopes(self) -> list[str]:
        """
        Return a list of Google OAuth scopes required by this specific service.
        Example: ["https://www.googleapis.com/auth/gmail.modify"]
        """
        pass

    @abstractmethod
    def register_tools(self, registry: ToolRegistry) -> None:
        """
        Mount the tools provided by this service into the agent's brain.

        Args:
            registry: The central ToolRegistry of the agent.
        """
        pass

    def require_approval(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Gate a destructive/outbound action behind the session approver.

        This is the single call-site all destructive Google leaf tools should use.
        Leaf tools call this and, when ``ok is False``, return a user-facing
        cancellation string without touching the Google API.

        Canonical *action* names:
            ``send_email``, ``delete_event``, ``delete_task``,
            ``delete_contact``, ``trash_file``, ``share_file``.

        Args:
            action:  Canonical action name.
            summary: Short human-readable description of what would happen.
            detail:  Optional extended context for the approval UI.

        Returns:
            ``(True, reason)`` if approved; ``(False, reason)`` if denied.
        """
        return self.client.require_approval(action, summary, detail)
