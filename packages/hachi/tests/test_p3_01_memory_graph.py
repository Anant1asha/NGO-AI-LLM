"""P3-01: M2 graph features — typed edges, Stage-C expansion, resume-pack composer.

Tests:
  1. MemoryNode accepts edges + status fields.
  2. _node_block() emits ->[:key=value] edge lines.
  3. parse_memory_file() reconstructs nodes with edges.
  4. expand_graph() joins task nodes that belong to a seeded project.
  5. expand_graph() filters superseded nodes.
  6. expand_graph() respects max_nodes cap.
  7. compose_resume_pack() returns non-empty string.
  8. compose_resume_pack() stays within token budget.
  9. retrieve_and_compose() works end-to-end on a temp memory dir.
  10. Extractor tool schema includes edges field.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 1. MemoryNode accepts edges + status
# ---------------------------------------------------------------------------


def test_memory_node_edges_field() -> None:
    from hachi.core.memory_writer import MemoryNode

    node = MemoryNode(
        name="my-task",
        role="task",
        dense="Migrate the payments table.",
        edges=["->[:about=billing-db-migration]", "->[:blocks=deploy]"],
        status="open",
    )
    assert node.edges == ["->[:about=billing-db-migration]", "->[:blocks=deploy]"]
    assert node.status == "open"


# ---------------------------------------------------------------------------
# 2. _node_block() emits edge lines
# ---------------------------------------------------------------------------


def test_node_block_writes_edges() -> None:
    from hachi.core.memory_writer import MemoryNode, _node_block

    node = MemoryNode(
        name="billing-task",
        role="task",
        dense="Migrate billing table.",
        status="blocked",
        edges=["->[:about=billing-db]", "->[:caused_by=circular-fk]"],
    )
    block = _node_block(node)
    assert "->[:about=billing-db]" in block
    assert "->[:caused_by=circular-fk]" in block
    assert "->[:status=blocked]" in block


# ---------------------------------------------------------------------------
# 3. parse_memory_file() reconstructs nodes with edges
# ---------------------------------------------------------------------------


_SAMPLE_OG = """\
::node[billing-task]
->[:role=task]
->[:status=open]
->[:about=billing-db-migration]
->[:keywords=billing, migrate, task]
->[:updated=2026-06-13T00:00:00Z]
::dense
Migrate the billing table to the new schema.

::node[billing-db-migration]
->[:role=fact]
->[:keywords=billing, database, migration]
->[:updated=2026-06-13T00:00:00Z]
::dense
Billing DB migration is 1/3 complete; pgloader chosen over DMS.
"""


def test_parse_memory_file(tmp_path: Path) -> None:
    from hachi.core.memory_graph import parse_memory_file

    og = tmp_path / "projects" / "billing.og"
    og.parent.mkdir()
    og.write_text(_SAMPLE_OG, encoding="utf-8")

    nodes = parse_memory_file(og)
    names = {n.name for n in nodes}
    assert "billing-task" in names
    assert "billing-db-migration" in names

    task = next(n for n in nodes if n.name == "billing-task")
    assert task.status == "open"
    assert "about" in task.edges
    assert "billing-db-migration" in task.edges["about"]


# ---------------------------------------------------------------------------
# 4. expand_graph() auto-joins open task nodes of seeded project
# ---------------------------------------------------------------------------


def test_expand_graph_joins_project_tasks() -> None:
    from hachi.core.memory_graph import GraphNode, expand_graph

    project = GraphNode(name="billing-db", role="fact", dense="Billing DB migration.")
    task = GraphNode(
        name="migrate-task",
        role="task",
        dense="Migrate payments table.",
        status="open",
        edges={"about": ["billing-db"]},
    )
    index = {"billing-db": project, "migrate-task": task}

    result = expand_graph(["billing-db"], index)
    names = {n.name for n in result}
    assert "billing-db" in names
    assert "migrate-task" in names, "Open task should be auto-joined via about edge"


# ---------------------------------------------------------------------------
# 5. expand_graph() filters superseded nodes
# ---------------------------------------------------------------------------


def test_expand_graph_filters_superseded() -> None:
    from hachi.core.memory_graph import GraphNode, expand_graph

    old_decision = GraphNode(name="old-db-decision", role="fact", dense="Use DMS.")
    new_decision = GraphNode(
        name="new-db-decision",
        role="fact",
        dense="Use pgloader (enum casts).",
        supersedes=["old-db-decision"],
    )
    index = {"old-db-decision": old_decision, "new-db-decision": new_decision}

    result = expand_graph(["new-db-decision", "old-db-decision"], index)
    names = {n.name for n in result}
    assert "new-db-decision" in names
    assert "old-db-decision" not in names, "Superseded node must be filtered out"


# ---------------------------------------------------------------------------
# 6. expand_graph() respects max_nodes
# ---------------------------------------------------------------------------


def test_expand_graph_respects_max_nodes() -> None:
    from hachi.core.memory_graph import GraphNode, expand_graph

    index = {
        f"node-{i}": GraphNode(name=f"node-{i}", role="fact", dense=f"Fact {i}.")
        for i in range(20)
    }
    seeds = list(index.keys())
    result = expand_graph(seeds, index, max_nodes=5)
    assert len(result) <= 5


# ---------------------------------------------------------------------------
# 7. compose_resume_pack() returns non-empty string
# ---------------------------------------------------------------------------


def test_compose_resume_pack_non_empty() -> None:
    from hachi.core.memory_graph import GraphNode, compose_resume_pack

    nodes = [
        GraphNode(name="billing-db", role="fact", dense="Billing DB migration is 1/3 complete."),
        GraphNode(name="migrate-task", role="task", dense="Migrate payments table.", status="open"),
    ]
    pack = compose_resume_pack(nodes, query="billing migration")
    assert pack, "compose_resume_pack returned empty string"
    assert "billing-db" in pack
    assert "migrate-task" in pack


# ---------------------------------------------------------------------------
# 8. compose_resume_pack() stays within token budget
# ---------------------------------------------------------------------------


def test_compose_resume_pack_budget() -> None:
    from hachi.core.memory_graph import GraphNode, compose_resume_pack

    nodes = [
        GraphNode(name=f"n{i}", role="fact", dense="A" * 200)
        for i in range(20)
    ]
    pack = compose_resume_pack(nodes, max_tokens=100)
    # 100 tokens ≈ 400 chars; pack should not be more than ~500 chars.
    assert len(pack) <= 600, f"Pack too long: {len(pack)} chars"


# ---------------------------------------------------------------------------
# 9. retrieve_and_compose() end-to-end
# ---------------------------------------------------------------------------


def test_retrieve_and_compose_end_to_end(tmp_path: Path) -> None:
    from hachi.core.memory_graph import retrieve_and_compose

    mem_dir = tmp_path / "memory"
    proj_dir = mem_dir / "projects"
    proj_dir.mkdir(parents=True)
    (proj_dir / "billing.og").write_text(_SAMPLE_OG, encoding="utf-8")

    result = retrieve_and_compose("billing migration", mem_dir, top_k_seeds=3)
    assert result, "retrieve_and_compose returned empty string for non-empty memory dir"
    assert "billing" in result.lower()


def test_retrieve_and_compose_empty_dir(tmp_path: Path) -> None:
    from hachi.core.memory_graph import retrieve_and_compose

    result = retrieve_and_compose("anything", tmp_path / "nonexistent")
    assert result == ""


# ---------------------------------------------------------------------------
# 10. Extractor tool schema includes edges field
# ---------------------------------------------------------------------------


def test_extractor_schema_has_edges_field() -> None:
    """The M1 extraction tool schema must include the edges field for P3-01."""
    import inspect

    import hachi.core.memory as memory_mod
    from hachi.core.memory import MemoryManager

    # The schema (including the edges field + edge-format docstring) lives in the
    # module-level extract_facts function.  Fall back to _run_typed_extraction so
    # the test stays green if the code is ever reorganised again.
    source = inspect.getsource(memory_mod.extract_facts)
    if "edges" not in source:
        source += inspect.getsource(MemoryManager._run_typed_extraction)  # type: ignore[attr-defined]
    assert "edges" in source, "Extractor tool schema missing 'edges' field"
    assert "->[:key=value]" in source or "->[:about=" in source, (
        "Extractor schema should document edge format"
    )
