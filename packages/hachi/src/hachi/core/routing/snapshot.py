"""RoutingSnapshot — immutable routing config bundle for per-session pull-at-turn-boundary.

A snapshot bundles the three config objects the ModelRouter reads:
  - ModelRegistry  — what models exist and their pricing/capabilities
  - RoutingPolicy  — default_model + per-capability model lists
  - RetryPolicy    — resilience / retry parameters

It does NOT include the ProviderRegistry.  Providers bake API keys at boot
(base URL, credential); swapping those requires _reload_agents().  Only the
*routing* layer (which model to pick) is hot-swappable via this snapshot.

version: monotonic int incremented by RoutingConfigStore.apply(); used by each
session's ExecutionLoop to check whether its current snapshot is stale.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hachi.core.resilience import RetryPolicy
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry


@dataclass(frozen=True)
class RoutingSnapshot:
    """Immutable bundle of routing config consumed by ModelRouter.

    Args:
        registry:   The model catalog.
        policy:     Capability → model mappings + default_model.
        resilience: Retry/circuit-breaker policy for LLM calls.
        version:    Monotonic version counter (set by RoutingConfigStore).
        source:     Human-readable origin for audit records (e.g. "ui", "init").
    """

    registry: ModelRegistry
    policy: RoutingPolicy
    resilience: RetryPolicy
    version: int
    source: str = field(default="init")
