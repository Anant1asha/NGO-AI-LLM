"""Tests for the `hachi skill assert` CLI command — checks a skill's
::assertion preconditions against --param values (engine + assertion_eval)."""

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"

# A skill with real `assert <lhs> <op> <rhs> "msg"` preconditions (the fixture
# sample_skill.og uses the non-checkable `key: prose` form → "manual").
_ASSERT_OG = """\
::meta
  title: Notify Skill
  version: 1.0.0

::index
  notify | skill | all | 0.9 | notify, slack

::node[notify]
->[:role=skill]
->[:keywords=notify, slack]
::dense
notify|slack
::assertion
assert channel_name != "" "A target channel must be provided."
assert message != "" "A message body is required."
"""


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    shutil.copy(FIXTURE, skills_dir / "sample_skill.og")
    (skills_dir / "notify.og").write_text(_ASSERT_OG, encoding="utf-8")
    monkeypatch.setattr("hachi.gateway.workspace.get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)  # isolate usage store
    return skills_dir


def test_assert_passes_with_valid_params(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        ["skill", "assert", "notify", "-p", "channel_name=#general", "-p", "message=hi", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert {r["status"] for r in payload["results"]} == {"pass"}


def test_assert_fails_on_empty_value(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        ["skill", "assert", "notify", "-p", "channel_name=", "-p", "message=hi", "--json"],
    )
    assert result.exit_code == 1  # a failing assertion → non-zero (CI gate)
    payload = json.loads(result.output)
    assert payload["ok"] is False
    statuses = {r["assertion"]: r["status"] for r in payload["results"]}
    assert statuses['assert channel_name != "" "A target channel must be provided."'] == "fail"


def test_assert_unknown_when_value_missing(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "assert", "notify", "--json"])
    assert result.exit_code == 1  # unknown (no value supplied) also blocks
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert any(r["status"] == "unknown" for r in payload["results"])


def test_assert_human_readable(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(
        app, ["skill", "assert", "notify", "-p", "channel_name=#x", "-p", "message=y"]
    )
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output
    assert "OK" in result.output


def test_assert_invalid_param_format(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "assert", "notify", "-p", "noequalssign"])
    assert result.exit_code == 2
    assert "Invalid --param" in result.output


def test_assert_not_found_exits_nonzero(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = runner.invoke(app, ["skill", "assert", "ghost_skill"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
