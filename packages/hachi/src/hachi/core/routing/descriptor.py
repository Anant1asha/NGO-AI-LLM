"""Model descriptor and bundled defaults.

``ModelDescriptor`` carries everything the router needs to evaluate a model candidate:
capabilities, context window, output budget, pricing, and feature flags.

``BUNDLED_MODEL_DEFAULTS`` is loaded from ``src/hachi/data/model-registry.json``
(via :func:`~hachi.core.routing.registry_data.load_model_registry_json`).  Adding a
model is a JSON-only edit — no Python change required.  The deferred import in
:func:`_load_bundled` breaks the ``descriptor ↔ registry_data`` circular reference
because ``Pricing`` and ``ModelDescriptor`` are already defined by the time the
function runs.
"""

from __future__ import annotations

from pydantic import BaseModel

from hachi.core.routing.capability import Capability


class Pricing(BaseModel):
    """USD per 1,000,000 tokens for one model.

    ``cache_read_mult`` and ``cache_write_mult`` are multipliers relative to the
    base ``input_per_mtok`` price — mirrors the Anthropic-style accounting already
    in ``cost.py``.
    """

    input_per_mtok: float
    output_per_mtok: float
    cache_read_mult: float = 0.1
    cache_write_mult: float = 1.25


class ModelDescriptor(BaseModel):
    """Immutable description of a single model variant.

    Registered in :class:`~hachi.core.routing.registry.ModelRegistry`; consumed by
    :class:`~hachi.core.routing.router.ModelRouter` for capability filtering and
    ordering.

    Args:
        id: Canonical model identifier (e.g. ``"claude-opus-4-8"``).
        provider: Key matching a registered :class:`~hachi.core.providers.base.AIProvider`
            (e.g. ``"anthropic"``).
        capabilities: Frozen set of :class:`~hachi.core.routing.capability.Capability`
            values the model supports.
        context_window: Maximum input tokens the model accepts.
        max_output: Maximum tokens the model may generate.
        pricing: Per-token cost.  ``None`` means cost is unknown; the router may still
            pick the model unless a hard cost constraint is set.
        supports_tools: Whether the model supports tool/function calling.
        supports_streaming: Whether the model supports streaming generation.
        tier_rank: Lower number = higher quality.  Used for ``prefer="quality"`` ordering
            when multiple models share a capability.  Defaults to 50 (mid-tier).
    """

    id: str
    provider: str
    capabilities: frozenset[Capability]
    context_window: int
    max_output: int
    pricing: Pricing | None = None
    supports_tools: bool = True
    supports_streaming: bool = True
    tier_rank: int = 50  # lower = higher quality; used for quality ordering


# ---------------------------------------------------------------------------
# Bundled defaults — loaded from model-registry.json (JSON is the source of truth)
# ---------------------------------------------------------------------------


def _load_bundled() -> list[ModelDescriptor]:
    # Deferred import: registry_data imports Pricing/ModelDescriptor from this module.
    # Both are already defined above by the time this function executes at module level.
    from hachi.core.routing.registry_data import load_model_registry_json

    return load_model_registry_json()


BUNDLED_MODEL_DEFAULTS: list[ModelDescriptor] = _load_bundled()
