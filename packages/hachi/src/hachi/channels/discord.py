"""Discord outbound sender + adapter.

Posts messages to Discord either via a Webhook URL (simplest; pre-bound to one channel)
or a Bot token (``POST /channels/{id}/messages``, can target any channel the bot can see).
Request building is pure and unit-tested; the HTTP POST goes through an injectable
``poster`` so tests run offline. Webhook URLs are validated through ``net_guard`` (SSRF).

Credentials are read from the environment at call time (never at import/boot):
``DISCORD_WEBHOOK_URL`` and/or ``DISCORD_BOT_TOKEN``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from hachi.channels.base import ChannelAdapter, InboundMessage, OutboundMessage
from hachi.core.net_guard import validate_outbound_url

# (url, json_payload, headers) -> (status_code, response_text)
Poster = Callable[[str, dict[str, Any], dict[str, str]], tuple[int, str]]

_BOT_API = "https://discord.com/api/v10/channels/{channel_id}/messages"
# Discord rejects messages longer than this; truncate so a long agent reply still posts.
MAX_CONTENT = 2000


class DiscordError(RuntimeError):
    """Raised when a Discord send is misconfigured or rejected by Discord."""


def _default_poster(url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[int, str]:
    import httpx

    with httpx.Client(timeout=15.0, follow_redirects=False) as client:
        resp = client.post(url, json=payload, headers=headers)
        return resp.status_code, resp.text


def _clamp(content: str) -> str:
    return content if len(content) <= MAX_CONTENT else content[: MAX_CONTENT - 1] + "…"


def build_webhook_request(
    webhook_url: str, content: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Build the (url, payload, headers) for a webhook post (pure)."""
    return webhook_url, {"content": _clamp(content)}, {"Content-Type": "application/json"}


def build_bot_request(
    token: str, channel_id: str, content: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Build the (url, payload, headers) for a bot-token channel message (pure)."""
    if not channel_id:
        raise DiscordError("a channel id is required with a bot token")
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }
    return _BOT_API.format(channel_id=channel_id), {"content": _clamp(content)}, headers


class DiscordSender:
    """Sends messages to Discord via webhook (preferred) or bot token."""

    def __init__(
        self,
        *,
        webhook_url: str | None = None,
        bot_token: str | None = None,
        poster: Poster | None = None,
        allow_private: bool = False,
    ) -> None:
        self._webhook_url = webhook_url or None
        self._bot_token = bot_token or None
        self._poster = poster or _default_poster
        self._allow_private = allow_private

    @classmethod
    def from_env(cls, poster: Poster | None = None) -> DiscordSender:
        return cls(
            webhook_url=os.environ.get("DISCORD_WEBHOOK_URL"),
            bot_token=os.environ.get("DISCORD_BOT_TOKEN"),
            poster=poster,
            allow_private=os.environ.get("HACHI_REST_ALLOW_PRIVATE", "").strip().lower()
            in {"1", "true", "yes"},
        )

    def is_configured(self) -> bool:
        return bool(self._webhook_url or self._bot_token)

    def send(self, content: str, channel: str = "") -> dict[str, Any]:
        """Post ``content`` to Discord. Returns a status dict; raises DiscordError on failure."""
        if not content.strip():
            raise DiscordError("message content is empty")

        if self._webhook_url:
            ok, reason = validate_outbound_url(self._webhook_url, allow_private=self._allow_private)
            if not ok:
                raise DiscordError(f"blocked webhook URL: {reason}")
            url, payload, headers = build_webhook_request(self._webhook_url, content)
            target = "webhook"
        elif self._bot_token:
            url, payload, headers = build_bot_request(self._bot_token, channel, content)
            target = channel
        else:
            raise DiscordError(
                "Discord is not configured (set DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN)"
            )

        status, body = self._poster(url, payload, headers)
        # Webhook success = 204 No Content; bot message create = 200/201.
        if status not in (200, 201, 204):
            raise DiscordError(f"Discord returned HTTP {status}: {body}")

        return {"status": "sent", "channel": "discord", "target": target}


class DiscordAdapter(ChannelAdapter):
    """Send-only Discord transport (inbound arrives via gateway webhook, not polling)."""

    name = "discord"

    def __init__(self, sender: DiscordSender) -> None:
        self._sender = sender

    def send(self, message: OutboundMessage) -> None:
        self._sender.send(content=message.text, channel=message.recipient_id)

    def poll_once(self) -> list[InboundMessage]:
        return []  # Discord inbound is delivered to /channels/discord/inbound, not polled.
