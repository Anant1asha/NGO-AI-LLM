"""ConnectionsView — MCP / integration connections table (Hachi Cockpit Wave-3).

Columns: health · connection · tools. Merges ``capabilities()`` (named integrations)
and ``mcp()`` (MCP servers) into a single health-overview table. The right inspector
shows status, scopes/can, tool count, and an ungated-tool warning for risky entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import ComposeResult

from hachi.client.models import Capability, McpServer
from hachi.tui.cockpit.base import CockpitView
from hachi.tui.cockpit.views.table import (
    CockpitTable,
    InspectorAction,
    InspectorField,
    TableCell,
    TableColumn,
    TableRow,
)
from hachi.tui.theme import AMBER, DANGER, FOREGROUND, GREEN, MUTED, NAVY

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

_DIM = "#6E6A74"

_STATUS_COLOR: dict[str, str] = {
    "connected": GREEN,
    "connected (mcp)": GREEN,
    "degraded": AMBER,
    "starting": AMBER,
    "none": _DIM,
    "blocked": DANGER,
}

_HEALTH_GLYPH: dict[str, str] = {
    "connected": "●",
    "connected (mcp)": "●",
    "degraded": "◐",
    "starting": "◌",
    "none": "○",
    "blocked": "✗",
}


@dataclass
class _ConnRow:
    """Unified row for capabilities and MCP servers."""

    name: str
    status: str
    tools: str
    can: str
    risky: bool
    source: str  # "capability" | "mcp"
    raw_status: str  # original status string for colour lookup


def _from_capability(cap: Capability) -> _ConnRow:
    status = cap.status  # "connected" | "degraded" | "none"
    tools_label = "—"
    return _ConnRow(
        name=cap.name,
        status=status,
        tools=tools_label,
        can=cap.can,
        risky=cap.risky,
        source="capability",
        raw_status=status,
    )


def _from_mcp(srv: McpServer) -> _ConnRow:
    status_map = {
        "connected": "connected (mcp)",
        "starting": "starting",
        "blocked": "blocked",
    }
    status = status_map.get(srv.status, srv.status)
    return _ConnRow(
        name=srv.name,
        status=status,
        tools=str(srv.tools) if srv.tools else "—",
        can=f"MCP · {srv.transport}" if srv.transport and srv.transport != "—" else "MCP server",
        risky=False,
        source="mcp",
        raw_status=srv.status,
    )


def _conn_inspector(
    conn: _ConnRow,
) -> tuple[list[InspectorField], list[InspectorAction], str]:
    """Build inspector fields + actions for a connection row."""
    color = _STATUS_COLOR.get(conn.status, MUTED)
    fields: list[InspectorField] = [
        InspectorField(line=True, value=conn.name, color=FOREGROUND),
        InspectorField(divider=True),
        InspectorField(row=True, label="status", value=conn.status, color=color),
        InspectorField(row=True, label="source", value=conn.source, color=MUTED),
        InspectorField(row=True, label="can", value=conn.can, color=MUTED),
        InspectorField(row=True, label="tools", value=conn.tools, color=NAVY),
    ]
    if conn.risky:
        fields.append(InspectorField(divider=True))
        fields.append(
            InspectorField(
                line=True,
                value="⚠ risky — this integration can modify external state",
                color=AMBER,
            )
        )
    if conn.status in ("none", "blocked"):
        fields.append(InspectorField(divider=True))
        fields.append(
            InspectorField(line=True, value="not connected — configure in settings", color=_DIM)
        )
    actions: list[InspectorAction] = [
        InspectorAction(key="e", label="enable / configure", primary=True, action="enable"),
        InspectorAction(key="d", label="disable", primary=False, action="disable"),
    ]
    return fields, actions, f"connection · {conn.name}"


class ConnectionsView(CockpitView):  # type: ignore[misc]
    """MCP / integration connections table (isTable view).

    Columns: health · connection · tools.
    Data source: ``CockpitData.capabilities()`` + ``CockpitData.mcp()`` (servers).
    Inspector: status, scopes/can, tool count, ungated-tool warning for risky entries.
    """

    view_id: ClassVar[str] = "connections"

    DEFAULT_CSS = """
    ConnectionsView {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._conns: list[_ConnRow] = []
        self._data: CockpitData | None = None

    def compose(self) -> ComposeResult:
        """Yield the reusable table widget."""
        yield CockpitTable(id="connections-table")

    def populate(self, data: CockpitData) -> None:
        """Load capability and MCP rows from *data* and render the table."""
        self._data = data
        caps = data.capabilities()
        servers, _ = data.mcp()
        self._conns = [_from_capability(c) for c in caps] + [_from_mcp(s) for s in servers]
        self._rebuild()

    def _build_rows(self) -> list[TableRow]:
        """Convert _ConnRow list to TableRow list."""
        rows: list[TableRow] = []
        for conn in self._conns:
            color = _STATUS_COLOR.get(conn.status, MUTED)
            glyph = _HEALTH_GLYPH.get(conn.status, "○")
            rows.append(
                TableRow(
                    cells=[
                        TableCell(f"{glyph} {conn.status}", color=color),
                        TableCell(conn.name, color=FOREGROUND),
                        TableCell(conn.tools, color=NAVY, align="right"),
                    ],
                    accent_color=color,
                )
            )
        return rows

    def _inspector_for_index(
        self, idx: int
    ) -> tuple[list[InspectorField], list[InspectorAction], str]:
        """Return inspector data for the connection at *idx*."""
        if not self._conns:
            return [], [], "connection · detail"
        idx = max(0, min(idx, len(self._conns) - 1))
        return _conn_inspector(self._conns[idx])

    def _rebuild(self) -> None:
        """Build columns, rows and inspector then call table.load()."""
        table = self.query_one(CockpitTable)
        columns = [
            TableColumn("health", 22),
            TableColumn("connection", grow=True),
            TableColumn("tools", 7, align="right"),
        ]
        rows = self._build_rows()
        fields, actions, title = self._inspector_for_index(table.selected_index)
        table.load(
            columns=columns,
            rows=rows,
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            empty_text="no connections configured",
        )

    def move_selection(self, delta: int) -> None:
        """Move table selection and rebuild the inspector for the new row."""
        table = self.query_one(CockpitTable)
        table.move_selection(delta)
        fields, actions, title = self._inspector_for_index(table.selected_index)
        table.load(
            columns=[
                TableColumn("health", 22),
                TableColumn("connection", grow=True),
                TableColumn("tools", 7, align="right"),
            ],
            rows=self._build_rows(),
            inspector_fields=fields,
            inspector_actions=actions,
            inspector_title=title,
            empty_text="no connections configured",
        )

    def toggle_inspector(self) -> None:
        """Show/hide the connection detail inspector panel."""
        self.query_one(CockpitTable).toggle_inspector()

    def toggle_capability(self) -> None:
        """Toggle the enabled flag on the selected capability row.

        Only acts on rows that originate from ``CockpitData.capabilities()``
        (``source == "capability"``).  MCP server rows are skipped — they have
        no ``set_capability`` endpoint.

        After the gateway call the view re-populates from fresh data so the
        health indicator and inspector reflect the new state.  A toast is shown
        via ``self.app.screen.notify_toast`` so the screen's toast layer is used.
        """
        if not self._conns or self._data is None:
            return
        table = self.query_one(CockpitTable)
        idx = max(0, min(table.selected_index, len(self._conns) - 1))
        conn = self._conns[idx]
        cockpit_screen: Any = self.app.screen
        if conn.source != "capability":
            # MCP servers don't have a toggle endpoint — surface a hint.
            if hasattr(cockpit_screen, "notify_toast"):
                cockpit_screen.notify_toast(
                    f"{conn.name} is an MCP server — configure in settings", glyph="◈"
                )
            return

        # Find the matching Capability object to get its id.
        caps = self._data.capabilities()
        cap = next((c for c in caps if c.name == conn.name), None)
        if cap is None:
            return
        new_enabled = not cap.enabled
        self._data.set_capability(cap.id, new_enabled)

        # Re-fetch so the table reflects the persisted state.
        self.populate(self._data)

        state_label = "enabled" if new_enabled else "disabled"
        if hasattr(cockpit_screen, "notify_toast"):
            cockpit_screen.notify_toast(f"{cap.name} {state_label}", glyph="◈")
