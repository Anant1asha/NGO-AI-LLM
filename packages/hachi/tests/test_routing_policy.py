"""Tests for RoutingPolicy — back-compat synthesis and auto-policy (Slice 2.1).

GATE-COMPAT: no [routing] config → single model for every capability.
"""

from __future__ import annotations

from hachi.core.routing.capability import Capability
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry


class _FakeConfig:
    """Minimal config stub for policy tests."""

    class _Provider:
        model = "claude-haiku-4-5"
        kind = "anthropic"

    provider = _Provider()
    routing = None  # No [routing] section by default.


class _FakeRoutingConfig:
    default_model = "claude-haiku-4-5"
    capabilities = {"vision": ["claude-opus-4-8"], "title_generation": ["claude-haiku-4-5"]}
    auto = False


class _ConfigWithRouting:
    class _Provider:
        model = "claude-haiku-4-5"

    provider = _Provider()
    routing = _FakeRoutingConfig()


# ---------------------------------------------------------------------------
# GATE-COMPAT: absent [routing] → back-compat synthesis
# ---------------------------------------------------------------------------


class TestBackCompatSynthesis:
    def test_no_routing_section_synthesises_single_model(self) -> None:
        policy = RoutingPolicy.from_config(_FakeConfig())
        for cap in Capability:
            candidates = policy.candidates(cap)
            assert candidates == ["claude-haiku-4-5"], (
                f"Capability {cap} should map to the single session model; got {candidates}"
            )

    def test_back_compat_default_model(self) -> None:
        policy = RoutingPolicy.from_config(_FakeConfig())
        assert policy.default_model == "claude-haiku-4-5"

    def test_back_compat_auto_is_false(self) -> None:
        policy = RoutingPolicy.from_config(_FakeConfig())
        assert policy.auto is False

    def test_explicit_routing_section_respected(self) -> None:
        policy = RoutingPolicy.from_config(_ConfigWithRouting())
        assert policy.candidates(Capability.VISION) == ["claude-opus-4-8"]
        assert policy.candidates(Capability.TITLE_GENERATION) == ["claude-haiku-4-5"]

    def test_empty_capability_slot_returns_empty_list(self) -> None:
        policy = RoutingPolicy.from_config(_ConfigWithRouting())
        # REASONING is not in _FakeRoutingConfig.capabilities
        assert policy.candidates(Capability.REASONING) == []


# ---------------------------------------------------------------------------
# Auto-policy (amendment A1)
# ---------------------------------------------------------------------------


class TestAutoPolicy:
    def _make_registry(self) -> ModelRegistry:
        return ModelRegistry.build(object(), None)

    def test_auto_false_returns_self(self) -> None:
        policy = RoutingPolicy(default_model="claude-haiku-4-5", auto=False)
        reg = self._make_registry()
        result = policy.derive_auto_policy(reg)
        assert result is policy  # Same object: no-op when auto=False.

    def test_auto_true_fills_title_generation(self) -> None:
        policy = RoutingPolicy(default_model="claude-haiku-4-5", auto=True)
        reg = self._make_registry()
        derived = policy.derive_auto_policy(reg)
        cands = derived.candidates(Capability.TITLE_GENERATION)
        assert len(cands) >= 1
        # Should pick a cheap model for title_generation.
        desc = reg.get(cands[0])
        assert desc is not None
        assert Capability.TITLE_GENERATION in desc.capabilities

    def test_auto_true_fills_vision(self) -> None:
        policy = RoutingPolicy(default_model="claude-haiku-4-5", auto=True)
        reg = self._make_registry()
        derived = policy.derive_auto_policy(reg)
        cands = derived.candidates(Capability.VISION)
        assert len(cands) >= 1
        for mid in cands:
            desc = reg.get(mid)
            assert desc is not None
            assert Capability.VISION in desc.capabilities

    def test_auto_does_not_override_explicit_caps(self) -> None:
        explicit = {Capability.VISION: ["claude-opus-4-8"]}
        policy = RoutingPolicy(default_model="claude-haiku-4-5", capabilities=explicit, auto=True)
        reg = self._make_registry()
        derived = policy.derive_auto_policy(reg)
        assert derived.candidates(Capability.VISION) == ["claude-opus-4-8"]
