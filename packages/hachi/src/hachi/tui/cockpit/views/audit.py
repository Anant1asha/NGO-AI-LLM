"""AuditView — permission audit log table (Hachi Cockpit Wave-3).

Columns: seq · time · event · owner · detail. Rows with a ``permission.requested``
operation are highlighted in BRAND red. The right inspector shows the full event
payload (op, target, policy, decision, timestamp).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult

from hachi.client.models import AuditEntry
from hachi.tui.cockpit.base import CockpitView
from hachi.tui.cockpit.views.table import (
    CockpitTable,
    InspectorAction,
    InspectorField,
    TableCell,
    TableColumn,
    TableRow,
)
from hachi.tui.theme import BRAND, FOREGROUND, GREEN, MUTED, NAVY

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

_DIM = "#6E6A74"

_DECISION_COLOR: dict[str, str] = {
    "allowed": GREEN,
    "allowed once": GREEN,
    "automatic": NAVY,
    "declined": BRAND,
}


def _audit_inspector(
    seq: int, entry: AuditEntry
) -> tuple[list[InspectorField], list[InspectorAction], str]:
    """Build inspector fields for a single AuditEntry."""
    dec_color = _DECISION_COLOR.get(entry.decision, MUTED)
    fields: list[InspectorField] = [
        InspectorField(line=True, value=entry.op, color=FOREGROUND),
        InspectorField(divider=True),
        InspectorField(row=True, label="seq", value=f"#{seq}", color=_DIM),
        InspectorField(row=True, label="time", value=entry.ts, color=MUTED),
        InspectorField(row=True, label="op", value=entry.op, color=FOREGROUND),
        InspectorField(row=True, label="target", value=entry.target or "—", color=MUTED),
        InspectorField(divider=True),
        InspectorField(row=True, label="policy", value=entry.policy or "—", color=MUTED),
        InspectorField(row=True, label="decision", value=entry.decision, color=dec_color),
    ]
    actions: list[InspectorAction] = [
        InspectorAction(key="c", label="copy target", primary=False, action="copy"),
    ]
    return fields, actions, f"event · {entry.op}"


class AuditView(CockpitView):  # type: ignore[misc]
    """Permission audit log table (isTable view).

    Columns: seq · time · event · owner · detail.
    Data source: ``CockpitData.audit()``.
    Inspector: full event payload (op, target, policy, decision, ts).
    Rows with a 'permission.requested' op are highlighted in BRAND red.
    """

    view_id: ClassVar[str] = "audit"

    DEFAULT_CSS = """
    AuditView {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._entries: list[AuditEntry] = []
        self._data: CockpitData | None = None

    def compose(self) -> ComposeResult:
        """Yield the reusable table widget."""
        yield CockpitTable(id="audit-table")

    def populate(self, data: CockpitData) -> None:
        """Load audit entries from *data* and render the table."""
        self._data = data
        self._entries = data.audit()
        self._rebuild()

    def _row_accent(self, entry: AuditEntry) -> str:
        """Return the row accent colour: BRAND for permission.requested, else DIM."""
        if "permission" in entry.op.lower() or "requested" in entry.op.lower():
            return str(BRAND)
        return _DIM

    def _build_rows(self) -> list[TableRow]:
        """Convert AuditEntry list to TableRow list (newest-first seq numbering)."""
        rows: list[TableRow] = []
        total = len(self._entries)
        for i, entry in enumerate(self._entries):
            seq = total - i  # descending sequence number
            accent = self._row_accent(entry)
            dec_color = _DECISION_COLOR.get(entry.decision, MUTED)
            # Cell colour: BRAND on permission.requested rows for visual emphasis.
            op_color = BRAND if accent == BRAND else FOREGROUND
            rows.append(
                TableRow(
                    cells=[
                        TableCell(f"#{seq}", color=_DIM, align="right"),
                        TableCell(entry.ts, color=MUTED),
                        TableCell(entry.op, color=op_color),
                        TableCell(entry.policy or "—", color=MUTED),
                        TableCell(entry.decision, color=dec_color),
                    ],
                    accent_color=accent,
                )
            )
        return rows

    def _inspector_for_index(
        self, idx: int
    ) -> tuple[list[InspectorField], list[InspectorAction], str]:
        """Return inspector data for the entry at *idx*."""
        if not self._entries:
            return [], [], "event · detail"
        idx = max(0, min(idx, len(self._entries) - 1))
        seq = len(self._entries) - idx
        return _audit_inspector(seq, self._entries[idx])

    def _rebuild(self) -> None:
        """Build columns, rows and inspector then call table.load()."""
        table = self.query_one(CockpitTable)
        columns = [
            TableColumn("seq", 5, align="right"),
            TableColumn("time", 10),
            TableColumn("event", 22),
            TableColumn("owner", grow=True),
            TableColumn("detail", 14),
        ]
        rows = self._build_rows()
        fields, actions, title = self._inspector_for_index(table.selected_index)
        table.load(
            columns=columns,
            rows=rows,
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            empty_text="no audit events yet",
        )

    def move_selection(self, delta: int) -> None:
        """Move table selection and rebuild the inspector for the new entry."""
        table = self.query_one(CockpitTable)
        table.move_selection(delta)
        fields, actions, title = self._inspector_for_index(table.selected_index)
        table.load(
            columns=[
                TableColumn("seq", 5, align="right"),
                TableColumn("time", 10),
                TableColumn("event", 22),
                TableColumn("owner", grow=True),
                TableColumn("detail", 14),
            ],
            rows=self._build_rows(),
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            empty_text="no audit events yet",
        )

    def toggle_inspector(self) -> None:
        """Show/hide the event detail inspector panel."""
        self.query_one(CockpitTable).toggle_inspector()
