"""Tests for the SkillEngine 3-pass loading model.

These prove the differentiator actually works: search (Pass 1) is lightweight,
peek (Pass 2) returns compressed summaries without heavy bodies, and load
(Pass 3) renders only the requested blocks and does NOT auto-expand the whole
dependency tree.
"""

from __future__ import annotations

import json
from pathlib import Path

from hachi.og_engine.engine import SkillEngine, estimate_tokens
from hachi.og_engine.parser import parse_og_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"

# A sentence that appears ONLY in deploy_to_prod's ::full block.
DEPLOY_FULL_MARKER = "multi-step process"
# A sentence that appears ONLY in run_tests' ::full block.
RUN_TESTS_FULL_MARKER = "Run the complete automated test suite"


def _engine() -> SkillEngine:
    engine = SkillEngine()
    engine.load_file(FIXTURE)
    return engine


def test_estimate_tokens_is_monotonic() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a") == 1
    assert estimate_tokens("x" * 400) == 100


def test_search_keyword_fuzzy_and_miss() -> None:
    engine = _engine()
    assert "deploy_to_prod" in {r["name"] for r in engine.search("deploy")}
    assert "run_tests" in {r["name"] for r in engine.search("pytest")}
    # fuzzy substring: "deployment" should still hit the "deploy" keyword
    assert "deploy_to_prod" in {r["name"] for r in engine.search("deployment")}
    # no match returns an empty list (not an error)
    assert engine.search("zzzznotarealkeyword") == []


def test_peek_returns_dense_and_manifest_not_bodies() -> None:
    engine = _engine()
    peeked = engine.peek(["deploy_to_prod"])
    entry = peeked["deploy_to_prod"]

    assert entry["dense"].startswith("deploy|prod")
    assert entry["warning"].startswith("Never deploy")
    assert entry["requires"] == ["run_tests"]
    # manifest lists heavy blocks + their token cost, but not their content
    assert "full" in entry["available_blocks"]
    assert "steps" in entry["available_blocks"]
    assert entry["available_blocks"]["full"] > 0

    # crucially, the heavy bodies are NOT present anywhere in the peek payload
    assert DEPLOY_FULL_MARKER not in json.dumps(peeked)


def test_peek_unknown_node_reports_error() -> None:
    engine = _engine()
    assert "error" in engine.peek(["does_not_exist"])["does_not_exist"]


def test_resolve_node_renders_only_requested_blocks() -> None:
    engine = _engine()
    steps_only = engine.resolve_node("deploy_to_prod", blocks=["steps"])
    assert "Verify the working tree is clean." in steps_only  # a step
    assert DEPLOY_FULL_MARKER not in steps_only  # full block excluded


def test_load_default_does_not_expand_dependency_tree() -> None:
    engine = _engine()
    rendered = engine.resolve_node("deploy_to_prod")  # default execution blocks

    assert DEPLOY_FULL_MARKER in rendered  # own full content is present
    # the dependency's full content is NOT pulled in automatically...
    assert RUN_TESTS_FULL_MARKER not in rendered
    # ...it is only listed by name for the agent to load on demand
    assert "Dependencies" in rendered
    assert "run_tests" in rendered


def test_resolve_node_all_expands_everything() -> None:
    engine = _engine()
    everything = engine.resolve_node("deploy_to_prod", blocks=["all"])
    assert DEPLOY_FULL_MARKER in everything
    assert "WARNING" in everything
    assert "Steps" in everything
    assert "MANDATORY ASSERTIONS" in everything


def test_load_time_nudges_to_check_skill_assertions() -> None:
    """M2: a Pass-3 load of a skill with ::assertions must point the agent at
    check_skill_assertions right in the load response — previously this instruction
    only lived in brain.og's system prompt, so it was easy for the loop to skip
    calling it despite the "MANDATORY" label right above it.
    """
    engine = _engine()
    everything = engine.resolve_node("deploy_to_prod", blocks=["all"])
    assert 'check_skill_assertions(name="deploy_to_prod"' in everything


def test_resolve_context_delegates_to_default_load() -> None:
    engine = _engine()
    assert engine.resolve_context("deploy_to_prod") == engine.resolve_node("deploy_to_prod")
    assert "not found" in engine.resolve_context("nope")


def test_export_skill_round_trips(tmp_path: Path) -> None:
    engine = _engine()
    text = engine.export_skill("deploy_to_prod")
    assert text is not None

    out = tmp_path / "exported.og"
    out.write_text(text, encoding="utf-8")
    reparsed = parse_og_file(str(out))
    node = reparsed.get_node_by_id("deploy_to_prod")
    assert node is not None
    assert node.dense == engine.get_node("deploy_to_prod").dense
    assert DEPLOY_FULL_MARKER in node.full

    assert engine.export_skill("does_not_exist") is None


def test_usage_tracking_records_and_flags_stale(tmp_path: Path) -> None:
    engine = _engine()
    # Redirect the usage DB off the real home directory for hermetic testing.
    engine._usage_path = tmp_path / "skill_usage.json"
    engine._usage = {}

    engine.record_use("deploy_to_prod")
    engine.record_use("deploy_to_prod")
    assert engine._usage["deploy_to_prod"]["use_count"] == 2
    assert (tmp_path / "skill_usage.json").exists()

    stale = engine.get_stale_skills()
    statuses = {s["name"]: s["status"] for s in stale}
    # run_tests was never loaded → reported as never_used
    assert statuses.get("run_tests") == "never_used"


def test_skill_inventory_joins_metadata_and_usage(tmp_path: Path) -> None:
    engine = _engine()
    engine._usage_path = tmp_path / "skill_usage.json"
    engine._usage = {}
    engine.record_use("deploy_to_prod")
    engine.record_use("deploy_to_prod")

    inventory = engine.get_skill_inventory()
    by_name = {row["name"]: row for row in inventory}

    # Every loaded node appears, even never-used ones.
    assert "deploy_to_prod" in by_name
    assert "run_tests" in by_name
    # Usage stats are joined in.
    assert by_name["deploy_to_prod"]["use_count"] == 2
    assert by_name["run_tests"]["use_count"] == 0
    assert by_name["run_tests"]["last_used"] is None
    # Node metadata is carried.
    assert by_name["deploy_to_prod"]["keyword_count"] >= 1
    assert by_name["deploy_to_prod"]["role"]
    # Sorted most-used first.
    assert inventory[0]["name"] == "deploy_to_prod"
