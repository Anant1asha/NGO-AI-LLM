"""Tests for the .og skill linter (engine.lint_og_file + `hachi skill lint`).

The linter enforces the conventions the 3-pass loader depends on: routable nodes
(index entry + keywords), a within-budget ::dense block, real Pass-3 content, and no
dangling ::index entries. These tests pin both the report structure and CLI exit codes.
"""

from pathlib import Path

from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.og_engine.engine import lint_og_file

runner = CliRunner()

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"

# A deliberately flawed file exercising every *warning/info* code using non-skill roles.
# Non-skill roles (rule/persona) only emit warnings, not errors, so ok=True.
BAD_OG = """::meta
  title: Lint Test
  version: 0.1.0

::index
  # node-id   | type  | scope | conf | keywords
  good_node   | rule  | all   | 0.9  | alpha, beta
  ghost       | rule  | all   | 0.9  | nothere

::node[good_node]
->[:role=rule]
->[:keywords=alpha, beta]
->[:requires=missing_dep]
::dense
this dense block is intentionally far too long to fit the token budget so the linter \
must flag it as over budget because it rambles on well past thirty tokens of content
::full
Some real Pass-3 content lives here.

::node[bare_node]
->[:role=rule]
::full
"""

# A flawed *skill-role* file: structural violations become errors for skill/native_integration.
BAD_SKILL_OG = """::meta
  title: Bad Skill
  version: 0.1.0

::index
  # node-id      | type  | scope | conf | keywords
  good_skill      | skill | all   | 0.9  | alpha, beta

::node[good_skill]
->[:role=skill]
->[:keywords=alpha, beta]
::dense
this dense block is intentionally far too long to fit the token budget so the linter \
must flag it as over budget because it rambles on well past thirty tokens of content
::full
Pass-3 content here.

::node[unindexed_skill]
->[:role=skill]
->[:keywords=gamma]
::full
No dense block and not in the index.
"""

EMPTY_OG = """::meta
  title: Nothing Here
  version: 0.1.0
"""


def _codes(report: dict) -> set[str]:
    return {issue["code"] for issue in report["issues"]}


def test_clean_fixture_passes():
    report = lint_og_file(FIXTURE)
    assert report["ok"] is True
    assert report["summary"]["errors"] == 0
    assert report["summary"]["warnings"] == 0
    assert report["node_count"] == 3


def test_missing_file_is_error():
    report = lint_og_file(Path("does") / "not" / "exist.og")
    assert report["ok"] is False
    assert "missing-file" in _codes(report)


def test_empty_file_has_no_nodes_error():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "empty.og"
        path.write_text(EMPTY_OG, encoding="utf-8")
        report = lint_og_file(path)
    assert report["ok"] is False
    assert "no-nodes" in _codes(report)


def test_flawed_file_surfaces_all_codes(tmp_path):
    path = tmp_path / "bad.og"
    path.write_text(BAD_OG, encoding="utf-8")
    report = lint_og_file(path)

    codes = _codes(report)
    # Warnings (advisory) for non-skill roles — file still "ok" because none are errors.
    assert "dangling-index" in codes  # ghost has no matching node
    assert "dense-over-budget" in codes  # good_node dense is too long
    assert "missing-index" in codes  # bare_node not in ::index
    assert "no-keywords" in codes  # bare_node has no keywords
    assert "missing-dense" in codes  # bare_node has no ::dense
    assert "empty-node" in codes  # bare_node has no Pass-3 content
    assert "external-requires" in codes  # good_node requires missing_dep

    assert report["ok"] is True  # all advisory (non-skill role), no errors
    assert report["summary"]["errors"] == 0
    assert report["summary"]["warnings"] > 0


def test_skill_role_structural_violations_are_errors(tmp_path):
    """missing-index, missing-dense, and dense-over-budget are errors for skill roles."""
    path = tmp_path / "bad_skill.og"
    path.write_text(BAD_SKILL_OG, encoding="utf-8")
    report = lint_og_file(path)

    codes = _codes(report)
    assert "dense-over-budget" in codes  # good_skill dense too long → error
    assert "missing-index" in codes  # unindexed_skill not in ::index → error
    assert "missing-dense" in codes  # unindexed_skill has no dense → error

    assert report["ok"] is False  # skill-role violations are blocking errors
    assert report["summary"]["errors"] >= 3


def test_cli_lint_clean_fixture_exits_zero():
    result = runner.invoke(app, ["skill", "lint", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_cli_lint_missing_path_exits_two():
    result = runner.invoke(app, ["skill", "lint", "no_such_path.og"])
    assert result.exit_code == 2


def test_cli_lint_strict_fails_on_warnings(tmp_path):
    path = tmp_path / "bad.og"
    path.write_text(BAD_OG, encoding="utf-8")

    # Without --strict, warnings do not fail the run.
    ok = runner.invoke(app, ["skill", "lint", str(path)])
    assert ok.exit_code == 0, ok.output

    # With --strict, warnings become failures (CI gate).
    strict = runner.invoke(app, ["skill", "lint", str(path), "--strict"])
    assert strict.exit_code == 1, strict.output


def test_cli_lint_json_output(tmp_path):
    import json

    path = tmp_path / "bad.og"
    path.write_text(BAD_OG, encoding="utf-8")
    result = runner.invoke(app, ["skill", "lint", str(path), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "reports" in payload
    assert payload["reports"][0]["node_count"] == 2
