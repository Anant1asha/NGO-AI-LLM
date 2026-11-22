"""ModelRouter — deterministic capability-based model selection.

Design doc 15 §3.  Given a health snapshot, ``select()`` is pure: same inputs
yield the same route.  Results are sticky per capability per turn (amendment A12).

Algorithm:
  1. candidates ← policy.candidates(cap)  # explicit config order
     if empty: candidates ← registry.by_capability(cap)
  2. resolve each id → ModelDescriptor via registry; drop unknowns
     (A11: unknown ids get a synthetic REASONING descriptor so they're usable)
  3. hard-filter: context_window, supports_tools, VISION capability, cost cap
  4. drop models whose provider breaker is OPEN
  5. order survivors: explicit config order wins; else by ``prefer``
  6. primary = survivors[0]; fallbacks = survivors[1:K]
  7. build ResilientClient(primary + fallback chain) → ResolvedModel
  8. NoRouteError if no survivors
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

if TYPE_CHECKING:
    from hachi.core.routing.snapshot import RoutingSnapshot

from pydantic import BaseModel, ConfigDict

from hachi.core.llm import BaseLLMClient
from hachi.core.resilience import HealthRecorder, ResilientClient, RetryPolicy
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry

logger = logging.getLogger(__name__)

_MAX_FALLBACKS = 2  # Maximum number of fallback candidates behind the primary.


class NoRouteError(Exception):
    """Raised when no model survives the routing algorithm.

    Args:
        capability: The capability that was requested.
        reason: Human-readable explanation (surfaced in logs and events).
    """

    def __init__(self, capability: Capability, reason: str = "") -> None:
        self.capability = capability
        self.reason = reason
        super().__init__(f"No route for {capability!r}: {reason}")


class RouteConstraints(BaseModel):
    """Hard constraints applied during routing step 3.

    Args:
        min_context: Minimum context window in tokens the model must support.
        needs_tools: Model must support tool/function calling.
        needs_vision: Model must have the VISION capability.
        max_input_cost_per_mtok: Hard cost ceiling (USD / 1M input tokens).
            Models with ``pricing=None`` are allowed through unless this is set.
        prefer: Ordering strategy when multiple models survive:
            ``"cost"`` cheapest first; ``"quality"`` highest tier first;
            ``"balanced"`` (default) cheapest among those meeting a quality floor.
    """

    model_config = ConfigDict(extra="ignore")

    min_context: int | None = None
    needs_tools: bool = False
    needs_vision: bool = False
    max_input_cost_per_mtok: float | None = None
    prefer: Literal["cost", "quality", "balanced"] = "balanced"


class ResolvedModel(NamedTuple):
    """Result of a successful ``ModelRouter.select()`` call.

    Attributes:
        client: A :class:`~hachi.core.resilience.ResilientClient` wrapping the
            primary model with the fallback chain wired in.
        descriptor: The :class:`~hachi.core.routing.descriptor.ModelDescriptor` of
            the primary model.
    """

    client: BaseLLMClient
    descriptor: ModelDescriptor


class ModelRouter:
    """Routes capability requests to the best available model.

    Stickiness (amendment A12): each ``select()`` call caches its result by
    ``(capability, constraints_fingerprint)`` within a single turn.  Call
    ``new_turn()`` at the start of each turn to clear the sticky cache.

    Args:
        registry: The :class:`~hachi.core.routing.registry.ModelRegistry`.
        policy: The :class:`~hachi.core.routing.policy.RoutingPolicy`.
        providers: The :class:`~hachi.core.providers.registry.ProviderRegistry`.
        resilience: The :class:`~hachi.core.resilience.RetryPolicy` for wrapping clients.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        policy: RoutingPolicy,
        providers: Any,  # ProviderRegistry — avoid circular import
        resilience: RetryPolicy,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._providers = providers
        self._resilience = resilience
        # Per-turn sticky cache: (Capability, constraints_key) → ResolvedModel
        self._sticky: dict[tuple[Capability, str], ResolvedModel] = {}
        # Health recorders keyed by provider name.
        self._recorders: dict[str, HealthRecorder] = {}

    # ------------------------------------------------------------------
    # Turn lifecycle
    # ------------------------------------------------------------------

    def new_turn(self) -> None:
        """Clear the sticky route cache.  Call at the start of each turn."""
        self._sticky.clear()

    def apply_snapshot(self, snap: RoutingSnapshot) -> None:
        """Adopt a new routing config at the turn boundary.

        Safe to call from the session's own turn thread only — no lock needed
        because each router is single-threaded-per-session (calls within a session
        serialise on _chat_lock upstream). Clears _sticky so the new config takes
        effect from the very next select() call in this turn.

        Args:
            snap: The new :class:`~hachi.core.routing.snapshot.RoutingSnapshot`.
        """
        self._registry = snap.registry
        self._policy = snap.policy
        self._resilience = snap.resilience
        self._sticky.clear()
        logger.debug(
            "ModelRouter.apply_snapshot: v%d (source=%s default=%s)",
            snap.version,
            snap.source,
            snap.policy.default_model,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(
        self,
        capability: Capability,
        constraints: RouteConstraints | None = None,
    ) -> ResolvedModel:
        """Pick the best available model for *capability* and return a resilient client.

        Pure / deterministic given a fixed health snapshot.  Results are sticky
        per ``(capability, constraints)`` within a turn (amendment A12).

        Args:
            capability: The :class:`~hachi.core.routing.capability.Capability` to route.
            constraints: Optional :class:`RouteConstraints` for hard filtering.

        Returns:
            A :class:`ResolvedModel` wrapping the primary client and descriptor.

        Raises:
            :class:`NoRouteError`: When no model survives all filters.
        """
        if constraints is None:
            constraints = RouteConstraints()

        sticky_key = (capability, _constraints_key(constraints))
        if sticky_key in self._sticky:
            return self._sticky[sticky_key]

        resolved = self._resolve(capability, constraints)
        self._sticky[sticky_key] = resolved
        return resolved

    def default_client(self) -> BaseLLMClient:
        """Return a resilient client for the configured default_model.

        Preserves today's single-client path: the execution loop calls this
        as its primary LLM client when no per-turn routing is needed.
        Returns a :class:`~hachi.core.resilience.ResilientClient` wrapping the
        raw provider client.
        """
        model_id = self._policy.default_model
        desc = self._registry.get(model_id)
        if desc is None:
            # A11: unknown model → synthesise a REASONING descriptor.
            desc = _synthetic_descriptor(model_id)

        raw_client = self._build_client(desc)
        recorder = self._get_recorder(desc.provider)
        return ResilientClient(inner=raw_client, policy=self._resilience, recorder=recorder)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve(self, capability: Capability, constraints: RouteConstraints) -> ResolvedModel:
        """Full routing algorithm (doc 15 §3)."""

        # Step 1: candidate model ids.
        # Track whether the order came from explicit policy (wins over prefer) or
        # from registry derivation (prefer-order applies).
        explicit_policy_ids = self._policy.candidates(capability)
        has_explicit_order = bool(explicit_policy_ids)
        if explicit_policy_ids:
            candidate_ids = explicit_policy_ids
        else:
            candidate_ids = [d.id for d in self._registry.by_capability(capability)]

        # Step 2: resolve to ModelDescriptor; unknown ids get synthetic REASONING descriptor.
        descriptors: list[ModelDescriptor] = []
        for mid in candidate_ids:
            desc = self._registry.get(mid)
            if desc is None:
                desc = _synthetic_descriptor(mid)
            descriptors.append(desc)

        # Step 3: hard-filter by constraints.
        filtered = [d for d in descriptors if _passes_hard_filter(d, constraints)]

        # Step 4: drop models whose provider breaker is OPEN.
        health_map = self._providers.health() if self._providers is not None else {}
        usable = [d for d in filtered if _provider_usable(d.provider, health_map)]

        if not usable:
            reason = (
                f"all {len(descriptors)} candidates filtered out "
                f"(hard_filter={len(filtered)}, breaker_check={len(usable)})"
            )
            raise NoRouteError(capability, reason)

        # Step 5: order survivors.
        if has_explicit_order:
            # Explicit policy order wins; preserve original relative order of survivors.
            id_order = {mid: idx for idx, mid in enumerate(candidate_ids)}
            ordered = sorted(usable, key=lambda d: id_order.get(d.id, len(candidate_ids)))
        else:
            ordered = _order_by_prefer(usable, constraints.prefer)

        # Step 6: primary + bounded fallbacks.
        primary_desc = ordered[0]
        fallback_descs = ordered[1 : 1 + _MAX_FALLBACKS]

        # Step 7: build ResilientClient with fallback chain.
        primary_recorder = self._get_recorder(primary_desc.provider)
        primary_client = self._build_client(primary_desc)

        fallback_chain: list[tuple[BaseLLMClient, HealthRecorder]] = []
        for fb_desc in fallback_descs:
            fb_recorder = self._get_recorder(fb_desc.provider)
            fb_client = self._build_client(fb_desc)
            fallback_chain.append((fb_client, fb_recorder))

        resilient = ResilientClient(
            inner=primary_client,
            policy=self._resilience,
            recorder=primary_recorder,
            fallbacks=fallback_chain,
        )

        logger.debug(
            "ModelRouter.select(%s): primary=%s fallbacks=%s",
            capability,
            primary_desc.id,
            [d.id for d in fallback_descs],
        )

        return ResolvedModel(client=resilient, descriptor=primary_desc)

    def _build_client(self, desc: ModelDescriptor) -> BaseLLMClient:
        """Build a raw (non-resilient) client for *desc* via its provider adapter."""
        if self._providers is not None:
            provider = self._providers.get_by_name(desc.provider)
            if provider is not None:
                try:
                    return provider.build_llm_client(desc.id)
                except Exception:
                    logger.debug(
                        "ModelRouter._build_client: provider %r failed for %r; "
                        "falling back to create_llm_client",
                        desc.provider,
                        desc.id,
                        exc_info=True,
                    )

        # Fallback: use create_llm_client directly.
        from hachi.core.llm import create_llm_client

        return create_llm_client({"kind": desc.provider, "model": desc.id})

    def _get_recorder(self, provider_name: str) -> HealthRecorder:
        """Return (or create) the HealthRecorder for *provider_name*.

        H7: wires the recorder's ``on_update`` sink to the real provider
        adapter's ``update_health`` when one is available, so the breaker
        filter in ``_resolve`` reflects actual call outcomes instead of the
        permanent boot-time default (``available=True``, breaker "closed").
        """
        if provider_name not in self._recorders:
            on_update = None
            if self._providers is not None:
                provider = self._providers.get_by_name(provider_name)
                if provider is not None and hasattr(provider, "update_health"):
                    on_update = provider.update_health
            self._recorders[provider_name] = HealthRecorder(
                provider_name, self._resilience, on_update=on_update
            )
        return self._recorders[provider_name]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_provider(model_id: str) -> str:
    """Guess a provider ``kind`` from a model id's naming family (H7).

    Undeclared models previously always synthesized as ``provider="anthropic"``
    regardless of what the id actually looked like — an undeclared ``gpt-4o``
    or ``gemini-2.0`` would be built against the wrong client. This is a
    best-effort naming-convention match, not a registry lookup; genuinely
    ambiguous ids still fall back to "anthropic" (the pre-existing default).
    """
    lowered = model_id.lower()
    if lowered.startswith(("gpt-", "o1", "o1-", "o3", "o3-", "o4", "o4-")) or "openai" in lowered:
        return "openai-compatible"
    if "gemini" in lowered:
        return "gemini"
    if "grok" in lowered:
        return "openai-compatible"  # xAI's API is OpenAI-compatible
    if lowered.startswith("claude") or "anthropic" in lowered:
        return "anthropic"
    return "anthropic"  # safest default; unrecognized families fall through here


def _synthetic_descriptor(model_id: str) -> ModelDescriptor:
    """Create a minimal descriptor for an undeclared model (amendment A11)."""
    from hachi.core.routing.descriptor import ModelDescriptor

    return ModelDescriptor(
        id=model_id,
        provider=_infer_provider(model_id),
        capabilities=frozenset({Capability.REASONING}),
        context_window=200_000,
        max_output=8_192,
        pricing=None,
    )


def _passes_hard_filter(desc: ModelDescriptor, constraints: RouteConstraints) -> bool:
    """Return ``True`` when *desc* satisfies all hard constraints."""
    if constraints.min_context is not None and desc.context_window < constraints.min_context:
        return False
    if constraints.needs_tools and not desc.supports_tools:
        return False
    if constraints.needs_vision and Capability.VISION not in desc.capabilities:
        return False
    if constraints.max_input_cost_per_mtok is not None:
        if desc.pricing is None:
            # Unknown pricing: allow through (cost-unknown models are not blocked).
            pass
        elif desc.pricing.input_per_mtok > constraints.max_input_cost_per_mtok:
            return False
    return True


def _provider_usable(provider_name: str, health_map: dict[str, Any]) -> bool:
    """Return ``True`` when the provider's breaker is not fully open."""
    health = health_map.get(provider_name)
    if health is None:
        return True  # Unknown provider → assume available.
    return bool(health.is_usable())


def _order_by_prefer(
    descriptors: list[ModelDescriptor],
    prefer: Literal["cost", "quality", "balanced"],
) -> list[ModelDescriptor]:
    """Sort *descriptors* by the ``prefer`` strategy."""
    if prefer == "cost":

        def _cost_key(d: ModelDescriptor) -> tuple[float, float]:
            if d.pricing is None:
                return (float("inf"), float("inf"))
            return (d.pricing.input_per_mtok, d.pricing.output_per_mtok)

        return sorted(descriptors, key=_cost_key)

    if prefer == "quality":
        return sorted(descriptors, key=lambda d: d.tier_rank)

    # "balanced": cheapest among those with acceptable quality (tier_rank ≤ median).
    ranks = sorted(d.tier_rank for d in descriptors)
    quality_floor = ranks[len(ranks) // 2] if ranks else 0

    def _balanced_key(d: ModelDescriptor) -> tuple[int, float, float]:
        in_floor = 0 if d.tier_rank <= quality_floor else 1
        if d.pricing is None:
            return (in_floor, float("inf"), float("inf"))
        return (in_floor, d.pricing.input_per_mtok, d.pricing.output_per_mtok)

    return sorted(descriptors, key=_balanced_key)


def _constraints_key(c: RouteConstraints) -> str:
    """Stable string fingerprint of *c* for the sticky-route cache key."""
    return (
        f"{c.min_context}:{c.needs_tools}:{c.needs_vision}:{c.max_input_cost_per_mtok}:{c.prefer}"
    )
