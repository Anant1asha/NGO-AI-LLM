"""
Hachi Cockpit — synchronous HTTP gateway client.

Built on ``httpx.Client`` (already a project dependency).  Construction is
lazy — no network calls are made until the first method is called.  Every
method raises ``GatewayError`` on HTTP or transport failure; callers should
catch it and fall back to placeholder data from ``gaps.py``.

Usage::

    client = GatewayClient("http://127.0.0.1:8787", token="secret")
    skills = client.list_skills()

Context-manager support::

    with GatewayClient("http://127.0.0.1:8787") as c:
        health = c.health()
"""

from __future__ import annotations

import os
import threading
from types import TracebackType
from typing import Any

import httpx

from .models import (
    ActivityEvent,
    AgentRow,
    Approval,
    AuditEntry,
    AuthTarget,
    Capability,
    ConfigSnapshot,
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
    source_to_diff_lines,
)


class GatewayError(Exception):
    """Raised when an API call fails with an HTTP error or transport error."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class GatewayClient:
    """
    Synchronous REST client for the Hachi gateway.

    Thread-safe via an internal ``threading.Lock``; an ``httpx.Client``
    is created lazily on the first request and reused across calls.
    """

    DEFAULT_TIMEOUT = 15.0

    def __init__(
        self, base_url: str, token: str | None = None, timeout: float | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()
        # Resolve the request timeout. Explicit arg > HACHI_GATEWAY_CLIENT_TIMEOUT env
        # > DEFAULT_TIMEOUT. The env override exists so the test harness can grant a
        # generous timeout for cold/loaded in-process gateway boots (POST /sessions
        # does heavy synchronous skill-engine + vault init that can exceed 15s on a
        # cold Windows process or under full-suite load) without changing the
        # production default. See tests/conftest.py.
        if timeout is None:
            _env_timeout = os.environ.get("HACHI_GATEWAY_CLIENT_TIMEOUT", "").strip()
            if _env_timeout:
                try:
                    timeout = float(_env_timeout)
                except ValueError:
                    timeout = self.DEFAULT_TIMEOUT
            else:
                timeout = self.DEFAULT_TIMEOUT
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        """Lazy init — not called at construction time."""
        with self._lock:
            if self._client is None:
                headers: dict[str, str] = {}
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"
                self._client = httpx.Client(
                    base_url=self._base_url,
                    headers=headers,
                    timeout=self._timeout,
                )
        return self._client

    def _get(self, path: str, **params: Any) -> Any:
        """GET request returning parsed JSON body."""
        client = self._get_client()
        # Strip None params — match TS buildUrl behaviour
        clean_params = {k: v for k, v in params.items() if v is not None}
        try:
            resp = client.get(path, params=clean_params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GatewayError(
                f"GET {path} → {exc.response.status_code}", exc.response.status_code
            ) from exc
        except httpx.TransportError as exc:
            raise GatewayError(f"GET {path} transport error: {exc}") from exc
        return resp.json() if resp.content else None

    def _post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        """POST request returning parsed JSON body."""
        client = self._get_client()
        try:
            resp = client.post(path, json=body or {})
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GatewayError(
                f"POST {path} → {exc.response.status_code}", exc.response.status_code
            ) from exc
        except httpx.TransportError as exc:
            raise GatewayError(f"POST {path} transport error: {exc}") from exc
        return resp.json() if resp.content else None

    def _put(self, path: str, body: dict[str, Any]) -> Any:
        """PUT request returning parsed JSON body."""
        client = self._get_client()
        try:
            resp = client.put(path, json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GatewayError(
                f"PUT {path} → {exc.response.status_code}", exc.response.status_code
            ) from exc
        except httpx.TransportError as exc:
            raise GatewayError(f"PUT {path} transport error: {exc}") from exc
        return resp.json() if resp.content else None

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    def list_skills(self) -> list[Skill]:
        """GET /skills → list[Skill]."""
        raw = self._get("/skills")
        return [Skill.from_api(s) for s in (raw or [])]

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def get_memory(self) -> MemorySnapshot:
        """GET /memory → MemorySnapshot."""
        raw = self._get("/memory")
        return MemorySnapshot.from_api(raw or {})

    def recall(self, query: str, top_k: int = 8) -> list[RecallHit]:
        """GET /memory/recall → list[RecallHit]."""
        raw = self._get("/memory/recall", query=query, top_k=top_k)
        return [RecallHit.from_api(h) for h in (raw or [])]

    def add_memory_fact(self, group: str, text: str) -> dict[str, Any]:
        """POST /memory/facts → raw dict {id: ...}.

        Args:
            group: Collection name — one of core_memory, user_profile, agent_profile.
            text:  Plain-text fact to persist.

        Returns:
            Raw API dict, e.g. ``{"id": "<fact_id>"}``.
        """
        return self._post("/memory/facts", {"group": group, "text": text}) or {}

    def delete_memory_fact(self, fact_id: str) -> dict[str, Any]:
        """DELETE /memory/facts/{fact_id} → raw dict {ok: true}.

        Args:
            fact_id: SHA-256 content hash returned by the add endpoint.

        Returns:
            Raw API dict, e.g. ``{"ok": true}``.
        """
        client = self._get_client()
        path = f"/memory/facts/{fact_id}"
        try:
            resp = client.delete(path)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GatewayError(
                f"DELETE {path} → {exc.response.status_code}", exc.response.status_code
            ) from exc
        except httpx.TransportError as exc:
            raise GatewayError(f"DELETE {path} transport error: {exc}") from exc
        return resp.json() if resp.content else {}

    # ------------------------------------------------------------------
    # OG graph
    # ------------------------------------------------------------------

    def og_graph(self) -> list[OgNode]:
        """GET /og/graph → list[OgNode]."""
        raw = self._get("/og/graph")
        nodes = (raw or {}).get("nodes") or []
        return [OgNode.from_api(n) for n in nodes]

    # ------------------------------------------------------------------
    # Authoring
    # ------------------------------------------------------------------

    def list_authoring_targets(self) -> list[AuthTarget]:
        """GET /authoring/targets → list[AuthTarget]."""
        raw = self._get("/authoring/targets")
        return [AuthTarget.from_api(t) for t in (raw or [])]

    def get_authoring_target(self, name: str) -> tuple[str, list[DiffLine]]:
        """
        GET /authoring/targets/{name} → (source_text, diff_lines).

        Returns the raw source string and a list of neutral DiffLine tuples.
        """
        raw = self._get(f"/authoring/targets/{name}")
        source = (raw or {}).get("source") or ""
        return source, source_to_diff_lines(source)

    def apply_authoring(self, name: str) -> dict[str, Any]:
        """POST /authoring/targets/{name}/apply → raw dict."""
        return self._post(f"/authoring/targets/{name}/apply") or {}

    def revert_authoring(self, name: str) -> dict[str, Any]:
        """POST /authoring/targets/{name}/revert → raw dict."""
        return self._post(f"/authoring/targets/{name}/revert") or {}

    # ------------------------------------------------------------------
    # Spend
    # ------------------------------------------------------------------

    def get_spend(self, session_id: str | None = None) -> SpendSnapshot:
        """GET /spend → SpendSnapshot."""
        raw = self._get("/spend", session_id=session_id)
        return SpendSnapshot.from_api(raw or {})

    # ------------------------------------------------------------------
    # Capabilities / integrations
    # ------------------------------------------------------------------

    def list_capabilities(self) -> list[Capability]:
        """GET /capabilities → list[Capability]."""
        raw = self._get("/capabilities")
        caps = raw if isinstance(raw, list) else (raw or {}).get("capabilities") or []
        return [Capability.from_api(c) for c in caps]

    def set_capability_enabled(self, cap_id: str, enabled: bool) -> dict[str, Any]:
        """PUT /capabilities/{cap_id}/enabled → raw dict."""
        return self._put(f"/capabilities/{cap_id}/enabled", {"enabled": enabled}) or {}

    # ------------------------------------------------------------------
    # MCP inventory
    # ------------------------------------------------------------------

    def mcp_inventory(self) -> tuple[list[McpServer], list[McpTool]]:
        """GET /runtime/mcp/inventory → (servers, tools)."""
        raw = self._get("/runtime/mcp/inventory") or {}
        raw_servers = raw.get("servers") or []
        servers = [McpServer.from_api(s) for s in raw_servers]
        tools: list[McpTool] = []
        for s_raw in raw_servers:
            server_name = s_raw.get("name") or "unknown"
            for tool_name in s_raw.get("tools") or []:
                tools.append(McpTool.from_api(str(tool_name), server_name))
        return servers, tools

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    def list_approvals(self) -> list[Approval]:
        """GET /approvals → list[Approval]."""
        raw = self._get("/approvals") or {}
        return [Approval.from_api(a) for a in (raw.get("pending") or [])]

    def decide_approval(self, request_id: str, action: str, rationale: str = "") -> dict[str, Any]:
        """POST /approvals/{request_id} with {action, rationale} → raw dict."""
        body = {"action": action, "rationale": rationale}
        return self._post(f"/approvals/{request_id}", body) or {}

    def permissions_audit(self, limit: int = 50) -> list[AuditEntry]:
        """GET /permissions/audit → list[AuditEntry]."""
        raw = self._get("/permissions/audit", limit=limit)
        items = raw if isinstance(raw, list) else []
        return [AuditEntry.from_api(e) for e in items]

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def active_jobs(self) -> list[TaskRow]:
        """GET /jobs/active → list[TaskRow]."""
        raw = self._get("/jobs/active")
        items = raw if isinstance(raw, list) else (raw or {}).get("jobs") or []
        return [TaskRow.from_active(j) for j in items]

    def failed_jobs(self, limit: int = 20) -> list[TaskRow]:
        """GET /jobs/failed → list[TaskRow]."""
        raw = self._get("/jobs/failed", limit=limit)
        items = raw if isinstance(raw, list) else []
        return [TaskRow.from_failed(j) for j in items]

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    def list_schedules(self) -> list[Routine]:
        """GET /schedules → list[Routine]."""
        raw = self._get("/schedules") or {}
        schedules = raw.get("schedules") or (raw if isinstance(raw, list) else [])
        return [Routine.from_api(s) for s in schedules]

    def set_schedule_enabled(self, schedule_id: str, enabled: bool) -> dict[str, Any]:
        """PUT /schedules/{schedule_id}/enabled → raw dict."""
        return self._put(f"/schedules/{schedule_id}/enabled", {"enabled": enabled}) or {}

    def delete_schedule(self, schedule_id: str) -> dict[str, Any]:
        """DELETE /schedules/{schedule_id} → raw dict."""
        client = self._get_client()
        try:
            resp = client.delete(f"/schedules/{schedule_id}")
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GatewayError(
                f"DELETE /schedules/{schedule_id} → {exc.response.status_code}",
                exc.response.status_code,
            ) from exc
        except httpx.TransportError as exc:
            raise GatewayError(f"DELETE /schedules/{schedule_id} transport error: {exc}") from exc
        return resp.json() if resp.content else {}

    # ------------------------------------------------------------------
    # Config & models
    # ------------------------------------------------------------------

    def get_config(self) -> ConfigSnapshot:
        """GET /config → ConfigSnapshot."""
        raw = self._get("/config")
        return ConfigSnapshot.from_api(raw or {})

    def set_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        """PUT /config/provider → raw dict (full updated config).

        Body shape: ``{"provider": {"model": "...", "kind": "...", ...}}``
        The gateway accepts any subset of provider fields and merges them.

        Args:
            payload: Dict with a ``provider`` key containing the fields to update.

        Returns:
            Raw API dict (full config after update).
        """
        return self._put("/config/provider", payload) or {}

    def set_permissions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """PUT /config/permissions → raw dict (full updated config).

        Body shape: ``{"permissions": {"tier": "sandbox|guided|unrestricted"}}``

        Args:
            payload: Dict with a ``permissions`` key containing the fields to update.

        Returns:
            Raw API dict (full config after update).
        """
        return self._put("/config/permissions", payload) or {}

    def validate_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /config/provider/validate → raw dict {ok, errors, warnings}.

        Body shape: ``{"provider": {"kind": "...", "model": "...", ...}}``

        Args:
            payload: Dict with a ``provider`` key containing fields to validate.

        Returns:
            Raw API dict with ``ok``, ``errors``, and ``warnings`` keys.
        """
        return self._post("/config/provider/validate", payload) or {}

    def list_models(self) -> list[ModelInfo]:
        """GET /models → list[ModelInfo]."""
        raw = self._get("/models")
        items = raw if isinstance(raw, list) else []
        return [ModelInfo.from_api(m) for m in items]

    # ------------------------------------------------------------------
    # Sub-agents & runtime events
    # ------------------------------------------------------------------

    def subagent_reports(self, top_k: int = 10) -> list[AgentRow]:
        """GET /subagents/reports → list[AgentRow]."""
        raw = self._get("/subagents/reports", top_k=top_k)
        items = raw if isinstance(raw, list) else []
        return [AgentRow.from_api(r) for r in items]

    def runtime_events(
        self, session_id: str | None = None, limit: int = 100
    ) -> tuple[list[ActivityEvent], list[ToolCallRow]]:
        """
        GET /runtime/events → (activity_events, tool_calls).

        Derives ``ToolCallRow`` from paired started/completed events, matching
        the TypeScript operator domain adapter logic.
        """
        raw = self._get("/runtime/events", session_id=session_id, limit=limit)
        items: list[dict[str, Any]] = raw if isinstance(raw, list) else []
        events = [ActivityEvent.from_api(e) for e in items]
        tool_calls = _derive_tool_calls(items)
        return events, tool_calls

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def list_sessions(self, limit: int = 10) -> list[SessionInfo]:
        """GET /sessions → list[SessionInfo]."""
        raw = self._get("/sessions", limit=limit)
        items = raw if isinstance(raw, list) else []
        return [SessionInfo.from_api(s, i) for i, s in enumerate(items)]

    def get_session(self, session_id: str) -> dict[str, Any]:
        """GET /sessions/{session_id} → raw dict."""
        return self._get(f"/sessions/{session_id}") or {}

    def send_message(self, session_id: str, text: str) -> dict[str, Any]:
        """POST /sessions/{session_id}/messages → raw dict {session_id, response}."""
        return self._post(f"/sessions/{session_id}/messages", {"prompt": text}) or {}

    def create_session(
        self,
        client_id: str = "tui",
        surface: str = "tui",
        protocol_version: str = "1.0",
        capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """POST /sessions → raw SessionCreateResponse dict."""
        return (
            self._post(
                "/sessions",
                {
                    "client_id": client_id,
                    "surface": surface,
                    "protocol_version": protocol_version,
                    "capabilities": capabilities or [],
                },
            )
            or {}
        )

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def get_setup(self) -> SetupState:
        """GET /setup → SetupState."""
        raw = self._get("/setup")
        return SetupState.from_api(raw or {})

    def apply_setup(self, plan: dict[str, Any]) -> dict[str, Any]:
        """POST /setup/apply → raw dict."""
        return self._post("/setup/apply", {"plan": plan}) or {}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> HealthStatus:
        """GET /health → HealthStatus."""
        raw = self._get("/health")
        return HealthStatus.from_api(raw or {})

    def readiness(self) -> dict[str, Any]:
        """GET /readiness → raw dict."""
        return self._get("/readiness") or {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying httpx client."""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    def __enter__(self) -> GatewayClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Internal: tool-call derivation (mirrors TS adaptToolCalls)
# ---------------------------------------------------------------------------


def _derive_tool_calls(events: list[dict[str, Any]]) -> list[ToolCallRow]:
    """Pair tool.call.started / tool.call.completed events → ToolCallRow list."""
    import datetime as _dt

    started: list[dict[str, Any]] = []
    completed: dict[str, dict[str, Any]] = {}  # keyed by tool name (latest wins)

    for ev in events:
        name = ev.get("name") or ""
        payload = ev.get("payload") or {}
        if name == "tool.call.started":
            started.append(
                {
                    "tool": payload.get("name") or "unknown",
                    "inp": payload.get("input") or str(payload),
                    "ts": ev.get("timestamp") or "",
                }
            )
        elif name == "tool.call.completed":
            tool_name = payload.get("name") or ""
            completed[tool_name] = ev

    rows: list[ToolCallRow] = []
    for s in started:
        comp = completed.get(s["tool"])
        comp_payload = (comp or {}).get("payload") or {}
        out = comp_payload.get("result_preview") or comp_payload.get("detail") or "—"
        dur = "—"
        if comp and s["ts"]:
            try:
                t_start = _dt.datetime.fromisoformat(s["ts"].replace("Z", "+00:00"))
                t_end = _dt.datetime.fromisoformat(
                    (comp.get("timestamp") or "").replace("Z", "+00:00")
                )
                diff_ms = int((t_end - t_start).total_seconds() * 1000)
                dur = f"{diff_ms}ms" if diff_ms < 1000 else f"{diff_ms / 1000:.1f}s"
            except Exception:
                pass
        rows.append(
            ToolCallRow(
                tool=s["tool"],
                inp=str(s["inp"]),
                out=str(out),
                dur=dur,
                ts=_format_ts_local(s["ts"]),
            )
        )
    return rows


def _format_ts_local(iso_ts: str) -> str:
    import datetime as _dt

    if not iso_ts:
        return "—"
    try:
        d = _dt.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return d.strftime("%H:%M:%S")
    except Exception:
        return iso_ts
