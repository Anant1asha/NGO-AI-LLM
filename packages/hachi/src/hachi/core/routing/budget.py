"""Budget-aware routing helper — Slice 2.5 (Initiative I).

Design doc 15 §9: automatic budget-aware downgrade is **deferred**.
This module provides the OPT-IN hook that consumers (e.g. the loop, a cost-cap tool)
can call explicitly to translate the session's current spend state into
:class:`~hachi.core.routing.router.RouteConstraints`.

Usage example (in the execution loop or a tool)::

    from hachi.core.routing.budget import budget_constraints

    # Pull the current cost snapshot from the tracker.
    snapshot = cost_tracker.snapshot()

    # Derive constraints (returns None below the soft cap — no change).
    constraints = budget_constraints(
        snapshot,
        soft_cap_usd=config.limits.max_session_cost_usd,
        hard_cap_usd=None,
    )
    if constraints is not None:
        resolved = router.select(Capability.REASONING, constraints)
    else:
        resolved = router.select(Capability.REASONING)

**Seam** (doc 15 §9): fully automatic downgrade — where the loop itself injects
``budget_constraints`` on every turn without the caller opting in — is intentionally
deferred. The trigger condition is: per-turn cost spikes become a UX problem at scale
*and* the latency/quality-aware ordering (also deferred) gives the auto-policy
meaningful model variety to choose from. Until then, callers opt in explicitly.
"""

from __future__ import annotations

from hachi.core.routing.router import RouteConstraints


def budget_constraints(
    snapshot: object,
    *,
    soft_cap_usd: float | None,
    hard_cap_usd: float | None = None,
    soft_cap_fraction: float = 0.80,
) -> RouteConstraints | None:
    """Derive :class:`RouteConstraints` from the current spend state.

    Returns ``None`` when spend is comfortably below the soft cap (no constraints
    needed — default routing applies).  Returns a :class:`RouteConstraints` with
    ``prefer="cost"`` (and optionally a ``max_input_cost_per_mtok`` ceiling) once
    spend reaches the soft-cap threshold.

    This is **opt-in**: callers must pass it explicitly to ``ModelRouter.select()``.
    The default routing path is not changed.  See module docstring for the
    auto-downgrade seam note.

    Args:
        snapshot: A :class:`~hachi.core.cost.CostSnapshot` (or any object with an
            ``estimated_cost_usd`` float attribute).
        soft_cap_usd: The session spend cap in USD.  When ``None``, no budget
            constraints are applied (returns ``None``).
        hard_cap_usd: Optional tighter ceiling applied as
            ``max_input_cost_per_mtok`` — limits routing to only the cheapest
            model tier.  When ``None``, no cost-per-token ceiling is set (prefer
            ordering alone handles it).
        soft_cap_fraction: Fraction of ``soft_cap_usd`` at which the soft cap
            triggers.  Default ``0.80`` (80 % of cap).

    Returns:
        ``None`` if no budget pressure, otherwise a :class:`RouteConstraints`
        that biases routing toward cheaper models.

    Example::

        # At 85 % of a $1.00 cap → returns RouteConstraints(prefer="cost")
        constraints = budget_constraints(snapshot, soft_cap_usd=1.0)

        # With a per-token ceiling, routing also excludes models above that price
        constraints = budget_constraints(
            snapshot, soft_cap_usd=1.0, hard_cap_usd=0.005
        )
    """
    if soft_cap_usd is None or soft_cap_usd <= 0:
        return None

    spend: float = float(getattr(snapshot, "estimated_cost_usd", 0.0))
    threshold = soft_cap_usd * soft_cap_fraction

    if spend < threshold:
        return None

    # Spend is at or above the soft-cap threshold: request cost-minimising routing.
    max_input: float | None = None
    if hard_cap_usd is not None and hard_cap_usd > 0:
        # hard_cap_usd is expressed as USD/Mtoken — passed directly as the per-token
        # ceiling.  Callers may derive this from their remaining budget as they see fit.
        # Express as "input cost per Mtoken should not exceed hard_cap_usd per Mtoken"
        max_input = hard_cap_usd

    return RouteConstraints(prefer="cost", max_input_cost_per_mtok=max_input)
