"""Unit tests for ToolRegistrar ordering constraints."""

from __future__ import annotations

import pytest

from hachi.gateway.tool_registration import ToolRegistrar, ToolSpec


def _noop(d) -> str:
    return "ok"


def test_registrar_installs_in_dependency_order():
    order = []
    specs = [
        ToolSpec(name="b", after={"a"}, register_fn=lambda d: order.append("b")),
        ToolSpec(name="a", register_fn=lambda d: order.append("a")),
    ]
    ToolRegistrar().install(specs, deps=None)
    assert order == ["a", "b"]


def test_delegation_always_last():
    order = []
    specs = [
        ToolSpec(name="a", register_fn=lambda d: order.append("a")),
        ToolSpec(name="delegation", last=True, register_fn=lambda d: order.append("delegation")),
        ToolSpec(name="b", register_fn=lambda d: order.append("b")),
    ]
    ToolRegistrar().install(specs, deps=None)
    assert order[-1] == "delegation"
    assert order.index("a") < order.index("delegation")
    assert order.index("b") < order.index("delegation")


def test_config_after_mcp():
    order = []
    specs = [
        ToolSpec(name="config", after={"mcp_tools"}, register_fn=lambda d: order.append("config")),
        ToolSpec(name="mcp_tools", register_fn=lambda d: order.append("mcp_tools")),
    ]
    ToolRegistrar().install(specs, deps=None)
    assert order.index("mcp_tools") < order.index("config")


def test_cycle_raises():
    specs = [
        ToolSpec(name="a", after={"b"}, register_fn=_noop),
        ToolSpec(name="b", after={"a"}, register_fn=_noop),
    ]
    with pytest.raises(ValueError, match="Cycle"):
        ToolRegistrar().install(specs, deps=None)


def test_unknown_after_dep_raises():
    specs = [
        ToolSpec(name="a", after={"nonexistent"}, register_fn=_noop),
    ]
    with pytest.raises(ValueError, match="nonexistent"):
        ToolRegistrar().install(specs, deps=None)


def test_results_map_captures_return_values():
    specs = [
        ToolSpec(name="browser", register_fn=lambda d: "browser_controller_instance"),
    ]
    results = ToolRegistrar().install(specs, deps=None)
    assert results["browser"] == "browser_controller_instance"


def test_multiple_last_specs_run_in_insertion_order():
    order = []
    specs = [
        ToolSpec(name="regular", register_fn=lambda d: order.append("regular")),
        ToolSpec(name="last_a", last=True, register_fn=lambda d: order.append("last_a")),
        ToolSpec(name="last_b", last=True, register_fn=lambda d: order.append("last_b")),
    ]
    ToolRegistrar().install(specs, deps=None)
    assert order.index("regular") < order.index("last_a")
    assert order.index("regular") < order.index("last_b")
    assert order.index("last_a") < order.index("last_b")


def test_empty_specs_returns_empty_dict():
    results = ToolRegistrar().install([], deps=None)
    assert results == {}


def test_single_spec_with_no_constraints():
    results = ToolRegistrar().install(
        [ToolSpec(name="only", register_fn=lambda d: 42)],
        deps=None,
    )
    assert results == {"only": 42}
