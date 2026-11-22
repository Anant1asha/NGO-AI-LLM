"""TasksView — work-queue table with lifecycle tabs (Hachi Cockpit Wave-3).

Displays active and failed tasks under tabbed lifecycle views. Columns:
state · kind · label · owner · age · retry. The right inspector shows full
task detail including error message for failed tasks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from textual.app import ComposeResult

from hachi.client.models import TaskRow
from hachi.tui.cockpit.base import CockpitView
from hachi.tui.cockpit.views.table import (
    CockpitTable,
    InspectorAction,
    InspectorField,
    TableCell,
    TableColumn,
    TableRow,
    TableTab,
)
from hachi.tui.theme import DANGER, FOREGROUND, MUTED, NAVY, status_color, status_word

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

_DIM = "#6E6A74"

# Lifecycle tab labels in display order.
_TAB_LABELS: list[str] = ["active", "scheduled", "completed", "failed", "paused", "blocked"]

TabLabel = Literal["active", "scheduled", "completed", "failed", "paused", "blocked"]


def _task_inspector(task: TaskRow) -> tuple[list[InspectorField], list[InspectorAction], str]:
    """Build inspector fields + actions for a single TaskRow."""
    color = status_color(task.status)
    pct = f"{int(task.progress * 100)}%"
    fields: list[InspectorField] = [
        InspectorField(line=True, value=task.title, color=FOREGROUND),
        InspectorField(divider=True),
        InspectorField(row=True, label="id", value=task.id, color=_DIM),
        InspectorField(row=True, label="state", value=status_word(task.status), color=color),
        InspectorField(row=True, label="kind", value=task.meta or "—", color=MUTED),
        InspectorField(row=True, label="progress", value=pct, color=NAVY),
        InspectorField(divider=True),
        InspectorField(row=True, label="when", value=task.when or "—", color=MUTED),
        InspectorField(row=True, label="spent", value=f"${task.spent:.4f}", color=NAVY),
        InspectorField(row=True, label="budget", value=f"${task.budget:.2f}", color=_DIM),
    ]
    if task.error:
        fields.append(InspectorField(divider=True))
        fields.append(InspectorField(line=True, value=task.error, color=DANGER))

    actions: list[InspectorAction] = [
        InspectorAction(key="x", label="cancel task", primary=False, action="cancel"),
        InspectorAction(key="r", label="retry task", primary=True, action="retry"),
    ]
    return fields, actions, f"task · {task.title[:24]}"


class TasksView(CockpitView):  # type: ignore[misc]
    """Work-queue table with lifecycle tabs (isTable view).

    Columns: state · kind · label · owner · age · retry.
    Tabs: active · scheduled · completed · failed · paused · blocked.
    Data source: ``CockpitData.active_tasks()`` + ``CockpitData.failed_tasks()``.
    Inspector: full task detail with error line for failed tasks.
    """

    view_id: ClassVar[str] = "tasks"

    DEFAULT_CSS = """
    TasksView {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._active: list[TaskRow] = []
        self._failed: list[TaskRow] = []
        self._active_tab: str = "active"
        self._data: CockpitData | None = None

    def compose(self) -> ComposeResult:
        """Yield the reusable table widget."""
        yield CockpitTable(id="tasks-table")

    def populate(self, data: CockpitData) -> None:
        """Load task rows from *data* and render the table."""
        self._data = data
        self._active = data.active_tasks()
        self._failed = data.failed_tasks()
        self._rebuild()

    def _visible_rows(self) -> list[TaskRow]:
        """Return the rows appropriate for the currently active tab."""
        tab = self._active_tab
        if tab == "active":
            return [t for t in self._active if t.status == "working"]
        if tab == "failed":
            return self._failed
        if tab == "blocked":
            return [t for t in self._active if t.status == "blocked"]
        if tab == "completed":
            return [t for t in self._active if t.status == "done"]
        # scheduled / paused — no direct gateway data yet; return all active as fallback.
        return self._active

    def _build_tabs(self) -> list[TableTab]:
        """Build the lifecycle tab list, marking the active one."""
        return [TableTab(label=lbl, active=(lbl == self._active_tab)) for lbl in _TAB_LABELS]

    def _build_rows(self, tasks: list[TaskRow]) -> list[TableRow]:
        """Convert TaskRow list to TableRow list."""
        rows: list[TableRow] = []
        for task in tasks:
            color = status_color(task.status)
            retry_label = "—" if not task.error else "1"
            rows.append(
                TableRow(
                    cells=[
                        TableCell(status_word(task.status), color=color),
                        TableCell(task.meta or "—", color=MUTED),
                        TableCell(task.title, color=FOREGROUND),
                        TableCell("—", color=_DIM),  # owner (not in model)
                        TableCell(task.when, color=MUTED),
                        TableCell(retry_label, color=DANGER if task.error else _DIM, align="right"),
                    ],
                    accent_color=color,
                )
            )
        return rows

    def _inspector_for_index(
        self, tasks: list[TaskRow], idx: int
    ) -> tuple[list[InspectorField], list[InspectorAction], str]:
        """Return inspector data for the row at *idx*."""
        if not tasks:
            return [], [], "task · detail"
        idx = max(0, min(idx, len(tasks) - 1))
        return _task_inspector(tasks[idx])

    def _rebuild(self) -> None:
        """Build columns, rows, tabs and inspector then call table.load()."""
        table = self.query_one(CockpitTable)
        tasks = self._visible_rows()
        columns = [
            TableColumn("state", 10),
            TableColumn("kind", 14),
            TableColumn("label", grow=True),
            TableColumn("owner", 10),
            TableColumn("age", 10),
            TableColumn("retry", 6, align="right"),
        ]
        rows = self._build_rows(tasks)
        tabs = self._build_tabs()
        fields, actions, title = self._inspector_for_index(tasks, table.selected_index)
        table.load(
            columns=columns,
            rows=rows,
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            tabs=tabs,
            empty_text="no tasks for this filter",
        )

    def move_selection(self, delta: int) -> None:
        """Move table selection and rebuild the inspector for the new row."""
        table = self.query_one(CockpitTable)
        table.move_selection(delta)
        tasks = self._visible_rows()
        fields, actions, title = self._inspector_for_index(tasks, table.selected_index)
        columns = [
            TableColumn("state", 10),
            TableColumn("kind", 14),
            TableColumn("label", grow=True),
            TableColumn("owner", 10),
            TableColumn("age", 10),
            TableColumn("retry", 6, align="right"),
        ]
        table.load(
            columns=columns,
            rows=self._build_rows(tasks),
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            tabs=self._build_tabs(),
            empty_text="no tasks for this filter",
        )

    def toggle_inspector(self) -> None:
        """Show/hide the task detail inspector panel."""
        self.query_one(CockpitTable).toggle_inspector()
