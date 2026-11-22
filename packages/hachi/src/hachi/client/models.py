"""
Hachi Cockpit â€” display models.

Frozen dataclasses mirroring ``frontend/src/lib/data/types.ts``.
Every class exposes a ``from_api(d: dict[str, Any]) -> Self`` classmethod that
adapts raw gateway JSON to the model, replicating the TypeScript
domain-adapter logic (defaults / fallbacks / normalisation included).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Helpers (private)
# ---------------------------------------------------------------------------

_MODEL_COLORS = ["#C2703D", "#3D7AC2", "#5BA86A", "#A85B9E", "#C2A23D"]


def _pick_color(index: int) -> str:
    return _MODEL_COLORS[index % len(_MODEL_COLORS)]


def _humanize_last_used(iso_date: str | None) -> str:
    """Return a human-readable relative date string or 'never'."""
    if not iso_date:
        return "never"
    try:
        d = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now(tz=UTC)
        diff_days = (now - d).days
        if diff_days == 0:
            return "today"
        if diff_days == 1:
            return "yesterday"
        if diff_days < 7:
            return f"{diff_days}d ago"
        if diff_days < 30:
            return f"{diff_days // 7}w ago"
        if diff_days < 365:
            return f"{diff_days // 30}mo ago"
        return f"{diff_days // 365}y ago"
    except Exception:
        return "never"


def _is_stale(iso_date: str | None) -> bool:
    """True when last_used is None or more than 30 days ago."""
    if not iso_date:
        return True
    try:
        d = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now(tz=UTC)
        return (now - d).total_seconds() > 30 * 24 * 3600
    except Exception:
        return True


def _humanize_schedule(kind: str, cron: str | None, interval_seconds: float | None) -> str:
    if kind == "cron" and cron:
        parts = cron.split()
        if len(parts) >= 5:
            mn, hr, dom, month, dow = parts[:5]
            if dom == "*" and month == "*":
                if dow == "*":
                    day_str = "every day"
                elif dow in ("1-5", "1,2,3,4,5"):
                    day_str = "weekdays"
                else:
                    day_str = f"day {dow}"
                time_str = f" at {hr.zfill(2)}:{mn.zfill(2)}" if hr != "*" and mn != "*" else ""
                return f"{day_str}{time_str}"
        return cron
    if kind == "interval" and interval_seconds is not None:
        secs = int(interval_seconds)
        if secs < 60:
            return f"every {secs}s"
        if secs < 3600:
            return f"every {round(secs / 60)}m"
        if secs < 86400:
            return f"every {round(secs / 3600)}h"
        return f"every {round(secs / 86400)}d"
    return "scheduled"


def _humanize_next_run(next_run: str | None) -> str:
    if not next_run:
        return "â€”"
    try:
        d = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
        now = datetime.now(tz=UTC)
        diff_s = (d - now).total_seconds()
        if diff_s < 0:
            return "overdue"
        if diff_s < 60:
            return "< 1 min"
        if diff_s < 3600:
            return f"in {round(diff_s / 60)} min"
        if diff_s < 86400:
            return f"in {round(diff_s / 3600)}h"
        return d.strftime("%a %H:%M")
    except Exception:
        return next_run


def _format_ts(iso_ts: str | None) -> str:
    if not iso_ts:
        return "â€”"
    try:
        d = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return d.strftime("%H:%M:%S")
    except Exception:
        return iso_ts or "â€”"


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


def _derive_risk(operation: str, tool: str) -> Literal["low", "medium", "high"]:
    combined = f"{operation} {tool}".lower()
    _high = r"shell|network|delete|rm |exec|subprocess|send_email|post|write_file|trash"
    if re.search(_high, combined):
        return "high"
    if re.search(r"write|update|patch|modify|create|upload|send", combined):
        return "medium"
    return "low"


def _derive_icon_approval(operation: str, tool: str) -> str:
    combined = f"{operation} {tool}".lower()
    if re.search(r"mail|email|gmail", combined):
        return "mail"
    if re.search(r"shell|exec|terminal|command", combined):
        return "terminal"
    if re.search(r"file|read|write|patch", combined):
        return "file"
    if re.search(r"network|http|fetch|url|api", combined):
        return "globe"
    if re.search(r"delete|rm |trash|remove", combined):
        return "trash"
    if re.search(r"calendar", combined):
        return "calendar"
    if re.search(r"slack|message|chat", combined):
        return "message-square"
    if re.search(r"search", combined):
        return "search"
    return "shield"


@dataclass(frozen=True, slots=True)
class Approval:
    """Pending permission request (GET /approvals)."""

    id: str  # gateway request_id (str, not numeric like TS)
    icon: str
    request: str
    why: str
    action: str
    op: str
    policy: str
    touches: tuple[str, ...]
    risk: Literal["low", "medium", "high"]
    scope: str
    expires_at: int
    total_ms: int

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Approval:
        operation = d.get("operation") or "unknown"
        tool = d.get("tool") or ""
        target = d.get("target") or ""
        return cls(
            id=d.get("request_id") or "",
            icon=_derive_icon_approval(operation, tool),
            request=tool or operation,
            why=d.get("reason") or "Hachi needs this to continue",
            action=f"{tool or operation} â†’ {target}",
            op=operation,
            policy=d.get("policy_summary") or "asks first",
            touches=(target,) if target else (),
            risk=_derive_risk(operation, tool),
            scope=operation,
            expires_at=0,
            total_ms=0,
        )


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Permission audit log entry (GET /permissions/audit)."""

    ts: str
    op: str
    target: str
    policy: str
    decision: str  # "allowed" | "allowed once" | "declined" | "automatic" | passthrough

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> AuditEntry:
        raw_decision = d.get("decision") or "automatic"
        decision_map = {
            "approve": "allowed",
            "allowed": "allowed",
            "allow_once": "allowed once",
            "allowed once": "allowed once",
            "deny": "declined",
            "declined": "declined",
            "automatic": "automatic",
        }
        decision = decision_map.get(raw_decision, raw_decision)
        return cls(
            ts=_format_ts(None),  # no ts from gateway â€” use now
            op=d.get("operation") or d.get("tool") or "unknown",
            target=d.get("target") or "",
            policy=d.get("reason") or d.get("operation") or "",
            decision=decision,
        )


# ---------------------------------------------------------------------------
# Work / Jobs / Schedules
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TaskRow:
    """Active or finished job (GET /jobs/active â†’ Run, GET /jobs/failed â†’ FailedTask)."""

    id: str  # gateway job_id
    title: str
    status: Literal["working", "on-watch", "done", "blocked"]
    progress: float
    spent: float
    budget: float
    meta: str
    when: str
    error: str  # populated for failed tasks

    @classmethod
    def from_active(cls, d: dict[str, Any]) -> TaskRow:
        status_map = {
            "running": "working",
            "active": "working",
            "waiting": "on-watch",
            "blocked": "blocked",
            "done": "done",
        }
        status: Literal["working", "on-watch", "done", "blocked"] = status_map.get(  # type: ignore[assignment]
            d.get("status") or "", "on-watch"
        )
        return cls(
            id=d.get("job_id") or "",
            title=d.get("label") or d.get("kind") or d.get("job_id") or "",
            status=status,
            progress=0.5 if status == "working" else (1.0 if status == "done" else 0.0),
            spent=0.0,
            budget=1.0,
            meta=d.get("kind") or "",
            when="running",
            error="",
        )

    @classmethod
    def from_failed(cls, d: dict[str, Any]) -> TaskRow:
        ts = d.get("timestamp")
        when = _format_ts(ts) if ts else "unknown"
        return cls(
            id=d.get("job_id") or "",
            title=d.get("label") or d.get("kind") or d.get("job_id") or "",
            status="blocked",
            progress=0.0,
            spent=0.0,
            budget=1.0,
            meta=d.get("kind") or "",
            when=when,
            error=d.get("error") or "Unknown error",
        )


@dataclass(frozen=True, slots=True)
class Routine:
    """Scheduled task (GET /schedules)."""

    id: str  # gateway schedule_id
    title: str
    schedule: str  # human-readable schedule string
    next: str  # human-readable next-run string
    cost: float
    paused: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Routine:
        return cls(
            id=d.get("schedule_id") or "",
            title=d.get("name") or d.get("task") or d.get("schedule_id") or "",
            schedule=_humanize_schedule(
                d.get("kind") or "",
                d.get("cron"),
                d.get("interval_seconds"),
            ),
            next=_humanize_next_run(d.get("next_run")),
            cost=0.0,
            paused=not bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Fact:
    """Single memory fact."""

    id: str
    text: str
    source: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Fact:
        return cls(
            id=d.get("id") or "",
            text=d.get("text") or "",
            source=d.get("source") or "",
        )


@dataclass(frozen=True, slots=True)
class MemGroup:
    """Named group of memory facts (GET /memory â†’ groups)."""

    id: str
    title: str
    facts: tuple[Fact, ...]

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> MemGroup:
        return cls(
            id=d.get("id") or "",
            title=d.get("title") or "",
            facts=tuple(Fact.from_api(f) for f in (d.get("facts") or [])),
        )


@dataclass(frozen=True, slots=True)
class BlockedItem:
    """Blocked memory item."""

    id: str
    text: str
    reason: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> BlockedItem:
        return cls(
            id=d.get("id") or "",
            text=d.get("text") or "",
            reason=d.get("reason") or "",
        )


@dataclass(frozen=True, slots=True)
class ProposedChange:
    """Proposed memory change."""

    from_text: str  # renamed from 'from' (Python keyword)
    to_text: str

    @classmethod
    def from_api(cls, d: dict[str, Any] | None) -> ProposedChange | None:
        if not d:
            return None
        return cls(
            from_text=d.get("from") or "",
            to_text=d.get("to") or "",
        )


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    """Full memory response (GET /memory)."""

    groups: tuple[MemGroup, ...]
    blocked: tuple[BlockedItem, ...]
    proposed: ProposedChange | None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> MemorySnapshot:
        return cls(
            groups=tuple(MemGroup.from_api(g) for g in (d.get("groups") or [])),
            blocked=tuple(BlockedItem.from_api(b) for b in (d.get("blocked") or [])),
            proposed=ProposedChange.from_api(d.get("proposed")),
        )


@dataclass(frozen=True, slots=True)
class RecallHit:
    """Semantic recall hit (GET /memory/recall)."""

    fact: str
    score: str  # stringified float per TS contract
    src: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> RecallHit:
        raw_score = d.get("score")
        score = "" if raw_score is None else str(raw_score)
        return cls(
            fact=d.get("fact") or "",
            score=score,
            src=d.get("src") or "",
        )


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Skill:
    """Skill entry (GET /skills)."""

    id: str
    icon: str
    name: str
    desc: str
    uses: str
    last_used: str
    stale: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Skill:
        use_count = d.get("use_count") or 0
        return cls(
            id=d.get("name") or "unknown",
            icon="sparkles",
            name=d.get("name") or "unknown",
            desc=f"role: {d['role']}" if d.get("role") else "skill",
            uses=f"{use_count} times",
            last_used=_humanize_last_used(d.get("last_used")),
            stale=_is_stale(d.get("last_used")),
        )


# ---------------------------------------------------------------------------
# OG explorer
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OgNode:
    """ObjectGraph node (GET /og/graph)."""

    id: str
    name: str
    kind: Literal["root", "skill", "leaf"]
    index: int
    dense: int
    full: int
    deps: tuple[str, ...]

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> OgNode:
        valid_kinds = {"root", "skill", "leaf"}
        raw_kind = d.get("kind") or "skill"
        kind: Literal["root", "skill", "leaf"] = raw_kind if raw_kind in valid_kinds else "skill"  # type: ignore[assignment]
        return cls(
            id=d.get("id") or "",
            name=d.get("name") or "",
            kind=kind,
            index=d.get("index") or 0,
            dense=d.get("dense") or 0,
            full=d.get("full") or 0,
            deps=tuple(d.get("deps") or []),
        )


# ---------------------------------------------------------------------------
# Authoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthTarget:
    """Editable .og or config target (GET /authoring/targets)."""

    name: str
    path: str
    kind: Literal["brain", "skill", "config"]
    dirty: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> AuthTarget:
        kind_map = {"brain": "brain", "skill": "skill", "config": "config"}
        raw_kind = d.get("kind") or "skill"
        kind: Literal["brain", "skill", "config"] = kind_map.get(raw_kind, "skill")  # type: ignore[assignment]
        return cls(
            name=d.get("name") or "",
            path=d.get("path") or "",
            kind=kind,
            dirty=bool(d.get("dirty", False)),
        )


# DiffLine: ("" | "add" | "del", line_text)
DiffLine = tuple[Literal["", "add", "del"], str]


def source_to_diff_lines(source: str) -> list[DiffLine]:
    """Convert raw source text to neutral DiffLine list."""
    return [("", line) for line in source.split("\n")]


# ---------------------------------------------------------------------------
# Spend
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpendTurn:
    """Per-turn token/cost row."""

    n: int
    in_t: int  # TS: inT
    out: int
    cost: float

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> SpendTurn:
        return cls(
            n=d.get("n") or 0,
            in_t=d.get("inT") or 0,
            out=d.get("out") or 0,
            cost=d.get("cost") or 0.0,
        )


@dataclass(frozen=True, slots=True)
class SpendTidy:
    """Compaction event row."""

    ts: str
    before: int
    after: int

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> SpendTidy:
        return cls(
            ts=d.get("ts") or "",
            before=d.get("before") or 0,
            after=d.get("after") or 0,
        )


@dataclass(frozen=True, slots=True)
class SpendModel:
    """Per-model token/cost summary."""

    name: str
    tokens: int
    cost: float
    color: str

    @classmethod
    def from_api(cls, d: dict[str, Any], index: int = 0) -> SpendModel:
        raw_color = d.get("color") or ""
        return cls(
            name=d.get("name") or "unknown",
            tokens=d.get("tokens") or 0,
            cost=d.get("cost") or 0.0,
            color=raw_color.strip() if raw_color.strip() else _pick_color(index),
        )


@dataclass(frozen=True, slots=True)
class SpendSnapshot:
    """Full spend response (GET /spend)."""

    turns: tuple[SpendTurn, ...]
    tidies: tuple[SpendTidy, ...]
    models: tuple[SpendModel, ...]

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> SpendSnapshot:
        turns = tuple(SpendTurn.from_api(t) for t in (d.get("turns") or []))
        tidies = tuple(SpendTidy.from_api(t) for t in (d.get("tidies") or []))
        models = tuple(
            SpendModel.from_api(m, i) for i, m in enumerate(d.get("models") or [])
        )
        return cls(turns=turns, tidies=tidies, models=models)


# ---------------------------------------------------------------------------
# Integrations / Capabilities / MCP
# ---------------------------------------------------------------------------

_CAP_DESCRIPTIONS: dict[str, str] = {
    "google": "Read Gmail, Calendar, Drive",
    "gmail": "Read and send email",
    "google_calendar": "Read and create calendar events",
    "google_drive": "Read and write Drive files",
    "slack": "Send messages, read channels",
    "notion": "Read and write Notion pages",
    "github": "Read repos, open issues and PRs",
    "linear": "Create and update issues",
    "telegram": "Send Telegram messages",
    "discord": "Send Discord messages",
    "whatsapp": "Send WhatsApp messages",
}

_CAP_ICONS: dict[str, str] = {
    "google": "google",
    "gmail": "mail",
    "google_calendar": "calendar",
    "google_drive": "folder",
    "slack": "slack",
    "notion": "notion",
    "github": "github",
    "linear": "linear",
    "telegram": "telegram",
    "discord": "discord",
    "whatsapp": "whatsapp",
}

_RISKY_IDS = {"github", "google_drive", "google"}


def _pretty_name(cap_id: str) -> str:
    return cap_id.replace("_", " ").title()


@dataclass(frozen=True, slots=True)
class Capability:
    """Native integration / capability (GET /capabilities)."""

    id: str
    icon: str
    name: str
    can: str
    status: Literal["connected", "degraded", "none"]
    risky: bool
    enabled: bool
    configured: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Capability:
        cap_id = d.get("id") or "unknown"
        enabled = bool(d.get("enabled", False))
        configured = bool(d.get("configured", False))
        if configured and enabled:
            status: Literal["connected", "degraded", "none"] = "connected"
        elif configured and not enabled:
            status = "degraded"
        else:
            status = "none"
        return cls(
            id=cap_id,
            icon=_CAP_ICONS.get(cap_id.lower(), "plug"),
            name=_pretty_name(cap_id),
            can=_CAP_DESCRIPTIONS.get(cap_id.lower(), "Access external service"),
            status=status,
            risky=cap_id.lower() in _RISKY_IDS,
            enabled=enabled,
            configured=configured,
        )


@dataclass(frozen=True, slots=True)
class McpServer:
    """MCP server entry (GET /runtime/mcp/inventory â†’ servers)."""

    name: str
    status: Literal["connected", "starting", "blocked"]
    tools: int
    transport: str
    uptime: str
    err: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> McpServer:
        raw_status = (d.get("status") or "").lower()
        status_map: dict[str, Literal["connected", "starting", "blocked"]] = {
            "connected": "connected",
            "ready": "connected",
            "running": "connected",
            "starting": "starting",
            "blocked": "blocked",
            "failed": "blocked",
            "error": "blocked",
        }
        return cls(
            name=d.get("name") or "unknown",
            status=status_map.get(raw_status, "starting"),
            tools=d.get("tool_count") or 0,
            transport="â€”",
            uptime="â€”",
            err="",
        )


@dataclass(frozen=True, slots=True)
class McpTool:
    """Individual MCP tool."""

    name: str
    server: str

    @classmethod
    def from_api(cls, name: str, server: str) -> McpTool:
        return cls(name=name, server=server)


# ---------------------------------------------------------------------------
# Sessions / Chat
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """Session summary (GET /sessions)."""

    id: str
    title: str
    turns: int
    model: str
    date: str
    active: bool

    @classmethod
    def from_api(cls, d: dict[str, Any], idx: int = 0) -> SessionInfo:
        active = not d.get("ended_at")
        date = "unknown"
        if started := d.get("started_at"):
            try:
                dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                date = dt.strftime("%-d %b %Y")
            except Exception:
                date = started
        return cls(
            id=d.get("id") or str(idx),
            title=d.get("title") or "Unnamed session",
            turns=d.get("total_turns") or 0,
            model=d.get("model") or "unknown",
            date=date,
            active=active,
        )


# ---------------------------------------------------------------------------
# Config / Setup
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    """Effective gateway config (GET /config + GET /models)."""

    provider_kind: str
    model: str
    tier: str  # "sandbox" | "guided" | "unrestricted"
    safety: str  # "guarded" | "standard" | "open"
    enable_session_history: bool
    enable_semantic_memory: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> ConfigSnapshot:
        prov = d.get("provider") or {}
        perms = d.get("permissions") or {}
        mem = d.get("memory") or {}
        tier = perms.get("tier") or "guided"
        tier_to_safety = {"sandbox": "guarded", "unrestricted": "open"}
        safety = tier_to_safety.get(tier, "standard")
        return cls(
            provider_kind=prov.get("kind") or "anthropic",
            model=prov.get("model") or "claude-haiku-4-5",
            tier=tier,
            safety=safety,
            enable_session_history=bool(mem.get("enable_session_history", True)),
            enable_semantic_memory=bool(mem.get("enable_semantic_memory", True)),
        )


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Available model (GET /models)."""

    id: str
    label: str
    provider: str
    recommended: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> ModelInfo:
        return cls(
            id=d.get("id") or "",
            label=d.get("label") or d.get("id") or "",
            provider=d.get("provider") or "",
            recommended=bool(d.get("recommended", False)),
        )


@dataclass(frozen=True, slots=True)
class SetupState:
    """Onboarding state (GET /setup)."""

    setup_version: int
    selected_tier: str
    completed_steps: tuple[str, ...]
    needs_setup: bool
    anthropic_env: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> SetupState:
        state = d.get("state") or {}
        env = d.get("environment") or {}
        return cls(
            setup_version=state.get("setup_version") or 0,
            selected_tier=state.get("selected_tier") or "",
            completed_steps=tuple(state.get("completed_steps") or []),
            needs_setup=bool(d.get("needs_setup", False)),
            anthropic_env=bool(env.get("anthropic_env", False)),
        )


# ---------------------------------------------------------------------------
# Operator / Sub-agents / Runtime events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentRow:
    """Sub-agent report entry (GET /subagents/reports)."""

    role: str
    task: str
    status: Literal["working", "done", "pending"]
    outcome: str
    tokens: int

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> AgentRow:
        status_map: dict[str, Literal["working", "done", "pending"]] = {
            "running": "working",
            "active": "working",
            "working": "working",
            "completed": "done",
            "done": "done",
            "success": "done",
            "idle": "pending",
            "pending": "pending",
            "waiting": "pending",
        }
        return cls(
            role=d.get("role") or "agent",
            task=d.get("summary") or "â€”",
            status=status_map.get(d.get("status") or "", "pending"),
            outcome=d.get("summary") or d.get("status") or "â€”",
            tokens=0,
        )


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    """Runtime event adapted for the activity lens."""

    t: str
    type: str
    d: str
    lvl: Literal["ok", "info", "warn", "error", "muted"]

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> ActivityEvent:
        name = d.get("name") or ""
        payload = d.get("payload") or {}
        detail = (
            payload.get("text")
            or payload.get("summary")
            or payload.get("name")
            or payload.get("detail")
            or ""
        )
        if re.search(r"error|fail", name):
            lvl: Literal["ok", "info", "warn", "error", "muted"] = "error"
        elif re.search(r"warn", name):
            lvl = "warn"
        elif name.startswith("tool."):
            lvl = "info"
        else:
            lvl = "muted"
        return cls(
            t=_format_ts(d.get("timestamp")),
            type=name or "event",
            d=str(detail),
            lvl=lvl,
        )


@dataclass(frozen=True, slots=True)
class ToolCallRow:
    """Tool call derived from paired started/completed runtime events."""

    tool: str
    inp: str
    out: str
    dur: str
    ts: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """Health response (GET /health)."""

    status: str
    service: str
    protocol_version: str
    time: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> HealthStatus:
        return cls(
            status=d.get("status") or "unknown",
            service=d.get("service") or "",
            protocol_version=d.get("protocol_version") or "",
            time=d.get("time") or "",
        )


# ---------------------------------------------------------------------------
# Dashboard aggregates
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrustBarSnapshot:
    """Aggregate for the cockpit trust bar / dashboard header."""

    tier: str
    safety: str
    model: str
    approval_count: int
    active_job_count: int
    total_cost_usd: float
    reconnecting: bool

    @classmethod
    def from_parts(
        cls,
        config: ConfigSnapshot | None,
        approvals: list[Approval],
        jobs: list[TaskRow],
        spend: SpendSnapshot | None,
        reconnecting: bool = False,
    ) -> TrustBarSnapshot:
        return cls(
            tier=config.tier if config else "guided",
            safety=config.safety if config else "standard",
            model=config.model if config else "â€”",
            approval_count=len(approvals),
            active_job_count=len(jobs),
            total_cost_usd=sum(m.cost for m in spend.models) if spend else 0.0,
            reconnecting=reconnecting,
        )


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Aggregate for the cockpit home/dashboard view."""

    active_jobs: tuple[TaskRow, ...]
    pending_approvals: tuple[Approval, ...]
    recent_sessions: tuple[SessionInfo, ...]
    trust_bar: TrustBarSnapshot



