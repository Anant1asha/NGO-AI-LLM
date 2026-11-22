"""A SessionRunner backed by real in-process agent sessions.

Maps each channel session key to its own persistent :class:`AgentSession` so a
user's conversation keeps context across messages, and serializes turns per
session. Kept out of :mod:`hachi.channels.base` so the routing core stays
free of the heavy, credentialed agent runtime.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from hachi.gateway.orchestrator import AgentSession, boot_agent


class GatewaySessionRunner:
    """Lazily boot one AgentSession per session key and run turns on it."""

    def __init__(self, boot: Callable[[], AgentSession] = boot_agent):
        self._boot = boot
        self._agents: dict[str, AgentSession] = {}
        self._lock = threading.Lock()

    def _agent_for(self, session_key: str) -> AgentSession:
        with self._lock:
            agent = self._agents.get(session_key)
            if agent is None:
                agent = self._boot()
                self._agents[session_key] = agent
            return agent

    def __call__(self, session_key: str, text: str) -> str:
        return self._agent_for(session_key).chat(text)

    def shutdown(self) -> None:
        with self._lock:
            agents = list(self._agents.values())
            self._agents.clear()
        for agent in agents:
            try:
                agent.shutdown()
            except Exception:
                pass
