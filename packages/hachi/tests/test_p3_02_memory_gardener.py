"""P3-02: M3 MemoryGardener — dedupe, expire, and diff-card tests.

Tests:
  1. GardeningResult.save() / load() round-trip.
  2. find_dedup_same_name() detects same node in two files.
  3. Auto-apply writes ::changelog to the older file.
  4. find_similar_content() proposes merge for high-Jaccard nodes.
  5. find_expired() flags past valid_until nodes.
  6. run() returns GardeningResult with auto_applied + pending_review.
  7. run() writes pending_diffs.json.
  8. _jaccard() baseline cases.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NODE_A = """\
::meta
  title: Project A

::node[billing-task]
->[:role=task]
->[:status=open]
->[:keywords=billing, payments]
->[:updated=2026-06-10T00:00:00Z]
::dense
Migrate the billing table to the new schema.
"""

_NODE_B = """\
::meta
  title: Project B (same node name)

::node[billing-task]
->[:role=task]
->[:status=open]
->[:keywords=billing, payments]
->[:updated=2026-06-12T00:00:00Z]
::dense
Migrate the billing table to the new schema (newer copy).
"""

_NODE_SIMILAR = """\
::meta
  title: Project Similar

::node[billing-work]
->[:role=task]
->[:status=open]
->[:keywords=billing, payments, migrate]
->[:updated=2026-06-10T00:00:00Z]
::dense
Migrate the billing table to the new schema, in progress.
"""

_NODE_EXPIRED = """\
::meta
  title: Expired Facts

::node[old-decision]
->[:role=fact]
->[:valid_until=2025-01-01T00:00:00Z]
->[:keywords=old, expired]
->[:updated=2025-01-01T00:00:00Z]
::dense
Use DMS for migration. (expired — replaced by pgloader decision)
"""


def _write_file(directory: Path, name: str, content: str, mtime_offset: float = 0.0) -> Path:
    p = directory / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if mtime_offset:
        new_mtime = p.stat().st_mtime + mtime_offset
        import os
        os.utime(p, (new_mtime, new_mtime))
    return p


# ---------------------------------------------------------------------------
# 1. GardeningResult save/load round-trip
# ---------------------------------------------------------------------------


def test_gardening_result_save_load(tmp_path: Path) -> None:
    from hachi.core.memory_gardener import GardeningProposal, GardeningResult, ProposalKind

    result = GardeningResult(
        run_ts="2026-06-13T00:00:00Z",
        auto_applied=[
            GardeningProposal(
                kind=ProposalKind.DEDUP_SAME_NAME,
                name_a="billing-task",
                reason="duplicate",
                confidence=1.0,
                file_path_a="a.og",
                file_path_b="b.og",
                auto_applied=True,
            )
        ],
        pending_review=[
            GardeningProposal(
                kind=ProposalKind.MERGE_SIMILAR,
                name_a="billing-work",
                name_b="billing-task",
                reason="Jaccard 0.85",
                confidence=0.85,
            )
        ],
    )
    path = tmp_path / "pending_diffs.json"
    result.save(path)
    loaded = GardeningResult.load(path)
    assert loaded.run_ts == "2026-06-13T00:00:00Z"
    assert len(loaded.auto_applied) == 1
    assert len(loaded.pending_review) == 1
    assert loaded.auto_applied[0].name_a == "billing-task"
    assert loaded.pending_review[0].kind == "merge_similar"


# ---------------------------------------------------------------------------
# 2. find_dedup_same_name detects same node in two files
# ---------------------------------------------------------------------------


def test_find_dedup_same_name(tmp_path: Path) -> None:
    from hachi.core.memory_gardener import MemoryGardener

    _write_file(tmp_path, "projects/a.og", _NODE_A, mtime_offset=-100)
    _write_file(tmp_path, "projects/b.og", _NODE_B)

    gardener = MemoryGardener(tmp_path)
    result = gardener.run(auto_apply=False)

    kinds = [p.kind for p in result.pending_review]
    assert "dedup_same_name" in kinds, f"Expected dedup proposal, got: {kinds}"
    dup_props = [p for p in result.pending_review if p.kind == "dedup_same_name"]
    assert any(p.name_a == "billing-task" for p in dup_props)


# ---------------------------------------------------------------------------
# 3. Auto-apply writes ::changelog to the older file
# ---------------------------------------------------------------------------


def test_auto_apply_writes_changelog(tmp_path: Path) -> None:
    from hachi.core.memory_gardener import MemoryGardener

    older = _write_file(tmp_path, "projects/a.og", _NODE_A, mtime_offset=-100)
    _write_file(tmp_path, "projects/b.og", _NODE_B)

    gardener = MemoryGardener(tmp_path)
    result = gardener.run(auto_apply=True)

    assert len(result.auto_applied) >= 1, "Expected at least one auto-applied dedup"
    older_text = older.read_text(encoding="utf-8")
    assert "::changelog" in older_text, "::changelog must be appended to the older file"


# ---------------------------------------------------------------------------
# 4. find_similar_content proposes merge for high-Jaccard nodes
# ---------------------------------------------------------------------------


def test_find_similar_content(tmp_path: Path) -> None:
    from hachi.core.memory_gardener import MemoryGardener

    _write_file(tmp_path, "projects/a.og", _NODE_A)
    _write_file(tmp_path, "projects/similar.og", _NODE_SIMILAR)

    gardener = MemoryGardener(tmp_path, similarity_threshold=0.5)
    result = gardener.run(auto_apply=False)

    kinds = [p.kind for p in result.pending_review]
    assert "merge_similar" in kinds, f"Expected merge_similar proposal; got {kinds}"


# ---------------------------------------------------------------------------
# 5. find_expired flags past valid_until nodes
# ---------------------------------------------------------------------------


def test_find_expired(tmp_path: Path) -> None:
    from hachi.core.memory_gardener import MemoryGardener

    _write_file(tmp_path, "projects/expired.og", _NODE_EXPIRED)
    gardener = MemoryGardener(tmp_path)
    result = gardener.run(auto_apply=False)

    kinds = [p.kind for p in result.pending_review]
    assert "expire_stale" in kinds, f"Expected expire_stale; got {kinds}"
    exp = next(p for p in result.pending_review if p.kind == "expire_stale")
    assert exp.name_a == "old-decision"


# ---------------------------------------------------------------------------
# 6. run() returns GardeningResult with both lists
# ---------------------------------------------------------------------------


def test_run_returns_result(tmp_path: Path) -> None:
    from hachi.core.memory_gardener import GardeningResult, MemoryGardener

    _write_file(tmp_path, "projects/a.og", _NODE_A, mtime_offset=-100)
    _write_file(tmp_path, "projects/b.og", _NODE_B)
    _write_file(tmp_path, "projects/expired.og", _NODE_EXPIRED)

    gardener = MemoryGardener(tmp_path)
    result = gardener.run()

    assert isinstance(result, GardeningResult)
    assert result.run_ts, "run_ts should be set"


# ---------------------------------------------------------------------------
# 7. run() writes pending_diffs.json
# ---------------------------------------------------------------------------


def test_run_writes_pending_diffs_json(tmp_path: Path) -> None:
    from hachi.core.memory_gardener import MemoryGardener

    _write_file(tmp_path, "projects/expired.og", _NODE_EXPIRED)
    gardener = MemoryGardener(tmp_path)
    gardener.run()

    diffs_path = tmp_path / "pending_diffs.json"
    assert diffs_path.exists(), "pending_diffs.json must be written by run()"
    import json
    data = json.loads(diffs_path.read_text(encoding="utf-8"))
    assert "pending_review" in data
    assert "auto_applied" in data


# ---------------------------------------------------------------------------
# 8. _jaccard baseline cases
# ---------------------------------------------------------------------------


def test_jaccard_identical() -> None:
    from hachi.core.memory_gardener import _jaccard

    assert _jaccard("billing migrate schema", "billing migrate schema") == 1.0


def test_jaccard_disjoint() -> None:
    from hachi.core.memory_gardener import _jaccard

    assert _jaccard("billing migrate schema", "weather forecast rain") == 0.0


def test_jaccard_partial() -> None:
    from hachi.core.memory_gardener import _jaccard

    sim = _jaccard("billing migrate schema", "billing migrate payments")
    assert 0.3 < sim < 0.9
