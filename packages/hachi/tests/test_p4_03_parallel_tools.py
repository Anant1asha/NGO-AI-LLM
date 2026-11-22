"""P4-03: Parallel tool execution inside ExecutionLoop.

Tests:
  1. ExecutionLoop has a _tool_pool ThreadPoolExecutor.
  2. _execute_single_tool returns (result, False, None) on success.
  3. _execute_single_tool catches SuspendWorkflow and returns it as third element.
  4. _execute_single_tool catches generic exceptions and sets is_error=True.
  5. Multiple tool calls in a batch execute concurrently (wall-clock ≈ max, not sum).
  6. Results are returned in original tool_call order.
  7. shutdown() does not raise.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loop():
    """Build a minimal ExecutionLoop without wiring up real LLM/memory."""
    from hachi.core.loop import ExecutionLoop

    loop = ExecutionLoop.__new__(ExecutionLoop)
    # Minimal wiring so the methods under test work without a full bootstrap.
    loop.registry = MagicMock()
    loop.on_event = lambda *a, **kw: None
    loop.skill_engine = None
    loop.memory = MagicMock()
    loop.memory.active_skill = "core"
    loop._active_groups = set()
    import concurrent.futures

    loop._tool_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=4, thread_name_prefix="test-pool"
    )
    return loop


def _make_tool_call(name: str, call_id: str = "tc1", input_data: dict | None = None):
    tc = MagicMock()
    tc.name = name
    tc.id = call_id
    tc.input = input_data or {}
    return tc


# ---------------------------------------------------------------------------
# 1. ExecutionLoop has a _tool_pool ThreadPoolExecutor
# ---------------------------------------------------------------------------


def test_execution_loop_has_tool_pool() -> None:
    import concurrent.futures

    loop = _make_loop()
    assert isinstance(loop._tool_pool, concurrent.futures.ThreadPoolExecutor)


# ---------------------------------------------------------------------------
# 2. _execute_single_tool returns (result, False, None) on success
# ---------------------------------------------------------------------------


def test_execute_single_tool_success() -> None:
    loop = _make_loop()
    loop.registry.execute.return_value = "weather: sunny"

    tc = _make_tool_call("get_weather")
    result, is_error, suspend = loop._execute_single_tool(tc)

    assert result == "weather: sunny"
    assert is_error is False
    assert suspend is None


# ---------------------------------------------------------------------------
# 3. _execute_single_tool catches SuspendWorkflow as third return value
# ---------------------------------------------------------------------------


def test_execute_single_tool_suspend() -> None:
    from hachi.core.loop import SuspendWorkflow

    loop = _make_loop()
    loop.registry.execute.side_effect = SuspendWorkflow("pause requested")

    tc = _make_tool_call("core_suspend_workflow")
    result, is_error, suspend = loop._execute_single_tool(tc)

    assert result is None
    assert is_error is False
    assert suspend is not None
    assert suspend.reason == "pause requested"


# ---------------------------------------------------------------------------
# 4. _execute_single_tool catches generic exceptions → is_error=True
# ---------------------------------------------------------------------------


def test_execute_single_tool_error() -> None:
    loop = _make_loop()
    loop.registry.execute.side_effect = RuntimeError("network timeout")

    tc = _make_tool_call("browse_web")
    result, is_error, suspend = loop._execute_single_tool(tc)

    assert "Tool Execution Error" in str(result)
    assert is_error is True
    assert suspend is None


def test_execute_single_tool_error_preserves_traceback_in_log(caplog) -> None:
    """The original exception + traceback must reach the logs (not just the
    stringified message returned to the model), so operators can debug the
    real failure instead of only seeing "Tool Execution Error: ...".
    """
    import logging

    loop = _make_loop()
    loop.registry.execute.side_effect = RuntimeError("network timeout")

    tc = _make_tool_call("browse_web")
    with caplog.at_level(logging.ERROR, logger="hachi.core.loop"):
        loop._execute_single_tool(tc)

    assert len(caplog.records) >= 1
    record = caplog.records[-1]
    assert "browse_web" in record.getMessage()
    # exc_info must be attached so the traceback (not just str(exc)) is preserved.
    assert record.exc_info is not None
    assert record.exc_info[1] is not None
    assert isinstance(record.exc_info[1], RuntimeError)
    assert record.exc_info[2] is not None, "traceback must be preserved, not discarded"


# ---------------------------------------------------------------------------
# 5. Multiple tool calls run concurrently (wall-clock ≈ max, not sum)
# ---------------------------------------------------------------------------


def test_parallel_execution_is_faster_than_sequential() -> None:
    """Submit 3 tools each sleeping 0.1s — concurrent = ~0.1s, sequential = ~0.3s."""

    loop = _make_loop()
    DELAY = 0.10  # seconds per tool

    def _slow_tool(tc):
        time.sleep(DELAY)
        return "done"

    loop.registry.execute.side_effect = _slow_tool

    tcs = [_make_tool_call(f"tool_{i}", f"id_{i}") for i in range(3)]
    start = time.monotonic()
    futures = {tc.id: loop._tool_pool.submit(loop._execute_single_tool, tc) for tc in tcs}
    results = [futures[tc.id].result() for tc in tcs]
    elapsed = time.monotonic() - start

    assert all(r[0] == "done" for r in results), "All results should succeed"
    assert elapsed < DELAY * len(tcs) * 0.8, (
        f"Expected <{DELAY * len(tcs) * 0.8:.2f}s (concurrent), got {elapsed:.2f}s"
    )


# ---------------------------------------------------------------------------
# 6. Results are in original tool_call order
# ---------------------------------------------------------------------------


def test_results_maintain_original_order() -> None:
    """Results should come back indexed by original call order, not completion order."""

    loop = _make_loop()
    delays = [0.05, 0.01, 0.03]  # second tool finishes first

    def _tool_with_delay(tc):
        i = int(tc.name.split("_")[1])
        time.sleep(delays[i])
        return f"result_{i}"

    loop.registry.execute.side_effect = _tool_with_delay

    tcs = [_make_tool_call(f"tool_{i}", f"id_{i}") for i in range(3)]
    futures_map = {tc.id: loop._tool_pool.submit(loop._execute_single_tool, tc) for tc in tcs}
    ordered = [futures_map[tc.id].result()[0] for tc in tcs]

    assert ordered == ["result_0", "result_1", "result_2"], (
        f"Order must match original tool_calls order: {ordered}"
    )


# ---------------------------------------------------------------------------
# 7. shutdown() does not raise
# ---------------------------------------------------------------------------


def test_shutdown_does_not_raise() -> None:
    loop = _make_loop()
    loop.shutdown(wait=True)


# ---------------------------------------------------------------------------
# 8. Dead code: _generate_with_retry was superseded by _stream_generate
# (P1-2, docs/DECISIONS.md) and run() no longer calls it. It must not linger
# unreferenced in ExecutionLoop.
# ---------------------------------------------------------------------------


def test_generate_with_retry_removed_as_dead_code() -> None:
    from hachi.core.loop import ExecutionLoop

    assert not hasattr(ExecutionLoop, "_generate_with_retry"), (
        "_generate_with_retry is dead code (superseded by _stream_generate) "
        "and must be deleted, not left unreferenced"
    )
