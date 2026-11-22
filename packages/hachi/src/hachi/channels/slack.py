"""Slack outbound sender + adapter.

Posts messages to Slack either via a Bot token (``chat.postMessage``, can target any
channel the bot is in) or an Incoming Webhook URL (single pre-bound channel). The
request-building logic is pure and unit-tested; the actual HTTP POST goes through an
injectable ``poster`` so tests run without a network. Webhook URLs are validated through
``net_guard`` (SSRF mitigation) before any request is made.

Credentials are read from the environment at call time (never at import/boot):
``SLACK_BOT_TOKEN`` and/or ``SLACK_WEBHOOK_URL``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from hachi.channels.base import ChannelAdapter, InboundMessage, OutboundMessage
from hachi.core.net_guard import validate_outbound_url

# (url, json_payload, headers) -> (status_code, response_text)
Poster = Callable[[str, dict[str, Any], dict[str, str]], tuple[int, str]]

_POST_MESSAGE_API = "https://slack.com/api/chat.postMessage"


class SlackError(RuntimeError):
    """Raised when a Slack send is misconfigured or rejected by Slack."""


def _default_poster(url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[int, str]:
    import httpx

    with httpx.Client(timeout=15.0, follow_redirects=False) as client:
        resp = client.post(url, json=payload, headers=headers)
        return resp.status_code, resp.text


def build_bot_request(
    token: str, channel: str, text: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Build the (url, payload, headers) for a bot-token ``chat.postMessage`` (pure)."""
    if not channel:
        raise SlackError("a channel (e.g. '#general' or a channel id) is required with a bot token")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    return _POST_MESSAGE_API, {"channel": channel, "text": text}, headers


def build_webhook_request(
    webhook_url: str, text: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Build the (url, payload, headers) for an incoming-webhook post (pure)."""
    return webhook_url, {"text": text}, {"Content-Type": "application/json"}


class SlackSender:
    """Sends messages to Slack via bot token (preferred) or incoming webhook."""

    def __init__(
        self,
        *,
        bot_token: str | None = None,
        webhook_url: str | None = None,
        poster: Poster | None = None,
        allow_private: bool = False,
    ) -> None:
        self._bot_token = bot_token or None
        self._webhook_url = webhook_url or None
        self._poster = poster or _default_poster
        self._allow_private = allow_private

    @classmethod
    def from_env(cls, poster: Poster | None = None) -> SlackSender:
        return cls(
            bot_token=os.environ.get("SLACK_BOT_TOKEN"),
            webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
            poster=poster,
            allow_private=os.environ.get("HACHI_REST_ALLOW_PRIVATE", "").strip().lower()
            in {"1", "true", "yes"},
        )

    def is_configured(self) -> bool:
        return bool(self._bot_token or self._webhook_url)

    def send(self, text: str, channel: str = "") -> dict[str, Any]:
        """Post ``text`` to Slack. Returns a small status dict; raises SlackError on failure."""
        if not text.strip():
            raise SlackError("message text is empty")

        if self._bot_token:
            url, payload, headers = build_bot_request(self._bot_token, channel, text)
            target = channel
        elif self._webhook_url:
            ok, reason = validate_outbound_url(self._webhook_url, allow_private=self._allow_private)
            if not ok:
                raise SlackError(f"blocked webhook URL: {reason}")
            url, payload, headers = build_webhook_request(self._webhook_url, text)
            target = "webhook"
        else:
            raise SlackError("Slack is not configured (set SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL)")

        status, body = self._poster(url, payload, headers)

        # Bot API returns HTTP 200 with {"ok": false, "error": ...} on logical failures;
        # incoming webhooks return HTTP 200 and the body "ok".
        if self._bot_token:
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {}
            if status != 200 or not parsed.get("ok", False):
                raise SlackError(
                    f"Slack rejected the message: {parsed.get('error') or body or status}"
                )
        elif status != 200:
            raise SlackError(f"Slack webhook returned HTTP {status}: {body}")

        return {"status": "sent", "channel": "slack", "target": target}


class SlackAdapter(ChannelAdapter):
    """Send-only Slack transport (inbound arrives via the Events API webhook, not polling)."""

    name = "slack"

    def __init__(self, sender: SlackSender) -> None:
        self._sender = sender

    def send(self, message: OutboundMessage) -> None:
        self._sender.send(text=message.text, channel=message.recipient_id)

    def poll_once(self) -> list[InboundMessage]:
        return []  # Slack inbound is delivered to /channels/slack/inbound, not polled.
