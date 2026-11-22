"""GATE-ROUTE tests for ModelRouter (Slice 2.1).

Covers:
  - Deterministic routing given a health snapshot.
  - Hard-constraint filtering (context/tools/vision/cost).
  - Ordering by prefer cost/quality/balanced.
  - Explicit policy order wins.
  - NoRouteError when none survive.
  - Stickiness: same route reused within a turn (amendment A12).
"""

from __future__ import annotations

import pytest

from hachi.core.providers.base import ProviderHealth
from hachi.core.resilience import RetryPolicy
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry
from hachi.core.routing.router import ModelRouter, NoRouteError, RouteConstraints

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, model: str = "fake") -> None:
        self.model = model

    def generate(self, messages, **kw):  # type: ignore[override]
        raise RuntimeError("FakeClient.generate should not be called in routing tests")

    def generate_stream(self, messages, **kw):  # type: ignore[override]
        raise RuntimeError("FakeClient.generate_stream should not be called in routing tests")

    def list_models(self):  # type: ignore[override]
        return []


class _FakeProvider:
    """Fake AIProvider adapter that hands out FakeClients."""

    def __init__(self, name: str, models: list[ModelDescriptor]) -> None:
        self.name = name
        self._models = models
        self._health = ProviderHealth(provider=name)
        self.health_updates: list[ProviderHealth] = []

    def update_health(self, health: ProviderHealth) -> None:
        self.health_updates.append(health)
        self._health = health

    def capabilities(self) -> set[Capability]:
        caps: set[Capability] = set()
        for d in self._models:
            caps.update(d.capabilities)
        return caps

    def models(self) -> list[ModelDescriptor]:
        return self._models

    def build_llm_client(self, model_id: str, **opts) -> _FakeClient:  # type: ignore[return-value]
        return _FakeClient(model=model_id)

    def health(self) -> ProviderHealth:
        return self._health


class _FakeProviderRegistry:
    """Minimal ProviderRegistry stub."""

    def __init__(self, providers: list[_FakeProvider]) -> None:
        self._providers = providers
        self._by_name = {p.name: p for p in providers}

    def health(self) -> dict[str, ProviderHealth]:
        return {p.name: p.health() for p in self._providers}

    def get_by_name(self, name: str) -> _FakeProvider | None:
        return self._by_name.get(name)

    def llm_providers(self) -> list[_FakeProvider]:
        return list(self._providers)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_descriptor(
    model_id: str,
    provider: str,
    caps: set[Capability],
    context_window: int = 200_000,
    supports_tools: bool = True,
    input_price: float = 1.0,
    output_price: float = 5.0,
    tier_rank: int = 30,
) -> ModelDescriptor:
    return ModelDescriptor(
        id=model_id,
        provider=provider,
        capabilities=frozenset(caps),
        context_window=context_window,
        max_output=8_192,
        pricing=Pricing(input_per_mtok=input_price, output_per_mtok=output_price),
        supports_tools=supports_tools,
        tier_rank=tier_rank,
    )


def _make_router(
    descriptors: list[ModelDescriptor],
    policy_caps: dict[Capability, list[str]] | None = None,
    default_model: str = "model-a",
) -> tuple[ModelRouter, _FakeProviderRegistry]:
    registry = ModelRegistry()
    providers_list: list[_FakeProvider] = []
    by_provider: dict[str, list[ModelDescriptor]] = {}
    for d in descriptors:
        by_provider.setdefault(d.provider, []).append(d)
        registry.register(d)

    for pname, pmodels in by_provider.items():
        providers_list.append(_FakeProvider(pname, pmodels))

    provider_reg = _FakeProviderRegistry(providers_list)
    policy = RoutingPolicy(
        default_model=default_model,
        capabilities=policy_caps or {},
    )
    router = ModelRouter(
        registry=registry,
        policy=policy,
        providers=provider_reg,
        resilience=RetryPolicy(max_attempts=1),  # no retries in routing tests
    )
    return router, provider_reg


# ---------------------------------------------------------------------------
# GATE-ROUTE: determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_same_route(self) -> None:
        descs = [
            _make_descriptor("model-a", "p1", {Capability.REASONING}),
            _make_descriptor("model-b", "p1", {Capability.REASONING}),
        ]
        router, _ = _make_router(descs, default_model="model-a")
        r1 = router.select(Capability.REASONING)
        r2 = router.select(Capability.REASONING)
        assert r1.descriptor.id == r2.descriptor.id

    def test_stickiness_within_turn(self) -> None:
        """Same route reused within one turn (amendment A12)."""
        descs = [
            _make_descriptor("model-a", "p1", {Capability.REASONING}),
        ]
        router, _ = _make_router(descs, default_model="model-a")
        r1 = router.select(Capability.REASONING)
        r2 = router.select(Capability.REASONING)
        assert r1 is r2  # Same object from sticky cache.

    def test_new_turn_clears_sticky(self) -> None:
        descs = [_make_descriptor("model-a", "p1", {Capability.REASONING})]
        router, _ = _make_router(descs, default_model="model-a")
        r1 = router.select(Capability.REASONING)
        router.new_turn()
        r2 = router.select(Capability.REASONING)
        # Should produce equal (not necessarily same) result after turn reset.
        assert r1.descriptor.id == r2.descriptor.id


# ---------------------------------------------------------------------------
# GATE-ROUTE: hard constraints
# ---------------------------------------------------------------------------


class TestHardConstraints:
    def test_context_window_filter(self) -> None:
        descs = [
            _make_descriptor("small", "p1", {Capability.REASONING}, context_window=10_000),
            _make_descriptor("large", "p1", {Capability.REASONING}, context_window=200_000),
        ]
        router, _ = _make_router(descs, default_model="large")
        result = router.select(Capability.REASONING, RouteConstraints(min_context=100_000))
        assert result.descriptor.id == "large"

    def test_context_window_filter_no_survivors(self) -> None:
        descs = [
            _make_descriptor("small", "p1", {Capability.REASONING}, context_window=10_000),
        ]
        router, _ = _make_router(descs, default_model="small")
        with pytest.raises(NoRouteError):
            router.select(Capability.REASONING, RouteConstraints(min_context=100_000))

    def test_needs_tools_filter(self) -> None:
        descs = [
            _make_descriptor("no-tools", "p1", {Capability.REASONING}, supports_tools=False),
            _make_descriptor("has-tools", "p1", {Capability.REASONING}, supports_tools=True),
        ]
        router, _ = _make_router(descs, default_model="has-tools")
        result = router.select(Capability.REASONING, RouteConstraints(needs_tools=True))
        assert result.descriptor.id == "has-tools"

    def test_needs_vision_filter(self) -> None:
        descs = [
            _make_descriptor("no-vision", "p1", {Capability.REASONING}),
            _make_descriptor("has-vision", "p1", {Capability.REASONING, Capability.VISION}),
        ]
        router, _ = _make_router(descs, default_model="has-vision")
        result = router.select(Capability.REASONING, RouteConstraints(needs_vision=True))
        assert result.descriptor.id == "has-vision"

    def test_cost_cap_filter(self) -> None:
        descs = [
            _make_descriptor("cheap", "p1", {Capability.REASONING}, input_price=0.5),
            _make_descriptor("expensive", "p1", {Capability.REASONING}, input_price=15.0),
        ]
        router, _ = _make_router(descs, default_model="cheap")
        result = router.select(Capability.REASONING, RouteConstraints(max_input_cost_per_mtok=1.0))
        assert result.descriptor.id == "cheap"

    def test_unknown_pricing_allowed_through_without_cost_cap(self) -> None:
        """A model with pricing=None is allowed when no cost cap is set."""
        no_price = ModelDescriptor(
            id="no-price",
            provider="p1",
            capabilities=frozenset({Capability.REASONING}),
            context_window=200_000,
            max_output=8_192,
            pricing=None,
        )
        registry = ModelRegistry()
        registry.register(no_price)
        provider_reg = _FakeProviderRegistry([_FakeProvider("p1", [no_price])])
        policy = RoutingPolicy(default_model="no-price")
        router = ModelRouter(
            registry=registry,
            policy=policy,
            providers=provider_reg,
            resilience=RetryPolicy(max_attempts=1),
        )
        result = router.select(Capability.REASONING)
        assert result.descriptor.id == "no-price"


# ---------------------------------------------------------------------------
# GATE-ROUTE: ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_prefer_cost_picks_cheapest(self) -> None:
        descs = [
            _make_descriptor("pricey", "p1", {Capability.REASONING}, input_price=15.0),
            _make_descriptor("cheap", "p1", {Capability.REASONING}, input_price=1.0),
        ]
        router, _ = _make_router(descs, default_model="cheap")
        result = router.select(Capability.REASONING, RouteConstraints(prefer="cost"))
        assert result.descriptor.id == "cheap"

    def test_prefer_quality_picks_highest_tier(self) -> None:
        descs = [
            _make_descriptor("mid", "p1", {Capability.REASONING}, tier_rank=30),
            _make_descriptor("top", "p1", {Capability.REASONING}, tier_rank=10),
        ]
        router, _ = _make_router(descs, default_model="top")
        result = router.select(Capability.REASONING, RouteConstraints(prefer="quality"))
        assert result.descriptor.id == "top"

    def test_explicit_policy_order_wins_over_prefer(self) -> None:
        """Policy-declared order must be honoured regardless of prefer."""
        descs = [
            _make_descriptor("model-b", "p1", {Capability.REASONING}, input_price=0.1),  # cheaper
            _make_descriptor("model-a", "p1", {Capability.REASONING}, input_price=15.0),  # pricier
        ]
        # Explicitly route REASONING to model-a first.
        router, _ = _make_router(
            descs,
            policy_caps={Capability.REASONING: ["model-a", "model-b"]},
            default_model="model-a",
        )
        result = router.select(Capability.REASONING, RouteConstraints(prefer="cost"))
        # Even though model-b is cheaper, explicit policy order wins.
        assert result.descriptor.id == "model-a"

    def test_no_route_error_when_none_survive(self) -> None:
        descs = [
            _make_descriptor("no-vision", "p1", {Capability.REASONING}),
        ]
        router, _ = _make_router(descs, default_model="no-vision")
        with pytest.raises(NoRouteError) as exc_info:
            router.select(Capability.VISION)
        assert "vision" in str(exc_info.value).lower() or "VISION" in str(exc_info.value)


# ---------------------------------------------------------------------------
# GATE-ROUTE: breaker filtering
# ---------------------------------------------------------------------------


class TestBreakerFiltering:
    def test_open_breaker_provider_is_skipped(self) -> None:
        descs = [
            _make_descriptor("primary", "broken-provider", {Capability.REASONING}),
            _make_descriptor("fallback", "healthy-provider", {Capability.REASONING}),
        ]
        router, provider_reg = _make_router(
            descs,
            policy_caps={Capability.REASONING: ["primary", "fallback"]},
            default_model="primary",
        )
        # Manually inject open breaker into the broken provider.
        for p in provider_reg._providers:
            if p.name == "broken-provider":
                p._health = ProviderHealth(provider="broken-provider", breaker="open")

        result = router.select(Capability.REASONING)
        assert result.descriptor.id == "fallback"

    def test_all_breakers_open_raises_no_route(self) -> None:
        descs = [
            _make_descriptor("primary", "broken", {Capability.REASONING}),
        ]
        router, provider_reg = _make_router(descs, default_model="primary")
        for p in provider_reg._providers:
            p._health = ProviderHealth(provider=p.name, breaker="open")

        with pytest.raises(NoRouteError):
            router.select(Capability.REASONING)


# ---------------------------------------------------------------------------
# default_client
# ---------------------------------------------------------------------------


class TestDefaultClient:
    def test_default_client_uses_default_model(self) -> None:
        descs = [_make_descriptor("claude-haiku-4-5", "p1", {Capability.REASONING})]
        router, _ = _make_router(descs, default_model="claude-haiku-4-5")
        client = router.default_client()
        # ResilientClient wraps the inner FakeClient.
        from hachi.core.resilience import ResilientClient

        assert isinstance(client, ResilientClient)

    def test_default_client_unknown_model_synthesises_descriptor(self) -> None:
        """Amendment A11: unknown models get a synthetic REASONING descriptor."""
        registry = ModelRegistry()  # empty — no bundled defaults
        policy = RoutingPolicy(default_model="some-local-ollama")
        provider_reg = _FakeProviderRegistry([])
        router = ModelRouter(
            registry=registry,
            policy=policy,
            providers=provider_reg,
            resilience=RetryPolicy(max_attempts=1),
        )
        # Should not raise; synthetic descriptor used.
        client = router.default_client()
        assert client is not None


class TestHealthFeedback:
    def test_call_outcomes_update_provider_health(self) -> None:
        """H7: HealthRecorder.record_success/record_failure must feed back into
        the real provider adapter's health, not just an internal recorder no one
        ever reads — previously the router's breaker filter saw a permanent
        boot-time default (available=True) no matter what actually happened.
        """
        descs = [_make_descriptor("claude-haiku-4-5", "p1", {Capability.REASONING})]
        router, provider_reg = _make_router(descs, default_model="claude-haiku-4-5")
        provider = provider_reg.get_by_name("p1")
        assert provider is not None

        recorder = router._get_recorder("p1")
        recorder.record_success(50.0)
        recorder.record_failure()

        assert len(provider.health_updates) == 2
        assert provider.health_updates[-1].consecutive_failures == 1


class TestSyntheticDescriptorProviderInference:
    @pytest.mark.parametrize(
        ("model_id", "expected_provider"),
        [
            ("gpt-4o", "openai-compatible"),
            ("gpt-4o-mini", "openai-compatible"),
            ("o3-mini", "openai-compatible"),
            ("gemini-2.0-flash", "gemini"),
            ("grok-3", "openai-compatible"),
            ("claude-haiku-4-5", "anthropic"),
        ],
    )
    def test_infers_provider_from_model_id_family(
        self, model_id: str, expected_provider: str
    ) -> None:
        """H7: an undeclared model id must synthesize a descriptor matching its
        naming family, not always 'anthropic' — an undeclared 'gpt-4o' was
        previously built against the wrong client entirely.
        """
        from hachi.core.routing.router import _synthetic_descriptor

        desc = _synthetic_descriptor(model_id)
        assert desc.provider == expected_provider
