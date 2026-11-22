"""Jobs command group: inspect and manage the durable background job queue."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

console = Console()

jobs_app = typer.Typer(help="Manage the durable background job queue.")


def _open_queue():  # type: ignore[return]
    """Open the default SQLiteJobQueue using standard platform paths."""
    from pathlib import Path

    from platformdirs import PlatformDirs

    from hachi.jobs.queue import SQLiteJobQueue

    # The queue DB lives under the user state dir (not the config dir).
    dirs = PlatformDirs("hachi", "opengigantic")
    db_path = Path(dirs.user_state_dir) / "jobs.db"
    return SQLiteJobQueue(db_path=db_path)


@jobs_app.command("dead-letter")
def jobs_dead_letter(
    limit: int = typer.Option(50, "--limit", "-n", help="Max number of jobs to show."),
    as_json: bool = typer.Option(False, "--json", help="Emit results as JSON."),
) -> None:
    """List jobs in the dead-letter queue (retry-exhausted, awaiting re-drive).

    These jobs failed on every attempt but have a registered handler, so they
    can be recovered with ``hachi jobs redrive``.
    """
    from hachi.jobs.queue import JobStatus

    q = _open_queue()
    try:
        with q._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY completed_at DESC
                LIMIT ?
                """,
                (JobStatus.DEAD_LETTER.value, limit),
            ).fetchall()
        jobs = [q._row_to_job(r) for r in rows]
    finally:
        q.shutdown()

    if as_json:
        print(json.dumps([j.to_dict() for j in jobs], indent=2))
        return

    if not jobs:
        console.print("[dim]No dead-letter jobs.[/dim]")
        return

    table = Table(title=f"Dead-letter jobs ({len(jobs)})", show_lines=False)
    table.add_column("job_id", style="dim", max_width=12)
    table.add_column("name")
    table.add_column("handler")
    table.add_column("attempts", justify="right")
    table.add_column("error", max_width=60)
    table.add_column("completed_at", style="dim")

    for j in jobs:
        err = ""
        if j.result and j.result.error:
            err = j.result.error[:80]
        table.add_row(
            j.job_id[:12],
            j.name,
            j.handler_name or "[dim]—[/dim]",
            str(j.attempt),
            err,
            (j.completed_at or "")[:19],
        )

    console.print(table)


@jobs_app.command("redrive")
def jobs_redrive(
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
) -> None:
    """Re-drive all dead-letter jobs: reset them to PENDING so they run again.

    Each job's attempt counter is reset to 0, giving it a full set of retries.
    Use ``hachi jobs dead-letter`` first to review what will be re-driven.
    """
    q = _open_queue()
    try:
        count = q.redrive_dead_letter()
    finally:
        q.shutdown()

    if as_json:
        print(json.dumps({"redriven": count}))
        return

    if count == 0:
        console.print("[dim]No dead-letter jobs to re-drive.[/dim]")
    else:
        console.print(
            f"[green]Re-drove {count} dead-letter job(s)[/green] → status reset to PENDING."
        )
