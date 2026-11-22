"""Skill command group: manage and import agent skills (.og / SKILL.md)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()

skill_app = typer.Typer(help="Manage and import agent skills (.og / SKILL.md).")

# Sub-app for community skill packs (legacy GitHub-based packs).
_community_pack_app = typer.Typer(help="Install and manage community skill packs.")
skill_app.add_typer(_community_pack_app, name="pack")

# Module-level hoisted option to avoid B008 mutable-container annotation warning.
_ASSERT_PARAM_OPTION = typer.Option(
    None, "--param", "-p", help="Parameter value as key=value (repeatable)."
)


@_community_pack_app.command("list")
def pack_list(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List all installed community skill packs."""
    from hachi.core.community_packs import list_packs
    from hachi.gateway.workspace import get_skills_dir

    skills_dir = get_skills_dir()
    packs = list_packs(skills_dir)

    if as_json:
        print(
            __import__("json").dumps(
                [
                    {
                        "name": p.name,
                        "source": p.source,
                        "file_count": p.file_count,
                        "version": p.version,
                        "description": p.description,
                    }
                    for p in packs
                ],
                indent=2,
            )
        )
        return

    if not packs:
        console.print("[dim]No community packs installed.[/dim]")
        console.print("Install one with: [bold]hachi skill pack install user/repo[/bold]")
        return

    from rich.table import Table

    table = Table(title="Installed Community Skill Packs", show_lines=False)
    table.add_column("Name", style="bold cyan")
    table.add_column("Skills", justify="right")
    table.add_column("Version")
    table.add_column("Description")
    for p in packs:
        table.add_row(
            p.name,
            str(p.file_count),
            p.version or "[dim]-[/dim]",
            p.description or "[dim]-[/dim]",
        )
    console.print(table)


@_community_pack_app.command("install")
def pack_install(
    spec: str = typer.Argument(
        ...,
        help=(
            "Pack source: GitHub 'user/repo[@ref]', full archive URL (.tar.gz/.zip), "
            "single .og URL, or local directory path."
        ),
    ),
    as_json: bool = typer.Option(False, "--json", help="Output result as JSON."),
) -> None:
    """Install a community skill pack from GitHub or a URL.

    Examples::

        hachi skill pack install alice/devops-skills
        hachi skill pack install alice/devops-skills@v2
        hachi skill pack install https://github.com/alice/skills/archive/main.tar.gz
        hachi skill pack install /path/to/local/skills-dir
    """
    from hachi.core.community_packs import install_pack
    from hachi.gateway.workspace import get_skills_dir

    skills_dir = get_skills_dir()
    try:
        info = install_pack(spec, skills_dir)
    except (ValueError, FileNotFoundError, OSError) as exc:
        console.print(f"[red]Install failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if as_json:
        print(
            __import__("json").dumps(
                {
                    "name": info.name,
                    "source": info.source,
                    "installed_path": str(info.installed_path),
                    "file_count": info.file_count,
                    "version": info.version,
                    "description": info.description,
                },
                indent=2,
            )
        )
        return

    console.print(
        f"[green]Installed[/green] pack [bold cyan]{info.name}[/bold cyan] "
        f"({info.file_count} skill(s)" + (f", v{info.version}" if info.version else "") + ")"
    )
    if info.description:
        console.print(f"  {info.description}")
    console.print(f"  Skills loaded from: [dim]{info.installed_path}[/dim]")
    console.print("Run [bold]hachi skill list[/bold] to see new skills.")


@_community_pack_app.command("remove")
def pack_remove(
    name: str = typer.Argument(..., help="The pack name to remove."),
) -> None:
    """Remove an installed community skill pack."""
    from hachi.core.community_packs import remove_pack
    from hachi.gateway.workspace import get_skills_dir

    skills_dir = get_skills_dir()
    removed = remove_pack(name, skills_dir)
    if removed:
        console.print(f"[green]Removed[/green] pack [bold]{name}[/bold].")
    else:
        console.print(f"[yellow]Pack '{name}' not found.[/yellow]")
        raise typer.Exit(1)


@skill_app.command("new")
def skill_new(
    name: str = typer.Argument(..., help="Skill name (e.g. my-skill or my_skill)."),
    output: Path | None = typer.Option(  # noqa: B008
        None,
        "--output",
        "-o",
        help="Output path. Defaults to <name>.og in the current directory.",
    ),
    domain: str = typer.Option("", "--domain", help="Domain tag (e.g. productivity)."),
    author: str = typer.Option("", "--author", help="Author identifier."),
) -> None:
    """Scaffold a new .og skill file with placeholder sections.

    Creates a ready-to-edit .og file in the ObjectGraph format. The generated
    file includes meta, index, and a single node with dense, full, steps, and
    assertion blocks pre-populated with TODO placeholders.

    Examples::

        hachi skill new my-skill
        hachi skill new my-skill --output skills/my-skill.og --domain productivity
    """
    # Derive a title-case name from the slug
    title = " ".join(word.capitalize() for word in re.split(r"[-_]", name))

    # Derive keywords from the name words
    keywords = ", ".join(re.split(r"[-_]", name))

    output_path = output if output is not None else Path(f"{name}.og")

    scaffold = f"""\
::meta
  title: {title}
  version: 0.1.0
  author: {author}
  domain: {domain}
  scope: all

::index
  # node-id   | type  | scope | conf | keywords
  {name:<10} | skill | all   | 0.90 | {keywords}

::node[{name}]
->[:role=skill]
->[:scope=all]
->[:keywords={keywords}]
::dense
{name}|TODO: add a brief keyword summary (10-15 tokens)
::full
TODO: describe what this skill does in 2-3 sentences.
::steps
1. TODO: first step.
2. TODO: second step.
::assertion
success: TODO: define what success looks like
"""

    output_path.write_text(scaffold, encoding="utf-8")
    console.print(f"[green]Created[/green] {output_path}")


@skill_app.command("import")
def skill_import(
    path: str = typer.Argument(..., help="A SKILL.md file or a directory containing .md skills."),
):
    """Import SKILL.md (Agent Skills) file(s) into Hachi's token-efficient .og library."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    target = Path(path)
    if not target.exists():
        console.print(f"[red]Not found:[/red] {path}")
        raise typer.Exit(2)

    engine = SkillEngine()
    skills_dir = get_skills_dir()
    engine.load_directory(skills_dir)

    files = sorted(target.glob("**/*.md")) if target.is_dir() else [target]
    if not files:
        console.print("[yellow]No .md files found.[/yellow]")
        return

    imported = 0
    for md in files:
        result = engine.import_skill_md(md)
        if result.get("status") == "imported":
            imported += 1
            kw = ", ".join(result.get("keywords", [])[:5])
            console.print(
                f"[green]Imported[/green] {md.name} → {result['name']}  [dim]({kw})[/dim]"
            )
        else:
            console.print(f"[yellow]Skipped[/yellow] {md.name}: {result.get('reason')}")

    console.print(
        f"\n[bold]Imported {imported}/{len(files)} skill(s)[/bold] into {skills_dir / 'imported'}."
    )


@skill_app.command("list")
def skill_list():
    """List all loaded .og skills (name, role, keywords)."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    skills = engine.list_all_skills()
    if not skills:
        console.print("[dim]No skills loaded.[/dim]")
        return
    for item in sorted(skills, key=lambda s: s["name"]):
        keywords = item.get("keywords", "")
        console.print(
            f"[bold]{item['name']}[/bold] [dim][{item.get('role', 'skill')}][/dim]  {keywords}"
        )
    console.print(f"\n[bold]{len(skills)} skill(s) loaded.[/bold]")


@skill_app.command("export")
def skill_export(
    name: str = typer.Argument(..., help="Exact skill node name (see `skill list`)."),
    output: str | None = typer.Option(None, "--output", "-o", help="Write to a file vs stdout."),
):
    """Export a loaded skill back to .og text."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    text = engine.export_skill(name)
    if text is None:
        console.print(f"[red]Skill not found:[/red] {name} [dim](see `hachi skill list`)[/dim]")
        raise typer.Exit(1)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]Exported[/green] {name} → {output}")
    else:
        console.print(text)


@skill_app.command("deps")
def skill_deps(
    name: str = typer.Argument(..., help="Exact skill node name (see `skill list`)."),
    as_json: bool = typer.Option(False, "--json", help="Emit the dependency report as JSON."),
):
    """Resolve a skill's transitive `requires` dependency chain (load these first)."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    result = engine.get_dependency_chain(name)
    if result is None:
        console.print(f"[red]Skill not found:[/red] {name} [dim](see `hachi skill list`)[/dim]")
        raise typer.Exit(1)

    if as_json:
        print(json.dumps(result, indent=2))
        return

    console.print(f"[bold]{name}[/bold] dependencies:")
    console.print(f"  direct:     {', '.join(result['direct']) or '(none)'}")
    console.print(f"  full chain: {', '.join(result['chain']) or '(none)'}")
    if result["missing"]:
        console.print(f"  [yellow]missing (not loaded):[/yellow] {', '.join(result['missing'])}")
    if result["has_cycle"]:
        console.print("  [red]⚠ dependency cycle detected[/red]")


@skill_app.command("show")
def skill_show(
    name: str = typer.Argument(..., help="Exact skill node name (see `skill list`)."),
    as_json: bool = typer.Option(False, "--json", help="Emit the skill view as JSON."),
):
    """Inspect one skill's Pass-2 view: metadata, dense summary, and a manifest of
    heavy blocks with their token cost — without loading the full body (the .og
    3-pass model). Shows why selective loading saves tokens."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())

    node = engine.get_node(name)
    if node is None:
        console.print(f"[red]Skill not found:[/red] {name} [dim](see `hachi skill list`)[/dim]")
        raise typer.Exit(1)

    peeked = engine.peek([name]).get(name, {})
    changelog = engine.get_node_changelog(name) or {}
    available = peeked.get("available_blocks", {})
    result = {
        "name": name,
        "role": node.role,
        "scope": node.scope,
        "version": changelog.get("version", ""),
        "keywords": list(node.keywords),
        "requires": list(node.requires),
        "requires_auth": list(node.requires_auth),
        "dense": peeked.get("dense", ""),
        "warning": peeked.get("warning", ""),
        "available_blocks": available,
        "full_load_tokens": sum(available.values()),
    }

    if as_json:
        print(json.dumps(result, indent=2))
        return

    console.print(f"[bold]{name}[/bold]  [dim]({node.role} · {node.scope})[/dim]")
    if result["version"]:
        console.print(f"  version:   {result['version']}")
    console.print(f"  keywords:  {', '.join(result['keywords']) or '(none)'}")
    console.print(f"  requires:  {', '.join(result['requires']) or '(none)'}")
    if result["requires_auth"]:
        console.print(f"  auth:      {', '.join(result['requires_auth'])}")
    console.print(f"  dense:     {result['dense'] or '(none)'}")
    if result["warning"]:
        console.print(f"  [yellow]warning:   {result['warning']}[/yellow]")
    if available:
        blocks = ", ".join(f"{block} (~{cost} tok)" for block, cost in available.items())
        console.print(f"  blocks:    {blocks}")
        console.print(
            f"  [dim]full load ≈ {result['full_load_tokens']} tokens "
            "(loaded only on demand via load_skill)[/dim]"
        )
    else:
        console.print("  blocks:    [dim](dense-only; no heavy content)[/dim]")


@skill_app.command("search")
def skill_search(
    query: str = typer.Argument(..., help="Keywords / natural-language query to route on."),
    as_json: bool = typer.Option(False, "--json", help="Emit matches as JSON."),
):
    """Test Pass-1 routing: which skills match a query by keyword (the agent's
    first step, before peek/load). Shows the .og index doing O(1) routing."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    matches = sorted(engine.search(query), key=lambda m: m["name"])

    if as_json:
        print(json.dumps({"query": query, "matches": matches}, indent=2))
        return

    if not matches:
        console.print(
            f"[yellow]No skills matched:[/yellow] {query} [dim](try `hachi skill list`)[/dim]"
        )
        return
    console.print(f"[bold]{len(matches)} skill(s)[/bold] matched [cyan]{query}[/cyan]:")
    for match in matches:
        console.print(
            f"  • [bold]{match['name']}[/bold]  [dim]({match['role']})[/dim]  {match['keywords']}"
        )


@skill_app.command("changelog")
def skill_changelog(
    name: str = typer.Argument(..., help="Exact skill node name (see `skill list`)."),
    as_json: bool = typer.Option(False, "--json", help="Emit the changelog as JSON."),
):
    """Show a skill's version + ::changelog entries — the .og delta-load story:
    check what changed (a few tokens) without re-reading the heavy content."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    result = engine.get_node_changelog(name)
    if result is None:
        console.print(f"[red]Skill not found:[/red] {name} [dim](see `hachi skill list`)[/dim]")
        raise typer.Exit(1)

    if as_json:
        print(json.dumps(result, indent=2))
        return

    version = result.get("version") or "(unversioned)"
    header = f"[bold]{name}[/bold]  v{version}"
    if result.get("updated"):
        header += f"  [dim](updated {result['updated']})[/dim]"
    console.print(header)
    entries = result.get("changelog") or []
    if not entries:
        console.print("  [dim]no changelog entries[/dim]")
        return
    for entry in entries:
        console.print(
            f"  {entry.get('date', '')}  [cyan]{entry.get('action', '')}[/cyan]  "
            f"{entry.get('target', '')}  {entry.get('description', '')}".rstrip()
        )


@skill_app.command("traverse")
def skill_traverse(
    name: str = typer.Argument(..., help="Exact skill node name (see `skill list`)."),
    as_json: bool = typer.Option(False, "--json", help="Emit the traverse hints as JSON."),
) -> None:
    """Show a skill's ::traverse hints — priority, entry node, and depth limit.

    Traverse hints guide how the agent navigates the skill graph:
    - priority (high/normal/low) — controls ranking in `skill search` results
    - entry — preferred sub-node to load first when this is a subgraph root
    - depth — how many requires edges to follow automatically
    """
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    result = engine.get_traverse_hints(name)
    if result is None:
        console.print(f"[red]Skill not found:[/red] {name} [dim](see `hachi skill list`)[/dim]")
        raise typer.Exit(1)

    if as_json:
        print(json.dumps(result, indent=2))
        return

    hints = result.get("traverse") or {}
    if not hints:
        console.print(f"[dim]{name} has no ::traverse hints.[/dim]")
        return

    console.print(f"[bold]{name}[/bold] traverse hints:")
    _KEY_LABELS = {"priority": "Priority", "entry": "Entry node", "depth": "Max depth"}
    for key, value in hints.items():
        label = _KEY_LABELS.get(key, key)
        console.print(f"  [cyan]{label}:[/cyan] {value}")


@skill_app.command("assert")
def skill_assert(
    name: str = typer.Argument(..., help="Exact skill node name (see `skill list`)."),
    param: list[str] | None = _ASSERT_PARAM_OPTION,
    as_json: bool = typer.Option(False, "--json", help="Emit the assertion report as JSON."),
):
    """Check a skill's ::assertion preconditions against parameter values.

    Deterministic — a bounded comparison grammar over the params you supply, no
    shell or LLM. Exits non-zero if any assertion fails or needs a value, so it
    works as a CI gate. Supply inputs with --param k=v (repeatable)."""
    from hachi.core.assertion_eval import evaluate_assertions
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    params: dict[str, str] = {}
    for item in param or []:
        if "=" not in item:
            console.print(f"[red]Invalid --param (expected key=value):[/red] {item}")
            raise typer.Exit(2)
        key, value = item.split("=", 1)
        params[key.strip()] = value.strip()

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    node = engine.get_node(name)
    if node is None:
        console.print(f"[red]Skill not found:[/red] {name} [dim](see `hachi skill list`)[/dim]")
        raise typer.Exit(1)

    results = evaluate_assertions(node.assertions, params)
    ok = all(r.status not in ("fail", "unknown") for r in results)
    report = {
        "skill": name,
        "ok": ok,
        "results": [
            {
                "assertion": r.assertion,
                "status": r.status,
                "message": r.message,
                "detail": r.detail,
            }
            for r in results
        ],
    }

    if as_json:
        print(json.dumps(report, indent=2))
        raise typer.Exit(0 if ok else 1)

    if not results:
        console.print(f"[dim]{name} has no ::assertion block.[/dim]")
        return
    status_style = {"pass": "green", "fail": "red", "unknown": "yellow", "manual": "dim"}
    for r in results:
        style = status_style.get(r.status, "white")
        line = f"  [{style}]{r.status.upper():7}[/{style}] {r.message or r.assertion}"
        if r.detail:
            line += f"  [dim]({r.detail})[/dim]"
        console.print(line)
    console.print(f"{name}: {'[green]OK[/green]' if ok else '[red]FAILED[/red]'}")
    raise typer.Exit(0 if ok else 1)


@skill_app.command("graph")
def skill_graph(
    as_json: bool = typer.Option(False, "--json", help="Emit the dependency graph as JSON."),
):
    """Show the whole-library skill dependency graph (who requires whom).

    Builds an adjacency view across every loaded skill from their typed
    `requires` edges, then flags entry-point roots, missing (referenced but not
    loaded) dependencies, and any dependency cycles — the .og dependency-aware
    traversal at library scale."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    graph = engine.get_skill_graph()
    nodes = graph["nodes"]
    roots = graph["roots"]
    missing = graph["missing"]
    cyclic = graph["cyclic"]

    if as_json:
        print(json.dumps(graph, indent=2))
        return

    if not nodes:
        console.print("[dim]No skills loaded.[/dim]")
        return
    console.print(
        f"[bold]Skill dependency graph[/bold]  "
        f"({graph['skill_count']} skills, {graph['edge_count']} edges)"
    )
    for node in nodes:
        arrow = " → " + ", ".join(node["direct"]) if node["direct"] else "  [dim](no deps)[/dim]"
        flag = "  [red]⚠ cycle[/red]" if node["has_cycle"] else ""
        console.print(f"  [bold]{node['name']}[/bold] [dim]({node['role']})[/dim]{arrow}{flag}")
    if roots:
        console.print(f"\n  [cyan]entry-point roots:[/cyan] {', '.join(roots)}")
    if missing:
        console.print(f"  [yellow]missing (referenced, not loaded):[/yellow] {', '.join(missing)}")
    if cyclic:
        console.print(f"  [red]cycles in:[/red] {', '.join(cyclic)}")


@skill_app.command("viz")
def skill_viz(
    fmt: str = typer.Option(
        "mermaid", "--format", "-f", help="Diagram format: mermaid | dot | html."
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Write to this file instead of stdout."
    ),
):
    """Visualize the skill dependency graph as a diagram.

    `mermaid` renders inline on GitHub/Markdown/Obsidian with no tooling; `dot`
    is Graphviz source (pipe to `dot -Tsvg -o skills.svg`); `html` is a
    self-contained interactive graph (drag/zoom/hover) — open it in a browser.
    Nodes are colored by role; roots, cycles, and missing deps are highlighted."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine
    from hachi.og_engine.graph_viz import render_graph

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    graph = engine.get_skill_graph()

    try:
        diagram = render_graph(graph, fmt)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc

    if output is not None:
        out_path = Path(output)
        out_path.write_text(diagram, encoding="utf-8")
        console.print(
            f"[green]Wrote {fmt} diagram[/green] ({graph['skill_count']} skills, "
            f"{graph['edge_count']} edges) → [cyan]{out_path}[/cyan]"
        )
        return
    print(diagram)


@skill_app.command("report")
def skill_report(
    stale_days: int = typer.Option(
        30, "--stale-days", help="Days of inactivity before a skill is flagged stale."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON (for CI/automation)."
    ),
) -> None:
    """Show skill-usage analytics: most-used, never-used, and stale skills.

    This realizes the .og self-optimization loop — usage is tracked every time
    the agent calls load_skill, so this report reveals which skills earn their
    keep and which are dead weight worth pruning or refining.
    """
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())

    report = engine.get_usage_report()
    stale = engine.get_stale_skills(stale_days=stale_days)
    never_used = [s for s in stale if s["status"] == "never_used"]
    aged = [s for s in stale if s["status"] == "stale"]

    if json_output:
        print(
            json.dumps(
                {"report": report, "stale": aged, "never_used": never_used},
                indent=2,
                default=str,
            )
        )
        return

    if report["total_skills"] == 0:
        console.print("[dim]No skills loaded.[/dim]")
        return

    summary = (
        f"Total: [bold]{report['total_skills']}[/bold]   "
        f"Tracked: [bold]{report['tracked_skills']}[/bold]   "
        f"Stale (>{stale_days}d): [yellow]{report['stale_count']}[/yellow]   "
        f"Never used: [yellow]{report['never_used_count']}[/yellow]"
    )
    console.print(Panel(summary, title="Skill Usage Report", border_style="cyan"))

    top = report.get("top_skills", [])
    if top:
        console.print("[bold]Most used[/bold]")
        for item in top:
            last = item.get("last_used") or "-"
            console.print(
                f"  [green]{item['use_count']:>4}x[/green]  {item['name']}  [dim]{last}[/dim]"
            )

    if aged:
        console.print(f"\n[bold yellow]Stale (>{stale_days}d inactive)[/bold yellow]")
        for item in sorted(aged, key=lambda s: s.get("days_inactive") or 0, reverse=True):
            console.print(
                f"  [dim]{item['days_inactive']}d ago[/dim]  {item['name']} "
                f"[dim](used {item['use_count']}x)[/dim]"
            )

    if never_used:
        console.print("\n[bold]Never used[/bold] [dim](candidates to prune or promote)[/dim]")
        for item in sorted(never_used, key=lambda s: s["name"]):
            console.print(f"  [dim]-[/dim] {item['name']}")


@skill_app.command("lint")
def skill_lint(
    path: str = typer.Argument(..., help="A .og file or a directory of .og skill files."),
    strict: bool = typer.Option(
        False, "--strict", help="Treat warnings as failures (exit non-zero) — good for CI."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON (for CI/automation)."
    ),
) -> None:
    """Lint .og skill files for structure + token efficiency before shipping them.

    Flags un-routable nodes (missing ::index entry/keywords), missing or oversized
    ::dense blocks, empty nodes, and dangling ::index entries — the conventions the
    3-pass loader and search depend on. Exits non-zero on errors (or any warning with
    --strict), so it can gate community skill packs in CI.
    """
    from hachi.og_engine.engine import lint_og_file

    target = Path(path)
    if not target.exists():
        console.print(f"[red]Not found:[/red] {path}")
        raise typer.Exit(2)

    if target.is_dir():
        files = sorted(target.glob("**/*.og"))
    else:
        files = [target]
    if not files:
        console.print("[yellow]No .og files found.[/yellow]")
        return

    reports = [lint_og_file(f) for f in files]

    total_errors = sum(r["summary"]["errors"] for r in reports)
    total_warnings = sum(r["summary"]["warnings"] for r in reports)

    if json_output:
        print(json.dumps({"reports": reports}, indent=2, default=str))
    else:
        _level_style = {"error": "red", "warning": "yellow", "info": "dim"}
        for report in reports:
            name = Path(report["file"]).name
            count = report["node_count"]
            if not report["issues"]:
                console.print(f"[green]OK[/green] {name} [dim]({count} node(s))[/dim]")
                continue
            verdict = "[red]FAIL[/red]" if not report["ok"] else "[yellow]WARN[/yellow]"
            console.print(f"{verdict} {name} [dim]({count} node(s))[/dim]")
            for issue in report["issues"]:
                color = _level_style.get(issue["level"], "white")
                console.print(
                    f"  [{color}]{issue['level']:<7}[/{color}] "
                    f"[bold]{issue['node']}[/bold] [dim]{issue['code']}[/dim]: {issue['message']}"
                )
        console.print(
            f"\n[bold]{len(files)} file(s)[/bold]  "
            f"[red]{total_errors} error(s)[/red]  "
            f"[yellow]{total_warnings} warning(s)[/yellow]"
        )

    failed = total_errors > 0 or (strict and total_warnings > 0)
    if failed:
        raise typer.Exit(1)


@skill_app.command("benchmark")
def skill_benchmark(
    dir_path: str | None = typer.Option(
        None, "--dir", help="Skill directory to benchmark. Defaults to the bundled default_skills."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON (for CI / sharing)."
    ),
    threshold: float = typer.Option(
        0.80,
        "--threshold",
        help="Minimum required savings fraction (0–1). Exit 1 if below. Default 0.80.",
    ),
    suite: str = typer.Option(
        "token",
        "--suite",
        help=(
            "Benchmark suite to run. "
            "'token' = token-savings only (default). "
            "'fast' = token-savings + M1 retrieval quality (P@5 ≥ 0.80, FPR < 0.20). "
            "'retrieval' = retrieval quality only. "
            "'full' = all arms (requires D-4 approval for live-LLM arms)."
        ),
    ),
    probe_file: str | None = typer.Option(
        None,
        "--probes",
        help="Path to a custom JSON probe file. Defaults to the bundled S-real corpus.",
    ),
) -> None:
    """Benchmark the 3-pass .og model against a dump-all baseline.

    Proves the ObjectGraph token-efficiency moat: loading skills via
    search → peek → resolve uses a fraction of the tokens compared to
    naively concatenating every skill into the prompt. Run this against
    your custom skill pack to see your own savings figure.

    --suite fast additionally gates M1 retrieval quality (P@5 ≥ 0.80 on keyword
    and paraphrase queries; false-positive rate < 0.20 on negative queries).

    Exits 1 when any gate fails (useful as a CI gate).
    """
    import json as _json

    from hachi.og_engine.engine import SkillEngine, estimate_tokens

    suite = suite.lower()
    if suite not in ("token", "fast", "retrieval", "full"):
        console.print(f"[red]Unknown --suite {suite!r}. Choose: token, fast, retrieval, full[/red]")
        raise typer.Exit(2)

    if dir_path is not None:
        skills_dir = Path(dir_path)
        if not skills_dir.exists():
            console.print(f"[red]Directory not found:[/red] {dir_path}")
            raise typer.Exit(2)
    else:
        from hachi.gateway.workspace import get_skills_dir

        skills_dir = get_skills_dir()

    engine = SkillEngine()
    engine.load_directory(skills_dir)
    nodes = engine.get_all_nodes()

    if len(nodes) < 3:
        console.print(
            "[yellow]Not enough skill nodes to run a meaningful benchmark "
            f"(found {len(nodes)}).[/yellow]"
        )
        raise typer.Exit(2)

    all_passed = True
    output: dict[str, object] = {"suite": suite, "nodes": len(nodes)}

    if suite in ("token", "fast", "full"):
        baseline_text = "\n".join(engine.resolve_node(n.name, blocks=["all"]) for n in nodes)
        baseline = estimate_tokens(baseline_text)

        import sys as _sys3

        _project_root = str(Path.cwd())
        if _project_root not in _sys3.path:
            _sys3.path.insert(0, _project_root)
        try:
            from benchmarks.og_bench.metrics import (  # type: ignore[import-not-found]
                pick_representative_query,
            )
        except ImportError as exc:
            console.print(f"[red]Cannot load benchmark metrics module: {exc}[/red]")
            raise typer.Exit(2) from exc

        # C3 fix: a naive keywords[0] pick can land on a bare name defined once
        # per roles/*.og file (e.g. "identity") — resolve_node refuses the
        # ambiguous match and returns an "Error: ..." sentinel, which would
        # silently masquerade as real Pass-3 content in the savings measurement.
        query = pick_representative_query(engine)
        if query is None:
            console.print(
                "[yellow]No indexed keyword resolves to a loadable skill node — "
                "cannot run token benchmark.[/yellow]"
            )
            raise typer.Exit(2)

        results = engine.search(query)
        candidates = [r["name"] for r in results][:5]
        p1 = estimate_tokens(_json.dumps(results[:5]))
        p2 = estimate_tokens(_json.dumps(engine.peek(candidates)))
        resolved = engine.resolve_node(candidates[0])
        if resolved.startswith("Error:"):
            console.print(
                f"[red]Representative query {query!r} resolved to a failed skill "
                f"load: {resolved!r}[/red]"
            )
            raise typer.Exit(2)
        p3 = estimate_tokens(resolved)
        three_pass = p1 + p2 + p3
        savings = 1.0 - (three_pass / baseline) if baseline > 0 else 0.0
        token_passed = savings >= threshold
        all_passed = all_passed and token_passed

        output["token"] = {
            "baseline_tokens": baseline,
            "three_pass_tokens": three_pass,
            "savings_pct": round(savings, 6),
            "p1_tokens": p1,
            "p2_tokens": p2,
            "p3_tokens": p3,
            "threshold": threshold,
            "passed": token_passed,
            "query": query,
        }

        if not as_json:
            vc = "green" if token_passed else "red"
            vi = "✓" if token_passed else "✗"
            console.print(
                Panel(
                    f"[bold]Token-Savings Arm[/bold]\n\n"
                    f"Skills:        [bold]{len(nodes)}[/bold] nodes\n"
                    f"Baseline:      [bold]{baseline:,}[/bold] tok\n"
                    f"3-pass total:  [bold]{three_pass:,}[/bold] tok  "
                    f"[dim](p1={p1:,}, p2={p2:,}, p3={p3:,})[/dim]\n"
                    f"Token savings: [{vc}][bold]{savings:.1%}[/bold]  "
                    f"{vi} {'above' if token_passed else 'below'} "
                    f"{threshold:.0%} threshold[/{vc}]",
                    border_style=vc,
                )
            )

    if suite in ("fast", "retrieval", "full"):
        try:
            from benchmarks.og_bench.metrics import compute_m1, load_probes
        except ImportError:
            import sys as _sys

            _project_root = str(Path.cwd())
            if _project_root not in _sys.path:
                _sys.path.insert(0, _project_root)
            try:
                from benchmarks.og_bench.metrics import (  # type: ignore[import-not-found]
                    compute_m1,
                    load_probes,
                )
            except ImportError as exc:
                console.print(f"[red]Cannot load benchmark metrics module: {exc}[/red]")
                raise typer.Exit(2) from exc

        _probe_path = Path(probe_file) if probe_file else None
        probes = load_probes(_probe_path)
        m1 = compute_m1(engine, probes, query_types=("K", "P", "I"), top_k=5)

        _P5_THRESHOLD = 0.80
        _FPR_THRESHOLD = 0.20
        m1_passed = m1.p_at_5 >= _P5_THRESHOLD and m1.fpr_negative <= _FPR_THRESHOLD
        all_passed = all_passed and m1_passed

        output["m1"] = {
            "p_at_1": m1.p_at_1,
            "p_at_5": m1.p_at_5,
            "r_at_5": m1.r_at_5,
            "mrr": m1.mrr,
            "fpr_negative": m1.fpr_negative,
            "n_queries": m1.n_queries,
            "n_negative": m1.n_negative,
            "p5_threshold": _P5_THRESHOLD,
            "fpr_threshold": _FPR_THRESHOLD,
            "passed": m1_passed,
            "misses": m1.misses,
            "false_positives": m1.false_positives,
        }

        if not as_json:
            vc = "green" if m1_passed else "red"
            miss_lines = "\n".join(f"  {ms}" for ms in m1.misses[:5]) or "  (none)"
            fp_lines = "\n".join(f"  {fp}" for fp in m1.false_positives[:3]) or "  (none)"
            console.print(
                Panel(
                    f"[bold]M1 Retrieval Quality Arm[/bold]\n\n"
                    f"Queries: {m1.n_queries} positive + {m1.n_negative} negative\n"
                    f"P@1:  [bold]{m1.p_at_1:.2f}[/bold]    "
                    f"P@5:  [bold]{m1.p_at_5:.2f}[/bold] (gate ≥{_P5_THRESHOLD})    "
                    f"MRR:  [bold]{m1.mrr:.2f}[/bold]\n"
                    f"FPR:  [bold]{m1.fpr_negative:.2f}[/bold] (gate ≤{_FPR_THRESHOLD})\n\n"
                    f"Misses:\n{miss_lines}\n\n"
                    f"False positives:\n{fp_lines}",
                    border_style=vc,
                )
            )

    if suite == "full":
        try:
            from benchmarks.og_bench.metrics import compute_m2, compute_m4, compute_m7
        except ImportError:
            import sys as _sys2

            _project_root2 = str(Path.cwd())
            if _project_root2 not in _sys2.path:
                _sys2.path.insert(0, _project_root2)
            try:
                from benchmarks.og_bench.metrics import (  # type: ignore[import-not-found]
                    compute_m2,
                    compute_m4,
                    compute_m7,
                )
            except Exception as exc:
                console.print(f"[yellow]M2/M4/M7: cannot load metrics module: {exc}[/yellow]")
                compute_m2 = compute_m4 = compute_m7 = None  # type: ignore[assignment]

        _p = load_probes(Path(probe_file) if probe_file else None)

        if compute_m7 is not None:
            m7 = compute_m7(engine, _p)
            output["m7"] = {
                "p1_rate": m7.p1_rate,
                "p2_rate": m7.p2_rate,
                "p3_rate": m7.p3_rate,
                "n_queries": m7.n_queries,
                "pass1_total": m7.pass1_total,
                "pass2_total": m7.pass2_total,
                "pass3_total": m7.pass3_total,
            }
            if not as_json:
                console.print(
                    Panel(
                        f"[bold]M7 Pass-Depth Distribution[/bold]\n\n"
                        f"Queries: {m7.n_queries}\n"
                        f"Pass-1 sufficient: [bold]{m7.p1_rate:.0%}[/bold]  "
                        f"Pass-2 sufficient: [bold]{m7.p2_rate:.0%}[/bold]  "
                        f"Pass-3 required:   [bold]{m7.p3_rate:.0%}[/bold]",
                        border_style="blue",
                    )
                )

        if compute_m2 is not None:
            m2 = compute_m2(engine, _p)
            output["m2"] = {
                "avg_tokens_pass1": m2.avg_tokens_pass1,
                "avg_tokens_pass2": m2.avg_tokens_pass2,
                "avg_tokens_pass3": m2.avg_tokens_pass3,
                "avg_tokens_total": m2.avg_tokens_total,
                "estimated_usd_per_1k_queries": m2.estimated_usd_per_1k_queries,
                "n_queries": m2.n_queries,
            }
            if not as_json:
                console.print(
                    Panel(
                        f"[bold]M2 Token Cost Model[/bold]\n\n"
                        f"Avg tokens/query: P1={m2.avg_tokens_pass1:.0f}  "
                        f"P2={m2.avg_tokens_pass2:.0f}  P3={m2.avg_tokens_pass3:.0f}  "
                        f"total={m2.avg_tokens_total:.0f}\n"
                        f"Est. cost: [bold]${m2.estimated_usd_per_1k_queries:.4f}[/bold]"
                        f" / 1k queries (uncached input @ $3/Mtok)",
                        border_style="blue",
                    )
                )

        if compute_m4 is not None:
            m4 = compute_m4(engine, _p)
            output["m4"] = {
                "avg_engine_ms": m4.avg_engine_ms,
                "rtt_estimate_ms": m4.rtt_estimate_ms,
                "total_estimate_ms": m4.total_estimate_ms,
                "rtt_per_pass_ms": m4.rtt_per_pass_ms,
                "n_queries": m4.n_queries,
            }
            if not as_json:
                console.print(
                    Panel(
                        f"[bold]M4 Engine Latency Model[/bold]\n\n"
                        f"Avg engine ops:   [bold]{m4.avg_engine_ms:.2f} ms[/bold] / query\n"
                        f"RTT estimate:     [bold]{m4.rtt_estimate_ms:.0f} ms[/bold] "
                        f"(3 passes × {m4.rtt_per_pass_ms:.0f} ms)\n"
                        f"Total estimate:   [bold]{m4.total_estimate_ms:.0f} ms[/bold] / query",
                        border_style="blue",
                    )
                )

    output["passed"] = all_passed
    if as_json:
        print(_json.dumps(output, indent=2))

    if not as_json and not all_passed:
        console.print("[red]One or more benchmark gates FAILED.[/red]")
    elif not as_json and all_passed:
        console.print("[green]All benchmark gates passed.[/green]")

    if not all_passed:
        raise typer.Exit(1)
