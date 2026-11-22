"""Session command group: inspect and manage past agent sessions."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

console = Console()

session_app = typer.Typer(
    help="Inspect past agent sessions — list, show transcripts, and search history.",
    no_args_is_help=True,
)


@session_app.command("list")
def session_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Max sessions to show."),
    as_json: bool = typer.Option(False, "--json", help="Emit as JSON."),
) -> None:
    """List the most recent agent sessions with date, model, and turn count."""
    from hachi.core.session_store import SessionStore

    store = SessionStore()
    sessions = store.get_recent_sessions(limit=limit)
    store.shutdown()

    if as_json:
        print(json.dumps(sessions, indent=2))
        return

    if not sessions:
        console.print("[dim]No sessions recorded yet.[/dim]")
        return

    console.print(f"[bold]Last {len(sessions)} session(s):[/bold]")
    for s in sessions:
        sid = s.get("id", "")
        started = (s.get("started_at") or "")[:19].replace("T", " ")
        ended = (s.get("ended_at") or "")[:19].replace("T", " ")
        model = s.get("model", "unknown")
        turns = s.get("total_turns", 0)
        title = (s.get("title") or "").strip()
        status = f"ended {ended}" if ended else "[yellow]active[/yellow]"
        title_line = f"  [white]{title}[/white]\n" if title else ""
        console.print(
            f"{title_line}  [cyan]{sid}[/cyan]  {started}  [dim]{model}[/dim]"
            f"  {turns} turn(s)  {status}"
        )


@session_app.command("show")
def session_show(
    session_id: str = typer.Argument(..., help="Session ID (or prefix) to display."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max messages to display."),
    as_json: bool = typer.Option(False, "--json", help="Emit transcript as JSON."),
) -> None:
    """Print the message transcript for a session.

    Pass the full session ID or a unique prefix from 'hachi session list'.
    """
    from hachi.core.session_store import SessionStore

    store = SessionStore()

    if len(session_id) < 16:
        candidates = store.get_recent_sessions(limit=200)
        matches = [s["id"] for s in candidates if str(s["id"]).startswith(session_id)]
        if not matches:
            console.print(f"[red]No session found with prefix:[/red] {session_id}")
            store.shutdown()
            raise typer.Exit(1)
        if len(matches) > 1:
            console.print(
                f"[yellow]Ambiguous prefix '{session_id}' matches {len(matches)} sessions.[/yellow]"
                " Use a longer prefix."
            )
            for m in matches[:5]:
                console.print(f"  {m}")
            store.shutdown()
            raise typer.Exit(1)
        session_id = matches[0]

    messages = store.get_session_messages(session_id, limit=limit)
    meta = store.get_session(session_id)
    store.shutdown()

    title = (meta.get("title") or "").strip() if meta else ""
    total_tokens = int(meta.get("total_tokens") or 0) if meta else 0
    total_cost_usd = float(meta.get("total_cost_usd") or 0.0) if meta else 0.0

    if as_json:
        print(
            json.dumps(
                {
                    "session_id": session_id,
                    "title": title,
                    "total_tokens": total_tokens,
                    "total_cost_usd": total_cost_usd,
                    "messages": messages,
                },
                indent=2,
            )
        )
        return

    if not messages:
        console.print(f"[dim]No messages found for session {session_id}.[/dim]")
        return

    if title:
        console.print(f"[bold white]{title}[/bold white]")
    cost_str = f"  ·  {total_tokens:,} tok  ~${total_cost_usd:.4f}" if total_tokens else ""
    console.print(
        f"[bold]Session[/bold] [cyan]{session_id}[/cyan]  ({len(messages)} messages){cost_str}"
    )
    console.print()
    for msg in messages:
        role = msg.get("role", "?")
        content = (msg.get("content") or "").strip()
        tool = msg.get("tool_name") or ""
        ts = (msg.get("timestamp") or "")[:19].replace("T", " ")

        if role == "user":
            label = "[bold green]You[/bold green]"
        elif role == "assistant":
            label = "[bold blue]Agent[/bold blue]"
        elif role == "tool" and tool:
            label = f"[dim]Tool({tool})[/dim]"
        else:
            label = f"[dim]{role}[/dim]"

        display = content[:400] + ("…" if len(content) > 400 else "")
        console.print(f"[dim]{ts}[/dim] {label}")
        if display:
            console.print(f"  {display}")
        console.print()


@session_app.command("search")
def session_search(
    query: str = typer.Argument(..., help="Text to search for across all sessions."),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results to show."),
    as_json: bool = typer.Option(False, "--json", help="Emit results as JSON."),
) -> None:
    """Search across all past session transcripts for a keyword or phrase."""
    from hachi.core.session_store import SessionStore

    store = SessionStore()
    results = store.search_sessions(query, limit=limit)
    store.shutdown()

    if as_json:
        print(json.dumps({"query": query, "results": results}, indent=2))
        return

    if not results:
        console.print(f"[dim]No sessions matched:[/dim] {query}")
        return

    console.print(f"[bold]{len(results)}[/bold] result(s) for [cyan]{query}[/cyan]:")
    for r in results:
        sid = r.get("session_id", "")
        date = (r.get("session_date") or "")[:10]
        model = r.get("model", "?")
        role = r.get("role", "?")
        snippet = r.get("snippet", "")
        console.print(
            f"  [cyan]{sid}[/cyan] [dim]{date}  {model}[/dim]"
            f"  [magenta]{role}[/magenta]  {snippet}"
        )


@session_app.command("delete")
def session_delete(
    session_id: str = typer.Argument(..., help="Session ID (or prefix) to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
) -> None:
    """Permanently delete a session and all its messages from the local store.

    The deletion is irreversible.  Pass the full session ID or a unique prefix
    from 'hachi session list'.
    """
    from hachi.core.session_store import SessionStore

    store = SessionStore()

    if len(session_id) < 36:
        candidates = store.get_recent_sessions(limit=200)
        matches = [s["id"] for s in candidates if str(s["id"]).startswith(session_id)]
        if not matches:
            store.shutdown()
            if as_json:
                print(json.dumps({"ok": False, "error": f"No session: {session_id}"}))
            else:
                console.print(f"[red]No session found with prefix:[/red] {session_id}")
            raise typer.Exit(1)
        if len(matches) > 1:
            store.shutdown()
            if as_json:
                print(json.dumps({"ok": False, "error": "Ambiguous", "matches": matches[:5]}))
            else:
                console.print(
                    f"[yellow]Ambiguous prefix '{session_id}' matches"
                    f" {len(matches)} sessions.[/yellow]  Use a longer prefix."
                )
                for m in matches[:5]:
                    console.print(f"  {m}")
            raise typer.Exit(1)
        session_id = matches[0]

    if not yes and not as_json:
        confirmed = typer.confirm(
            f"Delete session {session_id}? This cannot be undone.", default=False
        )
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            store.shutdown()
            return

    deleted = store.delete_session(session_id)
    store.shutdown()

    if as_json:
        print(json.dumps({"ok": deleted, "session_id": session_id}))
        if not deleted:
            raise typer.Exit(1)
        return

    if deleted:
        console.print(f"[green]Deleted[/green] session [cyan]{session_id}[/cyan].")
    else:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(1)


@session_app.command("export")
def session_export(
    session_id: str = typer.Argument(..., help="Session ID (or prefix) to export."),
    output: str = typer.Option("", "--output", "-o", help="Output file path (default: stdout)."),
    fmt: str = typer.Option("md", "--format", "-f", help="Output format: md or json."),
    limit: int = typer.Option(0, "--limit", "-n", help="Max messages (0 = all)."),
) -> None:
    """Export a session transcript to Markdown or JSON.

    Writes to stdout by default; pass -o FILE to write to a file instead.
    Pass the full session ID or a unique prefix from 'hachi session list'.
    """
    from hachi.core.session_store import SessionStore

    if fmt not in ("md", "json"):
        console.print(f"[red]Unknown format:[/red] {fmt!r} — choose 'md' or 'json'.")
        raise typer.Exit(1)

    store = SessionStore()

    if len(session_id) < 36:
        candidates = store.get_recent_sessions(limit=200)
        matches = [s["id"] for s in candidates if str(s["id"]).startswith(session_id)]
        if not matches:
            store.shutdown()
            console.print(f"[red]No session found with prefix:[/red] {session_id}")
            raise typer.Exit(1)
        if len(matches) > 1:
            store.shutdown()
            console.print(
                f"[yellow]Ambiguous prefix '{session_id}' matches {len(matches)} sessions.[/yellow]"
                " Use a longer prefix."
            )
            for m in matches[:5]:
                console.print(f"  {m}")
            raise typer.Exit(1)
        session_id = matches[0]

    lim = limit if limit > 0 else 10_000
    messages = store.get_session_messages(session_id, limit=lim)
    store.shutdown()

    if fmt == "json":
        text = json.dumps({"session_id": session_id, "messages": messages}, indent=2)
    else:
        lines: list[str] = [f"# Session {session_id}\n"]
        for msg in messages:
            role = msg.get("role", "?")
            content = (msg.get("content") or "").strip()
            tool = msg.get("tool_name") or ""
            ts = (msg.get("timestamp") or "")[:19].replace("T", " ")

            if role == "user":
                heading = f"## You  _{ts}_"
            elif role == "assistant":
                heading = f"## Agent  _{ts}_"
            elif role == "tool" and tool:
                heading = f"### Tool: {tool}  _{ts}_"
            else:
                heading = f"### {role}  _{ts}_"

            lines.append(heading)
            if content:
                lines.append(content)
            lines.append("")
        text = "\n".join(lines)

    if output:
        out_path = Path(output)
        out_path.write_text(text, encoding="utf-8")
        console.print(
            f"[green]Exported[/green] {len(messages)} message(s) → [cyan]{out_path}[/cyan]"
        )
    else:
        print(text)


@session_app.command("stats")
def session_stats(
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
) -> None:
    """Show aggregate statistics across all stored sessions."""
    import json as _json
    from collections import Counter

    from hachi.core.session_store import SessionStore

    store = SessionStore()
    sessions = store.get_recent_sessions(limit=10_000)
    store.shutdown()

    total_sessions = len(sessions)
    if total_sessions == 0:
        if as_json:
            print(_json.dumps({"total_sessions": 0}))
        else:
            console.print("[yellow]No sessions found.[/yellow]")
        raise typer.Exit(0)

    total_turns = sum(int(s.get("total_turns") or 0) for s in sessions)
    avg_turns = round(total_turns / total_sessions, 1)
    total_tokens = sum(int(s.get("total_tokens") or 0) for s in sessions)
    total_cost_usd = sum(float(s.get("total_cost_usd") or 0.0) for s in sessions)

    dates = [str(s.get("started_at") or "")[:10] for s in sessions if s.get("started_at")]
    first_session = min(dates) if dates else ""
    last_session = max(dates) if dates else ""

    date_counter: Counter[str] = Counter(d for d in dates if d)
    most_active_date, most_active_count = (
        date_counter.most_common(1)[0] if date_counter else ("", 0)
    )

    models = [str(s.get("model") or "") for s in sessions if s.get("model")]
    model_counter: Counter[str] = Counter(models)
    most_used_model = model_counter.most_common(1)[0][0] if model_counter else ""

    stats: dict[str, object] = {
        "total_sessions": total_sessions,
        "total_turns": total_turns,
        "avg_turns_per_session": avg_turns,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "first_session": first_session,
        "last_session": last_session,
        "most_active_date": most_active_date,
        "most_active_date_count": most_active_count,
        "most_used_model": most_used_model,
    }

    if as_json:
        print(_json.dumps(stats))
        return

    from rich.table import Table

    table = Table(title="Session Statistics", show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Total sessions", str(total_sessions))
    table.add_row("Total turns", str(total_turns))
    table.add_row("Avg turns/session", str(avg_turns))
    table.add_row(
        "Total API spend",
        f"{total_tokens:,} tokens  ~${total_cost_usd:.4f}" if total_tokens else "—",
    )
    table.add_row("Date range", f"{first_session} → {last_session}" if first_session else "—")
    table.add_row(
        "Most active day",
        f"{most_active_date} ({most_active_count} sessions)" if most_active_date else "—",
    )
    table.add_row("Most-used model", most_used_model or "—")
    console.print(table)


@session_app.command("clean")
def session_clean(
    older_than: int = typer.Option(
        30, "--older-than", "-d", help="Delete sessions older than this many days."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without deleting."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    as_json: bool = typer.Option(False, "--json", help="Emit result as JSON."),
) -> None:
    """Delete sessions older than N days to reclaim disk space."""
    import datetime
    import json as _json

    from hachi.core.session_store import SessionStore

    cutoff_dt = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=older_than)
    cutoff_iso = cutoff_dt.isoformat()

    store = SessionStore()
    all_sessions = store.get_recent_sessions(limit=10_000)
    matching = [s for s in all_sessions if str(s.get("started_at") or "") < cutoff_iso]
    count = len(matching)

    if count == 0:
        store.shutdown()
        if as_json:
            print(_json.dumps({"deleted": 0, "cutoff": cutoff_iso[:10], "dry_run": dry_run}))
        else:
            console.print(
                f"[yellow]Nothing to clean[/yellow] — no sessions older than {older_than} day(s)."
            )
        raise typer.Exit(0)

    if dry_run:
        store.shutdown()
        if as_json:
            print(
                _json.dumps(
                    {
                        "deleted": 0,
                        "would_delete": count,
                        "cutoff": cutoff_iso[:10],
                        "dry_run": True,
                    }
                )
            )
        else:
            console.print(
                f"[cyan]Dry run:[/cyan] would delete [bold]{count}[/bold] session(s) "
                f"older than [bold]{cutoff_iso[:10]}[/bold]."
            )
        raise typer.Exit(0)

    if not yes and not as_json:
        confirmed = typer.confirm(
            f"Permanently delete {count} session(s) older than {older_than} day(s)?",
            default=False,
        )
        if not confirmed:
            store.shutdown()
            raise typer.Exit(0)

    deleted = store.delete_sessions_before(cutoff_iso)
    store.shutdown()

    if as_json:
        print(_json.dumps({"deleted": deleted, "cutoff": cutoff_iso[:10], "dry_run": False}))
    else:
        console.print(
            f"[green]Deleted[/green] [bold]{deleted}[/bold] session(s) "
            f"older than [bold]{cutoff_iso[:10]}[/bold]."
        )


@session_app.command("retitle")
def session_retitle(
    session_id: str = typer.Argument(
        None, help="Session ID or prefix to retitle. Omit to backfill all untitled sessions."
    ),
    limit: int = typer.Option(
        50, "--limit", "-n", help="Max sessions to backfill when no ID is given."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Regenerate even when a title already exists."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit results as JSON."),
) -> None:
    """Generate titles for past sessions.

    With no SESSION_ID, titles every session that lacks one (oldest first). Pass a
    session ID or prefix to (re)title a single session; add --force to overwrite an
    existing title. Falls back to a truncation of the first message when no model
    provider is configured.
    """
    from hachi.core.config_loader import load_effective_config
    from hachi.core.llm import create_llm_client
    from hachi.core.secret_store import create_default_secret_store
    from hachi.core.session_store import SessionStore
    from hachi.core.session_titler import generate_title

    store = SessionStore()

    if session_id:
        target_id = session_id
        if len(session_id) < 16:
            candidates = store.get_recent_sessions(limit=10_000)
            matches = [s["id"] for s in candidates if str(s["id"]).startswith(session_id)]
            if not matches:
                console.print(f"[red]No session found with prefix:[/red] {session_id}")
                store.shutdown()
                raise typer.Exit(1)
            if len(matches) > 1:
                console.print(
                    f"[yellow]Ambiguous prefix '{session_id}'.[/yellow] Use a longer prefix."
                )
                store.shutdown()
                raise typer.Exit(1)
            target_id = matches[0]
        targets = [{"id": target_id}]
    else:
        targets = store.get_sessions_missing_title(limit=limit)

    if not targets:
        store.shutdown()
        if as_json:
            print(json.dumps({"retitled": 0, "sessions": []}))
        else:
            console.print("[dim]No sessions need titling.[/dim]")
        return

    client = None
    try:
        provider = load_effective_config().provider
        provider_config = {
            "kind": provider.kind,
            "model": provider.model,
            "api_key_ref": getattr(provider, "api_key_ref", None),
            "api_key_env": getattr(provider, "api_key_env", None),
            "base_url": getattr(provider, "base_url", None),
        }
        client = create_llm_client(provider_config, secret_store=create_default_secret_store())
    except Exception as exc:
        console.print(f"[yellow]No model client available ({exc}); using fallback titles.[/yellow]")

    results: list[dict[str, str]] = []
    try:
        for t in targets:
            sid = str(t["id"])
            meta = store.get_session(sid)
            if meta and (meta.get("title") or "").strip() and not force:
                continue
            messages = store.get_session_messages(sid, limit=10)
            first_user = next(
                (m["content"] for m in messages if m.get("role") == "user" and m.get("content")),
                "",
            )
            first_asst = next(
                (
                    m["content"]
                    for m in messages
                    if m.get("role") == "assistant" and m.get("content")
                ),
                "",
            )
            if not str(first_user).strip():
                continue
            title = generate_title(first_user, first_asst, llm_client=client)
            store.set_session_title(sid, title)
            results.append({"id": sid, "title": title})
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
        store.shutdown()

    if as_json:
        print(json.dumps({"retitled": len(results), "sessions": results}, indent=2))
        return

    if not results:
        console.print(
            "[dim]Nothing to retitle — targeted sessions are already titled "
            "(use --force to overwrite).[/dim]"
        )
        return
    console.print(f"[green]Titled[/green] {len(results)} session(s):")
    for r in results:
        console.print(f"  [cyan]{r['id'][:12]}[/cyan]  {r['title']}")
