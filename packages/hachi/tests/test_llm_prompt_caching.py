"""PERF-001: the message history must carry prompt-cache breakpoints.

Without a ``cache_control`` breakpoint on the ``messages`` array, the whole
conversation prefix (loaded .og skills + prior tool results) is re-billed at
full input price every turn — inflating spend and defeating the .og
token-efficiency moat. Anthropic allows at most 4 breakpoints, so we use
system (1) + last tool (1) + the last up-to-two messages (<=2).
"""

from __future__ import annotations

from typing import Any

from hachi.core.llm import AnthropicClient, Message


def _client() -> AnthropicClient:
    return AnthropicClient(api_key="test-key", model="claude-haiku-4-5", max_tokens=1024)


def _last_block_cached(content: Any) -> bool:
    return (
        isinstance(content, list)
        and bool(content)
        and isinstance(content[-1], dict)
        and content[-1].get("cache_control") == {"type": "ephemeral"}
    )


def _count_breakpoints(kwargs: dict[str, Any]) -> int:
    count = 0
    for block in kwargs.get("system", []) or []:
        if isinstance(block, dict) and "cache_control" in block:
            count += 1
    for tool in kwargs.get("tools", []) or []:
        if isinstance(tool, dict) and "cache_control" in tool:
            count += 1
    for msg in kwargs["messages"]:
        content = msg["content"]
        if isinstance(content, list):
            count += sum(
                1 for blk in content if isinstance(blk, dict) and "cache_control" in blk
            )
    return count


def test_last_two_messages_get_cache_breakpoint() -> None:
    client = _client()
    messages = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="hi"),
        Message(role="user", content="do the thing"),
    ]
    kwargs = client._build_kwargs(messages, system_prompt="sys", tools=None, dynamic_system=None)
    msgs = kwargs["messages"]
    assert _last_block_cached(msgs[-1]["content"])  # rolling breakpoint
    assert _last_block_cached(msgs[-2]["content"])  # second rolling breakpoint
    # An earlier message keeps its plain string content (no breakpoint).
    assert msgs[-3]["content"] == "hello"


def test_total_breakpoints_within_anthropic_limit() -> None:
    client = _client()
    messages = [Message(role="user", content=f"m{i}") for i in range(6)]
    tools = [{"name": "t1", "input_schema": {}}, {"name": "t2", "input_schema": {}}]
    kwargs = client._build_kwargs(
        messages, system_prompt="sys", tools=tools, dynamic_system="dyn"
    )
    count = _count_breakpoints(kwargs)
    assert count <= 4, f"Anthropic allows at most 4 cache breakpoints, got {count}"
    assert count == 4  # system(1) + last tool(1) + last two messages(2)


def test_single_message_string_becomes_cached_text_block() -> None:
    client = _client()
    kwargs = client._build_kwargs(
        [Message(role="user", content="solo")],
        system_prompt=None,
        tools=None,
        dynamic_system=None,
    )
    content = kwargs["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "solo"
    assert content[0]["cache_control"] == {"type": "ephemeral"}


def test_original_message_content_not_mutated() -> None:
    client = _client()
    msg = Message(
        role="user",
        content=[{"type": "tool_result", "tool_use_id": "x", "content": "ok"}],
    )
    before = dict(msg.content[-1])  # type: ignore[arg-type]
    client._build_kwargs([msg], system_prompt=None, tools=None, dynamic_system=None)
    # The stored message block must be untouched (no cache_control leak).
    assert "cache_control" not in msg.content[-1]  # type: ignore[operator]
    assert msg.content[-1] == before


def test_no_messages_does_not_error() -> None:
    client = _client()
    kwargs = client._build_kwargs([], system_prompt="sys", tools=None, dynamic_system=None)
    assert kwargs["messages"] == []
