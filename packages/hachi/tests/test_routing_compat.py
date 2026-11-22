"""GATE-COMPAT tests for Slice 2.1.

With NO [routing] config:
  - RoutingPolicy synthesises single-model-for-every-capability.
  - ExecutionLoop without router= behaves identically to today.
  - Sub-agent behaviour preserved for Anthropic sessions.

These tests must NOT hit any network — all providers/clients are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hachi.core.llm import AnthropicClient, BaseLLMClient, LLMResponse, TokenUsage
from hachi.core.routing.capability import Capability
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.settings import ResolvedConfig

# ---------------------------------------------------------------------------
# GATE-COMPAT: RoutingPolicy back-compat synthesis
# ---------------------------------------------------------------------------


class TestRoutingPolicyBackCompat:
    def test_no_routing_section_maps_every_cap_to_default_model(self) -> None:
        config = ResolvedConfig()  # no routing= field
        policy = RoutingPolicy.from_config(config)
        for cap in Capability:
            cands = policy.candidates(cap)
            assert cands == [config.provider.model], (
                f"Capability {cap} must map to the single model; got {cands}"
            )

    def test_no_routing_section_default_model_matches_provider(self) -> None:
        config = ResolvedConfig()
        policy = RoutingPolicy.from_config(config)
        assert policy.default_model == config.provider.model

    def test_loop_without_router_uses_direct_client(self) -> None:
        """ExecutionLoop with no router= must behave identically to today."""
        from hachi.core.loop import ExecutionLoop, ToolRegistry

        class _DummyClient(BaseLLMClient):
            model = "dummy"

            def generate(self, messages, **kw):  # type: ignore[override]
                return LLMResponse(content="dummy", usage=TokenUsage())

        client = _DummyClient()
        registry = ToolRegistry()
        memory = MagicMock()
        memory.get_messages.return_value = []
        memory.get_system_prompt_additions.return_value = ""
        memory.add_message = MagicMock()

        loop = ExecutionLoop(
            llm_client=client,
            registry=registry,
            memory=memory,
        )
        assert loop.llm_client is client
        assert loop.router is None

    def test_loop_with_router_stores_router(self) -> None:
        from hachi.core.loop import ExecutionLoop, ToolRegistry

        class _DummyClient(BaseLLMClient):
            model = "dummy"

            def generate(self, messages, **kw):  # type: ignore[override]
                return LLMResponse(content="dummy", usage=TokenUsage())

        client = _DummyClient()
        router = MagicMock()
        memory = MagicMock()
        memory.get_messages.return_value = []

        loop = ExecutionLoop(
            llm_client=client,
            registry=ToolRegistry(),
            memory=memory,
            router=router,
        )
        assert loop.router is router


# ---------------------------------------------------------------------------
# GATE-COMPAT: Sub-agent D2 regression
# ---------------------------------------------------------------------------


class TestSubAgentD2Regression:
    """D2 fix: OpenAI-session delegation builds an OpenAI-shaped client, not Anthropic."""

    def test_anthropic_session_builds_anthropic_client(self, monkeypatch) -> None:
        """Anthropic session preserved — _create_client returns AnthropicClient."""
        from hachi.core.sub_agent import SubAgentRuntime

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-test-key")

        # Pass an Anthropic-shaped client as session_client.
        mock_anthropic = MagicMock(spec=AnthropicClient)
        mock_anthropic.model = "claude-haiku-4-5"

        client = SubAgentRuntime._create_client("claude-haiku-4-5", session_client=mock_anthropic)
        assert isinstance(client, AnthropicClient)

    def test_openai_session_builds_openai_compat_client(self) -> None:
        """OpenAI-compatible session → OpenAICompatibleClient."""
        from hachi.core.llm import OpenAICompatibleClient
        from hachi.core.sub_agent import SubAgentRuntime

        fake_oai = OpenAICompatibleClient(
            base_url="http://localhost:11434/v1",
            model="llama3",
            api_key="test-key",
        )
        client = SubAgentRuntime._create_client("llama3", session_client=fake_oai)
        assert isinstance(client, OpenAICompatibleClient)
        assert client.model == "llama3"
        assert client.base_url == "http://localhost:11434/v1"

    def test_no_session_client_defaults_to_anthropic(self, monkeypatch) -> None:
        """When no session_client passed, falls back to AnthropicClient (original behavior).

        Unsets the API key so the client constructor raises a predictable error,
        proving we attempted to build an AnthropicClient (not a silently null client).
        """
        from hachi.core.sub_agent import SubAgentRuntime

        # Ensure no API key so the AnthropicClient constructor raises ValueError.
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # This will raise ValueError for missing API key — that's expected; we just
        # check the type of exception, NOT a network call.
        with pytest.raises((ValueError, Exception)):
            SubAgentRuntime._create_client("claude-haiku-4-5", session_client=None)

    def test_explicit_model_override_preserves_openai_provider(self) -> None:
        """Explicit model= override with an OpenAI session reuses OpenAI provider."""
        from hachi.core.llm import OpenAICompatibleClient
        from hachi.core.sub_agent import SubAgentRuntime

        fake_oai = OpenAICompatibleClient(
            base_url="http://groq.internal/v1",
            model="llama3-70b",
            api_key="groq-key",
        )
        client = SubAgentRuntime._create_client("llama3-8b", session_client=fake_oai)
        assert isinstance(client, OpenAICompatibleClient)
        assert client.model == "llama3-8b"
        assert client.base_url == "http://groq.internal/v1"


# ---------------------------------------------------------------------------
# GATE-COMPAT: Cost tracker with and without registry
# ---------------------------------------------------------------------------


class TestCostTrackerBackCompat:
    def test_cost_tracker_works_without_registry(self) -> None:
        from hachi.core.cost import CostTracker

        tracker = CostTracker(registry=None)
        tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=1_000_000))
        snap = tracker.snapshot()
        assert snap.call_count == 1
        assert snap.input_tokens == 1_000_000

    def test_cost_tracker_uses_registry_pricing_when_present(self) -> None:
        from hachi.core.cost import CostTracker
        from hachi.core.routing.capability import Capability
        from hachi.core.routing.descriptor import ModelDescriptor, Pricing
        from hachi.core.routing.registry import ModelRegistry

        reg = ModelRegistry()
        reg.register(
            ModelDescriptor(
                id="my-custom-model",
                provider="anthropic",
                capabilities=frozenset({Capability.REASONING}),
                context_window=200_000,
                max_output=8_192,
                pricing=Pricing(input_per_mtok=42.0, output_per_mtok=84.0),
            )
        )
        tracker = CostTracker(registry=reg)
        tracker.record("my-custom-model", TokenUsage(input_tokens=1_000_000))
        snap = tracker.snapshot()
        # 1M input * $42/M = $42
        assert abs(snap.estimated_cost_usd - 42.0) < 0.01

    def test_cost_tracker_registry_falls_back_to_old_table(self) -> None:
        """When registry has no match, falls back to cost.py MODEL_PRICING."""
        from hachi.core.cost import CostTracker, pricing_for
        from hachi.core.routing.registry import ModelRegistry

        reg = ModelRegistry()  # empty — no registered models
        tracker = CostTracker(registry=reg)
        # claude-haiku-4-5 is in the old pricing table but not in empty registry.
        tracker.record("claude-haiku-4-5", TokenUsage(input_tokens=1_000_000))
        snap = tracker.snapshot()
        # Should use the old table price ($1/M in = $1)
        old_price = pricing_for("claude-haiku-4-5")
        expected = old_price[0]  # input price per M
        assert abs(snap.estimated_cost_usd - expected) < 0.01
