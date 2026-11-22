"""
Slack Chat Service
Handles reading from channels and sending messages.
"""

import time

from hachi.core.loop import ToolRegistry
from hachi.core.secret_scanner import redact_outbound
from hachi.integrations.slack.service import SlackService


class SlackChat(SlackService):
    @staticmethod
    def _guard_outbound(text: str) -> tuple[str, str]:
        safe, count = redact_outbound(text)
        note = f" ({count} secret(s) redacted before sending for your safety.)" if count else ""
        return safe, note

    def send_message(self, channel_id: str, text: str) -> str:
        """
        Sends a message to a Slack channel or user.
        """
        text, guard_note = self._guard_outbound(text)
        payload = {"channel": channel_id, "text": text}

        try:
            res = self._post("/chat.postMessage", json_data=payload)
            ts = res.get("ts")
            return f"Successfully sent message to {channel_id} at timestamp {ts}.{guard_note}"
        except Exception as e:
            return f"Failed to send Slack message: {str(e)}"

    def upload_file(self, channel_id: str, file_path: str, initial_comment: str = "") -> str:
        """
        Uploads a local file to a Slack channel using the v2 upload API.
        """
        import os
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"

        if initial_comment:
            initial_comment, _note = self._guard_outbound(initial_comment)

        try:
            # Step 1: Get upload URL
            file_size = os.path.getsize(path)
            get_url_params = {"filename": path.name, "length": file_size}
            res_url = self._get("/files.getUploadURLExternal", params=get_url_params)
            upload_url = res_url.get("upload_url")
            file_id = res_url.get("file_id")

            # Step 2: Upload file to the URL
            import httpx

            with open(path, "rb") as f:
                # Direct post of file bytes, slack requires a standard post not multipart
                # for this URL
                upload_res = httpx.post(
                    upload_url,
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    data=f.read(),
                    timeout=60.0,
                )
                upload_res.raise_for_status()

            # Step 3: Complete upload
            complete_payload = {
                "files": [{"id": file_id, "title": path.name}],
                "channel_id": channel_id,
            }
            if initial_comment:
                complete_payload["initial_comment"] = initial_comment

            self._post("/files.completeUploadExternal", json_data=complete_payload)
            return f"Successfully uploaded {path.name} to {channel_id}."

        except Exception as e:
            return f"Failed to upload file to Slack: {str(e)}"

    def read_channel(self, channel_id: str, limit: int = 20) -> str:
        """
        Reads recent messages from a Slack channel.
        """
        params = {"channel": channel_id, "limit": limit}

        try:
            res = self._get("/conversations.history", params=params)
            messages = res.get("messages", [])

            if not messages:
                return f"No recent messages found in {channel_id}."

            formatted = []
            for msg in reversed(messages):  # Reverse to get chronological order
                user = msg.get("user", "Unknown User")
                text = msg.get("text", "")
                ts = msg.get("ts", "")

                # Format timestamp to readable string
                if ts:
                    readable_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
                else:
                    readable_time = "Unknown Time"

                formatted.append(f"[{readable_time}] {user}: {text}")

            return "\n".join(formatted)
        except Exception as e:
            return f"Failed to read Slack channel: {str(e)}"

    def read_thread(self, channel_id: str, thread_ts: str) -> str:
        """
        Reads all messages in a specific thread.
        """
        params = {"channel": channel_id, "ts": thread_ts}

        try:
            res = self._get("/conversations.replies", params=params)
            messages = res.get("messages", [])

            if not messages:
                return f"No messages found in thread {thread_ts}."

            formatted = []
            for msg in messages:
                user = msg.get("user", "Unknown User")
                text = msg.get("text", "")
                ts = msg.get("ts", "")

                if ts:
                    readable_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
                else:
                    readable_time = "Unknown Time"

                formatted.append(f"[{readable_time}] {user}: {text}")

            return "\n".join(formatted)
        except Exception as e:
            return f"Failed to read Slack thread: {str(e)}"

    def add_reaction(self, channel_id: str, timestamp: str, emoji_name: str) -> str:
        """
        Adds an emoji reaction to a message.
        """
        payload = {"channel": channel_id, "timestamp": timestamp, "name": emoji_name.strip(":")}

        try:
            self._post("/reactions.add", json_data=payload)
            return f"Successfully added reaction :{emoji_name}: to message {timestamp}."
        except Exception as e:
            return f"Failed to add reaction: {str(e)}"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            {
                "name": "slack_send_message",
                "description": "Send a text message to a specific Slack channel or Direct Message.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The ID of the Slack channel (starts with C, G, or D) "
                            "or the @username.",
                        },
                        "text": {"type": "string", "description": "The message text to send."},
                    },
                    "required": ["channel_id", "text"],
                },
            },
            self.send_message,
        )

        registry.register(
            {
                "name": "slack_upload_file",
                "description": "Upload a local binary file (e.g. PDF, Image, Text) to a Slack "
                "channel.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The ID of the Slack channel.",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the local file to upload.",
                        },
                        "initial_comment": {
                            "type": "string",
                            "description": "Optional text message to accompany the file.",
                        },
                    },
                    "required": ["channel_id", "file_path"],
                },
            },
            self.upload_file,
        )

        registry.register(
            {
                "name": "slack_read_channel",
                "description": "Read the most recent messages from a Slack channel to catch up "
                "on conversations.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The ID of the Slack channel (starts with C).",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of messages to retrieve (default 20).",
                        },
                    },
                    "required": ["channel_id"],
                },
            },
            self.read_channel,
        )

        registry.register(
            {
                "name": "slack_read_thread",
                "description": "Read all replies in a specific message thread.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The ID of the Slack channel.",
                        },
                        "thread_ts": {
                            "type": "string",
                            "description": "The timestamp (ts) of the parent message.",
                        },
                    },
                    "required": ["channel_id", "thread_ts"],
                },
            },
            self.read_thread,
        )

        registry.register(
            {
                "name": "slack_add_reaction",
                "description": "Add an emoji reaction to a specific message.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The ID of the Slack channel.",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "The timestamp (ts) of the message to react to.",
                        },
                        "emoji_name": {
                            "type": "string",
                            "description": "The name of the emoji without colons "
                            "(e.g., 'thumbsup', 'robot_face').",
                        },
                    },
                    "required": ["channel_id", "timestamp", "emoji_name"],
                },
            },
            self.add_reaction,
        )
