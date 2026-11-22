"""Tests for ADV-006 (fail-closed on role .og parse failure) and
ADV-012 (delegation depth/cycle backstop).

Covers:
1.  ADV-006: RoleResolver.resolve raises → delegate_task returns abort message,
    _build_scoped_registry is NOT called, SubAgentRuntime is NOT constructed.
2.  ADV-006: parse_og_file raises → same abort, no sub-agent started.
3.  ADV-006: delegation_complete event emitted with status="aborted" on .og failure.
4.  ADV-012: depth >= MAX_DEPTH → blocked with clear message.
5.  ADV-012: role already in ancestry → cycle blocked with clear message.
6.  ADV-012: depth/cycle event emitted with status="aborted".
7.  Happy path: valid role, depth=0 → sub-agent is constructed (sanity check).
8.  Lease released even when .og parse fails (no leak).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hachi.tools.delegation_tools import (
    _DELEGATION_MAX_DEPTH,
    _make_delegate_task,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_registry() -> Any:
    """Minimal ToolRegistry mock."""
    registry = MagicMock()
    registry.get_schemas.return_value = []
    registry._tools = {}
    registry.available_groups.return_value = {"core"}
    return registry


def _make_fn(
    on_event=None,
    lease_manager=None,
    depth: int = 0,
    ancestry: tuple[str, ...] = (),
) -> Any:
    """Build a delegate_task handler with the given depth/ancestry context."""
    return _make_delegate_task(
        parent_registry=_make_registry(),
        on_event=on_event,
        lease_manager=lease_manager,
        _depth=depth,
        _ancestry=ancestry,
    )


# ---------------------------------------------------------------------------
# 1. RoleResolver.resolve raises → abort, no sub-agent
# ---------------------------------------------------------------------------


def test_resolve_failure_returns_abort_message() -> None:
    """ADV-006: when RoleResolver.resolve raises, delegate_task aborts (fail closed)."""
    build_registry_calls: list = []
    runtime_calls: list = []

    def fake_build(*args, **kwargs):
        build_registry_calls.append(args)
        return _make_registry()

    with (
        patch(
            "hachi.tools.delegation_tools.RoleResolver.resolve",
            side_effect=FileNotFoundError("no role file"),
        ),
        patch(
            "hachi.tools.delegation_tools._build_scoped_registry",
            side_effect=fake_build,
        ),
        patch(
            "hachi.tools.delegation_tools.SubAgentRuntime",
            side_effect=lambda **kw: runtime_calls.append(kw),
        ),
    ):
        fn = _make_fn()
        result = fn(role="ghost", task="do something")

    assert "⛔ Delegation aborted" in result
    assert "ghost" in result
    assert "failing closed" in result
    # Critical: neither _build_scoped_registry nor SubAgentRuntime was called
    assert build_registry_calls == [], "build_scoped_registry must NOT be called on .og failure"
    assert runtime_calls == [], "SubAgentRuntime must NOT be constructed on .og failure"


# ---------------------------------------------------------------------------
# 2. parse_og_file raises → same abort, no sub-agent
# ---------------------------------------------------------------------------


def test_parse_og_failure_returns_abort_message() -> None:
    """ADV-006: when parse_og_file raises, delegate_task aborts (fail closed)."""
    build_registry_calls: list = []
    runtime_calls: list = []

    mock_path = MagicMock()

    with (
        patch(
            "hachi.tools.delegation_tools.RoleResolver.resolve",
            return_value=mock_path,
        ),
        patch(
            "hachi.tools.delegation_tools.parse_og_file",
            side_effect=ValueError("corrupt .og"),
        ),
        patch(
            "hachi.tools.delegation_tools._build_scoped_registry",
            side_effect=lambda *a, **kw: build_registry_calls.append(True) or _make_registry(),
        ),
        patch(
            "hachi.tools.delegation_tools.SubAgentRuntime",
            side_effect=lambda **kw: runtime_calls.append(kw),
        ),
    ):
        fn = _make_fn()
        result = fn(role="badparse", task="do something")

    assert "⛔ Delegation aborted" in result
    assert "badparse" in result
    assert "failing closed" in result
    assert build_registry_calls == [], "build_scoped_registry must NOT be called on .og failure"
    assert runtime_calls == [], "SubAgentRuntime must NOT be constructed on .og failure"


# ---------------------------------------------------------------------------
# 3. delegation_complete event emitted with status="aborted" on .og failure
# ---------------------------------------------------------------------------


def test_og_failure_emits_aborted_event() -> None:
    """ADV-006: a delegation_complete event with status='aborted' is emitted."""
    events: list[tuple[str, dict]] = []

    def capture(name: str, data: dict) -> None:
        events.append((name, data))

    with (
        patch(
            "hachi.tools.delegation_tools.RoleResolver.resolve",
            side_effect=FileNotFoundError("no og file"),
        ),
        patch("hachi.tools.delegation_tools._build_scoped_registry"),
        patch("hachi.tools.delegation_tools.SubAgentRuntime"),
    ):
        fn = _make_fn(on_event=capture)
        fn(role="phantom", task="t")

    aborted = [e for e in events if e[0] == "delegation_complete"]
    assert aborted, "delegation_complete event must be emitted on .og failure"
    assert aborted[0][1]["status"] == "aborted"
    assert aborted[0][1]["role"] == "phantom"


# ---------------------------------------------------------------------------
# 4. ADV-012: depth >= MAX_DEPTH → blocked
# ---------------------------------------------------------------------------


def test_depth_limit_blocks_delegation() -> None:
    """ADV-012: when depth >= MAX_DEPTH, delegation is refused."""
    runtime_calls: list = []

    with patch("hachi.tools.delegation_tools.SubAgentRuntime") as mock_runtime:
        mock_runtime.side_effect = lambda **kw: runtime_calls.append(kw)
        fn = _make_fn(depth=_DELEGATION_MAX_DEPTH)
        result = fn(role="coder", task="write code")

    assert "⛔ Delegation aborted" in result
    assert "depth" in result.lower()
    assert runtime_calls == [], "SubAgentRuntime must NOT be constructed when depth limit hit"


def test_depth_one_below_max_is_allowed() -> None:
    """ADV-012: depth = MAX_DEPTH - 1 should not be blocked by the depth check alone."""
    # We only check that the depth guard itself does not trigger; the subsequent
    # .og resolve will fail (no real .og file in tests), which is expected to
    # abort with ADV-006 — but the depth guard message must NOT appear.
    fn = _make_fn(depth=_DELEGATION_MAX_DEPTH - 1)
    result = fn(role="coder", task="write code")
    # The ADV-006 abort fires (no real .og), but NOT the depth-limit abort.
    assert "maximum delegation depth" not in result


# ---------------------------------------------------------------------------
# 5. ADV-012: role already in ancestry → cycle blocked
# ---------------------------------------------------------------------------


def test_cycle_detection_blocks_delegation() -> None:
    """ADV-012: if the role is already in the ancestry chain, delegation is refused."""
    runtime_calls: list = []

    with patch("hachi.tools.delegation_tools.SubAgentRuntime") as mock_runtime:
        mock_runtime.side_effect = lambda **kw: runtime_calls.append(kw)
        fn = _make_fn(depth=1, ancestry=("orchestrator", "coder"))
        result = fn(role="coder", task="write more code")

    assert "⛔ Delegation aborted" in result
    assert "cyclic" in result.lower()
    assert "coder" in result
    assert runtime_calls == [], "SubAgentRuntime must NOT be constructed on cycle detection"


def test_different_role_not_blocked_by_ancestry() -> None:
    """ADV-012: a role NOT in the ancestry chain should not be cycle-blocked."""
    # The subsequent .og resolve will fail (no real .og file), producing an ADV-006
    # abort — but the cycle message must NOT appear.
    fn = _make_fn(depth=1, ancestry=("orchestrator", "coder"))
    result = fn(role="researcher", task="research stuff")
    assert "cyclic" not in result.lower()


# ---------------------------------------------------------------------------
# 6. ADV-012: depth/cycle events emitted with status="aborted"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "depth,ancestry,role",
    [
        (_DELEGATION_MAX_DEPTH, (), "coder"),  # depth exceeded
        (1, ("orchestrator", "analyst"), "analyst"),  # cycle
    ],
)
def test_backstop_emits_aborted_event(depth: int, ancestry: tuple[str, ...], role: str) -> None:
    """ADV-012: depth/cycle violations emit a delegation_complete event with status='aborted'."""
    events: list[tuple[str, dict]] = []

    def capture(name: str, data: dict) -> None:
        events.append((name, data))

    with patch("hachi.tools.delegation_tools.SubAgentRuntime"):
        fn = _make_fn(on_event=capture, depth=depth, ancestry=ancestry)
        fn(role=role, task="t")

    aborted = [e for e in events if e[0] == "delegation_complete"]
    assert aborted, "delegation_complete event must be emitted on backstop refusal"
    assert aborted[0][1]["status"] == "aborted"


# ---------------------------------------------------------------------------
# 7. Happy path: valid role, depth=0 → sub-agent constructed
# ---------------------------------------------------------------------------


def test_happy_path_constructs_sub_agent() -> None:
    """Sanity: with a valid .og parse and depth=0, SubAgentRuntime IS constructed."""
    mock_og = MagicMock()
    mock_og.meta.tools = ""

    mock_report = MagicMock()
    mock_report.status.value = "success"
    mock_report.duration_seconds = 0.1
    mock_report.iterations = 1
    mock_report.to_orchestrator_string.return_value = "[Sub-Agent Report: coder]\nStatus: success"

    runtime_instance = MagicMock()
    runtime_instance.run.return_value = mock_report
    runtime_calls: list = []

    mock_path = MagicMock()

    with (
        patch(
            "hachi.tools.delegation_tools.RoleResolver.resolve",
            return_value=mock_path,
        ),
        patch(
            "hachi.tools.delegation_tools.parse_og_file",
            return_value=mock_og,
        ),
        patch(
            "hachi.tools.delegation_tools._build_scoped_registry",
            return_value=_make_registry(),
        ),
        patch(
            "hachi.tools.delegation_tools.SubAgentRuntime",
            return_value=runtime_instance,
        ) as MockRuntime,
    ):
        fn = _make_fn(depth=0)
        result = fn(role="coder", task="write tests")
        runtime_calls.append(MockRuntime.call_count)

    assert runtime_calls[0] == 1, "SubAgentRuntime must be constructed exactly once"
    assert "Sub-Agent Report" in result


# ---------------------------------------------------------------------------
# 8. Lease released even when .og parse fails
# ---------------------------------------------------------------------------


def test_lease_released_on_og_failure() -> None:
    """ADV-006: write-target leases are released even when .og parsing fails."""
    mock_lease = MagicMock()
    mock_lease.acquire.return_value = (True, None)

    with (
        patch(
            "hachi.tools.delegation_tools.RoleResolver.resolve",
            side_effect=FileNotFoundError("no og"),
        ),
        patch("hachi.tools.delegation_tools._build_scoped_registry"),
        patch("hachi.tools.delegation_tools.SubAgentRuntime"),
    ):
        fn = _make_fn(lease_manager=mock_lease)
        fn(role="ghost", task="t", write_targets=["projects/billing"])

    mock_lease.acquire.assert_called_once()
    mock_lease.release.assert_called_once_with("ghost", ["projects/billing"])
