"""Tests for the WhatsApp webhook channel.

Covers:
- parse_meta_webhook: normal payload, non-text messages, wrong object type
- parse_twilio_webhook: normal payload, bare number, missing fields
- WhatsAppWebhookServer GET (Meta verify challenge): valid, wrong token, no token
- WhatsAppWebhookServer POST: Meta JSON, Twilio form-encoded, allowlist filtering
- channel_whatsapp CLI command: starts server with correct args, allow flag
"""

from __future__ import annotations

import http.client
import json
import threading
import urllib.parse
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.channels.whatsapp import (
    WhatsAppWebhookServer,
    parse_meta_webhook,
    parse_twilio_webhook,
)
from hachi.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta_payload(
    *,
    sender: str = "+14155238886",
    name: str = "Alice",
    text: str = "Hello",
    msg_type: str = "text",
) -> bytes:
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"wa_id": sender, "profile": {"name": name}}],
                                "messages": [
                                    {
                                        "from": sender,
                                        "type": msg_type,
                                        "id": "msg-1",
                                        "text": {"body": text},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }
    ).encode()


def _twilio_payload(
    *,
    from_: str = "whatsapp:+14155238886",
    body: str = "Hello",
    profile: str = "Alice",
) -> bytes:
    return urllib.parse.urlencode(
        {"From": from_, "Body": body, "ProfileName": profile, "AccountSid": "ACxxx"}
    ).encode()


# ---------------------------------------------------------------------------
# parse_meta_webhook
# ---------------------------------------------------------------------------


class TestParseMetaWebhook:
    def test_normal_text_message(self) -> None:
        msgs = parse_meta_webhook(_meta_payload())
        assert len(msgs) == 1
        assert msgs[0].sender_id == "+14155238886"
        assert msgs[0].sender_name == "Alice"
        assert msgs[0].text == "Hello"

    def test_non_text_type_skipped(self) -> None:
        msgs = parse_meta_webhook(_meta_payload(msg_type="image"))
        assert msgs == []

    def test_wrong_object_type_ignored(self) -> None:
        data = json.dumps({"object": "page", "entry": []}).encode()
        assert parse_meta_webhook(data) == []

    def test_invalid_json_returns_empty(self) -> None:
        assert parse_meta_webhook(b"not json") == []

    def test_empty_entry_list(self) -> None:
        data = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
        assert parse_meta_webhook(data) == []

    def test_contact_name_falls_back_to_id(self) -> None:
        data = json.dumps(
            {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "contacts": [],
                                    "messages": [
                                        {
                                            "from": "+19999",
                                            "type": "text",
                                            "id": "m1",
                                            "text": {"body": "hi"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                ],
            }
        ).encode()
        msgs = parse_meta_webhook(data)
        assert msgs[0].sender_name == "+19999"

    def test_multiple_messages(self) -> None:
        data = json.dumps(
            {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "contacts": [],
                                    "messages": [
                                        {
                                            "from": "+1",
                                            "type": "text",
                                            "id": "m1",
                                            "text": {"body": "A"},
                                        },
                                        {
                                            "from": "+2",
                                            "type": "text",
                                            "id": "m2",
                                            "text": {"body": "B"},
                                        },
                                    ],
                                }
                            }
                        ]
                    }
                ],
            }
        ).encode()
        msgs = parse_meta_webhook(data)
        assert len(msgs) == 2
        assert {m.text for m in msgs} == {"A", "B"}


# ---------------------------------------------------------------------------
# parse_twilio_webhook
# ---------------------------------------------------------------------------


class TestParseTwilioWebhook:
    def test_normal_payload(self) -> None:
        msgs = parse_twilio_webhook(_twilio_payload())
        assert len(msgs) == 1
        assert msgs[0].sender_id == "+14155238886"
        assert msgs[0].text == "Hello"
        assert msgs[0].sender_name == "Alice"

    def test_strips_whatsapp_prefix(self) -> None:
        msgs = parse_twilio_webhook(_twilio_payload(from_="whatsapp:+447911123456"))
        assert msgs[0].sender_id == "+447911123456"

    def test_bare_number_no_prefix(self) -> None:
        msgs = parse_twilio_webhook(_twilio_payload(from_="+447911123456"))
        assert msgs[0].sender_id == "+447911123456"

    def test_missing_body_returns_empty(self) -> None:
        data = urllib.parse.urlencode({"From": "whatsapp:+14155238886"}).encode()
        assert parse_twilio_webhook(data) == []

    def test_missing_from_returns_empty(self) -> None:
        data = urllib.parse.urlencode({"Body": "hello"}).encode()
        assert parse_twilio_webhook(data) == []

    def test_invalid_bytes_returns_empty(self) -> None:
        # parse_qs won't crash but the result will be empty / missing keys
        result = parse_twilio_webhook(b"")
        assert result == []


# ---------------------------------------------------------------------------
# WhatsAppWebhookServer — live HTTP tests (bind on 127.0.0.1, free port)
# ---------------------------------------------------------------------------


def _start_server(
    *,
    verify_token: str = "",
    dispatcher=None,
    allowed_senders=None,
) -> tuple[WhatsAppWebhookServer, threading.Thread]:
    """Start a server on a free port and return (server, thread)."""
    srv = WhatsAppWebhookServer(
        host="127.0.0.1",
        port=0,  # OS picks a free port
        verify_token=verify_token,
        dispatcher=dispatcher,
        allowed_senders=allowed_senders or set(),
    )
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, t


def _get(server: WhatsAppWebhookServer, path: str) -> tuple[int, str]:
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=3)
    conn.request("GET", path)
    resp = conn.getresponse()
    return resp.status, resp.read().decode()


def _post(
    server: WhatsAppWebhookServer, body: bytes, content_type: str = "application/json"
) -> tuple[int, str]:
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=3)
    conn.request("POST", "/", body=body, headers={"Content-Type": content_type})
    resp = conn.getresponse()
    return resp.status, resp.read().decode()


class TestWhatsAppWebhookServer:
    def test_meta_verify_challenge_correct_token(self) -> None:
        srv, _ = _start_server(verify_token="secret")
        try:
            status, body = _get(
                srv,
                "/?hub.mode=subscribe&hub.verify_token=secret&hub.challenge=abc123",
            )
            assert status == 200
            assert body == "abc123"
        finally:
            srv.shutdown()

    def test_meta_verify_challenge_wrong_token(self) -> None:
        srv, _ = _start_server(verify_token="secret")
        try:
            status, _ = _get(
                srv,
                "/?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=abc123",
            )
            assert status == 403
        finally:
            srv.shutdown()

    def test_meta_verify_challenge_no_token_configured(self) -> None:
        """When no verify_token is configured, all tokens are accepted."""
        srv, _ = _start_server(verify_token="")
        try:
            status, body = _get(
                srv,
                "/?hub.mode=subscribe&hub.verify_token=anything&hub.challenge=xyz",
            )
            assert status == 200
            assert body == "xyz"
        finally:
            srv.shutdown()

    def test_post_meta_dispatches_message(self) -> None:
        received: list = []
        srv, _ = _start_server(dispatcher=lambda msg: received.append(msg))
        try:
            status, _ = _post(srv, _meta_payload(text="Yo!"))
            assert status == 200
            assert len(received) == 1
            assert received[0].text == "Yo!"
        finally:
            srv.shutdown()

    def test_post_twilio_dispatches_message(self) -> None:
        received: list = []
        srv, _ = _start_server(dispatcher=lambda msg: received.append(msg))
        try:
            status, _ = _post(
                srv,
                _twilio_payload(body="Hi Twilio"),
                content_type="application/x-www-form-urlencoded",
            )
            assert status == 200
            assert len(received) == 1
            assert received[0].text == "Hi Twilio"
        finally:
            srv.shutdown()

    def test_allowlist_blocks_unknown_sender(self) -> None:
        received: list = []
        srv, _ = _start_server(
            dispatcher=lambda msg: received.append(msg),
            allowed_senders={"+9999999"},
        )
        try:
            _post(srv, _meta_payload(sender="+14155238886"))
            assert received == []
        finally:
            srv.shutdown()

    def test_allowlist_passes_permitted_sender(self) -> None:
        received: list = []
        srv, _ = _start_server(
            dispatcher=lambda msg: received.append(msg),
            allowed_senders={"+14155238886"},
        )
        try:
            _post(srv, _meta_payload(sender="+14155238886"))
            assert len(received) == 1
        finally:
            srv.shutdown()

    def test_empty_allowlist_passes_all(self) -> None:
        received: list = []
        srv, _ = _start_server(dispatcher=lambda msg: received.append(msg))
        try:
            _post(srv, _meta_payload(sender="+99999"))
            assert len(received) == 1
        finally:
            srv.shutdown()

    def test_dispatcher_exception_doesnt_crash_server(self) -> None:
        """A dispatcher that raises must not crash the server."""

        def _boom(msg: object) -> None:
            raise RuntimeError("kaboom")

        srv, _ = _start_server(dispatcher=_boom)
        try:
            status, _ = _post(srv, _meta_payload())
            assert status == 200
        finally:
            srv.shutdown()


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


class TestChannelWhatsappCmd:
    """CLI tests patch at the source modules (local imports inside the function)."""

    def _patch_all(self, fake_server_cls=None):
        """Return a context manager that patches all heavy dependencies."""
        if fake_server_cls is None:
            mock_srv = MagicMock()
            mock_srv.serve_forever.side_effect = KeyboardInterrupt
            fake_server_cls = MagicMock(return_value=mock_srv)

        return (
            patch("hachi.channels.whatsapp.WhatsAppWebhookServer", fake_server_cls),
            patch("hachi.channels.runner.GatewaySessionRunner"),
            patch("hachi.channels.whatsapp.WhatsAppAdapter"),
            patch("hachi.channels.ChannelRouter"),
        )

    def test_command_starts_server_and_exits_cleanly(self) -> None:
        """KeyboardInterrupt from serve_forever should produce exit_code 0."""
        mock_srv = MagicMock()
        mock_srv.serve_forever.side_effect = KeyboardInterrupt
        mock_cls = MagicMock(return_value=mock_srv)

        patches = self._patch_all(fake_server_cls=mock_cls)
        with patches[0], patches[1], patches[2], patches[3]:
            result = runner.invoke(app, ["channel", "whatsapp", "--port", "9999"])

        assert result.exit_code == 0

    def test_command_passes_verify_token(self) -> None:
        created_kwargs: list[dict] = []

        class _FakeServer:
            def __init__(self, **kwargs: object) -> None:
                created_kwargs.append(dict(kwargs))

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

            def server_close(self) -> None:
                pass

        patches = (
            patch("hachi.channels.whatsapp.WhatsAppWebhookServer", _FakeServer),
            patch("hachi.channels.runner.GatewaySessionRunner"),
            patch("hachi.channels.whatsapp.WhatsAppAdapter"),
            patch("hachi.channels.ChannelRouter"),
        )
        with patches[0], patches[1], patches[2], patches[3]:
            runner.invoke(
                app, ["channel", "whatsapp", "--verify-token", "my-secret", "--port", "7777"]
            )

        assert created_kwargs[0]["verify_token"] == "my-secret"
        assert created_kwargs[0]["port"] == 7777

    def test_allow_flag_populates_allowlist(self) -> None:
        created_kwargs: list[dict] = []

        class _FakeServer:
            def __init__(self, **kwargs: object) -> None:
                created_kwargs.append(dict(kwargs))

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

            def server_close(self) -> None:
                pass

        patches = (
            patch("hachi.channels.whatsapp.WhatsAppWebhookServer", _FakeServer),
            patch("hachi.channels.runner.GatewaySessionRunner"),
            patch("hachi.channels.whatsapp.WhatsAppAdapter"),
            patch("hachi.channels.ChannelRouter"),
        )
        with patches[0], patches[1], patches[2], patches[3]:
            runner.invoke(
                app,
                ["channel", "whatsapp", "--allow", "+14155238886,+447911123456"],
            )

        allowed = created_kwargs[0]["allowed_senders"]
        assert "+14155238886" in allowed
        assert "+447911123456" in allowed
