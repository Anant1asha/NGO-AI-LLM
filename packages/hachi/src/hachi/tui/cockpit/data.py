"""CockpitData — the data facade for all 12 cockpit views.

Constructed with an optional GatewayClient (None ⇒ pure-offline mode).
Every method wraps the client call in try/except GatewayError and falls
back to the matching placeholder_*() from hachi.client.gaps.
Methods NEVER raise to the caller — they always return real or placeholder data.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator

from hachi.client.gaps import (
    placeholder_active_jobs,
    placeholder_activity,
    placeholder_agents,
    placeholder_approvals,
    placeholder_audit_log,
    placeholder_auth_targets,
    placeholder_capabilities,
    placeholder_config,
    placeholder_dashboard,
    placeholder_failed_jobs,
    placeholder_health,
    placeholder_mcp_servers,
    placeholder_mcp_tools,
    placeholder_memory,
    placeholder_models,
    placeholder_og_nodes,
    placeholder_recall,
    placeholder_routines,
    placeholder_sessions,
    placeholder_setup,
    placeholder_skills,
    placeholder_spend,
    placeholder_tool_calls,
    placeholder_trust_bar,
)
from hachi.client.gateway import GatewayClient
from hachi.client.models import (
    ActivityEvent,
    AgentRow,
    Approval,
    AuditEntry,
    AuthTarget,
    Capability,
    ConfigSnapshot,
    DashboardSnapshot,
    DiffLine,
    HealthStatus,
    McpServer,
    McpTool,
    MemorySnapshot,
    ModelInfo,
    OgNode,
    RecallHit,
    Routine,
    SessionInfo,
    SetupState,
    Skill,
    SpendSnapshot,
    TaskRow,
    ToolCallRow,
    TrustBarSnapshot,
)
from hachi.client.sse import RuntimeEvent, stream_events

log = logging.getLogger(__name__)


class CockpitData:
    """Facade that serves data to all 12 cockpit views.

    Usage::

        # Online mode — wraps gateway, falls back on error
        data = CockpitData(client)

        # Offline / test mode — pure placeholder data
        data = CockpitData(None)

    All methods are synchronous and safe to call on the Textual main thread for
    quick views; spawn a thread if you need to keep the UI responsive on slow
    connections.
    """

    def __init__(self, client: GatewayClient | None) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Skills view
    # ------------------------------------------------------------------

    def skills(self) -> list[Skill]:
        """Return the list of installed skills."""
        if self._client is not None:
            try:
                return self._client.list_skills()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("skills() fallback: %s", exc)
        return placeholder_skills()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Memory view
    # ------------------------------------------------------------------

    def memory(self) -> MemorySnapshot:
        """Return the current memory snapshot (groups, blocked, proposed)."""
        if self._client is not None:
            try:
                return self._client.get_memory()
            except Exception as exc:
                log.debug("memory() fallback: %s", exc)
        return placeholder_memory()

    def recall(self, q: str, top_k: int = 8) -> list[RecallHit]:
        """Semantic recall query against the memory vault."""
        if self._client is not None:
            try:
                return self._client.recall(q, top_k=top_k)  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("recall() fallback: %s", exc)
        return placeholder_recall()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # OG / Skills inspector
    # ------------------------------------------------------------------

    def og(self) -> list[OgNode]:
        """Return all ObjectGraph nodes."""
        if self._client is not None:
            try:
                return self._client.og_graph()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("og() fallback: %s", exc)
        return placeholder_og_nodes()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Authoring (governance / .og editor)
    # ------------------------------------------------------------------

    def authoring_targets(self) -> list[AuthTarget]:
        """Return the list of editable .og / config targets."""
        if self._client is not None:
            try:
                return self._client.list_authoring_targets()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("authoring_targets() fallback: %s", exc)
        return placeholder_auth_targets()  # type: ignore[no-any-return]

    def authoring_source(self, name: str) -> tuple[str, list[DiffLine]]:
        """Return (raw_source, diff_lines) for an authoring target."""
        if self._client is not None:
            try:
                return self._client.get_authoring_target(name)  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("authoring_source(%r) fallback: %s", name, exc)
        return ("# offline — no source available\n", [])

    # ------------------------------------------------------------------
    # Spend / Resources
    # ------------------------------------------------------------------

    def spend(self, session_id: str | None = None) -> SpendSnapshot:
        """Return the spend snapshot (turns, tidies, models)."""
        if self._client is not None:
            try:
                return self._client.get_spend(session_id=session_id)
            except Exception as exc:
                log.debug("spend() fallback: %s", exc)
        return placeholder_spend()

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    def approvals(self) -> list[Approval]:
        """Return the list of pending approval requests."""
        if self._client is not None:
            try:
                return self._client.list_approvals()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("approvals() fallback: %s", exc)
        return placeholder_approvals()  # type: ignore[no-any-return]

    def decide_approval(
        self, request_id: str, action: str, rationale: str = ""
    ) -> dict[str, object]:
        """Decide on an approval request.

        *action* must be one of: 'allow', 'deny', 'always'.
        Returns the raw API response dict, or {} on error.
        """
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.decide_approval(
                    request_id, action, rationale=rationale
                )
                return result
            except Exception as exc:
                log.debug(
                    "decide_approval(%r, %r) error: %s", request_id, action, exc
                )
        return {}

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def audit(self, limit: int = 50) -> list[AuditEntry]:
        """Return the permission audit log."""
        if self._client is not None:
            try:
                return self._client.permissions_audit(limit=limit)  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("audit() fallback: %s", exc)
        return placeholder_audit_log()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def active_tasks(self) -> list[TaskRow]:
        """Return currently active jobs."""
        if self._client is not None:
            try:
                return self._client.active_jobs()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("active_tasks() fallback: %s", exc)
        return placeholder_active_jobs()  # type: ignore[no-any-return]

    def failed_tasks(self, limit: int = 20) -> list[TaskRow]:
        """Return recently failed jobs."""
        if self._client is not None:
            try:
                return self._client.failed_jobs(limit=limit)  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("failed_tasks() fallback: %s", exc)
        return placeholder_failed_jobs()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Schedules / Routines
    # ------------------------------------------------------------------

    def routines(self) -> list[Routine]:
        """Return scheduled routines."""
        if self._client is not None:
            try:
                return self._client.list_schedules()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("routines() fallback: %s", exc)
        return placeholder_routines()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Sub-agents
    # ------------------------------------------------------------------

    def agents(self, top_k: int = 10) -> list[AgentRow]:
        """Return sub-agent reports."""
        if self._client is not None:
            try:
                return self._client.subagent_reports(top_k=top_k)  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("agents() fallback: %s", exc)
        return placeholder_agents()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Runtime activity
    # ------------------------------------------------------------------

    def activity(
        self, session_id: str | None = None, limit: int = 100
    ) -> list[ActivityEvent]:
        """Return recent activity events."""
        if self._client is not None:
            try:
                events, _ = self._client.runtime_events(
                    session_id=session_id, limit=limit
                )
                return events  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("activity() fallback: %s", exc)
        return placeholder_activity()  # type: ignore[no-any-return]

    def tool_calls(
        self, session_id: str | None = None, limit: int = 100
    ) -> list[ToolCallRow]:
        """Return recent tool call rows."""
        if self._client is not None:
            try:
                _, calls = self._client.runtime_events(
                    session_id=session_id, limit=limit
                )
                return calls  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("tool_calls() fallback: %s", exc)
        return placeholder_tool_calls()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Capabilities / Connections
    # ------------------------------------------------------------------

    def capabilities(self) -> list[Capability]:
        """Return the list of integration capabilities."""
        if self._client is not None:
            try:
                return self._client.list_capabilities()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("capabilities() fallback: %s", exc)
        return placeholder_capabilities()  # type: ignore[no-any-return]

    def set_capability(self, cap_id: str, enabled: bool) -> dict[str, object]:
        """Toggle a capability on or off. Returns raw API dict or {} on error."""
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.set_capability_enabled(
                    cap_id, enabled
                )
                return result
            except Exception as exc:
                log.debug(
                    "set_capability(%r, %r) error: %s", cap_id, enabled, exc
                )
        return {}

    def mcp(self) -> tuple[list[McpServer], list[McpTool]]:
        """Return the MCP server + tool inventory."""
        if self._client is not None:
            try:
                return self._client.mcp_inventory()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("mcp() fallback: %s", exc)
        return placeholder_mcp_servers(), placeholder_mcp_tools()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def sessions(self, limit: int = 10) -> list[SessionInfo]:
        """Return recent sessions."""
        if self._client is not None:
            try:
                return self._client.list_sessions(limit=limit)  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("sessions() fallback: %s", exc)
        return placeholder_sessions()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Config / Models / Setup
    # ------------------------------------------------------------------

    def config(self) -> ConfigSnapshot:
        """Return the current gateway configuration."""
        if self._client is not None:
            try:
                return self._client.get_config()
            except Exception as exc:
                log.debug("config() fallback: %s", exc)
        return placeholder_config()

    def models(self) -> list[ModelInfo]:
        """Return the list of available models."""
        if self._client is not None:
            try:
                return self._client.list_models()  # type: ignore[no-any-return]
            except Exception as exc:
                log.debug("models() fallback: %s", exc)
        return placeholder_models()  # type: ignore[no-any-return]

    def setup(self) -> SetupState:
        """Return the setup wizard state."""
        if self._client is not None:
            try:
                return self._client.get_setup()
            except Exception as exc:
                log.debug("setup() fallback: %s", exc)
        return placeholder_setup()

    def health(self) -> HealthStatus:
        """Return the gateway health status."""
        if self._client is not None:
            try:
                return self._client.health()
            except Exception as exc:
                log.debug("health() fallback: %s", exc)
        return placeholder_health()

    # ------------------------------------------------------------------
    # Live status
    # ------------------------------------------------------------------

    @property
    def is_live(self) -> bool:
        """True when a gateway client is attached (online mode, not placeholders)."""
        return self._client is not None

    @property
    def client(self) -> GatewayClient | None:
        """The underlying gateway client, or None in offline mode."""
        return self._client

    # ------------------------------------------------------------------
    # Authoring actions
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Memory CRUD
    # ------------------------------------------------------------------

    def add_fact(self, group: str, text: str) -> dict[str, object]:
        """Add a fact to the vault collection *group*. Returns {} on error/offline.

        Args:
            group: Collection name (core_memory | user_profile | agent_profile).
            text:  Plain-text fact to persist.
        """
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.add_memory_fact(group, text)
                return result
            except Exception as exc:
                log.debug("add_fact(%r, ...) error: %s", group, exc)
        return {}

    def delete_fact(self, fact_id: str) -> dict[str, object]:
        """Delete the vault fact with *fact_id*. Returns {} on error/offline.

        Args:
            fact_id: The SHA-256 content hash returned by the add endpoint.
        """
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.delete_memory_fact(fact_id)
                return result
            except Exception as exc:
                log.debug("delete_fact(%r) error: %s", fact_id, exc)
        return {}

    # ------------------------------------------------------------------
    # Config mutations
    # ------------------------------------------------------------------

    def switch_model(self, model: str) -> dict[str, object]:
        """Switch the active provider model via PUT /config/provider. Returns {} on error/offline.

        Args:
            model: The model identifier string (e.g. ``"claude-haiku-4-5"``).
        """
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.set_provider(
                    {"provider": {"model": model}}
                )
                return result
            except Exception as exc:
                log.debug("switch_model(%r) error: %s", model, exc)
        return {}

    def change_tier(self, tier: str) -> dict[str, object]:
        """Change the permission tier via PUT /config/permissions. Returns {} on error/offline.

        Args:
            tier: One of ``sandbox``, ``guided``, ``unrestricted``.
        """
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.set_permissions(
                    {"permissions": {"tier": tier}}
                )
                return result
            except Exception as exc:
                log.debug("change_tier(%r) error: %s", tier, exc)
        return {}

    # ------------------------------------------------------------------
    # Authoring actions
    # ------------------------------------------------------------------

    def authoring_apply(self, name: str) -> dict[str, object]:
        """Apply the pending patch for an authoring target. Returns {} on error/offline."""
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.apply_authoring(name)
                return result
            except Exception as exc:
                log.debug("authoring_apply(%r) error: %s", name, exc)
        return {}

    def authoring_revert(self, name: str) -> dict[str, object]:
        """Revert an authoring target to disk. Returns {} on error/offline."""
        if self._client is not None:
            try:
                result: dict[str, object] = self._client.revert_authoring(name)
                return result
            except Exception as exc:
                log.debug("authoring_revert(%r) error: %s", name, exc)
        return {}

    # ------------------------------------------------------------------
    # Chat session (live) — used by ChatView's streaming worker
    # ------------------------------------------------------------------

    def start_session(self) -> str | None:
        """Create a chat session and return its id, or None offline/on error."""
        if self._client is None:
            return None
        try:
            resp = self._client.create_session(client_id="cockpit", surface="tui")
            sid = resp.get("session_id") or resp.get("id")
            return str(sid) if sid else None
        except Exception as exc:
            log.debug("start_session error: %s", exc)
            return None

    def send(self, session_id: str, text: str) -> dict[str, object]:
        """Send a chat message to *session_id*. Returns {} offline/on error."""
        if self._client is None:
            return {}
        try:
            result: dict[str, object] = self._client.send_message(session_id, text)
            return result
        except Exception as exc:
            log.debug("send error: %s", exc)
            return {}

    def stream(
        self,
        session_id: str,
        after: int = 0,
        stop_event: threading.Event | None = None,
    ) -> Iterator[RuntimeEvent]:
        """Yield runtime events for *session_id* over SSE (empty iterator offline).

        Intended to run inside a Textual thread worker; pass a ``stop_event`` to
        cancel the stream cleanly when the view unmounts or the turn is interrupted.
        """
        if self._client is None:
            empty: list[RuntimeEvent] = []
            return iter(empty)
        return stream_events(  # type: ignore[no-any-return]
            self._client, session_id, after=after, stop_event=stop_event
        )

    # ------------------------------------------------------------------
    # Aggregates (assembled here; no single gateway endpoint)
    # ------------------------------------------------------------------

    def trust_bar(self) -> TrustBarSnapshot:
        """Assemble the TrustBarSnapshot from multiple gateway calls.

        Combines config (tier/model/safety) + pending approval count +
        active job count + total spend cost.  Falls back to placeholder
        on any error.
        """
        if self._client is None:
            return placeholder_trust_bar()

        try:
            cfg = self._client.get_config()
            approvals_list = self._client.list_approvals()
            jobs = self._client.active_jobs()
            sp = self._client.get_spend()

            total_cost = sum(m.cost for m in sp.models) if sp.models else 0.0

            return TrustBarSnapshot(
                tier=cfg.tier,
                safety=cfg.safety,
                model=cfg.model,
                approval_count=len(approvals_list),
                active_job_count=len(jobs),
                total_cost_usd=total_cost,
                reconnecting=False,
            )
        except Exception as exc:
            log.debug("trust_bar() fallback: %s", exc)
            return placeholder_trust_bar()

    def dashboard(self) -> DashboardSnapshot:
        """Assemble the DashboardSnapshot.

        Combines active_jobs + approvals + sessions + trust_bar.
        Falls back to placeholder on any error.
        """
        if self._client is None:
            return placeholder_dashboard()

        try:
            jobs = self._client.active_jobs()
            approvals_list = self._client.list_approvals()
            sess = self._client.list_sessions(limit=5)
            tb = self.trust_bar()

            return DashboardSnapshot(
                active_jobs=jobs,
                pending_approvals=approvals_list,
                recent_sessions=sess,
                trust_bar=tb,
            )
        except Exception as exc:
            log.debug("dashboard() fallback: %s", exc)
            return placeholder_dashboard()
