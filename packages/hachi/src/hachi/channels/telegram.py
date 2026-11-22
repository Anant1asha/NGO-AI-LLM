"""Telegram reference adapter.

Implements the :class:`~hachi.channels.base.ChannelAdapter` contract over
Telegram's Bot API using only the standard library (long-polling ``getUpdates``
+ ``sendMessage``). Running it live needs a bot token from @BotFather, but the
update-parsing logic is a pure function so it is unit-tested without a network.

Optional command registry
-------------------------
Pass a :class:`~hachi.channels.telegram_commands.TelegramCommandRegistry`
as ``command_registry`` to enable auto-skill creation for Telegram ``/commands``.
When present, ``poll_once`` runs every parsed message batch through the registry
before returning it: new commands get a stub .og skill written to disk and are
annotated for the agent.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import TYPE_CHECKING, Any

from hachi.channels.base import ChannelAdapter, InboundMessage, OutboundMessage

if TYPE_CHECKING:
    from hachi.channels.telegram_commands import TelegramCommandRegistry

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
# Safe URL template for logging — token placeholder never filled with the real value.
_API_LOG = "https://api.telegram.org/bot<redacted>/{method}"


def parse_updates(updates: list[dict[str, Any]]) -> list[InboundMessage]:
    """Convert raw Telegram ``getUpdates`` results into InboundMessages.

    Ignores non-text updates (stickers, edits without text, etc.). Pure — no I/O.
    """
    messages: list[InboundMessage] = []
    for update in updates:
        payload = update.get("message") or update.get("edited_message")
        if not isinstance(payload, dict):
            continue
        text = payload.get("text")
        if not text:
            continue
        chat = payload.get("chat", {}) or {}
        sender = payload.get("from", {}) or {}
        messages.append(
            InboundMessage(
                channel="telegram",
                sender_id=str(chat.get("id", "")),
                text=str(text),
                sender_name=str(sender.get("username") or sender.get("first_name") or ""),
            )
        )
    return messages


def latest_offset(updates: list[dict[str, Any]], current: int) -> int:
    """Return the next ``getUpdates`` offset given a batch (pure)."""
    if not updates:
        return current
    return max(int(u.get("update_id", current - 1)) for u in updates) + 1


class TelegramAdapter(ChannelAdapter):
    """Long-polling Telegram bot transport."""

    name = "telegram"

    def __init__(
        self,
        token: str,
        *,
        timeout: int = 30,
        command_registry: TelegramCommandRegistry | None = None,
    ):
        if not token:
            raise ValueError("Telegram bot token is required")
        self._token = token
        self._timeout = timeout
        self._offset = 0
        self._command_registry = command_registry

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        # MED-005: build the real URL with the token only for the actual request;
        # never log the full URL — the token embedded in the path would be captured
        # by proxies, log aggregators, and DEBUG-level log consumers.
        url = _API.format(token=self._token, method=method)
        logger.debug("Telegram API call: %s", _API_LOG.format(method=method))
        data = json.dumps(params).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self._timeout + 5) as response:  # noqa: S310
            result = json.loads(response.read().decode("utf-8"))
        return result if isinstance(result, dict) else {}

    def poll_once(self) -> list[InboundMessage]:
        result = self._call("getUpdates", {"offset": self._offset, "timeout": self._timeout})
        if not result.get("ok", True):
            logger.warning(
                "Telegram getUpdates returned ok=false: %s", result.get("description", result)
            )
            return []
        updates = result.get("result", []) or []
        self._offset = latest_offset(updates, self._offset)
        messages = parse_updates(updates)
        if self._command_registry is not None and messages:
            messages = self._command_registry.intercept_messages(messages)
        return messages

    def send(self, message: OutboundMessage) -> None:
        _MAX = 4096
        text = message.text
        for i in range(0, max(1, len(text)), _MAX):
            self._call("sendMessage", {"chat_id": message.recipient_id, "text": text[i : i + _MAX]})
