"""
Unit tests for ``hachi.client.models`` — adapter (from_api) logic.

All tests are pure Python, no network calls.  Run with:
    PYTHONPATH=src python -m pytest tests/test_client_models.py -q
"""

from __future__ import annotations

import pytest

from hachi.client.models import (
    ActivityEvent,
    AgentRow,
    Approval,
    AuditEntry,
    AuthTarget,
    Capability,
    ConfigSnapshot,
    HealthStatus,
    McpServer,
    MemorySnapshot,
    OgNode,
    RecallHit,
    Routine,
    SessionInfo,
    SetupState,
    Skill,
    SpendSnapshot,
    TaskRow,
    source_to_diff_lines,
)

# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


class TestSkillFromApi:
    def test_full(self) -> None:
        raw = {
            "name": "file-ops",
            "role": "filesystem handler",
            "keyword_count": 5,
            "use_count": 7,
            "last_used": None,
        }
        s = Skill.from_api(raw)
        assert s.id == "file-ops"
        assert s.name == "file-ops"
        assert s.uses == "7 times"
        assert s.last_used == "never"
        assert s.stale is True
        assert s.icon == "sparkles"

    def test_missing_role(self) -> None:
        raw = {"name": "web-search", "use_count": 0, "last_used": None}
        s = Skill.from_api(raw)
        assert s.desc == "skill"

    def test_with_role(self) -> None:
        raw = {"name": "x", "role": "searcher", "use_count": 1, "last_used": None}
        s = Skill.from_api(raw)
        assert s.desc == "role: searcher"

    def test_empty_dict(self) -> None:
        s = Skill.from_api({})
        assert s.id == "unknown"
        assert s.stale is True


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class TestMemoryFromApi:
    def test_full(self) -> None:
        raw = {
            "groups": [
                {
                    "id": "g1",
                    "title": "Profile",
                    "facts": [{"id": "f1", "text": "Name: Alex", "source": "setup"}],
                }
            ],
            "blocked": [{"id": "b1", "text": "secret", "reason": "privacy"}],
            "proposed": {"from": "old", "to": "new"},
        }
        snap = MemorySnapshot.from_api(raw)
        assert len(snap.groups) == 1
        assert snap.groups[0].id == "g1"
        assert len(snap.groups[0].facts) == 1
        assert snap.groups[0].facts[0].text == "Name: Alex"
        assert snap.blocked[0].reason == "privacy"
        assert snap.proposed is not None
        assert snap.proposed.from_text == "old"
        assert snap.proposed.to_text == "new"

    def test_empty(self) -> None:
        snap = MemorySnapshot.from_api({})
        assert snap.groups == ()
        assert snap.blocked == ()
        assert snap.proposed is None

    def test_proposed_none(self) -> None:
        snap = MemorySnapshot.from_api({"proposed": None})
        assert snap.proposed is None


class TestRecallHitFromApi:
    def test_numeric_score(self) -> None:
        hit = RecallHit.from_api({"fact": "hello", "score": 0.92, "src": "vault"})
        assert hit.score == "0.92"
        assert hit.fact == "hello"

    def test_missing_score(self) -> None:
        hit = RecallHit.from_api({"fact": "x"})
        assert hit.score == ""

    def test_string_score(self) -> None:
        hit = RecallHit.from_api({"fact": "x", "score": "0.8"})
        assert hit.score == "0.8"


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class TestApprovalFromApi:
    def test_full(self) -> None:
        raw = {
            "request_id": "req-123",
            "operation": "write",
            "tool": "write_file",
            "target": "~/doc.md",
            "reason": "needs saving",
            "policy_summary": "asks first",
        }
        a = Approval.from_api(raw)
        assert a.id == "req-123"
        # "write_file" matches the write_file pattern → high risk
        assert a.risk == "high"
        assert a.touches == ("~/doc.md",)
        assert a.icon == "file"

    def test_high_risk(self) -> None:
        raw = {"request_id": "r", "operation": "exec", "tool": "shell"}
        a = Approval.from_api(raw)
        assert a.risk == "high"

    def test_empty(self) -> None:
        a = Approval.from_api({"request_id": "r"})
        assert a.op == "unknown"
        assert a.touches == ()

    def test_terminal_icon(self) -> None:
        raw = {"request_id": "r", "operation": "exec", "tool": "terminal"}
        a = Approval.from_api(raw)
        assert a.icon == "terminal"


class TestAuditEntryFromApi:
    def test_approve_normalisation(self) -> None:
        ae = AuditEntry.from_api({"decision": "approve"})
        assert ae.decision == "allowed"

    def test_allow_once_normalisation(self) -> None:
        ae = AuditEntry.from_api({"decision": "allow_once"})
        assert ae.decision == "allowed once"

    def test_deny_normalisation(self) -> None:
        ae = AuditEntry.from_api({"decision": "deny"})
        assert ae.decision == "declined"

    def test_passthrough(self) -> None:
        ae = AuditEntry.from_api({"decision": "custom_value"})
        assert ae.decision == "custom_value"

    def test_empty(self) -> None:
        ae = AuditEntry.from_api({})
        assert ae.decision == "automatic"
        assert ae.op == "unknown"


# ---------------------------------------------------------------------------
# OG Node
# ---------------------------------------------------------------------------


class TestOgNodeFromApi:
    def test_full(self) -> None:
        raw = {
            "id": "n1", "name": "brain-main", "kind": "root",
            "index": 30, "dense": 80, "full": 400, "deps": ["n2"],
        }
        node = OgNode.from_api(raw)
        assert node.kind == "root"
        assert node.deps == ("n2",)

    def test_invalid_kind_falls_back(self) -> None:
        node = OgNode.from_api({"id": "x", "name": "x", "kind": "unknown_kind"})
        assert node.kind == "skill"

    def test_empty(self) -> None:
        node = OgNode.from_api({})
        assert node.id == ""
        assert node.deps == ()


# ---------------------------------------------------------------------------
# AuthTarget
# ---------------------------------------------------------------------------


class TestAuthTargetFromApi:
    def test_brain(self) -> None:
        t = AuthTarget.from_api(
            {"name": "brain.og", "path": "skills/brain.og", "kind": "brain", "dirty": False}
        )
        assert t.kind == "brain"
        assert t.dirty is False

    def test_invalid_kind_falls_back(self) -> None:
        t = AuthTarget.from_api({"name": "x", "path": "", "kind": "weird", "dirty": True})
        assert t.kind == "skill"
        assert t.dirty is True


# ---------------------------------------------------------------------------
# Spend
# ---------------------------------------------------------------------------


class TestSpendFromApi:
    def test_full(self) -> None:
        raw = {
            "turns": [{"n": 1, "inT": 100, "out": 50, "cost": 0.001}],
            "tidies": [{"ts": "2026-01-01T00:00:00Z", "before": 1000, "after": 200}],
            "models": [{"name": "claude-haiku-4-5", "tokens": 150, "cost": 0.001, "color": "#abc"}],
        }
        snap = SpendSnapshot.from_api(raw)
        assert len(snap.turns) == 1
        assert snap.turns[0].in_t == 100
        assert snap.models[0].color == "#abc"

    def test_color_fallback(self) -> None:
        snap = SpendSnapshot.from_api(
            {"models": [{"name": "m", "tokens": 0, "cost": 0.0, "color": ""}]}
        )
        assert snap.models[0].color == "#C2703D"  # first palette color

    def test_empty(self) -> None:
        snap = SpendSnapshot.from_api({})
        assert snap.turns == ()
        assert snap.models == ()


# ---------------------------------------------------------------------------
# Capability / Integration
# ---------------------------------------------------------------------------


class TestCapabilityFromApi:
    def test_connected(self) -> None:
        c = Capability.from_api({"id": "github", "enabled": True, "configured": True})
        assert c.status == "connected"
        assert c.risky is True

    def test_degraded(self) -> None:
        c = Capability.from_api({"id": "slack", "enabled": False, "configured": True})
        assert c.status == "degraded"

    def test_none(self) -> None:
        c = Capability.from_api({"id": "notion", "enabled": False, "configured": False})
        assert c.status == "none"
        assert c.risky is False


# ---------------------------------------------------------------------------
# McpServer
# ---------------------------------------------------------------------------


class TestMcpServerFromApi:
    def test_ready_maps_to_connected(self) -> None:
        s = McpServer.from_api({"name": "fs", "status": "ready", "tool_count": 5})
        assert s.status == "connected"
        assert s.tools == 5

    def test_unknown_status_maps_to_starting(self) -> None:
        s = McpServer.from_api({"name": "x", "status": "unknown_xyz"})
        assert s.status == "starting"


# ---------------------------------------------------------------------------
# SessionInfo
# ---------------------------------------------------------------------------


class TestSessionInfoFromApi:
    def test_active(self) -> None:
        raw = {
            "id": "s1", "started_at": "2026-06-18T10:00:00Z",
            "ended_at": None, "total_turns": 5, "model": "claude-haiku-4-5",
        }
        si = SessionInfo.from_api(raw)
        assert si.active is True
        assert si.turns == 5

    def test_inactive(self) -> None:
        raw = {"id": "s2", "started_at": "2026-06-17T10:00:00Z", "ended_at": "2026-06-17T11:00:00Z"}
        si = SessionInfo.from_api(raw)
        assert si.active is False


# ---------------------------------------------------------------------------
# ConfigSnapshot
# ---------------------------------------------------------------------------


class TestConfigSnapshotFromApi:
    def test_sandbox_tier(self) -> None:
        raw = {
            "provider": {"kind": "anthropic", "model": "claude-haiku-4-5"},
            "permissions": {"tier": "sandbox"},
        }
        c = ConfigSnapshot.from_api(raw)
        assert c.safety == "guarded"
        assert c.tier == "sandbox"

    def test_unrestricted_tier(self) -> None:
        c = ConfigSnapshot.from_api({"permissions": {"tier": "unrestricted"}})
        assert c.safety == "open"

    def test_default_guided(self) -> None:
        c = ConfigSnapshot.from_api({})
        assert c.safety == "standard"
        assert c.tier == "guided"


# ---------------------------------------------------------------------------
# SetupState
# ---------------------------------------------------------------------------


class TestSetupStateFromApi:
    def test_full(self) -> None:
        raw = {
            "state": {
                "setup_version": 1, "selected_tier": "lightning",
                "completed_steps": ["welcome", "finish"],
            },
            "needs_setup": False,
            "environment": {"anthropic_env": True},
        }
        s = SetupState.from_api(raw)
        assert s.needs_setup is False
        assert s.anthropic_env is True
        assert "welcome" in s.completed_steps

    def test_empty(self) -> None:
        s = SetupState.from_api({})
        assert s.needs_setup is False
        assert s.completed_steps == ()


# ---------------------------------------------------------------------------
# AgentRow
# ---------------------------------------------------------------------------


class TestAgentRowFromApi:
    def test_running_maps_to_working(self) -> None:
        a = AgentRow.from_api({"role": "researcher", "status": "running", "summary": "searching"})
        assert a.status == "working"
        assert a.role == "researcher"

    def test_completed_maps_to_done(self) -> None:
        a = AgentRow.from_api({"role": "x", "status": "completed", "summary": "done"})
        assert a.status == "done"

    def test_unknown_maps_to_pending(self) -> None:
        a = AgentRow.from_api({"role": "x", "status": "whatever"})
        assert a.status == "pending"


# ---------------------------------------------------------------------------
# ActivityEvent
# ---------------------------------------------------------------------------


class TestActivityEventFromApi:
    def test_tool_event_is_info(self) -> None:
        ae = ActivityEvent.from_api(
            {"name": "tool.call.started", "payload": {"name": "read_file"}, "timestamp": None}
        )
        assert ae.lvl == "info"
        assert ae.type == "tool.call.started"

    def test_error_event(self) -> None:
        ae = ActivityEvent.from_api({"name": "session.error", "payload": {}, "timestamp": None})
        assert ae.lvl == "error"

    def test_payload_text_extraction(self) -> None:
        ae = ActivityEvent.from_api(
            {"name": "text.stream.delta", "payload": {"text": "hello"}, "timestamp": None}
        )
        assert ae.d == "hello"


# ---------------------------------------------------------------------------
# TaskRow
# ---------------------------------------------------------------------------


class TestTaskRowFromApi:
    def test_active_running(self) -> None:
        t = TaskRow.from_active(
            {"job_id": "j1", "kind": "memory_write", "label": "embed", "status": "running"}
        )
        assert t.status == "working"
        assert t.progress == pytest.approx(0.5)
        assert t.error == ""

    def test_failed(self) -> None:
        t = TaskRow.from_failed(
            {"job_id": "j2", "kind": "embed", "label": "fail", "error": "OOM", "timestamp": None}
        )
        assert t.status == "blocked"
        assert t.error == "OOM"


# ---------------------------------------------------------------------------
# Routine
# ---------------------------------------------------------------------------


class TestRoutineFromApi:
    def test_cron(self) -> None:
        raw = {
            "schedule_id": "s1",
            "name": "daily",
            "kind": "cron",
            "cron": "0 8 * * *",
            "enabled": True,
            "next_run": None,
        }
        r = Routine.from_api(raw)
        assert r.paused is False
        assert "08:00" in r.schedule

    def test_interval(self) -> None:
        r = Routine.from_api(
            {"schedule_id": "s2", "name": "fast", "kind": "interval",
             "interval_seconds": 3600, "enabled": False}
        )
        assert r.paused is True
        assert "every 1h" in r.schedule


# ---------------------------------------------------------------------------
# source_to_diff_lines
# ---------------------------------------------------------------------------


def test_source_to_diff_lines() -> None:
    lines = source_to_diff_lines("line1\nline2\nline3")
    assert len(lines) == 3
    assert all(tag == "" for tag, _ in lines)
    assert lines[1][1] == "line2"


# ---------------------------------------------------------------------------
# HealthStatus
# ---------------------------------------------------------------------------


def test_health_from_api() -> None:
    h = HealthStatus.from_api(
        {"status": "ok", "service": "hachi-gateway", "protocol_version": "1.0", "time": "now"}
    )
    assert h.status == "ok"


def test_health_empty() -> None:
    h = HealthStatus.from_api({})
    assert h.status == "unknown"
