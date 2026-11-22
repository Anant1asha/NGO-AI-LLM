"""Tests for the activity projection and sequenced event log in RuntimeReadModelStore.

These projections make the read model the single owner of event→derivation:
the activity reducer is pure (the TUI status header folds events through the
same function), and the event log carries monotonic sequence numbers the
gateway events endpoint pages against.
"""

from __future__ import annotations

from hachi.core.runtime_events import RuntimeEvent
from hachi.core.runtime_read_models import (
    ActivitySnapshot,
    RuntimeReadModelStore,
    advance_activity,
)


def _ev(name: str, payload: dict, timestamp: str = "2026-06-06T10:00:00") -> RuntimeEvent:
    return RuntimeEvent(name=name, payload=payload, timestamp=timestamp)


# --- advance_activity (pure reducer) --------------------------------------


def test_chat_started_is_running() -> None:
    out = advance_activity(ActivitySnapshot("Idle", "idle"), "session.chat.started", {})
    assert (out.label, out.state) == ("Working…", "running")


def test_thinking_includes_iteration() -> None:
    out = advance_activity(ActivitySnapshot("Idle", "idle"), "thinking.step", {"iteration": 3})
    assert out.label == "Thinking · step 3"
    assert out.state == "running"


def test_permission_requested_is_pending_then_decided_resumes() -> None:
    pending = advance_activity(ActivitySnapshot("Idle", "idle"), "permission.requested", {})
    assert (pending.label, pending.state) == ("Waiting for approval", "pending")
    resumed = advance_activity(pending, "permission.decided", {})
    assert (resumed.label, resumed.state) == ("Working…", "running")


def test_completion_returns_to_idle() -> None:
    busy = advance_activity(ActivitySnapshot("Idle", "idle"), "session.chat.started", {})
    out = advance_activity(busy, "session.chat.completed", {})
    assert (out.label, out.state) == ("Idle", "idle")


def test_job_failed_returns_to_idle_not_failed() -> None:
    # A background job failing is surfaced via the warn counter, not by hijacking the
    # main activity status — a successful chat turn must never render as "Failed".
    busy = advance_activity(ActivitySnapshot("Idle", "idle"), "session.chat.started", {})
    out = advance_activity(busy, "job.failed", {})
    assert (out.label, out.state) == ("Idle", "idle")


def test_boot_failed_is_failed() -> None:
    # A genuine runtime boot failure is the one case that marks the activity failed.
    out = advance_activity(ActivitySnapshot("Idle", "idle"), "boot.failed", {})
    assert (out.label, out.state) == ("Failed", "failed")


def test_usage_updates_tokens_and_cost() -> None:
    out = advance_activity(
        ActivitySnapshot("Idle", "idle"),
        "usage.updated",
        {"total_tokens": 1234, "estimated_cost_usd": 0.5},
    )
    assert out.total_tokens == 1234
    assert out.estimated_cost_usd == 0.5
    # Usage does not disturb the activity label/state.
    assert (out.label, out.state) == ("Idle", "idle")


def test_unhandled_event_returns_prev_unchanged() -> None:
    prev = ActivitySnapshot("Working…", "running")
    assert advance_activity(prev, "mcp.server.ready", {}) is prev


def test_tool_started_then_completed_resolves_recent_tool() -> None:
    idle = ActivitySnapshot("Idle", "idle")
    s1 = advance_activity(idle, "tool.call.started", {"name": "read_file"})
    assert s1.label == "Running read_file…"
    assert [(t.name, t.status) for t in s1.recent_tools] == [("read_file", "running")]

    s2 = advance_activity(s1, "tool.call.completed", {"name": "read_file", "result_preview": "ok"})
    assert [(t.name, t.status) for t in s2.recent_tools] == [("read_file", "completed")]


def test_tool_completed_error_marks_recent_tool_failed() -> None:
    s1 = advance_activity(ActivitySnapshot("Idle", "idle"), "tool.call.started", {"name": "boom"})
    s2 = advance_activity(
        s1, "tool.call.completed", {"name": "boom", "result_preview": "Traceback: kaboom"}
    )
    assert s2.recent_tools[0].status == "failed"


def test_recent_tools_resolves_most_recent_running_first() -> None:
    # The recent-tools strip resolves the most-recent running entry of a name
    # (a reversed scan), preserving the pre-refactor header behavior. This is a
    # display-strip nicety distinct from the FIFO-paired tool *timeline*.
    state = ActivitySnapshot("Idle", "idle")
    state = advance_activity(state, "tool.call.started", {"name": "t"})
    state = advance_activity(state, "tool.call.started", {"name": "t"})
    state = advance_activity(state, "tool.call.completed", {"name": "t", "result_preview": "ok"})
    statuses = [t.status for t in state.recent_tools]
    assert statuses == ["running", "completed"]


def test_recent_tools_capped_at_twelve() -> None:
    state = ActivitySnapshot("Idle", "idle")
    for _ in range(20):
        state = advance_activity(state, "tool.call.started", {"name": "t"})
    assert len(state.recent_tools) == 12


# --- store.activity() integration -----------------------------------------


def test_store_activity_reflects_latest_event() -> None:
    store = RuntimeReadModelStore()
    assert store.activity().state == "idle"
    store.append_event(_ev("session.chat.started", {}))
    assert store.activity().state == "running"
    store.append_event(_ev("tool.call.started", {"name": "grep"}))
    assert store.activity().label == "Running grep…"
    store.append_event(_ev("session.chat.completed", {}))
    assert store.activity().state == "idle"


# --- sequence numbers + read_events_since ---------------------------------


def test_sequence_numbers_are_monotonic() -> None:
    store = RuntimeReadModelStore()
    store.append_event(_ev("a.b.c", {}))
    store.append_event(_ev("d.e.f", {}))
    store.append_event(_ev("g.h.i", {}))
    seqs = [snap.sequence for snap in store.runtime_events()]
    assert seqs == [1, 2, 3]


def test_read_events_since_filters_by_sequence() -> None:
    store = RuntimeReadModelStore()
    for name in ("e1", "e2", "e3", "e4"):
        store.append_event(_ev(name, {}))

    fresh = store.read_events_since(after=2)
    assert [snap.name for snap in fresh] == ["e3", "e4"]
    assert [snap.sequence for snap in fresh] == [3, 4]


def test_read_events_since_honours_limit() -> None:
    store = RuntimeReadModelStore()
    for i in range(10):
        store.append_event(_ev(f"e{i}", {}))

    batch = store.read_events_since(after=0, limit=3)
    assert len(batch) == 3
    assert [snap.sequence for snap in batch] == [1, 2, 3]


def test_read_events_since_after_tip_is_empty() -> None:
    store = RuntimeReadModelStore()
    store.append_event(_ev("only", {}))
    assert store.read_events_since(after=1) == ()


# --- B4 trim-underflow contract -------------------------------------------
# These tests establish the correctness contract for the O(1) index
# implementation.  A naive `start = after - base + 1` (no guard) would
# silently return a wrong tail slice when `after < base_sequence` — a
# condition that arises on any trimmed buffer (>2000 events appended).


def test_read_events_since_empty_buffer_returns_empty() -> None:
    """Empty buffer must return an empty tuple without indexing errors (B4)."""
    store = RuntimeReadModelStore()
    assert store.read_events_since(after=0) == ()
    assert store.read_events_since(after=999) == ()


def test_read_events_since_on_trimmed_buffer_returns_oldest_surviving_event() -> None:
    """after=0 on a trimmed buffer must return from the oldest surviving event (B4).

    After 2001 appends the buffer trims to the last 2000 (sequences 2..2001).
    A client polling with after=0 must receive the oldest survivor (seq=2),
    NOT an out-of-bounds tail slice.
    """
    store = RuntimeReadModelStore()
    # Trigger a trim: append > 2000 events.
    for i in range(2001):
        store.append_event(_ev(f"e{i}", {}))
    # Buffer now holds events with sequences 2..2001 (oldest trimmed away).
    result = store.read_events_since(after=0, limit=5)
    assert len(result) == 5
    # The oldest surviving event has sequence 2, not 1.
    assert result[0].sequence == 2
    assert result[0].name == "e1"


def test_read_events_since_stale_after_clamps_to_oldest_surviving() -> None:
    """after far below base must not wrap to a wrong tail slice (B4 underflow guard)."""
    store = RuntimeReadModelStore()
    for i in range(2001):
        store.append_event(_ev(f"e{i}", {}))
    # Client is very stale: requests events after sequence 0 (below the trim boundary).
    result = store.read_events_since(after=0)
    # Must start from seq=2 (oldest surviving), not from end-of-buffer.
    assert result[0].sequence == 2
    # Must NOT return a tail slice (the wrong wrap behaviour would yield seq~2001).
    assert result[0].sequence < 100


def test_read_events_since_parity_with_scan_after_trim() -> None:
    """O(1) result must equal the O(N) scan reference after a trim (B4 parity)."""
    store = RuntimeReadModelStore()
    for i in range(2010):
        store.append_event(_ev(f"ev{i}", {}))
    # Spot-check a cursor in the middle of the surviving window.
    cursor = 1500  # well below trim point 2010 - 2000 + 1 = 11
    reference = tuple(s for s in store._events if s.sequence > cursor)[:100]
    result = store.read_events_since(after=cursor, limit=100)
    assert result == reference
