"""LLM-callable notification tools (desktop pop-up + SMTP email digest + batched digest).

Lets the agent proactively alert the user outside the chat window:
- ``notify_user``         — OS-native desktop notification (macOS / Linux / Windows).
- ``send_email_digest``   — SMTP email notification / digest.
- ``buffer_notification`` — Add a message to an in-process digest buffer.
- ``flush_notification_digest`` — Flush the buffer as a batched email + desktop toast.

Both one-shot tools degrade gracefully:
- Desktop: returns a friendly "not available" string if OS tools are absent.
- Email:   returns a "not configured" string if SMTP creds are unset.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hachi.core.loop import ToolRegistry
from hachi.core.notifier import DesktopNotifier, DigestBuffer, EmailNotifier

# Module-level shared digest buffer (one per process).
_SHARED_DIGEST_BUFFER: DigestBuffer | None = None


def _get_shared_buffer() -> DigestBuffer:
    global _SHARED_DIGEST_BUFFER  # noqa: PLW0603
    if _SHARED_DIGEST_BUFFER is None:
        _SHARED_DIGEST_BUFFER = DigestBuffer()
    return _SHARED_DIGEST_BUFFER


# ---------------------------------------------------------------------------
# Desktop notification tool
# ---------------------------------------------------------------------------

NOTIFY_USER_SCHEMA = {
    "name": "notify_user",
    "description": (
        "Send a desktop OS notification (pop-up/toast) to the user's screen. "
        "Use this to proactively alert the user about completed tasks, reminders, "
        "or time-sensitive events — even when they're not looking at the chat window. "
        "Works on macOS (osascript), Linux (notify-send), and Windows (PowerShell)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short notification headline (≤60 chars)."},
            "body": {
                "type": "string",
                "description": "Notification body text (one or two sentences).",
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "normal", "critical"],
                "description": "Urgency level (Linux only; 'normal' on other platforms).",
            },
        },
        "required": ["title", "body"],
    },
}


def _make_notify_user(notifier: DesktopNotifier | None) -> Callable[[str, str, str], str]:
    """Build the notify_user tool function.

    Args:
        notifier: Injectable :class:`DesktopNotifier`; defaults to a live instance.
    """

    def notify_user(title: str, body: str, urgency: str = "normal") -> str:
        active: DesktopNotifier = notifier if notifier is not None else DesktopNotifier()
        result: str = active.send(title=title, body=body, urgency=urgency)
        return result

    return notify_user


# ---------------------------------------------------------------------------
# Email digest tool
# ---------------------------------------------------------------------------

SEND_EMAIL_DIGEST_SCHEMA = {
    "name": "send_email_digest",
    "description": (
        "Send an email notification or digest to the user via SMTP. "
        "Use this for longer summaries, daily/weekly digests, or when the user "
        "is away from their computer. "
        "Requires HACHI_SMTP_USER and HACHI_SMTP_PASSWORD to be configured. "
        "The default recipient is HACHI_SMTP_TO when `to` is omitted."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Email subject line."},
            "body": {
                "type": "string",
                "description": "Email body (plain text; markdown is acceptable).",
            },
            "to": {
                "type": "string",
                "description": "Recipient email address. Falls back to HACHI_SMTP_TO.",
            },
        },
        "required": ["subject", "body"],
    },
}


def _make_send_email_digest(
    email_notifier: EmailNotifier | None,
) -> Callable[[str, str, str], str]:
    """Build the send_email_digest tool function.

    Args:
        email_notifier: Injectable :class:`EmailNotifier`; defaults to env-based config.
    """

    def send_email_digest(subject: str, body: str, to: str = "") -> str:
        active = email_notifier or EmailNotifier.from_env()
        if not active.is_configured():
            return (
                "Email notifications are not configured. "
                "Set HACHI_SMTP_USER and HACHI_SMTP_PASSWORD (and optionally "
                "HACHI_SMTP_HOST, HACHI_SMTP_PORT, HACHI_SMTP_FROM, "
                "HACHI_SMTP_TO), then try again."
            )
        try:
            result = active.send(subject=subject, body=body, to=to)
        except RuntimeError as exc:
            return f"Email notification failed: {exc}"
        except Exception as exc:
            return f"Email notification failed: {exc}"
        return f"Email sent to {result.get('to')}: {result.get('subject')!r}"

    return send_email_digest


# ---------------------------------------------------------------------------
# Digest buffer tools
# ---------------------------------------------------------------------------

BUFFER_NOTIFICATION_SCHEMA = {
    "name": "buffer_notification",
    "description": (
        "Add a message to the pending notification digest buffer. Use this when you want "
        "to batch multiple notifications into one email/toast summary instead of sending "
        "them individually. Call `flush_notification_digest` to send the batch."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Notification text to add to the digest buffer.",
            },
        },
        "required": ["message"],
    },
}

FLUSH_NOTIFICATION_DIGEST_SCHEMA = {
    "name": "flush_notification_digest",
    "description": (
        "Send all buffered notifications as a single batched email digest and desktop "
        "toast. Returns a summary of what was sent. If the buffer is empty, returns an "
        "informational message. Clears the buffer after sending."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Email subject for the digest (default: 'Hachi digest').",
            },
            "to": {
                "type": "string",
                "description": "Recipient email (falls back to HACHI_SMTP_TO).",
            },
        },
        "required": [],
    },
}


def _make_buffer_notification(buf: DigestBuffer | None) -> Callable[[str], str]:
    def buffer_notification(message: str) -> str:
        active = buf or _get_shared_buffer()
        active.add(message)
        return f"Added to digest buffer ({active.pending_count()} item(s) pending)."

    return buffer_notification


def _make_flush_notification_digest(
    buf: DigestBuffer | None,
) -> Callable[[str, str], str]:
    def flush_notification_digest(subject: str = "Hachi digest", to: str = "") -> str:
        active = buf or _get_shared_buffer()
        if active.pending_count() == 0:
            return "Digest buffer is empty — nothing to send."
        result: dict[str, Any] = active.flush(subject=subject, to=to)
        parts: list[str] = []
        if result.get("sent_email"):
            parts.append("email sent")
        if result.get("sent_desktop"):
            parts.append("desktop notification shown")
        if not parts:
            err = result.get("error", "unknown error")
            return f"Digest flush attempted but nothing sent: {err}"
        summary = f"Digest sent ({result['item_count']} item(s)) via {', '.join(parts)}."
        if result.get("error"):
            summary += f" Warning: {result['error']}"
        return summary

    return flush_notification_digest


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_notification_tools(
    registry: ToolRegistry,
    *,
    notifier: DesktopNotifier | None = None,
    email_notifier: EmailNotifier | None = None,
    digest_buffer: DigestBuffer | None = None,
) -> None:
    """Register desktop-notification, email-digest, and batched-digest tools.

    Args:
        registry: The agent's :class:`~hachi.core.loop.ToolRegistry`.
        notifier: Injectable :class:`DesktopNotifier`; defaults to live OS calls.
        email_notifier: Injectable :class:`EmailNotifier`; defaults to env-based config.
        digest_buffer: Injectable :class:`DigestBuffer`; defaults to the shared instance.
    """
    registry.register(NOTIFY_USER_SCHEMA, _make_notify_user(notifier))
    registry.register(SEND_EMAIL_DIGEST_SCHEMA, _make_send_email_digest(email_notifier))
    registry.register(BUFFER_NOTIFICATION_SCHEMA, _make_buffer_notification(digest_buffer))
    registry.register(
        FLUSH_NOTIFICATION_DIGEST_SCHEMA, _make_flush_notification_digest(digest_buffer)
    )
