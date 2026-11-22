"""SkillsView — Installed skills list with OG 3-pass inspector (Wave-3).

Left pane: selectable list with columns [use, skill, stale] + footer tab line.
Right pane: OG inspector for the selected skill — pass1 index / pass2 dense /
            pass3 full token costs from a matching OgNode (matched by name);
            falls back to the skill's own fields if no node found.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from hachi.tui.cockpit.base import CockpitView
from hachi.tui.theme import (
    AMBER,
    BORDER_MUTED,
    BRAND,
    DANGER,
    FOREGROUND,
    GREEN,
    MUTED,
    NAVY,
    SURFACE,
)

if TYPE_CHECKING:
    from hachi.client.models import OgNode, Skill
    from hachi.tui.cockpit.data import CockpitData


def _stale_badge(skill: Skill) -> tuple[str, str]:
    """Return (badge_text, color) for the stale column."""
    if not skill.stale:
        return ("", MUTED)
    lu = skill.last_used or "never"
    return (f"{lu} !", AMBER if lu != "never" else DANGER)


def _skill_list_text(skills: list[Skill], selected: int) -> Text:
    """Render the skills list table."""
    t = Text()
    # header
    t.append(f"{'use':<8}", style=MUTED)
    t.append(f"{'skill':<32}", style=MUTED)
    t.append("stale\n", style=MUTED)
    t.append("─" * 60 + "\n", style=BORDER_MUTED)

    for i, skill in enumerate(skills):
        is_sel = i == selected
        border = "| " if is_sel else "  "
        border_col = BRAND if is_sel else BORDER_MUTED
        t.append(border, style=border_col)

        # use count column
        uses_str = skill.uses[:6] if skill.uses else "0"
        use_col = FOREGROUND if is_sel else MUTED
        t.append(f"{uses_str:<8}", style=use_col)

        # skill name column
        name_col = FOREGROUND if is_sel else (MUTED if not skill.stale else MUTED)
        t.append(f"{skill.name[:30]:<32}", style=name_col)

        # stale column
        badge, badge_col = _stale_badge(skill)
        t.append(f"{badge:<12}", style=badge_col)
        t.append("\n")

    if not skills:
        t.append("  no skills installed\n", style=MUTED)
    return t


def _og_inspector_text(skill: Skill, node: OgNode | None) -> Text:
    """Render the OG 3-pass inspector for a skill."""
    t = Text()
    t.append("og inspector  ", style=MUTED)
    t.append("▸  ", style=BRAND)
    t.append(skill.name + "\n\n", style=FOREGROUND)

    # -- pass 1: index -------------------------------------------------------
    idx_tokens = node.index if node else 0
    t.append("pass 1  ", style=NAVY)
    t.append("index\n", style=f"bold {NAVY}")
    t.append(f"  keywords: {skill.name.replace('-', ', ')} · routing hit\n", style=MUTED)
    t.append(f"  ~{idx_tokens} tok\n\n", style=MUTED)

    # -- pass 2: dense -------------------------------------------------------
    dense_tokens = node.dense if node else 0
    t.append("pass 2  ", style=AMBER)
    t.append("dense\n", style=f"bold {AMBER}")
    t.append(f"  {skill.desc[:60]}\n", style=MUTED)
    t.append(f"  ~{dense_tokens} tok\n\n", style=MUTED)

    # -- pass 3: full --------------------------------------------------------
    full_tokens = node.full if node else 0
    t.append("pass 3  ", style=GREEN)
    t.append("load\n", style=f"bold {GREEN}")
    t.append("  [Enter load full]", style=NAVY)
    t.append(f"  est {full_tokens} tok\n\n", style=MUTED)

    # -- deps / metadata ------------------------------------------------
    t.append("─" * 40 + "\n", style=BORDER_MUTED)
    if node and node.deps:
        t.append("requires  ", style=MUTED)
        t.append("  ".join(node.deps[:4]) + "\n", style=MUTED)
    t.append("used      ", style=MUTED)
    t.append(f"{skill.uses}  ·  last {skill.last_used}\n", style=MUTED)
    t.append("source    ", style=MUTED)
    t.append(f"~/.hachi/skills/{skill.name}.og\n", style=MUTED)
    if node:
        t.append("kind      ", style=MUTED)
        t.append(node.kind + "\n", style=MUTED)
    return t


class SkillsView(CockpitView):  # type: ignore[misc]
    """Installed skills list with OG 3-pass inspector.

    Layout
    ------
    Left pane (flex): selectable rows [use · skill · stale] + "tabs" footer line.
    Right pane (340 cols): OG inspector — pass1 index / pass2 dense / pass3 full
                           token costs; deps, source, usage.  OgNode matched by
                           ``skill.name``; falls back to skill's own fields if absent.

    Data used
    ---------
    data.skills()  -> list[Skill]  (id, name, desc, uses, last_used, stale)
    data.og()      -> list[OgNode]  (id, name, kind, index, dense, full, deps)

    Hooks
    -----
    move_selection(delta)   — j/k moves the skill list selection and updates inspector.
    toggle_inspector()      — show/hide the right-side OG inspector pane.
    """

    view_id: ClassVar[str] = "skills"

    DEFAULT_CSS = f"""
    SkillsView {{
        height: 1fr;
        width: 1fr;
        background: {SURFACE};
    }}
    #sk-list-pane {{
        border-right: solid {BORDER_MUTED};
        min-width: 40;
        height: 1fr;
        overflow-y: auto;
        padding: 0 0;
    }}
    #sk-list {{
        padding: 1 1;
        height: auto;
    }}
    #sk-tabs {{
        border-top: solid {BORDER_MUTED};
        padding: 0 1;
        height: 1;
        color: {MUTED};
    }}
    #sk-inspector-pane {{
        width: 42;
        padding: 1 1;
        overflow-y: auto;
        height: 1fr;
    }}
    """

    _selected: int = 0
    _skills: list[Skill] = []
    _og_nodes: list[OgNode] = []
    _inspector_visible: bool = True
    _data: CockpitData | None = None

    def compose(self) -> ComposeResult:  # noqa: D102
        with Horizontal():
            with Vertical(id="sk-list-pane"):
                yield Static("", id="sk-list")
                yield Static("tabs:  installed  ·  marketplace  ·  authored", id="sk-tabs")
            yield Static("", id="sk-inspector-pane")

    def populate(self, data: CockpitData) -> None:
        """Build or refresh the skills view from *data*."""
        self._data = data
        self._skills = data.skills()
        self._og_nodes = data.og()
        self._selected = min(self._selected, max(0, len(self._skills) - 1))
        self._render_list()
        self._render_inspector()

    def _node_for_skill(self, skill: Skill) -> OgNode | None:
        """Find the OgNode whose name matches the skill name (case-insensitive)."""
        skill_name = skill.name.lower()
        for node in self._og_nodes:
            if node.name.lower() == skill_name or node.id.lower() == skill_name:
                return node
        return None

    def _render_list(self) -> None:
        self.query_one("#sk-list", Static).update(_skill_list_text(self._skills, self._selected))

        # footer tabs
        tabs_t = Text()
        tabs_t.append("tabs:  ", style=MUTED)
        tabs_t.append("installed", style=FOREGROUND)
        tabs_t.append("  ·  marketplace  ·  authored", style=MUTED)
        self.query_one("#sk-tabs", Static).update(tabs_t)

    def _render_inspector(self) -> None:
        insp = self.query_one("#sk-inspector-pane", Static)
        if not self._inspector_visible or not self._skills:
            insp.update(Text())
            return
        skill = self._skills[self._selected]
        node = self._node_for_skill(skill)
        insp.update(_og_inspector_text(skill, node))

    def move_selection(self, delta: int) -> None:
        """Move the skill list selection by *delta* and refresh the inspector.

        Args:
            delta: +1 = down, -1 = up.
        """
        if not self._skills:
            return
        self._selected = (self._selected + delta) % len(self._skills)
        self._render_list()
        self._render_inspector()

    def toggle_inspector(self) -> None:
        """Show or hide the OG inspector pane.

        Toggles ``_inspector_visible`` and re-renders the right panel.
        """
        self._inspector_visible = not self._inspector_visible
        self._render_inspector()
