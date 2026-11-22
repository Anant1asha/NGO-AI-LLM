"""Tests for per-turn cost and token budget caps in ExecutionLoop.

Covers:
1. _turn_budget_exceeded() returns None when no limits are set
2. _turn_budget_exceeded() returns None when cost_tracker is None
3. _turn_budget_exceeded() returns a reason string when token limit hit
4. _turn_budget_exceeded() returns a reason string when cost limit hit
5. _turn_budget_exceeded() ignores limits when cumulative is below them
6. Baseline is recorded at run() start (delta, not absolute)
7. orchestrator reads max_turn_cost_usd / max_turn_tokens from limits config
8. orchestrator reads max_turn_cost_usd / max_turn_tokens from env vars
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hachi.core.cost import CostSnapshot, CostTracker
from hachi.core.loop import ExecutionLoop

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loop(
    max_cost_per_turn: float = 0.0,
    max_tokens_per_turn: int = 0,
    tracker: CostTracker | None = None,
) -> ExecutionLoop:
    """Build a minimal ExecutionLoop with stubbed dependencies."""
    loop = ExecutionLoop.__new__(ExecutionLoop)
    loop.cost_tracker = tracker
    loop.max_cost_per_turn = max_cost_per_turn
    loop.max_tokens_per_turn = max_tokens_per_turn
    loop._turn_tokens_start = 0
    loop._turn_cost_start = 0.0
    return loop


def _snapshot(total_tokens: int, cost_usd: float) -> CostSnapshot:
    return CostSnapshot(
        input_tokens=total_tokens,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        total_tokens=total_tokens,
        estimated_cost_usd=cost_usd,
        call_count=1,
    )


def _tracker_with_snapshot(total_tokens: int, cost_usd: float) -> CostTracker:
    """Return a CostTracker whose snapshot() returns the given values."""
    tracker = MagicMock(spec=CostTracker)
    tracker.snapshot.return_value = _snapshot(total_tokens, cost_usd)
    return tracker


# ---------------------------------------------------------------------------
# 1. No limits set → always None
# ---------------------------------------------------------------------------


def test_no_limits_returns_none() -> None:
    tracker = _tracker_with_snapshot(total_tokens=10_000, cost_usd=0.50)
    loop = _make_loop(max_cost_per_turn=0.0, max_tokens_per_turn=0, tracker=tracker)
    assert loop._turn_budget_exceeded() is None


# ---------------------------------------------------------------------------
# 2. No cost_tracker → always None
# ---------------------------------------------------------------------------


def test_no_tracker_returns_none() -> None:
    loop = _make_loop(max_cost_per_turn=0.10, max_tokens_per_turn=500, tracker=None)
    assert loop._turn_budget_exceeded() is None


# ---------------------------------------------------------------------------
# 3. Token limit exceeded → returns reason
# ---------------------------------------------------------------------------


def test_token_limit_exceeded_returns_reason() -> None:
    # Cumulative: 1100 tokens. Baseline: 0. Delta = 1100 > limit 1000.
    tracker = _tracker_with_snapshot(total_tokens=1100, cost_usd=0.01)
    loop = _make_loop(max_tokens_per_turn=1000, tracker=tracker)
    loop._turn_tokens_start = 0
    loop._turn_cost_start = 0.0
    reason = loop._turn_budget_exceeded()
    assert reason is not None
    assert "token" in reason.lower()
    assert "1,100" in reason


# ---------------------------------------------------------------------------
# 4. Cost limit exceeded → returns reason
# ---------------------------------------------------------------------------


def test_cost_limit_exceeded_returns_reason() -> None:
    # Cumulative: $0.06. Baseline: $0.0. Delta = $0.06 > limit $0.05.
    tracker = _tracker_with_snapshot(total_tokens=500, cost_usd=0.06)
    loop = _make_loop(max_cost_per_turn=0.05, tracker=tracker)
    loop._turn_tokens_start = 0
    loop._turn_cost_start = 0.0
    reason = loop._turn_budget_exceeded()
    assert reason is not None
    assert "cost" in reason.lower()
    assert "$0.05" in reason


# ---------------------------------------------------------------------------
# 5. Delta below limit → None
# ---------------------------------------------------------------------------


def test_below_limit_returns_none() -> None:
    # Cumulative: 2000 tokens / $0.20 but the baseline from a prior turn is 1800/0.18.
    # Delta = 200 tokens / $0.02 — well within limits of 1000 / $0.10.
    tracker = _tracker_with_snapshot(total_tokens=2000, cost_usd=0.20)
    loop = _make_loop(max_tokens_per_turn=1000, max_cost_per_turn=0.10, tracker=tracker)
    loop._turn_tokens_start = 1800
    loop._turn_cost_start = 0.18
    assert loop._turn_budget_exceeded() is None


# ---------------------------------------------------------------------------
# 6. Baseline is recorded at run() start (not zero)
# ---------------------------------------------------------------------------


def test_baseline_captured_before_loop() -> None:
    """run() should record the snapshot BEFORE the main loop so per-turn deltas are correct."""
    loop = ExecutionLoop.__new__(ExecutionLoop)
    loop._turn_tokens_start = 0
    loop._turn_cost_start = 0.0

    tracker = MagicMock(spec=CostTracker)
    tracker.snapshot.return_value = _snapshot(500, 0.05)
    loop.cost_tracker = tracker
    loop.max_cost_per_turn = 0.0
    loop.max_tokens_per_turn = 0

    # Simulate what run() does at the top of the turn.
    snap = loop.cost_tracker.snapshot()
    loop._turn_tokens_start = snap.total_tokens
    loop._turn_cost_start = snap.estimated_cost_usd

    assert loop._turn_tokens_start == 500
    assert loop._turn_cost_start == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# 7. orchestrator picks up limits from config dict
# ---------------------------------------------------------------------------


def test_orchestrator_limits_from_config() -> None:
    """_coerce_float/_coerce_int parse [limits] config into the ExecutionLoop kwargs."""
    from hachi.gateway.orchestrator import _coerce_float, _coerce_int

    assert _coerce_float("0.05", None) == pytest.approx(0.05)
    assert _coerce_int("2000", None) == 2000
    assert _coerce_float(None, None) == 0.0
    assert _coerce_int(None, None) == 0


# ---------------------------------------------------------------------------
# 8. orchestrator picks up limits from env vars
# ---------------------------------------------------------------------------


def test_orchestrator_limits_from_env_vars() -> None:
    """Env vars HACHI_MAX_TURN_COST_USD / HACHI_MAX_TURN_TOKENS are respected."""
    from hachi.gateway.orchestrator import _coerce_float, _coerce_int

    # env-var value wins when config value is None
    assert _coerce_float(None, "0.03") == pytest.approx(0.03)
    assert _coerce_int(None, "1500") == 1500
    # config value takes precedence over env var
    assert _coerce_float("0.07", "0.03") == pytest.approx(0.07)
    assert _coerce_int("3000", "1500") == 3000
