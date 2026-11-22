"""P2-08: Workflow Composer, DryRunGate, and condition triggers.

Tests:
- WorkflowSpec: dataclass instantiation, default values
- render_workflow_preview: contains trigger, steps, scopes, cost, dry-run label
- apply_dry_run: annotates outbound-send steps with stubs
- DryRunGate: blocks writes/deletes; allows reads; stub_outbound produces stub
- Schedule.condition_skill: field present, persists via to_dict/from_dict
- Scheduler.tick with condition_evaluator: skips when False, fires when True
- Backward compat: from_dict without condition_skill field defaults to None
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# WorkflowSpec + render_workflow_preview
# ---------------------------------------------------------------------------


def test_workflow_spec_defaults():
    from hachi.core.workflow_composer import WorkflowSpec

    spec = WorkflowSpec(name="my_workflow")
    assert spec.name == "my_workflow"
    assert spec.dry_run is False
    assert spec.steps == []
    assert spec.scopes == []
    assert spec.est_cost_usd == 0.0


def test_render_preview_contains_name():
    from hachi.core.workflow_composer import WorkflowSpec, render_workflow_preview

    spec = WorkflowSpec(name="morning_briefing", description="Send daily digest")
    card = render_workflow_preview(spec)
    assert "morning_briefing" in card
    assert "Send daily digest" in card


def test_render_preview_shows_trigger_cron():
    from hachi.core.workflow_composer import (
        WorkflowSpec,
        WorkflowTrigger,
        render_workflow_preview,
    )

    spec = WorkflowSpec(
        name="x",
        trigger=WorkflowTrigger(kind="cron", cron="0 9 * * 1-5"),
    )
    card = render_workflow_preview(spec)
    assert "0 9 * * 1-5" in card


def test_render_preview_shows_trigger_interval():
    from hachi.core.workflow_composer import (
        WorkflowSpec,
        WorkflowTrigger,
        render_workflow_preview,
    )

    spec = WorkflowSpec(name="x", trigger=WorkflowTrigger(kind="interval", interval_seconds=3600))
    card = render_workflow_preview(spec)
    assert "3600" in card


def test_render_preview_shows_trigger_condition():
    from hachi.core.workflow_composer import (
        WorkflowSpec,
        WorkflowTrigger,
        render_workflow_preview,
    )

    spec = WorkflowSpec(
        name="x",
        trigger=WorkflowTrigger(kind="condition", condition_skill="check_weather"),
    )
    card = render_workflow_preview(spec)
    assert "check_weather" in card


def test_render_preview_shows_steps():
    from hachi.core.workflow_composer import WorkflowSpec, WorkflowStep, render_workflow_preview

    spec = WorkflowSpec(
        name="x",
        steps=[WorkflowStep(description="Fetch emails"), WorkflowStep(description="Send summary")],
    )
    card = render_workflow_preview(spec)
    assert "Fetch emails" in card
    assert "Send summary" in card


def test_render_preview_shows_scopes():
    from hachi.core.workflow_composer import WorkflowSpec, render_workflow_preview

    spec = WorkflowSpec(name="x", scopes=["gmail.read", "slack.send"])
    card = render_workflow_preview(spec)
    assert "gmail.read" in card
    assert "slack.send" in card


def test_render_preview_shows_cost():
    from hachi.core.workflow_composer import WorkflowSpec, render_workflow_preview

    spec = WorkflowSpec(name="x", est_cost_usd=0.0042)
    card = render_workflow_preview(spec)
    assert "0.0042" in card


def test_render_preview_dry_run_label():
    from hachi.core.workflow_composer import WorkflowSpec, render_workflow_preview

    spec = WorkflowSpec(name="x", dry_run=True)
    card = render_workflow_preview(spec)
    assert "DRY-RUN" in card.upper()


def test_render_preview_shows_approve_reject():
    from hachi.core.workflow_composer import WorkflowSpec, render_workflow_preview

    card = render_workflow_preview(WorkflowSpec(name="x"))
    assert "Approve" in card
    assert "Reject" in card


def test_render_preview_shows_assertions():
    from hachi.core.workflow_composer import WorkflowSpec, render_workflow_preview

    spec = WorkflowSpec(name="x", assertions=["output contains 'done'"])
    card = render_workflow_preview(spec)
    assert "output contains" in card


# ---------------------------------------------------------------------------
# apply_dry_run + annotate_dry_run_step
# ---------------------------------------------------------------------------


def test_apply_dry_run_sets_flag():
    from hachi.core.workflow_composer import WorkflowSpec, apply_dry_run

    spec = WorkflowSpec(name="x")
    dry = apply_dry_run(spec)
    assert dry.dry_run is True


def test_apply_dry_run_annotates_send_tools():
    from hachi.core.workflow_composer import WorkflowSpec, WorkflowStep, apply_dry_run

    spec = WorkflowSpec(
        name="x",
        steps=[WorkflowStep(description="Send Slack", tool="send_slack_message")],
    )
    dry = apply_dry_run(spec)
    assert dry.steps[0].send_stub != ""
    assert "dry-run" in dry.steps[0].send_stub


def test_apply_dry_run_does_not_annotate_read_tools():
    from hachi.core.workflow_composer import WorkflowSpec, WorkflowStep, apply_dry_run

    spec = WorkflowSpec(
        name="x",
        steps=[WorkflowStep(description="Read file", tool="read_file")],
    )
    dry = apply_dry_run(spec)
    assert dry.steps[0].send_stub == ""


# ---------------------------------------------------------------------------
# DryRunGate
# ---------------------------------------------------------------------------


def _make_mock_gate():
    from hachi.core.permissions import PermissionResult

    mock = MagicMock()
    mock.summary = "Test gate"
    mock.check_path.return_value = PermissionResult(allowed=True, reason="ok")
    mock.check_command.return_value = PermissionResult(allowed=True, reason="ok")
    return mock


def test_dry_run_gate_blocks_write():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    result = gate.check_path("/home/user/file.txt", "write")
    assert result.allowed is False
    assert "dry-run" in result.reason.lower()


def test_dry_run_gate_blocks_delete():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    result = gate.check_path("/home/user/file.txt", "delete")
    assert result.allowed is False


def test_dry_run_gate_allows_read():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    result = gate.check_path("/home/user/file.txt", "read")
    assert result.allowed is True


def test_dry_run_gate_blocks_mutating_commands():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    result = gate.check_command("rm -rf /tmp/test")
    assert result.allowed is False
    assert "dry-run" in result.reason.lower()


def test_dry_run_gate_allows_ls():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    result = gate.check_command("ls /home")
    assert result.allowed is True


def test_dry_run_gate_is_dry_run():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    assert gate.is_dry_run() is True


def test_dry_run_gate_summary_includes_marker():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    assert "dry-run" in gate.summary.lower()


def test_dry_run_gate_stub_outbound():
    from hachi.core.permissions import DryRunGate

    gate = DryRunGate(_make_mock_gate())
    stub = gate.stub_outbound("send_email", {"to": "user@example.com"})
    assert "would call" in stub
    assert "send_email" in stub


# ---------------------------------------------------------------------------
# Schedule.condition_skill field
# ---------------------------------------------------------------------------


def test_schedule_has_condition_skill_field():
    from hachi.jobs.scheduler import Schedule, ScheduleKind

    s = Schedule(
        schedule_id="abc",
        name="test",
        task="do something",
        kind=ScheduleKind.INTERVAL,
        interval_seconds=60,
        condition_skill="check_weather",
    )
    assert s.condition_skill == "check_weather"


def test_schedule_condition_skill_defaults_none():
    from hachi.jobs.scheduler import Schedule, ScheduleKind

    s = Schedule(
        schedule_id="abc",
        name="test",
        task="do something",
        kind=ScheduleKind.INTERVAL,
        interval_seconds=60,
    )
    assert s.condition_skill is None


def test_schedule_from_dict_without_condition_skill():
    """Backward compat: old persisted records without condition_skill load cleanly."""
    from hachi.jobs.scheduler import Schedule

    data = {
        "schedule_id": "abc",
        "name": "test",
        "task": "run",
        "kind": "interval",
        "interval_seconds": 60,
        "run_at": None,
        "cron": None,
        "deliver_to": "chat",
        "webhook_url": None,
        "enabled": True,
        "created_at": "2026-06-13T00:00:00",
        "last_run": None,
        "next_run": None,
        "run_count": 0,
        "max_retries": 3,
    }
    s = Schedule.from_dict(data)
    assert s.condition_skill is None


def test_schedule_to_dict_includes_condition_skill():
    from hachi.jobs.scheduler import Schedule, ScheduleKind

    s = Schedule(
        schedule_id="abc",
        name="t",
        task="run",
        kind=ScheduleKind.INTERVAL,
        interval_seconds=60,
        condition_skill="my_condition",
    )
    d = s.to_dict()
    assert d["condition_skill"] == "my_condition"


# ---------------------------------------------------------------------------
# Scheduler.tick with condition_evaluator
# ---------------------------------------------------------------------------


def _make_interval_schedule(condition_skill: str | None = None) -> dict:
    return {
        "schedule_id": "sched-1",
        "name": "test",
        "task": "do it",
        "kind": "interval",
        "interval_seconds": 60,
        "run_at": None,
        "cron": None,
        "deliver_to": "chat",
        "webhook_url": None,
        "condition_skill": condition_skill,
        "enabled": True,
        "created_at": "2026-06-13T00:00:00+00:00",
        "last_run": None,
        "next_run": "2026-06-13T00:00:00+00:00",  # already due
        "run_count": 0,
        "max_retries": 3,
    }


def test_tick_without_condition_evaluator_fires_normally(tmp_path):
    from hachi.jobs.scheduler import Scheduler, ScheduleStore

    store_path = tmp_path / "sched.json"
    import json

    sched_data = _make_interval_schedule(condition_skill=None)
    store_path.write_text(json.dumps([sched_data]), encoding="utf-8")

    scheduler = Scheduler(ScheduleStore(store_path))
    fired = []
    now = datetime(2026, 6, 13, 1, 0, tzinfo=UTC)
    scheduler.tick(fired.append, now=now)
    assert len(fired) == 1


def test_tick_skips_when_condition_evaluator_returns_false(tmp_path):
    from hachi.jobs.scheduler import Scheduler, ScheduleStore

    store_path = tmp_path / "sched.json"
    import json

    sched_data = _make_interval_schedule(condition_skill="check_condition")
    store_path.write_text(json.dumps([sched_data]), encoding="utf-8")

    scheduler = Scheduler(ScheduleStore(store_path))
    fired = []
    now = datetime(2026, 6, 13, 1, 0, tzinfo=UTC)
    scheduler.tick(fired.append, now=now, condition_evaluator=lambda skill: False)
    assert len(fired) == 0


def test_tick_fires_when_condition_evaluator_returns_true(tmp_path):
    from hachi.jobs.scheduler import Scheduler, ScheduleStore

    store_path = tmp_path / "sched.json"
    import json

    sched_data = _make_interval_schedule(condition_skill="check_condition")
    store_path.write_text(json.dumps([sched_data]), encoding="utf-8")

    scheduler = Scheduler(ScheduleStore(store_path))
    fired = []
    now = datetime(2026, 6, 13, 1, 0, tzinfo=UTC)
    scheduler.tick(fired.append, now=now, condition_evaluator=lambda skill: True)
    assert len(fired) == 1


def test_tick_skips_when_condition_evaluator_raises(tmp_path):
    from hachi.jobs.scheduler import Scheduler, ScheduleStore

    store_path = tmp_path / "sched.json"
    import json

    sched_data = _make_interval_schedule(condition_skill="broken_condition")
    store_path.write_text(json.dumps([sched_data]), encoding="utf-8")

    scheduler = Scheduler(ScheduleStore(store_path))
    fired = []
    now = datetime(2026, 6, 13, 1, 0, tzinfo=UTC)

    def raising_evaluator(skill: str) -> bool:
        raise RuntimeError("evaluation failed")

    scheduler.tick(fired.append, now=now, condition_evaluator=raising_evaluator)
    assert len(fired) == 0


def test_tick_no_condition_skill_ignores_evaluator(tmp_path):
    """A schedule with no condition_skill fires even if an evaluator is supplied."""
    from hachi.jobs.scheduler import Scheduler, ScheduleStore

    store_path = tmp_path / "sched.json"
    import json

    sched_data = _make_interval_schedule(condition_skill=None)
    store_path.write_text(json.dumps([sched_data]), encoding="utf-8")

    scheduler = Scheduler(ScheduleStore(store_path))
    fired = []
    now = datetime(2026, 6, 13, 1, 0, tzinfo=UTC)
    scheduler.tick(fired.append, now=now, condition_evaluator=lambda skill: False)
    assert len(fired) == 1
