"""RoutingPolicy — the capability-to-candidates map.

This is the "Capability Registry" of the design brief — it maps each
:class:`~hachi.core.routing.capability.Capability` to an ordered list of model ids.

Back-compat (critical): when ``[routing]`` is absent from config, ``from_config``
synthesises a policy that maps EVERY capability to the single configured
``provider.model`` — identical to today's behaviour.

Amendment A1: ``auto=True`` derives a sensible default from the registry (cheapest
capable model for title_generation/compaction, any vision-capable model for vision,
session model for reasoning) so users get the benefit without hand-writing a table.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from hachi.core.routing.capability import Capability

if TYPE_CHECKING:
    from hachi.core.routing.registry import ModelRegistry

logger = logging.getLogger(__name__)


class RoutingPolicy(BaseModel):
    """Ordered candidate-model mapping per capability.

    Args:
        default_model: The fallback/session model.  ``ModelRouter.default_client()``
            uses this.
        capabilities: Explicit capability → ordered model-id list.  When empty for a
            given capability, the router derives candidates from the registry.
        auto: When ``True``, smart-defaults are layered in for capabilities that have
            no explicit entry (title_generation/compaction → cheapest; vision → any
            vision-capable; reasoning → default_model).
    """

    model_config = ConfigDict(extra="ignore")

    default_model: str = "claude-haiku-4-5"
    capabilities: dict[Capability, list[str]] = {}
    auto: bool = False

    def candidates(self, cap: Capability) -> list[str]:
        """Return the ordered candidate model ids for *cap*.

        An empty list means the router should derive candidates from the registry.
        """
        return self.capabilities.get(cap, [])

    def costly_capability_warnings(self, registry: ModelRegistry) -> list[str]:
        """Cost-governance guard (pure — never mutates routing).

        Flag when a high-volume chat capability (reasoning/coding) is pinned to a
        model substantially pricier (>= 3x input price) than this policy's
        ``default_model``, while ``default_model`` itself supports that capability.

        This surfaces the silent "every chat turn is routed to the priciest model"
        trap — e.g. ``default_model = "gpt-4o-mini"`` but
        ``routing.capabilities.reasoning = ["gpt-4o"]`` (~16x the input price) — so it
        shows up loudly at boot instead of hiding in the routing table. It does NOT
        change routing; an explicit choice is respected, only surfaced.
        """

        def _input_price(model_id: str) -> float | None:
            if not model_id:
                return None
            try:
                pricing = registry.pricing_for_model(model_id)
            except Exception:
                return None
            return float(pricing.input_per_mtok) if pricing is not None else None

        warnings: list[str] = []
        default_price = _input_price(self.default_model)
        if default_price is None or default_price <= 0:
            return warnings

        for cap in (Capability.REASONING, Capability.CODING):
            models = self.capabilities.get(cap) or [self.default_model]
            resolved = models[0] if models else self.default_model
            if not resolved or resolved == self.default_model:
                continue
            resolved_price = _input_price(resolved)
            if resolved_price is None:
                continue
            # Only warn if the cheaper default is actually viable for this capability.
            try:
                capable_ids = {d.id for d in registry.by_capability(cap)}
            except Exception:
                capable_ids = set()
            if self.default_model not in capable_ids:
                continue
            ratio = resolved_price / default_price
            if ratio >= 3.0:
                warnings.append(
                    f"[cost] routing.capabilities.{cap.value} = {resolved!r} costs "
                    f"${resolved_price:.2f}/Mtok input — {ratio:.0f}x your routing "
                    f"default_model {self.default_model!r} (${default_price:.2f}/Mtok), "
                    f"which also supports {cap.value}. Every {cap.value} turn pays the "
                    f"higher rate. Repoint [routing.capabilities].{cap.value} to a cheaper "
                    f"model unless you specifically need {resolved}."
                )
        return warnings

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: object) -> RoutingPolicy:
        """Build a :class:`RoutingPolicy` from a :class:`~hachi.core.settings.ResolvedConfig`.

        When ``config.routing`` is absent (no ``[routing]`` TOML section), synthesises
        a back-compat policy that maps every capability to the single configured
        ``provider.model`` — byte-for-byte today's behaviour through the new mechanism.

        Args:
            config: A :class:`~hachi.core.settings.ResolvedConfig` instance (or any
                object with a ``provider.model`` attribute and an optional ``routing``
                attribute).

        Returns:
            A :class:`RoutingPolicy`.
        """
        routing = getattr(config, "routing", None)

        if routing is None:
            # Back-compat synthesis: no [routing] section → single model for everything.
            default_model = _get_provider_model(config)
            logger.debug(
                "RoutingPolicy.from_config: no [routing] section — "
                "synthesising back-compat policy (model=%s)",
                default_model,
            )
            all_caps = {cap: [default_model] for cap in Capability}
            return cls(default_model=default_model, capabilities=all_caps, auto=False)

        # Explicit [routing] section present.
        default_model = getattr(routing, "default_model", None) or _get_provider_model(config)
        raw_caps: dict[str, list[str]] = getattr(routing, "capabilities", {}) or {}
        auto: bool = bool(getattr(routing, "auto", False))

        # Coerce string keys to Capability enum (tolerant of unknown strings).
        caps: dict[Capability, list[str]] = {}
        for key, val in raw_caps.items():
            try:
                caps[Capability(key)] = list(val)
            except ValueError:
                logger.warning(
                    "RoutingPolicy.from_config: unknown capability key %r — skipped", key
                )

        return cls(default_model=default_model, capabilities=caps, auto=auto)

    def derive_auto_policy(self, registry: ModelRegistry) -> RoutingPolicy:
        """Return a new policy with smart-defaults layered in for empty slots (A1).

        For capabilities not already in ``self.capabilities``:
          - ``TITLE_GENERATION`` / ``COMPACTION`` → cheapest capable model
          - ``VISION`` → any vision-capable model
          - ``REASONING`` (and others) → ``default_model``

        Args:
            registry: A :class:`~hachi.core.routing.registry.ModelRegistry` instance.

        Returns:
            A :class:`RoutingPolicy` with auto-derived entries merged in.
        """
        if not self.auto:
            return self

        merged: dict[Capability, list[str]] = dict(self.capabilities)

        def _cheapest_cap(cap: Capability) -> list[str]:
            try:
                candidates = registry.by_capability(cap)
            except Exception:
                return []
            priced = [d for d in candidates if d.pricing is not None]
            if priced:
                cheapest = min(
                    priced,
                    key=lambda d: d.pricing.input_per_mtok + d.pricing.output_per_mtok,
                )
                return [cheapest.id]
            return [d.id for d in candidates[:1]]

        for cheap_cap in (Capability.TITLE_GENERATION, Capability.COMPACTION):
            if cheap_cap not in merged:
                result = _cheapest_cap(cheap_cap)
                if result:
                    merged[cheap_cap] = result

        if Capability.VISION not in merged:
            try:
                vision_models = registry.by_capability(Capability.VISION)
            except Exception:
                vision_models = []
            if vision_models:
                merged[Capability.VISION] = [d.id for d in vision_models]

        if Capability.REASONING not in merged:
            merged[Capability.REASONING] = [self.default_model]

        return RoutingPolicy(default_model=self.default_model, capabilities=merged, auto=self.auto)


def _get_provider_model(config: object) -> str:
    """Extract ``provider.model`` from config, defaulting to ``claude-haiku-4-5``."""
    provider = getattr(config, "provider", None)
    if provider is not None:
        return str(getattr(provider, "model", "claude-haiku-4-5"))
    # config might be a dict (legacy path)
    if isinstance(config, dict):
        cfg_dict: dict[str, object] = config
        provider_section = cfg_dict.get("provider", {})
        if isinstance(provider_section, dict):
            return str(provider_section.get("model", "claude-haiku-4-5"))
    return "claude-haiku-4-5"
