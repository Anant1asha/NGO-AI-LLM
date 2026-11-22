"""
Workspace Manager

Manages the ~/.hachi/ directory structure — the local home of every Hachi installation.
Handles first-run setup, configuration loading, brain loading, and the device permissions wizard.
"""

import logging
import shutil
from pathlib import Path

from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.paths import ensure_directories, get_hachi_paths
from hachi.core.permissions import generate_permissions_og
from hachi.core.skill_packs import install_core_skill_packs, install_skill_pack

logger = logging.getLogger(__name__)

_LEGACY_BRAND_TOKEN = "tokoboros"

# ==========================================
# Path Resolution
# ==========================================


def get_workspace_dir() -> Path:
    """Returns the canonical global config directory for Hachi."""
    return get_hachi_paths().config_dir


def get_skills_dir() -> Path:
    """Returns the absolute path to the user skill directory."""
    skills_dir = get_hachi_paths().skills_dir
    if not skills_dir.exists():
        ensure_workspace()
    return skills_dir


def get_permissions_file() -> Path:
    """Returns the absolute path to the device-permissions.og manifest."""
    return get_hachi_paths().permissions_file


# ==========================================
# Workspace Bootstrap
# ==========================================


def _heal_legacy_brand(brain_file: Path, bundled_default: Path) -> bool:
    """Migrate a brain.og file that still contains the legacy "tokoboros" brand name.

    If ``brain_file`` exists and its content contains the legacy brand token
    (case-insensitive), this function:

    1. Backs up the existing file to ``<brain_file>.legacy-bak`` (skips backup if the
       ``.legacy-bak`` already exists so repeated calls are idempotent).
    2. Overwrites ``brain_file`` with the content of ``bundled_default``.
    3. Logs an INFO line describing the migration.

    Only modifies the file when the legacy brand token is present; fresh or already-
    migrated installs are left untouched.

    Args:
        brain_file: Absolute path to the local brain.og that should be checked.
        bundled_default: Absolute path to the canonical bundled brain.og.

    Returns:
        ``True`` if the file was migrated, ``False`` if no action was needed.
    """
    if not brain_file.exists():
        return False
    if not bundled_default.exists():
        return False

    content = brain_file.read_text(encoding="utf-8")
    if _LEGACY_BRAND_TOKEN not in content.lower():
        return False

    # Back up before overwriting (never clobber an existing backup).
    bak_path = brain_file.with_suffix(brain_file.suffix + ".legacy-bak")
    if not bak_path.exists():
        shutil.copy2(brain_file, bak_path)

    shutil.copy2(bundled_default, brain_file)
    logger.info(
        "Migrated legacy brain.og identity (tokoboros→hachi): %s → backed up to %s",
        brain_file,
        bak_path,
    )
    return True


def ensure_workspace():
    """
    Creates the default workspace structure if it doesn't exist.
    Does NOT trigger the permissions wizard — that is handled separately
    by ensure_device_permissions() during the boot sequence.
    """
    paths = get_hachi_paths()
    ensure_directories(paths)

    # Install only core, local-first skill packs by default.
    skills_dir = paths.skills_dir
    if not any(skills_dir.iterdir()):
        try:
            install_core_skill_packs(skills_dir)
        except Exception:
            pass

    bundled_default = Path(__file__).parent.parent / "default_skills" / "brain.og"

    # Create default brain.og if it doesn't exist
    brain_file = paths.brain_file
    if not brain_file.exists():
        if bundled_default.exists():
            shutil.copy2(bundled_default, brain_file)
        else:
            # Minimal fallback if default_skills is missing
            with open(brain_file, "w", encoding="utf-8") as f:
                f.write(
                    "::node[system]\n"
                    "->[:role=persona]\n"
                    "::dense\n"
                    "You are Hachi, an elite autonomous agent.\n"
                )
    else:
        # Heal any pre-rename install that still carries the legacy brand.
        _heal_legacy_brand(brain_file, bundled_default)

    # Also heal the secondary copy that install_core_skill_packs may have placed under
    # skills_dir/brain.og (present on older installs).
    secondary_brain = skills_dir / "brain.og"
    _heal_legacy_brand(secondary_brain, bundled_default)

    # Create canonical TOML config if it doesn't exist
    if not paths.global_config_toml.exists():
        write_global_config(load_effective_config(paths=paths), paths=paths)


# ==========================================
# Config & Brain Loaders
# ==========================================


def load_config() -> dict:
    """
    Loads the effective Hachi configuration.
    Falls back to defaults if not found.
    """
    ensure_workspace()
    return load_effective_config().model_dump(mode="python", exclude_none=True)


def install_optional_skill_pack(pack_id: str) -> list[Path]:
    """Install an optional built-in skill pack into the user skills directory."""
    ensure_workspace()
    return install_skill_pack(pack_id, get_hachi_paths().skills_dir)


def load_brain() -> str:
    """Load and render the core brain.og into a structured system prompt.

    Parses brain.og through the full OGFile pipeline, then renders each node
    into a clean, layered system prompt. This gives the orchestrator its
    identity, rules, and decision framework.

    Rendering order (optimized for LLM attention):
        1. Identity (::dense + ::full from persona nodes) — WHO you are
        2. Warnings (::warning from all nodes) — hard constraints, highest priority
        3. Rules (::full from rule nodes) — execution principles
        4. Everything else (steps, examples, etc.)

    Returns:
        A formatted system prompt string (~1000-1500 tokens).
    """
    brain_file = get_hachi_paths().brain_file
    if not brain_file.exists():
        ensure_workspace()

    try:
        from hachi.og_engine.parser import parse_og_file

        og_file = parse_og_file(str(brain_file))
    except Exception:
        # Fallback: if parsing fails, load raw text (backward compat)
        with open(brain_file, encoding="utf-8") as f:
            return f.read()

    return _render_brain_prompt(og_file)


def _render_brain_prompt(og_file) -> str:
    """Render an OGFile into a structured system prompt for the orchestrator.

    Separates content by node role and assembles them in optimal order
    for LLM attention: identity first, then hard constraints, then rules.

    Args:
        og_file: The parsed OGFile from brain.og.

    Returns:
        A formatted system prompt string.
    """
    sections = []

    # Layer 1 — Identity (persona nodes: dense + full)
    for node in og_file.nodes:
        if node.role in ("persona", "identity", "core_agent"):
            if node.dense:
                sections.append(node.dense)
            if node.full:
                sections.append(node.full)

    # Layer 2 — Hard Constraints (warnings from ALL nodes)
    warnings = [node.warning for node in og_file.nodes if node.warning]
    if warnings:
        sections.append("--- HARD CONSTRAINTS ---\n" + "\n".join(warnings))

    # Layer 3 — Rules (rule nodes: full content)
    for node in og_file.nodes:
        if node.role == "rule" and node.full:
            sections.append(node.full)

    # Layer 4 — Steps from any node (ordered instructions)
    for node in og_file.nodes:
        if node.steps and node.role == "rule":
            step_text = "\n".join(f"{i}. {s}" for i, s in enumerate(node.steps, 1))
            sections.append(step_text)

    # Fallback: if nothing was extracted, return raw file content
    if not sections:
        with open(str(og_file.source_file), encoding="utf-8") as f:
            return f.read()

    return "\n\n".join(sections)


# ==========================================
# Device Permissions Wizard
# ==========================================

# Tier metadata used by both the wizard and the CLI
TIER_INFO = {
    "sandbox": {
        "emoji": "[yellow]Sandbox[/yellow]",
        "label": "Sandbox",
        "description": "Desktop only, no terminal commands",
        "audience": "trying things out safely",
    },
    "guided": {
        "emoji": "[green]Guided[/green]",
        "label": "Guided",
        "description": "Choose folders + safe terminal commands",
        "audience": "everyday personal use",
    },
    "unrestricted": {
        "emoji": "[red]Unrestricted[/red]",
        "label": "Unrestricted",
        "description": "Full filesystem + full terminal access",
        "audience": "developers and power users",
    },
}


def run_permissions_wizard(console) -> str:
    """
    Interactive first-run wizard that generates device-permissions.og.

    Presents the user with 3 tier choices, optionally asks for custom paths
    in Guided mode, then writes the file.

    Args:
        console: A rich.console.Console instance for rendering.

    Returns:
        The tier that was selected ('sandbox', 'guided', 'unrestricted').
    """
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table

    # Header
    console.print()
    console.print(
        Panel(
            "[bold]Device Permissions Setup[/bold]\n\n"
            "Control what Hachi can access on your device.\n"
            "You can change this anytime by editing:\n"
            "[cyan]~/.hachi/device-permissions.og[/cyan]",
            title="[bold magenta]Hachi[/bold magenta]",
            border_style="magenta",
            padding=(1, 2),
        )
    )

    # Tier selection table
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2), expand=True)
    table.add_column("Option", style="bold cyan", width=8, no_wrap=True)
    table.add_column("Tier", min_width=12, no_wrap=True)
    table.add_column("Access", ratio=2, overflow="fold")
    table.add_column("Best For", style="dim", ratio=2, overflow="fold")

    table.add_row(
        "[1]",
        TIER_INFO["sandbox"]["emoji"],
        TIER_INFO["sandbox"]["description"],
        TIER_INFO["sandbox"]["audience"],
    )
    table.add_row(
        "[2]",
        TIER_INFO["guided"]["emoji"] + " *",
        TIER_INFO["guided"]["description"],
        TIER_INFO["guided"]["audience"],
    )
    table.add_row(
        "[3]",
        TIER_INFO["unrestricted"]["emoji"],
        TIER_INFO["unrestricted"]["description"],
        TIER_INFO["unrestricted"]["audience"],
    )

    console.print()
    console.print(table)
    console.print("  [dim]* Recommended[/dim]\n")

    # Prompt for choice
    choice = Prompt.ask(
        "  Choose your access tier",
        choices=["1", "2", "3"],
        default="2",
    )

    tier_map = {"1": "sandbox", "2": "guided", "3": "unrestricted"}
    tier = tier_map[choice]
    custom_paths = None

    # For Guided, ask for custom paths
    if tier == "guided":
        console.print()
        home = Path.home()
        default_paths = f"{home / 'Desktop'}, {home / 'Downloads'}, {home / 'Documents'}"

        console.print(f"  Default folders: [cyan]{default_paths}[/cyan]")
        path_input = Prompt.ask(
            "  Enter folders to allow [dim](comma-separated, or 'default')[/dim]",
            default="default",
        )

        if path_input.strip().lower() != "default":
            custom_paths = [p.strip() for p in path_input.split(",") if p.strip()]

    # Generate and write the file
    content = generate_permissions_og(tier, custom_paths)
    permissions_file = get_permissions_file()
    permissions_file.parent.mkdir(parents=True, exist_ok=True)

    with open(permissions_file, "w", encoding="utf-8") as f:
        f.write(content)

    # Confirmation
    info = TIER_INFO[tier]
    console.print()
    console.print(
        Panel(
            f"[bold green]Permissions saved![/bold green]\n\n"
            f"Tier: {info['emoji']}\n"
            f"Access: {info['description']}\n"
            f"File: [cyan]~/.hachi/device-permissions.og[/cyan]",
            border_style="green",
            padding=(0, 2),
        )
    )

    return tier


def ensure_device_permissions(console) -> Path:
    """
    Checks for device-permissions.og. If missing, runs the interactive wizard.

    Args:
        console: A rich.console.Console instance for rendering.

    Returns:
        The path to the device-permissions.og file.
    """
    permissions_file = get_permissions_file()
    if not permissions_file.exists():
        run_permissions_wizard(console)
    return permissions_file


def show_current_permissions(console):
    """
    Display the current permission configuration in a clean, readable format.

    Args:
        console: A rich.console.Console instance for rendering.
    """
    from rich.panel import Panel
    from rich.table import Table

    from hachi.core.permissions import PermissionGate

    permissions_file = get_permissions_file()

    if not permissions_file.exists():
        console.print(
            "[yellow]No device-permissions.og found. Run 'hachi run' to set up "
            "permissions.[/yellow]"
        )
        return

    gate = PermissionGate(permissions_file)

    # Build info table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold", width=20)
    table.add_column("Value", width=50)

    tier_info = TIER_INFO.get(gate.tier, TIER_INFO["sandbox"])
    table.add_row("Tier", tier_info["emoji"])

    # Filesystem paths
    if gate._fs.allow_all:
        table.add_row("Allowed Folders", "[green]All[/green]")
    else:
        paths = ", ".join(p.name for p in gate._fs.allowed_paths)
        table.add_row("Allowed Folders", f"[cyan]{paths}[/cyan]")

    blocked = ", ".join(p.name for p in gate._fs.blocked_paths)
    table.add_row("Blocked Folders", f"[red]{blocked}[/red]")

    table.add_row("Write Access", "[green]Yes[/green]" if gate._fs.allow_write else "[red]No[/red]")
    table.add_row(
        "Delete Access", "[green]Yes[/green]" if gate._fs.allow_delete else "[red]No[/red]"
    )

    # Terminal
    if gate._term.enabled:
        if gate._term.allow_all:
            table.add_row("Terminal", "[green]Full Access[/green]")
        else:
            cmd_count = len(gate._term.allowed_commands)
            table.add_row("Terminal", f"[green]Enabled[/green] ({cmd_count} allowed commands)")
    else:
        table.add_row("Terminal", "[red]Disabled[/red]")

    # MCP
    table.add_row(
        "MCP Filesystem",
        "[green]Enabled[/green]" if gate.is_mcp_filesystem_enabled() else "[red]Disabled[/red]",
    )

    console.print()
    console.print(
        Panel(
            table,
            title="[bold magenta]Device Permissions[/bold magenta]",
            subtitle="[dim]~/.hachi/device-permissions.og[/dim]",
            border_style="magenta",
            padding=(1, 1),
        )
    )
