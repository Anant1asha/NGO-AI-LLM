"""Tests for build_failure_report — exact aggregation over seeded rows.

Every test seeds a known list of rows and asserts EXACT values.  There is no
mocking, no randomness, and no I/O.  The tests fully pin the real math so any
accidental regression in the aggregation logic is caught immediately.
"""

from __future__ import annotations

from hachi.core.eval.report import _is_errored, build_failure_report

# ---------------------------------------------------------------------------
# Helpers — build minimal row dicts
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str = "r0",
    session_id: str = "s1",
    turn_id: str = "t0",
    ts: str = "2026-06-24T10:00:00",
    user_input: str = "hello",
    agent_output: str | None = "Hi there.",
    tool_calls: list = None,
    memory_hits: list = None,
    model_used: str | None = "claude-haiku-4-5",
    token_cost: float | None = 0.001,
    tokens: int | None = 100,
    rating: str | None = None,
    notes: str | None = None,
) -> dict:
    return {
        "id": id,
        "session_id": session_id,
        "turn_id": turn_id,
        "ts": ts,
        "user_input": user_input,
        "agent_output": agent_output,
        "tool_calls": tool_calls or [],
        "memory_hits": memory_hits or [],
        "model_used": model_used,
        "token_cost": token_cost,
        "tokens": tokens,
        "rating": rating,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Tests — empty input
# ---------------------------------------------------------------------------


def test_empty_input_returns_zero_report() -> None:
    """Empty interaction list → zero-valued report, no crash."""
    r = build_failure_report([])
    assert r.total_turns == 0
    assert r.rated_up == 0
    assert r.rated_down == 0
    assert r.unrated == 0
    assert r.failure_rate == 0.0
    assert r.total_cost == 0.0
    assert r.avg_cost_per_turn == 0.0
    assert r.errored_turns == 0
    assert r.top_failing_tools == []
    assert r.per_model == {}
    assert r.recent_failures == []


# ---------------------------------------------------------------------------
# Tests — rating counts and failure_rate
# ---------------------------------------------------------------------------


def test_rating_counts_exact() -> None:
    """rated_up / rated_down / unrated are counted correctly."""
    rows = [
        _row(id="r1", rating="up"),
        _row(id="r2", rating="up"),
        _row(id="r3", rating="down"),
        _row(id="r4", rating=None),
        _row(id="r5", rating="down"),
    ]
    r = build_failure_report(rows)
    assert r.total_turns == 5
    assert r.rated_up == 2
    assert r.rated_down == 2
    assert r.unrated == 1


def test_failure_rate_exact() -> None:
    """failure_rate = down / (up + down); unrated rows are excluded from denominator."""
    rows = [
        _row(id="r1", rating="up"),
        _row(id="r2", rating="down"),
        _row(id="r3", rating="down"),
        _row(id="r4", rating=None),  # unrated — does NOT affect failure_rate
    ]
    r = build_failure_report(rows)
    # 2 down / (1 up + 2 down) = 2/3 ≈ 0.6667
    assert abs(r.failure_rate - 2 / 3) < 1e-9


def test_failure_rate_zero_when_no_ratings() -> None:
    """failure_rate is 0.0 when no turns are rated (avoid ZeroDivisionError)."""
    rows = [_row(id="r1", rating=None), _row(id="r2", rating=None)]
    r = build_failure_report(rows)
    assert r.failure_rate == 0.0


def test_failure_rate_zero_when_all_up() -> None:
    """failure_rate is 0.0 when all rated turns are up."""
    rows = [_row(id="r1", rating="up"), _row(id="r2", rating="up")]
    r = build_failure_report(rows)
    assert r.failure_rate == 0.0


def test_failure_rate_one_when_all_down() -> None:
    """failure_rate is 1.0 when every rated turn is down."""
    rows = [_row(id="r1", rating="down"), _row(id="r2", rating="down")]
    r = build_failure_report(rows)
    assert r.failure_rate == 1.0


# ---------------------------------------------------------------------------
# Tests — cost aggregation
# ---------------------------------------------------------------------------


def test_cost_aggregation() -> None:
    """total_cost and avg_cost_per_turn are computed correctly."""
    rows = [
        _row(id="r1", token_cost=0.002),
        _row(id="r2", token_cost=0.004),
        _row(id="r3", token_cost=None),  # excluded from avg denominator
    ]
    r = build_failure_report(rows)
    assert abs(r.total_cost - 0.006) < 1e-9
    # avg over 2 rows with known cost
    assert abs(r.avg_cost_per_turn - 0.003) < 1e-9


def test_all_none_cost() -> None:
    """avg_cost_per_turn is 0.0 when no rows have a known cost (no ZeroDivisionError)."""
    rows = [_row(id="r1", token_cost=None), _row(id="r2", token_cost=None)]
    r = build_failure_report(rows)
    assert r.avg_cost_per_turn == 0.0
    assert r.total_cost == 0.0


# ---------------------------------------------------------------------------
# Tests — errored_turns rule
# ---------------------------------------------------------------------------


def test_errored_turns_empty_output() -> None:
    """Turns with None or empty/whitespace agent_output are counted as errored."""
    rows = [
        _row(id="r1", agent_output=None),
        _row(id="r2", agent_output=""),
        _row(id="r3", agent_output="   "),
        _row(id="r4", agent_output="normal reply"),
    ]
    r = build_failure_report(rows)
    assert r.errored_turns == 3


def test_errored_turns_error_prefix() -> None:
    """Turns whose output starts with a known error prefix are counted as errored."""
    rows = [
        _row(id="r1", agent_output="[error] something went wrong"),
        _row(id="r2", agent_output="Error: bad input"),
        _row(id="r3", agent_output="Exception: TypeError"),
        _row(id="r4", agent_output="Traceback (most recent call last):"),
        _row(id="r5", agent_output="[INCOMPLETE] reached iteration limit"),
        _row(id="r6", agent_output="This is a normal reply."),
    ]
    r = build_failure_report(rows)
    assert r.errored_turns == 5  # r6 is normal


def test_is_errored_helper_case_insensitive() -> None:
    """_is_errored is case-insensitive for prefix matching."""
    assert _is_errored({"agent_output": "ERROR: oops"})
    assert _is_errored({"agent_output": "[Error] bad"})
    assert _is_errored({"agent_output": "TRACEBACK ..."})
    assert not _is_errored({"agent_output": "The error was minor."})
    assert not _is_errored({"agent_output": "Everything is fine."})


# ---------------------------------------------------------------------------
# Tests — top_failing_tools (only from down-rated turns)
# ---------------------------------------------------------------------------


def test_top_failing_tools_counts_and_order() -> None:
    """top_failing_tools counts tool names from down-rated turns, sorted desc."""
    rows = [
        _row(
            id="r1",
            rating="down",
            tool_calls=[{"name": "search"}, {"name": "read_file"}],
        ),
        _row(
            id="r2",
            rating="down",
            tool_calls=[{"name": "search"}, {"name": "search"}],
        ),
        _row(
            id="r3",
            rating="up",
            tool_calls=[{"name": "read_file"}, {"name": "read_file"}],  # up — excluded
        ),
        _row(
            id="r4",
            rating="down",
            tool_calls=[{"name": "write_file"}],
        ),
    ]
    r = build_failure_report(rows)
    # search: 3 (r1=1, r2=2), read_file: 1 (r1), write_file: 1 (r4)
    by_name = dict(r.top_failing_tools)
    assert by_name["search"] == 3
    assert by_name["read_file"] == 1
    assert by_name["write_file"] == 1
    # sorted descending — search must come first
    assert r.top_failing_tools[0][0] == "search"
    assert r.top_failing_tools[0][1] == 3


def test_top_failing_tools_excludes_up_turns() -> None:
    """Tool calls from up-rated turns NEVER appear in top_failing_tools."""
    rows = [
        _row(id="r1", rating="up", tool_calls=[{"name": "expensive_tool"}]),
        _row(id="r2", rating="up", tool_calls=[{"name": "expensive_tool"}]),
    ]
    r = build_failure_report(rows)
    assert r.top_failing_tools == []


def test_top_failing_tools_string_tool_calls() -> None:
    """Raw string entries in tool_calls (not dicts) are handled gracefully."""
    rows = [
        _row(id="r1", rating="down", tool_calls=["search", "read_file"]),
    ]
    r = build_failure_report(rows)
    by_name = dict(r.top_failing_tools)
    assert by_name["search"] == 1
    assert by_name["read_file"] == 1


# ---------------------------------------------------------------------------
# Tests — per_model
# ---------------------------------------------------------------------------


def test_per_model_count_and_avg_cost() -> None:
    """per_model groups rows by model_used and computes correct stats."""
    rows = [
        _row(id="r1", model_used="haiku", token_cost=0.002, rating="up"),
        _row(id="r2", model_used="haiku", token_cost=0.004, rating="down"),
        _row(id="r3", model_used="sonnet", token_cost=0.010, rating=None),
    ]
    r = build_failure_report(rows)
    haiku = r.per_model["haiku"]
    assert haiku.count == 2
    assert abs(haiku.total_cost - 0.006) < 1e-9
    assert abs(haiku.avg_cost - 0.003) < 1e-9
    assert haiku.down_count == 1

    sonnet = r.per_model["sonnet"]
    assert sonnet.count == 1
    assert abs(sonnet.total_cost - 0.010) < 1e-9
    assert sonnet.down_count == 0


def test_per_model_none_bucketed_as_unknown() -> None:
    """Rows with model_used=None are bucketed under '(unknown)'."""
    rows = [_row(id="r1", model_used=None)]
    r = build_failure_report(rows)
    assert "(unknown)" in r.per_model
    assert r.per_model["(unknown)"].count == 1


# ---------------------------------------------------------------------------
# Tests — since filter
# ---------------------------------------------------------------------------


def test_since_filter_excludes_older_rows() -> None:
    """Only rows with ts >= since are included in the report."""
    rows = [
        _row(id="r1", ts="2026-06-20T00:00:00", rating="down"),
        _row(id="r2", ts="2026-06-22T00:00:00", rating="up"),
        _row(id="r3", ts="2026-06-24T00:00:00", rating="down"),
    ]
    r = build_failure_report(rows, since="2026-06-22")
    assert r.total_turns == 2          # r2 and r3
    assert r.rated_up == 1             # r2
    assert r.rated_down == 1           # r3
    assert r.since == "2026-06-22"


def test_since_filter_all_excluded() -> None:
    """since in the future → zero-valued report."""
    rows = [_row(id="r1", ts="2026-06-01T00:00:00", rating="down")]
    r = build_failure_report(rows, since="2030-01-01")
    assert r.total_turns == 0
    assert r.failure_rate == 0.0


def test_since_none_includes_all_rows() -> None:
    """since=None does not filter anything."""
    rows = [_row(id=f"r{i}", ts=f"2026-0{i+1}-01T00:00:00") for i in range(3)]
    r = build_failure_report(rows, since=None)
    assert r.total_turns == 3
    assert r.since is None


# ---------------------------------------------------------------------------
# Tests — recent_failures shape and cap
# ---------------------------------------------------------------------------


def test_recent_failures_appear_for_down_rows() -> None:
    """recent_failures contains a summary for each down-rated turn."""
    rows = [
        _row(
            id="rfail1",
            rating="down",
            user_input="bad query",
            agent_output="[error] crash",
            tool_calls=[{"name": "search"}],
            notes="regression",
        ),
        _row(id="rok1", rating="up"),
    ]
    r = build_failure_report(rows)
    assert len(r.recent_failures) == 1
    rf = r.recent_failures[0]
    assert rf.id == "rfail1"
    assert "bad query" in rf.user_input
    assert rf.tool_calls == ["search"]
    assert rf.notes == "regression"


def test_recent_failures_capped_at_10() -> None:
    """recent_failures is capped at 10 entries regardless of down-rated count."""
    rows = [_row(id=f"r{i}", rating="down") for i in range(15)]
    r = build_failure_report(rows)
    assert len(r.recent_failures) == 10


def test_recent_failures_empty_for_no_down_turns() -> None:
    """recent_failures is empty when no turns are rated down."""
    rows = [_row(id="r1", rating="up"), _row(id="r2", rating=None)]
    r = build_failure_report(rows)
    assert r.recent_failures == []
