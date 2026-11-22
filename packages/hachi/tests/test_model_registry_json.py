"""Tests for model-registry.json loading and load_model_registry_json() (Phase 1).

Covers:
  - JSON parses without error
  - Required fields are present and well-typed
  - user override JSON wins (last entry for same id)
  - status="disabled" entries are excluded from routing
  - status="deprecated" bumps tier_rank but is included
  - round-trip id lookup via ModelRegistry.get()
  - longest-prefix pricing match via ModelRegistry.pricing_for_model()
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hachi.core.routing.descriptor import ModelDescriptor
from hachi.core.routing.registry import ModelRegistry
from hachi.core.routing.registry_data import load_model_registry_json

_BUNDLED_JSON = Path(__file__).parent.parent / "src" / "hachi" / "data" / "model-registry.json"

# ---------------------------------------------------------------------------
# JSON structure
# ---------------------------------------------------------------------------


class TestJsonStructure:
    def test_bundled_json_is_valid(self) -> None:
        raw = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        assert isinstance(raw, list)
        assert len(raw) > 0

    @pytest.mark.parametrize(
        "field", ["id", "provider", "capabilities", "context_window", "max_output"]
    )
    def test_required_fields_present(self, field: str) -> None:
        entries = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        missing = [e.get("id", "<no-id>") for e in entries if field not in e]
        assert not missing, f"Field '{field}' missing from entries: {missing}"

    def test_all_ids_are_strings(self) -> None:
        entries = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        bad = [e.get("id") for e in entries if not isinstance(e.get("id"), str)]
        assert not bad

    def test_all_priced_entries_have_both_prices(self) -> None:
        entries = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        for e in entries:
            has_in = "input_per_mtok" in e
            has_out = "output_per_mtok" in e
            assert has_in == has_out, (
                f"Entry '{e.get('id')}' has only one of input_per_mtok/output_per_mtok"
            )

    def test_tier_rank_is_positive_int(self) -> None:
        entries = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        for e in entries:
            if "tier_rank" in e:
                assert isinstance(e["tier_rank"], int) and e["tier_rank"] > 0, (
                    f"Entry '{e.get('id')}' has bad tier_rank: {e['tier_rank']}"
                )

    def test_no_duplicate_ids(self) -> None:
        entries = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        ids = [e.get("id") for e in entries]
        dupes = [i for i in ids if ids.count(i) > 1]
        assert not dupes, f"Duplicate ids in bundled JSON: {set(dupes)}"


# ---------------------------------------------------------------------------
# load_model_registry_json() behaviour
# ---------------------------------------------------------------------------


class TestLoadModelRegistryJson:
    def test_returns_list_of_descriptors(self) -> None:
        result = load_model_registry_json()
        assert isinstance(result, list)
        assert all(isinstance(d, ModelDescriptor) for d in result)

    def test_bundled_ids_present(self) -> None:
        ids = {d.id for d in load_model_registry_json()}
        assert "claude-opus-4" in ids
        assert "claude-haiku-4-5" in ids
        assert "gpt-4o" in ids
        assert "gpt-4.1" in ids
        assert "o3-mini" in ids

    def test_status_disabled_excluded(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                [
                    {
                        "id": "phantom-model",
                        "provider": "test",
                        "capabilities": [],
                        "context_window": 8000,
                        "max_output": 1000,
                        "status": "disabled",
                    }
                ],
                f,
            )
            tmp = Path(f.name)
        try:
            result = load_model_registry_json(override_path=tmp)
            ids = {d.id for d in result}
            assert "phantom-model" not in ids
        finally:
            tmp.unlink(missing_ok=True)

    def test_status_deprecated_included_with_penalty(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                [
                    {
                        "id": "old-model-x",
                        "provider": "test",
                        "capabilities": [],
                        "context_window": 8000,
                        "max_output": 1000,
                        "tier_rank": 10,
                        "status": "deprecated",
                    }
                ],
                f,
            )
            tmp = Path(f.name)
        try:
            result = load_model_registry_json(override_path=tmp)
            desc = next((d for d in result if d.id == "old-model-x"), None)
            assert desc is not None, "deprecated entry should be included"
            assert desc.tier_rank > 10, "deprecated tier_rank must be bumped"
        finally:
            tmp.unlink(missing_ok=True)

    def test_user_override_wins(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                [
                    {
                        "id": "claude-haiku-4",
                        "provider": "anthropic",
                        "capabilities": ["REASONING"],
                        "context_window": 200000,
                        "max_output": 8192,
                        "input_per_mtok": 999.0,
                        "output_per_mtok": 999.0,
                        "status": "active",
                    }
                ],
                f,
            )
            tmp = Path(f.name)
        try:
            result = load_model_registry_json(override_path=tmp)
            desc = next(d for d in result if d.id == "claude-haiku-4")
            assert desc.pricing is not None
            assert desc.pricing.input_per_mtok == 999.0
        finally:
            tmp.unlink(missing_ok=True)

    def test_missing_override_path_falls_back_to_bundled(self) -> None:
        result_none = load_model_registry_json(override_path=None)
        result_missing = load_model_registry_json(
            override_path=Path("/nonexistent/path/model-registry.json")
        )
        ids_none = {d.id for d in result_none}
        ids_missing = {d.id for d in result_missing}
        assert ids_none == ids_missing


# ---------------------------------------------------------------------------
# Round-trip lookup and pricing via ModelRegistry
# ---------------------------------------------------------------------------


class TestRegistryRoundTrip:
    def _reg(self) -> ModelRegistry:
        return ModelRegistry.build(object(), None)

    def test_all_json_ids_accessible_via_get(self) -> None:
        entries = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        reg = self._reg()
        missing = [
            e["id"]
            for e in entries
            if e.get("status", "active") != "disabled" and reg.get(e["id"]) is None
        ]
        assert not missing, f"IDs in JSON but not accessible via registry.get(): {missing}"

    def test_pricing_round_trip(self) -> None:
        entries = json.loads(_BUNDLED_JSON.read_text(encoding="utf-8"))
        reg = self._reg()
        for e in entries:
            if e.get("status", "active") == "disabled":
                continue
            if "input_per_mtok" not in e:
                continue
            p = reg.pricing_for_model(e["id"])
            assert p is not None, f"{e['id']} has pricing in JSON but not in registry"
            assert p.input_per_mtok == pytest.approx(e["input_per_mtok"]), e["id"]
            assert p.output_per_mtok == pytest.approx(e["output_per_mtok"]), e["id"]

    def test_longest_prefix_pricing_dated_variant(self) -> None:
        """A date-suffixed id prefix-matches its base entry."""
        reg = self._reg()
        p_base = reg.pricing_for_model("claude-opus-4-8")
        p_dated = reg.pricing_for_model("claude-opus-4-8-20260101")
        assert p_base is not None
        assert p_dated is not None
        assert p_dated.input_per_mtok == p_base.input_per_mtok

    def test_gpt_4_1_mini_does_not_inherit_gpt_4_1_price(self) -> None:
        """Longest-prefix match must not price gpt-4.1-mini at the gpt-4.1 rate."""
        reg = self._reg()
        p_full = reg.pricing_for_model("gpt-4.1")
        p_mini = reg.pricing_for_model("gpt-4.1-mini")
        assert p_full is not None
        assert p_mini is not None
        assert p_mini.input_per_mtok < p_full.input_per_mtok

    def test_o3_mini_does_not_inherit_o3_price(self) -> None:
        """o3-mini must not prefix-match o3 and inherit its higher rate."""
        reg = self._reg()
        p_o3 = reg.pricing_for_model("o3")
        p_mini = reg.pricing_for_model("o3-mini")
        assert p_o3 is not None
        assert p_mini is not None
        assert p_mini.input_per_mtok < p_o3.input_per_mtok


# ---------------------------------------------------------------------------
# Phase 2 — new provider entries (Gemini, Grok)
# ---------------------------------------------------------------------------


class TestPhase2NewProviders:
    """Phase 2 pricing validation: Gemini and Grok must be present and priced."""

    GEMINI_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    GROK_MODELS = ["grok-3"]

    def _load(self) -> dict[str, ModelDescriptor]:
        return {d.id: d for d in load_model_registry_json()}

    def test_gemini_models_present(self) -> None:
        """All Gemini 2.5 family entries must be in the bundled registry."""
        ids = set(self._load())
        for mid in self.GEMINI_MODELS:
            assert mid in ids, f"{mid} missing from model-registry.json"

    def test_gemini_models_have_pricing(self) -> None:
        """Every Gemini entry must have a Pricing object."""
        models = self._load()
        for mid in self.GEMINI_MODELS:
            desc = models.get(mid)
            assert desc is not None, f"{mid} not found"
            assert desc.pricing is not None, f"{mid} has no pricing"
            assert desc.pricing.input_per_mtok > 0, f"{mid} has zero input price"
            assert desc.pricing.output_per_mtok > 0, f"{mid} has zero output price"

    def test_gemini_cost_tier_ordering(self) -> None:
        """flash-lite must be cheapest, then flash, then pro."""
        models = self._load()
        pro = models["gemini-2.5-pro"].pricing
        flash = models["gemini-2.5-flash"].pricing
        lite = models["gemini-2.5-flash-lite"].pricing
        assert pro is not None and flash is not None and lite is not None
        assert lite.input_per_mtok < flash.input_per_mtok < pro.input_per_mtok, (
            "gemini-2.5-flash-lite must be cheapest, gemini-2.5-pro most expensive"
        )

    def test_gemini_provider_field(self) -> None:
        """Gemini entries must have provider='google'."""
        models = self._load()
        for mid in self.GEMINI_MODELS:
            desc = models.get(mid)
            assert desc is not None
            assert desc.provider == "google", f"{mid} has wrong provider: {desc.provider!r}"

    def test_grok_models_present(self) -> None:
        """Grok entries must be in the bundled registry."""
        ids = set(self._load())
        for mid in self.GROK_MODELS:
            assert mid in ids, f"{mid} missing from model-registry.json"

    def test_grok_models_have_pricing(self) -> None:
        """Grok entries must have a Pricing object."""
        models = self._load()
        for mid in self.GROK_MODELS:
            desc = models.get(mid)
            assert desc is not None, f"{mid} not found"
            assert desc.pricing is not None, f"{mid} has no pricing"

    def test_new_providers_in_model_pricing(self) -> None:
        """Gemini and Grok entries must appear in MODEL_PRICING shim."""
        from hachi.core.cost import MODEL_PRICING

        for mid in self.GEMINI_MODELS + self.GROK_MODELS:
            assert mid in MODEL_PRICING, (
                f"{mid} present in registry JSON but missing from MODEL_PRICING shim — "
                "add the entry to model-registry.json"
            )
