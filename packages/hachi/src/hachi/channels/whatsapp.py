"""WhatsApp outbound sender + adapter + inbound webhook receiver.

Supports two providers (auto-detected from environment variables):

- **Meta Cloud API** (official WhatsApp Business API) — POST to
  ``https://graph.facebook.com/v18.0/{phone_number_id}/messages`` with a
  Bearer token.  Requires ``META_WHATSAPP_TOKEN`` and ``META_WHATSAPP_PHONE_ID``.

- **Twilio WhatsApp API** — POST to the Twilio Messages endpoint with HTTP
  Basic Auth.  Requires ``TWILIO_ACCOUNT_SID``, ``TWILIO_AUTH_TOKEN``, and
  ``TWILIO_WHATSAPP_FROM`` (e.g. ``whatsapp:+14155238886``).

Inbound messages (webhook server) are handled by :class:`WhatsAppWebhookServer`,
which exposes an HTTP endpoint compatible with Meta's and Twilio's webhook delivery.

Credentials are read from the environment at call time (never at import/boot).
The ``poster`` is injectable so tests run fully offline. Outbound URLs are
validated through ``net_guard`` (SSRF mitigation).
"""

from __future__ import annotations

import base64
import http.server
import json
import os
import urllib.parse
from collections.abc import Callable
from typing import Any

from hachi.channels.base import ChannelAdapter, InboundMessage, OutboundMessage
from hachi.core.net_guard import validate_outbound_url

# (url, json_payload, headers) -> (status_code, response_text)
Poster = Callable[[str, dict[str, Any], dict[str, str]], tuple[int, str]]

# WhatsApp rejects messages longer than this; truncate so a long reply still posts.
MAX_TEXT = 4096

_META_API = "https://graph.facebook.com/v18.0/{phone_number_id}/messages"
_TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"


class WhatsAppError(RuntimeError):
    """Raised when a WhatsApp send is misconfigured or rejected by the provider."""


def _clamp(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def _default_poster(url: str, payload: dict[str, Any], headers: dict[str, str]) -> tuple[int, str]:
    import httpx

    with httpx.Client(timeout=15.0, follow_redirects=False) as client:
        # Twilio uses form-encoded bodies; Meta uses JSON — detect via Content-Type.
        if headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
            resp = client.post(url, data=payload, headers=headers)
        else:
            resp = client.post(url, json=payload, headers=headers)
        return resp.status_code, resp.text


# ---------------------------------------------------------------------------
# Pure request builders (unit-testable without a sender)
# ---------------------------------------------------------------------------


def build_meta_request(
    token: str, phone_number_id: str, to: str, text: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Build a Meta Cloud API send-text request (pure).

    Args:
        token: Meta WhatsApp Business bearer token.
        phone_number_id: The sender phone-number ID from Meta.
        to: Recipient phone number in E.164 format (e.g. ``"+447911123456"``).
        text: Message body.

    Returns:
        ``(url, payload, headers)`` ready to POST.
    """
    if not to:
        raise WhatsAppError("recipient phone number is required")
    url = _META_API.format(phone_number_id=phone_number_id)
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+").replace(" ", ""),  # Meta expects no leading +
        "type": "text",
        "text": {"body": _clamp(text)},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return url, payload, headers


def build_twilio_request(
    account_sid: str, auth_token: str, from_number: str, to: str, text: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Build a Twilio WhatsApp send-message request (pure).

    Args:
        account_sid: Twilio Account SID.
        auth_token: Twilio Auth Token.
        from_number: Twilio WhatsApp sender (e.g. ``"whatsapp:+14155238886"``).
        to: Recipient WhatsApp number (e.g. ``"whatsapp:+447911123456"``).
        text: Message body.

    Returns:
        ``(url, payload, headers)`` ready to POST.
    """
    if not to:
        raise WhatsAppError("recipient phone number is required")
    url = _TWILIO_API.format(account_sid=account_sid)
    # Twilio uses form-encoded bodies, but we handle it as a JSON-keyed dict
    # for consistency — the sender converts to form data internally.
    payload = {
        "From": from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}",
        "To": to if to.startswith("whatsapp:") else f"whatsapp:{to}",
        "Body": _clamp(text),
    }
    creds = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    return url, payload, headers


# ---------------------------------------------------------------------------
# WhatsAppSender
# ---------------------------------------------------------------------------


class WhatsAppSender:
    """Send WhatsApp messages via the Meta Cloud API or the Twilio API.

    Mirrors the :class:`~hachi.channels.slack.SlackSender` and
    :class:`~hachi.channels.discord.DiscordSender` design:

    - Credentials are resolved at call time, never at import/boot.
    - An injectable ``poster`` makes offline tests trivial.
    - Uses :func:`~hachi.core.net_guard.validate_outbound_url` for SSRF.
    """

    def __init__(
        self,
        *,
        # Meta credentials
        meta_token: str | None = None,
        meta_phone_number_id: str | None = None,
        # Twilio credentials
        twilio_account_sid: str | None = None,
        twilio_auth_token: str | None = None,
        twilio_from: str | None = None,
        # Shared
        poster: Poster | None = None,
        allow_private: bool = False,
    ) -> None:
        self._meta_token = meta_token or None
        self._meta_phone_id = meta_phone_number_id or None
        self._twilio_sid = twilio_account_sid or None
        self._twilio_token = twilio_auth_token or None
        self._twilio_from = twilio_from or None
        self._poster = poster or _default_poster
        self._allow_private = allow_private

    @classmethod
    def from_env(cls, poster: Poster | None = None) -> WhatsAppSender:
        """Build from environment variables (Meta first, Twilio fallback)."""
        return cls(
            meta_token=os.environ.get("META_WHATSAPP_TOKEN"),
            meta_phone_number_id=os.environ.get("META_WHATSAPP_PHONE_ID"),
            twilio_account_sid=os.environ.get("TWILIO_ACCOUNT_SID"),
            twilio_auth_token=os.environ.get("TWILIO_AUTH_TOKEN"),
            twilio_from=os.environ.get("TWILIO_WHATSAPP_FROM"),
            poster=poster,
            allow_private=os.environ.get("HACHI_REST_ALLOW_PRIVATE", "").strip().lower()
            in {"1", "true", "yes"},
        )

    def is_configured(self) -> bool:
        """Return True when at least one provider has sufficient credentials."""
        meta_ok = bool(self._meta_token and self._meta_phone_id)
        twilio_ok = bool(self._twilio_sid and self._twilio_token and self._twilio_from)
        return meta_ok or twilio_ok

    @property
    def _active_provider(self) -> str:
        """Return the name of the first configured provider."""
        if self._meta_token and self._meta_phone_id:
            return "meta"
        if self._twilio_sid and self._twilio_token and self._twilio_from:
            return "twilio"
        return "none"

    def send(self, *, to: str, text: str) -> dict[str, Any]:
        """Send a WhatsApp message.  Raises :class:`WhatsAppError` on failure.

        Args:
            to: Recipient phone number (E.164 for Meta; ``whatsapp:+NNN`` or
                bare number for Twilio — the prefix is added automatically).
            text: Message body (truncated to :data:`MAX_TEXT` characters).

        Returns:
            A dict with ``provider`` and ``to``.
        """
        if not self.is_configured():
            raise WhatsAppError(
                "WhatsApp is not configured. Set META_WHATSAPP_TOKEN + "
                "META_WHATSAPP_PHONE_ID (Meta Cloud API), or "
                "TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_WHATSAPP_FROM (Twilio)."
            )

        provider = self._active_provider

        if provider == "meta":
            assert self._meta_token and self._meta_phone_id  # guarded by is_configured
            url, payload, headers = build_meta_request(
                self._meta_token, self._meta_phone_id, to, text
            )
        else:
            assert self._twilio_sid and self._twilio_token and self._twilio_from
            url, payload, headers = build_twilio_request(
                self._twilio_sid, self._twilio_token, self._twilio_from, to, text
            )

        ok, reason = validate_outbound_url(url, allow_private=self._allow_private)
        if not ok:
            raise WhatsAppError(f"blocked WhatsApp endpoint: {reason}")

        # The poster detects application/x-www-form-urlencoded and sends as form
        # data (data=payload) rather than JSON (json=payload) for Twilio.
        status, body = self._poster(url, payload, headers)

        if status not in (200, 201):
            raise WhatsAppError(f"WhatsApp send failed (HTTP {status}): {body[:200]}")

        return {"provider": provider, "to": to}


# ---------------------------------------------------------------------------
# ChannelAdapter (send-only; inbound arrives via the generic webhook)
# ---------------------------------------------------------------------------


class WhatsAppAdapter(ChannelAdapter):
    """Outbound WhatsApp adapter for the ChannelRouter.

    Inbound messages from WhatsApp arrive through the generic
    ``POST /channels/{channel}/inbound`` webhook — no polling required.
    This adapter only handles outbound sends.
    """

    def __init__(self, sender: WhatsAppSender | None = None) -> None:
        self._sender = sender or WhatsAppSender.from_env()

    def poll_once(self) -> list[InboundMessage]:
        """Inbound handled by generic webhook; always returns empty."""
        return []

    def send(self, message: OutboundMessage) -> None:
        """Send a WhatsApp message to ``message.recipient_id``."""
        if not self._sender.is_configured():
            raise WhatsAppError(
                "WhatsApp is not configured — set META_WHATSAPP_TOKEN + "
                "META_WHATSAPP_PHONE_ID or Twilio credentials."
            )
        self._sender.send(to=message.recipient_id, text=message.text)


# ---------------------------------------------------------------------------
# Inbound webhook parsing
# ---------------------------------------------------------------------------


def parse_meta_webhook(body: bytes) -> list[InboundMessage]:
    """Parse a Meta WhatsApp Cloud API webhook POST body into inbound messages.

    Handles the nested ``entry → changes → value → messages`` structure.
    Non-text message types (image, sticker, …) are skipped.

    Args:
        body: Raw UTF-8 JSON bytes from the POST request.

    Returns:
        List of :class:`~hachi.channels.base.InboundMessage` objects (may be empty).
    """
    try:
        data: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError:
        return []

    if data.get("object") != "whatsapp_business_account":
        return []

    results: list[InboundMessage] = []
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            # Build a wa_id → display name map from contacts list.
            contacts: dict[str, str] = {
                c.get("wa_id", ""): c.get("profile", {}).get("name", "")
                for c in value.get("contacts", [])
            }
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                sender_id = msg.get("from", "")
                text = msg.get("text", {}).get("body", "")
                if not sender_id or not text:
                    continue
                sender_name = contacts.get(sender_id, sender_id)
                results.append(
                    InboundMessage(
                        channel="whatsapp",
                        sender_id=sender_id,
                        sender_name=sender_name,
                        text=text,
                    )
                )
    return results


def parse_twilio_webhook(body: bytes) -> list[InboundMessage]:
    """Parse a Twilio WhatsApp webhook POST body (form-encoded) into inbound messages.

    Twilio delivers: ``From=whatsapp%3A%2B14155…&Body=Hello&AccountSid=…``

    Args:
        body: Raw URL-encoded form bytes from the POST request.

    Returns:
        List with at most one :class:`~hachi.channels.base.InboundMessage`.
    """
    try:
        params = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
    except Exception:
        return []

    raw_from = params.get("From", [""])[0]
    text = params.get("Body", [""])[0].strip()

    # Twilio prefixes sender with "whatsapp:" — strip it for a clean sender_id.
    sender_id = raw_from.removeprefix("whatsapp:").strip()
    if not sender_id or not text:
        return []

    return [
        InboundMessage(
            channel="whatsapp",
            sender_id=sender_id,
            sender_name=params.get("ProfileName", [sender_id])[0],
            text=text,
        )
    ]


# ---------------------------------------------------------------------------
# Webhook HTTP server (stdlib — no external deps)
# ---------------------------------------------------------------------------

# Dispatcher: receives an InboundMessage, returns reply text (or "").
WebhookDispatcher = Callable[[InboundMessage], str]


class _WhatsAppRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for WhatsApp webhook delivery."""

    server: WhatsAppWebhookServer  # set on creation by HTTPServer

    def log_message(self, fmt: str, *args: object) -> None:  # silence default stderr spam
        pass

    def do_GET(self) -> None:
        """Handle Meta webhook verification challenge."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        mode = params.get("hub.mode", [""])[0]
        token = params.get("hub.verify_token", [""])[0]
        challenge = params.get("hub.challenge", [""])[0]

        expected = self.server.verify_token
        if mode == "subscribe" and (not expected or token == expected):
            self._respond(200, challenge.encode())
        else:
            self._respond(403, b"Forbidden")

    def do_POST(self) -> None:
        """Handle inbound message from Meta or Twilio."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b""

        content_type = self.headers.get("Content-Type", "")
        if "application/x-www-form-urlencoded" in content_type:
            messages = parse_twilio_webhook(body)
        else:
            messages = parse_meta_webhook(body)

        allowed = self.server.allowed_senders
        dispatcher = self.server.dispatcher

        for msg in messages:
            if allowed and msg.sender_id not in allowed:
                continue
            if dispatcher:
                try:
                    dispatcher(msg)
                except Exception:
                    pass

        self._respond(200, b"OK")

    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WhatsAppWebhookServer(http.server.HTTPServer):
    """Stdlib HTTP server that receives WhatsApp webhook deliveries.

    Inject ``dispatcher`` to handle inbound messages without network calls in tests.
    ``verify_token`` should match the token configured in the Meta App Dashboard.

    Usage::

        server = WhatsAppWebhookServer(
            host="0.0.0.0", port=8080,
            verify_token="my-secret",
            dispatcher=lambda msg: router.dispatch(msg),
        )
        server.serve_forever()
    """

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = 8080,
        verify_token: str = "",
        dispatcher: WebhookDispatcher | None = None,
        allowed_senders: set[str] | None = None,
    ) -> None:
        self.verify_token = verify_token
        self.dispatcher = dispatcher
        self.allowed_senders = allowed_senders or set()
        super().__init__((host, port), _WhatsAppRequestHandler)
