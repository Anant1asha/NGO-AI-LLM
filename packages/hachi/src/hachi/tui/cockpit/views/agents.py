"""AgentsView — sub-agent roster table (Hachi Cockpit Wave-3).

Displays running and completed sub-agents with status/role/task/iter/time/tok
columns. The right-hand inspector shows a per-agent trace (task summary, tool
lines, model/cost/status). Row accent colour is driven by ``status_color``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult

from hachi.client.models import AgentRow
from hachi.tui.cockpit.base import CockpitView
from hachi.tui.cockpit.views.table import (
    CockpitTable,
    InspectorAction,
    InspectorField,
    TableCell,
    TableColumn,
    TableRow,
)
from hachi.tui.theme import FOREGROUND, MUTED, NAVY, status_color, status_word

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

# Dim colour reused from the table widget internals.
_DIM = "#6E6A74"


def _agent_inspector(agent: AgentRow) -> tuple[list[InspectorField], list[InspectorAction], str]:
    """Build inspector fields + actions for a single AgentRow."""
    color = status_color(agent.status)
    fields: list[InspectorField] = [
        InspectorField(line=True, value=agent.role, color=FOREGROUND),
        InspectorField(divider=True),
        InspectorField(row=True, label="task", value=agent.task, color=FOREGROUND),
        InspectorField(row=True, label="status", value=status_word(agent.status), color=color),
        InspectorField(row=True, label="outcome", value=agent.outcome or "—", color=MUTED),
        InspectorField(divider=True),
        InspectorField(row=True, label="tokens", value=str(agent.tokens), color=NAVY),
        InspectorField(row=True, label="model", value="—", color=_DIM),
        InspectorField(row=True, label="cost", value="—", color=_DIM),
    ]
    actions: list[InspectorAction] = [
        InspectorAction(key="t", label="open trace", primary=True, action="trace"),
        InspectorAction(key="r", label="re-run role", primary=False, action="rerun"),
    ]
    title = f"agent · {agent.role}"
    return fields, actions, title


class AgentsView(CockpitView):  # type: ignore[misc]
    """Sub-agent roster table (isTable view).

    Columns: status · role · task · iter · time · tok.
    Data source: ``CockpitData.agents()``.
    Inspector: per-agent trace with task summary, outcome, token count, model/cost.
    """

    view_id: ClassVar[str] = "agents"

    DEFAULT_CSS = """
    AgentsView {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._agents: list[AgentRow] = []
        self._data: CockpitData | None = None

    def compose(self) -> ComposeResult:
        """Yield the reusable table widget."""
        yield CockpitTable(id="agents-table")

    def populate(self, data: CockpitData) -> None:
        """Load agent rows from *data* and render the table."""
        self._data = data
        self._agents = data.agents()
        self._rebuild()

    def _rebuild(self) -> None:
        """Build columns, rows and inspector then call table.load()."""
        table = self.query_one(CockpitTable)
        agents = self._agents

        columns = [
            TableColumn("status", 10),
            TableColumn("role", 14),
            TableColumn("task", grow=True),
            TableColumn("iter", 6, align="right"),
            TableColumn("time", 8, align="right"),
            TableColumn("tok", 7, align="right"),
        ]

        rows: list[TableRow] = []
        for agent in agents:
            color = status_color(agent.status)
            rows.append(
                TableRow(
                    cells=[
                        TableCell(status_word(agent.status), color=color),
                        TableCell(agent.role, color=FOREGROUND),
                        TableCell(agent.task, color=MUTED),
                        TableCell("—", color=_DIM, align="right"),
                        TableCell("—", color=_DIM, align="right"),
                        TableCell(
                            str(agent.tokens) if agent.tokens else "—",
                            color=NAVY,
                            align="right",
                        ),
                    ],
                    accent_color=color,
                )
            )

        # Inspector for the currently selected row.
        fields, actions, title = self._inspector_for_index(table.selected_index)

        table.load(
            columns=columns,
            rows=rows,
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            empty_text="no sub-agents reported",
        )

    def _inspector_for_index(
        self, idx: int
    ) -> tuple[list[InspectorField], list[InspectorAction], str]:
        """Return inspector data for the row at *idx* (or an empty placeholder)."""
        if not self._agents:
            return [], [], "agent · detail"
        idx = max(0, min(idx, len(self._agents) - 1))
        return _agent_inspector(self._agents[idx])

    def move_selection(self, delta: int) -> None:
        """Move table selection and rebuild the inspector for the new row."""
        table = self.query_one(CockpitTable)
        table.move_selection(delta)
        # Rebuild inspector in-place: recompute for new selected_index, reload.
        fields, actions, title = self._inspector_for_index(table.selected_index)
        table.load(
            columns=[
                TableColumn("status", 10),
                TableColumn("role", 14),
                TableColumn("task", grow=True),
                TableColumn("iter", 6, align="right"),
                TableColumn("time", 8, align="right"),
                TableColumn("tok", 7, align="right"),
            ],
            rows=self._build_rows(),
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            empty_text="no sub-agents reported",
        )

    def _build_rows(self) -> list[TableRow]:
        """Reconstruct row list from cached agent data."""
        rows: list[TableRow] = []
        for agent in self._agents:
            color = status_color(agent.status)
            rows.append(
                TableRow(
                    cells=[
                        TableCell(status_word(agent.status), color=color),
                        TableCell(agent.role, color=FOREGROUND),
                        TableCell(agent.task, color=MUTED),
                        TableCell("—", color=_DIM, align="right"),
                        TableCell("—", color=_DIM, align="right"),
                        TableCell(
                            str(agent.tokens) if agent.tokens else "—",
                            color=NAVY,
                            align="right",
                        ),
                    ],
                    accent_color=color,
                )
            )
        return rows

    def toggle_inspector(self) -> None:
        """Show/hide the trace inspector panel."""
        self.query_one(CockpitTable).toggle_inspector()
