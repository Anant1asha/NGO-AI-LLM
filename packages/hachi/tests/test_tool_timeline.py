"""Tests for the tool-call timeline projection in RuntimeReadModelStore.

The store pairs ``tool.call.started`` with the matching ``tool.call.completed``
event (FIFO per tool name), computing status + duration — feeding the Ops
dashboard's Tool Timeline panel without any extra loop plumbing.
"""

from __future__ import annotations

from hachi.core.runtime_events import RuntimeEvent
from hachi.core.runtime_read_models import RuntimeReadModelStore


def _ev(name: str, payload: dict, timestamp: str) -> RuntimeEvent:
    return RuntimeEvent(name=name, payload=payload, timestamp=timestamp)


def test_started_then_completed_pairs_into_one_row() -> None:
    store = RuntimeReadModelStore()
    store.append_event(_ev("tool.call.started", {"name": "read_file"}, "2026-06-06T10:00:00"))
    store.append_event(
        _ev(
            "tool.call.completed",
            {"name": "read_file", "result_preview": "ok"},
            "2026-06-06T10:00:02",
        )
    )

    calls = store.tool_calls()
    assert len(calls) == 1
    row = calls[0]
    assert row.name == "read_file"
    assert row.status == "completed"
    assert row.detail == "ok"
    assert row.duration_seconds == 2.0
    assert row.timestamp == "2026-06-06T10:00:00"  # start time


def test_running_call_shows_before_completion() -> None:
    store = RuntimeReadModelStore()
    store.append_event(_ev("tool.call.started", {"name": "slow_tool"}, "2026-06-06T10:00:00"))

    calls = store.tool_calls()
    assert len(calls) == 1
    assert calls[0].status == "running"
    assert calls[0].duration_seconds == 0.0


def test_error_preview_marks_failed() -> None:
    store = RuntimeReadModelStore()
    store.append_event(_ev("tool.call.started", {"name": "boom"}, "2026-06-06T10:00:00"))
    store.append_event(
        _ev(
            "tool.call.completed",
            {"name": "boom", "result_preview": "Tool Execution Error: kaboom"},
            "2026-06-06T10:00:01",
        )
    )
    assert store.tool_calls()[0].status == "failed"


def test_fifo_pairing_with_concurrent_same_name_calls() -> None:
    store = RuntimeReadModelStore()
    store.append_event(_ev("tool.call.started", {"name": "t"}, "2026-06-06T10:00:00"))
    store.append_event(_ev("tool.call.started", {"name": "t"}, "2026-06-06T10:00:01"))
    # First completion resolves the FIRST (oldest) start.
    store.append_event(
        _ev("tool.call.completed", {"name": "t", "result_preview": "first"}, "2026-06-06T10:00:05")
    )

    calls = store.tool_calls()
    assert len(calls) == 2
    assert calls[0].status == "completed"
    assert calls[0].detail == "first"
    assert calls[0].duration_seconds == 5.0
    assert calls[1].status == "running"


def test_completed_without_start_is_recorded() -> None:
    store = RuntimeReadModelStore()
    store.append_event(
        _ev(
            "tool.call.completed",
            {"name": "orphan", "result_preview": "done"},
            "2026-06-06T10:00:00",
        )
    )
    calls = store.tool_calls()
    assert len(calls) == 1
    assert calls[0].name == "orphan"
    assert calls[0].status == "completed"
    assert calls[0].duration_seconds == 0.0
