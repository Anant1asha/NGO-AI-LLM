"""Transport-agnostic routing from inbound channel messages to agent replies."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from hachi.channels.base import InboundMessage, OutboundMessage, SessionRunner
from hachi.core.untrusted_content import guard_untrusted

logger = logging.getLogger(__name__)


class ChannelRouter:
    """Route inbound messages to per-sender agent sessions and produce replies.

    Responsibilities:
      * **Session continuity** — every distinct ``(channel, sender_id)`` maps to a
        stable session key so a user's conversation has memory across messages.
      * **Access control** — an optional allowlist restricts who may talk to the
        agent (important: a chat bot is an open door otherwise).
      * **Isolation of failures** — an error from the agent becomes a friendly
        reply rather than crashing the adapter's receive loop.
    """

    def __init__(
        self,
        runner: SessionRunner,
        allowlist: Iterable[str] | None = None,
        *,
        allow_all_when_no_allowlist: bool = False,
    ):
        """Initialise the router.

        Args:
            runner: Callable that executes one agent turn and returns the reply.
            allowlist: An explicit iterable of permitted ``sender_id`` strings.
                When provided (even as an empty iterable) ONLY the listed senders
                are admitted — an **empty allowlist denies everyone** (fail-closed).
                Pass ``None`` together with ``allow_all_when_no_allowlist=True`` to
                run in open-access mode (useful for private/trusted deployments where
                no allowlist is desired).  Defaults to ``None`` which, without the
                opt-in flag, *also* denies all senders to avoid silent exposure.
            allow_all_when_no_allowlist: Opt-in flag that makes a missing allowlist
                behave as open-access (admit any sender).  Default ``False``.
                Document this flag in your deployment config if you enable it.
        """
        self._runner = runner
        self._allow_all_when_no_allowlist = allow_all_when_no_allowlist
        # Build the allowlist set from the iterable, *preserving an empty set*
        # (distinct from None).  ``None`` means "no allowlist was supplied";
        # ``set()`` means "an empty allowlist was supplied → deny everyone".
        if allowlist is not None:
            self._allowlist: set[str] | None = {str(s) for s in allowlist}
        else:
            self._allowlist = None
        self._sessions: dict[tuple[str, str], str] = {}

    def session_key(self, channel: str, sender_id: str) -> str:
        """Return (creating if needed) the stable session key for a sender."""
        key = (channel, sender_id)
        if key not in self._sessions:
            self._sessions[key] = f"{channel}:{sender_id}"
        return self._sessions[key]

    def is_allowed(self, sender_id: str) -> bool:
        """Return whether ``sender_id`` is permitted to send messages.

        Decision table:
        - Allowlist supplied (even empty) → only listed senders admitted.
          An empty allowlist denies *everyone* (fail-closed).
        - No allowlist supplied + ``allow_all_when_no_allowlist=True`` → admit all.
        - No allowlist supplied + ``allow_all_when_no_allowlist=False`` (default)
          → deny all (fail-closed; forces explicit opt-in for open access).
        """
        if self._allowlist is not None:
            # Explicit allowlist present: set membership check (empty set → deny all).
            return str(sender_id) in self._allowlist
        # No allowlist supplied: honour the opt-in open-access flag.
        return self._allow_all_when_no_allowlist

    def dispatch(self, message: InboundMessage) -> OutboundMessage:
        """Handle one inbound message and return the reply to send back."""
        if not self.is_allowed(message.sender_id):
            logger.info("Blocked message from unauthorized sender %s", message.sender_id)
            return OutboundMessage(
                channel=message.channel,
                recipient_id=message.sender_id,
                text="Sorry — you're not authorized to use this assistant.",
            )

        session = self.session_key(message.channel, message.sender_id)
        try:
            # HIGH-002: wrap inbound channel text in the untrusted-content data envelope
            # before it reaches the LLM. Channel messages are untrusted third-party input
            # and can contain prompt-injection payloads aimed at hijacking the agent.
            source = f"{message.channel}:{message.sender_id}"
            guarded_text, _flagged = guard_untrusted(message.text, source=source)
            reply = self._runner(session, guarded_text)
        except Exception as e:  # never let one bad turn kill the receive loop
            logger.exception("Agent run failed for %s", session)
            reply = f"⚠️ Sorry, something went wrong handling your message: {e}"

        return OutboundMessage(
            channel=message.channel,
            recipient_id=message.sender_id,
            text=reply,
        )
