"""
Slack Workspace Service
Handles searching, listing channels, and other workspace-level operations.
"""

import time

from hachi.core.loop import ToolRegistry
from hachi.integrations.slack.service import SlackService


class SlackWorkspace(SlackService):
    def search_messages(self, query: str, limit: int = 10) -> str:
        """
        Searches for messages across the entire Slack workspace.

        Requires a user OAuth token (``xoxp-``) with the ``search:read`` scope — bot tokens
        (``xoxb-``) cannot call ``search.messages``.  Configure the user token via:
        ``hachi secrets --set slack_user_token``
        """
        params = {"query": query, "count": limit}

        try:
            res = self._get_as_user("/search.messages", params=params)
            messages = res.get("messages", {}).get("matches", [])

            if not messages:
                return f"No messages found matching '{query}'."

            formatted = []
            for msg in messages:
                channel = msg.get("channel", {}).get("name", "Unknown Channel")
                user = msg.get("username", "Unknown User")
                text = msg.get("text", "")
                ts = msg.get("ts", "")

                if ts:
                    readable_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
                else:
                    readable_time = "Unknown Time"

                formatted.append(f"[{readable_time}] [#{channel}] {user}: {text}")

            return "\n\n".join(formatted)
        except Exception as e:
            return f"Failed to search Slack workspace: {str(e)}"

    def list_channels(self, limit: int = 50) -> str:
        """
        Lists available public and private channels the bot has access to.
        """
        params = {
            "types": "public_channel,private_channel",
            "exclude_archived": "true",
            "limit": limit,
        }

        try:
            res = self._get("/conversations.list", params=params)
            channels = res.get("channels", [])

            if not channels:
                return "No channels found or bot doesn't have access to any channels."

            formatted = []
            for c in channels:
                name = c.get("name", "Unknown")
                c_id = c.get("id", "Unknown")
                is_private = c.get("is_private", False)
                type_str = "Private" if is_private else "Public"

                formatted.append(f"[{type_str}] #{name} (ID: {c_id})")

            return "\n".join(formatted)
        except Exception as e:
            return f"Failed to list Slack channels: {str(e)}"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            {
                "name": "slack_list_channels",
                "description": "List all public and private channels the bot has access to. "
                "Use this to find the correct channel_id.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max number of channels to list (default 50).",
                        }
                    },
                },
            },
            self.list_channels,
        )

        registry.register(
            {
                "name": "slack_search_messages",
                "description": "Search for specific messages across the entire Slack workspace. "
                "Note: This may require user token scopes depending on workspace settings.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query/keywords."},
                        "limit": {
                            "type": "integer",
                            "description": "Max number of results (default 10).",
                        },
                    },
                    "required": ["query"],
                },
            },
            self.search_messages,
        )
