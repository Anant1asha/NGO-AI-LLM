"""Tests for `hachi schedule pause` and `hachi schedule resume`.

Covers:
  1.  pause — known ID → set_enabled(False), prints "Paused"
  2.  pause --json — returns {paused: true, id: ...}
  3.  pause not found → exits 1
  4.  pause not found --json → {paused: false} (no exit 1 from JSON path)
  5.  resume — known ID → set_enabled(True), prints "Resumed"
  6.  resume --json — returns {resumed: true, id: ...}
  7.  resume not found → exits 1
  8.  resume not found --json → {resumed: false}
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


def _fake_scheduler(set_enabled_return: bool = True) -> MagicMock:
    sched = MagicMock()
    sched.set_enabled.return_value = set_enabled_return
    return sched


class TestSchedulePause:
    def test_pause_known_id_prints_paused(self) -> None:
        sched = _fake_scheduler(True)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "pause", "sched-abc"])
        assert result.exit_code == 0
        assert "Paused" in result.output
        sched.set_enabled.assert_called_once_with("sched-abc", False)

    def test_pause_json_output(self) -> None:
        sched = _fake_scheduler(True)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "pause", "sched-abc", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"paused": True, "id": "sched-abc"}

    def test_pause_not_found_exits_1(self) -> None:
        sched = _fake_scheduler(False)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "pause", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_pause_not_found_json_no_exit(self) -> None:
        sched = _fake_scheduler(False)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "pause", "missing", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["paused"] is False


class TestScheduleResume:
    def test_resume_known_id_prints_resumed(self) -> None:
        sched = _fake_scheduler(True)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "resume", "sched-abc"])
        assert result.exit_code == 0
        assert "Resumed" in result.output
        sched.set_enabled.assert_called_once_with("sched-abc", True)

    def test_resume_json_output(self) -> None:
        sched = _fake_scheduler(True)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "resume", "sched-abc", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"resumed": True, "id": "sched-abc"}

    def test_resume_not_found_exits_1(self) -> None:
        sched = _fake_scheduler(False)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "resume", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_resume_not_found_json_no_exit(self) -> None:
        sched = _fake_scheduler(False)
        with patch("hachi.cli.commands.schedule._get_scheduler", return_value=sched):
            result = runner.invoke(app, ["schedule", "resume", "missing", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["resumed"] is False
