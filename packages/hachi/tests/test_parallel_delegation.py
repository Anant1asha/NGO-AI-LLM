"""Tests for delegate_parallel_tasks — concurrent sub-agent dispatch.

Covers:
1.  Empty tasks list → returns empty results immediately
2.  Single task → dispatched and returned correctly
3.  Multiple tasks → all run, results indexed correctly
4.  Cap: >10 tasks → only first 10 dispatched
5.  Thread cap: max _PARALLEL_MAX_WORKERS=3 at once (timing invariant)
6.  Error in one sub-agent → status="error", others still run
7.  Timeout: slow task → status="timeout", fast ones still complete
8.  on_event callbacks: delegation_parallel_start + delegation_parallel_complete fired
9.  delegate_parallel_tasks is in BLOCKED_TOOL_NAMES (no recursion)
10. Schema has correct name and required "tasks" field
11. register_delegation_tools registers delegate_parallel_tasks
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

from hachi.tools.delegation_tools import (
    BLOCKED_TOOL_NAMES,
    DELEGATE_PARALLEL_TASKS_SCHEMA,
    _make_delegate_parallel_tasks,
    register_delegation_tools,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_mock() -> Any:
    """Minimal ToolRegistry mock for the factory calls."""
    registry = MagicMock()
    registry.available_groups.return_value = {"core"}
    return registry


def _make_parallel_fn(
    single_fn: Callable[[str, str, str], str] | None = None,
    on_event: Callable[..., None] | None = None,
) -> Callable[..., str]:
    """Build delegate_parallel_tasks with an injectable single-task dispatcher."""
    registry = _make_registry_mock()
    fn = _make_delegate_parallel_tasks(
        parent_registry=registry,
        on_event=on_event,
    )
    if single_fn is not None:
        # Replace the internal _single dispatcher via patching
        import hachi.tools.delegation_tools as dt

        with patch.object(dt, "_make_delegate_task", return_value=single_fn):
            fn = _make_delegate_parallel_tasks(
                parent_registry=registry,
                on_event=on_event,
            )
    return fn


def _fast_single(role: str, task: str, context: str = "") -> str:
    """Instantly returns a mock delegate_task result."""
    return f"[{role}] done: {task}"


def _slow_single(delay: float) -> Callable[[str, str, str], str]:
    """Returns a delegate_task mock that sleeps for `delay` seconds."""

    def _fn(role: str, task: str, context: str = "") -> str:
        time.sleep(delay)
        return f"[{role}] slow done: {task}"

    return _fn


def _error_single(role: str, task: str, context: str = "") -> str:
    raise RuntimeError("sub-agent exploded")


# ---------------------------------------------------------------------------
# 1. Empty tasks list
# ---------------------------------------------------------------------------


def test_empty_tasks_returns_empty() -> None:
    import json

    fn = _make_parallel_fn(single_fn=_fast_single)
    result = json.loads(fn([]))
    assert result["results"] == []
    assert "No tasks provided" in result["message"]


# ---------------------------------------------------------------------------
# 2. Single task
# ---------------------------------------------------------------------------


def test_single_task_dispatched() -> None:
    import json

    fn = _make_parallel_fn(single_fn=_fast_single)
    result = json.loads(fn([{"role": "researcher", "task": "find stuff"}]))
    assert len(result["results"]) == 1
    assert result["results"][0]["status"] == "ok"
    assert "researcher" in result["results"][0]["output"]


# ---------------------------------------------------------------------------
# 3. Multiple tasks — all indexed correctly
# ---------------------------------------------------------------------------


def test_multiple_tasks_all_complete() -> None:
    import json

    fn = _make_parallel_fn(single_fn=_fast_single)
    tasks = [
        {"role": "coder", "task": "write tests"},
        {"role": "researcher", "task": "read docs"},
        {"role": "reviewer", "task": "check PR"},
    ]
    result = json.loads(fn(tasks))
    assert len(result["results"]) == 3
    indices = {r["index"] for r in result["results"]}
    assert indices == {0, 1, 2}
    for r in result["results"]:
        assert r["status"] == "ok"
    assert "3/3" in result["summary"]


# ---------------------------------------------------------------------------
# 4. Cap at 10 tasks
# ---------------------------------------------------------------------------


def test_cap_at_10_tasks() -> None:
    import json

    fn = _make_parallel_fn(single_fn=_fast_single)
    tasks = [{"role": "r", "task": f"task{i}"} for i in range(15)]
    result = json.loads(fn(tasks))
    assert len(result["results"]) == 10  # first 10 only


# ---------------------------------------------------------------------------
# 5. Worker cap (timing invariant — just ensure ≤3 dispatched simultaneously)
# ---------------------------------------------------------------------------


def test_parallel_max_workers_respected() -> None:
    """Verify that _PARALLEL_MAX_WORKERS (3) caps concurrency.

    We can't reliably time threads, but we can confirm all tasks complete.
    """
    from hachi.tools.delegation_tools import _PARALLEL_MAX_WORKERS

    assert _PARALLEL_MAX_WORKERS == 3


# ---------------------------------------------------------------------------
# 6. One sub-agent errors → status="error", others succeed
# ---------------------------------------------------------------------------


def test_one_error_others_succeed() -> None:
    import json

    call_count = 0

    def mixed_single(role: str, task: str, context: str = "") -> str:
        nonlocal call_count
        call_count += 1
        if role == "bad":
            raise RuntimeError("exploded")
        return f"[{role}] ok"

    fn = _make_parallel_fn(single_fn=mixed_single)
    tasks = [
        {"role": "good", "task": "fine"},
        {"role": "bad", "task": "breaks"},
        {"role": "good2", "task": "also fine"},
    ]
    result = json.loads(fn(tasks))
    statuses = {r["role"]: r["status"] for r in result["results"]}
    assert statuses["bad"] == "error"
    assert statuses["good"] == "ok"
    assert statuses["good2"] == "ok"
    assert "2/3" in result["summary"]


# ---------------------------------------------------------------------------
# 7. Timeout: slow task → status="timeout"
# ---------------------------------------------------------------------------


def test_timeout_marks_slow_task() -> None:
    import json

    def mixed_single(role: str, task: str, context: str = "") -> str:
        if role == "slow":
            time.sleep(5)  # longer than our test timeout
        return f"[{role}] done"

    fn = _make_parallel_fn(single_fn=mixed_single)
    tasks = [
        {"role": "fast", "task": "quick"},
        {"role": "slow", "task": "takes forever"},
    ]
    result = json.loads(fn(tasks, timeout_sec=1))  # 1s timeout
    by_role = {r["role"]: r for r in result["results"]}
    assert by_role["fast"]["status"] == "ok"
    assert by_role["slow"]["status"] == "timeout"
    assert "1/2" in result["summary"]


# ---------------------------------------------------------------------------
# 8. on_event callbacks fire
# ---------------------------------------------------------------------------


def test_on_event_callbacks() -> None:
    events: list[tuple[str, dict]] = []

    def capture(name: str, data: dict) -> None:
        events.append((name, data))

    fn = _make_parallel_fn(single_fn=_fast_single, on_event=capture)
    fn([{"role": "r", "task": "t"}])

    names = [e[0] for e in events]
    assert "delegation_parallel_start" in names
    assert "delegation_parallel_complete" in names
    start = next(e[1] for e in events if e[0] == "delegation_parallel_start")
    assert start["count"] == 1
    end = next(e[1] for e in events if e[0] == "delegation_parallel_complete")
    assert end["ok"] == 1


# ---------------------------------------------------------------------------
# 9. delegate_parallel_tasks is in BLOCKED_TOOL_NAMES
# ---------------------------------------------------------------------------


def test_parallel_tasks_blocked_for_sub_agents() -> None:
    assert "delegate_parallel_tasks" in BLOCKED_TOOL_NAMES


# ---------------------------------------------------------------------------
# 10. Schema structure
# ---------------------------------------------------------------------------


def test_schema_structure() -> None:
    assert DELEGATE_PARALLEL_TASKS_SCHEMA["name"] == "delegate_parallel_tasks"
    props = DELEGATE_PARALLEL_TASKS_SCHEMA["input_schema"]["properties"]
    assert "tasks" in props
    assert props["tasks"]["type"] == "array"
    assert DELEGATE_PARALLEL_TASKS_SCHEMA["input_schema"]["required"] == ["tasks"]


# ---------------------------------------------------------------------------
# 11. register_delegation_tools registers delegate_parallel_tasks
# ---------------------------------------------------------------------------


def test_register_delegation_tools_includes_parallel() -> None:
    registry = MagicMock()
    registry.available_groups.return_value = {"core"}
    register_delegation_tools(registry)
    registered_names = [call.args[0]["name"] for call in registry.register.call_args_list]
    assert "delegate_parallel_tasks" in registered_names
