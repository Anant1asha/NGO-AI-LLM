"""Tests for deterministic .og assertion evaluation + the check_skill_assertions tool."""

from __future__ import annotations

import json

from hachi.core.assertion_eval import (
    AssertionReport,
    evaluate_assertion,
    evaluate_assertions,
)
from hachi.core.loop import ToolRegistry
from hachi.og_engine.engine import SkillEngine
from hachi.og_engine.parser import OGNode
from hachi.tools.og_tools import _make_check_skill_assertions, register_og_tools


# --------------------------------------------------------------------------- #
# Evaluator — single lines (using REAL bundled-skill assertion strings)
# --------------------------------------------------------------------------- #
def test_string_not_empty_pass() -> None:
    line = 'assert channel_name != "" "A target Slack channel must be provided for the standup."'
    r = evaluate_assertion(line, {"channel_name": "#ops"})
    assert r.status == "pass"


def test_string_not_empty_fail_carries_message() -> None:
    line = 'assert channel_name != "" "A target Slack channel must be provided for the standup."'
    r = evaluate_assertion(line, {"channel_name": ""})
    assert r.status == "fail"
    assert "Slack channel" in r.message


def test_two_variable_comparison() -> None:
    line = 'assert base != target "Base and target currencies must be different."'
    assert evaluate_assertion(line, {"base": "USD", "target": "EUR"}).status == "pass"
    assert evaluate_assertion(line, {"base": "USD", "target": "USD"}).status == "fail"


def test_numeric_comparison() -> None:
    line = 'assert lamin != 0 "A valid bounding box must be provided to prevent massive payloads."'
    assert evaluate_assertion(line, {"lamin": 5}).status == "pass"
    assert evaluate_assertion(line, {"lamin": 0}).status == "fail"


def test_ordering_operator() -> None:
    line = 'assert count >= 1 "At least one item is required."'
    assert evaluate_assertion(line, {"count": 3}).status == "pass"
    assert evaluate_assertion(line, {"count": 0}).status == "fail"


def test_missing_value_is_unknown() -> None:
    line = 'assert word != "" "A word must be provided for the dictionary lookup."'
    r = evaluate_assertion(line, {})
    assert r.status == "unknown"
    assert "word" in r.detail


def test_non_assert_line_is_manual() -> None:
    r = evaluate_assertion("trigger: before[destructive_command]", {})
    assert r.status == "manual"


# --------------------------------------------------------------------------- #
# Aggregate report
# --------------------------------------------------------------------------- #
def test_report_ok_only_when_no_fail_or_unknown() -> None:
    lines = [
        'assert a != "" "a required"',
        'assert b != "" "b required"',
    ]
    ok_report = AssertionReport("s", evaluate_assertions(lines, {"a": "x", "b": "y"}))
    assert ok_report.ok is True

    bad_report = AssertionReport("s", evaluate_assertions(lines, {"a": "", "b": "y"}))
    assert bad_report.ok is False
    assert len(bad_report.failed) == 1

    partial = AssertionReport("s", evaluate_assertions(lines, {"a": "x"}))
    assert partial.ok is False
    assert len(partial.unknown) == 1


# --------------------------------------------------------------------------- #
# Tool
# --------------------------------------------------------------------------- #
def _engine_with_assertions(assertions: list[str]) -> SkillEngine:
    eng = SkillEngine()
    node = OGNode(name="demo", source_file="test_assertions.og", assertions=assertions)
    qid = "test_assertions:demo"
    eng._nodes[qid] = node
    eng._bare_name_index["demo"] = [qid]
    return eng


def test_tool_ok_when_assertions_pass() -> None:
    tool = _make_check_skill_assertions(_engine_with_assertions(['assert ch != "" "need channel"']))
    data = json.loads(tool("demo", {"ch": "#ops"}))
    assert data["ok"] is True
    assert data["failed"] == []


def test_tool_reports_failure_and_message() -> None:
    tool = _make_check_skill_assertions(_engine_with_assertions(['assert ch != "" "need channel"']))
    data = json.loads(tool("demo", {"ch": ""}))
    assert data["ok"] is False
    assert "need channel" in data["failed"][0]


def test_tool_reports_missing_values() -> None:
    tool = _make_check_skill_assertions(_engine_with_assertions(['assert ch != "" "need channel"']))
    data = json.loads(tool("demo", {}))
    assert data["ok"] is False
    assert data["needs_values"]


def test_tool_unknown_skill() -> None:
    tool = _make_check_skill_assertions(SkillEngine())
    assert "not found" in tool("ghost", {})


def test_tool_no_assertions_is_ok() -> None:
    tool = _make_check_skill_assertions(_engine_with_assertions([]))
    data = json.loads(tool("demo", {}))
    assert data["ok"] is True
    assert data["results"] == []


def test_register_includes_check_skill_assertions() -> None:
    reg = ToolRegistry()
    register_og_tools(reg, SkillEngine())
    names = {s["name"] for s in reg.get_schemas()}
    assert "check_skill_assertions" in names
