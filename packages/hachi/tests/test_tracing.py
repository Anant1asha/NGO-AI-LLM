"""Tests for optional OpenTelemetry tracing.

Skipped automatically when the `tracing` extra isn't installed. The tracing CODE
no-ops without the SDK (verified by the rest of the suite running fine without it);
these tests verify the SDK-present behavior and the loop instrumentation.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk.trace")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from hachi.core import tracing  # noqa: E402
from hachi.core.llm import LLMResponse, ToolCall  # noqa: E402
from hachi.core.loop import ExecutionLoop, ToolRegistry  # noqa: E402
from hachi.core.sub_agent import SubAgentMemory  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_tracing():
    tracing._reset_for_tests()
    yield
    tracing._reset_for_tests()


def test_sdk_available() -> None:
    assert tracing.is_available() is True


def test_span_is_noop_before_setup() -> None:
    assert tracing.is_active() is False
    with tracing.span("anything", a=1):  # must not raise
        pass


def test_span_records_to_exporter() -> None:
    exporter = InMemorySpanExporter()
    assert tracing.setup_tracing(exporter=exporter, force=True) is True
    assert tracing.is_active() is True
    with tracing.span("tool.call", tool="echo"):
        pass
    spans = exporter.get_finished_spans()
    assert [s.name for s in spans] == ["tool.call"]
    assert spans[0].attributes.get("tool") == "echo"


def test_configure_from_env_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("HACHI_TRACING", raising=False)
    assert tracing.configure_from_env() is False
    assert tracing.is_active() is False


def test_configure_from_env_enables(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_TRACING", "true")
    assert tracing.configure_from_env() is True
    assert tracing.is_active() is True


def test_graceful_when_sdk_unavailable(monkeypatch) -> None:
    # Simulate the SDK being absent (the CI / no-extra environment): every entry
    # point must no-op safely without referencing any unimported OTel symbol.
    monkeypatch.setattr(tracing, "_OTEL_AVAILABLE", False)
    tracing._reset_for_tests()
    assert tracing.is_available() is False
    assert tracing.setup_tracing(exporter=object()) is False
    assert tracing.is_active() is False
    with tracing.span("x", a=1):  # no-op, no error
        pass
    monkeypatch.setenv("HACHI_TRACING", "true")
    assert tracing.configure_from_env() is False


def test_loop_emits_tool_and_llm_spans() -> None:
    exporter = InMemorySpanExporter()
    tracing.setup_tracing(exporter=exporter, force=True)

    registry = ToolRegistry()
    registry.register(
        {"name": "echo", "description": "d", "input_schema": {"type": "object", "properties": {}}},
        lambda **_kw: "ok",
    )

    class _ScriptedLLM:
        model = "fake-model"

        def __init__(self, responses):
            self._responses = responses
            self.calls = 0

        def generate(self, **_kwargs):
            resp = self._responses[min(self.calls, len(self._responses) - 1)]
            self.calls += 1
            return resp

        def generate_stream(self, **kwargs):
            response = self.generate(**kwargs)
            return response
            yield  # makes this a generator function

    responses = [
        LLMResponse(content="", tool_calls=[ToolCall(id="t1", name="echo", input={})]),
        LLMResponse(content="done", tool_calls=[]),
    ]
    loop = ExecutionLoop(
        _ScriptedLLM(responses), registry, SubAgentMemory(), base_system_prompt="x"
    )
    loop.add_user_message("go")
    loop.run(max_iterations=3)

    names = [s.name for s in exporter.get_finished_spans()]
    assert "tool.call" in names
    assert "llm.generate" in names
