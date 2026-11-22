"""ModelRegistry — the source of truth for what models exist and what they can do.

Seeding precedence (low → high):
    JSON bundled + user override  ←  provider discovery  ←  config overrides

The registry also exposes a ``pricing_for_model`` helper that replicates the
longest-prefix lookup from ``cost.py`` so ``CostTracker`` can fall back to
it when no registry is available.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing

if TYPE_CHECKING:
    from hachi.core.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry of :class:`~hachi.core.routing.descriptor.ModelDescriptor` instances.

    Thread-safe for concurrent reads after initial population; mutations
    (``register``) are not thread-safe once the registry is in active use.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, ModelDescriptor] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, descriptor: ModelDescriptor) -> None:
        """Add or replace a descriptor (last write wins — config overrides bundled).

        Args:
            descriptor: The :class:`ModelDescriptor` to register.
        """
        self._by_id[descriptor.id] = descriptor

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, model_id: str) -> ModelDescriptor | None:
        """Return the descriptor for *model_id*, or ``None`` if unknown.

        Amendment A11: unknown models should be treated as ``{REASONING}`` callers
        can synthesise a minimal descriptor; this method stays *None*-returning so
        registry-backed code can decide.
        """
        return self._by_id.get(model_id)

    def by_capability(self, cap: Capability) -> list[ModelDescriptor]:
        """Return all registered models that advertise *cap*, in registration order."""
        return [d for d in self._by_id.values() if cap in d.capabilities]

    def all(self) -> list[ModelDescriptor]:
        """Return all registered descriptors (insertion order)."""
        return list(self._by_id.values())

    # ------------------------------------------------------------------
    # Pricing helper (mirrors cost.py longest-prefix logic)
    # ------------------------------------------------------------------

    def pricing_for_model(self, model_id: str) -> Pricing | None:
        """Look up pricing for *model_id* using longest-prefix match.

        Returns ``None`` when no registered descriptor has a matching prefix and
        no exact match is found — the caller decides whether to fall back.
        """
        model_lower = (model_id or "").lower()

        # Exact match first.
        if model_lower in self._by_id and self._by_id[model_lower].pricing is not None:
            return self._by_id[model_lower].pricing

        # Longest prefix match.
        best: Pricing | None = None
        best_len = -1
        for mid, desc in self._by_id.items():
            if desc.pricing is None:
                continue
            if model_lower.startswith(mid.lower()) and len(mid) > best_len:
                best, best_len = desc.pricing, len(mid)

        return best

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, config: object, providers: ProviderRegistry | None) -> ModelRegistry:
        """Seed a registry from bundled defaults, provider discovery, and config overrides.

        Args:
            config: A :class:`~hachi.core.settings.ResolvedConfig`-compatible object.
                    Only ``config.routing.model_overrides`` is consumed.
            providers: A :class:`~hachi.core.providers.registry.ProviderRegistry`.

        Returns:
            A populated :class:`ModelRegistry`.
        """
        reg = cls()

        # 1. Bundled defaults + user config_dir/model-registry.json (lowest precedence).
        from hachi.core.paths import get_hachi_paths
        from hachi.core.routing.registry_data import load_model_registry_json

        try:
            override_path = get_hachi_paths().config_dir / "model-registry.json"
        except Exception:
            override_path = None
        for descriptor in load_model_registry_json(override_path=override_path):
            reg.register(descriptor)

        # 2. Provider-advertised models (override bundled).
        try:
            llm_providers = providers.llm_providers() if providers is not None else []
        except Exception:
            llm_providers = []

        for provider in llm_providers:
            try:
                for descriptor in provider.models():
                    reg.register(descriptor)
            except Exception:
                logger.debug(
                    "ModelRegistry.build: failed to get models from provider %s",
                    getattr(provider, "name", provider),
                    exc_info=True,
                )

        # 3. Config overrides (highest precedence).
        try:
            routing = getattr(config, "routing", None)
            overrides = getattr(routing, "model_overrides", []) if routing is not None else []
            for override in overrides:
                reg.register(override)
        except Exception:
            logger.debug("ModelRegistry.build: failed to apply config overrides", exc_info=True)

        return reg
