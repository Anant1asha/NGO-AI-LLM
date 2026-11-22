from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from hachi.cli.main import _InProcessGatewayRuntime
from hachi.core.runtime_events import RuntimeEvent
from hachi.core.runtime_read_models import RuntimeReadModelStore
from hachi.gateway.control_plane import GatewayProtocolError


class _FakeConfig:
    def __init__(self) -> None:
        self.memory = SimpleNamespace(
            enable_session_history=True,
            enable_semantic_memory=True,
        )

    def model_dump(self, mode: str = "python", exclude_none: bool = True):
        return {
            "memory": {
                "enable_session_history": self.memory.enable_session_history,
                "enable_semantic_memory": self.memory.enable_semantic_memory,
            }
        }


def test_update_memory_rejects_non_boolean_values(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    with pytest.raises(GatewayProtocolError, match="must be a boolean"):
        runtime.update_memory({"memory": {"enable_session_history": "false"}})


def test_update_memory_accepts_boolean_values(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    result = runtime.update_memory(
        {"memory": {"enable_session_history": False, "enable_semantic_memory": False}}
    )

    assert result["memory"]["enable_session_history"] is False
    assert result["memory"]["enable_semantic_memory"] is False


# Each booted agent owns a RuntimeReadModelStore — the single event log the
# gateway serves by sequence. These fakes stand in for that contract: events
# recorded on one agent's store are structurally invisible to another's.
class _StoreBackedAgent:
    def __init__(self) -> None:
        self._read_models = RuntimeReadModelStore()

    def emit(self, name: str, payload: dict) -> None:
        self._read_models.append_event(
            RuntimeEvent(name=name, payload=payload, timestamp="2026-06-06T10:00:00")
        )

    def chat(self, prompt: str) -> str:
        self.emit("text.stream.delta", {"text": prompt})
        return f"echo:{prompt}"

    def shutdown(self) -> None:
        return None

    def snapshot_events_since(self, after: int, limit: int = 100):
        return self._read_models.read_events_since(after, limit=limit)


def _fake_boot_agent(on_event=None, on_permission_request=None, resume_session_id=None):
    return _StoreBackedAgent()


def test_runtime_events_are_scoped_per_session(monkeypatch) -> None:
    monkeypatch.setattr("hachi.cli.main.boot_agent", _fake_boot_agent)

    runtime = _InProcessGatewayRuntime()
    runtime.register_connection("session-a", None)  # type: ignore[arg-type]
    runtime.register_connection("session-b", None)  # type: ignore[arg-type]

    response = runtime.chat("session-a", "private-from-a")
    assert response == "echo:private-from-a"

    a_events = runtime.read_events("session-a", after=0, limit=100)
    b_events = runtime.read_events("session-b", after=0, limit=100)

    assert any(event.payload.get("text") == "private-from-a" for event in a_events)
    assert all(event.payload.get("text") != "private-from-a" for event in b_events)


def test_runtime_events_remain_isolated_under_parallel_sessions(monkeypatch) -> None:
    monkeypatch.setattr("hachi.cli.main.boot_agent", _fake_boot_agent)

    runtime = _InProcessGatewayRuntime()
    runtime.register_connection("session-a", None)  # type: ignore[arg-type]
    runtime.register_connection("session-b", None)  # type: ignore[arg-type]

    a_prompts = [f"a-{idx}" for idx in range(20)]
    b_prompts = [f"b-{idx}" for idx in range(20)]

    def _run(session_id: str, prompts: list[str]) -> None:
        for prompt in prompts:
            runtime.chat(session_id, prompt)

    thread_a = threading.Thread(target=_run, args=("session-a", a_prompts))
    thread_b = threading.Thread(target=_run, args=("session-b", b_prompts))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    a_events = runtime.read_events("session-a", after=0, limit=500)
    b_events = runtime.read_events("session-b", after=0, limit=500)

    a_texts = {event.payload.get("text") for event in a_events}
    b_texts = {event.payload.get("text") for event in b_events}

    assert set(a_prompts).issubset(a_texts)
    assert set(b_prompts).issubset(b_texts)
    assert set(a_prompts).isdisjoint(b_texts)
    assert set(b_prompts).isdisjoint(a_texts)


def test_runtime_event_buffer_caps_at_2000_and_handles_sparse_cursors(monkeypatch) -> None:
    monkeypatch.setattr("hachi.cli.main.boot_agent", _fake_boot_agent)

    runtime = _InProcessGatewayRuntime()
    runtime.register_connection("session-a", None)  # type: ignore[arg-type]
    runtime.register_connection("session-b", None)  # type: ignore[arg-type]

    agent_a = runtime._get_agent("session-a")
    agent_b = runtime._get_agent("session-b")

    total_events = 2105
    for idx in range(total_events):
        agent_a.emit("text.stream.delta", {"text": f"a-{idx}"})
        agent_b.emit("text.stream.delta", {"text": f"b-{idx}"})

    a_events = runtime.read_events("session-a", after=0, limit=5000)
    b_events = runtime.read_events("session-b", after=0, limit=5000)

    assert len(a_events) == 2000
    assert len(b_events) == 2000
    assert a_events[0].sequence == 106
    assert b_events[0].sequence == 106
    assert a_events[0].payload["text"] == "a-105"
    assert b_events[0].payload["text"] == "b-105"

    sparse = runtime.read_events("session-a", after=2000, limit=200)
    assert len(sparse) == 105
    assert sparse[0].sequence == 2001
    assert sparse[-1].sequence == 2105

    beyond = runtime.read_events("session-a", after=999999, limit=50)
    assert beyond == []

    sparse_b = runtime.read_events("session-b", after=2000, limit=200)
    assert all(event.payload["text"].startswith("b-") for event in sparse_b)
