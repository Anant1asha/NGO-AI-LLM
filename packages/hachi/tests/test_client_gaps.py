"""
Unit tests for ``hachi.client.gaps`` — placeholder data getters.

Ensures every getter returns well-formed model instances matching the
expected types.  No network calls.
"""

from __future__ import annotations

from hachi.client.gaps import (
    DATA_GAPS,
    placeholder_active_jobs,
    placeholder_activity,
    placeholder_agents,
    placeholder_approvals,
    placeholder_audit_log,
    placeholder_auth_targets,
    placeholder_capabilities,
    placeholder_config,
    placeholder_dashboard,
    placeholder_failed_jobs,
    placeholder_health,
    placeholder_mcp_servers,
    placeholder_mcp_tools,
    placeholder_memory,
    placeholder_models,
    placeholder_og_nodes,
    placeholder_recall,
    placeholder_routines,
    placeholder_sessions,
    placeholder_setup,
    placeholder_skills,
    placeholder_spend,
    placeholder_tool_calls,
    placeholder_trust_bar,
)
from hachi.client.models import (
    ActivityEvent,
    AgentRow,
    Approval,
    AuditEntry,
    AuthTarget,
    Capability,
    ConfigSnapshot,
    DashboardSnapshot,
    HealthStatus,
    McpServer,
    McpTool,
    MemorySnapshot,
    ModelInfo,
    OgNode,
    RecallHit,
    Routine,
    SessionInfo,
    SetupState,
    Skill,
    SpendSnapshot,
    TaskRow,
    ToolCallRow,
    TrustBarSnapshot,
)

# ---------------------------------------------------------------------------
# DATA_GAPS
# ---------------------------------------------------------------------------


def test_data_gaps_is_frozenset() -> None:
    assert isinstance(DATA_GAPS, frozenset)


# ---------------------------------------------------------------------------
# Type checks — every getter must return the right type(s)
# ---------------------------------------------------------------------------


def test_placeholder_skills_type() -> None:
    result = placeholder_skills()
    assert isinstance(result, list)
    assert all(isinstance(s, Skill) for s in result)
    assert len(result) > 0


def test_placeholder_memory_type() -> None:
    result = placeholder_memory()
    assert isinstance(result, MemorySnapshot)
    assert len(result.groups) > 0


def test_placeholder_recall_type() -> None:
    result = placeholder_recall()
    assert isinstance(result, list)
    assert all(isinstance(h, RecallHit) for h in result)


def test_placeholder_og_nodes_type() -> None:
    result = placeholder_og_nodes()
    assert isinstance(result, list)
    assert all(isinstance(n, OgNode) for n in result)


def test_placeholder_auth_targets_type() -> None:
    result = placeholder_auth_targets()
    assert isinstance(result, list)
    assert all(isinstance(t, AuthTarget) for t in result)


def test_placeholder_spend_type() -> None:
    result = placeholder_spend()
    assert isinstance(result, SpendSnapshot)
    assert len(result.turns) > 0
    assert len(result.models) > 0


def test_placeholder_approvals_type() -> None:
    result = placeholder_approvals()
    assert isinstance(result, list)
    assert all(isinstance(a, Approval) for a in result)


def test_placeholder_audit_log_type() -> None:
    result = placeholder_audit_log()
    assert isinstance(result, list)
    assert all(isinstance(e, AuditEntry) for e in result)


def test_placeholder_active_jobs_type() -> None:
    result = placeholder_active_jobs()
    assert isinstance(result, list)
    assert all(isinstance(t, TaskRow) for t in result)


def test_placeholder_failed_jobs_type() -> None:
    result = placeholder_failed_jobs()
    assert isinstance(result, list)
    assert all(isinstance(t, TaskRow) for t in result)
    assert result[0].error != ""


def test_placeholder_routines_type() -> None:
    result = placeholder_routines()
    assert isinstance(result, list)
    assert all(isinstance(r, Routine) for r in result)


def test_placeholder_agents_type() -> None:
    result = placeholder_agents()
    assert isinstance(result, list)
    assert all(isinstance(a, AgentRow) for a in result)


def test_placeholder_activity_type() -> None:
    result = placeholder_activity()
    assert isinstance(result, list)
    assert all(isinstance(e, ActivityEvent) for e in result)


def test_placeholder_tool_calls_type() -> None:
    result = placeholder_tool_calls()
    assert isinstance(result, list)
    assert all(isinstance(t, ToolCallRow) for t in result)


def test_placeholder_capabilities_type() -> None:
    result = placeholder_capabilities()
    assert isinstance(result, list)
    assert all(isinstance(c, Capability) for c in result)


def test_placeholder_mcp_servers_type() -> None:
    result = placeholder_mcp_servers()
    assert isinstance(result, list)
    assert all(isinstance(s, McpServer) for s in result)


def test_placeholder_mcp_tools_type() -> None:
    result = placeholder_mcp_tools()
    assert isinstance(result, list)
    assert all(isinstance(t, McpTool) for t in result)


def test_placeholder_sessions_type() -> None:
    result = placeholder_sessions()
    assert isinstance(result, list)
    assert all(isinstance(s, SessionInfo) for s in result)


def test_placeholder_config_type() -> None:
    result = placeholder_config()
    assert isinstance(result, ConfigSnapshot)
    assert result.tier in {"sandbox", "guided", "unrestricted"}


def test_placeholder_models_type() -> None:
    result = placeholder_models()
    assert isinstance(result, list)
    assert all(isinstance(m, ModelInfo) for m in result)


def test_placeholder_setup_type() -> None:
    result = placeholder_setup()
    assert isinstance(result, SetupState)
    assert result.needs_setup is False


def test_placeholder_health_type() -> None:
    result = placeholder_health()
    assert isinstance(result, HealthStatus)
    assert result.status == "offline"


def test_placeholder_trust_bar_type() -> None:
    result = placeholder_trust_bar()
    assert isinstance(result, TrustBarSnapshot)
    assert result.tier in {"sandbox", "guided", "unrestricted"}


def test_placeholder_dashboard_type() -> None:
    result = placeholder_dashboard()
    assert isinstance(result, DashboardSnapshot)
    assert isinstance(result.trust_bar, TrustBarSnapshot)
    assert isinstance(result.active_jobs, tuple)
    assert isinstance(result.pending_approvals, tuple)
    assert isinstance(result.recent_sessions, tuple)


# ---------------------------------------------------------------------------
# Consistency checks
# ---------------------------------------------------------------------------


def test_skill_ids_are_unique() -> None:
    skills = placeholder_skills()
    ids = [s.id for s in skills]
    assert len(ids) == len(set(ids))


def test_approval_touches_are_tuples() -> None:
    for ap in placeholder_approvals():
        assert isinstance(ap.touches, tuple)
        assert ap.risk in ("low", "medium", "high")


def test_active_jobs_have_no_error() -> None:
    for job in placeholder_active_jobs():
        assert job.error == ""


def test_failed_jobs_have_status_blocked() -> None:
    for job in placeholder_failed_jobs():
        assert job.status == "blocked"
