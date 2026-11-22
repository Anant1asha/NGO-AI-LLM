"""
LLM Provider Abstraction Layer

This module provides a unified interface for interacting with various Large Language Models (LLMs).
By strictly programming to the `BaseLLMClient` interface, the Hachi agent remains entirely
model-agnostic, allowing seamless swapping between Anthropic, OpenAI, or local execution
(e.g., Ollama) without modifying the core agent loop.
"""

import abc
import json
import logging
import os
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import anthropic
import httpx
from pydantic import BaseModel, Field

from hachi.core.secret_store import SecretStore

logger = logging.getLogger(__name__)


def _synthesize_tool_call_id() -> str:
    """Generate a unique tool_use id for providers that stream an empty/constant one.

    BB-54: some OpenAI-compatible providers omit the ``id`` field on a
    tool-call delta (or reuse a constant placeholder). Pairing tool calls by
    id downstream (``ExecutionLoop``) would then collide — the second call's
    future/result silently overwrites the first's. A random uuid4-based id
    guarantees uniqueness within a response.
    """
    return f"call_{uuid.uuid4().hex}"


def _read_dotenv(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE dotenv file into a dictionary."""
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _resolve_api_key(api_key_env: str | None, explicit_api_key: str | None = None) -> str | None:
    """Resolve provider API key from explicit value, env var, then local project .env."""
    if explicit_api_key:
        return explicit_api_key
    if not api_key_env:
        return None

    env_name = str(api_key_env)
    from_env = os.environ.get(env_name)
    if from_env:
        return from_env

    # Fallback for local dev: allow project-level .env without requiring shell export.
    dotenv_values = _read_dotenv(Path.cwd() / ".env")
    return dotenv_values.get(env_name)


class Message(BaseModel):
    """
    Represents a standardized message in the conversation history.
    """

    role: str = Field(
        ..., description="The role of the speaker (e.g., 'user', 'assistant', 'system')."
    )
    content: str | list[dict[str, Any]] = Field(
        ..., description="The textual content of the message or a list of content blocks."
    )


class ToolCall(BaseModel):
    """
    Represents a tool execution requested by the LLM.
    """

    id: str = Field(..., description="The unique identifier for the tool call.")
    name: str = Field(..., description="The name of the tool to execute.")
    input: dict[str, Any] = Field(..., description="The arguments to pass to the tool.")
    parse_error: str | None = Field(
        default=None,
        description=(
            "Set when the provider's tool-call argument JSON was malformed or "
            "truncated (e.g. a max_tokens cutoff mid-tool-call). When set, "
            "``input`` is NOT a trustworthy reconstruction of the model's intent "
            "(BB-54) — callers (``ToolRegistry.execute``) must fail this specific "
            "call loudly instead of running the tool with empty/partial args."
        ),
    )


class TokenUsage(BaseModel):
    """Token accounting for a single LLM generation."""

    input_tokens: int = Field(default=0, description="Prompt/input tokens consumed.")
    output_tokens: int = Field(default=0, description="Generated/output tokens.")
    cache_read_tokens: int = Field(
        default=0, description="Input tokens served from the prompt cache (cheaper)."
    )
    cache_creation_tokens: int = Field(
        default=0, description="Input tokens written to the prompt cache (slightly pricier)."
    )


class LLMResponse(BaseModel):
    """
    Standardized response returned by any underlying LLM provider.
    """

    content: str = Field(default="", description="The textual response from the model.")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Any tool calls requested by the model."
    )
    usage: TokenUsage = Field(
        default_factory=TokenUsage, description="Token usage for this generation."
    )
    stop_reason: str | None = Field(
        default=None,
        description=(
            "The provider's raw stop/finish reason (e.g. Anthropic 'end_turn' / "
            "'max_tokens' / 'tool_use'; OpenAI-compat 'stop' / 'length' / "
            "'tool_calls'), when the provider reports one. Lets callers tell a "
            "clean completion apart from a max_tokens cutoff mid-tool-call (BB-54)."
        ),
    )


class BaseLLMClient(abc.ABC):
    """
    Abstract Base Class defining the contract for all LLM providers.
    Any new model provider must implement this interface.
    """

    @abc.abstractmethod
    def generate(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM based on the conversation history.

        Args:
            messages: The conversation history.
            system_prompt: Stable top-level instructions (the cacheable prefix).
            tools: Optional JSON Schema definitions of available tools.
            dynamic_system: Optional per-turn system content (time, recalled
                context) kept AFTER the cache breakpoint so it never invalidates
                the cached prefix. Providers without caching simply append it.

        Returns:
            An LLMResponse containing the text output and any requested tool calls.
        """
        pass

    def generate_stream(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> "Generator[str, None, LLMResponse]":
        """Stream text deltas; return the full LLMResponse as the generator return value.

        Providers that support native streaming (Anthropic, OpenAI-compat) override
        this method to yield tokens as they arrive. The default fallback calls
        ``generate()`` and yields the complete content as a single chunk — so all
        callers work correctly without requiring streaming support from every client.

        Usage (drive manually to capture the return value)::

            gen = client.generate_stream(messages, ...)
            try:
                while True:
                    chunk = next(gen)
                    emit_delta(chunk)
            except StopIteration as si:
                response = si.value  # full LLMResponse with tool_calls + usage

        Or use the helper::

            chunks, response = drain_stream(client.generate_stream(messages, ...))
        """
        response = self.generate(
            messages=messages,
            system_prompt=system_prompt,
            tools=tools,
            dynamic_system=dynamic_system,
        )
        if response.content:
            yield response.content
        return response

    def list_models(self) -> list[str]:
        """Return the model ids the provider currently exposes.

        Best-effort and network-bound: implementations must NEVER raise — they
        return ``[]`` when discovery is unavailable (offline, no endpoint, auth
        error) so callers can fall back to a curated/configured list.
        """
        return []

    @property
    def supports_vision(self) -> bool:
        """Return ``True`` when this client's model has the VISION capability.

        Derived from the model descriptor when available; defaults to ``False``
        on the base class so callers can check without string-matching the
        provider kind.  Concrete subclasses (or :class:`~hachi.core.resilience.ResilientClient`)
        override this by inspecting the resolved
        :class:`~hachi.core.routing.descriptor.ModelDescriptor`.
        """
        return False


def drain_stream(
    stream: "Generator[str, None, LLMResponse]",
) -> "tuple[list[str], LLMResponse]":
    """Drain a ``generate_stream()`` generator and return ``(chunks, final_response)``.

    Convenience helper for callers that need both the incremental text chunks and the
    final ``LLMResponse`` (tool calls, usage) without driving ``next()`` manually.
    """
    chunks: list[str] = []
    try:
        while True:
            chunks.append(next(stream))
    except StopIteration as si:
        return chunks, si.value


class AnthropicClient(BaseLLMClient):
    """
    Concrete implementation of BaseLLMClient for Anthropic's Claude models.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5",
        max_tokens: int = 4096,
        timeout: float | None = None,
    ):
        """
        Initialize the Anthropic client.

        Args:
            api_key: The Anthropic API key. If None, falls back to the ANTHROPIC_API_KEY
                environment variable.
            model: The target Claude model identifier.
            max_tokens: The maximum number of tokens to generate.
            timeout: Per-request timeout in seconds. None uses the SDK default (600s).
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be provided or set in the environment.")

        self.client = anthropic.Anthropic(api_key=self.api_key, timeout=timeout)
        self.model = model
        self.max_tokens = max_tokens

    @staticmethod
    def _cache_message_indices(count: int) -> list[int]:
        """Trailing message indices to mark with an ephemeral cache breakpoint.

        We cache the last up-to-two messages so the growing conversation prefix
        (loaded .og skills + prior tool results) is a cache hit on subsequent
        turns rather than being re-billed at full input price every turn
        (PERF-001).
        """
        if count <= 0:
            return []
        if count == 1:
            return [0]
        return [count - 2, count - 1]

    @staticmethod
    def _with_message_cache_control(
        content: str | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Copy an Anthropic message ``content`` with a cache breakpoint on its
        last block (a bare string becomes a single text block).  The original
        content is never mutated."""
        if isinstance(content, str):
            return [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
        blocks = list(content)
        if blocks and isinstance(blocks[-1], dict):
            blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
        return blocks

    def _build_kwargs(
        self,
        messages: list[Message],
        system_prompt: str | None,
        tools: list[dict[str, Any]] | None,
        dynamic_system: str | None,
    ) -> dict[str, Any]:
        """Build the kwargs dict shared by messages.create() and messages.stream()."""
        anthropic_messages = [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        # PERF-001: cache the conversation prefix too. Without a breakpoint on
        # the messages, the whole history (loaded .og skills + prior tool
        # results) is re-billed at full input price every turn — inflating spend
        # and defeating the .og token-efficiency moat. Anthropic allows up to 4
        # cache breakpoints; we use system (1) + tools (1) + the last <=2 messages.
        for _idx in self._cache_message_indices(len(anthropic_messages)):
            _msg = dict(anthropic_messages[_idx])
            _msg["content"] = self._with_message_cache_control(_msg["content"])
            anthropic_messages[_idx] = _msg
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
            "extra_headers": {"anthropic-beta": "prompt-caching-2024-07-31"},
        }
        if system_prompt:
            system_blocks: list[dict[str, Any]] = [
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
            ]
            if dynamic_system:
                system_blocks.append({"type": "text", "text": dynamic_system})
            kwargs["system"] = system_blocks
        if tools:
            tools_copy = list(tools)
            if tools_copy:
                last_tool = dict(tools_copy[-1])
                last_tool["cache_control"] = {"type": "ephemeral"}
                tools_copy[-1] = last_tool
            kwargs["tools"] = tools_copy
        return kwargs

    @staticmethod
    def _parse_message(msg: Any) -> LLMResponse:
        """Parse an Anthropic Message object into a standardised LLMResponse."""
        text_content = ""
        tool_calls: list[ToolCall] = []
        for block in msg.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
        raw_usage = getattr(msg, "usage", None)
        usage = TokenUsage(
            input_tokens=getattr(raw_usage, "input_tokens", 0) or 0,
            output_tokens=getattr(raw_usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(raw_usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(raw_usage, "cache_creation_input_tokens", 0) or 0,
        )
        raw_stop_reason = getattr(msg, "stop_reason", None)
        # Guard against non-string values (e.g. an unconfigured test double) —
        # a real Anthropic SDK Message always reports stop_reason as str|None.
        stop_reason = raw_stop_reason if isinstance(raw_stop_reason, str) else None
        return LLMResponse(
            content=text_content.strip(),
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=stop_reason,
        )

    def generate(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> LLMResponse:
        """Generate a response from Anthropic Claude using prompt caching."""
        kwargs = self._build_kwargs(messages, system_prompt, tools, dynamic_system)
        response = self.client.messages.create(**kwargs)
        return self._parse_message(response)

    def generate_stream(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> Generator[str, None, LLMResponse]:
        """Stream text deltas from Claude; return the full LLMResponse on exhaustion.

        Uses the Anthropic SDK's ``messages.stream()`` context manager. The HTTP
        connection is held open across ``yield`` points; the caller drives iteration
        with ``next()`` or by using ``drain_stream()``.
        """
        kwargs = self._build_kwargs(messages, system_prompt, tools, dynamic_system)
        final_msg: Any = None
        with self.client.messages.stream(**kwargs) as stream:
            yield from stream.text_stream
            final_msg = stream.get_final_message()
        return self._parse_message(final_msg)

    def list_models(self) -> list[str]:
        """List Claude models via the Anthropic models API (sorted; [] on error)."""
        try:
            page = self.client.models.list()
            ids = [str(m.id) for m in page.data if getattr(m, "id", None)]
            return sorted(ids)
        except Exception:
            return []


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI-compatible chat completions client (works for hosted and local endpoints)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        stream_usage: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        # Request usage metadata in streamed responses (OpenAI stream_options.include_usage).
        # Default True: every major hosted provider (OpenAI, Groq, Together, DeepSeek,
        # OpenRouter, Gemini-compat, recent Ollama/vLLM) supports it and without it the
        # final usage chunk is omitted — making token/cost accounting silently zero and
        # leaving the daily spend cap (P1-3) inert for all OpenAI-compat streaming turns.
        # Set stream_usage=False in the provider config ONLY for strict local servers that
        # return HTTP 400 on unknown request fields; that keeps chat working at the cost of
        # losing usage metrics for that provider.
        self._stream_usage: bool = stream_usage
        self._http = httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the underlying HTTP client and release its connections."""
        self._http.close()

    def __del__(self) -> None:
        """Safety-net finalizer — close the HTTP client if not already closed."""
        try:
            self._http.close()
        except Exception:
            pass

    @staticmethod
    def _adapt_messages(messages: list[Message]) -> list[dict[str, Any]]:
        """Convert Anthropic-format message history to OpenAI chat/completions format.

        Anthropic stores tool interactions as content blocks (tool_use / tool_result).
        OpenAI expects tool_calls on assistant messages and role="tool" for results.
        Plain-string messages pass through unchanged.
        """
        adapted: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                continue
            content = msg.content
            if isinstance(content, str):
                adapted.append({"role": msg.role, "content": content})
                continue
            if msg.role == "assistant":
                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                for block in content:
                    btype = block.get("type", "")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        tool_calls.append(
                            {
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block.get("input", {})),
                                },
                            }
                        )
                out: dict[str, Any] = {
                    "role": "assistant",
                    "content": " ".join(text_parts) or None,
                }
                if tool_calls:
                    out["tool_calls"] = tool_calls
                adapted.append(out)
            elif msg.role == "user":
                # tool_result blocks → individual role="tool" messages
                other_text: list[str] = []
                for block in content:
                    btype = block.get("type", "")
                    if btype == "tool_result":
                        rc = block.get("content", "")
                        if isinstance(rc, list):
                            rc = "\n".join(b.get("text", "") for b in rc if b.get("type") == "text")
                        adapted.append(
                            {
                                "role": "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content": str(rc),
                            }
                        )
                    elif btype == "text":
                        other_text.append(block.get("text", ""))
                if other_text:
                    adapted.append({"role": "user", "content": " ".join(other_text)})
            else:
                # Unexpected role — best-effort pass-through
                adapted.append(
                    {
                        "role": msg.role,
                        "content": content if isinstance(content, str) else str(content),
                    }
                )
        return adapted

    @staticmethod
    def _adapt_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not tools:
            return []

        adapted = []
        for tool in tools:
            adapted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", "tool"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get(
                            "input_schema", {"type": "object", "properties": {}}
                        ),
                    },
                }
            )
        return adapted

    def _build_request(
        self,
        messages: list[Message],
        system_prompt: str | None,
        tools: list[dict[str, Any]] | None,
        dynamic_system: str | None,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        """Return ``(headers, payload)`` for a /chat/completions request."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload_messages: list[dict[str, Any]] = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(self._adapt_messages(messages))
        # Volatile per-turn context (time header, recall) goes LAST, as its own
        # message, so it never mutates the stable system+tools prefix that OpenAI
        # auto-caches across turns (prompt caching is a prefix match). Appending it
        # to the system message — as we used to — changed the prefix every turn and
        # defeated OpenAI's automatic caching entirely (BB-29).
        if dynamic_system:
            payload_messages.append({"role": "system", "content": dynamic_system})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "max_tokens": self.max_tokens,
        }
        adapted_tools = self._adapt_tools(tools)
        if adapted_tools:
            payload["tools"] = adapted_tools
            payload["tool_choice"] = "auto"
        return headers, payload

    @staticmethod
    def _parse_tool_calls(raw_calls: list[Any]) -> list[ToolCall]:
        """Parse OpenAI-format tool_calls into ``ToolCall`` objects.

        BB-54: malformed/truncated argument JSON (e.g. a max_tokens cutoff
        mid-tool-call) must NOT silently become ``input={}`` — that lets the
        caller execute the tool with the wrong (empty) arguments as if the
        call had succeeded. Instead we log the failure and set
        ``ToolCall.parse_error`` so ``ToolRegistry.execute`` fails that
        specific call loudly. An empty/missing streamed id is replaced with a
        synthesized unique one so parallel tool calls can never collide when
        paired up by id downstream.
        """
        tool_calls: list[ToolCall] = []
        for raw_call in raw_calls or []:
            fn = raw_call.get("function", {})
            args_str = fn.get("arguments", "{}")
            name = str(fn.get("name", "unknown_tool"))
            parse_error: str | None = None
            try:
                args: dict[str, Any] = json.loads(args_str)
            except Exception as exc:
                logger.warning(
                    "OpenAICompatibleClient: malformed tool-call argument JSON for "
                    "tool %r (raw=%r): %s",
                    name,
                    args_str,
                    exc,
                )
                args = {}
                parse_error = f"malformed tool-call argument JSON: {exc}"
            call_id = str(raw_call.get("id") or "") or _synthesize_tool_call_id()
            tool_calls.append(ToolCall(id=call_id, name=name, input=args, parse_error=parse_error))
        return tool_calls

    @staticmethod
    def _usage_from_openai(raw: dict[str, Any]) -> TokenUsage:
        """Build a ``TokenUsage`` from an OpenAI-style ``usage`` object.

        OpenAI reports cached prompt tokens in ``prompt_tokens_details.cached_tokens``
        as a SUBSET of ``prompt_tokens``. We split them out into ``cache_read_tokens``
        so (a) the automatic prompt-cache discount is visible and (b) the fresh
        ``input_tokens`` portion isn't billed at full price for input that was
        actually served from cache. Providers that omit the field behave exactly as
        before (cached=0 → all prompt tokens counted as fresh input).
        """
        prompt_tokens = int(raw.get("prompt_tokens", 0) or 0)
        details = raw.get("prompt_tokens_details") or {}
        cached = int(details.get("cached_tokens", 0) or 0)
        cached = max(0, min(cached, prompt_tokens))  # never exceed prompt_tokens
        return TokenUsage(
            input_tokens=max(0, prompt_tokens - cached),
            output_tokens=int(raw.get("completion_tokens", 0) or 0),
            cache_read_tokens=cached,
        )

    def generate(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> LLMResponse:
        """Single-shot completion via the OpenAI-compatible /chat/completions endpoint."""
        headers, payload = self._build_request(messages, system_prompt, tools, dynamic_system)
        response = self._http.post(
            f"{self.base_url}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(content="", tool_calls=[])

        message = choices[0].get("message", {})
        content = message.get("content") or ""
        tool_calls = self._parse_tool_calls(message.get("tool_calls", []))
        raw_usage = data.get("usage", {}) or {}
        usage = self._usage_from_openai(raw_usage)
        stop_reason = choices[0].get("finish_reason")
        return LLMResponse(
            content=str(content).strip(),
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=stop_reason,
        )

    def generate_stream(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        dynamic_system: str | None = None,
    ) -> Generator[str, None, LLMResponse]:
        """Stream text deltas via SSE from an OpenAI-compatible endpoint.

        Accumulates tool-call argument fragments across chunks so that the returned
        ``LLMResponse`` contains complete ``ToolCall`` objects even when arguments
        span many SSE events. Usage metrics are included when the provider sends them
        in the final ``[DONE]`` chunk.
        """
        headers, payload = self._build_request(messages, system_prompt, tools, dynamic_system)
        payload["stream"] = True
        # Request usage in the final SSE chunk so token accounting and the daily spend cap
        # work correctly.  Omitted only when the operator explicitly sets stream_usage=False
        # for a strict local server that rejects unknown fields.
        if self._stream_usage:
            payload["stream_options"] = {"include_usage": True}

        text_parts: list[str] = []
        # Accumulate streaming tool-call fragments: {index: {id, name, args_parts}}
        tc_acc: dict[int, dict[str, Any]] = {}
        final_usage: TokenUsage = TokenUsage()
        final_stop_reason: str | None = None

        with self._http.stream(
            "POST", f"{self.base_url}/chat/completions", headers=headers, json=payload
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data: dict[str, Any] = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # Token usage sometimes arrives in the final chunk
                if "usage" in data and data["usage"]:
                    final_usage = self._usage_from_openai(data["usage"])

                choices = data.get("choices", [])
                if not choices:
                    continue
                finish_reason = choices[0].get("finish_reason")
                if finish_reason:
                    final_stop_reason = finish_reason
                delta = choices[0].get("delta", {})

                # Text delta
                text = delta.get("content")
                if text:
                    text_parts.append(text)
                    yield text

                # Tool-call fragments
                for tc_delta in delta.get("tool_calls", []) or []:
                    idx: int = tc_delta.get("index", 0)
                    if idx not in tc_acc:
                        tc_acc[idx] = {"id": "", "name": "", "args": []}
                    if tc_delta.get("id"):
                        tc_acc[idx]["id"] = tc_delta["id"]
                    fn = tc_delta.get("function", {})
                    if fn.get("name"):
                        tc_acc[idx]["name"] = fn["name"]
                    if fn.get("arguments"):
                        tc_acc[idx]["args"].append(fn["arguments"])

        # Reconstruct full tool calls. BB-54: truncated/malformed argument JSON
        # (e.g. a max_tokens cutoff mid-tool-call) must NOT silently become
        # input={} — log it and mark parse_error so the call fails loudly
        # instead of executing with the wrong (empty) arguments. An
        # empty/missing streamed id is replaced with a synthesized unique one
        # so parallel tool calls can never collide when paired up by id.
        tool_calls: list[ToolCall] = []
        for idx in sorted(tc_acc):
            acc = tc_acc[idx]
            args_str = "".join(acc["args"])
            parse_error: str | None = None
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "OpenAICompatibleClient: malformed/truncated tool-call argument "
                    "JSON for tool %r (raw=%r): %s",
                    acc["name"],
                    args_str,
                    exc,
                )
                args = {}
                parse_error = f"malformed/truncated tool-call argument JSON: {exc}"
            call_id = str(acc["id"] or "") or _synthesize_tool_call_id()
            tool_calls.append(
                ToolCall(id=call_id, name=acc["name"], input=args, parse_error=parse_error)
            )

        # S1: a real generation happened (text and/or tool calls were produced) but the
        # provider never sent a usage chunk, so final_usage is still the zero default.
        # Returning a hard 0 here silently under-counts real spend against any
        # configured cost/token cap (BUDGET_EXCEEDED would never fire for these calls).
        # We keep the zero-usage return value (callers already treat it as "unknown",
        # and a fabricated estimate could be worse than an honest zero) but make the
        # gap visible via a WARNING so operators can see spend is being under-tracked.
        if final_usage == TokenUsage() and (text_parts or tool_calls):
            logger.warning(
                "generate_stream: no usage data received from provider (stream_usage=%s) "
                "— cost/token tracking will under-count this call.",
                self._stream_usage,
            )

        return LLMResponse(
            content="".join(text_parts).strip(),
            tool_calls=tool_calls,
            usage=final_usage,
            stop_reason=final_stop_reason,
        )

    def list_models(self) -> list[str]:
        """List models via the OpenAI-compatible /models endpoint (sorted; [] on error).

        Works for hosted OpenAI-compatible providers and local Ollama (its
        /v1/models endpoint), which is how those are wired here.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = self._http.get(f"{self.base_url}/models", headers=headers)
            response.raise_for_status()
            data = response.json().get("data", [])
            ids = [str(m["id"]) for m in data if isinstance(m, dict) and m.get("id")]
            return sorted(ids)
        except Exception:
            return []


def resolve_available_models(
    discovered: list[str],
    allowed: list[str],
    current: str = "",
) -> list[str]:
    """The switchable model list for the UI.

    ``allowed`` (the config guardrail) is a HARD cap: when non-empty, the list is
    exactly the allowlist; otherwise it is whatever the provider exposed
    (``discovered``). The ``current`` model is always included so it can be shown
    and marked. Order is preserved and duplicates removed.
    """
    source = list(allowed) if allowed else list(discovered)
    result: list[str] = []
    for name in source:
        if name and name not in result:
            result.append(name)
    if current and current not in result:
        result.insert(0, current)
    return result


def can_switch_model(target: str, allowed: list[str]) -> bool:
    """Guardrail check: may ``target`` be selected?

    An empty ``allowed`` list means unrestricted. Otherwise the target must be a
    member of the allowlist.
    """
    if not allowed:
        return True
    return target in allowed


# Named OpenAI-compatible providers → their default base URL. All speak the same
# /chat/completions protocol, so one client serves them; a config `base_url` overrides.
_OPENAI_COMPAT_PRESETS: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "deepseek": "https://api.deepseek.com/v1",
    # Google Gemini — official OpenAI-compatible endpoint (free tier available).
    # Get a free key at https://aistudio.google.com/  (set GEMINI_API_KEY).
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def create_llm_client(
    provider_config: dict[str, Any], secret_store: SecretStore | None = None, max_tokens: int = 4096
) -> BaseLLMClient:
    """Build an LLM client from provider config plus secret references."""
    kind = str(provider_config.get("kind", "anthropic")).lower()
    model = str(provider_config.get("model", "claude-haiku-4-5"))
    api_key_ref = provider_config.get("api_key_ref")
    api_key_env = provider_config.get("api_key_env")
    base_url = provider_config.get("base_url")
    # stream_usage defaults True for all OpenAI-compat providers; operators of strict
    # local servers that reject unknown fields can set it False in provider config.
    stream_usage: bool = bool(provider_config.get("stream_usage", True))

    api_key: str | None = None
    if api_key_ref and secret_store is not None:
        api_key = secret_store.get(str(api_key_ref))
    if not api_key:
        api_key = _resolve_api_key(api_key_env)

    if kind == "anthropic":
        # Always prefer ANTHROPIC_API_KEY for this kind so a misconfigured
        # api_key_ref (e.g. the legacy default "OPENAI_API_KEY") doesn't shadow it.
        kind_key = _resolve_api_key("ANTHROPIC_API_KEY") or api_key
        return AnthropicClient(api_key=kind_key, model=model, max_tokens=max_tokens)

    if kind == "ollama":
        resolved_base = str(
            base_url or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434/v1"
        )
        return OpenAICompatibleClient(
            base_url=resolved_base,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            stream_usage=stream_usage,
        )

    if kind == "gemini":
        # Google Gemini — official OpenAI-compatible endpoint (free tier).
        # Falls back to GEMINI_API_KEY then GOOGLE_AI_API_KEY env vars.
        if not api_key:
            api_key = _resolve_api_key("GEMINI_API_KEY") or _resolve_api_key("GOOGLE_AI_API_KEY")
        resolved_base = str(base_url or _OPENAI_COMPAT_PRESETS["gemini"])
        # Default model if caller left the generic "claude-haiku-4-5" unchanged.
        if model == "claude-haiku-4-5":
            model = "gemini-2.0-flash"
        return OpenAICompatibleClient(
            base_url=resolved_base,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            stream_usage=stream_usage,
        )

    if kind == "chatgpt-web":
        # Unofficial ChatGPT web-session provider — opt-in only.
        # Requires HACHI_UNOFFICIAL=1 (see `pip install hachi-og[unofficial]`).
        if os.environ.get("HACHI_UNOFFICIAL") not in ("1", "true", "yes"):
            raise ValueError(
                "The chatgpt-web provider uses a reverse-engineered ChatGPT web API "
                "that may violate OpenAI's Terms of Service and risk account suspension.\n\n"
                "To opt in, set the environment variable:\n"
                "  HACHI_UNOFFICIAL=1\n\n"
                "Or install the unofficial extra and set the flag:\n"
                "  pip install hachi-og[unofficial]\n"
                "  export HACHI_UNOFFICIAL=1\n\n"
                "Only use this on accounts you own with full understanding of the risk."
            )
        from hachi.core.unofficial_providers import ChatGPTWebClient

        session_token = (
            api_key
            or _resolve_api_key("CHATGPT_SESSION_TOKEN")
            or _resolve_api_key("CHATGPT_ACCESS_TOKEN")
        )
        return ChatGPTWebClient(  # type: ignore[no-any-return]
            session_token=session_token,
            model=model if model != "claude-haiku-4-5" else "gpt-4o",
            max_tokens=max_tokens,
        )

    if kind in _OPENAI_COMPAT_PRESETS:
        # Named OpenAI-compatible providers (OpenRouter, Groq, Together, DeepSeek):
        # same wire protocol, different base URL. A config `base_url` still overrides.
        resolved_base = str(base_url or _OPENAI_COMPAT_PRESETS[kind])
        return OpenAICompatibleClient(
            base_url=resolved_base,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            stream_usage=stream_usage,
        )

    if kind in ("openai-compatible", "openai"):
        # "openai" is the kind on the bundled gpt-4o / gpt-4o-mini model descriptors;
        # it speaks the same wire protocol as "openai-compatible", just defaulting to
        # the canonical OpenAI base URL. Without this, routing to gpt-4o-mini raised
        # "Unsupported provider kind: openai" and silently fell back to the primary model.
        resolved_base = str(
            base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        )
        return OpenAICompatibleClient(
            base_url=resolved_base,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            stream_usage=stream_usage,
        )

    raise ValueError(f"Unsupported provider kind: {kind}")
