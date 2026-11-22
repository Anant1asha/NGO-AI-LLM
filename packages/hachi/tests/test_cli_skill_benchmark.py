"""Tests for `hachi skill benchmark` CLI command.

Four cases:
1. Happy path — runs against bundled skills, passes threshold, human output.
2. JSON output — `--json` flag produces valid JSON with expected keys.
3. Custom threshold — `--threshold 0.0` always passes; `--threshold 0.9999` fails (exit 1).
4. Dir not found — `--dir /nonexistent` exits 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bundled_dir() -> Path:
    """Return the bundled default_skills path (same logic as test_og_benchmark)."""
    import hachi.og_engine.engine as og_engine_mod

    pkg_root = Path(og_engine_mod.__file__).resolve().parent.parent
    return pkg_root / "default_skills"


def _skip_if_no_bundled():
    """pytest.skip when default_skills is missing or too small."""
    d = _bundled_dir()
    if not d.exists():
        pytest.skip("bundled default_skills directory not found")
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(d)
    if len(engine.get_all_nodes()) < 3:
        pytest.skip("not enough skill nodes to run benchmark")


# ---------------------------------------------------------------------------
# 1. Happy path — human-readable output, exit 0
# ---------------------------------------------------------------------------


def test_benchmark_human_output_exits_zero() -> None:
    _skip_if_no_bundled()
    result = runner.invoke(app, ["skill", "benchmark"])
    assert result.exit_code == 0, result.output
    # Must mention the key figures.
    assert "Token savings" in result.output
    assert "Baseline" in result.output
    assert "3-pass" in result.output


# ---------------------------------------------------------------------------
# 2. JSON output — --json flag, valid payload with all expected keys
# ---------------------------------------------------------------------------


def test_benchmark_json_output_has_expected_keys() -> None:
    _skip_if_no_bundled()
    result = runner.invoke(app, ["skill", "benchmark", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    # Top-level keys (suite=token by default)
    assert "nodes" in data
    assert "suite" in data
    assert "passed" in data
    assert data["suite"] == "token"
    # Token arm nested under "token"
    token = data["token"]
    for key in (
        "baseline_tokens",
        "three_pass_tokens",
        "savings_pct",
        "p1_tokens",
        "p2_tokens",
        "p3_tokens",
        "threshold",
        "passed",
        "query",
    ):
        assert key in token, f"Missing key '{key}' in token arm output"
    assert data["nodes"] >= 3
    assert token["baseline_tokens"] > 0
    assert token["three_pass_tokens"] > 0
    assert 0.0 <= token["savings_pct"] <= 1.0
    assert token["threshold"] == 0.80
    assert isinstance(token["passed"], bool)


# ---------------------------------------------------------------------------
# 3a. Custom threshold zero — always passes
# ---------------------------------------------------------------------------


def test_benchmark_threshold_zero_always_passes() -> None:
    _skip_if_no_bundled()
    result = runner.invoke(app, ["skill", "benchmark", "--json", "--threshold", "0.0"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["passed"] is True
    assert data["token"]["threshold"] == 0.0


# ---------------------------------------------------------------------------
# 3b. Custom threshold 0.9999 — triggers failure exit 1
# ---------------------------------------------------------------------------


def test_benchmark_threshold_999_fails_exit_1() -> None:
    _skip_if_no_bundled()
    result = runner.invoke(app, ["skill", "benchmark", "--json", "--threshold", "0.9999"])
    # savings will always be < 0.9999 (even at 97% we need > 99.99% to pass)
    data = json.loads(result.output)
    if data["token"]["savings_pct"] < 0.9999:
        assert result.exit_code == 1
        assert data["passed"] is False
    else:
        # extremely unlikely but we can't fail the test if savings really are > 99.99%
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 4. Dir not found — exits 2
# ---------------------------------------------------------------------------


def test_benchmark_dir_not_found_exits_2(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    result = runner.invoke(app, ["skill", "benchmark", "--dir", str(missing)])
    assert result.exit_code == 2
    assert "not found" in result.output.lower()
