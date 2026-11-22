from __future__ import annotations

from types import SimpleNamespace

from hachi.core.loop import ToolRegistry
from hachi.core.memory import MemoryManager
from hachi.gateway.orchestrator import AgentSession
from hachi.jobs import InMemoryJobQueue, JobRegistry, JobWorker
from hachi.tools.memory_tools import register_memory_tools


class _FakeQueue:
    def __init__(self) -> None:
        self.jobs = []

    def enqueue(self, job):
        self.jobs.append(job)
        return "job-1"


class _FakeVault:
    def semantic_search(self, _query: str, top_k: int = 3):
        return []

    def upsert_fact(self, _content: str, _category: str = "workspace_state") -> str:
        return "fact-1"

    def delete_fact(self, _fact_id: str) -> bool:
        return True

    def upsert_user_fact(self, _content: str, _category: str = "preference") -> str:
        return "user-fact-1"

    def get_profile_stats(self):
        return {"entries": 0, "max_entries": 25}

    def search_user_profile(self, _query: str, top_k: int = 10):
        return []

    def delete_user_fact(self, _fact_id: str) -> bool:
        return True


class _PrefetchVault(_FakeVault):
    def semantic_search(self, query: str, top_k: int = 3):
        return [{"content": f"prefetch:{query}", "raw_content": f"prefetch:{query}"}]


class _SnapshotVault(_FakeVault):
    def __init__(self) -> None:
        self.user_snapshot = ""

    def get_user_snapshot(self) -> str:
        if not self.user_snapshot:
            return ""
        return "## User Profile\n- [name] " + self.user_snapshot

    def get_agent_snapshot(self) -> str:
        return ""


class _LoopStub:
    def __init__(self) -> None:
        self.base_system_prompt = "base"
        self.turn_prompts: list[str] = []

    def add_user_message(self, _text: str) -> None:
        return

    def run(self, turn_context):
        self.turn_prompts.append(turn_context.system_prompt)
        return "ok"


def test_core_save_memory_enqueues_job_when_queue_available() -> None:
    registry = ToolRegistry()
    queue = _FakeQueue()
    register_memory_tools(registry, _FakeVault(), job_queue=queue)

    tool = registry._tools["core_save_memory"]
    result = tool(facts=[{"content": "Project uses uv for dependency management."}])

    assert "queued" in result.lower()
    assert len(queue.jobs) == 1
    assert queue.jobs[0].name == "memory_smart_upsert"
    assert queue.jobs[0].job_type == "persist"


def test_sync_turn_rapid_enqueues_are_processed_once_each() -> None:
    # P1-5: sync_turn now enqueues handler_name="extract_fact" (durable path).
    # The worker needs a registry; we inject a fake handler to track invocations.
    queue = InMemoryJobQueue()
    memory = MemoryManager(job_queue=queue)
    memory.set_vault(_FakeVault())

    processed: list[str] = []

    def _fake_handler(
        session_id: str = "",
        text: str = "",
        typed: bool = False,
        **_kwargs,
    ) -> str:
        processed.append(text)
        return "extracted:0"

    registry = JobRegistry()
    registry.register("extract_fact", _fake_handler)

    for idx in range(30):
        memory.sync_turn(
            user_content=f"User turn {idx} wants stable memory extraction.",
            assistant_content=f"Assistant response {idx} with meaningful context.",
        )

    worker = JobWorker(queue, registry=registry)
    while worker.execute_one():
        continue

    assert len(processed) == 30
    assert len(set(processed)) == 30


def test_prefetch_queue_mid_drain_continues_without_duplicates() -> None:
    queue = InMemoryJobQueue()
    memory = MemoryManager(job_queue=queue)
    session = AgentSession(
        loop=SimpleNamespace(base_system_prompt=""),
        skill_engine=SimpleNamespace(),
        memory=memory,
        integrations=SimpleNamespace(shutdown=lambda: None),
        mcp_manager=SimpleNamespace(server_count=0, shutdown=lambda: None),
        permission_gate=SimpleNamespace(),
        model_name="test-model",
        job_queue=queue,
    )
    session.set_vault(_PrefetchVault())

    for idx in range(8):
        session._enqueue_prefetch_job(f"q{idx}", turn_id=f"turn-{idx}")

    assert session._job_worker is not None
    assert session._job_worker.execute_one() is True

    second_worker = JobWorker(queue, on_job_event=session._emit_event)
    while second_worker.execute_one():
        continue

    latest = session._pop_prefetch()
    assert latest
    assert latest[0]["content"] == "prefetch:q7"
    assert session._pop_prefetch() == []


def test_chat_refreshes_memory_snapshot_each_turn() -> None:
    loop = _LoopStub()
    memory = MemoryManager()
    vault = _SnapshotVault()

    session = AgentSession(
        loop=loop,
        skill_engine=SimpleNamespace(),
        memory=memory,
        integrations=SimpleNamespace(shutdown=lambda: None),
        mcp_manager=SimpleNamespace(server_count=0, shutdown=lambda: None),
        permission_gate=SimpleNamespace(),
        model_name="test-model",
    )
    session.set_vault(vault)

    vault.user_snapshot = "User's name is Chuck"
    session.chat("hello")

    vault.user_snapshot = "User's name is Charlie"
    session.chat("hello again")

    assert len(loop.turn_prompts) == 2
    assert "User's name is Chuck" in loop.turn_prompts[0]
    assert "User's name is Charlie" in loop.turn_prompts[1]
