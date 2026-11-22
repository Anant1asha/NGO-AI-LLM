"""validate_routing() — pure validation of a proposed routing config.

Used by both the validate endpoint (no write) and the apply path (write only
after ok=True) so the two always enforce the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hachi.core.routing.capability import Capability
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry


@dataclass
class RoutingValidationResult:
    """Outcome of validate_routing().

    Attributes:
        ok:       True when the config is safe to apply.
        issues:   Blocking problems (non-empty → ok=False).
        warnings: Non-blocking observations (costly model choices, etc.).
    """

    ok: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_routing(
    registry: ModelRegistry,
    policy: RoutingPolicy,
    *,
    providers: Any = None,  # ProviderRegistry | None — unused today, reserved for future
) -> RoutingValidationResult:
    """Check that *policy* + *registry* form a valid, applicable routing config.

    Rules (blocking issues):
      - ``default_model`` must be non-empty and non-whitespace.
      - Every capability key in ``policy.capabilities`` must parse to a known
        :class:`~hachi.core.routing.capability.Capability` value.

    Advisory warnings (non-blocking):
      - Re-uses ``policy.costly_capability_warnings()`` (BB-30 guard) to flag
        any explicit per-capability override that prices orders-of-magnitude
        more than the default model.

    Unknown model IDs in the config are allowed — the router's amendment A11
    synthesises a minimal descriptor so undeclared models remain usable.

    Args:
        registry:  The model catalog to validate against.
        policy:    The routing policy to check.
        providers: Reserved; not used in validation today.

    Returns:
        A :class:`RoutingValidationResult` with ``ok``, ``issues``, and
        ``warnings`` populated.
    """
    issues: list[str] = []
    warnings: list[str] = []

    # Rule 1: default_model must be non-empty.
    if not (policy.default_model or "").strip():
        issues.append("default_model is empty or whitespace — a fallback model is required")

    # Rule 2: every capability key must be a known Capability value.
    valid_cap_values = {c.value for c in Capability}
    for cap_name in policy.capabilities or {}:
        if cap_name not in valid_cap_values:
            issues.append(
                f"Unknown capability key {cap_name!r} — valid values: "
                + ", ".join(sorted(valid_cap_values))
            )

    # Advisory: costly capability overrides (BB-30).
    try:
        warnings.extend(policy.costly_capability_warnings())
    except Exception:
        pass

    return RoutingValidationResult(ok=not issues, issues=issues, warnings=warnings)
