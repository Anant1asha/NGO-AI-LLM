"""View registry — maps view_id → CockpitView subclass.

Wave-3 agents: import your class here and add it to VIEW_REGISTRY.
The canonical class names are fixed — do not rename them.
"""

from __future__ import annotations

from hachi.tui.cockpit.base import CockpitView
from hachi.tui.cockpit.views.agents import AgentsView
from hachi.tui.cockpit.views.approvals import ApprovalsView
from hachi.tui.cockpit.views.audit import AuditView
from hachi.tui.cockpit.views.chat import ChatView
from hachi.tui.cockpit.views.connections import ConnectionsView
from hachi.tui.cockpit.views.dashboard import DashboardView
from hachi.tui.cockpit.views.governance import GovernanceView
from hachi.tui.cockpit.views.memory import MemoryView
from hachi.tui.cockpit.views.resources import ResourcesView
from hachi.tui.cockpit.views.settings import SettingsView
from hachi.tui.cockpit.views.skills import SkillsView
from hachi.tui.cockpit.views.tasks import TasksView

VIEW_REGISTRY: dict[str, type[CockpitView]] = {
    "chat":        ChatView,
    "dashboard":   DashboardView,
    "agents":      AgentsView,
    "tasks":       TasksView,
    "approvals":   ApprovalsView,
    "governance":  GovernanceView,
    "memory":      MemoryView,
    "skills":      SkillsView,
    "audit":       AuditView,
    "resources":   ResourcesView,
    "connections": ConnectionsView,
    "settings":    SettingsView,
}

__all__ = [
    "VIEW_REGISTRY",
    "CockpitView",
    "ChatView",
    "DashboardView",
    "AgentsView",
    "TasksView",
    "ApprovalsView",
    "GovernanceView",
    "MemoryView",
    "SkillsView",
    "AuditView",
    "ResourcesView",
    "ConnectionsView",
    "SettingsView",
]
