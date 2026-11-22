"""Tests for ModelRegistry and pricing parity guard (Slice 2.1 / Phase 1).

GATE tests:
  - Pricing parity: registry pricing == MODEL_PRICING (both derived from model-registry.json).
  - /models regression: configured model appears in registry.all().
"""

from __future__ import annotations

from hachi.core.cost import MODEL_PRICING
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing
from hachi.core.routing.registry import ModelRegistry

# ---------------------------------------------------------------------------
# Pricing parity guard (doc 14 §7)
# ---------------------------------------------------------------------------


class TestPricingParity:
    """Assert registry pricing == MODEL_PRICING — both are computed from model-registry.json."""

    def _registry_price(self, registry: ModelRegistry, prefix: str) -> tuple[float, float] | None:
        pricing = registry.pricing_for_model(prefix)
        if pricing is None:
            return None
        return (pricing.input_per_mtok, pricing.output_per_mtok)

    def test_claude_opus_4_parity(self) -> None:
        reg = ModelRegistry.build(object(), None)
        old = MODEL_PRICING["claude-opus-4"]
        new = self._registry_price(reg, "claude-opus-4")
        assert new == old, f"claude-opus-4 pricing mismatch: registry={new} vs cost.py={old}"

    def test_claude_sonnet_4_parity(self) -> None:
        reg = ModelRegistry.build(object(), None)
        old = MODEL_PRICING["claude-sonnet-4"]
        new = self._registry_price(reg, "claude-sonnet-4")
        assert new == old, f"claude-sonnet-4 pricing mismatch: registry={new} vs cost.py={old}"

    def test_claude_haiku_4_parity(self) -> None:
        reg = ModelRegistry.build(object(), None)
        old = MODEL_PRICING["claude-haiku-4"]
        new = self._registry_price(reg, "claude-haiku-4")
        assert new == old, f"claude-haiku-4 pricing mismatch: registry={new} vs cost.py={old}"

    def test_gpt_4o_parity(self) -> None:
        reg = ModelRegistry.build(object(), None)
        old = MODEL_PRICING["gpt-4o"]
        new = self._registry_price(reg, "gpt-4o")
        assert new == old, f"gpt-4o pricing mismatch: registry={new} vs cost.py={old}"

    def test_gpt_4o_mini_parity(self) -> None:
        reg = ModelRegistry.build(object(), None)
        old = MODEL_PRICING["gpt-4o-mini"]
        new = self._registry_price(reg, "gpt-4o-mini")
        assert new == old, f"gpt-4o-mini pricing mismatch: registry={new} vs cost.py={old}"

    def test_dated_variant_resolves_via_prefix(self) -> None:
        """A date-suffixed variant resolves to its base-model price via longest-prefix match."""
        reg = ModelRegistry.build(object(), None)
        old = MODEL_PRICING["claude-opus-4-8"]
        new = self._registry_price(reg, "claude-opus-4-8-20260101")
        assert new == old

    def test_all_json_entries_in_model_pricing(self) -> None:
        """Every priced, non-disabled entry in model-registry.json appears in MODEL_PRICING."""
        import json
        from pathlib import Path

        path = Path(__file__).parent.parent / "src" / "hachi" / "data" / "model-registry.json"
        entries = json.loads(path.read_text(encoding="utf-8"))
        missing = [
            e["id"]
            for e in entries
            if e.get("status", "active") != "disabled"
            and "input_per_mtok" in e
            and e["id"] not in MODEL_PRICING
        ]
        assert not missing, f"JSON models absent from MODEL_PRICING (shim broken): {missing}"


# ---------------------------------------------------------------------------
# ModelRegistry basics
# ---------------------------------------------------------------------------


class TestModelRegistry:
    def _build(self) -> ModelRegistry:
        return ModelRegistry.build(object(), None)

    def test_all_returns_bundled_defaults(self) -> None:
        reg = self._build()
        ids = [d.id for d in reg.all()]
        assert "claude-opus-4-8" in ids
        assert "claude-haiku-4-5" in ids
        assert "gpt-4o" in ids

    def test_get_known_model(self) -> None:
        reg = self._build()
        desc = reg.get("claude-haiku-4-5")
        assert desc is not None
        assert Capability.REASONING in desc.capabilities

    def test_get_unknown_model_returns_none(self) -> None:
        reg = self._build()
        assert reg.get("nonexistent-model-xyz") is None

    def test_by_capability_reasoning(self) -> None:
        reg = self._build()
        models = reg.by_capability(Capability.REASONING)
        assert len(models) > 0
        for d in models:
            assert Capability.REASONING in d.capabilities

    def test_by_capability_vision(self) -> None:
        reg = self._build()
        models = reg.by_capability(Capability.VISION)
        ids = [d.id for d in models]
        assert "claude-opus-4-8" in ids or "gpt-4o" in ids

    def test_register_overrides_bundled(self) -> None:
        reg = self._build()
        custom = ModelDescriptor(
            id="claude-haiku-4-5",
            provider="anthropic",
            capabilities=frozenset({Capability.CODING}),
            context_window=100,
            max_output=100,
            pricing=Pricing(input_per_mtok=999.0, output_per_mtok=999.0),
        )
        reg.register(custom)
        desc = reg.get("claude-haiku-4-5")
        assert desc is not None
        assert desc.pricing is not None
        assert desc.pricing.input_per_mtok == 999.0

    def test_unknown_model_pricing_returns_none(self) -> None:
        reg = self._build()
        result = reg.pricing_for_model("completely-unknown-model-xyz")
        assert result is None

    def test_configured_model_in_all(self) -> None:
        """/models regression: the configured running model appears in registry."""
        reg = self._build()
        # The typical default is claude-haiku-4-5.
        ids = [d.id for d in reg.all()]
        assert "claude-haiku-4-5" in ids


# ---------------------------------------------------------------------------
# Bug 8: current OpenAI models must be in the registry (descriptor + pricing)
# ---------------------------------------------------------------------------


class TestCurrentOpenAIModels:
    """gpt-4.1, gpt-4.1-mini, o3-mini and o4-mini must be catalog members.

    The config-loader defaults to gpt-4o-mini (fixed by Bug 1), but users who
    explicitly configure gpt-4.1-mini (the previous default) or newer models must
    get working cost tracking and model-picker UI.
    """

    NEW_OPENAI_MODELS = ["gpt-4.1", "gpt-4.1-mini", "o3-mini", "o4-mini"]

    def _reg(self) -> ModelRegistry:
        return ModelRegistry.build(object(), None)

    def test_new_openai_models_in_bundled_defaults(self) -> None:
        reg = self._reg()
        ids = {d.id for d in reg.all()}
        for mid in self.NEW_OPENAI_MODELS:
            assert mid in ids, f"{mid} missing from BUNDLED_MODEL_DEFAULTS"

    def test_new_openai_models_have_pricing(self) -> None:
        from hachi.core.cost import MODEL_PRICING

        reg = self._reg()
        for mid in self.NEW_OPENAI_MODELS:
            pricing = reg.pricing_for_model(mid)
            assert pricing is not None, f"{mid} has no pricing in registry"
            # Cross-check against MODEL_PRICING via prefix match.
            best = max(
                (p for p in MODEL_PRICING if mid.startswith(p)),
                key=len,
                default=None,
            )
            assert best is not None, f"{mid} has no prefix entry in MODEL_PRICING"

    def test_gpt_4_1_prefix_collision_resolved(self) -> None:
        """Longest-prefix-wins must not mis-price gpt-4.1-mini as gpt-4.1."""
        from hachi.core.cost import MODEL_PRICING

        assert "gpt-4.1" in MODEL_PRICING, "gpt-4.1 must have an explicit pricing entry"
        assert "gpt-4.1-mini" in MODEL_PRICING, "gpt-4.1-mini must have an explicit pricing entry"
        # Prices must differ (mini is always cheaper).
        assert MODEL_PRICING["gpt-4.1-mini"][0] < MODEL_PRICING["gpt-4.1"][0], (
            "gpt-4.1-mini input price must be less than gpt-4.1"
        )

    def test_o3_mini_has_independent_price_from_o3(self) -> None:
        """o3-mini must not silently inherit o3's pricing via prefix match."""
        from hachi.core.cost import MODEL_PRICING

        assert "o3-mini" in MODEL_PRICING, (
            "o3-mini must have an explicit entry; otherwise it prefix-matches 'o3' and gets "
            "the wrong price"
        )

    def test_drift_guard_covers_new_models(self) -> None:
        """Every model in BUNDLED_MODEL_DEFAULTS must have a MODEL_PRICING prefix match."""
        from hachi.core.cost import MODEL_PRICING
        from hachi.core.routing.descriptor import BUNDLED_MODEL_DEFAULTS

        unpriced = []
        for desc in BUNDLED_MODEL_DEFAULTS:
            has_entry = any(desc.id.startswith(p) for p in MODEL_PRICING)
            if not has_entry:
                unpriced.append(desc.id)
        assert not unpriced, (
            f"Models in BUNDLED_MODEL_DEFAULTS with no MODEL_PRICING prefix: {unpriced}. "
            "Add them to src/hachi/data/model-registry.json."
        )
