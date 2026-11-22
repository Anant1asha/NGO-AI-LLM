"""Schedule command group: manage proactive scheduled tasks."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from hachi.core.paths import get_hachi_paths
from hachi.gateway.orchestrator import boot_agent
from hachi.jobs.scheduler import Scheduler, ScheduleStore

console = Console()

schedule_app = typer.Typer(help="Manage proactive scheduled tasks (cron / interval / once).")


def _get_scheduler() -> Scheduler:
    return Scheduler(ScheduleStore(get_hachi_paths().schedules_file))


@schedule_app.command("add")
def schedule_add(
    name: str = typer.Argument(..., help="Short name for the schedule."),
    task: str = typer.Argument(..., help="Instruction the agent runs when it fires."),
    cron: str | None = typer.Option(None, "--cron", help="5-field cron, e.g. '0 9 * * 1-5'."),
    every: int | None = typer.Option(None, "--every", help="Interval in seconds."),
    at: str | None = typer.Option(None, "--at", help="One-shot ISO datetime (UTC)."),
    deliver_to: str = typer.Option("chat", "--deliver-to", help="chat | webhook | log."),
    webhook_url: str | None = typer.Option(None, "--webhook-url", help="Webhook URL."),
):
    """Add a proactive schedule. Provide exactly one of --cron / --every / --at."""
    chosen = [("cron", cron), ("interval", every), ("once", at)]
    selected = [(k, v) for k, v in chosen if v is not None]
    if len(selected) != 1:
        console.print("[red]Provide exactly one of --cron, --every, or --at.[/red]")
        raise typer.Exit(2)
    kind = selected[0][0]
    scheduler = _get_scheduler()
    try:
        schedule = scheduler.add(
            name=name,
            task=task,
            kind=kind,
            cron=cron,
            interval_seconds=every,
            run_at=at,
            deliver_to=deliver_to,
            webhook_url=webhook_url,
        )
    except ValueError as e:
        console.print(f"[red]Invalid schedule:[/red] {e}")
        raise typer.Exit(2) from e
    console.print(
        f"[green]Scheduled[/green] '{schedule.name}' ({kind}) — id {schedule.schedule_id}\n"
        f"Next run: {schedule.next_run}"
    )


@schedule_app.command("list")
def schedule_list():
    """List all configured schedules."""
    schedules = _get_scheduler().list_schedules()
    if not schedules:
        console.print("[dim]No schedules configured.[/dim]")
        return
    for s in schedules:
        state = "enabled" if s.enabled else "disabled"
        console.print(
            f"[bold]{s.name}[/bold] \\[{s.kind.value}, {state}] id={s.schedule_id}\n"
            f"  task: {s.task}\n  next_run: {s.next_run}  runs: {s.run_count}"
        )


@schedule_app.command("show")
def schedule_show(
    schedule_id: str = typer.Argument(..., help="Schedule ID (or unique prefix) to inspect."),
    as_json: bool = typer.Option(False, "--json", help="Emit full details as JSON."),
) -> None:
    """Show full details for a single schedule."""
    schedule = _get_scheduler().get(schedule_id)
    if schedule is None:
        console.print(f"[red]Schedule not found:[/red] {schedule_id!r}")
        raise typer.Exit(1)

    if as_json:
        print(json.dumps(schedule.to_dict()))
        return

    state = "[green]enabled[/green]" if schedule.enabled else "[yellow]disabled[/yellow]"
    console.print(f"[bold]{schedule.name}[/bold]  {state}")
    console.print(f"  ID:       {schedule.schedule_id}")
    console.print(f"  Kind:     {schedule.kind.value}")
    console.print(f"  Task:     {schedule.task}")
    if schedule.cron:
        console.print(f"  Cron:     {schedule.cron}")
    if schedule.interval_seconds is not None:
        console.print(f"  Interval: {schedule.interval_seconds}s")
    if schedule.run_at:
        console.print(f"  Run at:   {schedule.run_at}")
    console.print(f"  Deliver:  {schedule.deliver_to}")
    if schedule.webhook_url:
        console.print(f"  Webhook:  {schedule.webhook_url}")
    console.print(f"  Created:  {schedule.created_at}")
    console.print(f"  Next run: {schedule.next_run or '(none)'}")
    console.print(f"  Last run: {schedule.last_run or '(never)'}")
    console.print(f"  Run count: {schedule.run_count}")


@schedule_app.command("pause")
def schedule_pause(
    schedule_id: str = typer.Argument(..., help="Schedule ID to pause."),
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
) -> None:
    """Pause a schedule so it stops firing without being deleted.

    Resume it later with `hachi schedule resume <id>`.
    """
    ok = _get_scheduler().set_enabled(schedule_id, False)
    if as_json:
        print(json.dumps({"paused": ok, "id": schedule_id}))
        return
    if ok:
        console.print(f"[yellow]Paused[/yellow] {schedule_id}")
    else:
        console.print(f"[red]Schedule not found:[/red] {schedule_id!r}")
        raise typer.Exit(1)


@schedule_app.command("resume")
def schedule_resume(
    schedule_id: str = typer.Argument(..., help="Schedule ID to resume."),
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
) -> None:
    """Resume a previously paused schedule."""
    ok = _get_scheduler().set_enabled(schedule_id, True)
    if as_json:
        print(json.dumps({"resumed": ok, "id": schedule_id}))
        return
    if ok:
        console.print(f"[green]Resumed[/green] {schedule_id}")
    else:
        console.print(f"[red]Schedule not found:[/red] {schedule_id!r}")
        raise typer.Exit(1)


@schedule_app.command("remove")
def schedule_remove(schedule_id: str = typer.Argument(..., help="Schedule id to remove.")):
    """Remove a schedule by id."""
    if _get_scheduler().cancel(schedule_id):
        console.print(f"[green]Removed[/green] {schedule_id}")
    else:
        console.print(f"[yellow]No schedule found:[/yellow] {schedule_id}")
        raise typer.Exit(1)


@schedule_app.command("run-due")
def schedule_run_due():
    """Run every schedule that is currently due (intended for cron/daemon invocation)."""
    scheduler = _get_scheduler()
    due = scheduler.due()
    if not due:
        console.print("[dim]No schedules are due.[/dim]")
        return

    agent = boot_agent()
    try:

        def fire(schedule):
            console.print(f"[cyan]Running[/cyan] '{schedule.name}': {schedule.task}")
            reply = agent.chat(schedule.task)
            _deliver_schedule_result(schedule, reply)

        fired = scheduler.tick(fire)
        console.print(f"[green]Fired {len(fired)} schedule(s).[/green]")
    finally:
        try:
            agent.shutdown()
        except Exception:
            pass


@schedule_app.command("run-now")
def schedule_run_now(
    schedule_id: str = typer.Argument(..., help="Schedule ID to run immediately."),
) -> None:
    """Run a specific schedule immediately, regardless of its next-run time.

    Useful for one-off manual triggers, testing, and debugging scheduled tasks.
    The schedule's ``last_run`` and ``run_count`` are updated normally; cron and
    interval schedules stay enabled and advance to their next fire time.
    """
    import datetime

    scheduler = _get_scheduler()
    schedule = scheduler.get(schedule_id)
    if schedule is None:
        console.print(f"[red]Schedule not found:[/red] {schedule_id!r}")
        raise typer.Exit(1)

    console.print(f"[cyan]Running[/cyan] '{schedule.name}': {schedule.task}")
    agent = boot_agent()
    try:
        reply = agent.chat(schedule.task)
        _deliver_schedule_result(schedule, reply)
        scheduler.mark_fired(schedule, datetime.datetime.now(datetime.UTC))
        console.print(f"[green]Done.[/green] '{schedule.name}' completed successfully.")
        if reply:
            console.print(f"[dim]Result:[/dim] {reply[:200]}{'…' if len(reply) > 200 else ''}")
    except Exception as exc:
        console.print(f"[red]Error running schedule:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        try:
            agent.shutdown()
        except Exception:
            pass


def _deliver_schedule_result(schedule, reply: str) -> None:
    """Deliver a scheduled task's result to its configured destination."""
    if schedule.deliver_to == "webhook" and schedule.webhook_url:
        import urllib.request

        from hachi.core.net_guard import validate_outbound_url

        ok, reason = validate_outbound_url(schedule.webhook_url)
        if not ok:
            console.print(f"[red]Webhook blocked[/red] ({reason}): {schedule.webhook_url}")
            return

        from hachi.core.secret_scanner import redact_outbound

        safe_reply, _redacted = redact_outbound(reply)
        payload = json.dumps({"schedule": schedule.name, "result": safe_reply}).encode("utf-8")
        request = urllib.request.Request(
            schedule.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=15)  # noqa: S310
        except Exception as e:
            console.print(f"[yellow]Webhook delivery failed:[/yellow] {e}")
    else:
        console.print(Panel(Markdown(reply), title=f"Scheduled: {schedule.name}"))
