"""Tests for `hachi schedule run-now`.

Covers:
  1. Known schedule ID → runs chat, marks fired, prints Done + result preview
  2. Unknown schedule ID → exits 1 with "not found" message
  3. Agent chat() raises → exits 1 with error message
  4. Result longer than 200 chars → truncated with ellipsis
  5. Result exactly 200 chars → no ellipsis
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

_FAKE_NOW = datetime.datetime(2026, 6, 7, 12, 0, 0, tzinfo=datetime.UTC)


def _fake_schedule(task: str = "Summarize the news.") -> MagicMock:
    s = MagicMock()
    s.schedule_id = "sched001"
    s.name = "daily-summary"
    s.task = task
    s.deliver_to = None
    s.webhook_url = None
    return s


def _fake_scheduler(schedule=None) -> MagicMock:
    sched = MagicMock()
    sched.get.return_value = schedule  # None → not found
    sched.mark_fired.return_value = None
    return sched


def _fake_agent(reply: str = "Here is the summary.") -> MagicMock:
    agent = MagicMock()
    agent.chat.return_value = reply
    agent.shutdown.return_value = None
    return agent


# ---------------------------------------------------------------------------
# 1. Known schedule → success
# ---------------------------------------------------------------------------


def test_run_now_known_schedule_success() -> None:
    schedule = _fake_schedule()
    scheduler = _fake_scheduler(schedule=schedule)
    agent = _fake_agent(reply="Here is your daily summary.")

    with (
        patch("hachi.cli.commands.schedule._get_scheduler", return_value=scheduler),
        patch("hachi.cli.commands.schedule.boot_agent", return_value=agent),
    ):
        result = runner.invoke(app, ["schedule", "run-now", "sched001"])

    assert result.exit_code == 0
    assert "Done" in result.output
    assert "Here is your daily summary." in result.output
    agent.chat.assert_called_once_with(schedule.task)
    scheduler.mark_fired.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Unknown schedule ID → exit 1
# ---------------------------------------------------------------------------


def test_run_now_unknown_schedule_exits() -> None:
    scheduler = _fake_scheduler(schedule=None)

    with patch("hachi.cli.commands.schedule._get_scheduler", return_value=scheduler):
        result = runner.invoke(app, ["schedule", "run-now", "does-not-exist"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# 3. Agent chat() raises → exit 1
# ---------------------------------------------------------------------------


def test_run_now_agent_error_exits() -> None:
    schedule = _fake_schedule()
    scheduler = _fake_scheduler(schedule=schedule)
    agent = MagicMock()
    agent.chat.side_effect = RuntimeError("LLM timed out")
    agent.shutdown.return_value = None

    with (
        patch("hachi.cli.commands.schedule._get_scheduler", return_value=scheduler),
        patch("hachi.cli.commands.schedule.boot_agent", return_value=agent),
    ):
        result = runner.invoke(app, ["schedule", "run-now", "sched001"])

    assert result.exit_code == 1
    assert "error" in result.output.lower() or "Error" in result.output
    # mark_fired must NOT have been called on error
    scheduler.mark_fired.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Long result (>200 chars) shows ellipsis in the Result: preview line
# ---------------------------------------------------------------------------


def test_run_now_result_truncated() -> None:
    long_reply = "A" * 250
    schedule = _fake_schedule()
    scheduler = _fake_scheduler(schedule=schedule)
    agent = _fake_agent(reply=long_reply)

    with (
        patch("hachi.cli.commands.schedule._get_scheduler", return_value=scheduler),
        patch("hachi.cli.commands.schedule.boot_agent", return_value=agent),
    ):
        result = runner.invoke(app, ["schedule", "run-now", "sched001"])

    assert result.exit_code == 0
    # The "Result:" preview line must have the ellipsis suffix
    assert "…" in result.output
    # "Result:" label must appear before the preview
    assert "Result:" in result.output


# ---------------------------------------------------------------------------
# 5. Result exactly 200 chars → the "Result:" preview line has no ellipsis
# ---------------------------------------------------------------------------


def test_run_now_result_at_limit_no_ellipsis() -> None:
    exact_reply = "Z" * 200  # No A/B chars to avoid collision with other tests
    schedule = _fake_schedule()
    scheduler = _fake_scheduler(schedule=schedule)
    agent = _fake_agent(reply=exact_reply)

    with (
        patch("hachi.cli.commands.schedule._get_scheduler", return_value=scheduler),
        patch("hachi.cli.commands.schedule.boot_agent", return_value=agent),
    ):
        result = runner.invoke(app, ["schedule", "run-now", "sched001"])

    assert result.exit_code == 0
    # The Result: preview line must NOT have the ellipsis when reply fits in 200 chars
    # Extract just the "Result:" line for the check
    result_lines = [ln for ln in result.output.splitlines() if ln.startswith("Result:")]
    assert result_lines, "Expected 'Result:' line in output"
    result_line = result_lines[0]
    assert "…" not in result_line
