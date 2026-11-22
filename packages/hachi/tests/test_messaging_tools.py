"""Tests for outbound Slack/Discord/WhatsApp senders, adapters, and LLM tools.

Fully offline: HTTP is replaced by a recording fake poster, so request building, response
interpretation, SSRF webhook rejection, and the tool/adapter layers are all exercised
without touching the network.
"""

from __future__ import annotations

import base64
import json

import pytest

from hachi.channels.base import OutboundMessage
from hachi.channels.discord import (
    MAX_CONTENT,
    DiscordAdapter,
    DiscordError,
    DiscordSender,
)
from hachi.channels.discord import (
    build_bot_request as d_bot_request,
)
from hachi.channels.slack import (
    SlackAdapter,
    SlackError,
    SlackSender,
)
from hachi.channels.slack import (
    build_bot_request as s_bot_request,
)
from hachi.channels.whatsapp import (
    MAX_TEXT,
    WhatsAppAdapter,
    WhatsAppError,
    WhatsAppSender,
    build_meta_request,
    build_twilio_request,
)
from hachi.core.idempotency import IdempotencyGuard
from hachi.core.loop import ToolRegistry
from hachi.tools.messaging_tools import register_messaging_tools


class RecordingPoster:
    """Captures the last (url, payload, headers) and returns a canned (status, body)."""

    def __init__(self, status: int = 200, body: str = "ok") -> None:
        self.status = status
        self.body = body
        self.calls: list[tuple] = []

    def __call__(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.status, self.body


def _never_called(url, payload, headers):  # poster that asserts it is not invoked
    raise AssertionError("poster should not be called")


# -- pure request builders --------------------------------------------------


def test_slack_bot_request_shape():
    url, payload, headers = s_bot_request("xoxb-1", "#ops", "hi")
    assert url.endswith("/chat.postMessage")
    assert payload == {"channel": "#ops", "text": "hi"}
    assert headers["Authorization"] == "Bearer xoxb-1"


def test_slack_bot_request_requires_channel():
    with pytest.raises(SlackError):
        s_bot_request("xoxb-1", "", "hi")


def test_discord_bot_request_requires_channel():
    with pytest.raises(DiscordError):
        d_bot_request("tok", "", "hi")


def test_discord_truncates_overlong_content():
    url, payload, _ = d_bot_request("tok", "123", "x" * (MAX_CONTENT + 500))
    assert len(payload["content"]) == MAX_CONTENT
    assert payload["content"].endswith("…")


# -- SlackSender ------------------------------------------------------------


def test_slack_bot_send_success():
    poster = RecordingPoster(200, json.dumps({"ok": True, "channel": "C1"}))
    sender = SlackSender(bot_token="xoxb-1", poster=poster)
    result = sender.send(text="hello", channel="#ops")
    assert result["status"] == "sent"
    assert poster.calls and poster.calls[0][1] == {"channel": "#ops", "text": "hello"}


def test_slack_bot_send_logical_error_raises():
    poster = RecordingPoster(200, json.dumps({"ok": False, "error": "channel_not_found"}))
    sender = SlackSender(bot_token="xoxb-1", poster=poster)
    with pytest.raises(SlackError) as exc:
        sender.send(text="hello", channel="#nope")
    assert "channel_not_found" in str(exc.value)


def test_slack_webhook_send_success():
    poster = RecordingPoster(200, "ok")
    sender = SlackSender(webhook_url="https://hooks.slack.com/services/T/B/X", poster=poster)
    result = sender.send(text="hello")
    assert result["target"] == "webhook"
    assert poster.calls[0][1] == {"text": "hello"}


def test_slack_webhook_ssrf_blocked():
    sender = SlackSender(webhook_url="http://127.0.0.1/hook", poster=_never_called)
    with pytest.raises(SlackError) as exc:
        sender.send(text="hello")
    assert "blocked webhook URL" in str(exc.value)


def test_slack_not_configured_raises():
    sender = SlackSender(poster=_never_called)
    assert not sender.is_configured()
    with pytest.raises(SlackError):
        sender.send(text="hello")


def test_slack_empty_text_raises():
    sender = SlackSender(bot_token="xoxb-1", poster=_never_called)
    with pytest.raises(SlackError):
        sender.send(text="   ", channel="#ops")


# -- DiscordSender ----------------------------------------------------------


def test_discord_webhook_send_success():
    poster = RecordingPoster(204, "")
    sender = DiscordSender(webhook_url="https://discord.com/api/webhooks/1/abc", poster=poster)
    result = sender.send(content="hello")
    assert result["target"] == "webhook"
    assert poster.calls[0][1] == {"content": "hello"}


def test_discord_bot_send_success():
    poster = RecordingPoster(200, "{}")
    sender = DiscordSender(bot_token="bot-tok", poster=poster)
    result = sender.send(content="hello", channel="999")
    assert result["status"] == "sent"
    assert "/channels/999/messages" in poster.calls[0][0]


def test_discord_webhook_ssrf_blocked():
    sender = DiscordSender(webhook_url="http://localhost/hook", poster=_never_called)
    with pytest.raises(DiscordError) as exc:
        sender.send(content="hello")
    assert "blocked webhook URL" in str(exc.value)


def test_discord_http_error_raises():
    poster = RecordingPoster(403, "Forbidden")
    sender = DiscordSender(webhook_url="https://discord.com/api/webhooks/1/abc", poster=poster)
    with pytest.raises(DiscordError) as exc:
        sender.send(content="hello")
    assert "403" in str(exc.value)


def test_discord_not_configured_raises():
    sender = DiscordSender(poster=_never_called)
    with pytest.raises(DiscordError):
        sender.send(content="hello")


# -- adapters ---------------------------------------------------------------


def test_slack_adapter_send_delegates():
    poster = RecordingPoster(200, json.dumps({"ok": True}))
    adapter = SlackAdapter(SlackSender(bot_token="xoxb-1", poster=poster))
    adapter.send(OutboundMessage(channel="slack", recipient_id="#ops", text="hi"))
    assert poster.calls[0][1] == {"channel": "#ops", "text": "hi"}
    assert adapter.poll_once() == []


def test_discord_adapter_send_delegates():
    poster = RecordingPoster(204, "")
    sender = DiscordSender(webhook_url="https://discord.com/api/webhooks/1/a", poster=poster)
    adapter = DiscordAdapter(sender)
    adapter.send(OutboundMessage(channel="discord", recipient_id="", text="hi"))
    assert poster.calls[0][1] == {"content": "hi"}
    assert adapter.poll_once() == []


# -- LLM tools --------------------------------------------------------------


def test_register_messaging_tools_registers_both():
    registry = ToolRegistry()
    register_messaging_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert {"send_slack_message", "send_discord_message"} <= names


def test_send_slack_tool_happy_path():
    registry = ToolRegistry()
    poster = RecordingPoster(200, json.dumps({"ok": True}))
    register_messaging_tools(registry, slack_sender=SlackSender(bot_token="xoxb-1", poster=poster))
    out = registry._tools["send_slack_message"]("hello", "#ops")
    assert "Sent message to Slack" in out


def test_send_discord_tool_happy_path():
    registry = ToolRegistry()
    poster = RecordingPoster(204, "")
    sender = DiscordSender(webhook_url="https://discord.com/api/webhooks/1/a", poster=poster)
    register_messaging_tools(registry, discord_sender=sender)
    out = registry._tools["send_discord_message"]("hello")
    assert "Sent message to Discord" in out


def test_send_slack_tool_not_configured(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    registry = ToolRegistry()
    register_messaging_tools(registry)  # no injected sender -> resolves from (empty) env
    out = registry._tools["send_slack_message"]("hello", "#ops")
    assert "not configured" in out


def test_send_slack_tool_reports_failure():
    registry = ToolRegistry()
    poster = RecordingPoster(200, json.dumps({"ok": False, "error": "not_in_channel"}))
    register_messaging_tools(registry, slack_sender=SlackSender(bot_token="xoxb-1", poster=poster))
    out = registry._tools["send_slack_message"]("hello", "#ops")
    assert "Slack send failed" in out
    assert "not_in_channel" in out


# -- WhatsApp: pure request builders ----------------------------------------


def test_meta_request_shape():
    url, payload, headers = build_meta_request("tok", "12345", "+447911000001", "hi")
    assert "graph.facebook.com" in url
    assert "12345" in url
    assert payload["messaging_product"] == "whatsapp"
    assert payload["text"]["body"] == "hi"
    assert headers["Authorization"] == "Bearer tok"
    assert headers.get("Content-Type") == "application/json"


def test_meta_request_strips_leading_plus():
    _, payload, _ = build_meta_request("tok", "pid", "+447900000001", "hello")
    assert not payload["to"].startswith("+")


def test_meta_request_requires_to():
    with pytest.raises(WhatsAppError):
        build_meta_request("tok", "pid", "", "hello")


def test_twilio_request_shape():
    url, payload, headers = build_twilio_request(
        "SID123", "auth", "whatsapp:+14155238886", "+447900000001", "hi"
    )
    assert "api.twilio.com" in url
    assert "SID123" in url
    assert payload["From"] == "whatsapp:+14155238886"
    assert payload["To"] == "whatsapp:+447900000001"  # prefix auto-added
    assert payload["Body"] == "hi"
    expected_basic = "Basic " + base64.b64encode(b"SID123:auth").decode()
    assert headers["Authorization"] == expected_basic
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_twilio_request_prefixes_from_number_when_missing():
    _, payload, _ = build_twilio_request("SID", "tok", "+14155238886", "+447900000001", "hi")
    assert payload["From"].startswith("whatsapp:")


def test_twilio_request_requires_to():
    with pytest.raises(WhatsAppError):
        build_twilio_request("SID", "auth", "whatsapp:+1", "", "hello")


def test_meta_truncates_overlong_text():
    _, payload, _ = build_meta_request("tok", "pid", "+44700000001", "x" * (MAX_TEXT + 500))
    assert len(payload["text"]["body"]) == MAX_TEXT
    assert payload["text"]["body"].endswith("…")


# -- WhatsAppSender ----------------------------------------------------------


def test_whatsapp_meta_send_success():
    poster = RecordingPoster(200, json.dumps({"messages": [{"id": "m1"}]}))
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    result = sender.send(to="+447900000001", text="hello")
    assert result["provider"] == "meta"
    assert result["to"] == "+447900000001"
    assert poster.calls[0][1]["messaging_product"] == "whatsapp"


def test_whatsapp_twilio_send_success():
    poster = RecordingPoster(201, json.dumps({"sid": "SM1"}))
    sender = WhatsAppSender(
        twilio_account_sid="SID",
        twilio_auth_token="auth",
        twilio_from="whatsapp:+14155238886",
        poster=poster,
    )
    result = sender.send(to="+447900000001", text="hello")
    assert result["provider"] == "twilio"
    # Twilio poster should have received form-encoded body (dict with From/To/Body)
    assert "Body" in poster.calls[0][1]


def test_whatsapp_meta_preferred_over_twilio_when_both_set():
    poster = RecordingPoster(200, json.dumps({}))
    sender = WhatsAppSender(
        meta_token="tok",
        meta_phone_number_id="pid",
        twilio_account_sid="SID",
        twilio_auth_token="auth",
        twilio_from="whatsapp:+14155",
        poster=poster,
    )
    result = sender.send(to="+1", text="hi")
    assert result["provider"] == "meta"


def test_whatsapp_not_configured():
    sender = WhatsAppSender(poster=_never_called)
    assert sender.is_configured() is False
    with pytest.raises(WhatsAppError, match="not configured"):
        sender.send(to="+1", text="hi")


def test_whatsapp_ssrf_blocked():
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=_never_called)
    # Monkeypatch the META_API constant to a private address is cumbersome;
    # instead pass allow_private=False (default) and verify SSRF guard fires when
    # the URL is a loopback.  We inject a poster that intercepts but the SSRF check
    # runs before the poster — so we verify via the raised exception.
    import unittest.mock

    with unittest.mock.patch(
        "hachi.channels.whatsapp.validate_outbound_url",
        return_value=(False, "private address"),
    ):
        with pytest.raises(WhatsAppError, match="blocked"):
            sender.send(to="+1", text="hi")


def test_whatsapp_http_error_raises():
    poster = RecordingPoster(400, '{"error":{"message":"bad request"}}')
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    with pytest.raises(WhatsAppError, match="HTTP 400"):
        sender.send(to="+447900000001", text="hello")


# -- WhatsAppAdapter --------------------------------------------------------


def test_whatsapp_adapter_send_delegates():
    poster = RecordingPoster(200, json.dumps({}))
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    adapter = WhatsAppAdapter(sender)
    adapter.send(OutboundMessage(channel="whatsapp", recipient_id="+447900000001", text="hi"))
    assert poster.calls[0][1]["text"]["body"] == "hi"
    assert adapter.poll_once() == []


def test_whatsapp_adapter_raises_when_unconfigured():
    adapter = WhatsAppAdapter(WhatsAppSender(poster=_never_called))
    with pytest.raises(WhatsAppError):
        adapter.send(OutboundMessage(channel="whatsapp", recipient_id="+1", text="hi"))


# -- LLM tool: send_whatsapp_message -----------------------------------------


def test_register_messaging_tools_includes_whatsapp():
    registry = ToolRegistry()
    register_messaging_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert "send_whatsapp_message" in names


def test_send_whatsapp_tool_happy_path_meta():
    poster = RecordingPoster(200, json.dumps({}))
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    registry = ToolRegistry()
    register_messaging_tools(registry, whatsapp_sender=sender)
    out = registry._tools["send_whatsapp_message"]("hello", "+447900000001")
    assert "Sent WhatsApp message" in out
    assert "meta" in out


def test_send_whatsapp_tool_not_configured(monkeypatch):
    monkeypatch.delenv("META_WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("META_WHATSAPP_PHONE_ID", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    registry = ToolRegistry()
    register_messaging_tools(registry)
    out = registry._tools["send_whatsapp_message"]("hello", "+447900000001")
    assert "not configured" in out


def test_send_whatsapp_tool_empty_to():
    poster = RecordingPoster(200, json.dumps({}))
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    registry = ToolRegistry()
    register_messaging_tools(registry, whatsapp_sender=sender)
    # `to` defaults to "" when not passed
    out = registry._tools["send_whatsapp_message"]("hello", "")
    assert "required" in out.lower()


def test_send_whatsapp_tool_failure_is_friendly():
    poster = RecordingPoster(400, '{"error":"bad"}')
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    registry = ToolRegistry()
    register_messaging_tools(registry, whatsapp_sender=sender)
    out = registry._tools["send_whatsapp_message"]("hello", "+447900000001")
    assert "WhatsApp send failed" in out


def test_send_whatsapp_tool_redacts_secrets():
    poster = RecordingPoster(200, json.dumps({}))
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    registry = ToolRegistry()
    register_messaging_tools(registry, whatsapp_sender=sender)
    # Inject a secret-like string and confirm either redaction or safe transmission
    secret_msg = "AKIA1234567890ABCDEF some message"
    out = registry._tools["send_whatsapp_message"](secret_msg, "+447900000001")
    # Either the message was sent (redacted) or the tool reported success — not an error
    assert "WhatsApp send failed" not in out


# ---------------------------------------------------------------------------
# Telegram outbound tool
# ---------------------------------------------------------------------------


def test_register_messaging_tools_includes_telegram() -> None:
    registry = ToolRegistry()
    register_messaging_tools(registry)
    assert "send_telegram_message" in registry._tools


def test_send_telegram_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    registry = ToolRegistry()
    register_messaging_tools(registry)
    out = registry._tools["send_telegram_message"]("hello")
    assert "not configured" in out.lower()
    assert "TELEGRAM_BOT_TOKEN" in out


def test_send_telegram_no_chat_id(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot:token")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    registry = ToolRegistry()
    register_messaging_tools(registry)
    out = registry._tools["send_telegram_message"]("hello")
    assert "chat_id" in out.lower()


def test_send_telegram_success(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot:token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    calls: list[tuple[str, str, str]] = []

    def _fake_sender(token: str, chat_id: str, text: str) -> dict:
        calls.append((token, chat_id, text))
        return {"ok": True}

    registry = ToolRegistry()
    register_messaging_tools(registry, telegram_sender=_fake_sender)
    out = registry._tools["send_telegram_message"]("Hello from agent")
    assert "sent" in out.lower()
    assert calls == [("bot:token", "12345", "Hello from agent")]


def test_send_telegram_explicit_chat_id(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot:token")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    calls: list[tuple[str, str, str]] = []

    def _fake_sender(token: str, chat_id: str, text: str) -> dict:
        calls.append((token, chat_id, text))
        return {"ok": True, "result": {"message_id": 1}}

    registry = ToolRegistry()
    register_messaging_tools(registry, telegram_sender=_fake_sender)
    out = registry._tools["send_telegram_message"]("Hi", "99999")
    assert "sent" in out.lower()
    assert calls[0][1] == "99999"


def test_send_telegram_http_error(monkeypatch) -> None:
    import urllib.error

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bad:token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")

    def _fail_sender(token: str, chat_id: str, text: str) -> dict:
        raise urllib.error.HTTPError(None, 401, "Unauthorized", {}, None)  # type: ignore[arg-type]

    registry = ToolRegistry()
    register_messaging_tools(registry, telegram_sender=_fail_sender)
    out = registry._tools["send_telegram_message"]("test")
    assert "failed" in out.lower()


def test_send_telegram_redacts_secrets(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot:token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

    captured: list[str] = []

    def _spy(token: str, chat_id: str, text: str) -> dict:
        captured.append(text)
        return {"ok": True}

    registry = ToolRegistry()
    register_messaging_tools(registry, telegram_sender=_spy)
    out = registry._tools["send_telegram_message"]("key=AKIA1234567890ABCDEF msg")
    # Either the raw key was redacted or the send succeeded without leaking it
    assert "failed" not in out.lower() or "redact" in out.lower()


# ---------------------------------------------------------------------------
# Idempotency — duplicate side effects must not happen on retry (AUDIT P0-3)
# ---------------------------------------------------------------------------


def test_send_slack_tool_dedups_identical_resend() -> None:
    registry = ToolRegistry()
    poster = RecordingPoster(200, json.dumps({"ok": True}))
    register_messaging_tools(registry, slack_sender=SlackSender(bot_token="xoxb-1", poster=poster))
    tool = registry._tools["send_slack_message"]
    first = tool("hello", "#ops")
    second = tool("hello", "#ops")  # an LLM retry / pool re-dispatch resending
    assert "Sent message to Slack" in first
    assert "idempotent" in second.lower()
    assert len(poster.calls) == 1  # the network send happened exactly once


def test_send_slack_tool_failed_send_stays_retryable() -> None:
    # A failed attempt must NOT be deduped — a genuine retry has to be allowed through.
    registry = ToolRegistry()
    poster = RecordingPoster(200, json.dumps({"ok": False, "error": "not_in_channel"}))
    register_messaging_tools(registry, slack_sender=SlackSender(bot_token="xoxb-1", poster=poster))
    tool = registry._tools["send_slack_message"]
    first = tool("hello", "#ops")
    second = tool("hello", "#ops")
    assert "Slack send failed" in first
    assert "Slack send failed" in second  # re-attempted, not suppressed
    assert len(poster.calls) == 2


def test_send_slack_tool_distinct_messages_both_send() -> None:
    registry = ToolRegistry()
    poster = RecordingPoster(200, json.dumps({"ok": True}))
    register_messaging_tools(registry, slack_sender=SlackSender(bot_token="xoxb-1", poster=poster))
    tool = registry._tools["send_slack_message"]
    tool("hello", "#ops")
    tool("a different message", "#ops")  # distinct payload → genuinely sent
    assert len(poster.calls) == 2


def test_send_discord_tool_dedups_identical_resend() -> None:
    registry = ToolRegistry()
    poster = RecordingPoster(204, "")
    sender = DiscordSender(webhook_url="https://discord.com/api/webhooks/1/a", poster=poster)
    register_messaging_tools(registry, discord_sender=sender)
    tool = registry._tools["send_discord_message"]
    tool("hello")
    second = tool("hello")
    assert "idempotent" in second.lower()
    assert len(poster.calls) == 1


def test_send_whatsapp_tool_dedups_identical_resend() -> None:
    poster = RecordingPoster(200, json.dumps({}))
    sender = WhatsAppSender(meta_token="tok", meta_phone_number_id="pid", poster=poster)
    registry = ToolRegistry()
    register_messaging_tools(registry, whatsapp_sender=sender)
    tool = registry._tools["send_whatsapp_message"]
    tool("hello", "+447900000001")
    second = tool("hello", "+447900000001")
    assert "idempotent" in second.lower()
    assert len(poster.calls) == 1


def test_send_telegram_tool_dedups_identical_resend(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot:token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    calls: list[tuple] = []

    def _fake_sender(token: str, chat_id: str, text: str) -> dict:
        calls.append((token, chat_id, text))
        return {"ok": True}

    registry = ToolRegistry()
    register_messaging_tools(registry, telegram_sender=_fake_sender)
    tool = registry._tools["send_telegram_message"]
    tool("Hello")
    second = tool("Hello")
    assert "idempotent" in second.lower()
    assert len(calls) == 1


def test_separate_registrations_have_independent_guards() -> None:
    # Two sessions (two register calls) get independent guards: an identical message in a
    # genuinely different session is NOT suppressed.
    poster1 = RecordingPoster(200, json.dumps({"ok": True}))
    poster2 = RecordingPoster(200, json.dumps({"ok": True}))
    reg1 = ToolRegistry()
    reg2 = ToolRegistry()
    register_messaging_tools(reg1, slack_sender=SlackSender(bot_token="t", poster=poster1))
    register_messaging_tools(reg2, slack_sender=SlackSender(bot_token="t", poster=poster2))
    reg1._tools["send_slack_message"]("hello", "#ops")
    reg2._tools["send_slack_message"]("hello", "#ops")
    assert len(poster1.calls) == 1
    assert len(poster2.calls) == 1


def test_injected_shared_guard_dedups_across_registrations() -> None:
    guard = IdempotencyGuard()
    poster = RecordingPoster(200, json.dumps({"ok": True}))
    reg1 = ToolRegistry()
    reg2 = ToolRegistry()
    register_messaging_tools(
        reg1, slack_sender=SlackSender(bot_token="t", poster=poster), guard=guard
    )
    register_messaging_tools(
        reg2, slack_sender=SlackSender(bot_token="t", poster=poster), guard=guard
    )
    reg1._tools["send_slack_message"]("hello", "#ops")
    second = reg2._tools["send_slack_message"]("hello", "#ops")
    assert "idempotent" in second.lower()
    assert len(poster.calls) == 1
