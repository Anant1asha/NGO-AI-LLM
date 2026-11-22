"""Regression tests for security hardening fixes found in the audit.

- python_sandbox tier restriction must work under the interactive gate (which
  exposes `.tier` but not `._tier`).
- Sub-agents must not inherit privileged main-agent tools (workflow suspend,
  skill authoring, scheduling).
"""

from __future__ import annotations

import pytest

from hachi.core.loop import ToolRegistry
from hachi.tools.delegation_tools import BLOCKED_TOOL_NAMES
from hachi.tools.sandbox_tools import register_sandbox_tools


class _InteractiveGateLike:
    """Mimics InteractivePermissionGate: exposes `tier`, but no `_tier`."""

    def __init__(self, tier: str) -> None:
        self._value = tier

    @property
    def tier(self) -> str:
        return self._value


@pytest.mark.parametrize("tier", ["sandbox", "guided"])
def test_python_sandbox_blocked_under_interactive_gate(tier: str, monkeypatch) -> None:
    # CRIT-005a: opt the tool in so we can verify the tier-block layer still raises.
    monkeypatch.setenv("HACHI_SANDBOX_PRODUCTION", "1")
    registry = ToolRegistry()
    register_sandbox_tools(registry, _InteractiveGateLike(tier))
    sandbox = registry._tools["python_sandbox"]
    with pytest.raises(PermissionError):
        sandbox("print('should not run')")


def test_python_sandbox_not_registered_without_production_optin(monkeypatch) -> None:
    # CRIT-005a: the sandbox tool must not be exposed at all unless the operator
    # explicitly opts in via HACHI_SANDBOX_PRODUCTION=1.
    monkeypatch.delenv("HACHI_SANDBOX_PRODUCTION", raising=False)
    registry = ToolRegistry()
    register_sandbox_tools(registry, _InteractiveGateLike("unrestricted"))
    assert "python_sandbox" not in registry._tools


def test_sub_agent_blocklist_covers_privileged_tools() -> None:
    # The registered name is core_suspend_workflow (the old "suspend_workflow"
    # entry silently failed to match).
    assert "core_suspend_workflow" in BLOCKED_TOOL_NAMES
    assert "suspend_workflow" not in BLOCKED_TOOL_NAMES
    for name in ("save_skill", "schedule_task", "list_schedules", "cancel_schedule"):
        assert name in BLOCKED_TOOL_NAMES
    # Delegation itself must still be blocked (no recursive spawning).
    assert "delegate_task" in BLOCKED_TOOL_NAMES
