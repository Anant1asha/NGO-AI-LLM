from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import uvicorn

PROTOCOL_VERSION = "1.0"


@dataclass(frozen=True)
class ConnectRequest:
    client_id: str
    surface: str
    protocol_version: str
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectResponse:
    session_id: str
    protocol_version: str
    accepted: bool
    server_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class ChatRequest:
    session_id: str
    prompt: str


@dataclass(frozen=True)
class ChatResponse:
    session_id: str
    response: str


@dataclass(frozen=True)
class GatewayEvent:
    sequence: int
    event_type: str
    payload: dict[str, Any]
    time: str


class GatewayProtocolError(ValueError):
    """Raised when a typed gateway envelope is malformed."""

    def __init__(self, message: str, *, code: str = "protocol_error") -> None:
        super().__init__(message)
        self.code = code


class SessionExpiredError(GatewayProtocolError):
    """Raised when a session_id is known in SQLite but not in active memory.

    Issue 1: frontend can distinguish this from an unknown/garbage id and
    initiate a graceful session re-creation rather than showing a generic error.
    The ``code`` attribute is always ``"session_expired"``.
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session '{session_id}' is no longer active. Create a new session to continue.",
            code="session_expired",
        )
        self.session_id = session_id


class GatewayUnavailableError(RuntimeError):
    """Raised when a requested gateway operation is unavailable."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class GatewayControlPlane:
    """Typed gateway control plane with runtime, read-model, and setup/config surfaces."""

    def __init__(
        self,
        readiness_probe: (
            Callable[[], tuple[bool, list[str]] | tuple[bool, list[str], dict[str, str]]] | None
        ) = None,
        on_connect: Callable[[str, ConnectRequest], None] | None = None,
        on_disconnect: Callable[[str], None] | None = None,
        on_chat: Callable[[str, str], str] | None = None,
        read_events: Callable[[str, int, int], list[GatewayEvent]] | None = None,
        get_session_state: Callable[[str], dict[str, Any]] | None = None,
        get_recent_sessions: Callable[[int], list[dict[str, Any]]] | None = None,
        get_session_messages: Callable[[str, int], list[dict[str, Any]]] | None = None,
        delete_session: Callable[[str], bool] | None = None,
        get_runtime_events: Callable[[str | None, int], list[dict[str, Any]]] | None = None,
        get_mcp_inventory: Callable[[], dict[str, Any]] | None = None,
        get_active_jobs: Callable[[], list[dict[str, Any]]] | None = None,
        get_failed_jobs: Callable[[int], list[dict[str, Any]]] | None = None,
        get_permission_audit: Callable[[int], list[dict[str, Any]]] | None = None,
        get_subagent_reports: Callable[[str, int], list[dict[str, Any]]] | None = None,
        get_capabilities: Callable[[], list[dict[str, Any]]] | None = None,
        get_config: Callable[[], dict[str, Any]] | None = None,
        update_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        validate_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        update_permissions: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        update_memory: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        list_models: Callable[[], list[dict[str, Any]]] | None = None,
        get_setup_state: Callable[[], dict[str, Any]] | None = None,
        apply_setup: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        list_schedules: Callable[[], list[dict[str, Any]]] | None = None,
        cancel_schedule: Callable[[str], dict[str, Any]] | None = None,
        toggle_schedule: Callable[[str, bool], dict[str, Any]] | None = None,
        run_schedule_now: Callable[[str], dict[str, Any]] | None = None,
        get_skills: Callable[[], list[dict[str, Any]]] | None = None,
        get_memory: Callable[[], dict[str, Any]] | None = None,
        get_memory_recall: Callable[[str, int], list[dict[str, Any]]] | None = None,
        get_og_graph: Callable[[], dict[str, Any]] | None = None,
        get_authoring_targets: Callable[[], list[dict[str, Any]]] | None = None,
        get_authoring_target: Callable[[str], dict[str, Any]] | None = None,
        authoring_generate: Callable[[str, str], dict[str, Any]] | None = None,
        authoring_apply: Callable[[str], dict[str, Any]] | None = None,
        authoring_revert: Callable[[str], dict[str, Any]] | None = None,
        authoring_save_source: Callable[[str, str], dict[str, Any]] | None = None,
        get_spend: Callable[[str | None], dict[str, Any]] | None = None,
        get_spend_daily: Callable[[], dict[str, Any]] | None = None,
        set_capability_enabled: Callable[[str, bool], dict[str, Any]] | None = None,
        add_memory_fact: Callable[[str, str], dict[str, Any]] | None = None,
        delete_memory_fact: Callable[[str], dict[str, Any]] | None = None,
        # G1 — new handlers
        update_limits: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        add_allowed_folder: Callable[[str], dict[str, Any]] | None = None,
        add_allowed_command: Callable[[str], dict[str, Any]] | None = None,
        remove_allowed_folder: Callable[[str], dict[str, Any]] | None = None,
        remove_allowed_command: Callable[[str], dict[str, Any]] | None = None,
        add_always_allow: Callable[[str, str, str], dict[str, Any]] | None = None,
        register_mcp_server: (Callable[..., dict[str, Any]] | None) = None,
        set_mcp_enabled: Callable[[str, bool], dict[str, Any]] | None = None,
        delete_mcp_server: Callable[[str], dict[str, Any]] | None = None,
        get_kennel: Callable[[], list[dict[str, Any]]] | None = None,
        add_skill: Callable[[str], dict[str, Any]] | None = None,
        # Multi-provider admin handlers
        list_providers: Callable[[], dict[str, Any]] | None = None,
        add_or_update_provider: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        remove_provider: Callable[[str], dict[str, Any]] | None = None,
        get_routing: Callable[[], dict[str, Any]] | None = None,
        set_routing: Callable[[str, dict[str, list[str]]], dict[str, Any]] | None = None,
        validate_routing: Callable[[str, dict[str, list[str]]], dict[str, Any]] | None = None,
        rollback_routing: Callable[[], dict[str, Any]] | None = None,
        get_routing_audit: Callable[[int], list[dict[str, Any]]] | None = None,
        test_provider_connection: Callable[[str], dict[str, Any]] | None = None,
        list_all_models: Callable[[], dict[str, Any]] | None = None,
        probe_provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        # P1-4 — server-side turn interrupt
        on_interrupt: Callable[[str], dict[str, Any]] | None = None,
        # Credential manager (cred: namespace)
        store_secret: Callable[[str, str], dict[str, Any]] | None = None,
        list_secret_names: Callable[[], dict[str, Any]] | None = None,
        delete_secret: Callable[[str], dict[str, Any]] | None = None,
        # Tavily live reload
        reload_search_tools: Callable[[], dict[str, Any]] | None = None,
        max_active_sessions: int = 100,
        max_prompt_chars: int = 100_000,
    ) -> None:
        self._readiness_probe = readiness_probe or (lambda: (True, []))
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_chat = on_chat
        self._read_events = read_events
        self._get_session_state = get_session_state
        self._get_recent_sessions = get_recent_sessions
        self._get_session_messages = get_session_messages
        self._delete_session = delete_session
        self._get_runtime_events = get_runtime_events
        self._get_mcp_inventory = get_mcp_inventory
        self._get_active_jobs = get_active_jobs
        self._get_failed_jobs = get_failed_jobs
        self._get_permission_audit = get_permission_audit
        self._get_subagent_reports = get_subagent_reports
        self._get_capabilities = get_capabilities
        self._get_config = get_config
        self._update_provider = update_provider
        self._validate_provider = validate_provider
        self._update_permissions = update_permissions
        self._update_memory = update_memory
        self._list_models = list_models
        self._get_setup_state = get_setup_state
        self._apply_setup = apply_setup
        self._list_schedules = list_schedules
        self._cancel_schedule = cancel_schedule
        self._toggle_schedule = toggle_schedule
        self._run_schedule_now = run_schedule_now
        self._get_skills = get_skills
        self._get_memory = get_memory
        self._get_memory_recall = get_memory_recall
        self._get_og_graph = get_og_graph
        self._get_authoring_targets = get_authoring_targets
        self._get_authoring_target = get_authoring_target
        self._authoring_generate = authoring_generate
        self._authoring_apply = authoring_apply
        self._authoring_revert = authoring_revert
        self._authoring_save_source = authoring_save_source
        self._get_spend = get_spend
        self._get_spend_daily = get_spend_daily
        self._set_capability_enabled = set_capability_enabled
        self._add_memory_fact = add_memory_fact
        self._delete_memory_fact = delete_memory_fact
        # G1 — new handlers
        self._update_limits = update_limits
        self._add_allowed_folder = add_allowed_folder
        self._add_allowed_command = add_allowed_command
        self._remove_allowed_folder = remove_allowed_folder
        self._remove_allowed_command = remove_allowed_command
        self._add_always_allow = add_always_allow
        self._register_mcp_server = register_mcp_server
        self._set_mcp_enabled = set_mcp_enabled
        self._delete_mcp_server = delete_mcp_server
        self._get_kennel = get_kennel
        self._add_skill = add_skill
        # Multi-provider admin handlers
        self._list_providers = list_providers
        self._add_or_update_provider = add_or_update_provider
        self._remove_provider = remove_provider
        self._get_routing = get_routing
        self._set_routing = set_routing
        self._validate_routing_handler = validate_routing
        self._rollback_routing_handler = rollback_routing
        self._get_routing_audit_handler = get_routing_audit
        self._test_provider_connection = test_provider_connection
        self._list_all_models = list_all_models
        self._probe_provider = probe_provider
        self._on_interrupt = on_interrupt
        self._store_secret = store_secret
        self._list_secret_names = list_secret_names
        self._delete_secret = delete_secret
        self._reload_search_tools = reload_search_tools
        self._connections: dict[str, dict[str, Any]] = {}
        self._api_sessions: dict[str, str] = {}  # session_key -> session_id (facade sessions)
        self._connections_lock = threading.Lock()
        self._max_active_sessions = max(1, max_active_sessions)
        self._max_prompt_chars = max(1, max_prompt_chars)

    def _require_handler(self, handler: Any, operation: str) -> Any:
        if handler is None:
            raise GatewayUnavailableError(f"{operation} is not attached")
        return handler

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "hachi-gateway",
            "protocol_version": PROTOCOL_VERSION,
            "time": _now_iso(),
        }

    def readiness(self) -> dict[str, Any]:
        """Return a structured readiness payload.

        The registered probe may return either a legacy ``(ready, blockers)``
        two-tuple or the extended ``(ready, blockers, checks)`` three-tuple.
        Both forms are handled transparently; callers always receive a payload
        that includes the ``checks`` key (empty dict for legacy probes).
        """
        result = self._readiness_probe()
        ready: bool = result[0]
        blockers: list[str] = result[1]
        checks: dict[str, str] = result[2] if len(result) == 3 else {}
        with self._connections_lock:
            active = len(self._connections)
        return {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "blockers": blockers,
            "checks": checks,
            "active_connections": active,
            "time": _now_iso(),
        }

    def create_session(
        self,
        *,
        client_id: str,
        surface: str,
        capabilities: list[str] | tuple[str, ...] | None = None,
        protocol_version: str = PROTOCOL_VERSION,
    ) -> dict[str, Any]:
        normalized_client_id = client_id.strip()
        normalized_surface = surface.strip()
        capabilities_raw = list(capabilities or [])

        if not normalized_client_id:
            raise GatewayProtocolError("client_id is required")
        if not normalized_surface:
            raise GatewayProtocolError("surface is required")
        if protocol_version != PROTOCOL_VERSION:
            raise GatewayProtocolError(
                f"Unsupported protocol_version '{protocol_version}'. Expected '{PROTOCOL_VERSION}'"
            )
        if not all(isinstance(item, str) for item in capabilities_raw):
            raise GatewayProtocolError("capabilities must be a list of strings")

        req = ConnectRequest(
            client_id=normalized_client_id,
            surface=normalized_surface,
            protocol_version=protocol_version,
            capabilities=tuple(capabilities_raw),
        )

        with self._connections_lock:
            if len(self._connections) >= self._max_active_sessions:
                raise GatewayProtocolError(
                    f"Maximum active sessions reached ({self._max_active_sessions})."
                )
            session_id = str(uuid.uuid4())
            self._connections[session_id] = {
                "client_id": req.client_id,
                "surface": req.surface,
                "capabilities": list(req.capabilities),
                "connected_at": _now_iso(),
                # C1: store owner hash at creation time; None means no-auth / legacy.
                "owner_token_hash": None,
            }

        if self._on_connect is not None:
            try:
                self._on_connect(session_id, req)
            except Exception:
                # Boot (agent/MCP/DB init) failed — release the registered session
                # slot so repeated failed connects don't exhaust max_active_sessions.
                with self._connections_lock:
                    self._connections.pop(session_id, None)
                raise

        response = ConnectResponse(
            session_id=session_id,
            protocol_version=PROTOCOL_VERSION,
            accepted=True,
            server_capabilities=(
                "health",
                "readiness",
                "chat",
                "events",
                "session_state",
                "recent_sessions",
                "runtime_events",
                "mcp_inventory",
                "active_jobs",
                "failed_jobs",
                "permission_audit",
                "subagent_reports",
                "capabilities",
                "config",
                "models",
                "setup",
            ),
        )

        return {
            "accepted": response.accepted,
            "session_id": response.session_id,
            "protocol_version": response.protocol_version,
            "server_capabilities": list(response.server_capabilities),
        }

    def set_session_owner(self, session_id: str, owner_token_hash: str) -> None:
        """Record the sha256(bearer_token) digest as the owner of this session.

        C1 — called by the FastAPI layer immediately after create_session returns,
        using the digest of the validated bearer token.  Stored in-memory for
        fast O(1) ownership checks on every subsequent request.

        Args:
            session_id: The session created by this caller.
            owner_token_hash: sha256 hex-digest of the caller's raw bearer token.
        """
        with self._connections_lock:
            if session_id in self._connections:
                self._connections[session_id]["owner_token_hash"] = owner_token_hash

    def get_session_owner(self, session_id: str) -> str | None:
        """Return the stored owner_token_hash for a session, or None if not set.

        C1 — None means a legacy / no-auth session; callers MUST allow access
        (backward-compat policy: NULL owner = allow).

        Args:
            session_id: Session to query.

        Returns:
            sha256 hex-digest string, or None for legacy / anonymous sessions.
        """
        with self._connections_lock:
            record = self._connections.get(session_id)
        if record is None:
            return None
        return record.get("owner_token_hash")

    def send_message(self, *, session_id: str, prompt: str) -> dict[str, Any]:
        if self._on_chat is None:
            raise GatewayUnavailableError("chat runtime is not attached")

        normalized_session_id = session_id.strip()
        normalized_prompt = prompt.strip()
        if not normalized_session_id:
            raise GatewayProtocolError("session_id is required")
        with self._connections_lock:
            if normalized_session_id not in self._connections:
                # Issue 1: distinguish a known-but-expired session (has history in SQLite)
                # from a garbage id so the frontend can recover gracefully.
                # TODO(issue1): full session re-boot-on-resume — for now surface a typed
                # SessionExpiredError so the caller can create a new session and optionally
                # replay history via GET /sessions/{id}/events before continuing.
                _known_in_db = self._is_session_in_store(normalized_session_id)
                raise (
                    SessionExpiredError(normalized_session_id)
                    if _known_in_db
                    else (
                        GatewayProtocolError(
                            f"Unknown session_id '{normalized_session_id}'",
                            code="unknown_session",
                        )
                    )
                )
        if not normalized_prompt:
            raise GatewayProtocolError("prompt is required")
        if len(prompt) > self._max_prompt_chars:
            raise GatewayProtocolError(
                f"prompt exceeds max length of {self._max_prompt_chars} characters"
            )

        req = ChatRequest(session_id=normalized_session_id, prompt=normalized_prompt)
        result = self._on_chat(req.session_id, req.prompt)
        response = ChatResponse(
            session_id=req.session_id,
            response=result,
        )

        return {
            "session_id": response.session_id,
            "response": response.response,
        }

    def get_or_create_session(
        self, session_key: str = "__default__", *, owner_token_hash: str | None = None
    ) -> str:
        """Return the session_id for ``session_key``, creating it if necessary.

        Extracted from ``complete_chat`` so the streaming path can obtain the
        session_id before launching a background turn, enabling event polling
        while the turn runs.

        Args:
            session_key: The facade key (e.g. ``f"{channel}:{sender}"`` or the
                OpenAI-compat chat id) mapped to a real session_id.
            owner_token_hash: H6 — sha256 hex-digest of the caller's bearer
                token, stamped as the owner the first time this session_key is
                created, exactly like the normal ``POST /sessions`` route
                does via ``set_session_owner``. ``None`` (no-auth mode / no
                caller context) leaves the session ownerless, matching legacy
                behaviour.
        """
        with self._connections_lock:
            session_id = self._api_sessions.get(session_key)
            known = bool(session_id and session_id in self._connections)
        if not known:
            created = self.create_session(
                client_id=f"api:{session_key}",
                surface="api",
                protocol_version=PROTOCOL_VERSION,
                capabilities=[],
            )
            session_id = created["session_id"]
            with self._connections_lock:
                self._api_sessions[session_key] = session_id
            # H6: stamp ownership immediately, mirroring the /sessions create route —
            # facade sessions (OpenAI-compat, channel-inbound) must not be ownerless.
            if owner_token_hash is not None:
                self.set_session_owner(session_id, owner_token_hash)
        assert session_id is not None, "session_id must be set after get_or_create_session"
        return session_id

    def complete_chat(
        self,
        prompt: str,
        *,
        session_key: str = "__default__",
        owner_token_hash: str | None = None,
    ) -> dict[str, Any]:
        """Run a prompt through an auto-managed session keyed by ``session_key``.

        Powers stateless-looking facades (OpenAI-compatible endpoint, channel
        webhooks) that don't manage sessions themselves: the first call for a key
        creates a session (booting an agent via on_connect), subsequent calls
        reuse it so the conversation keeps continuity.

        Args:
            owner_token_hash: H6 — forwarded to ``get_or_create_session`` so a
                freshly-created facade session is stamped with the caller's
                identity instead of staying ownerless.
        """
        session_id = self.get_or_create_session(session_key, owner_token_hash=owner_token_hash)
        return self.send_message(session_id=session_id, prompt=prompt)

    def close_session(self, session_id: str) -> dict[str, Any]:
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise GatewayProtocolError("session_id is required")
        was_live = False
        with self._connections_lock:
            if normalized_session_id in self._connections:
                was_live = True
                self._connections.pop(normalized_session_id, None)
                # Prune any api-facade session-key that pointed at this session_id.
                stale_keys = [
                    k for k, v in self._api_sessions.items() if v == normalized_session_id
                ]
                for k in stale_keys:
                    del self._api_sessions[k]
        if was_live and self._on_disconnect is not None:
            self._on_disconnect(normalized_session_id)

        # Also remove the persisted record so the conversation disappears from the
        # recent-sessions list. The recent list is keyed by SessionStore ids, which
        # are never live connections — so historical sessions are delete-only here.
        deleted = False
        if self._delete_session is not None:
            try:
                deleted = bool(self._delete_session(normalized_session_id))
            except Exception:
                deleted = False

        if not was_live and not deleted:
            raise GatewayProtocolError("Unknown session_id")

        return {"session_id": normalized_session_id, "closed": True}

    def read_session_events(
        self, session_id: str, after: int = 0, limit: int = 100
    ) -> dict[str, Any]:
        if not session_id:
            raise GatewayProtocolError("session_id is required")

        safe_limit = max(1, min(limit, 500))
        safe_after = max(0, after)

        with self._connections_lock:
            is_live = session_id in self._connections

        if is_live:
            if self._read_events is None:
                raise GatewayUnavailableError("event stream is not attached")
            batch = self._read_events(session_id, safe_after, safe_limit)
            next_sequence = safe_after
            if batch:
                next_sequence = batch[-1].sequence
            return {
                "session_id": session_id,
                "events": [
                    {
                        "sequence": event.sequence,
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "time": event.time,
                    }
                    for event in batch
                ],
                "next_sequence": next_sequence,
            }

        # Not a live connection — replay the persisted transcript so a past session
        # can be resumed. We synthesize the same event envelopes the client already
        # reconstructs from a live turn, so the UI replay path is identical.
        if self._get_session_messages is None:
            raise GatewayProtocolError("Unknown session_id")
        events = self._synthesize_history_events(session_id, safe_after, safe_limit)
        next_sequence = events[-1]["sequence"] if events else safe_after
        return {
            "session_id": session_id,
            "events": events,
            "next_sequence": next_sequence,
        }

    def _synthesize_history_events(
        self, session_id: str, after: int, limit: int
    ) -> list[dict[str, Any]]:
        """Turn a stored transcript into the event envelopes the client replays.

        user msg  → ``session.turn.started`` {user_text}
        assistant → ``text.stream.delta`` {text} + ``session.chat.completed``
        tool msg  → ``tool.call.completed`` {name, result_preview}
        """
        if self._get_session_messages is None:
            return []
        messages = self._get_session_messages(session_id, 500) or []
        events: list[dict[str, Any]] = []
        seq = 0
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content") or ""
            ts = msg.get("time") or msg.get("timestamp") or ""
            if role == "user":
                seq += 1
                events.append(
                    {
                        "sequence": seq,
                        "event_type": "session.turn.started",
                        "payload": {"user_text": content},
                        "time": ts,
                    }
                )
            elif role == "assistant":
                seq += 1
                events.append(
                    {
                        "sequence": seq,
                        "event_type": "text.stream.delta",
                        "payload": {"text": content},
                        "time": ts,
                    }
                )
                seq += 1
                events.append(
                    {
                        "sequence": seq,
                        "event_type": "session.chat.completed",
                        "payload": {"model": msg.get("model")},
                        "time": ts,
                    }
                )
            elif role == "tool":
                seq += 1
                events.append(
                    {
                        "sequence": seq,
                        "event_type": "tool.call.completed",
                        "payload": {
                            "name": msg.get("tool_name") or "tool",
                            "result_preview": content,
                        },
                        "time": ts,
                    }
                )
        # Honour pagination: drop events at/below `after`, cap to `limit`.
        return [e for e in events if e["sequence"] > after][:limit]

    def _is_session_in_store(self, session_id: str) -> bool:
        """Return True when *session_id* exists as a row in the SQLite session store.

        Used by :meth:`send_message` and :meth:`session_state` to distinguish a
        known-but-expired session from a garbage id. Safe to call outside the
        connections lock — reads from the already-initialised SQLite store.

        Returns:
            True if the session has a persisted record; False if unknown or the
            store handler is not wired.
        """
        if self._get_session_messages is None:
            return False
        try:
            messages = self._get_session_messages(session_id, 1)
            # A non-empty list means the session has at least one persisted message.
            # An empty list means the session id is unknown (no messages ever written).
            return isinstance(messages, list) and len(messages) > 0
        except Exception:
            return False

    def session_state(self, session_id: str) -> Any:
        """Return a state dict for *session_id*.

        Issue 1: when the session is not in the in-memory connection map (e.g.
        the gateway process restarted), fall back to a lightweight dict built
        from the SQLite transcript so the UI can still show session metadata
        without raising ``GatewayProtocolError("Unknown session_id")``.

        Args:
            session_id: The session to query.

        Returns:
            A state dict.  Live sessions use the full handler; dead-but-known
            sessions return a minimal ``{"session_id": ..., "status": "expired"}``
            dict.  Completely unknown ids raise ``GatewayProtocolError``.
        """
        if not session_id:
            raise GatewayProtocolError("session_id is required")
        with self._connections_lock:
            is_live = session_id in self._connections

        if is_live:
            handler = self._require_handler(self._get_session_state, "session state")
            return handler(session_id)

        # Not live — check SQLite before raising so a page-refresh after a gateway
        # restart returns usable metadata rather than an error.
        if self._is_session_in_store(session_id):
            return {
                "session_id": session_id,
                "status": "expired",
                "active_skill": None,
                "last_user_query": "",
                "model_name": None,
                "boot_ready": False,
                "pending_job_count": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            }

        raise GatewayProtocolError(f"Unknown session_id '{session_id}'", code="unknown_session")

    def recent_sessions(self, limit: int = 10) -> Any:
        handler = self._require_handler(self._get_recent_sessions, "recent sessions")
        return handler(max(1, min(limit, 100)))

    def runtime_events(self, session_id: str | None, limit: int = 100) -> Any:
        handler = self._require_handler(self._get_runtime_events, "runtime events")
        normalized_session_id = session_id.strip() if isinstance(session_id, str) else ""
        return handler(normalized_session_id or None, max(1, min(limit, 500)))

    def mcp_inventory(self) -> Any:
        """Return the MCP server inventory with ``enabled`` state from settings.toml.

        Merges the live agent's inventory (name/status/tools/transport/err) with
        the persisted ``enabled`` boolean from ``[mcp_servers]`` in settings.toml.
        Servers not present in settings.toml default to ``enabled=True`` (they were
        configured via .og / device-permissions.og, not via the register API).
        """
        handler = self._require_handler(self._get_mcp_inventory, "MCP inventory")
        raw: dict[str, Any] = handler()

        # Load enabled-state map from settings.toml.
        enabled_map: dict[str, bool] = {}
        try:
            from hachi.core.paths import get_hachi_paths as _get_paths

            config_toml = _get_paths().global_config_toml
            if config_toml.exists():
                import tomlkit as _tomlkit

                doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
                for sname, sentry in (doc.get("mcp_servers") or {}).items():
                    enabled_map[str(sname)] = bool(sentry.get("enabled", True))
        except Exception:
            pass  # Best-effort; leave enabled_map empty → all default True.

        # Inject enabled field into each server entry.
        servers = raw.get("servers", [])
        enriched: list[dict[str, Any]] = []
        for server in servers:
            sdict = dict(server) if not isinstance(server, dict) else server
            sname = sdict.get("name", "")
            sdict["enabled"] = enabled_map.get(sname, True)
            enriched.append(sdict)

        # BB-10: Merge TOML-only servers (persisted but not yet started in this
        # session) so the inventory is complete even when no agent is live.
        # "pending_restart" means "not yet attempted in the current session";
        # a prior session's failure reason is not persisted, so it cannot be shown.
        try:
            from hachi.core.paths import get_hachi_paths as _get_paths

            config_toml = _get_paths().global_config_toml
            if config_toml.exists():
                import tomlkit as _tomlkit

                _doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
                live_names = {s.get("name", "") for s in enriched}
                for sname, sentry in (_doc.get("mcp_servers") or {}).items():
                    if str(sname) in live_names:
                        continue
                    enriched.append(
                        {
                            "name": str(sname),
                            "status": "pending_restart",
                            "transport": sentry.get("transport", "stdio"),
                            "tool_count": 0,
                            "tools": [],
                            "enabled": enabled_map.get(
                                str(sname), bool(sentry.get("enabled", True))
                            ),
                            "err": None,
                        }
                    )
        except Exception:
            pass  # Best-effort; live servers are still shown.

        raw["servers"] = enriched
        return raw

    def active_jobs(self) -> Any:
        handler = self._require_handler(self._get_active_jobs, "active jobs")
        return handler()

    def failed_jobs(self, limit: int = 20) -> Any:
        handler = self._require_handler(self._get_failed_jobs, "failed jobs")
        return handler(max(1, min(limit, 200)))

    def permission_audit(self, limit: int = 50) -> Any:
        handler = self._require_handler(self._get_permission_audit, "permission audit")
        return handler(max(1, min(limit, 500)))

    def subagent_reports(self, query: str = "recent delegation", top_k: int = 10) -> Any:
        handler = self._require_handler(self._get_subagent_reports, "subagent reports")
        query_text = query.strip() if query else "recent delegation"
        return handler(query_text, max(1, min(top_k, 100)))

    def capabilities(self) -> Any:
        handler = self._require_handler(self._get_capabilities, "capabilities")
        return handler()

    def get_config(self) -> Any:
        handler = self._require_handler(self._get_config, "config")
        return handler()

    def update_provider(self, payload: dict[str, Any]) -> Any:
        handler = self._require_handler(self._update_provider, "provider update")
        return handler(payload)

    def validate_provider(self, payload: dict[str, Any]) -> Any:
        handler = self._require_handler(self._validate_provider, "provider validation")
        return handler(payload)

    def update_permissions(self, payload: dict[str, Any]) -> Any:
        handler = self._require_handler(self._update_permissions, "permissions update")
        return handler(payload)

    def update_memory(self, payload: dict[str, Any]) -> Any:
        handler = self._require_handler(self._update_memory, "memory update")
        return handler(payload)

    def models(self) -> Any:
        handler = self._require_handler(self._list_models, "model listing")
        return handler()

    def setup_state(self) -> Any:
        handler = self._require_handler(self._get_setup_state, "setup state")
        return handler()

    def apply_setup(self, payload: dict[str, Any]) -> Any:
        handler = self._require_handler(self._apply_setup, "setup apply")
        return handler(payload)

    def list_schedules(self) -> Any:
        if self._list_schedules is None:
            return []
        return self._list_schedules()

    def cancel_schedule(self, schedule_id: str) -> Any:
        if self._cancel_schedule is None:
            return {"ok": False, "detail": "schedules not available"}
        return self._cancel_schedule(schedule_id)

    def toggle_schedule(self, schedule_id: str, enabled: bool) -> Any:
        if self._toggle_schedule is None:
            return {"ok": False, "detail": "schedules not available"}
        return self._toggle_schedule(schedule_id, enabled)

    def run_schedule_now(self, schedule_id: str) -> Any:
        if self._run_schedule_now is None:
            return {"ok": False, "detail": "schedules not available"}
        return self._run_schedule_now(schedule_id)

    # ==========================================
    # Web endpoint handlers — added for web UI (#1–#6)
    # ==========================================

    def skills(self) -> Any:
        """Return the .og skill inventory list (GET /skills)."""
        if self._get_skills is None:
            return []
        return self._get_skills()

    def memory(self) -> Any:
        """Return grouped memory facts, blocked items, and proposed changes (GET /memory)."""
        handler = self._require_handler(self._get_memory, "memory facts")
        return handler()

    def memory_recall(self, query: str, top_k: int = 8) -> Any:
        """Return semantic memory recall results (GET /memory/recall)."""
        handler = self._require_handler(self._get_memory_recall, "memory recall")
        return handler(query, max(1, min(top_k, 50)))

    def og_graph(self) -> Any:
        """Return the ObjectGraph node graph (GET /og/graph)."""
        if self._get_og_graph is None:
            return {"nodes": []}
        return self._get_og_graph()

    def authoring_targets(self) -> Any:
        """Return the list of editable authoring targets (GET /authoring/targets)."""
        handler = self._require_handler(self._get_authoring_targets, "authoring targets")
        return handler()

    def authoring_target(self, name: str) -> Any:
        """Return the source of a single authoring target (GET /authoring/targets/{name})."""
        handler = self._require_handler(self._get_authoring_target, "authoring target")
        return handler(name)

    def authoring_generate(self, name: str, prompt: str) -> Any:
        """Generate a proposed patch for a target (POST /authoring/targets/{name}/generate)."""
        handler = self._require_handler(self._authoring_generate, "authoring generate")
        return handler(name, prompt)

    def authoring_apply(self, name: str) -> Any:
        """Apply a pending patch to an authoring target (POST /authoring/targets/{name}/apply)."""
        handler = self._require_handler(self._authoring_apply, "authoring apply")
        return handler(name)

    def authoring_revert(self, name: str) -> Any:
        """Revert (no-op stub) an authoring target (POST /authoring/targets/{name}/revert)."""
        handler = self._require_handler(self._authoring_revert, "authoring revert")
        return handler(name)

    def authoring_save_source(self, name: str, content: str) -> Any:
        """Persist manually edited content to a target file (POST /authoring/targets/{name}/source).

        CONTRACT-AUTHORING-SAVE: validates the target name, validates parse for .og files,
        and writes atomically.  Returns ``{"ok": True, "name": name}`` on success.
        """
        handler = self._require_handler(self._authoring_save_source, "authoring save source")
        return handler(name, content)

    def spend(self, session_id: str | None = None) -> Any:
        """Return spend analytics for the current or specified session (GET /spend).

        When no active session is available (turns/models are empty), falls back to
        the durable daily-spend ledger so the Spend tab shows real historical totals
        even when the gateway is idle.  The ``{turns, tidies, models}`` shape is
        always preserved; missing breakdowns from the durable source are left empty.
        """
        if self._get_spend is None:
            live: dict[str, Any] = {"turns": [], "tidies": [], "models": []}
        else:
            live = self._get_spend(session_id)

        # If the live session provided turn/model data, return it as-is.
        if live.get("turns") or live.get("models"):
            return live

        # No active session: enrich with durable daily spend so the UI isn't blank.
        try:
            daily = self.spend_daily()
            spent_usd: float = float(daily.get("spent_usd") or 0.0)
            if spent_usd > 0.0:
                # Surface the daily total as a single synthetic model row so the
                # Spend UI can at least show "today's spend" without fabricating
                # per-turn or per-model breakdown we don't have.
                live = dict(live)
                live.setdefault("turns", [])
                live.setdefault("tidies", [])
                # Only add a synthetic model row when none are present.
                if not live.get("models"):
                    live["models"] = [
                        {
                            "name": "durable-ledger",
                            "model": "durable-ledger",
                            "tokens": 0,
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "cost": round(spent_usd, 6),
                            "cost_usd": round(spent_usd, 6),
                            "color": "",
                        }
                    ]
                live["cumulative_usd"] = round(spent_usd, 6)
        except Exception:
            pass  # Best-effort fallback; never block the main response.

        return live

    def spend_daily(self) -> Any:
        """Return today's accumulated daily spend plus configured caps (GET /spend/daily).

        Always returns a safe dict even when no handler is wired, so callers can
        rely on the ``spent_usd`` / ``daily_cap_usd`` / ``task_cap_usd`` keys being
        present without a None-guard.
        """
        if self._get_spend_daily is None:
            return {
                "spent_usd": 0.0,
                "daily_cap_usd": None,
                "task_cap_usd": None,
                "date": datetime.now(UTC).date().isoformat(),
            }
        return self._get_spend_daily()

    def set_capability_enabled(self, cap_id: str, enabled: bool) -> Any:
        """Toggle a capability on/off (PUT /capabilities/{id}/enabled)."""
        handler = self._require_handler(self._set_capability_enabled, "capability toggle")
        return handler(cap_id, bool(enabled))

    def add_memory_fact(self, group: str, text: str) -> Any:
        """Add a fact to a vault collection (POST /memory/facts)."""
        if self._add_memory_fact is None:
            return {"id": "", "error": "memory vault not available"}
        return self._add_memory_fact(group, text)

    def delete_memory_fact(self, fact_id: str) -> Any:
        """Delete a fact from the vault (DELETE /memory/facts/{fact_id})."""
        if self._delete_memory_fact is None:
            return {"ok": False, "error": "memory vault not available"}
        return self._delete_memory_fact(fact_id)

    # ==========================================
    # G1 — new gateway handlers
    # ==========================================

    def update_limits(self, payload: dict[str, Any]) -> Any:
        """Persist spend caps (PUT /config/limits)."""
        handler = self._require_handler(self._update_limits, "limits update")
        return handler(payload)

    def add_allowed_folder(self, folder_path: str) -> Any:
        """Append a folder to the allowed_paths list (POST /config/permissions/folders)."""
        handler = self._require_handler(self._add_allowed_folder, "add allowed folder")
        return handler(folder_path)

    def add_allowed_command(self, command: str) -> Any:
        """Append a command to the allowed_commands list (POST /config/permissions/commands)."""
        handler = self._require_handler(self._add_allowed_command, "add allowed command")
        return handler(command)

    def remove_allowed_folder(self, folder_path: str) -> Any:
        """Remove a folder from the allowed_paths list (DELETE /config/permissions/folders)."""
        handler = self._require_handler(self._remove_allowed_folder, "remove allowed folder")
        return handler(folder_path)

    def remove_allowed_command(self, command: str) -> Any:
        """Remove a command from the allowed_commands list (DELETE /config/permissions/commands)."""
        handler = self._require_handler(self._remove_allowed_command, "remove allowed command")
        return handler(command)

    def add_always_allow(self, session_id: str, request: str, action: str) -> Any:
        """Persist a standing always-allow rule (POST /sessions/{id}/permissions/always-allow)."""
        handler = self._require_handler(self._add_always_allow, "always-allow")
        return handler(session_id, request, action)

    def register_mcp_server(
        self,
        name: str,
        transport: str = "stdio",
        command: str = "",
        args: str = "",
        env_vars: dict[str, str] | None = None,
        url: str = "",
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Register a new MCP server (POST /runtime/mcp/register)."""
        handler = self._require_handler(self._register_mcp_server, "MCP server registration")
        return handler(
            name=name,
            transport=transport,
            command=command,
            args=args,
            env_vars=env_vars or {},
            url=url,
            headers=headers or {},
        )

    def set_mcp_enabled(self, name: str, enabled: bool) -> Any:
        """Enable or disable a named MCP server by persisting ``enabled`` to settings.toml.

        Mirrors the ``[mcp_servers.NAME]`` persistence path used by
        :meth:`register_mcp_server`.  Returns ``{"ok": True}`` on success;
        raises ``HTTPException(404)`` when the name is unknown.

        Args:
            name:    Server name as it appears in ``GET /runtime/mcp/inventory``.
            enabled: ``True`` to enable, ``False`` to disable.
        """
        # Prefer the runtime handler: it persists the flag AND applies the change
        # to the live agent's tool registry (and can create the entry for
        # .og-declared servers), so a disable/enable takes effect without a restart.
        if self._set_mcp_enabled is not None:
            return self._set_mcp_enabled(name, enabled)

        import tomlkit as _tomlkit
        from fastapi import HTTPException as _HTTPException

        from hachi.core.paths import get_hachi_paths as _get_paths

        paths = _get_paths()
        config_toml = paths.global_config_toml

        if config_toml.exists():
            doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        else:
            doc = _tomlkit.document()

        mcp_section = doc.get("mcp_servers", {})
        if name not in mcp_section:
            raise _HTTPException(status_code=404, detail=f"MCP server {name!r} not found")

        mcp_section[name]["enabled"] = enabled

        import os as _os

        tmp = config_toml.with_name(f"{config_toml.name}.tmp")
        tmp.write_text(_tomlkit.dumps(doc), encoding="utf-8")
        _os.replace(tmp, config_toml)

        return {"ok": True, "name": name, "enabled": enabled}

    def delete_mcp_server(self, name: str) -> Any:
        """Remove a registered MCP server from settings.toml.

        Deletes the ``[mcp_servers.NAME]`` table entry and atomically rewrites
        settings.toml.  Returns ``{"ok": True}`` on success; raises
        ``HTTPException(404)`` when the name is unknown.

        Args:
            name: Server name exactly as it appears in ``GET /runtime/mcp/inventory``.
        """
        # Prefer the runtime handler: it tears down the live connection + tools
        # (so the server leaves the inventory immediately), removes every persisted
        # source (settings.toml entry, mcp-<name>.og file, or a tombstone for
        # bundled servers), and is idempotent (repeat delete → 200, not 404).
        if self._delete_mcp_server is not None:
            return self._delete_mcp_server(name)

        import tomlkit as _tomlkit
        from fastapi import HTTPException as _HTTPException

        from hachi.core.paths import get_hachi_paths as _get_paths

        paths = _get_paths()
        config_toml = paths.global_config_toml

        if config_toml.exists():
            doc = _tomlkit.parse(config_toml.read_text(encoding="utf-8"))
        else:
            doc = _tomlkit.document()

        mcp_section = doc.get("mcp_servers", {})
        if name not in mcp_section:
            raise _HTTPException(status_code=404, detail=f"MCP server {name!r} not found")

        del mcp_section[name]

        import os as _os

        tmp = config_toml.with_name(f"{config_toml.name}.tmp")
        tmp.write_text(_tomlkit.dumps(doc), encoding="utf-8")
        _os.replace(tmp, config_toml)

        return {"ok": True, "name": name}

    def session_transcript(self, session_id: str, limit: int = 200) -> dict[str, Any] | None:
        """Return the durable message transcript for *session_id*, or ``None`` if unknown.

        Fetches directly from the SQLite ``messages`` table via the
        ``_get_session_messages`` callback (wired from
        :meth:`~hachi.cli.main._InProcessGatewayRuntime.session_messages`).

        The caller (HTTP layer) converts ``None`` to HTTP 404.

        Args:
            session_id: Session id to fetch (may be historical / no longer active).
            limit:      Maximum number of messages to return (oldest-first chronological).

        Returns:
            ``{"session_id": ..., "messages": [...]}`` on success, or ``None``
            when the session is unknown / store not wired.
        """
        if self._get_session_messages is None:
            return None
        try:
            messages = self._get_session_messages(session_id, limit)
        except Exception:
            return None
        if not messages:
            return None
        # Messages from SessionStore have: role, content, tool_name, timestamp.
        # Include the row id if present (it's an int autoincrement PK).
        return {
            "session_id": session_id,
            "messages": list(messages),
        }

    def kennel(self) -> Any:
        """Return the available skills kennel listing (GET /skills/kennel)."""
        if self._get_kennel is None:
            return []
        return self._get_kennel()

    def add_skill(self, kennel_id: str) -> Any:
        """Install a skill from the kennel (POST /skills/add)."""
        handler = self._require_handler(self._add_skill, "skill install")
        return handler(kennel_id)

    # ==========================================
    # Multi-provider admin public methods
    # ==========================================

    def list_providers(self) -> Any:
        """Return all configured providers (secrets masked) — GET /config/providers."""
        if self._list_providers is None:
            return {"providers": []}
        return self._list_providers()

    def add_or_update_provider(self, name: str, spec: dict[str, Any]) -> Any:
        """Upsert a named provider — POST /config/providers or PUT /config/providers/{name}."""
        handler = self._require_handler(self._add_or_update_provider, "provider upsert")
        return handler(name, spec)

    def remove_provider(self, name: str) -> Any:
        """Delete a named provider — DELETE /config/providers/{name}."""
        handler = self._require_handler(self._remove_provider, "provider removal")
        return handler(name)

    def get_routing(self) -> Any:
        """Return the capability routing matrix — GET /config/routing."""
        if self._get_routing is None:
            return {"default_model": "claude-haiku-4-5", "capabilities": []}
        return self._get_routing()

    def set_routing(self, default_model: str, capabilities: dict[str, list[str]]) -> Any:
        """Persist the routing matrix — PUT /config/routing (hot-reload)."""
        handler = self._require_handler(self._set_routing, "routing update")
        return handler(default_model, capabilities)

    def validate_routing(
        self, default_model: str, capabilities: dict[str, list[str]]
    ) -> dict[str, Any]:
        """Validate a routing config without persisting — POST /config/routing/validate.

        Always returns HTTP 200; the caller checks ``ok``.

        Returns:
            ``{"ok": bool, "issues": list[str], "warnings": list[str]}``.
        """
        if self._validate_routing_handler is not None:
            return self._validate_routing_handler(default_model, capabilities)
        try:
            from hachi.core.routing.policy import RoutingPolicy
            from hachi.core.routing.registry import ModelRegistry
            from hachi.core.routing.validate import validate_routing as _validate

            policy = RoutingPolicy(
                default_model=default_model,
                capabilities={k: v for k, v in (capabilities or {}).items()},
            )
            reg = ModelRegistry.build({}, None)
            result = _validate(reg, policy, providers=None)
            return {
                "ok": result.ok,
                "issues": result.issues,
                "warnings": result.warnings,
            }
        except Exception as exc:
            return {"ok": False, "issues": [str(exc)], "warnings": []}

    def rollback_routing(self) -> dict[str, Any]:
        """Restore the last-known-good routing config — POST /config/routing/rollback.

        Returns:
            ``{"ok": bool, "detail": str, "routing": dict | None}``.
        """
        if self._rollback_routing_handler is not None:
            return self._rollback_routing_handler()
        try:
            from hachi.gateway.shared_services import ProcessSharedServices

            shared = ProcessSharedServices.instance()
            store = getattr(shared, "routing_store", None) if shared is not None else None
            if store is None:
                return {"ok": False, "detail": "routing store not available", "routing": None}
            restored = store.rollback()
            if restored is None:
                return {"ok": False, "detail": "no prior snapshot to restore", "routing": None}
            return {
                "ok": True,
                "detail": f"restored v{store.version} (default={restored.policy.default_model})",
                "routing": self.get_routing(),
            }
        except Exception as exc:
            return {"ok": False, "detail": str(exc), "routing": None}

    def get_routing_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent routing-change audit records — GET /config/routing/audit.

        Returns:
            List of audit records (newest first). Empty when no changes recorded.
        """
        if self._get_routing_audit_handler is not None:
            return self._get_routing_audit_handler(limit)
        try:
            from hachi.gateway.shared_services import ProcessSharedServices

            shared = ProcessSharedServices.instance()
            store = getattr(shared, "routing_store", None) if shared is not None else None
            if store is None:
                return []
            return store.audit_records(limit=limit)
        except Exception:
            return []

    def test_provider_connection(self, name: str) -> Any:
        """Test connectivity for a named provider — POST /config/providers/{name}/test-connection.

        Returns ``{"ok": bool, "detail": str}``.
        """
        if self._test_provider_connection is None:
            return {"ok": False, "detail": "test_connection not available"}
        return self._test_provider_connection(name)

    def list_all_models(self) -> Any:
        """Return models indexed by provider — GET /config/models/all."""
        if self._list_all_models is None:
            return {}
        return self._list_all_models()

    def probe_provider(self, spec: dict[str, Any]) -> Any:
        """Probe an unsaved provider spec — POST /config/providers/probe.

        Returns ``{"ok": bool, "detail": str, "models": list[str]}``.
        """
        if self._probe_provider is None:
            return {"ok": False, "detail": "probe not available", "models": []}
        return self._probe_provider(spec)

    def interrupt(self, session_id: str) -> dict[str, Any]:
        """Signal a live session's execution loop to stop at its next iteration boundary.

        P1-4: wires the HTTP-level Stop action to ``ExecutionLoop.cancel()`` so that a
        browser disconnect or explicit Stop button actually stops the worker thread, not
        just the awaiting coroutine.

        Returns ``{"interrupted": True}`` when the signal was delivered to a live session,
        ``{"interrupted": False}`` when the session is not live (safe, no exception).

        Args:
            session_id: The session to interrupt.

        Returns:
            Dict with a single boolean key ``interrupted``.
        """
        normalized = session_id.strip()
        with self._connections_lock:
            is_live = normalized in self._connections
        if not is_live:
            return {"interrupted": False}
        if self._on_interrupt is None:
            # Runtime not attached (standalone gateway without --runtime): the
            # session connection record exists but there is no live loop to cancel.
            return {"interrupted": False}
        try:
            result = self._on_interrupt(normalized)
            return result if isinstance(result, dict) else {"interrupted": False}
        except Exception:
            return {"interrupted": False}

    # ------------------------------------------------------------------ #
    # Credential manager (BB-9 / cred: namespace)
    # ------------------------------------------------------------------ #

    def store_secret(self, name: str, value: str) -> dict[str, Any]:
        """Store a user-managed credential under ``cred:<name>``."""
        handler = self._require_handler(self._store_secret, "store secret")
        return handler(name, value)

    def list_secret_names(self) -> dict[str, Any]:
        """List user-managed credential names (``cred:`` prefix stripped from each)."""
        handler = self._require_handler(self._list_secret_names, "list secret names")
        return handler()

    def delete_secret(self, name: str) -> dict[str, Any]:
        """Delete the ``cred:<name>`` credential (idempotent)."""
        handler = self._require_handler(self._delete_secret, "delete secret")
        return handler(name)

    def reload_search_tools(self) -> dict[str, Any]:
        """Re-evaluate search-provider availability after a credential change."""
        if self._reload_search_tools is None:
            return {"ok": True, "live": False, "note": "no runtime attached"}
        try:
            return self._reload_search_tools()
        except Exception as exc:
            return {"ok": False, "live": False, "note": str(exc)}

    # Backward-compatible aliases for previous envelope methods.
    def connect(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = payload.get("payload") if isinstance(payload, dict) else None
        if not isinstance(body, dict):
            raise GatewayProtocolError("payload must be an object")
        request = self.create_session(
            client_id=str(body.get("client_id") or ""),
            surface=str(body.get("surface") or ""),
            capabilities=body.get("capabilities")
            if isinstance(body.get("capabilities"), list)
            else [],
            protocol_version=str(body.get("protocol_version") or ""),
        )
        return {
            "type": "connect_ack",
            "request_id": str(payload.get("request_id") or ""),
            "payload": request,
        }

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = payload.get("payload") if isinstance(payload, dict) else None
        if not isinstance(body, dict):
            raise GatewayProtocolError("payload must be an object")
        response = self.send_message(
            session_id=str(body.get("session_id") or ""),
            prompt=str(body.get("prompt") or ""),
        )
        return {
            "type": "chat.response",
            "request_id": str(payload.get("request_id") or ""),
            "payload": response,
        }

    def events(self, session_id: str, after: int = 0, limit: int = 100) -> dict[str, Any]:
        payload = self.read_session_events(session_id=session_id, after=after, limit=limit)
        return {
            "type": "events.batch",
            "payload": payload,
        }


class GatewayHTTPServer:
    """Uvicorn wrapper exposing FastAPI gateway endpoints with start/stop semantics."""

    def __init__(
        self,
        control_plane: GatewayControlPlane,
        host: str = "127.0.0.1",
        port: int = 0,
        auth_token: str | None = None,
        frontend_dist: Path | None = None,
    ) -> None:
        self._control_plane = control_plane
        self._host = host
        self._port = port
        self._auth_token = auth_token
        self._frontend_dist = frontend_dist
        self._bound_port: int = 0
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._startup_error: Exception | None = None

    @property
    def bound_port(self) -> int:
        return self._bound_port

    def _detect_bound_port(self) -> int:
        server = self._server
        if server is None:
            return 0

        uvicorn_servers = getattr(server, "servers", []) or []
        for uvicorn_server in uvicorn_servers:
            sockets = getattr(uvicorn_server, "sockets", []) or []
            for socket in sockets:
                sockname = socket.getsockname()
                if isinstance(sockname, tuple) and len(sockname) >= 2:
                    return int(sockname[1])
        return 0

    def _serve(self) -> None:
        from hachi.gateway.fastapi_app import create_gateway_app

        try:
            app = create_gateway_app(
                self._control_plane,
                auth_token=self._auth_token,
                bind_host=self._host,
                frontend_dist=self._frontend_dist,
            )
            config = uvicorn.Config(
                app,
                host=self._host,
                port=self._port,
                log_level="warning",
                lifespan="on",
            )
            server = uvicorn.Server(config)
            self._server = server
            server.run()
        except Exception as exc:  # pragma: no cover
            self._startup_error = exc

    def start(self) -> int:
        if self._thread and self._thread.is_alive():
            return self.bound_port

        self._startup_error = None
        self._bound_port = 0
        self._thread = threading.Thread(
            target=self._serve,
            name="gateway-http",
            daemon=True,
        )
        self._thread.start()

        deadline = time.time() + 5.0
        while time.time() < deadline:
            if self._startup_error is not None:
                raise OSError(
                    f"Gateway server failed to start: {self._startup_error}"
                ) from self._startup_error
            if self._server is not None and self._server.started:
                self._bound_port = self._detect_bound_port() or self._port
                if self._bound_port:
                    return self._bound_port
            if self._thread and not self._thread.is_alive():
                break
            time.sleep(0.01)

        if self._startup_error is not None:
            raise OSError(
                f"Gateway server failed to start: {self._startup_error}"
            ) from self._startup_error
        raise OSError("Gateway server failed to start within timeout")

    def stop(self) -> None:
        server = self._server
        if server is None:
            return

        server.should_exit = True
        server.force_exit = True

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._server = None
        self._bound_port = 0
