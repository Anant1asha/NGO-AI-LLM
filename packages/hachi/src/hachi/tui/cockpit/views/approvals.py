"""ApprovalsView — pending approval requests table (Hachi Cockpit Wave-3).

Columns: age · agent · action · target · risk. The inspector shows full
request detail with allow / deny / always action buttons and an auto-deny
countdown footer. An ungated-tool warning flag is shown when any pending
approval has a high-risk operation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult

from hachi.client.models import Approval
from hachi.tui.cockpit.base import CockpitView
from hachi.tui.cockpit.views.table import (
    CockpitTable,
    InspectorAction,
    InspectorField,
    TableCell,
    TableColumn,
    TableRow,
)
from hachi.tui.theme import AMBER, DANGER, FOREGROUND, GREEN, MUTED

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

_DIM = "#6E6A74"

_RISK_COLOR: dict[str, str] = {
    "low": GREEN,
    "medium": AMBER,
    "high": DANGER,
}

_COUNTDOWN_TEXT = "⧖ approvals auto-deny in 180s — you decide before then"
_UNGATED_FLAG = "⚠ ungated tool — this approval bypasses your policy"
_EMPTY_TEXT = "✓ no approvals waiting — Hachi is resting"


def _approval_inspector(
    appr: Approval,
) -> tuple[list[InspectorField], list[InspectorAction], str]:
    """Build inspector fields + actions for a single Approval."""
    risk_color = _RISK_COLOR.get(appr.risk, MUTED)
    fields: list[InspectorField] = [
        InspectorField(line=True, value=appr.request, color=FOREGROUND),
        InspectorField(divider=True),
        InspectorField(row=True, label="why", value=appr.why, color=MUTED),
        InspectorField(row=True, label="action", value=appr.action, color=FOREGROUND),
        InspectorField(row=True, label="op", value=appr.op, color=MUTED),
        InspectorField(divider=True),
        InspectorField(row=True, label="risk", value=appr.risk, color=risk_color),
        InspectorField(row=True, label="policy", value=appr.policy, color=MUTED),
        InspectorField(row=True, label="scope", value=appr.scope, color=_DIM),
    ]
    if appr.touches:
        fields.append(
            InspectorField(row=True, label="touches", value=", ".join(appr.touches), color=AMBER)
        )
    actions: list[InspectorAction] = [
        InspectorAction(key="y", label="allow once", primary=True, action="allow"),
        InspectorAction(key="n", label="deny", primary=False, action="deny"),
        InspectorAction(key="A", label="always allow", primary=False, action="always"),
    ]
    return fields, actions, f"approval · {appr.request}"


class ApprovalsView(CockpitView):  # type: ignore[misc]
    """Pending approval requests table (isTable view).

    Columns: age · agent · action · target · risk.
    Data source: ``CockpitData.approvals()``.
    Inspector: full request detail with allow/deny/always action buttons.
    Footer: auto-deny countdown when any pending; ungated-tool flag on high-risk.
    ``decide_top(action)`` decides the selected (or first) approval and refreshes.
    """

    view_id: ClassVar[str] = "approvals"

    DEFAULT_CSS = """
    ApprovalsView {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._approvals: list[Approval] = []
        self._data: CockpitData | None = None

    def compose(self) -> ComposeResult:
        """Yield the reusable table widget."""
        yield CockpitTable(id="approvals-table")

    def populate(self, data: CockpitData) -> None:
        """Load approval rows from *data* and render the table."""
        self._data = data
        self._approvals = data.approvals()
        self._rebuild()

    def _build_rows(self) -> list[TableRow]:
        """Convert Approval list to TableRow list."""
        rows: list[TableRow] = []
        for appr in self._approvals:
            risk_color = _RISK_COLOR.get(appr.risk, MUTED)
            # Target: first element of touches or derived from action.
            target = appr.touches[0] if appr.touches else appr.scope
            rows.append(
                TableRow(
                    cells=[
                        TableCell("now", color=_DIM),  # age — no timestamp in model
                        TableCell(appr.scope, color=MUTED),  # agent / scope
                        TableCell(appr.action, color=FOREGROUND),
                        TableCell(target, color=MUTED),
                        TableCell(appr.risk, color=risk_color),
                    ],
                    accent_color=risk_color,
                )
            )
        return rows

    def _inspector_for_index(
        self, idx: int
    ) -> tuple[list[InspectorField], list[InspectorAction], str]:
        """Return inspector data for the approval at *idx*."""
        if not self._approvals:
            return [], [], "approval · detail"
        idx = max(0, min(idx, len(self._approvals) - 1))
        return _approval_inspector(self._approvals[idx])

    def _rebuild(self) -> None:
        """Build columns, rows, footer and inspector then call table.load()."""
        table = self.query_one(CockpitTable)
        columns = [
            TableColumn("age", 6),
            TableColumn("agent", 14),
            TableColumn("action", grow=True),
            TableColumn("target", 22),
            TableColumn("risk", 8),
        ]
        rows = self._build_rows()
        fields, actions, title = self._inspector_for_index(table.selected_index)

        # Countdown when there are pending approvals.
        countdown = _COUNTDOWN_TEXT if self._approvals else ""
        # Flag when any approval looks high-risk / ungated.
        flag = _UNGATED_FLAG if any(a.risk == "high" for a in self._approvals) else ""

        table.load(
            columns=columns,
            rows=rows,
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            countdown=countdown,
            flag=flag,
            empty_text=_EMPTY_TEXT,
        )

    def move_selection(self, delta: int) -> None:
        """Move table selection and rebuild the inspector for the new row."""
        table = self.query_one(CockpitTable)
        table.move_selection(delta)
        fields, actions, title = self._inspector_for_index(table.selected_index)
        countdown = _COUNTDOWN_TEXT if self._approvals else ""
        flag = _UNGATED_FLAG if any(a.risk == "high" for a in self._approvals) else ""
        table.load(
            columns=[
                TableColumn("age", 6),
                TableColumn("agent", 14),
                TableColumn("action", grow=True),
                TableColumn("target", 22),
                TableColumn("risk", 8),
            ],
            rows=self._build_rows(),
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            countdown=countdown,
            flag=flag,
            empty_text=_EMPTY_TEXT,
        )

    def toggle_inspector(self) -> None:
        """Show/hide the request detail inspector panel."""
        self.query_one(CockpitTable).toggle_inspector()

    def decide_top(self, action: str) -> None:
        """Decide on the selected (or first) approval and refresh the view.

        *action* must be one of: 'allow', 'deny', 'always'.
        """
        if not self._approvals or self._data is None:
            return
        table = self.query_one(CockpitTable)
        idx = max(0, min(table.selected_index, len(self._approvals) - 1))
        approval_id = self._approvals[idx].id
        self._data.decide_approval(approval_id, action)
        # Refresh — in offline mode the approval list is unchanged, but in
        # live mode the decided entry will be removed on the next gateway poll.
        self._approvals = self._data.approvals()
        self._rebuild()
