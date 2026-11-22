"""Tests for the ObjectGraph (.og) parser.

The parser had zero coverage; these lock in the structural contract the engine
and the 3-pass loading model depend on (meta, index, node blocks, edges, scope).
"""

from __future__ import annotations

from pathlib import Path

from hachi.og_engine.parser import parse_og_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"


def _parse():
    return parse_og_file(str(FIXTURE))


def test_meta_block_parsed() -> None:
    og = _parse()
    assert og.meta.title == "Deployment Skills"
    assert og.meta.version == "1.0.0"
    assert og.meta.domain == "deployment|devops"
    assert og.meta.scope == "all"


def test_index_routing_table_parsed() -> None:
    og = _parse()
    ids = {entry.node_id for entry in og.index}
    assert ids == {"deploy_to_prod", "run_tests", "secret_rotation"}

    deploy = next(e for e in og.index if e.node_id == "deploy_to_prod")
    assert deploy.node_type == "skill"
    assert deploy.scope == "all"
    assert deploy.confidence == 0.99
    assert "production" in deploy.keywords

    # The compact index prompt is the ~30-token Pass-1 routing map.
    prompt = og.get_index_prompt()
    assert "deploy_to_prod" in prompt
    assert "secret_rotation" in prompt


def test_all_nodes_and_block_types_parsed() -> None:
    og = _parse()
    assert {n.name for n in og.nodes} == {"deploy_to_prod", "run_tests", "secret_rotation"}

    deploy = og.get_node_by_id("deploy_to_prod")
    assert deploy is not None
    # metadata edges
    assert deploy.role == "skill"
    assert deploy.scope == "all"
    assert "production" in deploy.keywords
    assert deploy.requires == ["run_tests"]
    # content blocks
    assert deploy.dense.startswith("deploy|prod")
    assert "multi-step process" in deploy.full
    assert deploy.warning.startswith("Never deploy")
    assert len(deploy.steps) == 5
    # leading numbering is stripped by the parser
    assert deploy.steps[0] == "Verify the working tree is clean."
    assert "bash" in deploy.code_blocks
    assert "pytest -q" in deploy.code_blocks["bash"]
    assert len(deploy.assertions) == 2
    assert any("[:requires]" in edge for edge in deploy.edges)


def test_scope_metadata_distinguishes_nodes() -> None:
    og = _parse()
    secret = og.get_node_by_id("secret_rotation")
    assert secret is not None
    assert secret.scope == "orchestrator"


def test_filter_by_scope_enforces_rbac() -> None:
    og = _parse()
    worker_view = og.filter_by_scope("worker")
    names = {n.name for n in worker_view.nodes}
    assert "deploy_to_prod" in names  # scope=all is always visible
    assert "secret_rotation" not in names  # orchestrator-only hidden from worker
    # the index is filtered too
    assert all(e.node_id != "secret_rotation" for e in worker_view.index)

    orch_view = og.filter_by_scope("orchestrator")
    assert "secret_rotation" in {n.name for n in orch_view.nodes}


def test_malformed_file_does_not_crash(tmp_path: Path) -> None:
    bad = tmp_path / "broken.og"
    bad.write_text("this is not a valid og file ::node[ unterminated", encoding="utf-8")
    # Parser should return a structure, not raise, on garbage input.
    og = parse_og_file(str(bad))
    assert og.meta.title == ""
    assert og.index == []
