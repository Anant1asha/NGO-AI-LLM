"""P5-01 conformance suite — verifies all spec fixtures parse correctly.

Reads spec/conformance/conformance.json, iterates each fixture file,
calls parse_og_file(), resolves every assertion path (dot notation +
array indexing), and checks equals/contains conditions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from hachi.og_engine.parser import OGFile, parse_og_file

SPEC_DIR = Path(__file__).parent.parent / "spec"
CONFORMANCE_JSON = SPEC_DIR / "conformance" / "conformance.json"
FIXTURES_DIR = SPEC_DIR / "conformance" / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ARRAY_IDX = re.compile(r"^(\w+)\[(\d+)\]$")


def _resolve_path(obj: Any, path: str) -> Any:
    """Walk dot-separated path with optional array indexing.

    Handles:
    - Pydantic model attributes (getattr)
    - Dict key lookup (when obj is a dict)
    - List index access via ``attr[N]`` syntax

    Examples::
        _resolve_path(og, "meta.title")               -> str
        _resolve_path(og, "nodes[0].name")            -> str
        _resolve_path(og, "nodes[0].requires[0]")     -> str
        _resolve_path(og, "nodes[0].traverse.priority") -> str
    """
    for segment in path.split("."):
        if obj is None:
            return None
        m = _ARRAY_IDX.match(segment)
        if m:
            attr, idx = m.group(1), int(m.group(2))
            if isinstance(obj, dict):
                obj = obj.get(attr)
            else:
                obj = getattr(obj, attr, None)
            if obj is None:
                return None
            obj = obj[idx]
        else:
            if isinstance(obj, dict):
                obj = obj.get(segment)
            else:
                obj = getattr(obj, segment, None)
    return obj


def _check(assertion: dict, og: OGFile) -> None:
    """Evaluate one assertion dict against a parsed OGFile."""
    path = assertion["path"]
    value = _resolve_path(og, path)

    if "equals" in assertion:
        expected = assertion["equals"]
        assert value == expected, (
            f"Path {path!r}: expected {expected!r}, got {value!r}"
        )
    elif "contains" in assertion:
        needle = assertion["contains"]
        if isinstance(value, str):
            assert needle in value, (
                f"Path {path!r}: {needle!r} not found in {value!r}"
            )
        elif isinstance(value, (list, dict)):
            assert needle in value, (
                f"Path {path!r}: {needle!r} not found in {value!r}"
            )
        else:
            pytest.fail(f"Path {path!r}: cannot check 'contains' on {type(value).__name__}")
    else:
        pytest.fail(f"Unknown assertion operator in: {assertion}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _load_conformance():
    return json.loads(CONFORMANCE_JSON.read_text(encoding="utf-8"))


def test_conformance_json_exists_and_has_fixtures() -> None:
    """The conformance.json file must exist and declare at least one fixture."""
    assert CONFORMANCE_JSON.exists(), f"conformance.json not found at {CONFORMANCE_JSON}"
    data = _load_conformance()
    assert "fixtures" in data
    assert len(data["fixtures"]) >= 1


def test_all_fixture_files_exist() -> None:
    """Every fixture listed in conformance.json must exist on disk."""
    data = _load_conformance()
    for entry in data["fixtures"]:
        path = SPEC_DIR / "conformance" / entry["file"]
        assert path.exists(), f"Fixture file missing: {path}"


def test_fixture_01_minimal_parses() -> None:
    """01-minimal.og: simplest valid file must parse without crashing."""
    path = FIXTURES_DIR / "01-minimal.og"
    og = parse_og_file(str(path))
    assert og.meta.title != "", "meta.title should be set"
    assert len(og.nodes) == 1, f"Expected 1 node, got {len(og.nodes)}"
    assert len(og.index) == 1, f"Expected 1 index entry, got {len(og.index)}"


def test_fixture_02_full_node_parses() -> None:
    """02-full-node.og: every tag type must be populated in the parsed node."""
    path = FIXTURES_DIR / "02-full-node.og"
    og = parse_og_file(str(path))
    assert len(og.nodes) == 1
    node = og.nodes[0]
    assert node.dense, "::dense must be populated"
    assert node.full, "::full must be populated"
    assert node.warning, "::warning must be populated"
    assert node.note, "::note must be populated"
    assert node.example, "::example must be populated"
    assert len(node.steps) >= 1, "::steps must have at least one entry"
    assert len(node.assertions) >= 1, "::assertion must have at least one entry"
    assert len(node.edges) >= 1, "::edges must have at least one entry"
    assert node.traverse, "::traverse must be populated"
    assert node.requires == ["hello"], "requires edge must be parsed"


def test_fixture_03_scoped_parses_and_filters() -> None:
    """03-scoped.og: two nodes with different scopes; filter_by_scope works."""
    path = FIXTURES_DIR / "03-scoped.og"
    og = parse_og_file(str(path))
    assert len(og.nodes) == 2

    scopes = {n.name: n.scope for n in og.nodes}
    assert scopes.get("public_action") == "all"
    assert scopes.get("restricted_step") == "orchestrator"

    # Worker view: only scope=all node visible
    worker_view = og.filter_by_scope("worker")
    worker_names = {n.name for n in worker_view.nodes}
    assert "public_action" in worker_names
    assert "restricted_step" not in worker_names

    # Orchestrator view: both visible
    orch_view = og.filter_by_scope("orchestrator")
    orch_names = {n.name for n in orch_view.nodes}
    assert "public_action" in orch_names
    assert "restricted_step" in orch_names


@pytest.mark.parametrize(
    "fixture_name",
    ["01-minimal.og", "02-full-node.og", "03-scoped.og"],
)
def test_conformance_assertions(fixture_name: str) -> None:
    """Each fixture satisfies every assertion declared in conformance.json."""
    data = _load_conformance()

    # Find the entry for this fixture
    rel_path = f"fixtures/{fixture_name}"
    entry = next((f for f in data["fixtures"] if f["file"] == rel_path), None)
    assert entry is not None, f"No conformance entry for {fixture_name}"

    path = SPEC_DIR / "conformance" / rel_path
    og = parse_og_file(str(path))

    for assertion in entry["assertions"]:
        _check(assertion, og)
