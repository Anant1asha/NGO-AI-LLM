"""RunState domain models for durable execution (Initiative D).

These are the pure data contracts; persistence lives in ``store.py``.
``resume_cursor`` is a TURN index (the number of turns completed before suspend),
not a mid-loop pointer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    """Lifecycle status of a durable run."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WaitKind(StrEnum):
    """The kind of condition a WAITING run is blocked on."""

    USER = "user"  # Human approval (generalises PendingApprovalRegistry)
    EVENT = "event"  # An EventBus event matching a pattern
    TIME = "time"  # A wall-clock timestamp (ISO-8601)
    WEBHOOK = "webhook"  # An inbound webhook POST (seam — not yet built)
    TOOL = "tool"  # Async tool completion (seam — not yet built)


class WaitCondition(BaseModel):
    """Describes what a WAITING run is blocked on."""

    kind: WaitKind
    key: str  # event pattern / approval id / ISO-8601 / webhook token
    created_at: str
    timeout_at: str | None = None


class RunState(BaseModel):
    """Persisted state of a single durable run."""

    run_id: str
    session_id: str
    status: RunStatus
    wait: WaitCondition | None = None
    resume_cursor: int = Field(default=0, description="Turn index at which to resume")
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: str


class RunStateView(BaseModel):
    """Public API projection of RunState (used as FastAPI response_model)."""

    run_id: str
    session_id: str
    status: str
    wait_kind: str | None = None
    wait_key: str | None = None
    wait_timeout_at: str | None = None
    resume_cursor: int = 0
    updated_at: str

    @classmethod
    def from_run_state(cls, rs: RunState) -> RunStateView:
        """Project a RunState to a public view."""
        return cls(
            run_id=rs.run_id,
            session_id=rs.session_id,
            status=rs.status.value,
            wait_kind=rs.wait.kind.value if rs.wait else None,
            wait_key=rs.wait.key if rs.wait else None,
            wait_timeout_at=rs.wait.timeout_at if rs.wait else None,
            resume_cursor=rs.resume_cursor,
            updated_at=rs.updated_at,
        )


class WakeRequest(BaseModel):
    """Body for POST /runs/{id}/wake."""

    result: dict[str, Any] = Field(default_factory=dict)
    source: str = "webhook"
