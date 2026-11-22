"""Multi-channel chat adapters.

Lets users talk to Hachi from where they already are — Telegram today, with
Slack / Discord / WhatsApp following the same contract — instead of only the TUI
or web app. Inbound messages are routed (with per-sender session continuity and
an optional allowlist) into agent sessions, and replies are sent back out.

The routing core (:class:`ChannelRouter`) is transport-agnostic and pure, so it
is fully unit-testable without any network or bot credentials.
"""

from hachi.channels.base import ChannelAdapter, InboundMessage, OutboundMessage, SessionRunner
from hachi.channels.router import ChannelRouter

__all__ = [
    "ChannelAdapter",
    "ChannelRouter",
    "InboundMessage",
    "OutboundMessage",
    "SessionRunner",
]
