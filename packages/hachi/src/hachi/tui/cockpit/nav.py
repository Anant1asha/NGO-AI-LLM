"""Navigation registry for the Hachi Cockpit.

Pure data module — no Textual imports. Fully unit-testable.
Defines the 12 views, their g-mnemonics, footer key hints, and command palette items.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ViewMeta:
    """Metadata for a single cockpit view."""

    view_id: str
    """Stable identifier used throughout the codebase."""
    label: str
    """Human-readable display name."""
    mnemonic: str
    """Single character after 'g' that navigates to this view (e.g. 'c' for 'gc')."""
    altitude: Literal["focus", "cockpit"]
    """'focus' for chat (operator focus mode), 'cockpit' for all data views."""


@dataclass(frozen=True)
class FooterKey:
    """A single key-hint pair shown in the footer."""

    key: str
    label: str


@dataclass(frozen=True)
class PaletteItem:
    """A single entry in the command palette."""

    section: Literal["go to", "do", "open"]
    label: str
    key: str
    """Keyboard shortcut hint (may be empty string)."""
    action: str
    """Action token the screen can dispatch. For 'go to' views this is 'go:<view_id>'."""


# ---------------------------------------------------------------------------
# The canonical ordered list of 12 views.
# Order and mnemonics EXACTLY match the help keymap in the design (Hachi Cockpit.dc.html).
# ---------------------------------------------------------------------------
VIEWS: tuple[ViewMeta, ...] = (
    ViewMeta(view_id="chat",        label="chat",        mnemonic="c", altitude="focus"),
    ViewMeta(view_id="dashboard",   label="dashboard",   mnemonic="d", altitude="cockpit"),
    ViewMeta(view_id="agents",      label="agents",      mnemonic="a", altitude="cockpit"),
    ViewMeta(view_id="tasks",       label="tasks",       mnemonic="t", altitude="cockpit"),
    ViewMeta(view_id="approvals",   label="approvals",   mnemonic="p", altitude="cockpit"),
    ViewMeta(view_id="governance",  label="governance",  mnemonic="g", altitude="cockpit"),
    ViewMeta(view_id="memory",      label="memory",      mnemonic="m", altitude="cockpit"),
    ViewMeta(view_id="skills",      label="skills",      mnemonic="k", altitude="cockpit"),
    ViewMeta(view_id="audit",       label="audit",       mnemonic="l", altitude="cockpit"),
    ViewMeta(view_id="resources",   label="resources",   mnemonic="r", altitude="cockpit"),
    ViewMeta(view_id="connections", label="connections", mnemonic="n", altitude="cockpit"),
    ViewMeta(view_id="settings",    label="settings",    mnemonic="s", altitude="cockpit"),
)

# Lookup maps derived from VIEWS — built once at import time.
_BY_ID: dict[str, ViewMeta] = {v.view_id: v for v in VIEWS}
_BY_MNEMONIC: dict[str, ViewMeta] = {v.mnemonic: v for v in VIEWS}


def view_by_id(view_id: str) -> ViewMeta | None:
    """Return the ViewMeta for *view_id*, or None if not found."""
    return _BY_ID.get(view_id)


def view_by_mnemonic(char: str) -> ViewMeta | None:
    """Return the ViewMeta whose g-mnemonic matches *char*, or None."""
    return _BY_MNEMONIC.get(char)


# ---------------------------------------------------------------------------
# Per-view footer key hints.
# Mirrors footerFor(v) in the design prototype exactly.
# ---------------------------------------------------------------------------
_FOOTER_KEYS: dict[str, list[FooterKey]] = {
    "chat": [
        FooterKey("↵", "send"),
        FooterKey("⇧↵", "newline"),
        FooterKey("⌃K", "palette"),
        FooterKey("⌃O", "cockpit"),
        FooterKey("⎋", "interrupt"),
    ],
    "dashboard": [
        FooterKey("↵", "drill in"),
        FooterKey("a", "approvals"),
        FooterKey("t", "tasks"),
        FooterKey("r", "resources"),
        FooterKey("l", "ledger"),
    ],
    "agents": [
        FooterKey("↵", "trace"),
        FooterKey("w", "watch"),
        FooterKey("x", "cancel"),
        FooterKey("r", "retry"),
        FooterKey("d", "delegate"),
        FooterKey("/", "filter"),
    ],
    "tasks": [
        FooterKey("↵", "detail"),
        FooterKey("P", "pause"),
        FooterKey("Re", "resume"),
        FooterKey("X", "cancel"),
        FooterKey("R", "retry"),
        FooterKey("/", "filter"),
    ],
    "approvals": [
        FooterKey("y", "allow"),
        FooterKey("A", "always"),
        FooterKey("n", "deny"),
        FooterKey("␣", "select"),
        FooterKey("Y", "all"),
        FooterKey("N", "none"),
    ],
    "governance": [
        FooterKey("e", "edit"),
        FooterKey("T", "tier"),
        FooterKey("G", "gate"),
        FooterKey("H", "hot-reload"),
    ],
    "memory": [
        FooterKey("/", "search"),
        FooterKey("e", "edit"),
        FooterKey("x", "delete"),
        FooterKey("a", "add fact"),
    ],
    "skills": [
        FooterKey("↵", "3-pass"),
        FooterKey("E", "edit"),
        FooterKey("n", "new"),
        FooterKey("x", "uninstall"),
        FooterKey("/", "filter"),
    ],
    "audit": [
        FooterKey("f", "follow"),
        FooterKey("/", "filter"),
        FooterKey("w", "watch ⚠"),
        FooterKey("E", "export"),
    ],
    "resources": [
        FooterKey("r", "refresh"),
        FooterKey("↔", "scope"),
        FooterKey("↵", "filter audit"),
    ],
    "connections": [
        FooterKey("+", "add"),
        FooterKey("t", "test"),
        FooterKey("r", "retry"),
        FooterKey("d", "disconnect"),
    ],
    "settings": [
        FooterKey("e", "edit"),
        FooterKey("m", "switch model"),
        FooterKey("✓", "validate"),
    ],
}


def footer_keys(view_id: str) -> list[FooterKey]:
    """Return the ordered footer key-hints for *view_id*.

    Returns an empty list for unknown view_ids.
    """
    return _FOOTER_KEYS.get(view_id, [])


# ---------------------------------------------------------------------------
# Command palette items.
# Mirrors paletteAll() in the design prototype.
# ---------------------------------------------------------------------------

def palette_items() -> list[PaletteItem]:
    """Return the full command palette item list.

    Items are grouped by section in order: 'go to', 'do', 'open'.
    The screen filters this list by the user's search query.
    """
    items: list[PaletteItem] = []

    # --- go to ---
    for v in VIEWS:
        items.append(PaletteItem(
            section="go to",
            label=v.label,
            key=f"g{v.mnemonic}",
            action=f"go:{v.view_id}",
        ))

    # --- do ---
    items.extend([
        PaletteItem(
            section="do", label="approve all pending",
            key="", action="do:approve_all",
        ),
        PaletteItem(
            section="do", label="require approval for ungated tools",
            key="G", action="do:gate_ungated",
        ),
        PaletteItem(
            section="do", label="switch model",
            key="m", action="do:switch_model",
        ),
        PaletteItem(
            section="do", label="compact memory now",
            key="", action="do:compact_memory",
        ),
        PaletteItem(
            section="do", label="export audit (jsonl)",
            key="E", action="do:export_audit",
        ),
    ])

    # --- open ---
    items.extend([
        PaletteItem(
            section="open", label="session: AI funding one-pager",
            key="", action="open:session_latest",
        ),
        PaletteItem(
            section="open", label="skill: research-protocol",
            key="", action="open:skill_research",
        ),
        PaletteItem(
            section="open", label='memory: "Acme raised $40M"',
            key="", action="open:memory_latest",
        ),
    ])

    return items
