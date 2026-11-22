"""Slice 2.5 — Multi-provider depth (Initiative I) tests.

Covers:
  - failover-under-load: primary LLM provider fails terminally; router transparently
    re-issues against a SECOND provider's model and succeeds; provider.failover signal
    recorded.
  - budget-aware selection: budget_constraints() returns None below soft cap;
    returns prefer="cost" at/above the soft cap; routing then picks the cheaper model.
  - cost attribution: calls to two different models/providers attributed separately;
    per-provider rollup sums correctly.
  - health-aware ordering (multi-provider): provider with OPEN breaker is skipped;
    next usable provider's model is chosen.

All tests are deterministic — NO network, NO wall-clock delays.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

import pytest

from hachi.core.cost import CostSnapshot, CostTracker, ModelCostSnapshot
from hachi.core.llm import BaseLLMClient, LLMResponse, Message, TokenUsage
from hachi.core.providers.base import ProviderHealth
from hachi.core.resilience import HealthRecorder, ResilientClient, RetryPolicy
from hachi.core.routing.budget import budget_constraints
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry
from hachi.core.routing.router import ModelRouter, NoRouteError, RouteConstraints

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _TransientError(Exception):
    """Simulates a 503 Service Unavailable — transient."""

    status_code = 503


class _PermanentError(Exception):
    """Simulates a 400 Bad Request — non-retryable."""

    status_code = 400


def _ok(model: str = "ok") -> LLMResponse:
    return LLMResponse(content=f"ok-{model}", usage=TokenUsage(input_tokens=10, output_tokens=5))


class _FakeClient(BaseLLMClient):
    """Configurable fake LLM client."""

    def __init__(
        self,
        responses: list[LLMResponse | Exception],
        model: str = "fake",
    ) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.model = model

    def generate(self, messages: list[Message], **kw: Any) -> LLMResponse:
        if self._call_count >= len(self._responses):
            return _ok(self.model)
        r = self._responses[self._call_count]
        self._call_count += 1
        if isinstance(r, Exception):
            raise r
        return r

    def generate_stream(  # type: ignore[override]
        self, messages: list[Message], **kw: Any
    ) -> Generator[str, None, LLMResponse]:
        resp = self.generate(messages, **kw)
        if resp.content:
            yield resp.content
        return resp

    def list_models(self) -> list[str]:
        return [self.model]


class _FakeProvider:
    """Fake AIProvider that vends _FakeClients on demand."""

    def __init__(
        self,
        name: str,
        models: list[ModelDescriptor],
        breaker: str = "closed",
    ) -> None:
        self.name = name
        self._models = models
        self._health_obj = ProviderHealth(provider=name, breaker=breaker)
        # Pre-configure per-model response sequences (set after construction).
        self._response_sequences: dict[str, list[LLMResponse | Exception]] = {}

    def capabilities(self) -> set[Capability]:
        caps: set[Capability] = set()
        for d in self._models:
            caps.update(d.capabilities)
        return caps

    def models(self) -> list[ModelDescriptor]:
        return self._models

    def build_llm_client(self, model_id: str, **opts: Any) -> _FakeClient:
        seq = self._response_sequences.get(model_id, [_ok(model_id)])
        return _FakeClient(responses=seq, model=model_id)

    def health(self) -> ProviderHealth:
        return self._health_obj

    def set_breaker(self, state: str) -> None:
        self._health_obj = ProviderHealth(provider=self.name, breaker=state)

    def configure_responses(self, model_id: str, responses: list[LLMResponse | Exception]) -> None:
        self._response_sequences[model_id] = responses


class _FakeProviderRegistry:
    """Minimal ProviderRegistry stub wrapping a list of _FakeProvider."""

    def __init__(self, providers: list[_FakeProvider]) -> None:
        self._providers = providers
        self._by_name: dict[str, _FakeProvider] = {p.name: p for p in providers}

    def health(self) -> dict[str, ProviderHealth]:
        return {p.name: p.health() for p in self._providers}

    def get_by_name(self, name: str) -> _FakeProvider | None:
        return self._by_name.get(name)

    def llm_providers(self) -> list[_FakeProvider]:
        return list(self._providers)


def _make_descriptor(
    model_id: str,
    provider: str,
    caps: set[Capability] | None = None,
    input_price: float = 1.0,
    output_price: float = 5.0,
    tier_rank: int = 30,
) -> ModelDescriptor:
    return ModelDescriptor(
        id=model_id,
        provider=provider,
        capabilities=frozenset(caps or {Capability.REASONING}),
        context_window=200_000,
        max_output=8_192,
        pricing=Pricing(input_per_mtok=input_price, output_per_mtok=output_price),
        supports_tools=True,
        tier_rank=tier_rank,
    )


def _two_provider_setup(
    *,
    primary_breaker: str = "closed",
    fallback_breaker: str = "closed",
    primary_responses: list[LLMResponse | Exception] | None = None,
    fallback_responses: list[LLMResponse | Exception] | None = None,
    primary_price: float = 15.0,
    fallback_price: float = 1.0,
) -> tuple[ModelRouter, _FakeProvider, _FakeProvider]:
    """Build a two-provider ModelRouter with configurable health and responses."""
    desc_a = _make_descriptor(
        "model-primary", "provider-a", input_price=primary_price, tier_rank=10
    )
    desc_b = _make_descriptor(
        "model-fallback", "provider-b", input_price=fallback_price, tier_rank=30
    )

    prov_a = _FakeProvider("provider-a", [desc_a], breaker=primary_breaker)
    prov_b = _FakeProvider("provider-b", [desc_b], breaker=fallback_breaker)

    if primary_responses is not None:
        prov_a.configure_responses("model-primary", primary_responses)
    if fallback_responses is not None:
        prov_b.configure_responses("model-fallback", fallback_responses)

    registry = ModelRegistry()
    registry.register(desc_a)
    registry.register(desc_b)

    provider_reg = _FakeProviderRegistry([prov_a, prov_b])
    policy = RoutingPolicy(
        default_model="model-primary",
        capabilities={Capability.REASONING: ["model-primary", "model-fallback"]},
    )
    router = ModelRouter(
        registry=registry,
        policy=policy,
        providers=provider_reg,
        resilience=RetryPolicy(max_attempts=2, backoff_base_s=0.0),
    )
    return router, prov_a, prov_b


# ---------------------------------------------------------------------------
# 1. Failover under load
# ---------------------------------------------------------------------------


class TestFailoverUnderLoad:
    """GATE-FAILOVER: primary fails terminally → fallback provider serves the call."""

    def test_failover_to_second_provider(self) -> None:
        """Primary always fails; fallback (different provider) succeeds.

        Verifies that ResilientClient's fallback chain spans different providers
        and that the correct model (from provider-b) is used.
        """
        # Primary fails with transient errors on every call (max_attempts=2 → terminal).
        primary = _FakeClient(
            [_TransientError("503"), _TransientError("503"), _TransientError("503")],
            model="model-primary",
        )
        fallback = _FakeClient([_ok("model-fallback")], model="model-fallback")

        policy = RetryPolicy(max_attempts=2, backoff_base_s=0.0)
        primary_rec = HealthRecorder("provider-a", policy)
        fallback_rec = HealthRecorder("provider-b", policy)

        failover_signals: list[str] = []

        # Build the ResilientClient directly (same chain the router builds).
        client = ResilientClient(
            inner=primary,
            policy=policy,
            recorder=primary_rec,
            fallbacks=[(fallback, fallback_rec)],
        )

        # Monkey-patch _call_with_chain to intercept the failover log signal.
        def _patched(fn_builder: Any) -> Any:
            chain = [(client._inner, client._recorder)] + client._fallbacks
            last_exc = None
            for idx, (c, rec) in enumerate(chain):
                if idx > 0:
                    failover_signals.append(f"provider.failover:idx={idx},model={c.model}")
                import hachi.core.resilience as _res

                fn = fn_builder(c)
                try:
                    return _res.resilient_call(fn, policy, rec)
                except Exception as exc:
                    last_exc = exc
            raise last_exc or RuntimeError("exhausted")

        client._call_with_chain = _patched  # type: ignore[method-assign]

        result = client.generate([Message(role="user", content="hi")])

        # Fallback provided the response.
        assert result.content == "ok-model-fallback"
        assert fallback._call_count == 1
        # Failover signal was recorded.
        assert len(failover_signals) == 1
        assert "provider.failover" in failover_signals[0]
        assert "model-fallback" in failover_signals[0]

    def test_router_select_spans_two_providers(self) -> None:
        """ModelRouter.select() builds a fallback chain across provider-a and provider-b."""
        router, prov_a, prov_b = _two_provider_setup()
        resolved = router.select(Capability.REASONING)

        # The primary descriptor should be model-primary (explicit policy order).
        assert resolved.descriptor.id == "model-primary"
        # The client is a ResilientClient.
        assert isinstance(resolved.client, ResilientClient)
        # The fallback chain has one element (model-fallback from provider-b).
        assert len(resolved.client._fallbacks) == 1
        fallback_client, _ = resolved.client._fallbacks[0]
        assert fallback_client.model == "model-fallback"

    def test_end_to_end_failover_through_router(self) -> None:
        """End-to-end: router builds chain; primary fails; fallback from provider-b serves."""
        router, prov_a, prov_b = _two_provider_setup(
            primary_responses=[_TransientError("503"), _TransientError("503")],
            fallback_responses=[_ok("model-fallback")],
        )
        resolved = router.select(Capability.REASONING)

        # Now actually call generate() on the resilient client.
        result = resolved.client.generate([Message(role="user", content="test")])
        assert "model-fallback" in result.content

    def test_failover_signal_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """ResilientClient emits a WARNING log when failing over (provider.failover signal)."""
        import logging

        primary = _FakeClient(
            [_TransientError("503"), _TransientError("503")], model="model-primary"
        )
        fallback = _FakeClient([_ok("model-fallback")], model="model-fallback")
        policy = RetryPolicy(max_attempts=2, backoff_base_s=0.0)
        primary_rec = HealthRecorder("provider-a", policy)
        fallback_rec = HealthRecorder("provider-b", policy)

        client = ResilientClient(
            inner=primary,
            policy=policy,
            recorder=primary_rec,
            fallbacks=[(fallback, fallback_rec)],
        )

        with caplog.at_level(logging.WARNING, logger="hachi.core.resilience"):
            client.generate([Message(role="user", content="hi")])

        assert any("failing over" in rec.message.lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# 2. Budget-aware selection
# ---------------------------------------------------------------------------


@dataclass
class _FakeSnapshot:
    """Minimal stand-in for CostSnapshot."""

    estimated_cost_usd: float


class TestBudgetAwareSelection:
    """budget_constraints() — opt-in hook; deterministic, no wall-clock."""

    def test_below_soft_cap_returns_none(self) -> None:
        """Well below the 80 % threshold → no constraints, default routing applies."""
        snap = _FakeSnapshot(estimated_cost_usd=0.50)
        result = budget_constraints(snap, soft_cap_usd=1.0)
        assert result is None

    def test_exactly_at_threshold_returns_constraints(self) -> None:
        """At exactly 80 % → returns prefer="cost"."""
        snap = _FakeSnapshot(estimated_cost_usd=0.80)
        result = budget_constraints(snap, soft_cap_usd=1.0)
        assert result is not None
        assert result.prefer == "cost"

    def test_above_soft_cap_returns_cost_prefer(self) -> None:
        """At 90 % → prefer="cost" with no per-token ceiling (no hard_cap set)."""
        snap = _FakeSnapshot(estimated_cost_usd=0.90)
        result = budget_constraints(snap, soft_cap_usd=1.0)
        assert result is not None
        assert result.prefer == "cost"
        assert result.max_input_cost_per_mtok is None

    def test_hard_cap_sets_max_input_cost(self) -> None:
        """When hard_cap_usd is set, max_input_cost_per_mtok is applied."""
        snap = _FakeSnapshot(estimated_cost_usd=0.90)
        result = budget_constraints(snap, soft_cap_usd=1.0, hard_cap_usd=2.0)
        assert result is not None
        assert result.max_input_cost_per_mtok == 2.0

    def test_no_cap_configured_returns_none(self) -> None:
        """When soft_cap_usd is None, no constraints are returned."""
        snap = _FakeSnapshot(estimated_cost_usd=9999.0)
        result = budget_constraints(snap, soft_cap_usd=None)
        assert result is None

    def test_zero_cap_returns_none(self) -> None:
        """Zero or negative cap is ignored (no meaningful constraint)."""
        snap = _FakeSnapshot(estimated_cost_usd=1.0)
        result = budget_constraints(snap, soft_cap_usd=0.0)
        assert result is None

    def test_custom_soft_cap_fraction(self) -> None:
        """Custom soft_cap_fraction of 50 % triggers at half the cap."""
        snap_below = _FakeSnapshot(estimated_cost_usd=0.49)
        snap_above = _FakeSnapshot(estimated_cost_usd=0.51)
        assert budget_constraints(snap_below, soft_cap_usd=1.0, soft_cap_fraction=0.50) is None
        assert budget_constraints(snap_above, soft_cap_usd=1.0, soft_cap_fraction=0.50) is not None

    def test_budget_constraints_drives_cheaper_model_selection(self) -> None:
        """Routing with budget constraints picks cheaper model; without, picks quality."""
        desc_cheap = _make_descriptor(
            "cheap-model", "p-cheap", input_price=0.15, output_price=0.60, tier_rank=35
        )
        desc_pricey = _make_descriptor(
            "pricey-model", "p-pricey", input_price=15.0, output_price=75.0, tier_rank=10
        )

        prov_cheap = _FakeProvider("p-cheap", [desc_cheap])
        prov_pricey = _FakeProvider("p-pricey", [desc_pricey])

        registry = ModelRegistry()
        registry.register(desc_cheap)
        registry.register(desc_pricey)

        provider_reg = _FakeProviderRegistry([prov_cheap, prov_pricey])
        # No explicit capability order → registry-derived candidates, prefer controls order.
        policy = RoutingPolicy(default_model="pricey-model", capabilities={})
        router = ModelRouter(
            registry=registry,
            policy=policy,
            providers=provider_reg,
            resilience=RetryPolicy(max_attempts=1),
        )

        # Without budget pressure: prefer="quality" picks the pricier, higher-tier model.
        no_budget = RouteConstraints(prefer="quality")
        result_quality = router.select(Capability.REASONING, no_budget)
        assert result_quality.descriptor.id == "pricey-model"

        router.new_turn()  # Clear sticky cache.

        # With budget pressure: budget_constraints returns prefer="cost" → cheap model.
        snap = _FakeSnapshot(estimated_cost_usd=0.90)
        budget = budget_constraints(snap, soft_cap_usd=1.0)
        assert budget is not None
        result_budget = router.select(Capability.REASONING, budget)
        assert result_budget.descriptor.id == "cheap-model"


# ---------------------------------------------------------------------------
# 3. Cost attribution
# ---------------------------------------------------------------------------


class TestCostAttribution:
    """CostTracker.per_model_snapshot / per_provider_snapshot correctness."""

    def test_two_models_attributed_separately(self) -> None:
        """Calls to two different models are attributed to separate buckets."""
        tracker = CostTracker(provider_map={"model-a": "provider-a", "model-b": "provider-b"})
        usage_a = TokenUsage(input_tokens=1000, output_tokens=200)
        usage_b = TokenUsage(input_tokens=500, output_tokens=100)

        tracker.record("model-a", usage_a)
        tracker.record("model-b", usage_b)

        per_model = tracker.per_model_snapshot()
        assert "model-a" in per_model
        assert "model-b" in per_model

        snap_a = per_model["model-a"]
        snap_b = per_model["model-b"]

        assert snap_a.input_tokens == 1000
        assert snap_a.output_tokens == 200
        assert snap_a.call_count == 1

        assert snap_b.input_tokens == 500
        assert snap_b.output_tokens == 100
        assert snap_b.call_count == 1

        # Total cost from snapshot equals sum of per-model costs.
        total_snap = tracker.snapshot()
        combined = snap_a.estimated_cost_usd + snap_b.estimated_cost_usd
        assert abs(total_snap.estimated_cost_usd - combined) < 1e-9

    def test_per_provider_rollup_sums_models(self) -> None:
        """per_provider_snapshot aggregates models from the same provider."""
        tracker = CostTracker(
            provider_map={
                "haiku": "anthropic",
                "sonnet": "anthropic",
                "gpt-mini": "openai",
            }
        )
        tracker.record("haiku", TokenUsage(input_tokens=1000, output_tokens=100))
        tracker.record("sonnet", TokenUsage(input_tokens=500, output_tokens=50))
        tracker.record("gpt-mini", TokenUsage(input_tokens=200, output_tokens=20))

        per_provider = tracker.per_provider_snapshot()
        assert "anthropic" in per_provider
        assert "openai" in per_provider

        anth = per_provider["anthropic"]
        oai = per_provider["openai"]

        # Anthropic: haiku + sonnet calls combined.
        assert anth.call_count == 2
        assert anth.input_tokens == 1500
        assert anth.output_tokens == 150

        # OpenAI: only gpt-mini.
        assert oai.call_count == 1
        assert oai.input_tokens == 200

    def test_unknown_provider_grouped_under_unknown(self) -> None:
        """Models with no provider mapping are grouped as 'unknown'."""
        tracker = CostTracker()  # no provider_map
        tracker.record("mystery-model", TokenUsage(input_tokens=100, output_tokens=10))
        per_provider = tracker.per_provider_snapshot()
        assert "unknown" in per_provider
        assert per_provider["unknown"].call_count == 1

    def test_multiple_calls_to_same_model_accumulate(self) -> None:
        """Multiple record() calls for the same model accumulate in one bucket."""
        tracker = CostTracker(provider_map={"m": "p"})
        for _ in range(5):
            tracker.record("m", TokenUsage(input_tokens=100, output_tokens=10))
        per_model = tracker.per_model_snapshot()
        assert per_model["m"].call_count == 5
        assert per_model["m"].input_tokens == 500

    def test_per_model_snapshot_returns_modelcostsnapshot(self) -> None:
        """Return type is ModelCostSnapshot with correct fields."""
        tracker = CostTracker(provider_map={"x": "p-x"})
        tracker.record("x", TokenUsage(input_tokens=10, output_tokens=5))
        per_model = tracker.per_model_snapshot()
        snap = per_model["x"]
        assert isinstance(snap, ModelCostSnapshot)
        assert snap.model_id == "x"
        assert snap.provider == "p-x"

    def test_cost_snapshot_still_works(self) -> None:
        """Existing CostSnapshot path is unchanged after adding per-model tracking."""
        tracker = CostTracker()
        tracker.record("model-a", TokenUsage(input_tokens=100, output_tokens=50))
        tracker.record("model-b", TokenUsage(input_tokens=200, output_tokens=100))
        snap = tracker.snapshot()
        assert isinstance(snap, CostSnapshot)
        assert snap.input_tokens == 300
        assert snap.output_tokens == 150
        assert snap.call_count == 2

    def test_to_dict_includes_provider(self) -> None:
        """ModelCostSnapshot.to_dict() includes all expected keys."""
        snap = ModelCostSnapshot(
            model_id="m",
            provider="p",
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.001,
            call_count=1,
        )
        d = snap.to_dict()
        assert d["model_id"] == "m"
        assert d["provider"] == "p"
        assert d["input_tokens"] == 10
        assert d["call_count"] == 1


# ---------------------------------------------------------------------------
# 4. Health-aware ordering (multi-provider explicit test)
# ---------------------------------------------------------------------------


class TestHealthAwareMultiProvider:
    """GATE-ROUTE (multi-provider): open breaker on one provider routes to the other."""

    def test_open_breaker_on_primary_provider_skips_to_secondary(self) -> None:
        """When provider-a has an open breaker, router picks model from provider-b."""
        router, prov_a, prov_b = _two_provider_setup(primary_breaker="open")
        result = router.select(Capability.REASONING)
        # provider-a models are filtered out; provider-b's model survives.
        assert result.descriptor.provider == "provider-b"
        assert result.descriptor.id == "model-fallback"

    def test_both_providers_healthy_uses_explicit_policy_order(self) -> None:
        """Both healthy → explicit policy order wins (model-primary first)."""
        router, _, _ = _two_provider_setup()
        result = router.select(Capability.REASONING)
        assert result.descriptor.id == "model-primary"
        assert result.descriptor.provider == "provider-a"

    def test_both_providers_breaker_open_raises_no_route(self) -> None:
        """All providers broken → NoRouteError."""
        router, prov_a, prov_b = _two_provider_setup(
            primary_breaker="open", fallback_breaker="open"
        )
        with pytest.raises(NoRouteError):
            router.select(Capability.REASONING)

    def test_half_open_provider_is_still_usable(self) -> None:
        """A provider in half-open state is treated as usable (allowed to retry)."""
        router, prov_a, _ = _two_provider_setup(primary_breaker="half_open")
        result = router.select(Capability.REASONING)
        # half_open is usable → model-primary is selected (explicit order).
        assert result.descriptor.id == "model-primary"

    def test_router_new_turn_clears_sticky_and_re_evaluates_health(self) -> None:
        """After new_turn(), breaker state change is reflected in next select()."""
        router, prov_a, prov_b = _two_provider_setup()
        # First turn: both healthy → model-primary.
        r1 = router.select(Capability.REASONING)
        assert r1.descriptor.id == "model-primary"

        # Simulate primary's breaker opening between turns.
        prov_a.set_breaker("open")

        # Same turn: sticky cache returns model-primary (stale but unchanged).
        r2 = router.select(Capability.REASONING)
        assert r2 is r1  # from sticky cache

        # New turn: sticky cache cleared; re-evaluates → fallback selected.
        router.new_turn()
        r3 = router.select(Capability.REASONING)
        assert r3.descriptor.id == "model-fallback"
