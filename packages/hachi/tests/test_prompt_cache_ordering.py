"""Prompt-cache-aware system-prompt ordering.

The stable brain/.og prefix must carry the cache breakpoint while the per-turn
time header and recalled context sit in a separate dynamic block AFTER it, so the
cached prefix is reused (0.1x reads) instead of rewritten every turn.
"""

from __future__ import annotations

from hachi.core.llm import LLMResponse, TokenUsage
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.sub_agent import SubAgentMemory
from hachi.core.turn_context import TurnContext

_BASE = "STABLE_BRAIN_AND_OG_CONTENT"


def test_turn_context_splits_stable_prefix_from_volatile_tail() -> None:
    tc = TurnContext.build(
        turn_id="t1",
        session_id="s1",
        user_input="hi",
        system_prompt_base=_BASE,
        recalled_context="RECALL_PAYLOAD",
        user_profile_snapshot="PROFILE_FACTS",
    )
    # Stable content is cacheable; volatile content is not in the cacheable block.
    assert _BASE in tc.cacheable_system
    assert "PROFILE_FACTS" in tc.cacheable_system  # session-frozen → cacheable
    assert _BASE not in tc.dynamic_system
    assert "CURRENT TIME" in tc.dynamic_system  # time header is per-turn
    assert "RECALL_PAYLOAD" in tc.dynamic_system  # recall is per-turn
    # Full prompt keeps the stable content first (model reads instructions first).
    assert tc.system_prompt.index(_BASE) < tc.system_prompt.index("CURRENT TIME")


class _SysRecordingLLM:
    model = "fake-model"

    def __init__(self) -> None:
        self.system_seen: str | None = None
        self.dynamic_seen: str | None = None

    def generate(self, **kwargs) -> LLMResponse:
        self.system_seen = kwargs.get("system_prompt")
        self.dynamic_seen = kwargs.get("dynamic_system")
        return LLMResponse(content="done", tool_calls=[], usage=TokenUsage())

    def generate_stream(self, **kwargs):  # noqa: ANN201
        response = self.generate(**kwargs)
        if False:
            yield ""
        return response


def test_loop_sends_cacheable_prefix_and_dynamic_tail_separately() -> None:
    tc = TurnContext.build(
        turn_id="t1",
        session_id="s1",
        user_input="hi",
        system_prompt_base=_BASE,
        recalled_context="RECALL_PAYLOAD",
    )
    llm = _SysRecordingLLM()
    loop = ExecutionLoop(llm, ToolRegistry(), SubAgentMemory(), base_system_prompt="x")
    loop.add_user_message("hi")
    loop.run(max_iterations=1, turn_context=tc)

    # The cached block is the stable prefix; the dynamic block carries time/recall.
    assert llm.system_seen is not None and _BASE in llm.system_seen
    assert "CURRENT TIME" not in llm.system_seen  # volatile content kept out of cache
    assert llm.dynamic_seen is not None and "CURRENT TIME" in llm.dynamic_seen
    assert "RECALL_PAYLOAD" in llm.dynamic_seen
    assert _BASE not in llm.dynamic_seen


def test_loop_falls_back_to_single_block_without_turn_context() -> None:
    llm = _SysRecordingLLM()
    loop = ExecutionLoop(llm, ToolRegistry(), SubAgentMemory(), base_system_prompt=_BASE)
    loop.add_user_message("hi")
    loop.run(max_iterations=1)  # no turn_context → legacy single-block path
    assert llm.system_seen is not None and _BASE in llm.system_seen
    assert llm.dynamic_seen is None
