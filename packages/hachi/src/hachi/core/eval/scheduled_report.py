"""Scheduled failure-report generation for the eval loop.

All core logic is pure / side-effect-free so it can be unit-tested without
threads, clocks, or a real database.  The resident thread in
``orchestrator._start_eval_report_scheduler`` calls ``maybe_generate_report``
each wake cycle; all I/O decisions and state mutations happen inside that
single testable function.

Public API
----------
- :func:`render_report_markdown`         — pure EvalReport → markdown string
- :class:`ReportArtifact`                — typed result of a report run
- :func:`generate_failure_report_artifact` — write md + json files, return artifact
- :func:`due_for_report`                 — pure predicate (when is next run due?)
- :func:`read_last_report_at`            — read marker file (None if absent/corrupt)
- :func:`write_last_report_at`           — atomic marker write (temp + os.replace)
- :func:`maybe_generate_report`          — the full due-check + generate + emit unit
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hachi.core.eval.report import EvalReport, build_failure_report

# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def render_report_markdown(report: EvalReport) -> str:
    """Render an :class:`~hachi.core.eval.report.EvalReport` as a Markdown string.

    Uses only the real field names from ``EvalReport`` and its nested types.
    The output is designed to be human-readable when stored as a plain ``.md``
    file and when embedded in a notification/email.

    Args:
        report: A populated :class:`~hachi.core.eval.report.EvalReport`.

    Returns:
        A multi-section Markdown string.
    """
    lines: list[str] = []

    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = "# Hachi Weekly Failure Report"
    if report.since:
        title += f"  (since {report.since})"
    lines.append(title)
    lines.append(f"\n_Generated: {generated_at}_\n")

    # --- Summary table ---
    failure_pct = f"{report.failure_rate * 100:.1f}%"
    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Total turns | {report.total_turns} |")
    lines.append(f"| Rated up | {report.rated_up} |")
    lines.append(f"| Rated down | {report.rated_down} |")
    lines.append(f"| Unrated | {report.unrated} |")
    lines.append(f"| Failure rate (down / rated) | {failure_pct} |")
    lines.append(f"| Errored turns | {report.errored_turns} |")
    lines.append(f"| Total cost | ${report.total_cost:.4f} |")
    lines.append(f"| Avg cost / turn | ${report.avg_cost_per_turn:.4f} |")

    # --- Per-model breakdown ---
    if report.per_model:
        lines.append("\n## Per-model breakdown\n")
        lines.append("| Model | Turns | Avg cost | Rated down |")
        lines.append("| --- | --- | --- | --- |")
        for model, ms in sorted(report.per_model.items(), key=lambda kv: -kv[1].count):
            lines.append(
                f"| {model} | {ms.count} | ${ms.avg_cost:.4f} | {ms.down_count} |"
            )

    # --- Top failing tools ---
    if report.top_failing_tools:
        lines.append("\n## Top tools in down-rated turns\n")
        lines.append("| Tool | Down-turn calls |")
        lines.append("| --- | --- |")
        for tool_name, cnt in report.top_failing_tools[:10]:
            lines.append(f"| {tool_name} | {cnt} |")

    # --- Recent failures ---
    if report.recent_failures:
        lines.append("\n## Recent failures (down-rated)\n")
        for rf in report.recent_failures:
            lines.append(f"### {rf.ts[:19]}  `{rf.id[:12]}`")
            lines.append(f"- **Session:** `{rf.session_id[:12]}`")
            lines.append(f"- **User input:** {rf.user_input[:120]}")
            lines.append(f"- **Output head:** {rf.agent_output_head[:120]}")
            if rf.tool_calls:
                lines.append(f"- **Tools:** {', '.join(rf.tool_calls)}")
            if rf.notes:
                lines.append(f"- **Notes:** {rf.notes}")
            lines.append("")

    if report.total_turns == 0:
        lines.append("\n_No interaction rows found for this window._")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Artifact dataclass
# ---------------------------------------------------------------------------


@dataclass
class ReportArtifact:
    """Typed result of a completed report generation run.

    Attributes:
        markdown_path: Path to the written ``.md`` file.
        json_path:     Path to the written ``.json`` file.
        report:        The :class:`~hachi.core.eval.report.EvalReport` instance.
        generated_at:  ISO-8601 UTC timestamp string for the run.
    """

    markdown_path: Path
    json_path: Path
    report: EvalReport
    generated_at: str


# ---------------------------------------------------------------------------
# Core artifact generator
# ---------------------------------------------------------------------------


def _to_serialisable(obj: object) -> object:
    """Recursively convert dataclasses / tuples to JSON-safe types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return {k: _to_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_serialisable(i) for i in obj]
    if isinstance(obj, tuple):
        return [_to_serialisable(i) for i in obj]
    return obj


def generate_failure_report_artifact(
    store: Any,
    *,
    out_dir: Path,
    since: str | None = None,
    limit: int = 1000,
    now: datetime | None = None,
) -> ReportArtifact:
    """Generate and persist both a Markdown and JSON failure-report artifact.

    Reads rows from *store* (any object with a ``get_interactions(limit=...)``
    method), builds the report via :func:`build_failure_report`, renders it to
    Markdown and JSON, and writes both to *out_dir*.  The directory is created
    automatically (``parents=True``).

    The JSON serialisation mirrors the ``hachi eval report --json`` output:
    ``top_failing_tools`` tuples are coerced to lists, and nested dataclasses
    are converted via :func:`dataclasses.asdict`.

    Args:
        store:   Object with a ``get_interactions(limit: int) -> list[dict]``
                 method (typically a :class:`~hachi.core.session_store.SessionStore`).
        out_dir: Directory to write ``eval-report-<YYYYMMDD-HHMMSS>.md`` and
                 ``eval-report-<YYYYMMDD-HHMMSS>.json`` into.
        since:   Optional ISO-8601 filter forwarded to :func:`build_failure_report`.
        limit:   Maximum rows to load from *store*.
        now:     Override the current timestamp (UTC) for deterministic tests.
                 Defaults to :func:`datetime.now(UTC)`.

    Returns:
        A :class:`ReportArtifact` with paths + the live report object.
    """
    if now is None:
        now = datetime.now(UTC)

    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = store.get_interactions(limit=limit)
    report = build_failure_report(rows, since=since)

    stamp = now.strftime("%Y%m%d-%H%M%S")
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    md_path = out_dir / f"eval-report-{stamp}.md"
    json_path = out_dir / f"eval-report-{stamp}.json"

    # Write markdown
    md_content = render_report_markdown(report)
    md_path.write_text(md_content, encoding="utf-8")

    # Write JSON — mirror eval report --json serialisation
    d = dataclasses.asdict(report)
    d["top_failing_tools"] = [list(t) for t in report.top_failing_tools]
    json_path.write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")

    return ReportArtifact(
        markdown_path=md_path,
        json_path=json_path,
        report=report,
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Marker helpers
# ---------------------------------------------------------------------------

_MARKER_KEY = "last_report_at"


def read_last_report_at(state_path: Path) -> datetime | None:
    """Read the timestamp of the last completed report from the marker file.

    Returns ``None`` when the file is absent, empty, or contains invalid JSON /
    an unparseable timestamp — all treated as "never run".

    Args:
        state_path: Path to the ``.last_report.json`` marker file.

    Returns:
        The parsed UTC :class:`datetime`, or ``None``.
    """
    try:
        text = state_path.read_text(encoding="utf-8")
        data = json.loads(text)
        iso = data.get(_MARKER_KEY)
        if not iso:
            return None
        dt = datetime.fromisoformat(iso)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:
        return None


def write_last_report_at(state_path: Path, when: datetime) -> None:
    """Atomically write the last-report timestamp to the marker file.

    Uses a temp-file + :func:`os.replace` (atomic on POSIX; best-effort on
    Windows where the destination is replaced if it exists).

    Args:
        state_path: Path to the ``.last_report.json`` marker file.
        when:       The timestamp to persist (should be UTC-aware).
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({_MARKER_KEY: when.isoformat()})
    fd, tmp_path = tempfile.mkstemp(
        dir=state_path.parent,
        prefix=".last_report_tmp_",
        suffix=".json",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, state_path)
    except Exception:
        # Clean up temp file on failure if it still exists.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Due-for-report predicate
# ---------------------------------------------------------------------------


def due_for_report(
    last_run_at: datetime | None,
    now: datetime,
    interval_seconds: int,
) -> bool:
    """Return ``True`` if a new report should be generated.

    Args:
        last_run_at:       Timestamp of the previous run, or ``None`` (never run).
        now:               Current timestamp (UTC-aware or naive; comparison is by
                           total seconds elapsed).
        interval_seconds:  Minimum seconds between reports.

    Returns:
        ``True`` when *last_run_at* is ``None`` or when at least
        *interval_seconds* have elapsed since the last run.
    """
    if last_run_at is None:
        return True
    # Handle mixed-tz comparison: strip tz if necessary
    _now = now.replace(tzinfo=None) if now.tzinfo is not None else now
    _last = last_run_at.replace(tzinfo=None) if last_run_at.tzinfo is not None else last_run_at
    return (_now - _last).total_seconds() >= interval_seconds


# ---------------------------------------------------------------------------
# Orchestrated maybe-generate (called each resident-thread wake)
# ---------------------------------------------------------------------------


def maybe_generate_report(
    store: Any,
    *,
    out_dir: Path,
    marker_path: Path,
    interval_seconds: int,
    limit: int,
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    now: datetime | None = None,
) -> ReportArtifact | None:
    """Generate a new report if the interval has elapsed; otherwise do nothing.

    This is the single testable unit that the resident scheduler thread calls
    each wake cycle.  All logic is extracted here so it can be exercised in unit
    tests without spawning real threads or manipulating a real clock.

    Steps when *due*:
    1. Call :func:`generate_failure_report_artifact`.
    2. Write the updated marker via :func:`write_last_report_at`.
    3. Call ``emit("eval.report.generated", payload)`` if *emit* is provided.
    4. Return the :class:`ReportArtifact`.

    Args:
        store:            Object with ``get_interactions(limit=int)`` method.
        out_dir:          Directory for output files.
        marker_path:      Path to the ``.last_report.json`` marker.
        interval_seconds: Minimum interval between reports (seconds).
        limit:            Max rows to load.
        emit:             Optional callable ``(event_name, payload) -> None``.
                          Called when a new report is generated.
        now:              Override current UTC time for testing.

    Returns:
        A :class:`ReportArtifact` when a new report was generated; ``None``
        otherwise (not yet due).
    """
    if now is None:
        now = datetime.now(UTC)

    last_run_at = read_last_report_at(marker_path)
    if not due_for_report(last_run_at, now, interval_seconds):
        return None

    artifact = generate_failure_report_artifact(
        store,
        out_dir=out_dir,
        limit=limit,
        now=now,
    )
    write_last_report_at(marker_path, now)

    if emit is not None:
        emit(
            "eval.report.generated",
            {
                "markdown_path": str(artifact.markdown_path),
                "json_path": str(artifact.json_path),
                "total_turns": artifact.report.total_turns,
                "failure_rate": artifact.report.failure_rate,
                "generated_at": artifact.generated_at,
            },
        )

    return artifact
