"""Declarative tool registration for the boot sequence.

TOOL_SPECS is a topologically-ordered table of registrations. ToolRegistrar
enforces ordering constraints (after, last) at install time.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BootDeps:
    """Injectable dependency bundle for tool registration.

    Constructed from real objects in boot_agent(); tests pass fakes.
    """

    gate: Any
    skill_engine: Any
    checkpoint_manager: Any
    vault: Any  # MemoryVault | None
    job_queue: Any
    session_store: Any
    integrations: Any
    mcp_manager: Any
    scheduler: Any
    relay_event: Callable[..., Any]
    sub_agent_llm: Any
    cost_tracker: Any
    provider_kind: str
    secret_store: Any
    tool_registry: Any  # ToolRegistry — passed so specs can access it
    # P4-01: write-target lease manager (None when delegation is disabled)
    lease_manager: Any = None
    # P4-G: ModelRouter for capability-based routing (None when routing is unconfigured).
    router: Any = None
    # P4-G: ProviderRegistry for speech/search provider resolution (None when unavailable).
    provider_registry: Any = None
    # P4-G: Session LLM client (raw, pre-routing); used to check supports_vision for vision tools.
    session_llm: Any = None


@dataclass
class ToolSpec:
    """One entry in the TOOL_SPECS table."""

    name: str
    register_fn: Callable[[BootDeps], Any]
    # Specs that must complete before this one runs (topological ordering).
    after: set[str] = field(default_factory=set)
    # If True, this spec runs after ALL others (except other last=True specs).
    last: bool = False


class ToolRegistrar:
    """Installs ToolSpecs in dependency order.

    Uses topological sort on the ``after`` constraints. ``last=True`` specs run
    after all non-last specs; ordering among ``last=True`` specs is by insertion order.
    Raises ValueError if a cycle is detected or an unknown ``after`` dep is named.
    """

    def install(self, specs: list[ToolSpec], deps: BootDeps) -> dict[str, Any]:
        """Run all specs in order, returning a map of name → return value.

        Args:
            specs: The TOOL_SPECS list.
            deps: The BootDeps bundle.

        Returns:
            dict mapping each spec name to the return value of its register_fn.
        """
        regular = [s for s in specs if not s.last]
        last_specs = [s for s in specs if s.last]

        ordered_regular = self._toposort(regular)
        results: dict[str, Any] = {}

        for spec in ordered_regular:
            logger.debug("Registering tool group: %s", spec.name)
            results[spec.name] = spec.register_fn(deps)

        for spec in last_specs:
            logger.debug("Registering tool group (last): %s", spec.name)
            results[spec.name] = spec.register_fn(deps)

        return results

    def _toposort(self, specs: list[ToolSpec]) -> list[ToolSpec]:
        """Kahn's algorithm — raises ValueError on cycles or unknown deps."""
        name_set = {s.name for s in specs}
        for spec in specs:
            unknown = spec.after - name_set
            if unknown:
                raise ValueError(
                    f"Tool spec '{spec.name}' declares after={unknown!r}, "
                    f"but those names are not in the spec list."
                )

        in_degree: dict[str, int] = {s.name: 0 for s in specs}
        dependents: dict[str, list[str]] = {s.name: [] for s in specs}
        for spec in specs:
            for dep in spec.after:
                dependents[dep].append(spec.name)
                in_degree[spec.name] += 1

        queue = [s for s in specs if in_degree[s.name] == 0]
        result: list[ToolSpec] = []
        spec_by_name = {s.name: s for s in specs}

        while queue:
            current = queue.pop(0)
            result.append(current)
            for dependent_name in dependents[current.name]:
                in_degree[dependent_name] -= 1
                if in_degree[dependent_name] == 0:
                    queue.append(spec_by_name[dependent_name])

        if len(result) != len(specs):
            remaining = {s.name for s in specs} - {s.name for s in result}
            raise ValueError(f"Cycle detected in tool registration order: {remaining}")

        return result
