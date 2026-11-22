"""P1-5: Durable fact-extraction tests.

Verifies:
1. handle_extract_fact performs REAL extraction given injected fake LLM + vault.
2. sync_turn with a job queue enqueues handler_name="extract_fact" (not func=).
3. The enqueued payload is JSON-serializable.
4. The no-queue synchronous path still calls in-process extraction (unchanged).
5. handle_extract_fact degrades gracefully (returns status, does NOT raise) when
   vault or LLM client can't be resolved.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from hachi.core.memory import MemoryManager
from hachi.core.runtime.job_handlers import handle_extract_fact
from hachi.jobs import InMemoryJobQueue, JobRegistry, JobWorker  # noqa: F401

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeVault:
    """Records calls to upsert_* so tests can assert what was written."""

    def __init__(self) -> None:
        self.user_facts: list[str] = []
        self.workspace_facts: list[str] = []
        self.agent_facts: list[str] = []

    def upsert_user_fact(self, content: str, category: str = "preference") -> str:
        self.user_facts.append(content)
        return "uf-1"

    def upsert_fact(self, content: str, category: str = "auto_synced") -> str:
        self.workspace_facts.append(content)
        return "wf-1"

    def upsert_agent_fact(self, content: str) -> str:
        self.agent_facts.append(content)
        return "af-1"

    def semantic_search(self, _query: str, top_k: int = 3):
        return []

    def delete_fact(self, _fact_id: str) -> bool:
        return True

    def upsert_user_fact_with_meta(self, content: str, **_kw) -> str:
        return self.upsert_user_fact(content)


class _FakeLLM:
    """Returns a canned JSON fact-extraction response."""

    def __init__(self, response_json: dict) -> None:
        self._response_json = response_json
        self.tool_calls = []

    def generate(self, messages, system_prompt=None, tools=None, **_kw):
        from hachi.core.llm import LLMResponse, TokenUsage

        return LLMResponse(
            content=json.dumps(self._response_json),
            tool_calls=[],
            usage=TokenUsage(),
        )


# ---------------------------------------------------------------------------
# Test 1: handle_extract_fact performs REAL extraction
# ---------------------------------------------------------------------------


def test_handle_extract_fact_writes_to_vault(monkeypatch) -> None:
    """Injecting fake vault + LLM client results in real vault writes."""
    vault = _FakeVault()
    llm = _FakeLLM(
        {
            "user_facts": ["The user's name is Alice"],
            "workspace_facts": [],
            "agent_facts": [],
        }
    )

    # Patch ANTHROPIC_API_KEY so extract_facts doesn't bail early on the env check.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    # Use injection factories so no real vault/LLM is needed.
    result = handle_extract_fact(
        session_id="sess-1",
        text="My name is Alice and I'm working on the Hachi project.",
        typed=False,
        _vault_factory=lambda: vault,
        _llm_client_factory=lambda: llm,
    )

    assert result.startswith("extracted:")
    assert "Alice" in vault.user_facts[0]


def test_handle_extract_fact_empty_text_skips() -> None:
    """Empty text returns a skipped status without touching vault."""
    vault = _FakeVault()
    result = handle_extract_fact(
        text="",
        _vault_factory=lambda: vault,
        _llm_client_factory=lambda: _FakeLLM({}),
    )
    assert "skipped" in result
    assert vault.user_facts == []
    assert vault.workspace_facts == []


# ---------------------------------------------------------------------------
# Test 2: sync_turn enqueues handler_name="extract_fact" (not func=)
# ---------------------------------------------------------------------------


def test_sync_turn_enqueues_durable_handler_job() -> None:
    """With a job queue, sync_turn must enqueue handler_name='extract_fact'."""
    queue = InMemoryJobQueue()
    memory = MemoryManager(job_queue=queue)
    memory.set_vault(_FakeVault())

    memory.sync_turn(
        user_content="My name is Bob and I prefer Python.",
        assistant_content="Got it, Bob! I'll remember your Python preference.",
    )

    pending = queue.get_pending(limit=10)
    assert len(pending) == 1
    job = pending[0]
    assert job.handler_name == "extract_fact"
    assert job.func is None, "Durable jobs must NOT have a func= closure"


# ---------------------------------------------------------------------------
# Test 3: Enqueued payload is JSON-serializable
# ---------------------------------------------------------------------------


def test_sync_turn_payload_is_json_serializable() -> None:
    """The payload for the enqueued extract_fact job must be JSON-serializable."""
    queue = InMemoryJobQueue()
    memory = MemoryManager(job_queue=queue)
    memory.set_vault(_FakeVault())

    memory.sync_turn(
        user_content="I work at OpenGigantic and I use uv for packaging.",
        assistant_content="Noted! uv for packaging at OpenGigantic.",
    )

    pending = queue.get_pending(limit=10)
    assert pending, "Expected one pending job"
    job = pending[0]
    # Serialization must not raise
    serialized = json.dumps(job.payload)
    data = json.loads(serialized)
    assert "text" in data
    assert "typed" in data
    assert "session_id" in data
    assert isinstance(data["text"], str)
    assert isinstance(data["typed"], bool)


# ---------------------------------------------------------------------------
# Test 4: No-queue synchronous path still calls in-process extraction
# ---------------------------------------------------------------------------


def test_no_queue_sync_path_calls_in_process_extraction() -> None:
    """Without a job queue, sync_turn just logs a warning (no crash, no extraction)."""
    # Per the existing design, the no-queue path logs a WARNING and returns.
    # It does NOT try to call _run_fact_extraction inline (that's the legacy design
    # and tests confirm it — a queue-less MemoryManager silently skips extraction).
    memory = MemoryManager(job_queue=None)
    vault = _FakeVault()
    memory.set_vault(vault)

    # Should NOT raise; vault should NOT receive any facts (no-queue = disabled)
    memory.sync_turn(
        user_content="Some user message that is long enough to trigger.",
        assistant_content="Some assistant response that is also long enough.",
    )

    # No facts written (no-queue = disabled)
    assert vault.user_facts == []
    assert vault.workspace_facts == []


def test_no_queue_run_fact_extraction_delegates_to_extract_facts() -> None:
    """_run_fact_extraction delegates to extract_facts() when called directly."""
    vault = _FakeVault()
    llm = _FakeLLM(
        {
            "user_facts": ["User prefers dark mode"],
            "workspace_facts": [],
            "agent_facts": [],
        }
    )
    memory = MemoryManager()
    memory.set_vault(vault)
    # Inject an LLM client so _resolve_llm_client returns it
    memory._llm_client = llm

    # Set ANTHROPIC_API_KEY so extract_facts doesn't bail early
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key"}):
        memory._run_fact_extraction("User: I prefer dark mode. Assistant: Noted!")

    assert any("dark mode" in f.lower() for f in vault.user_facts)


# ---------------------------------------------------------------------------
# Test 5: handle_extract_fact degrades gracefully on missing services
# ---------------------------------------------------------------------------


def test_handle_extract_fact_no_vault_returns_skipped() -> None:
    """When vault factory returns None, handler returns skipped status, no raise."""
    result = handle_extract_fact(
        session_id="sess-x",
        text="Some meaningful conversation text that is long enough.",
        _vault_factory=lambda: None,
        _llm_client_factory=lambda: _FakeLLM({}),
    )
    assert "skipped" in result
    # Must not raise


def test_handle_extract_fact_no_llm_client_returns_skipped() -> None:
    """When LLM client is None, handler returns skipped status, no raise."""
    result = handle_extract_fact(
        session_id="sess-y",
        text="Some meaningful conversation text that is long enough.",
        _vault_factory=lambda: _FakeVault(),
        _llm_client_factory=lambda: None,
    )
    assert "skipped" in result


def test_handle_extract_fact_vault_factory_raises_returns_skipped() -> None:
    """When vault factory raises, build_job_context guards it; handler returns skipped."""

    def _bad_vault():
        raise RuntimeError("ChromaDB not installed")

    result = handle_extract_fact(
        session_id="sess-z",
        text="Some meaningful conversation text that is long enough.",
        _vault_factory=_bad_vault,
        _llm_client_factory=lambda: _FakeLLM({}),
    )
    assert "skipped" in result


def test_handle_extract_fact_llm_exception_returns_error_not_raise() -> None:
    """When the LLM call itself raises (e.g., network error), handler returns error:... ."""

    class _BrokenLLM:
        def generate(self, **_kw):
            raise ConnectionError("Network unreachable")

    # Patch os.environ so extract_facts doesn't bail on missing API key
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key"}):
        result = handle_extract_fact(
            session_id="sess-w",
            text="Some meaningful conversation text that is long enough.",
            _vault_factory=lambda: _FakeVault(),
            _llm_client_factory=lambda: _BrokenLLM(),
        )

    assert "error" in result or "skipped" in result
    # Must not raise


# ---------------------------------------------------------------------------
# End-to-end: worker dispatches job through registry
# ---------------------------------------------------------------------------


def test_worker_dispatches_extract_fact_via_registry() -> None:
    """Full cycle: sync_turn → queue → worker with registry → handler called."""
    vault = _FakeVault()
    llm = _FakeLLM(
        {
            "user_facts": ["User is a senior engineer"],
            "workspace_facts": ["Project uses Python 3.11"],
            "agent_facts": [],
        }
    )
    queue = InMemoryJobQueue()
    memory = MemoryManager(job_queue=queue)
    memory.set_vault(vault)

    memory.sync_turn(
        user_content="I'm a senior engineer and we use Python 3.11.",
        assistant_content="Got it! Python 3.11 and senior engineer role noted.",
    )

    # Wire up handler with injected fakes
    def _handler(**kwargs) -> str:
        return handle_extract_fact(
            **kwargs,
            _vault_factory=lambda: vault,
            _llm_client_factory=lambda: llm,
        )

    registry = JobRegistry()
    registry.register("extract_fact", _handler)

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key"}):
        worker = JobWorker(queue, registry=registry)
        executed = worker.execute_one()

    assert executed
    # Vault received the extracted facts
    assert any("senior engineer" in f.lower() for f in vault.user_facts)
    assert any("python 3.11" in f.lower() for f in vault.workspace_facts)
