"""
G3 compaction and client-reuse tests.

Covers:
  G3-T1 / HIGH-015 — sliding-window compaction is off the hot path (no blocking LLM call
                      inside prepare_for_turn).
  G3-T1 guard       — no double-enqueue while a compaction job is already in flight.
  G3-T1 correctness — the summary job eventually runs and the flag is cleared.
  G3-T6 / MED-022   — MemoryManager._resolve_llm_client() returns the injected shared
                       client and does NOT fall back to _get_llm_client() when one is
                       supplied.

No real API calls are made; the LLM client is mocked throughout.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

from hachi.core.llm import Message
from hachi.core.memory import MemoryManager
from hachi.jobs.queue import InMemoryJobQueue, JobWorker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SlowLLMClient:
    """Mock LLM client whose generate() sleeps to simulate network latency."""

    def __init__(self, sleep_seconds: float = 2.0) -> None:
        self._sleep = sleep_seconds
        self.call_count = 0

    def generate(self, messages: list, **kwargs: Any) -> Any:  # noqa: ANN001
        self.call_count += 1
        time.sleep(self._sleep)
        response = MagicMock()
        response.content = "## Active Task\n[Mocked structured summary]"
        response.tool_calls = []
        return response


class _FastLLMClient:
    """Mock LLM client that returns immediately."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, messages: list, **kwargs: Any) -> Any:  # noqa: ANN001
        self.call_count += 1
        response = MagicMock()
        response.content = "## Active Task\n[Fast summary]"
        response.tool_calls = []
        return response


def _make_messages(n: int) -> list[Message]:
    """Create a simple alternating user/assistant history of length n."""
    msgs: list[Message] = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(Message(role=role, content=f"message {i}"))
    return msgs


def _fill_to_trigger(mm: MemoryManager, extra: int = 1) -> None:
    """Append enough messages to cross max_active_messages and trigger compaction."""
    target = mm._max_active_messages + extra
    for i in range(target):
        role = "user" if i % 2 == 0 else "assistant"
        mm._history.append(Message(role=role, content=f"filler {i}"))
    # Manually trigger sliding window (add_message checks length after append)
    mm._sliding_window_compact()


# ---------------------------------------------------------------------------
# G3-T1: prepare_for_turn() returns fast even when compaction is triggered
# ---------------------------------------------------------------------------


def test_prepare_for_turn_does_not_block_on_llm(tmp_path):
    """prepare_for_turn() must return in <100 ms even when the LLM call sleeps 2 s.

    Sliding-window compaction is triggered inside add_message() when history exceeds
    max_active_messages, so we fill the history via add_message() to trigger it, then
    measure the time of a subsequent prepare_for_turn() to confirm it's still fast.
    We also directly time _sliding_window_compact() to confirm the hot path.
    """
    slow_client = _SlowLLMClient(sleep_seconds=2.0)
    queue = InMemoryJobQueue()
    mm = MemoryManager(max_active_messages=8, job_queue=queue, llm_client=slow_client)

    # Fill history directly (bypassing the sliding window check) so we can time
    # _sliding_window_compact() itself — the actual gated function.
    msgs = _make_messages(12)
    for m in msgs:
        mm._history.append(m)

    # Time _sliding_window_compact() directly — this is the function that was blocking
    start = time.monotonic()
    mm._sliding_window_compact()
    elapsed = time.monotonic() - start

    # Must return fast (well under 100 ms when LLM is mocked to sleep 2 s)
    assert elapsed < 0.1, f"_sliding_window_compact blocked for {elapsed:.3f}s — LLM on hot path?"

    # The slow LLM must NOT have been called yet
    assert slow_client.call_count == 0, "LLM was called synchronously inside _sliding_window_compact"  # noqa: E501

    # A job must be enqueued
    pending = queue.get_pending(limit=10)
    summary_jobs = [j for j in pending if j.name == "generate_structured_summary"]
    assert summary_jobs, "No generate_structured_summary job was enqueued"

    # prepare_for_turn() must also be fast
    start2 = time.monotonic()
    mm.prepare_for_turn()
    elapsed2 = time.monotonic() - start2
    assert elapsed2 < 0.1, f"prepare_for_turn blocked for {elapsed2:.3f}s"


# ---------------------------------------------------------------------------
# G3-T1: summary is eventually applied (job runs and clears the flag)
# ---------------------------------------------------------------------------


def test_summary_job_runs_and_clears_flag(tmp_path):
    """After the background job is drained, _compaction_in_flight must be False."""
    fast_client = _FastLLMClient()
    queue = InMemoryJobQueue()
    mm = MemoryManager(max_active_messages=8, job_queue=queue, llm_client=fast_client)

    # Patch ANTHROPIC_API_KEY so client resolution succeeds
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        msgs = _make_messages(12)
        for m in msgs:
            mm._history.append(m)
        mm._sliding_window_compact()

        assert mm._compaction_in_flight is True, "_compaction_in_flight should be set after enqueue"

        # Drain the queue synchronously (run all jobs)
        worker = JobWorker(queue)
        drained = 0
        while worker.execute_one():
            drained += 1

    assert mm._compaction_in_flight is False, (
        "_compaction_in_flight not cleared after job completed"
    )
    assert drained >= 1, "No jobs were drained from the queue"


# ---------------------------------------------------------------------------
# G3-T1: no double-enqueue while a compaction job is in flight
# ---------------------------------------------------------------------------


def test_no_double_enqueue_while_compaction_in_flight():
    """A second _sliding_window_compact() call while a job is in flight must NOT enqueue again."""
    fast_client = _FastLLMClient()
    queue = InMemoryJobQueue()
    mm = MemoryManager(max_active_messages=8, job_queue=queue, llm_client=fast_client)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        msgs = _make_messages(12)
        for m in msgs:
            mm._history.append(m)

        # First compaction
        mm._sliding_window_compact()
        assert mm._compaction_in_flight is True

        # Simulate more messages arriving while the first job is still pending
        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            mm._history.append(Message(role=role, content=f"extra {i}"))

        # Second compaction call — should skip the summary job enqueue
        mm._sliding_window_compact()

    # Only one generate_structured_summary job should exist
    all_jobs = queue.get_recent_jobs(limit=50)
    summary_jobs = [j for j in all_jobs if j.name == "generate_structured_summary"]
    assert len(summary_jobs) == 1, (
        f"Expected 1 summary job but found {len(summary_jobs)} — double-enqueue occurred"
    )


# ---------------------------------------------------------------------------
# G3-T1: flag clears on job failure (no permanent lock-out)
# ---------------------------------------------------------------------------


def test_compaction_flag_clears_on_job_failure():
    """If the summary job raises, _compaction_in_flight must still be cleared."""
    failing_client = MagicMock()
    failing_client.generate.side_effect = RuntimeError("simulated LLM failure")

    queue = InMemoryJobQueue()
    mm = MemoryManager(max_active_messages=8, job_queue=queue, llm_client=failing_client)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        msgs = _make_messages(12)
        for m in msgs:
            mm._history.append(m)
        mm._sliding_window_compact()

        assert mm._compaction_in_flight is True

        # Drain — the job will fail but the flag should still clear via finally
        worker = JobWorker(queue)
        # Allow enough retries to exhaust max_retries
        for _ in range(10):
            worker.execute_one()

    # The flag must be cleared regardless of job failure
    assert mm._compaction_in_flight is False, (
        "_compaction_in_flight not cleared after job failure"
    )


# ---------------------------------------------------------------------------
# G3-T6: _resolve_llm_client() returns the injected client
# ---------------------------------------------------------------------------


def test_resolve_llm_client_prefers_injected():
    """When an llm_client is injected, _resolve_llm_client() must return it directly."""
    injected = _FastLLMClient()
    mm = MemoryManager(llm_client=injected)
    resolved = mm._resolve_llm_client()
    assert resolved is injected, "_resolve_llm_client() did not return the injected client"


def test_resolve_llm_client_falls_back_to_vault_singleton():
    """Without an injected client, _resolve_llm_client() falls back to _get_llm_client()."""
    mm = MemoryManager()  # no llm_client
    sentinel = object()
    with patch("hachi.core.memory_vault._get_llm_client", return_value=sentinel):
        resolved = mm._resolve_llm_client()
    assert resolved is sentinel, "_resolve_llm_client() did not fall back to vault singleton"


def test_background_ops_use_injected_client_not_vault_singleton():
    """Background ops must call the injected client, not memory_vault._get_llm_client()."""
    injected = _FastLLMClient()
    queue = InMemoryJobQueue()
    mm = MemoryManager(max_active_messages=8, job_queue=queue, llm_client=injected)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        # Patch _get_llm_client to a sentinel that must NOT be called
        sentinel_client = MagicMock()
        sentinel_client.generate.side_effect = AssertionError(
            "_get_llm_client() was called — shared client NOT used"
        )
        with patch("hachi.core.memory_vault._get_llm_client", return_value=sentinel_client):
            msgs = _make_messages(12)
            for m in msgs:
                mm._history.append(m)
            mm._sliding_window_compact()

            worker = JobWorker(queue)
            while worker.execute_one():
                pass

    # injected client was used (call_count > 0)
    assert injected.call_count > 0, "Injected client was never called during background job"


# ---------------------------------------------------------------------------
# G3-T1: reset() clears the compaction flag
# ---------------------------------------------------------------------------


def test_reset_clears_compaction_flag():
    """reset() must clear _compaction_in_flight so a new session starts clean."""
    mm = MemoryManager()
    mm._compaction_in_flight = True
    mm.reset()
    assert mm._compaction_in_flight is False


# ---------------------------------------------------------------------------
# queue.py WAL pragma: SQLiteJobQueue opens with WAL mode
# ---------------------------------------------------------------------------


def test_sqlite_job_queue_wal_mode(tmp_path):
    """SQLiteJobQueue must open its connection with journal_mode=WAL."""
    from hachi.jobs.queue import SQLiteJobQueue

    db = tmp_path / "test_jobs.db"
    jq = SQLiteJobQueue(db_path=db)
    try:
        # Query the journal mode directly on the same connection
        with jq._conn() as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
        mode = row[0] if row else ""
        assert mode == "wal", f"Expected WAL journal mode, got: {mode!r}"
    finally:
        jq.shutdown()
