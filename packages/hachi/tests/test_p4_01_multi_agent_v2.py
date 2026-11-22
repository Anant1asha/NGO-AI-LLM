"""P4-01: Multi-agent v2 — leases, needs continuations, provenance edges.

Tests:
  1. LeaseManager.acquire() succeeds when target is free.
  2. LeaseManager.acquire() fails (conflict) when target is already held.
  3. Prefix match: a lease on 'projects/billing' blocks 'projects/billing/schema'.
  4. LeaseManager.release() clears the held target.
  5. Expired leases (TTL=0) do not block new acquisitions.
  6. LeaseManager.snapshot() returns currently active leases.
  7. SubAgentReport has a 'needs' field defaulting to None.
  8. SubAgentReport.to_orchestrator_string() includes continuation hint when needs set.
  9. MemoryWriter.write_nodes() injects provenance edge when by_agent is set.
  10. MemoryWriter.write_fact() convenience method writes a fact node.
  11. delegate_task blocks and returns error when lease conflict exists.
"""

from __future__ import annotations

import time
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. LeaseManager.acquire() succeeds for a free target
# ---------------------------------------------------------------------------


def test_lease_acquire_free_target() -> None:
    from hachi.core.lease_manager import LeaseManager

    mgr = LeaseManager()
    ok, conflict = mgr.acquire("researcher", ["projects/billing"])
    assert ok is True
    assert conflict is None


# ---------------------------------------------------------------------------
# 2. LeaseManager.acquire() fails when target is already held
# ---------------------------------------------------------------------------


def test_lease_acquire_conflict() -> None:
    from hachi.core.lease_manager import LeaseManager

    mgr = LeaseManager()
    mgr.acquire("researcher", ["projects/billing"])
    ok, conflict = mgr.acquire("analyst", ["projects/billing"])

    assert ok is False
    assert conflict is not None
    assert "researcher" in conflict


# ---------------------------------------------------------------------------
# 3. Prefix match: lease on 'a/b' blocks 'a/b/c'
# ---------------------------------------------------------------------------


def test_lease_prefix_match() -> None:
    from hachi.core.lease_manager import LeaseManager

    mgr = LeaseManager()
    mgr.acquire("agent-a", ["projects/billing"])
    ok, conflict = mgr.acquire("agent-b", ["projects/billing/schema"])

    assert ok is False, "Sub-prefix should be blocked by parent lease"


# ---------------------------------------------------------------------------
# 4. LeaseManager.release() clears the held target
# ---------------------------------------------------------------------------


def test_lease_release_clears_target() -> None:
    from hachi.core.lease_manager import LeaseManager

    mgr = LeaseManager()
    mgr.acquire("researcher", ["projects/billing"])
    mgr.release("researcher", ["projects/billing"])

    ok, _ = mgr.acquire("analyst", ["projects/billing"])
    assert ok is True, "Target should be available after release"


# ---------------------------------------------------------------------------
# 5. Expired leases (TTL≈0) do not block new acquisitions
# ---------------------------------------------------------------------------


def test_lease_ttl_expiry() -> None:
    from hachi.core.lease_manager import LeaseManager

    mgr = LeaseManager()
    mgr.acquire("researcher", ["projects/old"], ttl_seconds=0.001)
    time.sleep(0.01)  # let it expire

    ok, _ = mgr.acquire("analyst", ["projects/old"])
    assert ok is True, "Expired lease should not block new acquisition"


# ---------------------------------------------------------------------------
# 6. LeaseManager.snapshot() returns active leases
# ---------------------------------------------------------------------------


def test_lease_snapshot() -> None:
    from hachi.core.lease_manager import LeaseManager

    mgr = LeaseManager()
    mgr.acquire("researcher", ["projects/billing", "drive.write"])
    snap = mgr.snapshot()

    assert len(snap) == 1
    assert snap[0]["role"] == "researcher"
    assert "expires_in_s" in snap[0]


# ---------------------------------------------------------------------------
# 7. SubAgentReport has 'needs' field defaulting to None
# ---------------------------------------------------------------------------


def test_sub_agent_report_needs_default() -> None:
    from hachi.core.sub_agent import SubAgentReport, SubAgentStatus

    report = SubAgentReport(
        status=SubAgentStatus.SUCCESS,
        summary="done",
        role="researcher",
        task="find billing schema",
    )
    assert report.needs is None


# ---------------------------------------------------------------------------
# 8. SubAgentReport.to_orchestrator_string() includes needs when set
# ---------------------------------------------------------------------------


def test_sub_agent_report_needs_in_string() -> None:
    from hachi.core.sub_agent import SubAgentReport, SubAgentStatus

    report = SubAgentReport(
        status=SubAgentStatus.SUCCESS,
        summary="Research complete.",
        role="researcher",
        task="find billing schema",
        needs={"role": "analyst", "task": "analyse the schema"},
    )
    text = report.to_orchestrator_string()

    assert "Continuation requested" in text
    assert "analyst" in text
    assert "REQUEST" in text  # safety note present


# ---------------------------------------------------------------------------
# 9. MemoryWriter.write_nodes() injects provenance when by_agent set
# ---------------------------------------------------------------------------


def test_memory_writer_provenance_edge(tmp_path: Path) -> None:
    from hachi.core.memory_writer import MemoryNode, MemoryWriter

    writer = MemoryWriter(memory_dir=tmp_path)
    node = MemoryNode(name="billing-fact", role="fact", dense="billing schema v2")
    writer.write_nodes([node], by_agent="researcher")

    written_file = tmp_path / "core_memory.og"
    assert written_file.exists()
    content = written_file.read_text(encoding="utf-8")
    assert "->[:by=agent:researcher]" in content


# ---------------------------------------------------------------------------
# 10. MemoryWriter.write_fact() creates a fact node
# ---------------------------------------------------------------------------


def test_memory_writer_write_fact(tmp_path: Path) -> None:
    from hachi.core.memory_writer import MemoryWriter

    writer = MemoryWriter(memory_dir=tmp_path)
    fact_id = writer.write_fact("billing migration uses pgloader", category="decision")

    assert isinstance(fact_id, str)
    assert fact_id.startswith("fact-")
    # File should exist with a ::node block
    og_file = tmp_path / "core_memory.og"
    assert og_file.exists()
    assert "::node[" in og_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 11. delegate_task returns error when lease conflict exists
# ---------------------------------------------------------------------------


def test_delegate_task_blocked_by_lease() -> None:
    from hachi.core.lease_manager import LeaseManager
    from hachi.core.loop import ToolRegistry
    from hachi.tools.delegation_tools import _make_delegate_task

    mgr = LeaseManager()
    mgr.acquire("existing-agent", ["projects/billing"])

    registry = ToolRegistry()
    handler = _make_delegate_task(
        parent_registry=registry,
        lease_manager=mgr,
    )

    result = handler(role="coder", task="update billing", write_targets=["projects/billing"])
    assert "error" in result.lower() or "blocked" in result.lower(), (
        f"Expected blocked error, got: {result}"
    )
