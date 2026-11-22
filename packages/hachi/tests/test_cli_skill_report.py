"""Tests for the `hachi skill report` CLI command.

The report surfaces the .og self-optimization data (usage tracking + staleness)
that the engine already collects. These tests isolate both the skills directory
and the on-disk usage store so they are deterministic and side-effect free.
"""

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    """Point the CLI at a temp skills dir and isolate the usage store under tmp home."""
    import hachi.og_engine.engine as engine_mod
    from hachi.core.paths import HachiPaths

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    shutil.copy(FIXTURE, skills_dir / "sample_skill.og")

    monkeypatch.setattr(
        "hachi.gateway.workspace.get_skills_dir",
        lambda: skills_dir,
    )
    # Redirect Path.home() so any home-dir lookups stay inside tmp_path.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Also redirect get_hachi_paths so state_dir is under tmp_path (not a system dir).
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    mock_paths = HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=state_dir,
    )
    monkeypatch.setattr(engine_mod, "get_hachi_paths", lambda: mock_paths)
    return skills_dir


def test_skill_report_human_readable(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = runner.invoke(app, ["skill", "report"])

    assert result.exit_code == 0, result.output
    assert "Skill Usage Report" in result.output
    # No usage recorded yet -> all fixture nodes are "never used".
    assert "Never used" in result.output
    assert "deploy_to_prod" in result.output


def test_skill_report_json_shape(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    result = runner.invoke(app, ["skill", "report", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) == {"report", "stale", "never_used"}
    report = payload["report"]
    assert report["total_skills"] >= 3
    assert report["tracked_skills"] == 0
    assert report["never_used_count"] == report["total_skills"]
    # Every node should appear in the never_used list when there is no usage.
    names = {item["name"] for item in payload["never_used"]}
    assert "deploy_to_prod" in names


def test_skill_report_reflects_recorded_usage(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    # Pre-seed the usage store the engine reads from on construction.
    usage_path = tmp_path / "state" / "skill_usage.json"
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    usage_path.write_text(
        json.dumps(
            {
                "deploy_to_prod": {
                    "use_count": 7,
                    "first_used": "2026-01-01T00:00:00+00:00",
                    "last_used": "2026-06-01T00:00:00+00:00",
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skill", "report", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["report"]["tracked_skills"] == 1
    top = payload["report"]["top_skills"]
    assert top and top[0]["name"] == "deploy_to_prod"
    assert top[0]["use_count"] == 7
