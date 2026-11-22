"""Tests for ProviderRegistry and provider adapters (Slice 2.1).

Covers:
  - Registration and capability indexing.
  - from_config with Anthropic and OpenAI providers.
  - Health snapshot aggregation.
"""

from __future__ import annotations

from hachi.core.providers.base import ProviderHealth
from hachi.core.providers.registry import ProviderRegistry
from hachi.core.routing.capability import Capability
from hachi.core.settings import ResolvedConfig

# ---------------------------------------------------------------------------
# Fake provider
# ---------------------------------------------------------------------------


class _FakeLLMProvider:
    """Minimal AIProvider stub."""

    def __init__(self, name: str, caps: set[Capability]) -> None:
        self.name = name
        self._caps = caps

    def capabilities(self) -> set[Capability]:
        return self._caps

    def models(self):  # type: ignore[return]
        return []

    def build_llm_client(self, model_id: str, **opts):  # type: ignore[return]
        return None

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProviderRegistry:
    def test_register_and_providers_for(self) -> None:
        reg = ProviderRegistry()
        p = _FakeLLMProvider("myp", {Capability.REASONING, Capability.VISION})
        reg.register(p)
        assert p in reg.providers_for(Capability.REASONING)
        assert p in reg.providers_for(Capability.VISION)
        assert p not in reg.providers_for(Capability.EMBEDDINGS)

    def test_llm_providers(self) -> None:
        reg = ProviderRegistry()
        p = _FakeLLMProvider("p1", {Capability.REASONING})
        reg.register(p)
        assert p in reg.llm_providers()

    def test_health_aggregation(self) -> None:
        reg = ProviderRegistry()
        p = _FakeLLMProvider("p1", {Capability.REASONING})
        reg.register(p)
        health = reg.health()
        assert "p1" in health
        assert health["p1"].available is True

    def test_get_by_name(self) -> None:
        reg = ProviderRegistry()
        p = _FakeLLMProvider("anthropic", {Capability.REASONING})
        reg.register(p)
        assert reg.get_by_name("anthropic") is p
        assert reg.get_by_name("missing") is None

    def test_register_same_name_replaces(self) -> None:
        reg = ProviderRegistry()
        p1 = _FakeLLMProvider("p", {Capability.REASONING})
        p2 = _FakeLLMProvider("p", {Capability.VISION})
        reg.register(p1)
        reg.register(p2)
        assert reg.get_by_name("p") is p2

    def test_from_config_anthropic(self) -> None:
        """from_config with default Anthropic provider registers anthropic adapter."""
        config = ResolvedConfig()
        reg = ProviderRegistry.from_config(config)
        assert reg.get_by_name("anthropic") is not None
        anthropic_provider = reg.get_by_name("anthropic")
        assert Capability.REASONING in anthropic_provider.capabilities()

    def test_from_config_no_providers_no_crash(self) -> None:
        config = ResolvedConfig()
        reg = ProviderRegistry.from_config(config)
        # Should succeed without raising.
        assert reg is not None

    def test_anthropic_provider_capabilities(self) -> None:
        from hachi.core.providers.anthropic_provider import AnthropicProvider

        p = AnthropicProvider()
        caps = p.capabilities()
        assert Capability.REASONING in caps
        assert Capability.CODING in caps
        assert Capability.VISION in caps

    def test_anthropic_provider_models(self) -> None:
        from hachi.core.providers.anthropic_provider import AnthropicProvider

        p = AnthropicProvider()
        models = p.models()
        ids = [m.id for m in models]
        assert any("claude" in mid for mid in ids)

    def test_openai_compat_provider_capabilities(self) -> None:
        from hachi.core.providers.openai_compat_provider import OpenAICompatProvider

        p = OpenAICompatProvider(kind="openai")
        caps = p.capabilities()
        assert Capability.REASONING in caps
        assert Capability.VISION in caps

    def test_openai_compat_groq_no_vision(self) -> None:
        from hachi.core.providers.openai_compat_provider import OpenAICompatProvider

        p = OpenAICompatProvider(kind="groq")
        caps = p.capabilities()
        # Groq is not in the vision-capable preset list.
        assert Capability.VISION not in caps
