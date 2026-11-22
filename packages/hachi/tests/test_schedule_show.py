"""Tests for `hachi schedule show`.

Covers:
  1. Human-readable output — shows name, id, kind, task, next_run, run_count
  2. --json output — full dict round-trips through json.loads
  3. Not found → exit 1 with error message
  4. Cron schedule → shows cron field
  5. Interval schedule → shows interval_seconds field
  6. Disabled schedule → shows disabled state
  7. Webhook delivery → shows webhook_url
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_schedule(**kwargs) -> MagicMock:
    s = MagicMock()
    s.schedule_id = kwargs.get("schedule_id", "sched-abc123")
    s.name = kwargs.get("name", "weekly-report")
    s.task = kwargs.get("task", "Send me a weekly summary.")
    s.kind = MagicMock()
    s.kind.value = kwargs.get("kind", "cron")
    s.cron = kwargs.get("cron", "0 9 * * 1")
    s.interval_seconds = kwargs.get("interval_seconds", None)
    s.run_at = kwargs.get("run_at", None)
    s.deliver_to = kwargs.get("deliver_to", "chat")
    s.webhook_url = kwargs.get("webhook_url", None)
    s.enabled = kwargs.get("enabled", True)
    s.created_at = kwargs.get("created_at", "2026-06-01T09:00:00+00:00")
    s.next_run = kwargs.get("next_run", "2026-06-09T09:00:00+00:00")
    s.last_run = kwargs.get("last_run", None)
    s.run_count = kwargs.get("run_count", 0)
    s.to_dict.return_value = {
        "schedule_id": s.schedule_id,
        "name": s.name,
        "task": s.task,
        "kind": s.kind.value,
        "cron": s.cron,
        "interval_seconds": s.interval_seconds,
        "run_at": s.run_at,
        "deliver_to": s.deliver_to,
        "webhook_url": s.webhook_url,
        "enabled": s.enabled,
        "created_at": s.created_at,
        "next_run": s.next_run,
        "last_run": s.last_run,
        "run_count": s.run_count,
        "max_retries": 3,
    }
    return s


def _fake_scheduler(schedule=None) -> MagicMock:
    sched = MagicMock()
    sched.get.return_value = schedule
    return sched


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScheduleShow:
    def test_human_output_shows_key_fields(self) -> None:
        s = _fake_schedule()
        patcher = patch(
            "hachi.cli.commands.schedule._get_scheduler",
            return_value=_fake_scheduler(s),
        )
        with patcher:
            result = runner.invoke(app, ["schedule", "show", "sched-abc123"])
        assert result.exit_code == 0
        assert "weekly-report" in result.output
        assert "sched-abc123" in result.output
        assert "Send me a weekly summary." in result.output
        assert "2026-06-09" in result.output  # next_run
        assert "0" in result.output  # run_count

    def test_json_output_round_trips(self) -> None:
        s = _fake_schedule(run_count=5)
        patcher = patch(
            "hachi.cli.commands.schedule._get_scheduler",
            return_value=_fake_scheduler(s),
        )
        with patcher:
            result = runner.invoke(app, ["schedule", "show", "sched-abc123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["schedule_id"] == "sched-abc123"
        assert data["name"] == "weekly-report"
        assert data["run_count"] == 5

    def test_not_found_exits_1(self) -> None:
        patcher = patch(
            "hachi.cli.commands.schedule._get_scheduler",
            return_value=_fake_scheduler(None),
        )
        with patcher:
            result = runner.invoke(app, ["schedule", "show", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_cron_schedule_shows_cron_field(self) -> None:
        s = _fake_schedule(kind="cron", cron="*/5 * * * *")
        patcher = patch(
            "hachi.cli.commands.schedule._get_scheduler",
            return_value=_fake_scheduler(s),
        )
        with patcher:
            result = runner.invoke(app, ["schedule", "show", "sched-abc123"])
        assert result.exit_code == 0
        assert "*/5 * * * *" in result.output

    def test_interval_schedule_shows_interval_seconds(self) -> None:
        s = _fake_schedule(kind="interval", cron=None, interval_seconds=3600)
        patcher = patch(
            "hachi.cli.commands.schedule._get_scheduler",
            return_value=_fake_scheduler(s),
        )
        with patcher:
            result = runner.invoke(app, ["schedule", "show", "sched-abc123"])
        assert result.exit_code == 0
        assert "3600" in result.output

    def test_disabled_schedule_shown(self) -> None:
        s = _fake_schedule(enabled=False)
        patcher = patch(
            "hachi.cli.commands.schedule._get_scheduler",
            return_value=_fake_scheduler(s),
        )
        with patcher:
            result = runner.invoke(app, ["schedule", "show", "sched-abc123"])
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_webhook_delivery_shows_url(self) -> None:
        s = _fake_schedule(deliver_to="webhook", webhook_url="https://example.com/hook")
        patcher = patch(
            "hachi.cli.commands.schedule._get_scheduler",
            return_value=_fake_scheduler(s),
        )
        with patcher:
            result = runner.invoke(app, ["schedule", "show", "sched-abc123"])
        assert result.exit_code == 0
        assert "https://example.com/hook" in result.output
