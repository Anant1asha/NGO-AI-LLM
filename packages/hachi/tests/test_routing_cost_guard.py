"""Cost-governance guard (BB-30): warn at boot when a high-volume chat capability
(reasoning/coding) is routed to a model much pricier than the routing default_model
— the 'every chat turn silently on gpt-4o' trap. The guard never mutates routing;
an explicit choice is respected, just surfaced loudly instead of hiding in config.
"""

from __future__ import annotations

from hachi.core.routing.capability import Capability
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry


def _registry() -> ModelRegistry:
    return ModelRegistry.build(object(), None)


def test_warns_when_reasoning_pinned_to_pricier_model_than_default() -> None:
    # default_model gpt-4o-mini ($0.15) but reasoning pinned to gpt-4o ($2.50) = ~16x.
    policy = RoutingPolicy(
        default_model="gpt-4o-mini",
        capabilities={Capability.REASONING: ["gpt-4o"]},
    )
    warns = policy.costly_capability_warnings(_registry())
    assert any("reasoning" in w and "gpt-4o" in w for w in warns), warns


def test_silent_when_reasoning_uses_the_default() -> None:
    policy = RoutingPolicy(
        default_model="gpt-4o-mini",
        capabilities={Capability.REASONING: ["gpt-4o-mini"]},
    )
    assert policy.costly_capability_warnings(_registry()) == []


def test_silent_when_override_is_only_modestly_pricier() -> None:
    # gpt-4.1-mini ($0.40) vs default gpt-4o-mini ($0.15) is < 3x — not egregious.
    policy = RoutingPolicy(
        default_model="gpt-4o-mini",
        capabilities={Capability.REASONING: ["gpt-4.1-mini"]},
    )
    assert policy.costly_capability_warnings(_registry()) == []
