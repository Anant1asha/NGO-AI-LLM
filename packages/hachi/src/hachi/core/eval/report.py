"""Failure-mining report built from interaction_log rows.

All logic is PURE (no I/O, no DB access, no side effects) so it is trivially
unit-testable by seeding a known list of rows and asserting exact aggregations.

Row schema (from SessionStore.get_interactions)
-----------------------------------------------
{
    id: str,
    session_id: str,
    turn_id: str,
    ts: str,                     # ISO-8601 timestamp string, e.g. "2026-06-24T10:00:00"
    user_input: str,
    agent_output: str | None,
    tool_calls: list[str|dict],  # already decoded from JSON
    memory_hits: list[str|dict], # already decoded from JSON
    model_used: str | None,
    token_cost: float | None,
    tokens: int | None,
    rating: str | None,          # "up" | "down" | None
    notes: str | None,
}

Errored-turns definition
------------------------
A turn is counted as "errored" when EITHER of the following is true:
  1. ``agent_output`` is None, empty string, or contains only whitespace.
  2. ``agent_output`` starts with one of the known error marker prefixes (case-insensitive):
     "[error]", "error:", "exception:", "traceback", "[incomplete]".

This is intentionally conservative: it catches outright failures (empty reply,
crash traces, iteration-limit markers) without over-flagging short-but-valid responses.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

# Error-marker prefixes checked against the first 80 chars of agent_output (lower-cased).
_ERROR_PREFIXES: tuple[str, ...] = (
    "[error]",
    "error:",
    "exception:",
    "traceback",
    "[incomplete]",
)


def _is_errored(row: dict[str, Any]) -> bool:
    """Return True if the row's agent_output indicates a failed/incomplete turn.

    See module docstring for the full definition.
    """
    output: str | None = row.get("agent_output")
    if not output or not output.strip():
        return True
    head = output[:80].lower()
    return any(head.startswith(prefix) for prefix in _ERROR_PREFIXES)


@dataclass
class PerModelStats:
    """Aggregated stats for a single model string."""

    count: int = 0
    total_cost: float = 0.0
    down_count: int = 0

    @property
    def avg_cost(self) -> float:
        """Average cost per turn for this model (0 when no turns)."""
        return self.total_cost / self.count if self.count else 0.0


@dataclass
class RecentFailure:
    """Compact summary of a down-rated turn for quick review."""

    id: str
    session_id: str
    ts: str
    user_input: str
    agent_output_head: str  # first 200 chars
    tool_calls: list[str]   # tool names (or raw strings) called in this turn
    notes: str | None


@dataclass
class EvalReport:
    """Aggregated analytics report over a set of interaction_log rows.

    Fields
    ------
    total_turns : int
        Total number of rows analysed (after optional ``since`` filter).
    rated_up : int
        Turns explicitly rated "up" (thumbs-up).
    rated_down : int
        Turns explicitly rated "down" (thumbs-down).
    unrated : int
        Turns with no explicit rating (neither "up" nor "down").
    failure_rate : float
        ``rated_down / (rated_up + rated_down)`` — the fraction of rated turns that
        were rated down.  ``0.0`` when no turns have been rated.
    avg_cost_per_turn : float
        Mean ``token_cost`` across all turns in the window (turns with None cost
        are excluded from the denominator).
    total_cost : float
        Sum of ``token_cost`` across all turns (None treated as 0).
    errored_turns : int
        Turns matching the "errored" definition — see module docstring.
    top_failing_tools : list[tuple[str, int]]
        Tool name → count across down-rated turns, sorted descending by count.
        Only tools from *down-rated* turns are included.
    per_model : dict[str, PerModelStats]
        Model string → :class:`PerModelStats` (count, avg_cost, down_count).
        Rows with ``model_used=None`` are bucketed under ``"(unknown)"``.
    recent_failures : list[RecentFailure]
        Compact summaries of the most recent down-rated turns, newest first.
        Capped at ``_RECENT_FAILURES_LIMIT`` entries (default 10).
    since : str | None
        The ``since`` filter applied, if any; None when no filter was used.
    """

    total_turns: int = 0
    rated_up: int = 0
    rated_down: int = 0
    unrated: int = 0
    failure_rate: float = 0.0
    avg_cost_per_turn: float = 0.0
    total_cost: float = 0.0
    errored_turns: int = 0
    top_failing_tools: list[tuple[str, int]] = field(default_factory=list)
    per_model: dict[str, PerModelStats] = field(default_factory=dict)
    recent_failures: list[RecentFailure] = field(default_factory=list)
    since: str | None = None


_RECENT_FAILURES_LIMIT = 10


def build_failure_report(
    interactions: list[dict[str, Any]],
    *,
    since: str | None = None,
) -> EvalReport:
    """Aggregate ``interaction_log`` rows into an :class:`EvalReport`.

    This is a **pure function** — it performs no I/O, no database access, and
    has no side effects.  Its correctness is entirely determined by the input
    rows, making it trivially testable.

    Args:
        interactions: Rows as returned by ``SessionStore.get_interactions()``.
                      Each row must be a dict with at least the keys documented
                      in the module docstring.  Extra keys are ignored.
        since:        Optional ISO-8601 timestamp string (``YYYY-MM-DDTHH:MM:SS``
                      or date-only ``YYYY-MM-DD``).  When provided, rows with
                      ``ts < since`` are excluded *before* all aggregation so
                      the report reflects only the requested window.

    Returns:
        A fully populated :class:`EvalReport`.  Empty input returns a zero-valued
        report (not an error) so callers can safely render an "empty store" state.
    """
    # --- Optional time filter ---
    rows = interactions
    if since is not None:
        rows = [r for r in rows if (r.get("ts") or "") >= since]

    report = EvalReport(since=since)
    report.total_turns = len(rows)

    if not rows:
        return report

    # --- Per-row aggregation ---
    failing_tool_counts: dict[str, int] = defaultdict(int)
    per_model: dict[str, PerModelStats] = defaultdict(PerModelStats)
    recent_down: list[dict[str, Any]] = []
    cost_sum: float = 0.0
    cost_count: int = 0

    for row in rows:
        rating: str | None = row.get("rating")
        if rating == "up":
            report.rated_up += 1
        elif rating == "down":
            report.rated_down += 1
        else:
            report.unrated += 1

        if _is_errored(row):
            report.errored_turns += 1

        cost: float | None = row.get("token_cost")
        if cost is not None:
            cost_sum += cost
            cost_count += 1
            report.total_cost += cost

        model: str = row.get("model_used") or "(unknown)"
        ms = per_model[model]
        ms.count += 1
        ms.total_cost += cost if cost is not None else 0.0
        if rating == "down":
            ms.down_count += 1

        # Accumulate tool names from down-rated turns only.
        if rating == "down":
            tool_calls = row.get("tool_calls") or []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name") or tc.get("tool") or str(tc)
                else:
                    name = str(tc)
                if name:
                    failing_tool_counts[name] += 1
            recent_down.append(row)

    # --- Derived metrics ---
    rated_total = report.rated_up + report.rated_down
    report.failure_rate = report.rated_down / rated_total if rated_total > 0 else 0.0
    report.avg_cost_per_turn = cost_sum / cost_count if cost_count > 0 else 0.0
    report.top_failing_tools = sorted(
        failing_tool_counts.items(), key=lambda kv: kv[1], reverse=True
    )
    report.per_model = dict(per_model)

    # Recent failures: keep newest-first (rows arrive newest-first from the store).
    for row in recent_down[:_RECENT_FAILURES_LIMIT]:
        tool_calls_raw = row.get("tool_calls") or []
        tool_names: list[str] = []
        for tc in tool_calls_raw:
            if isinstance(tc, dict):
                tool_names.append(tc.get("name") or tc.get("tool") or str(tc))
            else:
                tool_names.append(str(tc))
        report.recent_failures.append(
            RecentFailure(
                id=row.get("id") or "",
                session_id=row.get("session_id") or "",
                ts=row.get("ts") or "",
                user_input=(row.get("user_input") or "")[:200],
                agent_output_head=(row.get("agent_output") or "")[:200],
                tool_calls=tool_names,
                notes=row.get("notes"),
            )
        )

    return report
