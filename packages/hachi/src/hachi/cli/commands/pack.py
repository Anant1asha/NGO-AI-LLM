"""Pack command group: manage .ogpack skill packs (install, list, remove, update)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from hachi.core.paths import get_hachi_paths

console = Console()

ogpack_app = typer.Typer(help="Manage .ogpack skill packs (install, list, remove, update).")
_pack_index_app = typer.Typer(help="Manage the community pack index cache.")
ogpack_app.add_typer(_pack_index_app, name="index")


def _get_skills_dir() -> Path:
    return Path(get_hachi_paths().skills_dir)


@ogpack_app.command("install")
def ogpack_install(
    source: str = typer.Argument(..., help="Path to a .ogpack archive or unpacked directory."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip consent confirmation prompt."),
) -> None:
    """Install a skill pack from a local .ogpack archive or directory.

    Renders a consent sheet showing declared scopes before copying any files.
    If the pack is already installed and the update widens scopes, a diff is shown.
    """
    from hachi.core.og_pack import (
        get_installed_manifest,
        install_ogpack_from_archive,
        install_ogpack_from_dir,
        parse_pack_toml,
        render_consent_sheet,
    )

    skills_dir = _get_skills_dir()
    source_path = Path(source).resolve()

    if not source_path.exists():
        console.print(f"[red]Not found:[/red] {source_path}")
        raise typer.Exit(1)

    try:
        if source_path.is_dir():
            manifest_preview = parse_pack_toml((source_path / "pack.toml").read_bytes())
        else:
            import tarfile
            import tempfile

            from hachi.core.archive_safety import ArchiveSecurityError, safe_extract

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                with tarfile.open(source_path, "r:*") as tf:
                    safe_extract(tf, tmp_path)
                candidates = list(tmp_path.rglob("pack.toml"))
                if not candidates:
                    console.print("[red]No pack.toml found in archive.[/red]")
                    raise typer.Exit(1)
                manifest_preview = parse_pack_toml(candidates[0].read_bytes())
    except ArchiveSecurityError as exc:
        console.print(f"[red]Archive rejected (security):[/red] {exc}")
        raise typer.Exit(1) from exc
    except (FileNotFoundError, ValueError, KeyError) as exc:
        console.print(f"[red]Cannot read pack.toml:[/red] {exc}")
        raise typer.Exit(1) from exc

    old_manifest = get_installed_manifest(manifest_preview.id, skills_dir)
    is_update = old_manifest is not None

    sheet = render_consent_sheet(manifest_preview, update=is_update)
    console.print(sheet)

    if not yes:
        confirmed = typer.confirm("Proceed?", default=False)
        if not confirmed:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    try:
        if source_path.is_dir():
            manifest, files = install_ogpack_from_dir(
                source_path,
                skills_dir,
                source=str(source_path),
                confirm=True,
                old_manifest=old_manifest,
            )
        else:
            manifest, files = install_ogpack_from_archive(
                source_path,
                skills_dir,
                source=str(source_path),
                confirm=True,
                old_manifest=old_manifest,
            )
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Install failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    action = "Updated" if is_update else "Installed"
    console.print(
        f"[green]{action}[/green] [bold]{manifest.id}[/bold] v{manifest.semver}"
        f" — {len(files)} skill file(s)"
    )


@ogpack_app.command("list")
def ogpack_list() -> None:
    """List all installed skill packs."""
    from hachi.core.og_pack import list_ogpacks

    packs = list_ogpacks(_get_skills_dir())
    if not packs:
        console.print("[dim]No skill packs installed.[/dim]")
        return

    for pack in packs:
        scopes_str = ", ".join(pack.scope_ids) if pack.scope_ids else "none"
        console.print(
            f"[bold]{pack.id}[/bold] v{pack.semver}  ({pack.og_file_count} skill(s))\n"
            f"  {pack.description or '—'}\n"
            f"  scopes: {scopes_str}"
        )


@ogpack_app.command("remove")
def ogpack_remove(
    pack_id: str = typer.Argument(..., help="Pack id to remove (from 'pack list')."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Remove an installed skill pack by id."""
    from hachi.core.og_pack import remove_ogpack

    if not yes:
        confirmed = typer.confirm(f"Remove pack '{pack_id}'?", default=False)
        if not confirmed:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    if remove_ogpack(pack_id, _get_skills_dir()):
        console.print(f"[green]Removed[/green] {pack_id}")
    else:
        console.print(f"[yellow]Pack not found:[/yellow] {pack_id}")
        raise typer.Exit(1)


@ogpack_app.command("update")
def ogpack_update(
    source: str = typer.Argument(..., help="Path to updated .ogpack archive or directory."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip consent confirmation."),
) -> None:
    """Update an installed pack from a new archive.

    If the new version requests wider scopes, a diff is shown before proceeding.
    Equivalent to 'pack install' but always compares against the current version.
    """
    from hachi.core.og_pack import (
        get_installed_manifest,
        install_ogpack_from_archive,
        install_ogpack_from_dir,
        parse_pack_toml,
        render_consent_sheet,
        render_scope_diff,
    )

    skills_dir = _get_skills_dir()
    source_path = Path(source).resolve()

    if not source_path.exists():
        console.print(f"[red]Not found:[/red] {source_path}")
        raise typer.Exit(1)

    try:
        if source_path.is_dir():
            manifest_preview = parse_pack_toml((source_path / "pack.toml").read_bytes())
        else:
            import tarfile
            import tempfile

            from hachi.core.archive_safety import ArchiveSecurityError, safe_extract

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                with tarfile.open(source_path, "r:*") as tf:
                    safe_extract(tf, tmp_path)
                candidates = list(tmp_path.rglob("pack.toml"))
                if not candidates:
                    console.print("[red]No pack.toml found in archive.[/red]")
                    raise typer.Exit(1)
                manifest_preview = parse_pack_toml(candidates[0].read_bytes())
    except ArchiveSecurityError as exc:
        console.print(f"[red]Archive rejected (security):[/red] {exc}")
        raise typer.Exit(1) from exc
    except (FileNotFoundError, ValueError, KeyError) as exc:
        console.print(f"[red]Cannot read pack.toml:[/red] {exc}")
        raise typer.Exit(1) from exc

    old_manifest = get_installed_manifest(manifest_preview.id, skills_dir)
    if old_manifest is None:
        console.print(
            f"[yellow]Pack '{manifest_preview.id}' is not installed"
            " — use 'pack install' instead.[/yellow]"
        )
        raise typer.Exit(1)

    diff = render_scope_diff(old_manifest, manifest_preview)
    if diff:
        console.print(diff)
    sheet = render_consent_sheet(manifest_preview, update=True)
    console.print(sheet)

    if not yes:
        confirmed = typer.confirm("Proceed with update?", default=False)
        if not confirmed:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    try:
        if source_path.is_dir():
            manifest, files = install_ogpack_from_dir(
                source_path,
                skills_dir,
                source=str(source_path),
                confirm=False,
                old_manifest=old_manifest,
            )
        else:
            manifest, files = install_ogpack_from_archive(
                source_path,
                skills_dir,
                source=str(source_path),
                confirm=False,
                old_manifest=old_manifest,
            )
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Update failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(
        f"[green]Updated[/green] [bold]{manifest.id}[/bold] v{old_manifest.semver}"
        f" → v{manifest.semver}  ({len(files)} skill file(s))"
    )


@ogpack_app.command("search")
def ogpack_search(
    query: str = typer.Argument(..., help="Search term (id, name, or description)."),
    index_url: str | None = typer.Option(None, "--index-url", help="Override index URL."),
) -> None:
    """Search the community pack index for matching skill packs."""
    from hachi.core.pack_index import DEFAULT_INDEX_URL, fetch_pack_index

    state_dir = get_hachi_paths().state_dir
    url = index_url or DEFAULT_INDEX_URL
    try:
        index = fetch_pack_index(state_dir, url=url)
    except RuntimeError as exc:
        console.print(f"[red]Cannot load index:[/red] {exc}")
        raise typer.Exit(1) from exc

    results = index.search(query)
    if not results:
        console.print(f"[dim]No packs found matching '{query}'.[/dim]")
        return

    for entry in results:
        scopes_str = ", ".join(entry.scopes) if entry.scopes else "none"
        console.print(
            f"[bold]{entry.id}[/bold] v{entry.semver}\n"
            f"  {entry.description or '—'}\n"
            f"  source: {entry.source}  scopes: {scopes_str}"
        )


@_pack_index_app.command("refresh")
def pack_index_refresh(
    index_url: str | None = typer.Option(None, "--index-url", help="Override index URL."),
) -> None:
    """Force-refresh the local community pack index cache."""
    from hachi.core.pack_index import DEFAULT_INDEX_URL, fetch_pack_index

    state_dir = get_hachi_paths().state_dir
    url = index_url or DEFAULT_INDEX_URL
    try:
        index = fetch_pack_index(state_dir, url=url, force=True)
    except RuntimeError as exc:
        console.print(f"[red]Refresh failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(f"[green]Index refreshed[/green] — {len(index.packs)} pack(s) available.")


@_pack_index_app.command("show")
def pack_index_show() -> None:
    """Show all packs in the cached community index."""
    from hachi.core.pack_index import load_cached_index

    state_dir = get_hachi_paths().state_dir
    index = load_cached_index(state_dir)
    if index is None:
        console.print("[dim]No index cached. Run: hachi pack index refresh[/dim]")
        return

    if not index.packs:
        console.print("[dim]Index is empty.[/dim]")
        return

    for entry in index.packs:
        console.print(f"[bold]{entry.id}[/bold] v{entry.semver}  {entry.description or '—'}")
