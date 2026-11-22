"""Regression test for BB-32: MCP tools classified as 'integrations' group,
never activated, invisible to the LLM.

Root cause:
  - classify() stamps all un-prefixed tools with default="integrations"
  - _active_groups starts empty (only "core" is always-on)
  - get_schemas(active_groups=set()) only returns "core" tools
  - MCP tools are therefore invisible to the LLM every turn

Fix:
  - reclassify_by_prefix() moves MCP-namespaced tools into the "mcp" group
  - The "mcp" group is activated at session start whenever MCP servers exist
"""

from __future__ import annotations

from hachi.core.loop import ToolRegistry


class TestMcpToolVisibility:
    """MCP tools must be visible to the LLM after classify (BB-32)."""

    def _make_registry_with_mcp_tool(self) -> ToolRegistry:
        """Set up a ToolRegistry that mirrors the production boot sequence:
        one core tool + one MCP-namespaced tool, then classify() with
        default="integrations" (the pre-fix production logic).
        """
        reg = ToolRegistry()
        reg.register({"name": "use_tools"}, lambda: "ok")
        reg.register({"name": "demo_list_files"}, lambda: "files")
        # Mirrors orchestrator.py classify() call with default="integrations"
        reg.classify(
            core_names={"use_tools"},
            group_by_name={},
            prefix_groups={"google_": "google"},
            default="integrations",
        )
        return reg

    def test_mcp_tool_hidden_without_fix(self) -> None:
        """Before the fix: demo_list_files is in 'integrations' group, which is
        never in _active_groups, so get_schemas(active_groups=set()) hides it.
        This documents the bug and will pass only as long as the classify()
        default remains "integrations" and no fix has been applied yet.
        """
        reg = self._make_registry_with_mcp_tool()
        # Confirm classify stamped it as "integrations"
        assert reg._groups["demo_list_files"] == "integrations"
        # Confirm LLM would not see it (empty active_groups)
        schemas = reg.get_schemas(active_groups=set())
        schema_names = {s["name"] for s in schemas}
        assert "demo_list_files" not in schema_names, (
            "demo_list_files must NOT appear when active_groups=set() "
            "(it is in 'integrations' which is never activated) — "
            "this assertion documents the pre-fix bug"
        )

    def test_reclassify_by_prefix_moves_mcp_tools_into_mcp_group(self) -> None:
        """After reclassify_by_prefix({'demo_': 'mcp'}), the tool is in 'mcp' group."""
        reg = self._make_registry_with_mcp_tool()
        # Apply the fix
        reg.reclassify_by_prefix({"demo_": "mcp"})
        assert reg._groups["demo_list_files"] == "mcp"

    def test_mcp_tool_visible_after_reclassify_and_activate(self) -> None:
        """After reclassify + activating 'mcp' group, the LLM sees the tool."""
        reg = self._make_registry_with_mcp_tool()
        reg.reclassify_by_prefix({"demo_": "mcp"})
        schemas = reg.get_schemas(active_groups={"mcp"})
        schema_names = {s["name"] for s in schemas}
        assert "demo_list_files" in schema_names, (
            "demo_list_files must be visible when 'mcp' is an active group"
        )

    def test_reclassify_by_prefix_longest_prefix_wins(self) -> None:
        """Longer prefix takes priority over shorter one (same as classify)."""
        reg = ToolRegistry()
        reg.register({"name": "demo_sub_list"}, lambda: "x")
        reg.register({"name": "demo_list"}, lambda: "y")
        reg.classify(core_names=set(), group_by_name={}, default="integrations")
        reg.reclassify_by_prefix({"demo_": "mcp", "demo_sub_": "mcp_sub"})
        assert reg._groups["demo_sub_list"] == "mcp_sub"
        assert reg._groups["demo_list"] == "mcp"

    def test_reclassify_by_prefix_no_match_unchanged(self) -> None:
        """Tools with no matching prefix stay in their current group."""
        reg = ToolRegistry()
        reg.register({"name": "other_tool"}, lambda: "x")
        reg.classify(core_names=set(), group_by_name={}, default="integrations")
        reg.reclassify_by_prefix({"demo_": "mcp"})
        # "other_tool" has no "demo_" prefix — stays "integrations"
        assert reg._groups["other_tool"] == "integrations"

    def test_reclassify_by_prefix_empty_dict_is_noop(self) -> None:
        """Calling reclassify_by_prefix({}) leaves all groups unchanged."""
        reg = self._make_registry_with_mcp_tool()
        before = dict(reg._groups)
        reg.reclassify_by_prefix({})
        assert reg._groups == before
