"""P2-03b: skill benchmark --suite flag tests.

Verifies that the CLI `hachi skill benchmark --suite <X>` correctly:
- Runs token arm for `--suite token` (default)
- Runs M1 arm for `--suite retrieval`
- Runs both arms for `--suite fast`
- Returns correct JSON keys per suite
- Exits 1 when a gate fails
- Rejects unknown suite values
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# M1 metrics unit tests (metrics.py)
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_probes() -> list[dict[str, Any]]:
    return [
        {"id": "k001", "type": "K", "query": "currency exchange", "expected": ["core_currency"]},
        {"id": "k002", "type": "K", "query": "weather forecast", "expected": ["core_weather"]},
        {
            "id": "p001",
            "type": "P",
            "query": "convert dollars to euros",
            "expected": ["core_currency"],
        },
        {
            "id": "i001",
            "type": "I",
            "query": "check the weather in London",
            "expected": ["core_weather"],
        },
        {"id": "n001", "type": "N", "query": "supercalifragilistic nothing", "expected": []},
    ]


def _make_engine(hits: dict[str, list[str]]) -> Any:
    """Stub SkillEngine whose search() returns controlled results."""
    engine = MagicMock()

    def _search(query: str):
        names = hits.get(query, [])
        return [{"name": n} for n in names]

    engine.search.side_effect = _search
    return engine


def test_m1_perfect_retrieval(sample_probes):
    from benchmarks.og_bench.metrics import compute_m1

    engine = _make_engine(
        {
            "currency exchange": ["core_currency"],
            "weather forecast": ["core_weather"],
            "convert dollars to euros": ["core_currency"],
            "check the weather in London": ["core_weather"],
            "supercalifragilistic nothing": [],  # negative — returns nothing
        }
    )
    m1 = compute_m1(engine, sample_probes)
    assert m1.p_at_1 == 1.0
    assert m1.p_at_5 == 1.0
    assert m1.mrr == 1.0
    assert m1.fpr_negative == 0.0
    assert m1.n_queries == 4
    assert m1.n_negative == 1


def test_m1_all_misses(sample_probes):
    from benchmarks.og_bench.metrics import compute_m1

    engine = _make_engine({})  # every query returns empty list
    m1 = compute_m1(engine, sample_probes)
    assert m1.p_at_1 == 0.0
    assert m1.p_at_5 == 0.0
    assert m1.mrr == 0.0
    assert len(m1.misses) == 4


def test_m1_false_positives_on_negative_probes(sample_probes):
    from benchmarks.og_bench.metrics import compute_m1

    engine = _make_engine(
        {
            # Positive queries hit correctly
            "currency exchange": ["core_currency"],
            "weather forecast": ["core_weather"],
            "convert dollars to euros": ["core_currency"],
            "check the weather in London": ["core_weather"],
            # Negative query also returns a result (FP)
            "supercalifragilistic nothing": ["some_skill"],
        }
    )
    m1 = compute_m1(engine, sample_probes)
    assert m1.fpr_negative == 1.0
    assert len(m1.false_positives) == 1


def test_m1_partial_retrieval(sample_probes):
    from benchmarks.og_bench.metrics import compute_m1

    # Only keyword probes hit; paraphrase and intent miss
    engine = _make_engine(
        {
            "currency exchange": ["core_currency"],
            "weather forecast": ["core_weather"],
            # p001 and i001 miss
            "supercalifragilistic nothing": [],
        }
    )
    m1 = compute_m1(engine, sample_probes)
    # 2/4 positive hit at rank 1
    assert m1.p_at_1 == 0.5
    assert m1.p_at_5 == 0.5
    assert len(m1.misses) == 2


def test_m1_no_negative_probes():
    from benchmarks.og_bench.metrics import compute_m1

    probes = [
        {"id": "k001", "type": "K", "query": "foo", "expected": ["skill_foo"]},
    ]
    engine = _make_engine({"foo": ["skill_foo"]})
    m1 = compute_m1(engine, probes)
    assert m1.fpr_negative == 0.0
    assert m1.n_negative == 0


# ---------------------------------------------------------------------------
# load_probes
# ---------------------------------------------------------------------------


def test_load_probes_default_file():
    from benchmarks.og_bench.metrics import load_probes

    probes = load_probes()
    assert len(probes) >= 30
    assert all("id" in p and "type" in p and "query" in p and "expected" in p for p in probes)


def test_load_probes_custom_file(tmp_path: Path):
    from benchmarks.og_bench.metrics import load_probes

    data = {
        "corpus": "test",
        "probes": [{"id": "x001", "type": "K", "query": "test", "expected": ["some_skill"]}],
    }
    f = tmp_path / "custom.json"
    f.write_text(json.dumps(data))
    probes = load_probes(f)
    assert len(probes) == 1
    assert probes[0]["id"] == "x001"


# ---------------------------------------------------------------------------
# CLI integration (typer test client)
# ---------------------------------------------------------------------------


def _make_skill_engine_mock(nodes_count: int = 10, keyword: str = "currency") -> Any:
    """Create a MagicMock SkillEngine for CLI-level tests."""
    node = MagicMock()
    node.name = "core_currency"

    engine = MagicMock()
    engine.get_all_nodes.return_value = [node] * nodes_count
    engine._keyword_index = {keyword: ["core_currency"]}
    engine.search.return_value = [{"name": "core_currency", "score": 0.9}]
    engine.peek.return_value = {"core_currency": {"dense": "Currency exchange tool."}}
    engine.resolve_node.return_value = "Currency exchange content."
    return engine


@pytest.fixture()
def cli_runner():
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture()
def cli_app():
    from hachi.cli.main import app

    return app


def test_cli_suite_unknown_exits_2(cli_runner, cli_app):
    result = cli_runner.invoke(cli_app, ["skill", "benchmark", "--suite", "bogus"])
    assert result.exit_code == 2


@patch("hachi.og_engine.engine.estimate_tokens", return_value=1000)
@patch("hachi.og_engine.engine.SkillEngine")
@patch("hachi.gateway.workspace.get_skills_dir", return_value=Path("."))
def test_cli_suite_token_json_output(mock_dir, mock_engine_cls, mock_tokens, cli_runner, cli_app):
    mock_engine_cls.return_value = _make_skill_engine_mock()
    result = cli_runner.invoke(
        cli_app, ["skill", "benchmark", "--suite", "token", "--json", "--threshold", "0.70"]
    )
    if result.exit_code not in (0, 1):
        # If there's an unexpected error, show output
        print(result.output)
    output_json = json.loads(result.output.strip())
    assert output_json["suite"] == "token"
    assert "token" in output_json
    assert "m1" not in output_json


@patch("hachi.og_engine.engine.estimate_tokens", return_value=1000)
@patch("hachi.og_engine.engine.SkillEngine")
@patch("hachi.gateway.workspace.get_skills_dir", return_value=Path("."))
def test_cli_suite_fast_json_has_both_arms(
    mock_dir, mock_engine_cls, mock_tokens, cli_runner, cli_app
):
    eng = _make_skill_engine_mock()
    mock_engine_cls.return_value = eng
    with patch("benchmarks.og_bench.metrics.compute_m1") as mock_m1, patch(
        "benchmarks.og_bench.metrics.load_probes"
    ) as mock_load:
        from benchmarks.og_bench.metrics import M1Result

        mock_load.return_value = [
            {
                "id": "k001",
                "type": "K",
                "query": "currency exchange",
                "expected": ["core_currency"],
            },
            {"id": "n001", "type": "N", "query": "nonsense xyz", "expected": []},
        ]
        mock_m1.return_value = M1Result(
            p_at_1=1.0, p_at_5=1.0, r_at_5=1.0, mrr=1.0,
            fpr_negative=0.0, n_queries=1, n_negative=1,
        )
        result = cli_runner.invoke(
            cli_app, ["skill", "benchmark", "--suite", "fast", "--json", "--threshold", "0.70"]
        )
    try:
        output_json = json.loads(result.output.strip())
    except json.JSONDecodeError:
        pytest.fail(f"Non-JSON output:\n{result.output}")
    assert output_json["suite"] == "fast"
    assert "token" in output_json
    assert "m1" in output_json
    assert output_json["m1"]["passed"] is True


@patch("hachi.og_engine.engine.estimate_tokens", return_value=1000)
@patch("hachi.og_engine.engine.SkillEngine")
@patch("hachi.gateway.workspace.get_skills_dir", return_value=Path("."))
def test_cli_m1_gate_fail_exits_1(mock_dir, mock_engine_cls, mock_tokens, cli_runner, cli_app):
    eng = _make_skill_engine_mock()
    mock_engine_cls.return_value = eng
    with patch("benchmarks.og_bench.metrics.compute_m1") as mock_m1, patch(
        "benchmarks.og_bench.metrics.load_probes"
    ) as mock_load:
        from benchmarks.og_bench.metrics import M1Result

        mock_load.return_value = [
            {
                "id": "k001",
                "type": "K",
                "query": "currency exchange",
                "expected": ["core_currency"],
            },
        ]
        # P@5 below 0.80 — should fail
        mock_m1.return_value = M1Result(
            p_at_1=0.5, p_at_5=0.5, r_at_5=0.5, mrr=0.5,
            fpr_negative=0.0, n_queries=1, n_negative=0,
        )
        result = cli_runner.invoke(
            cli_app, ["skill", "benchmark", "--suite", "retrieval", "--json"]
        )
    assert result.exit_code == 1
    output_json = json.loads(result.output.strip())
    assert output_json["m1"]["passed"] is False
    assert output_json["passed"] is False
