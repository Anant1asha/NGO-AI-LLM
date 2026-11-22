"""P1-2 — hot-path model tiering tests.

Covers:
  1. classify_turn_capability maps short/simple prompts to REASONING (default),
     and long/coding/multi-step prompts to heavier capabilities (table-driven).
  2. When a router is present, run() classifies the turn, calls router.select()
     with the classified capability, and generates with the selected client.
  3. When router is None, llm_client is used unchanged (back-compat).
  4. A NoRouteError from select() falls back to llm_client (turn still completes).
  5. Sticky-per-turn: router.new_turn() is called once per run() so each turn
     re-selects independently.
"""

from __future__ import annotations

from typing import Any

import pytest

from hachi.core.llm import LLMResponse, TokenUsage
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.routing.capability import Capability
from hachi.core.routing.classifier import classify_turn_capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing
from hachi.core.routing.router import NoRouteError, ResolvedModel
from hachi.core.sub_agent import SubAgentMemory

# ---------------------------------------------------------------------------
# Test doubles — reused across all scenarios
# ---------------------------------------------------------------------------


class _CapturingLLMClient:
    """Fake LLM that records every generate/generate_stream call and returns a fixed response."""

    model: str

    def __init__(self, model: str = "capturing-client", response_text: str = "done") -> None:
        self.model = model
        self.calls: int = 0
        self.call_kwargs: list[dict[str, Any]] = []
        self._response_text = response_text

    def generate(self, **kwargs: Any) -> LLMResponse:
        self.calls += 1
        self.call_kwargs.append(kwargs)
        return LLMResponse(content=self._response_text, usage=TokenUsage())

    def generate_stream(self, **kwargs: Any):  # type: ignore[return]
        response = self.generate(**kwargs)

        def _gen():
            if response.content:
                yield response.content
            return response

        return _gen()


class _FakeRouter:
    """Minimal ModelRouter stub that records select() calls and returns a given client."""

    def __init__(self, selected_client: _CapturingLLMClient, descriptor: ModelDescriptor) -> None:
        self._client = selected_client
        self._descriptor = descriptor
        self.selected_capabilities: list[Capability] = []
        self.new_turn_calls: int = 0

    def new_turn(self) -> None:
        self.new_turn_calls += 1

    def select(self, capability: Capability, constraints: Any = None) -> ResolvedModel:
        self.selected_capabilities.append(capability)
        return ResolvedModel(client=self._client, descriptor=self._descriptor)


class _RaisingRouter:
    """Router whose select() always raises NoRouteError."""

    def __init__(self) -> None:
        self.new_turn_calls: int = 0

    def new_turn(self) -> None:
        self.new_turn_calls += 1

    def select(self, capability: Capability, constraints: Any = None) -> ResolvedModel:
        raise NoRouteError(capability, "no candidates in test")


def _make_descriptor(model_id: str = "test-model") -> ModelDescriptor:
    return ModelDescriptor(
        id=model_id,
        provider="anthropic",
        capabilities=frozenset({Capability.REASONING}),
        context_window=200_000,
        max_output=8_192,
        pricing=Pricing(input_per_mtok=1.0, output_per_mtok=5.0),
    )


def _make_loop_with_router(
    router: Any,
    *,
    fallback_response: str = "done",
    router_client_response: str = "routed",
    router_client_model: str = "routed-model",
) -> tuple[ExecutionLoop, _CapturingLLMClient, _CapturingLLMClient]:
    """Build a loop with a known fallback client and a router pointing to a second client.

    Returns (loop, fallback_llm_client, router_selected_client).
    """
    fallback = _CapturingLLMClient(model="fallback-model", response_text=fallback_response)
    loop = ExecutionLoop(
        llm_client=fallback,
        registry=ToolRegistry(),
        memory=SubAgentMemory(),
        base_system_prompt="test",
        router=router,
    )
    # The router's selected client is whoever the router points to — callers pass in router.
    return loop, fallback, getattr(router, "_client", fallback)


# ---------------------------------------------------------------------------
# 1. Classifier: capability mapping rules (table-driven)
# ---------------------------------------------------------------------------


class TestClassifyTurnCapability:
    """classify_turn_capability maps prompts to the right Capability."""

    @pytest.mark.parametrize(
        "prompt,expected_cap",
        [
            # Short simple prompts → REASONING (default/general bucket)
            ("Hello!", Capability.REASONING),
            ("What is the capital of France?", Capability.REASONING),
            ("", Capability.REASONING),
            ("Tell me a joke.", Capability.REASONING),
            # Code fences → CODING
            ("Here is my function:\n```python\ndef foo():\n    pass\n```", Capability.CODING),
            # Coding keywords (2+ hits) → CODING
            ("Please debug this function and fix the error in the import", Capability.CODING),
            ("Refactor this class and fix the exception handling", Capability.CODING),
            ("implement a pytest unittest for this function", Capability.CODING),
            # Long prompt (≥ 16 000 chars) → LONG_CONTEXT
            ("x" * 16_001, Capability.LONG_CONTEXT),
            # Long-context phrases → LONG_CONTEXT
            ("Please read the entire file and summarize it for me", Capability.LONG_CONTEXT),
            ("Here is the whole codebase, tell me what it does", Capability.LONG_CONTEXT),
            # Summarization phrases → SUMMARIZATION
            ("Can you summarize this document?", Capability.SUMMARIZATION),
            ("TL;DR of the above please", Capability.SUMMARIZATION),
            ("What are the key points of this article?", Capability.SUMMARIZATION),
            # Multi-step / analytical (long enough) → REASONING
            (
                "Please explain step by step how the OAuth2 flow works "
                "and why each step is necessary for security.",
                Capability.REASONING,
            ),
            (
                "Compare the pros and cons of using a microservices architecture "
                "versus a monolith for a small startup team of 5 engineers.",
                Capability.REASONING,
            ),
        ],
    )
    def test_classifier_mapping(self, prompt: str, expected_cap: Capability) -> None:
        result = classify_turn_capability(prompt)
        assert result == expected_cap, (
            f"classify_turn_capability({prompt[:60]!r}) → {result!r}, expected {expected_cap!r}"
        )

    def test_long_prompt_without_keywords_still_long_context(self) -> None:
        """Very long prompts trigger LONG_CONTEXT before any keyword check."""
        prompt = "Please help me with this. " * 700  # > 16 000 chars
        assert classify_turn_capability(prompt) == Capability.LONG_CONTEXT

    def test_coding_single_keyword_not_enough(self) -> None:
        """A single coding keyword below the threshold stays at the default."""
        # Only "implement" — one keyword, below threshold of 2
        result = classify_turn_capability("Please implement it")
        # Single keyword should NOT trigger CODING
        assert result != Capability.CODING

    def test_summarization_takes_priority_over_reasoning(self) -> None:
        """summarize in an analytical prompt → SUMMARIZATION, not REASONING."""
        prompt = (
            "Please summarize this report and explain the key trade-offs "
            "step by step so I understand the reasoning behind each conclusion."
        )
        assert classify_turn_capability(prompt) == Capability.SUMMARIZATION


# ---------------------------------------------------------------------------
# 2. When router present: run() selects via router.select() and generates with it
# ---------------------------------------------------------------------------


class TestHotPathRoutingWithRouter:
    def test_router_select_called_with_classified_capability(self) -> None:
        """run() calls router.select() with the capability from classify_turn_capability."""
        descriptor = _make_descriptor("routed-model")
        router_client = _CapturingLLMClient(model="routed-model", response_text="routed response")
        fake_router = _FakeRouter(selected_client=router_client, descriptor=descriptor)

        loop = ExecutionLoop(
            llm_client=_CapturingLLMClient(model="fallback"),
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=fake_router,
        )
        # Simple prompt → REASONING
        loop.run(turn_context=None)

        assert len(fake_router.selected_capabilities) == 1
        assert fake_router.selected_capabilities[0] == Capability.REASONING

    def test_generation_uses_router_selected_client_not_llm_client(self) -> None:
        """When router is present, generate() is called on the router's client, not llm_client."""
        descriptor = _make_descriptor("routed-model")
        router_client = _CapturingLLMClient(model="routed-model", response_text="routed response")
        fake_router = _FakeRouter(selected_client=router_client, descriptor=descriptor)
        fallback = _CapturingLLMClient(model="fallback")

        loop = ExecutionLoop(
            llm_client=fallback,
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=fake_router,
        )
        result = loop.run()

        # The routed client must have been called; the fallback must NOT.
        assert router_client.calls >= 1, "router_client should have been called for generation"
        assert fallback.calls == 0, "fallback llm_client must NOT be called when router is present"
        assert "routed response" in result

    def test_coding_prompt_routes_to_coding_capability(self) -> None:
        """A code-fence prompt triggers CODING capability selection.

        Verifies the classifier + loop integration: a prompt with a code fence
        causes the loop to call router.select() with Capability.CODING.
        """
        descriptor = _make_descriptor("coding-model")
        router_client = _CapturingLLMClient(model="coding-model", response_text="code answer")
        fake_router = _FakeRouter(selected_client=router_client, descriptor=descriptor)

        mem = SubAgentMemory()
        # Store the coding prompt as _last_user_query so run() picks it up
        # (this is the back-compat path: no TurnContext, reads from memory attribute).
        mem._last_user_query = "Please fix this:\n```python\ndef foo(): pass\n```"

        loop = ExecutionLoop(
            llm_client=_CapturingLLMClient(model="fallback"),
            registry=ToolRegistry(),
            memory=mem,
            base_system_prompt="test",
            router=fake_router,
        )
        loop.run()

        assert len(fake_router.selected_capabilities) == 1
        assert fake_router.selected_capabilities[0] == Capability.CODING

    def test_new_turn_called_once_per_run(self) -> None:
        """router.new_turn() is called exactly once at the start of each run()."""
        descriptor = _make_descriptor()
        router_client = _CapturingLLMClient(response_text="ok")
        fake_router = _FakeRouter(selected_client=router_client, descriptor=descriptor)

        loop = ExecutionLoop(
            llm_client=_CapturingLLMClient(model="fallback"),
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=fake_router,
        )

        assert fake_router.new_turn_calls == 0
        loop.run()
        assert fake_router.new_turn_calls == 1
        loop.run()
        assert fake_router.new_turn_calls == 2


# ---------------------------------------------------------------------------
# 3. When router is None: llm_client used unchanged (back-compat)
# ---------------------------------------------------------------------------


class TestNoRouterBackCompat:
    def test_no_router_uses_llm_client_directly(self) -> None:
        """When router=None, generate() is called on llm_client, not some routed client."""
        direct_client = _CapturingLLMClient(model="direct", response_text="direct response")

        loop = ExecutionLoop(
            llm_client=direct_client,
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=None,
        )
        result = loop.run()

        assert direct_client.calls >= 1
        assert "direct response" in result

    def test_no_router_llm_client_attribute_unchanged(self) -> None:
        """With no router, loop.llm_client is the exact object passed in."""
        client = _CapturingLLMClient(model="original")
        loop = ExecutionLoop(
            llm_client=client,
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
        )
        assert loop.llm_client is client
        assert loop.router is None

    def test_no_router_turn_client_equals_llm_client(self) -> None:
        """_turn_client is set to llm_client when no router configured."""
        client = _CapturingLLMClient(model="original")
        loop = ExecutionLoop(
            llm_client=client,
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
        )
        loop.run()
        # After run(), _turn_client must be the same object as llm_client (no routing).
        assert loop._turn_client is client


# ---------------------------------------------------------------------------
# 4. NoRouteError from select() falls back to llm_client (turn still completes)
# ---------------------------------------------------------------------------


class TestNoRouteErrorFallback:
    def test_no_route_error_falls_back_to_llm_client(self) -> None:
        """When router.select() raises NoRouteError, llm_client is used and turn completes."""
        raising_router = _RaisingRouter()
        direct_client = _CapturingLLMClient(model="fallback", response_text="fallback answer")

        loop = ExecutionLoop(
            llm_client=direct_client,
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=raising_router,
        )
        result = loop.run()

        # Turn must complete without raising.
        assert "fallback answer" in result
        # The fallback llm_client must have been used.
        assert direct_client.calls >= 1
        # new_turn() was still called before select() raised.
        assert raising_router.new_turn_calls == 1

    def test_no_route_error_does_not_propagate(self) -> None:
        """NoRouteError from the router must NEVER propagate out of run()."""
        raising_router = _RaisingRouter()
        loop = ExecutionLoop(
            llm_client=_CapturingLLMClient(response_text="ok"),
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=raising_router,
        )
        # This must not raise NoRouteError.
        try:
            loop.run()
        except NoRouteError:
            pytest.fail("NoRouteError must not propagate out of ExecutionLoop.run()")

    def test_arbitrary_router_exception_falls_back(self) -> None:
        """Any unexpected exception from router.select() falls back to llm_client."""

        class _BrokenRouter:
            def new_turn(self) -> None:
                pass

            def select(self, cap: Any, constraints: Any = None) -> Any:
                raise RuntimeError("simulated router crash")

        direct = _CapturingLLMClient(model="direct", response_text="safe answer")
        loop = ExecutionLoop(
            llm_client=direct,
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=_BrokenRouter(),
        )
        result = loop.run()
        assert "safe answer" in result
        assert direct.calls >= 1

    def test_no_route_error_logs_at_warning_not_debug(self, caplog: Any) -> None:
        """S3: a router falling back to llm_client is an operationally-visible event
        (the model actually used silently changed) — it must be logged at WARNING,
        not DEBUG, so it isn't invisible in normal operation.
        """
        import logging

        raising_router = _RaisingRouter()
        loop = ExecutionLoop(
            llm_client=_CapturingLLMClient(response_text="fallback answer"),
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=raising_router,
        )
        with caplog.at_level(logging.WARNING, logger="hachi.core.loop"):
            loop.run()

        assert any("routing" in r.getMessage().lower() for r in caplog.records), (
            "expected a WARNING log when the router falls back to llm_client"
        )

    def test_arbitrary_router_exception_logs_at_warning_not_debug(self, caplog: Any) -> None:
        """S3: an unexpected router exception falling back to llm_client must also
        be WARNING, not DEBUG — same visibility requirement as NoRouteError.
        """
        import logging

        class _BrokenRouter:
            def new_turn(self) -> None:
                pass

            def select(self, cap: Any, constraints: Any = None) -> Any:
                raise RuntimeError("simulated router crash")

        loop = ExecutionLoop(
            llm_client=_CapturingLLMClient(response_text="safe answer"),
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=_BrokenRouter(),
        )
        with caplog.at_level(logging.WARNING, logger="hachi.core.loop"):
            loop.run()

        assert any("routing" in r.getMessage().lower() for r in caplog.records), (
            "expected a WARNING log when the router raises an unexpected exception"
        )


# ---------------------------------------------------------------------------
# 5. Integration: multi-turn run with router — each turn re-selects
# ---------------------------------------------------------------------------


class TestMultiTurnRouterReset:
    def test_each_turn_calls_new_turn_once(self) -> None:
        """Multiple successive run() calls each reset the sticky cache once."""
        descriptor = _make_descriptor()
        router_client = _CapturingLLMClient(response_text="ok")
        fake_router = _FakeRouter(selected_client=router_client, descriptor=descriptor)

        loop = ExecutionLoop(
            llm_client=_CapturingLLMClient(model="fallback"),
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=fake_router,
        )

        for i in range(3):
            loop.run()
            assert fake_router.new_turn_calls == i + 1

    def test_turn_client_refreshed_per_run(self) -> None:
        """_turn_client is re-resolved on each run(), not reused from a prior turn."""
        descriptor = _make_descriptor()
        router_client = _CapturingLLMClient(response_text="ok")
        fake_router = _FakeRouter(selected_client=router_client, descriptor=descriptor)
        fallback = _CapturingLLMClient(model="fallback")

        loop = ExecutionLoop(
            llm_client=fallback,
            registry=ToolRegistry(),
            memory=SubAgentMemory(),
            base_system_prompt="test",
            router=fake_router,
        )

        loop.run()
        # After run(), _turn_client points to the router's selected client.
        assert loop._turn_client is router_client
        # fallback must not have been called.
        assert fallback.calls == 0
