"""Regression tests for delegation credential propagation.

Bug: spawning a sub-agent failed with "ANTHROPIC_API_KEY must be provided or set
in the environment" even though the main agent was working, because the sub-agent
built a bare LLM client instead of reusing the credential-resolved one. These
tests pin the fix: the injected client is used and no env key is required.
"""

from __future__ import annotations

from hachi.core.llm import LLMResponse
from hachi.core.loop import ToolRegistry
from hachi.core.sub_agent import SubAgentRuntime, SubAgentStatus
from hachi.tools.delegation_tools import _make_delegate_task


class _FakeLLM:
    """Minimal LLM client that finishes immediately (no tool calls)."""

    model = "fake-model"

    def generate(self, messages, system_prompt=None, tools=None):  # noqa: ANN001, ANN201
        return LLMResponse(content="sub-agent finished the task")

    def generate_stream(self, **kwargs):  # noqa: ANN201
        response = self.generate(**kwargs)
        if False:
            yield ""
        return response


def test_sub_agent_uses_injected_client(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runtime = SubAgentRuntime(role="analyst", task="do a thing", llm_client=_FakeLLM())
    report = runtime.run()
    assert report.status == SubAgentStatus.SUCCESS
    assert "finished" in report.summary


def test_delegate_task_passes_resolved_client(monkeypatch) -> None:
    # No env key set: success is only possible if the injected client is used.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    delegate = _make_delegate_task(
        ToolRegistry(),
        gate=None,
        on_event=None,
        vault=None,
        job_queue=None,
        sub_agent_llm=_FakeLLM(),
    )
    result = delegate("analyst", "run a quick analysis")
    assert "Status: success" in result
    assert "ANTHROPIC_API_KEY" not in result  # the old credential error is gone


def test_delegate_task_without_client_still_reports_cleanly(monkeypatch) -> None:
    # Defensive: with no client and no env key, delegation must fail gracefully
    # with a structured report rather than crashing the orchestrator turn.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    delegate = _make_delegate_task(ToolRegistry(), sub_agent_llm=None)
    result = delegate("analyst", "run a quick analysis")
    assert "[Sub-Agent Report: analyst]" in result
    assert "Status:" in result
