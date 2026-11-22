"""
Hachi Cockpit — placeholder / gap data.

Provides representative placeholder values for every model type so the cockpit
is always demonstrable even when the gateway is unreachable or an endpoint
errors.  Values mirror the mock data baked into the Hachi Cockpit design HTML
(the ``state`` / ``tableData`` / ``inspectorData`` objects).

Expose ``DATA_GAPS`` — a frozenset naming any domain still considered preview
(currently empty, all endpoints are wired).
"""

from __future__ import annotations

from .models import (
    ActivityEvent,
    AgentRow,
    Approval,
    AuditEntry,
    AuthTarget,
    Capability,
    ConfigSnapshot,
    DashboardSnapshot,
    Fact,
    HealthStatus,
    McpServer,
    McpTool,
    MemGroup,
    MemorySnapshot,
    ModelInfo,
    OgNode,
    RecallHit,
    Routine,
    SessionInfo,
    SetupState,
    Skill,
    SpendModel,
    SpendSnapshot,
    SpendTidy,
    SpendTurn,
    TaskRow,
    ToolCallRow,
    TrustBarSnapshot,
)

# Domains still considered preview (none at this time — all endpoints wired).
DATA_GAPS: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


def placeholder_skills() -> list[Skill]:
    """Return representative placeholder skill rows."""
    return [
        Skill(
            id="file-ops",
            icon="sparkles",
            name="file-ops",
            desc="role: filesystem operations",
            uses="14 times",
            last_used="2d ago",
            stale=False,
        ),
        Skill(
            id="web-search",
            icon="sparkles",
            name="web-search",
            desc="role: search the web",
            uses="7 times",
            last_used="today",
            stale=False,
        ),
        Skill(
            id="code-runner",
            icon="sparkles",
            name="code-runner",
            desc="role: execute code snippets",
            uses="0 times",
            last_used="never",
            stale=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


def placeholder_memory() -> MemorySnapshot:
    """Return a representative placeholder MemorySnapshot."""
    return MemorySnapshot(
        groups=(
            MemGroup(
                id="user_profile",
                title="User profile",
                facts=(
                    Fact(id="f1", text="Name: Alex", source="setup"),
                    Fact(id="f2", text="Prefers concise answers", source="conversation"),
                ),
            ),
            MemGroup(
                id="agent_profile",
                title="Agent profile",
                facts=(
                    Fact(id="f3", text="Hachi runs in lightning tier", source="config"),
                ),
            ),
        ),
        blocked=(
            # No blocked items by default
        ),
        proposed=None,
    )


def placeholder_recall() -> list[RecallHit]:
    """Return representative recall hits."""
    return [
        RecallHit(fact="User prefers concise answers", score="0.93", src="user_profile"),
        RecallHit(fact="Agent is in lightning tier", score="0.87", src="agent_profile"),
    ]


# ---------------------------------------------------------------------------
# OG
# ---------------------------------------------------------------------------


def placeholder_og_nodes() -> list[OgNode]:
    """Return representative OG graph nodes."""
    return [
        OgNode(id="root", name="brain-main", kind="root", index=30, dense=80, full=400, deps=()),
        OgNode(
            id="skill-file-ops",
            name="file-ops",
            kind="skill",
            index=10,
            dense=40,
            full=200,
            deps=("root",),
        ),
        OgNode(
            id="skill-web",
            name="web-search",
            kind="skill",
            index=8,
            dense=35,
            full=180,
            deps=("root",),
        ),
    ]


# ---------------------------------------------------------------------------
# Authoring
# ---------------------------------------------------------------------------


def placeholder_auth_targets() -> list[AuthTarget]:
    """Return representative authoring targets."""
    return [
        AuthTarget(name="brain-main.og", path="skills/brain-main.og", kind="brain", dirty=False),
        AuthTarget(name="file-ops.og", path="skills/file-ops.og", kind="skill", dirty=True),
        AuthTarget(
            name="device-permissions.og",
            path="skills/device-permissions.og",
            kind="config",
            dirty=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Spend
# ---------------------------------------------------------------------------


def placeholder_spend() -> SpendSnapshot:
    """Return representative spend data."""
    return SpendSnapshot(
        turns=(
            SpendTurn(n=1, in_t=1200, out=340, cost=0.0014),
            SpendTurn(n=2, in_t=1540, out=420, cost=0.0018),
            SpendTurn(n=3, in_t=1620, out=390, cost=0.0017),
        ),
        tidies=(SpendTidy(ts="2026-06-18T10:00:00Z", before=8200, after=1200),),
        models=(
            SpendModel(name="claude-haiku-4-5", tokens=5120, cost=0.0049, color="#C2703D"),
        ),
    )


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


def placeholder_approvals() -> list[Approval]:
    """Return representative pending approval rows."""
    return [
        Approval(
            id="req-001",
            icon="file",
            request="write_file",
            why="Need to save analysis results",
            action="write_file → ~/Documents/report.md",
            op="write",
            policy="asks first",
            touches=("~/Documents/report.md",),
            risk="medium",
            scope="write",
            expires_at=0,
            total_ms=0,
        ),
    ]


def placeholder_audit_log() -> list[AuditEntry]:
    """Return representative audit log entries."""
    return [
        AuditEntry(
            ts="10:14:02",
            op="read_file",
            target="~/notes.md",
            policy="filesystem.read",
            decision="automatic",
        ),
        AuditEntry(
            ts="10:13:55",
            op="web_search",
            target="https://example.com",
            policy="network.fetch",
            decision="allowed once",
        ),
    ]


# ---------------------------------------------------------------------------
# Work / Jobs / Schedules
# ---------------------------------------------------------------------------


def placeholder_active_jobs() -> list[TaskRow]:
    """Return representative active job rows."""
    return [
        TaskRow(
            id="job-001",
            title="Summarise project notes",
            status="working",
            progress=0.5,
            spent=0.0,
            budget=1.0,
            meta="memory_write",
            when="running",
            error="",
        ),
    ]


def placeholder_failed_jobs() -> list[TaskRow]:
    """Return representative failed job rows."""
    return [
        TaskRow(
            id="job-002",
            title="ChromaDB embed",
            status="blocked",
            progress=0.0,
            spent=0.0,
            budget=1.0,
            meta="memory_write",
            when="09:42:10",
            error="ChromaDB unavailable",
        ),
    ]


def placeholder_routines() -> list[Routine]:
    """Return representative schedule/routine rows."""
    return [
        Routine(
            id="sched-001",
            title="Daily digest",
            schedule="every day at 08:00",
            next="in 14h",
            cost=0.0,
            paused=False,
        ),
        Routine(
            id="sched-002",
            title="Weekly review",
            schedule="weekdays at 17:00",
            next="in 2 min",
            cost=0.0,
            paused=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Operator / Agents
# ---------------------------------------------------------------------------


def placeholder_agents() -> list[AgentRow]:
    """Return representative sub-agent rows."""
    return [
        AgentRow(
            role="researcher",
            task="Find recent Python async patterns",
            status="done",
            outcome="Found 3 relevant patterns",
            tokens=0,
        ),
        AgentRow(
            role="writer",
            task="Draft summary paragraph",
            status="working",
            outcome="—",
            tokens=0,
        ),
    ]


def placeholder_activity() -> list[ActivityEvent]:
    """Return representative activity events."""
    return [
        ActivityEvent(t="10:14:03", type="tool.call.started", d="read_file", lvl="info"),
        ActivityEvent(t="10:14:04", type="tool.call.completed", d="read_file", lvl="info"),
        ActivityEvent(t="10:14:05", type="session.chat.completed", d="", lvl="muted"),
    ]


def placeholder_tool_calls() -> list[ToolCallRow]:
    """Return representative tool call rows."""
    return [
        ToolCallRow(
            tool="read_file",
            inp='{"path": "~/notes.md"}',
            out="# Notes\n...",
            dur="42ms",
            ts="10:14:03",
        ),
    ]


# ---------------------------------------------------------------------------
# Capabilities / Integrations / MCP
# ---------------------------------------------------------------------------


def placeholder_capabilities() -> list[Capability]:
    """Return representative capability rows."""
    return [
        Capability(
            id="github",
            icon="github",
            name="Github",
            can="Read repos, open issues and PRs",
            status="none",
            risky=True,
            enabled=False,
            configured=False,
        ),
        Capability(
            id="slack",
            icon="slack",
            name="Slack",
            can="Send messages, read channels",
            status="none",
            risky=False,
            enabled=False,
            configured=False,
        ),
    ]


def placeholder_mcp_servers() -> list[McpServer]:
    """Return representative MCP server rows."""
    return [
        McpServer(
            name="filesystem",
            status="connected",
            tools=5,
            transport="—",
            uptime="—",
            err="",
        ),
    ]


def placeholder_mcp_tools() -> list[McpTool]:
    """Return representative MCP tool rows."""
    return [
        McpTool(name="read_file", server="filesystem"),
        McpTool(name="write_file", server="filesystem"),
    ]


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def placeholder_sessions() -> list[SessionInfo]:
    """Return representative session rows."""
    return [
        SessionInfo(
            id="sess-001",
            title="Project planning",
            turns=12,
            model="claude-haiku-4-5",
            date="17 Jun 2026",
            active=False,
        ),
        SessionInfo(
            id="sess-002",
            title="Unnamed session",
            turns=3,
            model="claude-haiku-4-5",
            date="18 Jun 2026",
            active=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def placeholder_config() -> ConfigSnapshot:
    """Return a representative config snapshot."""
    return ConfigSnapshot(
        provider_kind="anthropic",
        model="claude-haiku-4-5",
        tier="guided",
        safety="standard",
        enable_session_history=True,
        enable_semantic_memory=True,
    )


def placeholder_models() -> list[ModelInfo]:
    """Return representative model list."""
    return [
        ModelInfo(
            id="claude-haiku-4-5",
            label="Claude Haiku 4.5",
            provider="anthropic",
            recommended=True,
        ),
        ModelInfo(
            id="claude-sonnet-4-5",
            label="Claude Sonnet 4.5",
            provider="anthropic",
            recommended=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def placeholder_setup() -> SetupState:
    """Return a representative setup state."""
    return SetupState(
        setup_version=1,
        selected_tier="lightning",
        completed_steps=("welcome", "provider", "safety", "finish"),
        needs_setup=False,
        anthropic_env=True,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def placeholder_health() -> HealthStatus:
    """Return a representative health status (offline fallback)."""
    return HealthStatus(
        status="offline",
        service="hachi-gateway",
        protocol_version="1.0",
        time="",
    )


# ---------------------------------------------------------------------------
# Dashboard aggregates
# ---------------------------------------------------------------------------


def placeholder_trust_bar() -> TrustBarSnapshot:
    """Return a representative trust-bar snapshot."""
    return TrustBarSnapshot(
        tier="guided",
        safety="standard",
        model="claude-haiku-4-5",
        approval_count=1,
        active_job_count=1,
        total_cost_usd=0.0049,
        reconnecting=False,
    )


def placeholder_dashboard() -> DashboardSnapshot:
    """Return a representative dashboard snapshot (all placeholder data)."""
    return DashboardSnapshot(
        active_jobs=tuple(placeholder_active_jobs()),
        pending_approvals=tuple(placeholder_approvals()),
        recent_sessions=tuple(placeholder_sessions()),
        trust_bar=placeholder_trust_bar(),
    )
