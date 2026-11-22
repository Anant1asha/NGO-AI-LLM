"""SettingsView — provider / memory / sub-agents / appearance / setup nav.

Faithful recreation of the Settings panel from the Hachi Cockpit design
(lines 421–445 of Hachi Cockpit.dc.html).  Left rail with five nav items;
content pane shows Provider & Model by default with live data from
``ConfigSnapshot`` and ``ModelInfo`` list.

Layout follows the same pattern as GovernanceView: Horizontal with two
Vertical containers (rail + content), each with a single Static inside.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from hachi.tui.cockpit.base import CockpitView
from hachi.tui.theme import (
    BORDER_MUTED,
    BRAND,
    FOREGROUND,
    GREEN,
    MUTED,
    NAVY,
    SURFACE,
)

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

_DIM = "#6E6A74"

# Left-rail section labels (sentence-case, calm)
_SECTIONS = [
    "Provider",
    "Memory",
    "Sub-agents",
    "Appearance",
    "Setup wizard",
]


class SettingsView(CockpitView):  # type: ignore[misc]
    """Settings view with left-rail section nav.

    Left rail: Provider / Memory / Sub-agents / Appearance / Setup wizard.
    Content pane: selected section's fields.  Default = Provider.

    Navigation:
    - j/k (via ``move_selection``) moves the rail cursor.
    - The content pane refreshes on each selection change.

    Data sources: ``CockpitData.config()``, ``CockpitData.models()``,
    ``CockpitData.setup()``.
    """

    view_id: ClassVar[str] = "settings"

    DEFAULT_CSS = f"""
    SettingsView {{
        height: 1fr;
        width: 1fr;
        background: {SURFACE};
    }}
    #settings-rail {{
        width: 22;
        border-right: solid {BORDER_MUTED};
        padding: 1 1;
        height: 1fr;
    }}
    #settings-rail-label {{
        height: auto;
    }}
    #settings-content {{
        padding: 1 2;
        overflow-y: auto;
        height: 1fr;
    }}
    #settings-pane {{
        height: auto;
    }}
    """

    _selected: int = 0
    _data: CockpitData | None = None

    def compose(self) -> ComposeResult:
        """Build the two-panel layout."""
        with Horizontal():
            with Vertical(id="settings-rail"):
                yield Static("", id="settings-rail-label")
            with Vertical(id="settings-content"):
                yield Static("", id="settings-pane")

    def populate(self, data: CockpitData) -> None:
        """Load config/model data and render the default Provider section."""
        self._data = data
        self._refresh_panels()

    # ------------------------------------------------------------------
    # Hook: j/k navigation
    # ------------------------------------------------------------------

    def move_selection(self, delta: int) -> None:
        """Move the rail selection by *delta* (+1 down, -1 up) and refresh."""
        self._selected = (self._selected + delta) % len(_SECTIONS)
        self._refresh_panels()

    def switch_model(self) -> None:
        """Cycle to the next available model and persist via PUT /config/provider (key: m).

        Reads the model list from data.models(), finds the current model position,
        and advances to the next one.  Silently no-ops if offline or no data.
        """
        if self._data is None:
            return
        models = self._data.models()
        if not models:
            scr: Any = self.app.screen
            if hasattr(scr, "notify_toast"):
                scr.notify_toast("no models available", glyph="◈")
            return
        cfg = self._data.config()
        current = cfg.model if cfg else ""
        model_ids = [m.id for m in models]
        try:
            idx = model_ids.index(current)
            next_idx = (idx + 1) % len(model_ids)
        except ValueError:
            next_idx = 0
        next_model = model_ids[next_idx]
        self._data.switch_model(next_model)
        # Re-populate so the displayed model reflects the change.
        self._refresh_panels()
        scr2: Any = self.app.screen
        if hasattr(scr2, "notify_toast"):
            scr2.notify_toast(f"model → {next_model}", glyph="⟳")

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _refresh_panels(self) -> None:
        """Re-draw both panels for the current selection."""
        self.query_one("#settings-rail-label", Static).update(self._build_rail())
        self.query_one("#settings-pane", Static).update(self._build_content())

    def _build_rail(self) -> Text:
        """Build the rail Text with the selected item highlighted."""
        t = Text()
        for i, label in enumerate(_SECTIONS):
            if i == self._selected:
                t.append(f" {label}\n", style=f"bold {BRAND}")
            else:
                t.append(f" {label}\n", style=MUTED)
        return t

    def _build_content(self) -> Text:
        """Dispatch to the appropriate section builder."""
        section = _SECTIONS[self._selected]
        builders = {
            "Provider": self._section_provider,
            "Memory": self._section_memory,
            "Sub-agents": self._section_subagents,
            "Appearance": self._section_appearance,
            "Setup wizard": self._section_setup,
        }
        return builders[section]()

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _section_provider(self) -> Text:
        """Provider & model section — uses config() + models()."""
        cfg = self._data.config() if self._data else None
        model_list = self._data.models() if self._data else []

        provider = cfg.provider_kind if cfg else "anthropic"
        model = cfg.model if cfg else "—"
        tier = cfg.tier if cfg else "guided"

        t = Text()
        t.append("Provider & model\n\n", style=FOREGROUND)

        t.append("provider  ", style=_DIM)
        t.append(f"{provider}  ", style=MUTED)
        t.append("[change]\n", style=NAVY)

        t.append("model     ", style=_DIM)
        t.append(f"{model}  ", style=MUTED)
        t.append("[m] switch  ", style=NAVY)
        t.append("[v] validate\n", style=GREEN)

        # List allowed models from API
        if model_list:
            labels = " · ".join(
                (m.label or m.id) + (" *" if m.recommended else "")
                for m in model_list[:6]
            )
            t.append("allowed   ", style=_DIM)
            t.append(f"{labels}\n", style=MUTED)
        else:
            t.append("allowed   ", style=_DIM)
            t.append("haiku · sonnet · opus  ", style=MUTED)
            t.append("(guardrail)\n", style=_DIM)

        t.append("tier      ", style=_DIM)
        t.append(f"{tier}\n", style=MUTED)

        t.append("\n")
        t.append(
            "providers: anthropic · openai-compatible · openrouter · groq"
            " · together · deepseek · gemini · ollama\n",
            style=_DIM,
        )
        return t

    def _section_memory(self) -> Text:
        """Memory section — uses ConfigSnapshot flags."""
        cfg = self._data.config() if self._data else None
        history = cfg.enable_session_history if cfg else True
        semantic = cfg.enable_semantic_memory if cfg else True

        t = Text()
        t.append("Memory\n\n", style=FOREGROUND)

        t.append("session history   ", style=_DIM)
        t.append("on\n" if history else "off\n", style=GREEN if history else MUTED)

        t.append("semantic memory   ", style=_DIM)
        t.append("on\n" if semantic else "off\n", style=GREEN if semantic else MUTED)

        t.append("\n")
        t.append(
            "vault layers: core_memory · user_profile · agent_profile"
            " · delegation_log\n",
            style=_DIM,
        )
        t.append("compaction: deferred / async (never inline per turn)\n", style=_DIM)
        return t

    def _section_subagents(self) -> Text:
        """Sub-agents section — shows model defaults."""
        cfg = self._data.config() if self._data else None
        model = cfg.model if cfg else "claude-haiku-4-5"

        t = Text()
        t.append("Sub-agents\n\n", style=FOREGROUND)

        t.append("default model     ", style=_DIM)
        t.append(f"{model}  ", style=MUTED)
        t.append("(cost-aware)\n", style=_DIM)

        t.append("per-role model    ", style=_DIM)
        t.append("researcher→haiku · coder→sonnet  ", style=MUTED)
        t.append("[e]\n", style=NAVY)

        t.append("\n")
        t.append(
            "Delegation creates a scoped ToolRegistry per role;\n"
            "results returned via delegation_log in memory.\n",
            style=_DIM,
        )
        return t

    @staticmethod
    def _section_appearance() -> Text:
        """Appearance section — static display."""
        t = Text()
        t.append("Appearance\n\n", style=FOREGROUND)
        t.append("theme     ", style=_DIM)
        t.append("hachi (warm-dark)\n", style=MUTED)
        t.append("font      ", style=_DIM)
        t.append("JetBrains Mono\n", style=MUTED)
        t.append("palette   ", style=_DIM)
        t.append(
            "brand #E25A44 · navy #7C9BD1 · amber #E0922E · green #3F9D6B\n",
            style=MUTED,
        )
        return t

    def _section_setup(self) -> Text:
        """Setup wizard section — uses SetupState."""
        state = self._data.setup() if self._data else None
        needs = state.needs_setup if state else False
        steps = state.completed_steps if state else ()
        tier = state.selected_tier if state else "—"
        env_ok = state.anthropic_env if state else False

        t = Text()
        t.append("Setup wizard\n\n", style=FOREGROUND)

        t.append("tier         ", style=_DIM)
        t.append(f"{tier}\n", style=MUTED)

        t.append("api key env  ", style=_DIM)
        t.append("ok\n" if env_ok else "missing\n", style=GREEN if env_ok else BRAND)

        t.append("steps done   ", style=_DIM)
        t.append(f"{len(steps)}\n", style=MUTED)

        if needs:
            t.append("\n")
            t.append("[s] open setup wizard  ", style=NAVY)
            t.append("(setup incomplete)\n", style=BRAND)
        else:
            t.append("\n")
            t.append("Setup complete  ", style=GREEN)
            t.append("✓\n", style=GREEN)

        return t
