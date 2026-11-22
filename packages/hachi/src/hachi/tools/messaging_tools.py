"""LLM-callable outbound messaging tools (Slack / Discord / WhatsApp / Telegram).

Let the agent proactively post to messaging platforms — e.g. "send the summary to #ops"
or "send this update to +447911123456 on WhatsApp". Credentials are resolved lazily from
the environment at call time (no boot-time prompts), or an explicit sender can be injected
(tests). Every failure is returned as a readable message rather than raised, so the agent
can recover or report it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from hachi.channels.discord import DiscordError, DiscordSender
from hachi.channels.slack import SlackError, SlackSender
from hachi.channels.whatsapp import WhatsAppError, WhatsAppSender
from hachi.core.idempotency import IdempotencyGuard, make_idempotency_key
from hachi.core.loop import ToolRegistry
from hachi.core.secret_scanner import redact_outbound

# ---------------------------------------------------------------------------
# Telegram sender (stdlib only — no external deps)
# ---------------------------------------------------------------------------

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _telegram_send(token: str, chat_id: str, text: str) -> dict[str, Any]:
    """POST text to a Telegram chat. Returns the API response dict."""
    url = _TELEGRAM_API.format(token=token, method="sendMessage")
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        data: dict[str, Any] = json.loads(resp.read().decode())
        return data


TelegramSender = Callable[[str, str, str], dict[str, Any]]


def _guard_outbound(text: str) -> tuple[str, str]:
    """Redact secrets from outbound text via the shared outbound-redaction policy.

    Returns ``(safe_text, note)`` — ``note`` is a non-empty suffix to append to the
    tool result when something was redacted, so the agent knows it happened. The opt-out
    (``HACHI_ALLOW_OUTBOUND_SECRETS=true``) is honored inside ``redact_outbound``.
    """
    safe, count = redact_outbound(text)
    note = f" ({count} secret(s) redacted before sending for your safety.)" if count else ""
    return safe, note


def _duplicate_result(platform: str, target_desc: str, prior: str | None) -> str:
    """Result string for a duplicate outbound send suppressed by the idempotency guard.

    ``prior`` is the earlier successful result when one exists (the message *was*
    delivered once — we replay that with a marker so the agent doesn't re-send), or
    ``None`` when a concurrent duplicate is still in flight.
    """
    if prior is not None:
        return f"{prior} [idempotent: identical message already sent moments ago — not resent]"
    return (
        f"Duplicate suppressed: an identical {platform} message to {target_desc} is already "
        "being sent (idempotency guard) — not sent again."
    )


def _make_send_slack(
    sender: SlackSender | None, guard: IdempotencyGuard
) -> Callable[[str, str], str]:
    def send_slack_message(text: str, channel: str = "") -> str:
        text, guard_note = _guard_outbound(text)
        active = sender or SlackSender.from_env()
        if not active.is_configured():
            return (
                "Slack is not configured. Set SLACK_BOT_TOKEN (and pass a channel) or "
                "SLACK_WEBHOOK_URL, then try again."
            )
        key = make_idempotency_key("send_slack_message", channel or "<default>", text)
        is_dup, prior = guard.begin(key)
        if is_dup:
            return _duplicate_result("Slack", channel or "the default channel", prior)
        try:
            result = active.send(text=text, channel=channel)
        except SlackError as exc:
            guard.abort(key)
            return f"Slack send failed: {exc}"
        except Exception as exc:
            guard.abort(key)
            return f"Slack send failed: {exc}"
        final = f"Sent message to Slack ({result.get('target')})." + guard_note
        guard.finish(key, final)
        return final

    return send_slack_message


def _make_send_discord(
    sender: DiscordSender | None, guard: IdempotencyGuard
) -> Callable[[str, str], str]:
    def send_discord_message(content: str, channel: str = "") -> str:
        content, guard_note = _guard_outbound(content)
        active = sender or DiscordSender.from_env()
        if not active.is_configured():
            return (
                "Discord is not configured. Set DISCORD_WEBHOOK_URL or DISCORD_BOT_TOKEN "
                "(and pass a channel id), then try again."
            )
        key = make_idempotency_key("send_discord_message", channel or "<default>", content)
        is_dup, prior = guard.begin(key)
        if is_dup:
            return _duplicate_result("Discord", channel or "the default channel", prior)
        try:
            result = active.send(content=content, channel=channel)
        except DiscordError as exc:
            guard.abort(key)
            return f"Discord send failed: {exc}"
        except Exception as exc:
            guard.abort(key)
            return f"Discord send failed: {exc}"
        final = f"Sent message to Discord ({result.get('target')})." + guard_note
        guard.finish(key, final)
        return final

    return send_discord_message


SEND_SLACK_MESSAGE_SCHEMA = {
    "name": "send_slack_message",
    "description": (
        "Post a message to Slack. Use this to proactively notify a channel or user — e.g. send a "
        "summary, alert, or reply. With a bot token you must pass a `channel` (like '#ops' or a "
        "channel id); with an incoming webhook the channel is fixed and `channel` is ignored."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The message text to post."},
            "channel": {
                "type": "string",
                "description": "Target channel ('#name' or id). Required with a bot token.",
            },
        },
        "required": ["text"],
    },
}

SEND_DISCORD_MESSAGE_SCHEMA = {
    "name": "send_discord_message",
    "description": (
        "Post a message to Discord. Use this to proactively notify a channel — e.g. send a "
        "summary, alert, or reply. With a webhook the channel is fixed; with a bot token pass the "
        "target `channel` id. Messages longer than 2000 characters are truncated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The message content to post."},
            "channel": {
                "type": "string",
                "description": "Channel id; required for bot tokens, ignored for webhooks.",
            },
        },
        "required": ["content"],
    },
}


def _make_send_whatsapp(
    sender: WhatsAppSender | None, guard: IdempotencyGuard
) -> Callable[[str, str], str]:
    def send_whatsapp_message(text: str, to: str = "") -> str:
        text, guard_note = _guard_outbound(text)
        active = sender or WhatsAppSender.from_env()
        if not active.is_configured():
            return (
                "WhatsApp is not configured. Set META_WHATSAPP_TOKEN + META_WHATSAPP_PHONE_ID "
                "(Meta Cloud API), or TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + "
                "TWILIO_WHATSAPP_FROM (Twilio), then try again."
            )
        if not to:
            return "A recipient phone number (`to`) is required to send a WhatsApp message."
        key = make_idempotency_key("send_whatsapp_message", to, text)
        is_dup, prior = guard.begin(key)
        if is_dup:
            return _duplicate_result("WhatsApp", to, prior)
        try:
            result = active.send(to=to, text=text)
        except WhatsAppError as exc:
            guard.abort(key)
            return f"WhatsApp send failed: {exc}"
        except Exception as exc:
            guard.abort(key)
            return f"WhatsApp send failed: {exc}"
        provider = result.get("provider")
        final = f"Sent WhatsApp message to {result.get('to')} via {provider}." + guard_note
        guard.finish(key, final)
        return final

    return send_whatsapp_message


SEND_WHATSAPP_MESSAGE_SCHEMA = {
    "name": "send_whatsapp_message",
    "description": (
        "Send a WhatsApp message to a phone number. Use this to proactively notify someone "
        "on WhatsApp — e.g. send a summary, reminder, or alert. Requires a recipient phone "
        "number in E.164 format (e.g. '+447911123456'). Supports Meta Cloud API or Twilio."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The message text to send."},
            "to": {
                "type": "string",
                "description": "Recipient phone number in E.164 format (e.g. '+447911123456').",
            },
        },
        "required": ["text", "to"],
    },
}


def _make_send_telegram(
    sender: TelegramSender | None, guard: IdempotencyGuard
) -> Callable[[str, str], str]:
    def send_telegram_message(text: str, chat_id: str = "") -> str:
        text, guard_note = _guard_outbound(text)
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        target = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        if not token:
            return (
                "Telegram is not configured. Set TELEGRAM_BOT_TOKEN and optionally "
                "TELEGRAM_CHAT_ID (or pass chat_id), then try again."
            )
        if not target:
            return "No Telegram chat_id provided. Pass `chat_id` or set TELEGRAM_CHAT_ID."
        key = make_idempotency_key("send_telegram_message", target, text)
        is_dup, prior = guard.begin(key)
        if is_dup:
            return _duplicate_result("Telegram", f"chat {target}", prior)
        fn = sender or _telegram_send
        try:
            result = fn(token, target, text)
        except urllib.error.HTTPError as exc:
            guard.abort(key)
            return f"Telegram send failed: HTTP {exc.code} — {exc.reason}"
        except Exception as exc:
            guard.abort(key)
            return f"Telegram send failed: {exc}"
        if not result.get("ok"):
            guard.abort(key)
            description = result.get("description", "unknown error")
            return f"Telegram send failed: {description}"
        final = f"Sent Telegram message to chat {target}." + guard_note
        guard.finish(key, final)
        return final

    return send_telegram_message


SEND_TELEGRAM_MESSAGE_SCHEMA = {
    "name": "send_telegram_message",
    "description": (
        "Send a message to a Telegram chat via a bot. Use this to proactively notify "
        "the user or a group on Telegram — e.g. send a summary, reminder, or alert. "
        "Requires TELEGRAM_BOT_TOKEN. Pass `chat_id` or set TELEGRAM_CHAT_ID."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The message text to send."},
            "chat_id": {
                "type": "string",
                "description": (
                    "Target chat id (user, group, or channel). Falls back to "
                    "TELEGRAM_CHAT_ID env var when omitted."
                ),
            },
        },
        "required": ["text"],
    },
}


def register_messaging_tools(
    registry: ToolRegistry,
    *,
    slack_sender: SlackSender | None = None,
    discord_sender: DiscordSender | None = None,
    whatsapp_sender: WhatsAppSender | None = None,
    telegram_sender: TelegramSender | None = None,
    guard: IdempotencyGuard | None = None,
) -> None:
    """Register outbound Slack/Discord/WhatsApp/Telegram tools.

    Senders are optional — when omitted, credentials are resolved from the environment at
    call time, so the tools register cleanly even before any token is configured (they return
    a friendly "not configured" message until then). Tests inject fake senders.

    ``guard`` is a shared :class:`~hachi.core.idempotency.IdempotencyGuard` that suppresses
    duplicate *successful* sends inside a short window — defending against an LLM retry,
    tool-pool re-dispatch, or turn-resume re-sending the same message. One guard is created
    per call by default, so it is scoped to the session whose tool registry this is (every
    in-session retry path reuses these same closures); injecting a guard is for tests.
    """
    # Explicit None check, NOT ``guard or ...``: IdempotencyGuard defines __len__, so an
    # empty (len 0) injected guard is falsy and ``or`` would silently discard it.
    active_guard = guard if guard is not None else IdempotencyGuard()
    registry.register(SEND_SLACK_MESSAGE_SCHEMA, _make_send_slack(slack_sender, active_guard))
    registry.register(SEND_DISCORD_MESSAGE_SCHEMA, _make_send_discord(discord_sender, active_guard))
    registry.register(
        SEND_WHATSAPP_MESSAGE_SCHEMA, _make_send_whatsapp(whatsapp_sender, active_guard)
    )
    registry.register(
        SEND_TELEGRAM_MESSAGE_SCHEMA, _make_send_telegram(telegram_sender, active_guard)
    )
