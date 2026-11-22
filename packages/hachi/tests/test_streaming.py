"""P2-01a — generate_stream() provider seam unit tests.

Verifies that:
  - BaseLLMClient default fallback yields one chunk = full content, returns LLMResponse
  - drain_stream() helper returns (chunks, LLMResponse)
  - AnthropicClient.generate_stream() yields SDK text_stream chunks (mocked SDK)
  - AnthropicClient.generate_stream() returns LLMResponse with tool_calls + usage
  - OpenAICompatibleClient.generate_stream() yields SSE text deltas (mocked httpx)
  - OpenAICompatibleClient.generate_stream() accumulates tool-call fragments across chunks
  - Existing single-shot generate() path is untouched (existing tests pass, no regression)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from hachi.core.llm import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    drain_stream,
)

# ---------------------------------------------------------------------------
# Helper: minimal concrete BaseLLMClient for testing the default fallback
# ---------------------------------------------------------------------------


class _MinimalClient:
    """Concrete client that only implements generate(); inherits generate_stream default."""

    model = "minimal"

    def __init__(self, response: LLMResponse) -> None:
        self._response = response
        self.generate_calls = 0

    def generate(self, **_kwargs: Any) -> LLMResponse:
        self.generate_calls += 1
        return self._response

    # generate_stream is inherited from BaseLLMClient (default fallback)
    # We can't actually inherit since _MinimalClient doesn't extend BaseLLMClient,
    # so we import the default from the ABC and call it directly.
    def generate_stream(self, **kwargs: Any):  # type: ignore[override]
        from hachi.core.llm import BaseLLMClient

        return BaseLLMClient.generate_stream(self, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Default fallback tests
# ---------------------------------------------------------------------------


def test_default_fallback_yields_content_as_one_chunk() -> None:
    client = _MinimalClient(LLMResponse(content="hello world", tool_calls=[]))
    gen = client.generate_stream(messages=[Message(role="user", content="hi")])
    chunks: list[str] = []
    try:
        while True:
            chunks.append(next(gen))
    except StopIteration:
        pass
    assert chunks == ["hello world"]


def test_default_fallback_returns_llm_response() -> None:
    resp = LLMResponse(
        content="answer",
        tool_calls=[ToolCall(id="tc1", name="tool_x", input={"k": "v"})],
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )
    client = _MinimalClient(resp)
    gen = client.generate_stream(messages=[Message(role="user", content="q")])
    chunks, final = drain_stream(gen)
    assert chunks == ["answer"]
    assert final.content == "answer"
    assert len(final.tool_calls) == 1
    assert final.tool_calls[0].name == "tool_x"
    assert final.usage.input_tokens == 10


def test_default_fallback_empty_content_yields_nothing() -> None:
    client = _MinimalClient(LLMResponse(content="", tool_calls=[]))
    gen = client.generate_stream(messages=[Message(role="user", content="q")])
    chunks, final = drain_stream(gen)
    assert chunks == []
    assert final.content == ""


def test_default_fallback_calls_generate_once() -> None:
    client = _MinimalClient(LLMResponse(content="done"))
    gen = client.generate_stream(messages=[Message(role="user", content="go")])
    drain_stream(gen)
    assert client.generate_calls == 1


# ---------------------------------------------------------------------------
# drain_stream helper
# ---------------------------------------------------------------------------


def test_drain_stream_returns_chunks_and_response() -> None:
    resp = LLMResponse(content="abc def", tool_calls=[])
    client = _MinimalClient(resp)
    chunks, final = drain_stream(
        client.generate_stream(messages=[Message(role="user", content="x")])
    )
    assert "".join(chunks) == "abc def"
    assert final is resp or final.content == "abc def"


# ---------------------------------------------------------------------------
# AnthropicClient.generate_stream() — mocked SDK
# ---------------------------------------------------------------------------


def _make_anthropic_client() -> Any:
    """Return an AnthropicClient with the Anthropic SDK patched so no API key needed."""
    from hachi.core.llm import AnthropicClient

    with patch("hachi.core.llm.anthropic.Anthropic") as mock_anthropic:
        client = AnthropicClient.__new__(AnthropicClient)
        client.api_key = "sk-test"
        client.model = "claude-test"
        client.max_tokens = 1024
        client.client = mock_anthropic()
    return client


def test_anthropic_generate_stream_yields_text_deltas() -> None:
    client = _make_anthropic_client()

    # Build a fake stream context manager
    fake_stream = MagicMock()
    fake_stream.__enter__ = MagicMock(return_value=fake_stream)
    fake_stream.__exit__ = MagicMock(return_value=False)
    fake_stream.text_stream = iter(["Hello", ", ", "world!"])

    # Final message with text content
    fake_final = MagicMock()
    fake_final.content = [MagicMock(type="text", text="Hello, world!")]
    fake_final.usage = MagicMock(
        input_tokens=8,
        output_tokens=5,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    fake_stream.get_final_message = MagicMock(return_value=fake_final)

    client.client.messages.stream = MagicMock(return_value=fake_stream)

    gen = client.generate_stream(messages=[Message(role="user", content="hi")])
    chunks, final = drain_stream(gen)

    assert chunks == ["Hello", ", ", "world!"]
    assert final.content == "Hello, world!"
    assert final.usage.input_tokens == 8
    assert final.usage.output_tokens == 5


def test_anthropic_generate_stream_returns_tool_calls() -> None:
    client = _make_anthropic_client()

    fake_stream = MagicMock()
    fake_stream.__enter__ = MagicMock(return_value=fake_stream)
    fake_stream.__exit__ = MagicMock(return_value=False)
    fake_stream.text_stream = iter([])  # no text — pure tool call response

    # 'name' is a special MagicMock constructor arg (sets repr); set it as attribute instead
    fake_tc = MagicMock()
    fake_tc.type = "tool_use"
    fake_tc.id = "call_1"
    fake_tc.name = "my_tool"
    fake_tc.input = {"x": 1}
    fake_final = MagicMock()
    fake_final.content = [fake_tc]
    fake_final.usage = MagicMock(
        input_tokens=5,
        output_tokens=3,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    fake_stream.get_final_message = MagicMock(return_value=fake_final)
    client.client.messages.stream = MagicMock(return_value=fake_stream)

    _, final = drain_stream(
        client.generate_stream(messages=[Message(role="user", content="use tool")])
    )

    assert len(final.tool_calls) == 1
    assert final.tool_calls[0].id == "call_1"
    assert final.tool_calls[0].name == "my_tool"
    assert final.tool_calls[0].input == {"x": 1}


def test_anthropic_generate_stream_passes_system_prompt() -> None:
    """generate_stream must include the system prompt in the SDK call kwargs."""
    client = _make_anthropic_client()

    fake_stream = MagicMock()
    fake_stream.__enter__ = MagicMock(return_value=fake_stream)
    fake_stream.__exit__ = MagicMock(return_value=False)
    fake_stream.text_stream = iter(["ok"])
    fake_final = MagicMock()
    fake_final.content = [MagicMock(type="text", text="ok")]
    fake_final.usage = MagicMock(
        input_tokens=1,
        output_tokens=1,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    fake_stream.get_final_message = MagicMock(return_value=fake_final)
    client.client.messages.stream = MagicMock(return_value=fake_stream)

    drain_stream(
        client.generate_stream(
            messages=[Message(role="user", content="hi")],
            system_prompt="You are a test assistant.",
        )
    )

    call_kwargs = client.client.messages.stream.call_args[1]
    assert "system" in call_kwargs
    system_blocks = call_kwargs["system"]
    assert any("You are a test assistant." in b.get("text", "") for b in system_blocks)


# ---------------------------------------------------------------------------
# OpenAICompatibleClient.generate_stream() — mocked httpx
# ---------------------------------------------------------------------------


def _make_openai_client() -> Any:
    from hachi.core.llm import OpenAICompatibleClient

    client = OpenAICompatibleClient.__new__(OpenAICompatibleClient)
    client.base_url = "https://api.example.com/v1"
    client.model = "gpt-test"
    client.api_key = "sk-test"
    client.max_tokens = 1024
    client._stream_usage = True  # mirror __init__ default (True = request include_usage)
    client._http = MagicMock()
    return client


def _sse_lines(*chunks: str, include_usage: bool = False) -> str:
    """Build a fake SSE response body with text delta chunks."""
    lines: list[str] = []
    for _i, text in enumerate(chunks):
        data: dict[str, Any] = {"choices": [{"delta": {"content": text}, "index": 0}]}
        lines.append(f"data: {json.dumps(data)}")
    if include_usage:
        usage_data = {"usage": {"prompt_tokens": 10, "completion_tokens": len(chunks)}}
        lines.append(f"data: {json.dumps(usage_data)}")
    lines.append("data: [DONE]")
    return "\n".join(lines)


def _make_mock_stream_response(lines_body: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.iter_lines = MagicMock(return_value=iter(lines_body.splitlines()))
    return mock_resp


def test_openai_stream_yields_text_deltas() -> None:
    client = _make_openai_client()
    body = _sse_lines("Hi ", "there", "!")
    client._http.stream = MagicMock(return_value=_make_mock_stream_response(body))

    gen = client.generate_stream(messages=[Message(role="user", content="hello")])
    chunks, final = drain_stream(gen)

    assert chunks == ["Hi ", "there", "!"]
    assert final.content == "Hi there!"


def test_openai_stream_captures_usage_from_final_chunk() -> None:
    client = _make_openai_client()
    body = _sse_lines("answer", include_usage=True)
    client._http.stream = MagicMock(return_value=_make_mock_stream_response(body))

    _, final = drain_stream(client.generate_stream(messages=[Message(role="user", content="q")]))

    assert final.usage.input_tokens == 10
    assert final.usage.output_tokens == 1


def test_openai_stream_splits_cached_prompt_tokens() -> None:
    # BB-28: OpenAI reports prompt_tokens_details.cached_tokens (a subset of
    # prompt_tokens). Split it into cache_read_tokens so the cache discount is
    # visible and fresh input_tokens isn't billed at full price for cached input.
    client = _make_openai_client()
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 5,
        "prompt_tokens_details": {"cached_tokens": 80},
    }
    lines = "\n".join(
        [
            f"data: {json.dumps({'choices': [{'delta': {'content': 'hi'}, 'index': 0}]})}",
            f"data: {json.dumps({'choices': [], 'usage': usage})}",
            "data: [DONE]",
        ]
    )
    client._http.stream = MagicMock(return_value=_make_mock_stream_response(lines))
    _, final = drain_stream(client.generate_stream(messages=[Message(role="user", content="q")]))
    assert final.usage.cache_read_tokens == 80
    assert final.usage.input_tokens == 20  # fresh = prompt_tokens - cached
    assert final.usage.output_tokens == 5


def test_openai_generate_splits_cached_prompt_tokens() -> None:
    client = _make_openai_client()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(
        return_value={
            "choices": [{"message": {"content": "hello"}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 5,
                "prompt_tokens_details": {"cached_tokens": 80},
            },
        }
    )
    client._http.post = MagicMock(return_value=resp)
    out = client.generate(messages=[Message(role="user", content="q")])
    assert out.usage.cache_read_tokens == 80
    assert out.usage.input_tokens == 20
    assert out.usage.output_tokens == 5


def test_openai_request_keeps_time_header_out_of_system_message() -> None:
    # BB-29: the volatile dynamic block (time header / recall) must NOT be
    # appended to the cacheable system message — that changes the prefix every
    # turn and defeats OpenAI's automatic prefix caching. It belongs in a
    # trailing message after the conversation.
    client = _make_openai_client()
    _headers, payload = client._build_request(
        messages=[Message(role="user", content="hello")],
        system_prompt="STABLE_BRAIN_PROMPT",
        tools=None,
        dynamic_system="--- CURRENT TIME AND DATE --- 2026-06-28 ...",
    )
    msgs = payload["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "STABLE_BRAIN_PROMPT"  # no time header appended
    assert "CURRENT TIME" not in msgs[0]["content"]
    # The dynamic block is present, as its own trailing entry (not in system[0]).
    assert any("CURRENT TIME" in (m.get("content") or "") for m in msgs[1:])
    # The real user message is preserved.
    assert any(m["role"] == "user" and "hello" in (m.get("content") or "") for m in msgs)


def test_openai_stream_accumulates_tool_call_fragments() -> None:
    """Tool-call arguments arrive in pieces; must be reassembled into one ToolCall."""
    client = _make_openai_client()

    # Simulate tool-call streaming: id/name in first chunk, args split across two
    chunks_data = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_99",
                                "type": "function",
                                "function": {"name": "search", "arguments": ""},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"q":'}}]}}
            ]
        },
        {
            "choices": [
                {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"cats"}'}}]}}
            ]
        },
    ]
    lines = "\n".join(f"data: {json.dumps(d)}" for d in chunks_data) + "\ndata: [DONE]"

    mock_resp = _make_mock_stream_response(lines)
    client._http.stream = MagicMock(return_value=mock_resp)

    _, final = drain_stream(
        client.generate_stream(messages=[Message(role="user", content="search")])
    )

    assert len(final.tool_calls) == 1
    tc = final.tool_calls[0]
    assert tc.id == "call_99"
    assert tc.name == "search"
    assert tc.input == {"q": "cats"}


def test_openai_stream_empty_lines_ignored() -> None:
    """Empty lines and non-data lines in the SSE stream must be ignored safely."""
    client = _make_openai_client()
    lines = "\n: keepalive\n\ndata: [DONE]"
    mock_resp = _make_mock_stream_response(lines)
    client._http.stream = MagicMock(return_value=mock_resp)

    chunks, final = drain_stream(
        client.generate_stream(messages=[Message(role="user", content="hi")])
    )

    assert chunks == []
    assert final.content == ""


# ---------------------------------------------------------------------------
# stream_usage / stream_options tests (COST-1 fix)
# ---------------------------------------------------------------------------


def test_openai_stream_default_sends_stream_options() -> None:
    """generate_stream default: payload must include stream_options={"include_usage": True}."""
    client = _make_openai_client()  # _stream_usage=True is set by the helper

    body = _sse_lines("ok")
    mock_resp = _make_mock_stream_response(body)
    client._http.stream = MagicMock(return_value=mock_resp)

    drain_stream(client.generate_stream(messages=[Message(role="user", content="hi")]))

    call_kwargs = client._http.stream.call_args
    sent_payload = call_kwargs[1]["json"]  # keyword arg: json=payload
    assert sent_payload.get("stream") is True
    assert sent_payload.get("stream_options") == {"include_usage": True}


def test_openai_stream_opt_out_omits_stream_options() -> None:
    """When stream_usage=False the payload must NOT contain stream_options."""
    from hachi.core.llm import OpenAICompatibleClient

    # Build via __init__ so stream_usage=False is wired through the normal code path.
    client = OpenAICompatibleClient(
        base_url="https://api.example.com/v1",
        model="gpt-test",
        api_key="sk-test",
        max_tokens=1024,
        stream_usage=False,
    )
    client._http = MagicMock()

    body = _sse_lines("ok")
    mock_resp = _make_mock_stream_response(body)
    client._http.stream = MagicMock(return_value=mock_resp)

    drain_stream(client.generate_stream(messages=[Message(role="user", content="hi")]))

    call_kwargs = client._http.stream.call_args
    sent_payload = call_kwargs[1]["json"]
    assert sent_payload.get("stream") is True
    assert "stream_options" not in sent_payload

    client.close()


def test_openai_stream_usage_captured_from_final_chunk() -> None:
    """Simulate a stream whose FINAL chunk has empty choices + usage; verify usage captured."""
    client = _make_openai_client()  # _stream_usage=True is set by the helper

    # Two content chunks, then a usage-only final chunk, then [DONE]
    content_chunks = [
        json.dumps({"choices": [{"delta": {"content": "Hello"}, "index": 0}]}),
        json.dumps({"choices": [{"delta": {"content": " world"}, "index": 0}]}),
        # Final usage-only chunk: empty choices list + usage field (OpenAI spec)
        json.dumps({"choices": [], "usage": {"prompt_tokens": 123, "completion_tokens": 45}}),
        "[DONE]",
    ]
    sse_body = "\n".join(f"data: {line}" for line in content_chunks)

    mock_resp = _make_mock_stream_response(sse_body)
    client._http.stream = MagicMock(return_value=mock_resp)

    chunks, final = drain_stream(
        client.generate_stream(messages=[Message(role="user", content="hi")])
    )

    assert chunks == ["Hello", " world"]
    assert final.content == "Hello world"
    assert final.usage.input_tokens == 123
    assert final.usage.output_tokens == 45


def test_openai_stream_no_usage_chunk_returns_zeros() -> None:
    """A stream with NO usage chunk must still return a valid LLMResponse with usage zeros."""
    client = _make_openai_client()  # _stream_usage=True is set by the helper

    body = _sse_lines("pong")
    mock_resp = _make_mock_stream_response(body)
    client._http.stream = MagicMock(return_value=mock_resp)

    chunks, final = drain_stream(
        client.generate_stream(messages=[Message(role="user", content="ping")])
    )

    assert chunks == ["pong"]
    assert final.content == "pong"
    # No usage chunk → graceful zero fallback
    assert final.usage == TokenUsage()
    assert final.usage.input_tokens == 0
    assert final.usage.output_tokens == 0


def test_openai_stream_no_usage_chunk_logs_warning(caplog: Any) -> None:
    """S1: real content was generated but usage came back all-zero (unknown) — this
    silently under-counts spend against any configured cost/token cap, so it must be
    logged at WARNING (not silently swallowed), even though the zero-usage fallback
    return value itself is unchanged (see test_openai_stream_no_usage_chunk_returns_zeros).
    """
    import logging

    client = _make_openai_client()  # _stream_usage=True is set by the helper

    body = _sse_lines("pong")
    mock_resp = _make_mock_stream_response(body)
    client._http.stream = MagicMock(return_value=mock_resp)

    with caplog.at_level(logging.WARNING, logger="hachi.core.llm"):
        drain_stream(client.generate_stream(messages=[Message(role="user", content="ping")]))

    assert any("usage" in r.getMessage().lower() for r in caplog.records), (
        "expected a WARNING log when a stream completes with unknown/zero usage"
    )


# ---------------------------------------------------------------------------
# Existing generate() path unchanged (regression guard)
# ---------------------------------------------------------------------------


def test_anthropic_generate_still_works_after_refactor() -> None:
    """Refactoring generate() to use _build_kwargs must not change its behaviour."""
    from hachi.core.llm import AnthropicClient

    client = AnthropicClient.__new__(AnthropicClient)
    client.api_key = "sk-test"
    client.model = "claude-haiku-4-5"
    client.max_tokens = 1024

    fake_response = MagicMock()
    fake_response.content = [MagicMock(type="text", text="legacy answer")]
    fake_response.usage = MagicMock(
        input_tokens=3,
        output_tokens=2,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=fake_response)
    client.client = mock_client

    result = client.generate(messages=[Message(role="user", content="hi")])
    assert result.content == "legacy answer"
    assert result.usage.input_tokens == 3


def test_openai_generate_still_works_after_refactor() -> None:
    """Refactoring generate() to use _build_request must not change its behaviour."""
    client = _make_openai_client()
    client._http.post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value={
                    "choices": [{"message": {"content": "legacy reply", "tool_calls": []}}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }
            ),
            raise_for_status=MagicMock(),
        )
    )

    result = client.generate(messages=[Message(role="user", content="test")])
    assert result.content == "legacy reply"
    assert result.usage.input_tokens == 4


# ---------------------------------------------------------------------------
# BB-54 — malformed/truncated tool-arg JSON must NOT silently execute with
# input={}; must be logged and the specific tool call must carry a visible
# parse_error instead of empty args.
# ---------------------------------------------------------------------------


def test_openai_generate_malformed_tool_json_sets_parse_error(caplog: Any) -> None:
    """Non-streaming: malformed tool-call argument JSON must not become input={}."""
    import logging

    client = _make_openai_client()
    client._http.post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_bad",
                                        "type": "function",
                                        "function": {
                                            "name": "transfer_funds",
                                            # Truncated JSON — e.g. cut off mid-object by
                                            # a max_tokens stop.
                                            "arguments": '{"amount": 500, "account":',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }
            ),
            raise_for_status=MagicMock(),
        )
    )

    with caplog.at_level(logging.WARNING):
        result = client.generate(messages=[Message(role="user", content="pay someone")])

    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    # The dangerous behaviour this regression guards against: treating empty
    # args as a *successful* parse instead of visibly flagging the failure.
    assert tc.parse_error, "ToolCall.parse_error must be set on malformed JSON"
    assert any(
        "transfer_funds" in r.message or "parse" in r.message.lower() for r in caplog.records
    ), "malformed tool-arg JSON must be logged, not silently swallowed"


def test_openai_stream_truncated_tool_json_sets_parse_error(caplog: Any) -> None:
    """Streaming: JSON truncated mid-object (e.g. max_tokens cutoff) must not become input={}."""
    import logging

    client = _make_openai_client()

    chunks_data = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_trunc",
                                "type": "function",
                                "function": {"name": "search", "arguments": '{"q": "cats"'},
                            }
                        ]
                    }
                }
            ]
        },
    ]
    # No closing brace ever arrives — simulates a max_tokens cutoff mid-tool-call.
    lines = (
        "\n".join(f"data: {json.dumps(d)}" for d in chunks_data)
        + f"\ndata: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'length'}]})}"
        + "\ndata: [DONE]"
    )
    mock_resp = _make_mock_stream_response(lines)
    client._http.stream = MagicMock(return_value=mock_resp)

    with caplog.at_level(logging.WARNING):
        _, final = drain_stream(
            client.generate_stream(messages=[Message(role="user", content="search")])
        )

    assert len(final.tool_calls) == 1
    tc = final.tool_calls[0]
    assert tc.parse_error, "ToolCall.parse_error must be set on truncated JSON"
    assert any("search" in r.message or "parse" in r.message.lower() for r in caplog.records), (
        "truncated tool-arg JSON must be logged, not silently swallowed"
    )


# ---------------------------------------------------------------------------
# BB-54 — empty/constant streamed tool_use_id must not collide across calls.
# ---------------------------------------------------------------------------


def test_openai_stream_empty_tool_use_id_gets_synthesized_unique_ids() -> None:
    """Two parallel tool calls that both stream an empty id must not collide."""
    client = _make_openai_client()

    chunks_data = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "",  # some providers stream an empty id
                                "type": "function",
                                "function": {"name": "tool_a", "arguments": "{}"},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 1,
                                "id": "",  # ...and the second call also arrives empty
                                "type": "function",
                                "function": {"name": "tool_b", "arguments": "{}"},
                            }
                        ]
                    }
                }
            ]
        },
    ]
    lines = "\n".join(f"data: {json.dumps(d)}" for d in chunks_data) + "\ndata: [DONE]"
    mock_resp = _make_mock_stream_response(lines)
    client._http.stream = MagicMock(return_value=mock_resp)

    _, final = drain_stream(
        client.generate_stream(messages=[Message(role="user", content="do both")])
    )

    assert len(final.tool_calls) == 2
    ids = [tc.id for tc in final.tool_calls]
    assert all(i for i in ids), "every ToolCall must have a non-empty id"
    assert len(set(ids)) == 2, f"synthesized ids must be unique, got {ids}"


# ---------------------------------------------------------------------------
# BB-54 — stop_reason/finish_reason must be surfaced on LLMResponse so callers
# can distinguish a clean completion from a max_tokens mid-tool-call cutoff.
# ---------------------------------------------------------------------------


def test_anthropic_generate_surfaces_stop_reason() -> None:
    from hachi.core.llm import AnthropicClient

    client = AnthropicClient.__new__(AnthropicClient)
    client.api_key = "sk-test"
    client.model = "claude-haiku-4-5"
    client.max_tokens = 1024

    fake_response = MagicMock()
    fake_response.content = [MagicMock(type="text", text="cut off mid")]
    fake_response.stop_reason = "max_tokens"
    fake_response.usage = MagicMock(
        input_tokens=3,
        output_tokens=2,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=fake_response)
    client.client = mock_client

    result = client.generate(messages=[Message(role="user", content="hi")])
    assert result.stop_reason == "max_tokens"


def test_openai_generate_surfaces_finish_reason() -> None:
    client = _make_openai_client()
    client._http.post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(
                return_value={
                    "choices": [{"message": {"content": "cut off"}, "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }
            ),
            raise_for_status=MagicMock(),
        )
    )

    result = client.generate(messages=[Message(role="user", content="test")])
    assert result.stop_reason == "length"


def test_openai_stream_surfaces_finish_reason() -> None:
    client = _make_openai_client()
    body = (
        f"data: {json.dumps({'choices': [{'delta': {'content': 'hi'}, 'index': 0}]})}\n"
        f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'max_tokens'}]})}\n"
        "data: [DONE]"
    )
    mock_resp = _make_mock_stream_response(body)
    client._http.stream = MagicMock(return_value=mock_resp)

    _, final = drain_stream(client.generate_stream(messages=[Message(role="user", content="q")]))
    assert final.stop_reason == "max_tokens"
