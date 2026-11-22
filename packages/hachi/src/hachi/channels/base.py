"""Core contracts shared by every chat channel."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

# A SessionRunner turns (session_key, user_text) into the agent's reply text.
# Production runners map the session_key to a persistent AgentSession; tests pass
# a trivial function. Keeping this a plain callable keeps the router decoupled
# from the (heavy, credentialed) agent runtime.
SessionRunner = Callable[[str, str], str]


@dataclass(slots=True)
class InboundMessage:
    """A message received from an external channel."""

    channel: str  # e.g. "telegram"
    sender_id: str  # stable per-user/chat id within the channel
    text: str
    sender_name: str = ""


@dataclass(slots=True)
class OutboundMessage:
    """A reply to deliver back to a channel recipient."""

    channel: str
    recipient_id: str
    text: str


class ChannelAdapter(ABC):
    """Transport for a specific chat platform.

    An adapter knows how to receive messages from and send messages to one
    platform. It delegates all reasoning to a :class:`~hachi.channels.router.ChannelRouter`.
    """

    name: str = "channel"

    @abstractmethod
    def send(self, message: OutboundMessage) -> None:
        """Deliver a reply to the channel."""

    @abstractmethod
    def poll_once(self) -> list[InboundMessage]:
        """Fetch any newly received messages (one batch)."""
