"""Regression test for BB-34: duplicate skill names in get_skill_inventory().

Root cause: _nodes is keyed by qid; two nodes with the same display name
(e.g. "identity" defined in two .og files) produce duplicate rows. The web UI
uses name as the React key, so duplicates cause "Encountered two children with
the same key" warnings and broken list reconciliation.

Fix: get_skill_inventory() deduplicates by name after sorting — highest
use_count entry wins (first in the sorted list).
"""

from __future__ import annotations

from hachi.og_engine.engine import SkillEngine
from hachi.og_engine.parser import OGNode


def _engine_with_duplicate_names() -> SkillEngine:
    """Build a SkillEngine with two nodes that share the same display name."""
    eng = SkillEngine()
    node_a = OGNode(name="identity", source_file="file_a.og")
    node_b = OGNode(name="identity", source_file="file_b.og")
    node_c = OGNode(name="other", source_file="file_c.og")
    eng._nodes["file_a:identity"] = node_a
    eng._nodes["file_b:identity"] = node_b
    eng._nodes["file_c:other"] = node_c
    return eng


class TestSkillInventoryDedup:
    """get_skill_inventory() must not emit duplicate names (BB-34)."""

    def test_no_duplicate_names_in_inventory(self) -> None:
        """Inventory must have unique names even when _nodes has same-name entries."""
        eng = _engine_with_duplicate_names()
        inventory = eng.get_skill_inventory()
        names = [item["name"] for item in inventory]
        assert len(names) == len(set(names)), (
            f"Duplicate names in inventory: {names} — "
            "get_skill_inventory() must deduplicate by name (BB-34)"
        )

    def test_identity_appears_exactly_once(self) -> None:
        """The 'identity' skill must appear exactly once despite two source nodes."""
        eng = _engine_with_duplicate_names()
        inventory = eng.get_skill_inventory()
        identity_entries = [i for i in inventory if i["name"] == "identity"]
        assert len(identity_entries) == 1, (
            f"Expected 1 'identity' entry, got {len(identity_entries)} (BB-34)"
        )

    def test_all_distinct_names_present(self) -> None:
        """All distinct skill names must still appear in the inventory."""
        eng = _engine_with_duplicate_names()
        names = {item["name"] for item in eng.get_skill_inventory()}
        assert "identity" in names
        assert "other" in names
