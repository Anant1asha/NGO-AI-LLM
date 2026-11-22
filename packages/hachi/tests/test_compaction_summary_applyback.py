"""Tests for P1-6: apply compaction summary back into live history.

Verifies:
  1. After compaction enqueues the background summary job, running the job
     replaces the placeholder checkpoint in _history with the real summary
     (sentinel gone, real text present).
  2. If the placeholder was removed before the job runs (e.g. re-compaction),
     the job is a no-op — no raise, no stray append.
  3. The synchronous (no-queue) path still produces the real summary inline,
     unchanged by this fix.
  4. _apply_summary_to_history replaces content in-place on the same Message
     object that is still referenced by _history.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from hachi.core.llm import Message
from hachi.core.memory import MemoryManager
from hachi.jobs.queue import InMemoryJobQueue, JobWorker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REAL_SUMMARY = (
    "## Active Task\nImplement the compaction apply-back.\n\n"
    "## Completed Actions\n1. Wrote _apply_summary_to_history\n\n"
    "## Active State\nbranch=reassess, tests green"
)
_PLACEHOLDER_SENTINEL = MemoryManager._COMPACTION_PLACEHOLDER_SENTINEL


class _FakeLLMClient:
    """Returns a canned real summary without hitting the network."""

    def __init__(self, summary: str = _REAL_SUMMARY) -> None:
        self._summary = summary
        self.call_count = 0

    def generate(self, messages: list, **kwargs: Any) -> Any:  # noqa: ANN001
        self.call_count += 1
        response = MagicMock()
        response.content = self._summary
        response.tool_calls = []
        return response


def _make_messages(n: int) -> list[Message]:
    """Create a simple alternating user/assistant history of length n."""
    msgs: list[Message] = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(Message(role=role, content=f"message {i}"))
    return msgs


def _build_mm_and_trigger(
    fake_client: _FakeLLMClient | None = None,
    max_active_messages: int = 8,
) -> tuple[MemoryManager, InMemoryJobQueue]:
    """Create a MemoryManager with a queue, fill history, and trigger compaction."""
    if fake_client is None:
        fake_client = _FakeLLMClient()
    queue = InMemoryJobQueue()
    mm = MemoryManager(
        max_active_messages=max_active_messages,
        job_queue=queue,
        llm_client=fake_client,
    )
    for m in _make_messages(max_active_messages + 4):
        mm._history.append(m)
    mm._sliding_window_compact()
    return mm, queue


# ---------------------------------------------------------------------------
# Test 1: placeholder is replaced by the real summary after job runs
# ---------------------------------------------------------------------------


def test_background_job_replaces_placeholder_with_real_summary() -> None:
    """Running the background summary job must replace the placeholder checkpoint.

    After _sliding_window_compact() the history contains a checkpoint whose
    content includes the _COMPACTION_PLACEHOLDER_SENTINEL.  After the job worker
    drains the queue, that checkpoint must contain the real summary text, and the
    sentinel must be gone.
    """
    fake_client = _FakeLLMClient(summary=_REAL_SUMMARY)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        mm, queue = _build_mm_and_trigger(fake_client)

        # Placeholder is present before the job runs.
        checkpoint_before = next(
            (
                m
                for m in mm._history
                if isinstance(m.content, str) and _PLACEHOLDER_SENTINEL in m.content
            ),
            None,
        )
        assert checkpoint_before is not None, (
            "No placeholder checkpoint found in _history after compaction"
        )

        # Drain the queue (runs the background summary job synchronously in test).
        worker = JobWorker(queue)
        drained = 0
        while worker.execute_one():
            drained += 1

    assert drained >= 1, "No jobs were drained"

    # The placeholder sentinel must be gone.
    sentinel_present = any(
        isinstance(m.content, str) and _PLACEHOLDER_SENTINEL in m.content for m in mm._history
    )
    assert not sentinel_present, "Placeholder sentinel still present in _history after job ran"

    # The real summary text must appear in a checkpoint message.
    real_summary_present = any(
        isinstance(m.content, str)
        and "Active Task" in m.content
        and "Completed Actions" in m.content
        for m in mm._history
    )
    assert real_summary_present, "Real summary text not found in _history after job ran"

    # The checkpoint framing must still be present.
    framing_present = any(
        isinstance(m.content, str)
        and "[CONTEXT CHECKPOINT — REFERENCE ONLY, DO NOT RESPOND TO THIS]" in m.content
        for m in mm._history
    )
    assert framing_present, "Checkpoint framing header missing after apply-back"

    # LLM was actually called (real summary, not fallback path).
    assert fake_client.call_count >= 1, "LLM client was not called — summary is fallback"


# ---------------------------------------------------------------------------
# Test 2: placeholder gone before job runs → no-op, no raise, no stray append
# ---------------------------------------------------------------------------


def test_apply_back_is_noop_when_placeholder_already_gone() -> None:
    """If the placeholder is no longer in _history, _run_and_clear_summary_job is a no-op.

    Simulates the scenario where a second compaction replaced _history before the
    background job ran.  The job must not raise and must not append a stray summary.
    """
    fake_client = _FakeLLMClient(summary=_REAL_SUMMARY)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        mm, queue = _build_mm_and_trigger(fake_client)

        # Record history length after compaction but before the job runs.
        len_before = len(mm._history)

        # Manually remove the placeholder to simulate a re-compaction that rebuilt history.
        mm._history = [
            m
            for m in mm._history
            if not (isinstance(m.content, str) and _PLACEHOLDER_SENTINEL in m.content)
        ]
        assert len(mm._history) < len_before, "Placeholder was not removed by test setup"

        len_after_removal = len(mm._history)

        # Run the job — must not raise, must not append.
        worker = JobWorker(queue)
        while worker.execute_one():
            pass

    # _history must not have grown (no stray summary appended).
    assert len(mm._history) == len_after_removal, (
        f"_history grew from {len_after_removal} to {len(mm._history)} — stray summary was appended"
    )

    # Sentinel must still be absent.
    sentinel_present = any(
        isinstance(m.content, str) and _PLACEHOLDER_SENTINEL in m.content for m in mm._history
    )
    assert not sentinel_present

    # _compaction_in_flight must be cleared (finally block ran).
    assert mm._compaction_in_flight is False


# ---------------------------------------------------------------------------
# Test 3: synchronous (no-queue) path still produces real summary inline
# ---------------------------------------------------------------------------


def test_synchronous_path_produces_real_summary_inline() -> None:
    """Without a job queue, _sliding_window_compact must embed the real summary inline.

    The no-queue path calls _generate_structured_summary synchronously and sets
    the checkpoint content directly.  No placeholder should appear.
    """
    fake_client = _FakeLLMClient(summary=_REAL_SUMMARY)
    # No job_queue — synchronous path.
    mm = MemoryManager(max_active_messages=8, job_queue=None, llm_client=fake_client)

    for m in _make_messages(12):
        mm._history.append(m)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        mm._sliding_window_compact()

    # Placeholder sentinel must NOT appear.
    sentinel_present = any(
        isinstance(m.content, str) and _PLACEHOLDER_SENTINEL in m.content for m in mm._history
    )
    assert not sentinel_present, (
        "Synchronous path should not produce placeholder — summary should be inline"
    )

    # Real summary must appear in a checkpoint.
    real_summary_present = any(
        isinstance(m.content, str) and "Active Task" in m.content for m in mm._history
    )
    assert real_summary_present, "Synchronous path did not embed real summary in checkpoint"

    # LLM was called synchronously.
    assert fake_client.call_count >= 1


# ---------------------------------------------------------------------------
# Test 4: _apply_summary_to_history replaces content in-place
# ---------------------------------------------------------------------------


def test_apply_summary_replaces_content_in_place() -> None:
    """_apply_summary_to_history must mutate the existing Message object, not rebuild _history."""
    mm = MemoryManager()  # no queue needed for this unit test

    placeholder_msg = Message(
        role="user",
        content=(
            "[CONTEXT CHECKPOINT — REFERENCE ONLY, DO NOT RESPOND TO THIS]\n"
            "[Context compacted asynchronously. "
            "Permanent facts are being flushed to Long-Term Memory in the background.]"
        ),
    )
    other_msg = Message(role="user", content="some other message")

    mm._history = [other_msg, placeholder_msg]

    # Capture the object identity of the placeholder before the call.
    original_id = id(placeholder_msg)

    mm._apply_summary_to_history(_REAL_SUMMARY)

    # The object must be the same (in-place mutation, not a new Message).
    assert id(mm._history[1]) == original_id, (
        "_apply_summary_to_history replaced the Message object instead of mutating it"
    )

    # Content must be updated.
    assert _PLACEHOLDER_SENTINEL not in mm._history[1].content
    assert "Active Task" in mm._history[1].content
    assert "[CONTEXT CHECKPOINT — REFERENCE ONLY, DO NOT RESPOND TO THIS]" in mm._history[1].content

    # Other messages must be untouched.
    assert mm._history[0].content == "some other message"
