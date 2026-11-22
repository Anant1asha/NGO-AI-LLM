"""AgentSession.shutdown() must shut down the per-session tool thread pool.

Regression coverage: ``AgentSession.shutdown()`` closes the session store,
LLM clients, browser controller, memory vault, integrations, and MCP manager
— but never called ``self.loop.shutdown()``, which is what actually shuts
down ``ExecutionLoop._tool_pool`` (a ``ThreadPoolExecutor`` with 4 worker
threads created per session). Every session ended this way leaked its tool
thread pool for the lifetime of the process.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from hachi.gateway.orchestrator import AgentSession


def _minimal_agent_session() -> AgentSession:
    """Build a minimal AgentSession instance touching only what shutdown() reads.

    Mirrors the ``_agent_with()`` pattern in tests/test_mcp_lifecycle.py:
    ``AgentSession.__new__`` + manual attribute wiring, avoiding a full
    ``boot_agent`` bootstrap (LLM client, vault, DB, etc.) for a pure
    lifecycle/plumbing test.
    """
    agent = AgentSession.__new__(AgentSession)
    agent.loop = MagicMock()
    agent.loop.llm_client = None
    agent.memory = MagicMock()
    agent.memory.history = []
    agent.memory.vault = None
    agent.vault = None
    agent.integrations = MagicMock()
    agent.mcp_manager = MagicMock()
    agent.mcp_manager.server_count = 0
    agent._schedule_runner = None
    agent._resident_worker = None
    agent._job_worker = None
    agent._session_id = None
    agent._session_store = None
    agent._sub_agent_client = None
    agent._browser_controller = None
    agent._event_emitter = lambda *_a, **_kw: None
    return agent


class TestAgentSessionShutdown:
    def test_shutdown_shuts_down_tool_pool(self) -> None:
        agent = _minimal_agent_session()

        agent.shutdown()

        agent.loop.shutdown.assert_called_once()
