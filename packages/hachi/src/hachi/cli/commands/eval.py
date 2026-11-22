"""Eval command group: failure-mining reports and regression-case runner.

Commands
--------
``hachi eval report``   — Query the interaction_log and print an analytics report.
``hachi eval run``      — Run the regression suite via record/replay and print a scorecard.
``hachi eval snapshot`` — Generate a failure-report artifact NOW (manual / OS-cron entry point).

Design note
-----------
``eval report`` is fully functional: it reads real rows from the default
SessionStore and builds a real EvalReport via ``build_failure_report``.

``eval run`` is a REAL, deterministic, CI-able command backed by a record/replay
harness (see ``hachi.core.eval.replay``).  It drives a production ``ExecutionLoop``
with a ``ScriptedLLMClient`` that replays pre-recorded ``LLMResponse`` objects —
no live API key required.  It exits non-zero if any case fails.

``eval snapshot`` generates a failure-report artifact immediately (bypassing the
weekly schedule) and writes it to ``state_dir/eval-reports/`` (or a custom
``--out`` directory).  Running it also resets the weekly clock so the next
automatic run is deferred by the full interval.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from hachi.core.session_store import SessionStore

eval_app = typer.Typer(help="Eval tooling: failure-mining reports and regression runner.")

console = Console()


def _open_store() -> SessionStore:
    """Open the default SessionStore using the standard Hachi paths."""
    from hachi.core.session_store import SessionStore

    # SessionStore defaults to get_hachi_paths().sessions_db when db_path is None.
    return SessionStore()


# ---------------------------------------------------------------------------
# hachi eval report
# ---------------------------------------------------------------------------


@eval_app.command("report")
def eval_report(
    as_json: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
    since: str | None = typer.Option(
        None,
        "--since",
        help="ISO timestamp (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD) — filter rows from this point.",
    ),
    session_id: str | None = typer.Option(
        None,
        "--session",
        help="Restrict report to a single session ID.",
    ),
    limit: int = typer.Option(
        500,
        "--limit",
        "-n",
        help="Maximum number of interaction rows to load (newest first).",
    ),
) -> None:
    """Build a failure-mining report over the interaction log.

    Reads rows from the default SessionStore (same DB as ``hachi session``),
    aggregates them via ``build_failure_report``, and prints a human-readable
    table (or JSON with ``--json``).

    An empty store produces a zero-valued report — not an error.

    Examples::

        hachi eval report
        hachi eval report --since 2026-06-01
        hachi eval report --session abc123 --limit 200
        hachi eval report --json
    """
    from hachi.core.eval.report import build_failure_report

    store = _open_store()
    try:
        rows = store.get_interactions(session_id=session_id, limit=limit)
    finally:
        store.shutdown()

    report = build_failure_report(rows, since=since)

    if as_json:
        # Serialise — PerModelStats has no to_dict; use dataclasses.asdict.
        import dataclasses

        def _to_serialisable(obj: object) -> object:
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return dataclasses.asdict(obj)
            if isinstance(obj, dict):
                return {k: _to_serialisable(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_to_serialisable(i) for i in obj]
            if isinstance(obj, tuple):
                return [_to_serialisable(i) for i in obj]
            return obj

        d = dataclasses.asdict(report)
        # top_failing_tools is list[tuple] — make it list[list] for JSON.
        d["top_failing_tools"] = [list(t) for t in report.top_failing_tools]
        print(json.dumps(d, indent=2, default=str))
        return

    # --- Human-readable output ---
    now = _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = f"Hachi Eval Report — {now}"
    if report.since:
        title += f"  (since {report.since})"
    if session_id:
        title += f"  [session {session_id[:12]}]"

    console.rule(title)

    # Summary table
    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")
    summary.add_row("Total turns", str(report.total_turns))
    summary.add_row("Rated up", f"[green]{report.rated_up}[/green]")
    summary.add_row("Rated down", f"[red]{report.rated_down}[/red]")
    summary.add_row("Unrated", str(report.unrated))
    failure_pct = f"{report.failure_rate * 100:.1f}%"
    failure_color = "red" if report.failure_rate > 0.1 else "green"
    rate_cell = f"[{failure_color}]{failure_pct}[/{failure_color}]"
    summary.add_row("Failure rate (down / rated)", rate_cell)
    summary.add_row("Errored turns", str(report.errored_turns))
    summary.add_row("Total cost", f"${report.total_cost:.4f}")
    summary.add_row("Avg cost / turn", f"${report.avg_cost_per_turn:.4f}")
    console.print(summary)

    # Per-model table
    if report.per_model:
        console.print()
        mtable = Table(title="Per-model breakdown", show_lines=False)
        mtable.add_column("Model")
        mtable.add_column("Turns", justify="right")
        mtable.add_column("Avg cost", justify="right")
        mtable.add_column("Rated down", justify="right")
        for model, ms in sorted(report.per_model.items(), key=lambda kv: -kv[1].count):
            mtable.add_row(
                model,
                str(ms.count),
                f"${ms.avg_cost:.4f}",
                str(ms.down_count),
            )
        console.print(mtable)

    # Top failing tools
    if report.top_failing_tools:
        console.print()
        ttable = Table(title="Top tools in down-rated turns", show_lines=False)
        ttable.add_column("Tool name")
        ttable.add_column("Down-turn calls", justify="right")
        for tool_name, cnt in report.top_failing_tools[:10]:
            ttable.add_row(tool_name, str(cnt))
        console.print(ttable)

    # Recent failures
    if report.recent_failures:
        console.print()
        ftable = Table(title="Recent failures (down-rated)", show_lines=True)
        ftable.add_column("ts", style="dim", max_width=20)
        ftable.add_column("user_input", max_width=40)
        ftable.add_column("output_head", max_width=50)
        ftable.add_column("tools")
        for rf in report.recent_failures:
            ftable.add_row(
                rf.ts[:19],
                rf.user_input[:40],
                rf.agent_output_head[:50],
                ", ".join(rf.tool_calls) or "—",
            )
        console.print(ftable)

    if report.total_turns == 0:
        console.print("[dim]No interaction rows found.[/dim]")


# ---------------------------------------------------------------------------
# hachi eval snapshot
# ---------------------------------------------------------------------------


@eval_app.command("snapshot")
def eval_snapshot(
    since: str | None = typer.Option(
        None,
        "--since",
        help="ISO timestamp (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD) — filter rows from this point.",
    ),
    limit: int = typer.Option(
        1000,
        "--limit",
        "-n",
        help="Maximum number of interaction rows to load (newest first).",
    ),
    out: str | None = typer.Option(
        None,
        "--out",
        help="Output directory for the report artifacts.  "
             "Defaults to state_dir/eval-reports/.",
    ),
) -> None:
    """Generate a failure-report artifact immediately (manual / OS-cron entry point).

    Reads the interaction_log from the default SessionStore, builds an
    :class:`~hachi.core.eval.report.EvalReport`, and writes both a Markdown
    summary and a JSON file to the output directory.  Also updates the weekly
    scheduler marker so the next automatic run is deferred by the full interval.

    Examples::

        hachi eval snapshot
        hachi eval snapshot --since 2026-06-01
        hachi eval snapshot --out /tmp/reports --limit 500
    """
    from pathlib import Path as _Path

    from hachi.core.eval.scheduled_report import (
        generate_failure_report_artifact,
        write_last_report_at,
    )
    from hachi.core.paths import get_hachi_paths

    paths = get_hachi_paths()
    out_dir = _Path(out) if out is not None else paths.state_dir / "eval-reports"

    store = _open_store()
    try:
        artifact = generate_failure_report_artifact(
            store,
            out_dir=out_dir,
            since=since,
            limit=limit,
        )
    finally:
        store.shutdown()

    # Reset the weekly clock so the resident scheduler is not triggered again
    # for a full interval after a manual snapshot.
    marker_path = out_dir / ".last_report.json"
    write_last_report_at(marker_path, _dt.datetime.now(tz=_dt.UTC))

    failure_pct = f"{artifact.report.failure_rate * 100:.1f}%"
    console.print(
        f"[green]Snapshot written[/green]  "
        f"turns={artifact.report.total_turns}  failure_rate={failure_pct}"
    )
    console.print(f"  md  → {artifact.markdown_path}")
    console.print(f"  json→ {artifact.json_path}")


# ---------------------------------------------------------------------------
# hachi eval run
# ---------------------------------------------------------------------------


@eval_app.command("run")
def eval_run(
    suite_path: str | None = typer.Option(
        None,
        "--suite",
        help="Path to a .py file defining SUITE: list[ReplayCase].  "
             "Omit to use the built-in DEFAULT_REPLAY_SUITE.",
    ),
) -> None:
    """Run the replay regression suite and print a scorecard.

    Every case is executed via a real ``ExecutionLoop`` driven by a scripted LLM
    client — no live API key required.  Assertions are checked against the REAL
    trajectory produced by running production loop code.

    Exits with code 0 when every case passes; exits with code 1 when any case
    fails (so this command can serve as a CI gate).

    Custom suites
    -------------
    Pass ``--suite path/to/my_suite.py`` where the file defines::

        SUITE: list[ReplayCase] = [...]

    Bare ``EvalCase`` objects are not directly runnable via ``eval run`` — wrap
    them in a ``ReplayCase`` with an appropriate ``llm_script``.

    JSON suites are not yet supported (use a ``.py`` file).

    Examples::

        hachi eval run
        hachi eval run --suite path/to/my_suite.py
    """
    from hachi.core.eval.corpus import DEFAULT_REPLAY_SUITE
    from hachi.core.eval.replay import ReplayCase, run_replay_suite

    # ------------------------------------------------------------------ #
    # Load suite
    # ------------------------------------------------------------------ #
    suite: list[ReplayCase]

    if suite_path is not None:
        import importlib.util
        import pathlib

        p = pathlib.Path(suite_path)
        if not p.exists():
            console.print(f"[red]Error:[/red] suite file not found: {suite_path}")
            raise typer.Exit(code=1)
        if p.suffix == ".py":
            spec = importlib.util.spec_from_file_location("_eval_suite", p)
            if spec is None or spec.loader is None:
                console.print(f"[red]Error:[/red] cannot load suite module: {suite_path}")
                raise typer.Exit(code=1)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            loaded = getattr(mod, "SUITE", None) or getattr(mod, "DEFAULT_SUITE", None)
            if loaded is None:
                console.print(
                    "[red]Error:[/red] suite .py must define SUITE or DEFAULT_SUITE "
                    "(a list[ReplayCase])."
                )
                raise typer.Exit(code=1)
            suite = loaded
        else:
            # JSON suites not yet supported — be honest rather than faking.
            console.print(
                "[yellow]JSON suite loading not yet implemented — "
                "use a .py file that defines SUITE: list[ReplayCase].[/yellow]"
            )
            raise typer.Exit(code=1)
    else:
        suite = DEFAULT_REPLAY_SUITE

    # ------------------------------------------------------------------ #
    # Run the suite via the record/replay harness
    # ------------------------------------------------------------------ #
    console.rule(f"[bold]hachi eval run[/bold] — {len(suite)} case(s)")

    results = run_replay_suite(suite)

    # ------------------------------------------------------------------ #
    # Print scorecard
    # ------------------------------------------------------------------ #
    passed_count = 0
    failed_count = 0

    for result in results:
        if result.passed:
            passed_count += 1
            status = "[bold green]PASS[/bold green]"
        else:
            failed_count += 1
            status = "[bold red]FAIL[/bold red]"

        console.print(f"  {status}  {result.name}")
        for reason in result.failures:
            console.print(f"         [dim]↳ {reason}[/dim]")

    console.rule()

    summary_color = "green" if failed_count == 0 else "red"
    console.print(
        f"[{summary_color}]{passed_count} passed / {failed_count} failed[/{summary_color}]"
        f"  out of {len(results)} total"
    )

    if failed_count > 0:
        raise typer.Exit(code=1)
