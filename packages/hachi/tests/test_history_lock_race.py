"""Regression test for H1 (docs/audit/2026-07-03 PRODUCTION_READINESS.md §4):

``_history`` was mutated/read without consistently holding ``_history_lock``.
``_sliding_window_compact`` took the lock around its ``self._history = ...``
reassignment, but ``apply_pending_compaction`` performed the *exact same shape*
of read-then-reassign (``self._history = [...] + self._history[boundary:]``)
with **no lock at all**. If a background compaction path
(``_sliding_window_compact``, triggered from ``add_message`` on a live turn)
and a deferred skill-switch compaction (``apply_pending_compaction``, meant to
run "between turns") ever executed concurrently -- e.g. a slow background
summary job still finishing its own locked reassignment while the next turn's
``prepare_for_turn()`` calls ``apply_pending_compaction()`` on the main
thread -- the two reassignments race with no mutual exclusion. Since both
replace ``self._history`` wholesale (last-writer-wins on the list reference,
not a merge), whichever reassignment lands second silently discards the other
one's compaction, which can drop a live tool_use/tool_result pair that the
*other* thread had already retained.

This test forces that exact interleaving deterministically (rather than
relying on timing luck) using a threading.Event pause inside
``apply_pending_compaction``.
"""

from __future__ import annotations

import threading
from typing import Any

import hachi.core.memory as memory_module
from hachi.core.llm import Message
from hachi.core.memory import MemoryManager


def _make_tool_pair(call_id: str) -> tuple[Message, Message]:
    """Build a tool_use/tool_result message pair with a given id."""
    tool_use_msg = Message(
        role="assistant",
        content=[{"type": "tool_use", "id": call_id, "name": "read_file", "input": {}}],
    )
    tool_result_msg = Message(
        role="user",
        content=[{"type": "tool_result", "tool_use_id": call_id, "content": "ok"}],
    )
    return tool_use_msg, tool_result_msg


def test_concurrent_apply_pending_compaction_and_sliding_window_compact_dont_clobber(
    monkeypatch: Any,
) -> None:
    """apply_pending_compaction() racing _sliding_window_compact() must not lose
    a tool_use/tool_result pair that the other thread already retained.

    Both methods replace ``self._history`` wholesale
    (``self._history = <new list>``). Forces ``apply_pending_compaction`` to
    pause mid-critical-section (after it has read the boundary/old messages,
    before it reassigns ``self._history``) so ``_sliding_window_compact`` can
    run to completion -- including its OWN locked reassignment -- on another
    thread in that window. When ``apply_pending_compaction`` resumes and
    reassigns from its now-stale trailing slice, it must not discard the
    tool_use/tool_result pair that ``_sliding_window_compact`` already
    retained in its own (later, but concurrently-run) reassignment.
    """
    mm = MemoryManager(max_active_messages=6, job_queue=None)

    # Seed a first "turn" for the deferred skill-switch compaction.
    mm._history.append(Message(role="user", content="do task A"))
    mm._history.append(Message(role="assistant", content="done with A"))
    mm.signal_skill_switch("skill-a")  # first call just sets active_skill
    mm._history.append(Message(role="user", content="do task B"))
    mm.signal_skill_switch("skill-b")  # arms pending compaction

    assert mm._pending_compaction is True

    # Now append a live tool_use/tool_result pair -- this is the turn that
    # must survive both compactions running concurrently.
    tool_use_msg, tool_result_msg = _make_tool_pair("call_123")
    mm._history.append(tool_use_msg)
    mm._history.append(tool_result_msg)
    # Two more messages push us over max_active_messages=6 (len becomes 7),
    # so _sliding_window_compact() actually has work to do.
    mm._history.append(Message(role="user", content="do task C"))
    mm._history.append(Message(role="assistant", content="done with C"))

    assert len(mm._history) == 7

    resume_apply_pending = threading.Event()
    paused_once = threading.Event()
    real_message_cls = memory_module.Message

    def _pausing_message(*args: Any, **kwargs: Any) -> Message:
        # apply_pending_compaction() constructs its two checkpoint Message()
        # objects right before reassigning self._history. Pause there, once,
        # so _sliding_window_compact can run concurrently (on another thread)
        # in the gap.
        if not paused_once.is_set():
            paused_once.set()
            resume_apply_pending.wait(timeout=5)
        return real_message_cls(*args, **kwargs)

    monkeypatch.setattr(memory_module, "Message", _pausing_message)

    apply_result: dict[str, bool] = {}

    def _run_apply_pending() -> None:
        apply_result["applied"] = mm.apply_pending_compaction()

    apply_worker = threading.Thread(target=_run_apply_pending)
    apply_worker.start()

    paused_once.wait(timeout=5)

    # While apply_pending_compaction is paused mid-critical-section, run the
    # real _sliding_window_compact() on its OWN thread. This mirrors
    # add_message() triggering compaction on a live turn while the deferred
    # skill-switch compaction is still in flight from a prior turn. It must
    # run on a separate thread (not the test's main thread) because with the
    # fix in place _sliding_window_compact blocks on the same _history_lock
    # apply_pending_compaction is holding -- if this were called inline here,
    # the main thread would never reach resume_apply_pending.set() below,
    # deadlocking the test itself.
    compact_worker = threading.Thread(target=mm._sliding_window_compact)
    compact_worker.start()

    # Give the compaction thread a brief window to reach (and block on)
    # _history_lock before we release the paused apply_pending_compaction --
    # this maximizes the chance both critical sections are genuinely
    # contending for the lock at the same time.
    compact_worker.join(timeout=0.2)

    resume_apply_pending.set()
    apply_worker.join(timeout=5)
    compact_worker.join(timeout=5)
    assert not apply_worker.is_alive(), "apply_pending_compaction worker thread did not finish"
    assert not compact_worker.is_alive(), "_sliding_window_compact worker thread did not finish"
    assert apply_result.get("applied") is True

    history = mm.history

    tool_use_ids = {
        block["id"]
        for msg in history
        if isinstance(msg.content, list)
        for block in msg.content
        if isinstance(block, dict) and block.get("type") == "tool_use"
    }
    tool_result_ids = {
        block["tool_use_id"]
        for msg in history
        if isinstance(msg.content, list)
        for block in msg.content
        if isinstance(block, dict) and block.get("type") == "tool_result"
    }

    # The tool_use/tool_result pair retained by _sliding_window_compact()
    # must not have been silently discarded by apply_pending_compaction()'s
    # racing reassignment (built from a stale pre-compaction snapshot), and
    # must not be split (only one side surviving) across the two competing
    # history rebuilds.
    assert "call_123" in tool_use_ids, (
        "tool_use retained by _sliding_window_compact was lost when "
        "apply_pending_compaction reassigned _history concurrently without "
        "sharing _history_lock"
    )
    assert "call_123" in tool_result_ids, (
        "tool_result retained by _sliding_window_compact was lost -- torn "
        "tool_use/tool_result pair caused by the two racing reassignments"
    )
