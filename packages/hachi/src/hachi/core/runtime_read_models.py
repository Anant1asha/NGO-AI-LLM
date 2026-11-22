"""Immutable TUI-facing read models derived from runtime events."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from hachi.core.runtime_events import RuntimeEvent
from hachi.core.secret_scanner import redact_secrets


def _looks_like_error(text: str) -> bool:
    """Heuristic: does a tool-result preview describe a failure?"""
    lowered = text.lower()
    return any(token in lowered for token in ("failed", "error:", "traceback", "exception"))


def _duration_seconds(start: str, end: str) -> float:
    """Best-effort seconds between two ISO timestamps; 0.0 if unparseable."""
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        return max(0.0, delta.total_seconds())
    except (ValueError, TypeError):
        return 0.0


@dataclass(frozen=True, slots=True)
class SessionStateSnapshot:
    session_id: str
    active_skill: str | None
    last_user_query: str
    model_name: str
    boot_ready: bool
    pending_job_count: int
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class TaskLedgerItemSnapshot:
    skill_name: str
    user_query: str
    summary: str


@dataclass(frozen=True, slots=True)
class MemoryRecallSnapshot:
    fact_id: str
    content: str
    category: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class PermissionAuditSnapshot:
    operation: str
    tool: str
    target: str
    decision: str
    reason: str


@dataclass(frozen=True, slots=True)
class MCPServerSnapshot:
    name: str
    status: str
    tool_count: int
    tools: tuple[str, ...]
    transport: str = "stdio"
    # Failure reason when status is "failed"/"stopped" (e.g. bad command/url, server
    # crashed on start). Surfaced to the UI so "not reachable" shows WHY (Issue 4).
    err: str | None = None


@dataclass(frozen=True, slots=True)
class MCPInventorySnapshot:
    server_count: int
    total_tool_count: int
    servers: tuple[MCPServerSnapshot, ...]


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    job_id: str
    kind: str
    label: str
    status: str


@dataclass(frozen=True, slots=True)
class JobFailureSnapshot:
    job_id: str
    kind: str
    label: str
    attempt: int
    error: str
    duration_seconds: float
    timestamp: str


@dataclass(frozen=True, slots=True)
class SubAgentReportSnapshot:
    role: str
    status: str
    duration_seconds: float
    iterations: int
    summary: str


@dataclass(frozen=True, slots=True)
class ToolCallSnapshot:
    name: str
    status: str  # running | completed | failed
    detail: str  # result preview (or "")
    duration_seconds: float
    timestamp: str  # when the call started


@dataclass(frozen=True, slots=True)
class SkillSnapshot:
    name: str
    role: str
    keyword_count: int
    use_count: int
    last_used: str | None


@dataclass(frozen=True, slots=True)
class RuntimeEventSnapshot:
    name: str
    payload: dict[str, Any]
    timestamp: str
    sequence: int = 0


@dataclass(frozen=True, slots=True)
class RecentToolSnapshot:
    name: str
    status: str  # running | completed | failed


@dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    """Derived 'what is the agent doing right now' state for status surfaces."""

    label: str
    state: str  # idle | running | pending | failed
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    recent_tools: tuple[RecentToolSnapshot, ...] = ()


_IDLE_ACTIVITY = ActivitySnapshot(label="Idle", state="idle")


def advance_activity(
    prev: ActivitySnapshot, event_name: str, payload: dict[str, Any]
) -> ActivitySnapshot:
    """Fold one runtime event into the activity projection.

    Pure function — the single owner of event→activity derivation. Both the
    read model and the TUI status header call this so the two can never drift.
    Events that don't affect activity return ``prev`` unchanged.
    """
    if event_name == "session.chat.started":
        return replace(prev, label="Working…", state="running")
    if event_name == "thinking.step":
        step = payload.get("iteration", "?")
        return replace(prev, label=f"Thinking · step {step}", state="running")
    if event_name == "tool.call.started":
        name = str(payload.get("name", "tool"))
        started = (*prev.recent_tools, RecentToolSnapshot(name=name, status="running"))[-12:]
        return replace(prev, label=f"Running {name}…", state="running", recent_tools=started)
    if event_name == "tool.call.completed":
        name = str(payload.get("name", "tool"))
        # Defensive pass: events reaching advance_activity() come from adapt_event()
        # and are already redacted, but guard here too for any direct callers.
        preview, _ = redact_secrets(str(payload.get("result_preview", "")))
        status = "failed" if _looks_like_error(preview) else "completed"
        recent = _resolve_recent_tool(prev.recent_tools, name, status)
        return replace(prev, recent_tools=recent)
    if event_name == "permission.requested":
        return replace(prev, label="Waiting for approval", state="pending")
    if event_name == "permission.decided":
        return replace(prev, label="Working…", state="running")
    if event_name == "usage.updated":
        return replace(
            prev,
            total_tokens=int(payload.get("total_tokens") or 0),
            estimated_cost_usd=float(payload.get("estimated_cost_usd") or 0.0),
        )
    if event_name == "job.started":
        return replace(prev, label=f"Running job: {payload.get('label', 'job')}", state="running")
    if event_name in ("session.chat.completed", "job.completed", "job.failed"):
        # A finished background job — success OR failure — returns activity to idle.
        # A failed job is already surfaced via the warn counter and the jobs snapshot;
        # it must NOT flip the main activity status to "Failed", or a successful chat
        # turn would render the whole session as failed. Only a genuine boot failure
        # (the runtime itself is broken) marks the activity "Failed".
        return replace(prev, label="Idle", state="idle")
    if event_name == "boot.failed":
        return replace(prev, label="Failed", state="failed")
    return prev


def _resolve_recent_tool(
    recent: tuple[RecentToolSnapshot, ...], name: str, status: str
) -> tuple[RecentToolSnapshot, ...]:
    """Mark the most recent still-running tool of ``name`` with ``status`` (FIFO of one)."""
    out = list(recent)
    for i in range(len(out) - 1, -1, -1):
        if out[i].name == name and out[i].status == "running":
            out[i] = RecentToolSnapshot(name=name, status=status)
            break
    return tuple(out)


class RuntimeReadModelStore:
    """Maintains read-only state projections for TUI queries."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._boot_ready = False
        self._jobs: dict[str, JobSnapshot] = {}
        self._job_failures: list[JobFailureSnapshot] = []
        self._permission_audit: list[PermissionAuditSnapshot] = []
        self._subagent_reports: list[SubAgentReportSnapshot] = []
        self._events: list[RuntimeEventSnapshot] = []
        self._tool_calls: list[ToolCallSnapshot] = []
        # name -> FIFO of indices into _tool_calls still in the "running" state,
        # so a completed event resolves the matching earlier start.
        self._pending_tool_calls: dict[str, list[int]] = {}
        # Monotonic per-store event counter; the sole source of event sequence
        # numbers that paging clients poll against.
        self._sequence = 0
        self._activity = _IDLE_ACTIVITY

    def append_event(self, event: RuntimeEvent) -> None:
        with self._lock:
            self._sequence += 1
            self._events.append(
                RuntimeEventSnapshot(
                    event.name, dict(event.payload), event.timestamp, self._sequence
                )
            )
            # This log is the single source for sequence-based polling (the gateway
            # events endpoint), so keep a generous tail for slow-polling clients.
            if len(self._events) > 2000:
                self._events = self._events[-2000:]

            self._activity = advance_activity(self._activity, event.name, event.payload)

            if event.name == "boot.complete":
                self._boot_ready = True

            if event.name == "tool.call.started":
                name = str(event.payload.get("name", "tool"))
                self._tool_calls.append(
                    ToolCallSnapshot(
                        name=name,
                        status="running",
                        detail="",
                        duration_seconds=0.0,
                        timestamp=event.timestamp,
                    )
                )
                self._pending_tool_calls.setdefault(name, []).append(len(self._tool_calls) - 1)

            if event.name == "tool.call.completed":
                name = str(event.payload.get("name", "tool"))
                # ADV-022/UC-MOB-001: apply a defensive redaction pass here even though
                # adapt_event() already scrubs result_preview upstream.  This ensures the
                # ToolCallSnapshot.detail stored in the read model (and served to the web
                # companion) is clean regardless of how the event was produced.
                raw_preview, _ = redact_secrets(str(event.payload.get("result_preview", "")))
                pending = self._pending_tool_calls.get(name)
                if pending:
                    idx = pending.pop(0)
                    started = self._tool_calls[idx]
                    self._tool_calls[idx] = ToolCallSnapshot(
                        name=name,
                        status="failed" if _looks_like_error(raw_preview) else "completed",
                        detail=raw_preview,
                        duration_seconds=_duration_seconds(started.timestamp, event.timestamp),
                        timestamp=started.timestamp,
                    )
                else:
                    # Completed with no recorded start (e.g. truncated history).
                    self._tool_calls.append(
                        ToolCallSnapshot(
                            name=name,
                            status="failed" if _looks_like_error(raw_preview) else "completed",
                            detail=raw_preview,
                            duration_seconds=0.0,
                            timestamp=event.timestamp,
                        )
                    )

            if len(self._tool_calls) > 500:
                drop = len(self._tool_calls) - 500
                self._tool_calls = self._tool_calls[-500:]
                # Re-base the pending indices after trimming the front.
                self._pending_tool_calls = {
                    key: [i - drop for i in idxs if i - drop >= 0]
                    for key, idxs in self._pending_tool_calls.items()
                }

            if event.name == "job.started":
                job_id = str(event.payload.get("job_id", "job:unknown"))
                self._jobs[job_id] = JobSnapshot(
                    job_id=job_id,
                    kind=str(event.payload.get("kind", "generic")),
                    label=str(event.payload.get("label") or event.payload.get("job_name", "Job")),
                    status="running",
                )

            if event.name == "job.completed":
                job_id = str(event.payload.get("job_id", "job:unknown"))
                current = self._jobs.get(job_id)
                self._jobs[job_id] = JobSnapshot(
                    job_id=job_id,
                    kind=current.kind if current else str(event.payload.get("kind", "generic")),
                    label=current.label
                    if current and current.label != "Job"
                    else str(event.payload.get("label") or event.payload.get("job_name", "Job")),
                    status=str(event.payload.get("status", "completed")),
                )

            if event.name in ("job.failed", "job.dead_letter"):
                job_id = str(event.payload.get("job_id", "job:unknown"))
                current = self._jobs.get(job_id)
                kind = current.kind if current else str(event.payload.get("kind", "generic"))
                label = (
                    current.label
                    if current and current.label != "Job"
                    else str(event.payload.get("label") or event.payload.get("job_name", "Job"))
                )
                self._jobs[job_id] = JobSnapshot(
                    job_id=job_id,
                    kind=kind,
                    label=label,
                    status=str(event.payload.get("status", "failed")),
                )
                # ADV-022: scrub the raw error string before it lands in the web-facing
                # job-failure surface (gateway /sessions/{id}/events + memory browser).
                raw_error, _ = redact_secrets(str(event.payload.get("error", "")))
                self._job_failures.append(
                    JobFailureSnapshot(
                        job_id=job_id,
                        kind=kind,
                        label=label,
                        attempt=int(event.payload.get("attempt", 0)),
                        error=raw_error,
                        duration_seconds=float(event.payload.get("duration_seconds") or 0.0),
                        timestamp=event.timestamp,
                    )
                )

            if event.name == "permission.requested":
                self._permission_audit.append(
                    PermissionAuditSnapshot(
                        operation=str(event.payload.get("operation", "unknown")),
                        tool=str(event.payload.get("tool", "unknown")),
                        target=str(event.payload.get("target", "")),
                        decision="requested",
                        reason="Pending decision",
                    )
                )

            if event.name == "permission.decided":
                self._permission_audit.append(
                    PermissionAuditSnapshot(
                        operation=str(event.payload.get("operation", "unknown")),
                        tool=str(event.payload.get("tool", "unknown")),
                        target=str(event.payload.get("target", "")),
                        decision=str(event.payload.get("decision", "unknown")),
                        reason=str(event.payload.get("reason", "")),
                    )
                )

            if event.name == "subagent.completed":
                # ADV-022/UC-MOB-001: scrub the sub-agent summary before it lands in
                # the web companion's memory browser / subagent report surface.
                raw_summary, _ = redact_secrets(str(event.payload.get("summary") or ""))
                self._subagent_reports.append(
                    SubAgentReportSnapshot(
                        role=str(event.payload.get("role", "unknown")),
                        status=str(event.payload.get("status", "unknown")),
                        duration_seconds=float(event.payload.get("duration") or 0.0),
                        iterations=int(event.payload.get("iterations") or 0),
                        summary=raw_summary,
                    )
                )

            if len(self._permission_audit) > 500:
                self._permission_audit = self._permission_audit[-500:]
            if len(self._subagent_reports) > 300:
                self._subagent_reports = self._subagent_reports[-300:]

    def boot_ready(self) -> bool:
        with self._lock:
            return self._boot_ready

    def active_jobs(self) -> tuple[JobSnapshot, ...]:
        with self._lock:
            return tuple(job for job in self._jobs.values() if job.status == "running")

    def permission_audit(self, limit: int = 50) -> tuple[PermissionAuditSnapshot, ...]:
        with self._lock:
            return tuple(self._permission_audit[-limit:])

    def subagent_reports(self, limit: int = 20) -> tuple[SubAgentReportSnapshot, ...]:
        with self._lock:
            return tuple(self._subagent_reports[-limit:])

    def failed_jobs(self, limit: int = 20) -> tuple[JobFailureSnapshot, ...]:
        with self._lock:
            return tuple(self._job_failures[-limit:])

    def runtime_events(self, limit: int = 100) -> tuple[RuntimeEventSnapshot, ...]:
        with self._lock:
            return tuple(self._events[-limit:])

    def read_events_since(self, after: int, limit: int = 100) -> tuple[RuntimeEventSnapshot, ...]:
        """Events whose sequence is greater than ``after``, oldest→newest, capped at ``limit``.

        The single source for sequence-based polling (the gateway events endpoint).
        O(1) index into the bounded ring-tail: the event at index ``i`` has sequence
        ``base + i`` where ``base = self._events[0].sequence``.  Clamp ``start`` to
        zero for stale clients (``after < base``) to avoid the silent tail-slice wrap
        that a naive ``after - base + 1`` would produce after a trim (BB entry).
        """
        with self._lock:
            if not self._events:
                return ()
            base = self._events[0].sequence
            start = max(0, after - base + 1)
            return tuple(self._events[start : start + limit])

    def activity(self) -> ActivitySnapshot:
        """Current derived activity (label, state, usage, recent tools)."""
        with self._lock:
            return self._activity

    def tool_calls(self, limit: int = 50) -> tuple[ToolCallSnapshot, ...]:
        """Most-recent tool calls (oldest→newest), paired start→completion."""
        with self._lock:
            return tuple(self._tool_calls[-limit:])
