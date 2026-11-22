"""Regression test for BB-33: web_search / extract_url classified as
'integrations' group after classify(), invisible to the LLM even when
Tavily is configured.

Root cause:
  - register_search_tools() calls registry.register(...) with no explicit
    group= arg, so both tools land in group="core" (the register() default).
  - classify() iterates all registered tools; for any tool whose CURRENT
    group is "core" but that is NOT in core_names, it reclassifies it to
    default="integrations".
  - web_search / extract_url were absent from _CORE_TOOL_NAMES, so classify()
    demoted them to "integrations".
  - _active_groups never contains "integrations", so get_schemas() hides them
    every turn → the LLM cannot call web_search.

Fix: add "web_search" and "extract_url" to _CORE_TOOL_NAMES in orchestrator.py.
"""

from __future__ import annotations

from hachi.core.loop import ToolRegistry
from hachi.gateway.orchestrator import (
    _CORE_TOOL_NAMES,
    _GROUP_BY_TOOL_NAME,
)


def _make_registry_with_search_tools() -> ToolRegistry:
    """Mirror the production boot sequence for search tools:
    register web_search + extract_url (as register_search_tools does),
    then run classify() with the exact production parameters.
    """
    reg = ToolRegistry()
    # A minimal core tool so core group is non-trivial
    reg.register({"name": "use_tools"}, lambda: "ok")
    reg.register({"name": "browse_web"}, lambda: "browse")
    # Mirrors register_search_tools() — no explicit group= arg
    reg.register({"name": "web_search"}, lambda: "search")
    reg.register({"name": "extract_url"}, lambda: "extract")
    # Run production classify() exactly
    reg.classify(
        core_names=set(_CORE_TOOL_NAMES),
        group_by_name=_GROUP_BY_TOOL_NAME,
        prefix_groups={"google_": "google"},
        default="integrations",
    )
    return reg


class TestSearchToolVisibility:
    """web_search and extract_url must be visible to the LLM after classify() (BB-33)."""

    def test_web_search_in_core_group_after_classify(self) -> None:
        """web_search must land in 'core' after production classify()."""
        reg = _make_registry_with_search_tools()
        actual = reg._groups["web_search"]
        assert actual == "core", (
            f"web_search is in group {actual!r} — add it to _CORE_TOOL_NAMES in orchestrator.py "
            "(BB-33: classify() reclassifies it to 'integrations' which is never activated)"
        )

    def test_extract_url_in_core_group_after_classify(self) -> None:
        """extract_url must land in 'core' after production classify()."""
        reg = _make_registry_with_search_tools()
        actual = reg._groups["extract_url"]
        assert actual == "core", (
            f"extract_url is in group {actual!r} — add it to _CORE_TOOL_NAMES in orchestrator.py "
            "(BB-33: classify() reclassifies it to 'integrations' which is never activated)"
        )

    def test_search_tools_visible_to_llm_without_unlocking_extra_groups(self) -> None:
        """LLM must see web_search and extract_url with only the 'core' group active."""
        reg = _make_registry_with_search_tools()
        schemas = reg.get_schemas(active_groups=set())
        names = {s["name"] for s in schemas}
        assert "web_search" in names, (
            "web_search not in get_schemas(active_groups=set()) — LLM can never call it (BB-33)"
        )
        assert "extract_url" in names, (
            "extract_url not in get_schemas(active_groups=set()) — LLM can never call it (BB-33)"
        )

    def test_browse_web_stays_core_unaffected(self) -> None:
        """browse_web must stay 'core' — confirm the fix doesn't break existing core tools."""
        reg = _make_registry_with_search_tools()
        assert reg._groups["browse_web"] == "core"
