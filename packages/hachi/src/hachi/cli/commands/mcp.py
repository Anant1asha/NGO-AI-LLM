"""MCP command group: manage Model Context Protocol server connections."""

from __future__ import annotations

import json

import typer
from rich.console import Console

console = Console()

mcp_app = typer.Typer(help="Manage Model Context Protocol (MCP) server connections.")

_MCP_ENV_OPTION = typer.Option(
    None,
    "--env",
    "-e",
    help="Environment variable as KEY=VALUE (repeatable). "
    "Stored in the .og node and injected when the server starts.",
)

_MCP_OG_TEMPLATE = """\
::node[{name}]
->[:role=mcp]
->[:keywords=mcp, {name}]

::dense
MCP server: {name}
Package: {package}

::config
command: npx
args: -y {package}
"""


@mcp_app.command("list")
def mcp_list(
    as_json: bool = typer.Option(False, "--json", help="Emit the server list as JSON."),
) -> None:
    """List all configured MCP servers and the tools each one exposes.

    MCP servers are declared as .og nodes with role=mcp. Each entry shows the
    server name, npx command, and how many tools it advertises. Servers must
    be running (agent session active) to report an accurate tool count — this
    command reads the static declarations only."""
    from hachi.gateway.workspace import get_skills_dir
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(get_skills_dir())
    nodes = engine.get_nodes_by_role("mcp")

    if as_json:
        servers = [
            {
                "name": n.name,
                "command": n.config.get("command", ""),
                "args": n.config.get("args", ""),
                "env_vars": [k for k in n.config if k.startswith("env_")],
            }
            for n in nodes
        ]
        print(json.dumps({"servers": servers, "count": len(servers)}, indent=2))
        return

    if not nodes:
        console.print(
            "[dim]No MCP servers configured.[/dim]\n"
            "Add one with: [cyan]hachi mcp add <name> <npm-package>[/cyan]"
        )
        return

    console.print(f"[bold]MCP Servers[/bold]  ({len(nodes)} configured)\n")
    for node in nodes:
        command = node.config.get("command", "")
        args = node.config.get("args", "")
        env_keys = [k for k in node.config if k.startswith("env_")]
        env_note = f"  [dim]env: {', '.join(k[4:] for k in env_keys)}[/dim]" if env_keys else ""
        console.print(
            f"  [bold cyan]{node.name}[/bold cyan]  [dim]{command} {args}[/dim]{env_note}"
        )


@mcp_app.command("add")
def mcp_add(
    name: str = typer.Argument(..., help="Short identifier for the server (e.g. 'github')."),
    package: str = typer.Argument(
        ..., help="npm package to run via npx (e.g. '@modelcontextprotocol/server-github')."
    ),
    env: list[str] | None = _MCP_ENV_OPTION,
    as_json: bool = typer.Option(False, "--json", help="Emit the created file path as JSON."),
) -> None:
    """Add a new MCP server by generating an .og node in your skills directory.

    Creates <skills-dir>/mcp-<name>.og with the command, package, and any env
    vars you supply. The server is activated the next time you start the agent.

    Example:
        hachi mcp add github @modelcontextprotocol/server-github \\
            --env GITHUB_TOKEN=ghp_...
    """
    from hachi.gateway.workspace import get_skills_dir

    if not name.replace("-", "").replace("_", "").isalnum():
        console.print(
            f"[red]Invalid name:[/red] {name!r} — use letters, digits, hyphens, underscores only."
        )
        raise typer.Exit(2)

    skills_dir = get_skills_dir()
    dest = skills_dir / f"mcp-{name}.og"
    if dest.exists():
        console.print(
            f"[yellow]Already exists:[/yellow] {dest}\n"
            f"Edit it directly or remove it first with: "
            f"[cyan]hachi mcp remove {name}[/cyan]"
        )
        raise typer.Exit(1)

    og_text = _MCP_OG_TEMPLATE.format(name=name, package=package)

    env_lines: list[str] = []
    for item in env or []:
        if "=" not in item:
            console.print(f"[red]Invalid --env (expected KEY=VALUE):[/red] {item}")
            raise typer.Exit(2)
        key, value = item.split("=", 1)
        env_lines.append(f"env_{key.strip()}: {value.strip()}")
    if env_lines:
        og_text = og_text.rstrip() + "\n" + "\n".join(env_lines) + "\n"

    dest.write_text(og_text, encoding="utf-8")

    if as_json:
        print(json.dumps({"name": name, "file": str(dest), "package": package}, indent=2))
        return

    console.print(
        f"[green]Created[/green] [cyan]{dest.name}[/cyan]\n"
        f"Package: {package}\n"
        f"Restart the agent to activate this MCP server.\n"
        f"[dim]Edit {dest} to add env vars or change the command.[/dim]"
    )


@mcp_app.command("remove")
def mcp_remove(
    name: str = typer.Argument(..., help="Server name as used in `hachi mcp list`."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Remove a user-added MCP server by deleting its .og node file.

    Only removes files created by `hachi mcp add` (named mcp-<name>.og in
    the user skills directory). System-managed or bundled MCP nodes are not touched.
    """
    from hachi.gateway.workspace import get_skills_dir

    skills_dir = get_skills_dir()
    target = skills_dir / f"mcp-{name}.og"
    if not target.exists():
        console.print(
            f"[red]Not found:[/red] mcp-{name}.og in {skills_dir}\n"
            f"Run [cyan]hachi mcp list[/cyan] to see configured servers."
        )
        raise typer.Exit(1)

    if not yes:
        confirm = typer.confirm(f"Remove MCP server '{name}' ({target.name})?")
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    target.unlink()
    console.print(f"[green]Removed[/green] {target.name}")
