from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import anyio
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

# UC-PERM-006: approvals inbox REST surface. core/approvals.py is a foundation
# module that is always present, so these imports are direct.
from hachi.core.approvals import get_approval_registry
from hachi.core.permissions import PermissionDecision
from hachi.core.rate_limit import RateLimiter
from hachi.core.untrusted_content import guard_untrusted
from hachi.gateway.control_plane import (
    PROTOCOL_VERSION,
    GatewayControlPlane,
    GatewayProtocolError,
    GatewayUnavailableError,
    SessionExpiredError,
)

_APPROVALS_AVAILABLE = True


_log = logging.getLogger(__name__)


def _is_loopback_host(host: str) -> bool:
    """Return *True* when ``host`` is a loopback address (127.0.0.1 / ::1 / localhost)."""
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _parse_allowlist(raw: str | None) -> set[str]:
    return {item.strip() for item in raw.split(",")} - {""} if raw else set()


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    protocol_version: str
    time: str


class ReadinessResponse(BaseModel):
    status: str
    ready: bool
    blockers: list[str]
    checks: dict[str, str] = Field(default_factory=dict)
    active_connections: int
    time: str


class SessionCreateRequest(BaseModel):
    client_id: str
    surface: str
    protocol_version: str = PROTOCOL_VERSION
    capabilities: list[str] = Field(default_factory=list)


class SessionCreateResponse(BaseModel):
    accepted: bool
    session_id: str
    protocol_version: str
    server_capabilities: list[str]


class SessionMessageRequest(BaseModel):
    prompt: str
    attachment_ids: list[str] = []
    # Optional ingress idempotency token (AUDIT P0-3). When supplied — preferably via the
    # ``Idempotency-Key`` HTTP header, with this body field as a fallback — a duplicate
    # POST with the same key replays the prior turn's response instead of re-running the
    # turn (no double spend / duplicate side effects). The header takes precedence.
    idempotency_key: str | None = None


class SessionMessageResponse(BaseModel):
    response: str
    # Optional: the normal chat path returns the resolved session_id, but
    # synthetic slash-command replies (e.g. /model, /help) omit it — the client
    # already knows which session it posted to, so echoing it back (and risking a
    # literal "None") is noise. Excluded from the payload when None via the
    # route's response_model_exclude_none.
    session_id: str | None = None


class GatewayEventPayload(BaseModel):
    sequence: int
    event_type: str
    payload: dict[str, Any]
    time: str


class SessionEventsResponse(BaseModel):
    session_id: str
    events: list[GatewayEventPayload]
    next_sequence: int


class SessionCloseResponse(BaseModel):
    session_id: str
    closed: bool


class SessionInterruptResponse(BaseModel):
    """Response for POST /sessions/{session_id}/interrupt (P1-4)."""

    interrupted: bool


class RuntimeEventsResponseItem(BaseModel):
    model_config = ConfigDict(extra="allow")


class ConfigPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class ProviderRequest(BaseModel):
    provider: dict[str, Any]


class ProviderUpsertRequest(BaseModel):
    """Body for POST /config/providers (add) and PUT /config/providers/{name} (update)."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None  # present for POST; absent for PUT (name in path)
    kind: str = "anthropic"
    model: str = ""
    base_url: str | None = None
    allowed_models: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    api_key: str | None = None


class RoutingUpdateRequest(BaseModel):
    """Body for PUT /config/routing."""

    model_config = ConfigDict(extra="ignore")

    default_model: str
    capabilities: dict[str, list[str]] = Field(default_factory=dict)


class VoiceSpeakBody(BaseModel):
    """Body for POST /voice/speak."""

    model_config = ConfigDict(extra="ignore")

    text: str = Field(max_length=8000)
    voice: str | None = None
    model: str | None = None
    format: str = "mp3"
    provider: Literal["openai", "elevenlabs"] | None = None


class PermissionsRequest(BaseModel):
    permissions: dict[str, Any]


class MemoryRequest(BaseModel):
    memory: dict[str, Any]


class MemoryFactAddRequest(BaseModel):
    """Body for POST /memory/facts."""

    group: str  # "core_memory" | "user_profile" | "agent_profile"
    text: str


class MemoryFactDeleteResponse(BaseModel):
    """Response for DELETE /memory/facts/{fact_id}."""

    ok: bool


class OpenAIMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: str
    content: Any = None  # string or list of content blocks


class OpenAIChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    messages: list[OpenAIMessage]
    model: str | None = None
    stream: bool = False


class ChannelInboundRequest(BaseModel):
    sender_id: str
    text: str
    sender_name: str = ""


class ScheduleToggleRequest(BaseModel):
    enabled: bool


class CapabilityToggleRequest(BaseModel):
    """Body for PUT /capabilities/{id}/enabled."""

    enabled: bool


# G1 — new request models


class LimitsRequest(BaseModel):
    """Body for PUT /config/limits (G1-T3)."""

    per_task_cap_usd: float | None = None
    daily_cap_usd: float | None = None


class AllowedFolderRequest(BaseModel):
    """Body for POST /config/permissions/folders (G1-T3)."""

    path: str


class AllowedCommandRequest(BaseModel):
    """Body for POST /config/permissions/commands (G1-T3)."""

    command: str


class AlwaysAllowRequest(BaseModel):
    """Body for POST /sessions/{id}/permissions/always-allow (G1-T4)."""

    request: str
    action: str


class SecretStoreRequest(BaseModel):
    """Body for POST /runtime/secrets."""

    name: str = Field(..., pattern=r"^[\w.\-]+$")
    value: str = Field(..., min_length=1)


class McpRegisterRequest(BaseModel):
    """Body for POST /runtime/mcp/register (G1-T5 / CONTRACT-MCP).

    Supports three transport kinds:
      - ``stdio`` (default): requires ``command`` + optional ``args`` / ``env_vars``.
      - ``sse``:             requires ``url`` + optional ``headers`` / ``env_vars``.
      - ``http``:            requires ``url`` + optional ``headers`` / ``env_vars``.
    """

    name: str
    transport: str = "stdio"
    # stdio fields
    command: str = ""
    args: str = ""
    env_vars: dict[str, str] = Field(default_factory=dict)
    # sse / http fields
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


class SkillAddRequest(BaseModel):
    """Body for POST /skills/add (G1-T6)."""

    kennel_id: str


class AuthoringGenerateRequest(BaseModel):
    """Body for POST /authoring/targets/{name}/generate (G1-T2 / CRIT-002)."""

    prompt: str


class AuthoringSourceSaveRequest(BaseModel):
    """Body for POST /authoring/targets/{name}/source (CONTRACT-AUTHORING-SAVE)."""

    content: str


def _last_user_text(messages: list[OpenAIMessage]) -> str:
    """Extract the latest user message text from an OpenAI-style message list."""
    for message in reversed(messages):
        if message.role != "user":
            continue
        content = message.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            return " ".join(parts).strip()
    return ""


class SetupApplyRequest(BaseModel):
    plan: dict[str, Any]


class ApprovalActionRequest(BaseModel):
    """Body for POST /approvals/{request_id} (UC-PERM-006)."""

    action: str  # "approve" | "deny" | "allow_once"
    rationale: str = ""


# ---------------------------------------------------------------------------
# Eval loop — interaction read/rating models (E1)
# ---------------------------------------------------------------------------


class InteractionRecord(BaseModel):
    """One row from ``interaction_log`` — the per-turn eval ground truth.

    ``tool_calls`` and ``memory_hits`` are decoded JSON arrays (lists of strings).
    Numeric fields are optional because they may be NULL for older rows.
    """

    id: str
    session_id: str
    turn_id: str | None = None
    ts: str
    user_input: str | None = None
    agent_output: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
    memory_hits: list[str] = Field(default_factory=list)
    model_used: str | None = None
    token_cost: float | None = None
    tokens: int | None = None
    rating: str | None = None
    notes: str | None = None


class InteractionListResponse(BaseModel):
    """Response for ``GET /interactions``."""

    interactions: list[InteractionRecord]


class RatingRequest(BaseModel):
    """Body for ``PUT /interactions/{interaction_id}/rating``."""

    rating: Literal["up", "down"]
    notes: str | None = None


class RatingResponse(BaseModel):
    """Response for ``PUT /interactions/{interaction_id}/rating``."""

    ok: bool


_GATEWAY_THREAD_LIMITER_ENV = "HACHI_GATEWAY_THREAD_LIMITER"
_DEFAULT_THREAD_LIMITER = 64


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # B6: raise the AnyIO default threadpool limit (40) to accommodate concurrent
    # blocking REST reads (session list, message history, event history) plus
    # in-flight per-turn send_message threads without queuing. Configurable via
    # HACHI_GATEWAY_THREAD_LIMITER; intentionally separate from the session-object
    # cap (HACHI_GATEWAY_MAX_SESSIONS) which governs agent lifetime, not I/O threads.
    _thread_cap = int(os.environ.get(_GATEWAY_THREAD_LIMITER_ENV, str(_DEFAULT_THREAD_LIMITER)))
    anyio.to_thread.current_default_thread_limiter().total_tokens = _thread_cap
    yield


def _error_response(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message, details=details).model_dump(mode="json"),
    )


def _resolve_session_store() -> Any:
    """Return the process-wide ``SessionStore`` (preferred) or a fresh fallback, else None.

    Mirrors the ``ProcessSharedServices`` access pattern used elsewhere in this module so
    durable ingress idempotency (AUDIT P0-3) reads/writes the same database the rest of the
    gateway uses. Patched in tests to point at an isolated DB.
    """
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        store = getattr(shared, "session_store", None) if shared is not None else None
        if store is not None:
            return store
        from hachi.core.session_store import SessionStore

        return SessionStore()
    except Exception:  # pragma: no cover - store is best-effort; never break the turn
        return None


class _SPAStaticFiles(StaticFiles):
    """StaticFiles with a history fallback for client-side routing.

    Starlette's ``html=True`` resolves directory-like paths to ``index.html``, but
    it does **not** fall back for arbitrary deep paths. A single-page app serves
    one entry document and routes on the client, so ``/conversation`` (a route,
    not a file) must return ``index.html`` or every refresh and every direct link
    is a 404.

    API prefixes are excluded so a genuinely missing endpoint still reports 404
    rather than a confusing HTML body.
    """

    _NON_SPA_PREFIXES = ("api/", "v1/", "sessions/", "config/", "setup/", "memory/", "jobs/")

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.startswith(self._NON_SPA_PREFIXES):
                raise
            return await super().get_response("index.html", scope)


def create_gateway_app(
    control_plane: GatewayControlPlane,
    auth_token: str | None = None,
    *,
    bind_host: str | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
    """Create the Hachi gateway FastAPI application.

    Args:
        control_plane: The :class:`GatewayControlPlane` that backs all routes.
        auth_token: Bearer token required on all protected routes.  When *None*
            the token is still enforced unless the opt-out env var
            ``HACHI_GATEWAY_NO_AUTH=1`` is set (power-user escape hatch).
        bind_host: The host address the server will bind to.  When supplied the
            function enforces the loopback-only constraint for NO_AUTH mode and
            the hard-error for non-loopback binds without a token.  When *None*
            (default, used by unit-test helpers and the OpenAPI export command)
            these startup guards are skipped.
        frontend_dist: Path to the pre-built frontend ``dist`` directory.  When
            provided, the directory is mounted as a static files handler at the
            root ``/`` route after all API routes (CRIT-008 / ``hachi serve``).
            When *None* (default) no static files are mounted.

    Auth posture (UC-AUTH-001/ADV-014):
        All protected routes require ``Authorization: Bearer <token>``.
        Loopback binding does NOT exempt authentication — a localhost-only
        daemon is still reachable by any process on the same machine.
        The opt-out env flag ``HACHI_GATEWAY_NO_AUTH=1`` disables the
        check **only when the bind address is a loopback** (E8/T8.2).  Using
        NO_AUTH on a non-loopback host is a startup error.

    CORS posture (UC-AUTH-003):
        Allow-list is limited to local dev origins (localhost:5173/4173) or
        the caller-provided ``HACHI_CORS_ORIGINS`` env var.
        ``allow_origins=["*"]`` is intentionally NOT used together with
        credentials / auth headers — that combination is a security anti-pattern.
    """
    # Determine effective auth posture.
    _no_auth_override = os.environ.get("HACHI_GATEWAY_NO_AUTH", "").strip() == "1"

    # E8/T8.2 — Guard 1: NO_AUTH is only allowed on loopback.
    if _no_auth_override and bind_host is not None and not _is_loopback_host(bind_host):
        raise ValueError(
            f"HACHI_GATEWAY_NO_AUTH=1 is not permitted when binding to a non-loopback "
            f"host ('{bind_host}'). Remove the env var or bind to 127.0.0.1/::1/localhost."
        )

    # E8/T8.2 — Guard 2: non-loopback bind without a token is a hard startup error.
    if bind_host is not None and not _is_loopback_host(bind_host) and not auth_token:
        raise ValueError(
            f"Gateway cannot start on non-loopback host '{bind_host}' without an auth token. "
            "Set HACHI_GATEWAY_API_TOKEN (or HACHI_GATEWAY_API_TOKEN_FILE) before starting."
        )

    # CRIT-001 — Guard 3: fail-closed when a bind_host is known but no token was
    # configured AND no-auth override is absent.  Unit tests that call
    # create_gateway_app(cp) without a bind_host keep working (bind_host=None skips
    # this check); the gateway-openapi export path passes bind_host=None explicitly.
    if (
        bind_host is not None
        and _is_loopback_host(bind_host)
        and not auth_token
        and not _no_auth_override
    ):
        raise ValueError(
            "Gateway cannot start on loopback without an auth token and no "
            "HACHI_GATEWAY_NO_AUTH=1 override. "
            "The CLI always generates a token; this error indicates a misconfiguration."
        )

    _auth_enabled = not _no_auth_override
    if _no_auth_override:
        _log.warning(
            "HACHI_GATEWAY_NO_AUTH=1 is set — "
            "the gateway control plane is running WITHOUT authentication. "
            "Do NOT expose this gateway on a network-accessible interface."
        )

    app = FastAPI(title="Hachi Gateway", version="1.0.0", lifespan=_lifespan)

    _raw_origins = os.environ.get("HACHI_CORS_ORIGINS", "")
    _cors_origins: list[str] = (
        [o.strip() for o in _raw_origins.split(",") if o.strip()]
        if _raw_origins.strip()
        else ["http://localhost:5173", "http://localhost:4173"]
    )
    # Security: allow_credentials=False — our stateless Bearer auth is header-based
    # and does not rely on cookies.  Using allow_origins=["*"] with credentials
    # would be a CORS misconfiguration; we keep the origin allow-list explicit.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )
    # Phase 4: request-tracing middleware (pure ASGI, after CORS, before auth).
    # No-op when tracing is inactive; adds `traceparent` response header only —
    # zero OpenAPI schema change (verified: run `hachi gateway-openapi`).
    from hachi.gateway.middleware.trace import TraceMiddleware

    app.add_middleware(TraceMiddleware)

    class _AuthRequired(Exception):
        pass

    @app.exception_handler(_AuthRequired)
    async def _auth_required_handler(_request: Request, _exc: _AuthRequired) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Missing or invalid bearer token",
        )

    def _require_auth(request: Request) -> str | None:
        """Enforce bearer-token authentication on protected routes.

        Auth is enforced when BOTH:
        - ``auth_token`` is non-empty (i.e. a token was configured/generated), AND
        - ``HACHI_GATEWAY_NO_AUTH=1`` is NOT set.

        Loopback binding does NOT exempt this check (MR-2 / UC-AUTH-001 / ADV-014).
        The security fix is at the CLI layer: ``_start_gateway_server`` now always
        generates/persists a token for loopback hosts, so ``auth_token`` is always
        truthy in normal operation.

        The startup guards in ``create_gateway_app`` (E8/T8.2) ensure that:
        - ``NO_AUTH=1`` on a non-loopback host is a hard error before serving starts.
        - A non-loopback host without a token is a hard error before serving starts.
        - A loopback host with bind_host set and no token (and no NO_AUTH) is also a
          hard error (CRIT-001).

        Tests that call ``create_gateway_app(cp)`` without a token AND without a
        bind_host continue to work — bind_host=None skips the startup guard, and
        here ``auth_token=None`` means no enforcement (e.g. pure unit tests).

        Returns:
            sha256 hex-digest of the caller's raw bearer token when auth is enforced
            and the credential is valid.  Returns ``None`` in no-auth mode or when
            running as a test helper without a configured token.  The digest is used
            for session-ownership checks (C1) without exposing the raw token in memory.
        """
        if not _auth_enabled:
            return None
        if not auth_token:
            # No token configured AND bind_host was None (unit-test / export path) →
            # no enforcement.  When bind_host was provided, the startup guard (CRIT-001)
            # already raised ValueError before the server started, so reaching here
            # with bind_host set and no token is structurally impossible in production.
            return None
        expected = f"Bearer {auth_token}"
        received = request.headers.get("Authorization", "")
        if not secrets.compare_digest(received.strip(), expected):
            raise _AuthRequired()
        raw_token = received.strip()[len("Bearer ") :].strip()
        # C1: return the sha256 digest so routes can compare ownership without
        # storing or comparing the raw bearer value.
        return hashlib.sha256(raw_token.encode()).hexdigest()

    # Issue 1: SessionExpiredError must be registered BEFORE GatewayProtocolError
    # (it is a subclass).  HTTP 410 Gone tells the frontend the session existed but
    # is no longer active, and the client should create a new session.
    @app.exception_handler(SessionExpiredError)
    async def _session_expired_handler(_request: Request, exc: SessionExpiredError) -> JSONResponse:
        return _error_response(
            status_code=410,
            code=exc.code,
            message=str(exc),
            details={"session_id": exc.session_id},
        )

    @app.exception_handler(GatewayProtocolError)
    async def _protocol_error_handler(_request: Request, exc: GatewayProtocolError) -> JSONResponse:
        return _error_response(
            status_code=400,
            code=getattr(exc, "code", "protocol_error"),
            message=str(exc),
        )

    @app.exception_handler(GatewayUnavailableError)
    async def _unavailable_error_handler(
        _request: Request, exc: GatewayUnavailableError
    ) -> JSONResponse:
        return _error_response(status_code=503, code="service_unavailable", message=str(exc))

    # Provider (LLM) errors — surface the upstream provider's actionable message
    # (e.g. "credit balance too low", auth failure, rate limit) instead of masking
    # it as an opaque 500 internal_error. Only the provider's user-facing message
    # is exposed — never the stack trace or API key. Registered against
    # anthropic.APIStatusError; its subclasses (BadRequestError / AuthenticationError
    # / RateLimitError / ...) are matched via the exception MRO. Guarded import so
    # the gateway still starts if the SDK is absent (e.g. non-runtime mode).
    _anthropic: Any = None
    try:
        import anthropic

        _anthropic = anthropic
    except Exception:  # pragma: no cover - anthropic is present in runtime mode
        pass

    if _anthropic is not None:

        @app.exception_handler(_anthropic.APIStatusError)
        async def _provider_error_handler(_request: Request, exc: Any) -> JSONResponse:
            status = getattr(exc, "status_code", None) or 400
            message: str | None = None
            body = getattr(exc, "body", None)
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict) and isinstance(err.get("message"), str):
                    message = err["message"]
            if not message:
                message = getattr(exc, "message", None) or "AI provider request failed."
            # Upstream 5xx / overloaded → transient: report as unavailable so clients
            # may retry. Upstream 4xx (billing / auth / validation / rate-limit) →
            # surface the actionable message under a stable provider_error code so the
            # UI can show it (and the user can fix billing / key / model).
            if status in (500, 502, 503, 504, 529):
                return _error_response(
                    status_code=503,
                    code="provider_unavailable",
                    message=f"AI provider temporarily unavailable: {message}",
                )
            client_status = status if status in (400, 401, 403, 404, 409, 422, 429) else 400
            return _error_response(
                status_code=client_status,
                code="provider_error",
                message=message,
            )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _internal_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Catch-all: prevents the LLM raising (e.g. 401 from a bad API key) from
        # returning a raw text/plain 500 that clients cannot parse.
        # Exception details (type, message, traceback) are logged server-side only —
        # never returned to the client to avoid leaking internal paths or secrets.
        import logging as _logging
        import traceback as _traceback

        correlation_id = str(uuid.uuid4())
        _logging.getLogger(__name__).error(
            "Internal error [%s]: %s\n%s",
            correlation_id,
            exc,
            _traceback.format_exc(),
        )
        return _error_response(
            status_code=500,
            code="internal_error",
            message="An unexpected error occurred.",
            details={"correlation_id": correlation_id},
        )

    # All "protected" routes carry the auth dependency.
    # When auth_token is truthy AND HACHI_GATEWAY_NO_AUTH is not set,
    # _require_auth enforces the bearer check.  The auth_token is always
    # populated by the CLI layer (MR-2 / UC-AUTH-001 / ADV-014).
    protected_dependencies = [Depends(_require_auth)]

    system = APIRouter(tags=["system"])
    sessions = APIRouter(prefix="/sessions", tags=["sessions"], dependencies=protected_dependencies)
    runtime_ops = APIRouter(tags=["runtime"], dependencies=protected_dependencies)
    config = APIRouter(prefix="/config", tags=["config"], dependencies=protected_dependencies)
    setup = APIRouter(prefix="/setup", tags=["setup"], dependencies=protected_dependencies)

    def _service_descriptor() -> dict[str, Any]:
        return {
            "service": "Hachi Gateway",
            "version": "1.0.0",
            "health": "/health",
            "readiness": "/readiness",
            "docs": "/docs",
        }

    @system.get("/status")
    async def get_status() -> Any:
        """Stable home for the service descriptor.

        Added because "/" now belongs to the SPA whenever a frontend is mounted —
        the URL `hachi serve` prints is the web UI, and users pointing a browser
        at it must not get raw JSON.
        """
        return _service_descriptor()

    @system.get("/")
    async def get_root() -> Any:
        # P-32: with a frontend mounted, "/" is the web UI. This route is
        # registered before the static mount, so it previously won the match and
        # every user following the printed "Web UI: http://…" URL got JSON.
        if frontend_dist is not None:
            _index = Path(frontend_dist) / "index.html"
            if _index.is_file():
                return FileResponse(str(_index))
        return _service_descriptor()

    @system.get("/health", response_model=HealthResponse)
    async def get_health() -> Any:
        return control_plane.health()

    @system.get("/readiness", response_model=ReadinessResponse)
    async def get_readiness() -> JSONResponse:
        readiness = control_plane.readiness()
        status = 200 if readiness["ready"] else 503
        return JSONResponse(status_code=status, content=readiness)

    @system.get("/capabilities", dependencies=protected_dependencies)
    async def get_capabilities() -> Any:
        return control_plane.capabilities()

    @system.get("/models", dependencies=protected_dependencies)
    async def get_models() -> Any:
        return control_plane.models()

    def _check_session_ownership(session_id: str, caller_hash: str | None) -> None:
        """Enforce C1 session-ownership policy.

        If the session has an owner set, the caller's token-hash must match.
        Legacy sessions (NULL owner) are accessible by any authenticated caller
        for backward compatibility.  In no-auth mode (caller_hash is None) all
        sessions are accessible.

        Args:
            session_id: The session being accessed.
            caller_hash: sha256 hex-digest returned by ``_require_auth``, or None
                in no-auth / test-helper mode.

        Raises:
            HTTPException: 403 if the caller does not own the session.
        """
        if caller_hash is None:
            # No-auth mode or unconfigured token: skip ownership check.
            return
        owner = control_plane.get_session_owner(session_id)
        if owner is not None and not secrets.compare_digest(owner, caller_hash):
            raise HTTPException(
                status_code=403,
                detail="access denied: session is owned by another caller",
            )

    @sessions.post("", response_model=SessionCreateResponse)
    async def create_session(payload: SessionCreateRequest, request: Request) -> Any:
        # boot_agent runs MCP subprocess spawns — move off the event loop so
        # SSE keepalives and health checks stay responsive during boot.
        caller_hash = _require_auth(request)
        result = await anyio.to_thread.run_sync(
            lambda: control_plane.create_session(
                client_id=payload.client_id,
                surface=payload.surface,
                capabilities=payload.capabilities,
                protocol_version=payload.protocol_version,
            )
        )
        # C1: stamp ownership immediately after creation so subsequent accesses
        # are gated.  When auth is disabled caller_hash is None — skip stamping.
        if caller_hash is not None:
            control_plane.set_session_owner(result["session_id"], caller_hash)
        return result

    @sessions.get("")
    async def list_sessions(request: Request, limit: int = Query(default=10, ge=1, le=100)) -> Any:
        # C1: filter sessions so a caller only sees sessions they own.
        # Legacy sessions (NULL owner) are always returned for backward compat.
        caller_hash = _require_auth(request)
        # B5+B7a: offload the SQLite read (now 2 queries instead of 2N) off the
        # event loop; owner filtering runs inline after (in-memory O(1) dict lookups).
        all_sessions = await anyio.to_thread.run_sync(lambda: control_plane.recent_sessions(limit))
        if caller_hash is None:
            # No-auth mode: return everything.
            return all_sessions

        # Filter: include the session if the owner is NULL (legacy) or matches caller.
        def _owned(s: dict[str, Any]) -> bool:
            sid = s.get("session_id") or s.get("id") or ""
            if not sid:
                return True  # can't tell — include it
            owner = control_plane.get_session_owner(sid)
            return owner is None or secrets.compare_digest(owner, caller_hash)

        if isinstance(all_sessions, list):
            return [s for s in all_sessions if _owned(s)]
        return all_sessions

    @sessions.get("/{session_id}")
    async def get_session(session_id: str, request: Request) -> Any:
        _check_session_ownership(session_id, _require_auth(request))
        return control_plane.session_state(session_id)

    # Step 7 — Minimal slash-command handler.
    # Intercepts messages whose text starts with '/' BEFORE the LLM sees them
    # so that simple meta-commands work even when no agent is booted yet.
    _SLASH_HELP_TEXT = (
        "Available slash commands:\n"
        "  /model — Show the current model and how to change it\n"
        "  /memory <query>  — Search long-term memory\n"
        "  /remember <fact> — Save a fact to long-term memory\n"
        "  /help  — Show this help text"
    )

    def _build_augmented_prompt(prompt: str, attachment_ids: list[str]) -> str:
        """Append file-attachment context blocks to *prompt* (graceful: errors skipped)."""
        if not attachment_ids:
            return prompt
        try:
            from hachi.core.files.store import FileMetaStore, LocalStorageProvider
            from hachi.core.paths import get_hachi_paths

            paths = get_hachi_paths()
            meta_store = FileMetaStore(paths.files_db)
            storage = LocalStorageProvider(paths.blobs_dir)

            parts: list[str] = []
            for file_id in attachment_ids[:5]:  # cap at 5 attachments per turn
                try:
                    meta = meta_store.get(file_id)
                    if meta is None:
                        continue
                    if meta.media_type.startswith("image/"):
                        blob_path = str(paths.blobs_dir / file_id)
                        parts.append(
                            f"[Attached image: {meta.name}]\n"
                            f"(Use the view_image tool with path: {blob_path})"
                        )
                    elif meta.extracted_text_ref:
                        try:
                            with storage.open(meta.extracted_text_ref) as f:
                                text = f.read(4096).decode("utf-8", errors="replace")
                            parts.append(f"[Attached file: {meta.name}]\n{text}")
                        except Exception:
                            parts.append(f"[Attached file: {meta.name} — extraction pending]")
                    else:
                        parts.append(
                            f"[Attached file: {meta.name} ({meta.media_type})]"
                            " — no extracted text yet"
                        )
                except Exception:
                    continue
            if not parts:
                return prompt
            return prompt.rstrip() + "\n\n" + "\n\n".join(parts)
        except Exception:
            return prompt

    def _handle_slash_command(session_id: str, prompt: str) -> dict[str, Any] | None:
        """Return a synthetic assistant response for leading-slash commands, or None.

        Returns None when ``prompt`` is NOT a slash command so the caller can
        fall through to the normal LLM path unaffected.
        """
        stripped = prompt.strip()
        if not stripped.startswith("/"):
            return None
        # Extract the command word (everything up to first whitespace) and the
        # remainder of the line as the command's argument text.
        rest = stripped[1:]
        parts = rest.split(maxsplit=1)
        word = parts[0].lower() if rest.strip() else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if word == "model":
            try:
                from hachi.core.config_loader import load_effective_config as _load_cfg

                cfg = _load_cfg()
                model_name = cfg.provider.model
                provider_kind = cfg.provider.kind
            except Exception:
                model_name = "unknown"
                provider_kind = "unknown"
            reply = (
                f"Current model: **{model_name}** (provider: {provider_kind})\n\n"
                "To change the model, go to **Settings → Provider** in the web UI, "
                "or run `hachi setup --tier lightning` and select a different model."
            )
        elif word == "memory":
            # H4: /memory <query> — real semantic recall, wired to GET /memory/recall's
            # backing handler so this behaves identically to that endpoint.
            if not arg:
                reply = "Usage: `/memory <query>` — searches long-term memory for a query."
            else:
                try:
                    hits = control_plane.memory_recall(query=arg, top_k=5)
                except Exception:
                    hits = []
                if not hits:
                    reply = f"No memory found for “{arg}”."
                else:
                    lines = [f"Memory results for “{arg}”:"]
                    for hit in hits:
                        content = (
                            hit.get("content") or hit.get("raw_content") or ""
                            if isinstance(hit, dict)
                            else str(hit)
                        )
                        if content:
                            lines.append(f"- {content}")
                    reply = "\n".join(lines)
        elif word == "remember":
            # H4: /remember <fact> — real write, wired to POST /memory/facts' backing
            # handler (stored in the user_profile collection, like the UI's memory tool).
            if not arg:
                reply = "Usage: `/remember <fact>` — saves a fact to long-term memory."
            else:
                try:
                    control_plane.add_memory_fact(group="user_profile", text=arg)
                    reply = f"Got it — I'll remember: “{arg}”."
                except Exception as exc:
                    reply = f"Couldn't save that fact: {exc}"
        elif word == "help":
            reply = _SLASH_HELP_TEXT
        else:
            reply = f"Unknown command `/{word}`. Try /help to see available commands."

        return {"response": reply}

    @sessions.post(
        "/{session_id}/messages",
        response_model=SessionMessageResponse,
        response_model_exclude_none=True,
    )
    def post_message(session_id: str, payload: SessionMessageRequest, request: Request) -> Any:
        _check_session_ownership(session_id, _require_auth(request))
        # Ingress idempotency (AUDIT P0-3 / Theme A): a duplicate POST — client retry,
        # reconnect, or double-click — carrying the same key replays the prior turn's
        # response instead of re-running the whole turn (no double spend, no duplicate
        # side effects). The header wins over the body field; an absent key disables it.
        idem_key = (request.headers.get("Idempotency-Key") or payload.idempotency_key or "").strip()
        store = _resolve_session_store() if idem_key else None
        if store is not None:
            prior = store.get_idempotent_response(session_id, idem_key)
            if prior is not None:
                return prior
        # Step 7: intercept slash commands before the LLM.
        slash_result = _handle_slash_command(session_id, payload.prompt)
        if slash_result is not None:
            return slash_result
        augmented = _build_augmented_prompt(payload.prompt, payload.attachment_ids)
        result = control_plane.send_message(session_id=session_id, prompt=augmented)
        # Persist only on success (send_message raises on failure → left retryable).
        if store is not None:
            store.save_idempotent_response(session_id, idem_key, result)
        return result

    @sessions.delete("/{session_id}", response_model=SessionCloseResponse)
    async def delete_session(session_id: str, request: Request) -> Any:
        _check_session_ownership(session_id, _require_auth(request))
        return control_plane.close_session(session_id)

    # P1-4 — POST /sessions/{session_id}/interrupt
    # Signals the live execution loop to stop at its next iteration boundary so that
    # a browser Stop button or SSE disconnect actually cancels the server-side turn
    # instead of only closing the coroutine while the worker thread keeps running.
    @sessions.post("/{session_id}/interrupt", response_model=SessionInterruptResponse)
    async def interrupt_session(session_id: str, request: Request) -> Any:
        """Cancel the in-progress turn for a live session.

        Delivers a cancellation signal to the session's ``ExecutionLoop`` via
        ``ExecutionLoop.cancel()`` (a thread-safe ``threading.Event``). The current
        LLM chunk and any in-progress tool call finish first; the loop exits cleanly
        at the top of the following iteration, preserving message-history integrity.

        Returns ``{"interrupted": true}`` when the signal was delivered to a live
        session, ``{"interrupted": false}`` when the session is not live or no
        in-process runtime is attached (safe — never raises a 5xx).
        """
        _check_session_ownership(session_id, _require_auth(request))
        return control_plane.interrupt(session_id)

    # Issue 12 — POST /sessions/cleanup-empty
    # Deletes session rows that have no messages (ghost sessions accumulated before
    # the lazy-row-creation fix landed).  Requires auth; returns {"removed": <int>}.
    @sessions.post("/cleanup-empty")
    async def cleanup_empty_sessions() -> Any:
        """Delete all empty sessions (no messages) from the SQLite store.

        Safe to call at any time.  Sessions that are currently booting (in-memory
        but with no messages yet) are not affected — they have no DB row yet.

        Returns:
            ``{"removed": <count>}`` — the number of rows deleted.
        """
        removed = 0
        try:
            from hachi.gateway.shared_services import ProcessSharedServices

            _shared = ProcessSharedServices.instance()
            if _shared is not None and hasattr(_shared, "session_store"):
                _store = _shared.session_store
                if _store is not None and hasattr(_store, "delete_empty_sessions"):
                    removed = _store.delete_empty_sessions()
            else:
                # Fallback: instantiate a fresh store (same DB file).
                from hachi.core.session_store import SessionStore

                _store = SessionStore()
                removed = _store.delete_empty_sessions()
        except Exception:
            _log.warning("cleanup_empty_sessions: failed to delete empty sessions", exc_info=True)
        return {"removed": removed}

    # TASK-B — GET /sessions/{session_id}/messages
    # Returns the durable transcript for a past (or live) session.  Sourced directly
    # from the SQLite SessionStore so it works even when the session is no longer active.
    # HTTP 404 when the session_id is unknown or has no persisted messages.
    @sessions.get("/{session_id}/messages")
    async def get_session_messages(
        session_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> Any:
        """Return the durable message transcript for *session_id*.

        Sourced from the SQLite ``messages`` table so it works for historical
        sessions that are no longer active.  Messages are returned in chronological
        order (oldest first).

        Returns::

            {
              "session_id": "<id>",
              "messages": [
                {"id": <int>, "role": "user"|"assistant"|"tool",
                 "content": "...", "tool_name": null|"...", "timestamp": "<iso>"},
                ...
              ]
            }

        HTTP 404 when *session_id* is unknown or has no persisted messages.
        """
        # B5: session_transcript hits SQLite — offload to thread so the event loop
        # stays free for SSE keepalives during a long message-history fetch.
        result = await anyio.to_thread.run_sync(
            lambda: control_plane.session_transcript(session_id=session_id, limit=limit)
        )
        if result is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
        return result

    # G1-T4 — POST /sessions/{session_id}/permissions/always-allow
    # The frontend posts to /sessions/current/permissions/always-allow — "current" is a
    # sentinel that the server resolves to the most-recently-booted session (or ignores
    # ownership when running no-auth).  When the literal session_id exists in the connection
    # map the ownership check applies; for the "current" sentinel we skip it (no session to
    # own) and delegate resolution to the handler.
    @sessions.post("/{session_id}/permissions/always-allow")
    async def post_always_allow(
        session_id: str, payload: AlwaysAllowRequest, request: Request
    ) -> Any:
        """Persist a standing always-allow rule for the given request+action pair.

        The frontend sends ``session_id = "current"`` as a sentinel; the backend
        resolves it to the active session or persists the rule globally.

        Body: ``{"request": "<tool/path>", "action": "<operation>"}``
        """
        caller_hash = _require_auth(request)
        # Only enforce ownership for real (non-sentinel) session ids.
        if session_id != "current":
            _check_session_ownership(session_id, caller_hash)
        return control_plane.add_always_allow(session_id, payload.request, payload.action)

    @sessions.get("/{session_id}/events", response_model=SessionEventsResponse)
    async def get_session_events(
        session_id: str,
        request: Request,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> Any:
        _check_session_ownership(session_id, _require_auth(request))
        # B5: thread the whole call — historical sessions hit SQLite via
        # _synthesize_history_events; live sessions use an in-memory slice (minor
        # thread-hop overhead, acceptable since live callers use SSE not this endpoint).
        return await anyio.to_thread.run_sync(
            lambda: control_plane.read_session_events(
                session_id=session_id, after=after, limit=limit
            )
        )

    @sessions.get("/{session_id}/stream")
    async def stream_session_events(
        session_id: str,
        request: Request,
        after: int = Query(default=0, ge=0),
        poll_interval: float = Query(default=1.0, ge=0.0, le=10.0),
        max_idle_cycles: int = Query(default=30, ge=1, le=600),
    ) -> StreamingResponse:
        """Server-Sent Events stream of runtime events — replaces client polling.

        Pushes events as they arrive, then closes after ``max_idle_cycles`` idle
        polls (an EventSource auto-reconnects, so this stays cheap and robust).
        Clients resume with the last ``id`` they saw via the ``after`` query param.
        """
        # C1: ownership check before any streaming starts.
        _check_session_ownership(session_id, _require_auth(request))
        # Validate up front so unknown-session / unattached-stream surface as proper
        # HTTP errors instead of mid-stream failures.
        control_plane.read_session_events(session_id=session_id, after=after, limit=1)

        async def event_stream() -> AsyncIterator[str]:
            cursor = after
            idle = 0
            # MED-002: use asyncio.Event to avoid busy-polling.  The event is set
            # by a short-interval background task that acts as an adaptive timer
            # rather than a fixed sleep.  When the session just produced events we
            # wait only 50 ms (tight loop for incremental text); when idle we wait
            # up to poll_interval seconds, waking early if new events arrive.
            _wake = asyncio.Event()
            _wake.set()  # fire immediately on first iteration

            async def _poll_trigger() -> None:
                """Signal _wake whenever the session has events or at poll_interval."""
                while True:
                    await asyncio.sleep(0.05)
                    _wake.set()

            _trigger_task: asyncio.Task[None] = asyncio.create_task(_poll_trigger())

            yield ": connected\n\n"
            try:
                while True:
                    # Wait for wake signal (set either on first tick or by trigger task).
                    await _wake.wait()
                    _wake.clear()

                    if await request.is_disconnected():
                        # P1-4: on browser disconnect also cancel the server-side turn so
                        # the worker thread stops, not just the coroutine awaiting it.
                        control_plane.interrupt(session_id)
                        break
                    try:
                        batch = control_plane.read_session_events(
                            session_id=session_id, after=cursor, limit=100
                        )
                    except (GatewayProtocolError, GatewayUnavailableError):
                        # Session was closed (or the runtime detached) mid-stream. The
                        # response has already started, so end gracefully instead of
                        # letting the exception abort the connection.
                        yield "event: closed\ndata: {}\n\n"
                        break
                    events = batch.get("events", [])
                    if events:
                        idle = 0
                        for event in events:
                            cursor = event["sequence"]
                            yield (
                                f"id: {event['sequence']}\n"
                                f"event: {event['event_type']}\n"
                                f"data: {json.dumps(event)}\n\n"
                            )
                    else:
                        idle += 1
                        if idle >= max_idle_cycles:
                            break
                        yield ": keepalive\n\n"
                        # Slow down the trigger task when idle to save CPU.
                        await asyncio.sleep(max(0.0, poll_interval - 0.05))
            finally:
                _trigger_task.cancel()
                try:
                    await _trigger_task
                except asyncio.CancelledError:
                    pass

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    @runtime_ops.get("/runtime/events")
    async def get_runtime_events(
        session_id: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> Any:
        return control_plane.runtime_events(session_id=session_id, limit=limit)

    @runtime_ops.get("/runtime/mcp/inventory")
    async def get_mcp_inventory() -> Any:
        return control_plane.mcp_inventory()

    # G1-T5 / CONTRACT-MCP — POST /runtime/mcp/register
    @runtime_ops.post("/runtime/mcp/register")
    async def post_mcp_register(payload: McpRegisterRequest) -> Any:
        """Register a new MCP server and bring it online without a gateway restart.

        Body (stdio transport):
            ``{"name": "...", "command": "npx", "args": "...", "env_vars": {}}``

        Body (sse / http transport):
            ``{"name": "...", "transport": "sse"|"http", "url": "https://...", "headers": {}}``
        """
        _ALLOWED_COMMANDS = {"npx", "uvx", "python", "python3", "node", "uv"}
        _ALLOWED_TRANSPORTS = {"stdio", "sse", "http"}
        _SECRET_PATTERNS = {
            "key",
            "token",
            "secret",
            "password",
            "passwd",
            "credential",
            "private",
            "auth",
            "bearer",
            "apikey",
            "api_key",
        }
        import re

        name = payload.name.strip()
        transport = payload.transport.strip().lower()

        if not name or not re.match(r"^[\w-]+$", name):
            raise HTTPException(
                status_code=422,
                detail=(
                    "name must be non-empty and contain only letters, digits, hyphens, underscores"
                ),
            )
        if transport not in _ALLOWED_TRANSPORTS:
            raise HTTPException(
                status_code=422,
                detail=f"transport must be one of: {', '.join(sorted(_ALLOWED_TRANSPORTS))}",
            )

        if transport == "stdio":
            command = payload.command.strip()
            args = payload.args.strip()
            if command not in _ALLOWED_COMMANDS:
                raise HTTPException(
                    status_code=422,
                    detail=f"command must be one of: {', '.join(sorted(_ALLOWED_COMMANDS))}",
                )
            if not args:
                raise HTTPException(status_code=422, detail="args is required for stdio transport")
            if re.search(r"[;&|><`]|\$[({]|&&|\|\|", args):
                raise HTTPException(
                    status_code=422,
                    detail="args must not contain shell metacharacters",
                )
        else:
            # sse / http
            url = payload.url.strip()
            if not url or not re.match(r"^https?://", url):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"url is required and must be an http/https URL for {transport} transport"
                    ),
                )

        # Reject raw secrets in env_vars/headers; allow secret:<name> references (BB-9).
        # A key that looks like a secret (contains "key", "token", etc.) is accepted ONLY
        # when its value is a secret: reference — which resolves at connect time, so the
        # real credential never touches TOML.  We also verify the cred: entry exists now
        # so a dangling reference is caught before the config is persisted.
        all_pairs: list[tuple[str, str]] = list(payload.env_vars.items()) + list(
            payload.headers.items()
        )
        for env_key, env_val in all_pairs:
            lower = env_key.lower()
            key_looks_secret = any(p in lower for p in _SECRET_PATTERNS)
            val_is_ref = isinstance(env_val, str) and env_val.startswith("secret:")
            if key_looks_secret and not val_is_ref:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"key '{env_key}' looks like a secret; "
                        "store the value via POST /runtime/secrets "
                        "and reference it as secret:<name>"
                    ),
                )
            if val_is_ref:
                cred_name = env_val[len("secret:") :]
                try:
                    from hachi.core.secret_store import (
                        create_default_secret_store as _css,
                    )

                    if _css().get(f"cred:{cred_name}") is None:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                f"secret reference 'secret:{cred_name}' "
                                "has no matching credential. "
                                f"Store it via POST /runtime/secrets name='{cred_name}'."
                            ),
                        )
                except HTTPException:
                    raise
                except Exception:
                    pass  # secret store unavailable — skip validation, fail at connect time

        return control_plane.register_mcp_server(
            name=name,
            transport=transport,
            command=payload.command.strip(),
            args=payload.args.strip(),
            env_vars=dict(payload.env_vars),
            url=payload.url.strip(),
            headers=dict(payload.headers),
        )

    # CONTRACT-MCP — POST /runtime/mcp/{name}/enable
    @runtime_ops.post("/runtime/mcp/{name}/enable")
    async def post_mcp_enable(name: str) -> Any:
        """Enable the named MCP server (persists ``enabled=true`` to settings.toml).

        Returns ``{"ok": true}`` on success, HTTP 404 if the server is unknown.
        """
        return control_plane.set_mcp_enabled(name=name, enabled=True)

    # CONTRACT-MCP — POST /runtime/mcp/{name}/disable
    @runtime_ops.post("/runtime/mcp/{name}/disable")
    async def post_mcp_disable(name: str) -> Any:
        """Disable the named MCP server (persists ``enabled=false`` to settings.toml).

        Returns ``{"ok": true}`` on success, HTTP 404 if the server is unknown.
        """
        return control_plane.set_mcp_enabled(name=name, enabled=False)

    # CONTRACT-MCP — DELETE /runtime/mcp/{name}
    @runtime_ops.delete("/runtime/mcp/{name}")
    async def delete_mcp_server(name: str) -> Any:
        """Remove a registered MCP server from settings.toml.

        Returns ``{"ok": true}`` on success, HTTP 404 if the server is unknown.
        """
        return control_plane.delete_mcp_server(name=name)

    # ------------------------------------------------------------------ #
    # Credential manager — BB-9
    # Reserved namespace: cred:<name>  (system keys are never listed/deleted)
    # ------------------------------------------------------------------ #

    @runtime_ops.post("/runtime/secrets")
    async def post_secret(payload: SecretStoreRequest) -> Any:
        """Store a user-managed credential as ``cred:<name>`` in the secret store."""
        return control_plane.store_secret(payload.name, payload.value)

    @runtime_ops.get("/runtime/secrets")
    async def get_secrets() -> Any:
        """List user-managed credential names (``cred:`` prefix stripped, values never returned)."""
        return control_plane.list_secret_names()

    @runtime_ops.delete("/runtime/secrets/{name}")
    async def delete_secret(name: str) -> Any:
        """Delete ``cred:<name>`` (idempotent; system keys are silently ignored)."""
        return control_plane.delete_secret(name)

    @runtime_ops.get("/jobs/active")
    async def get_active_jobs() -> Any:
        return control_plane.active_jobs()

    @runtime_ops.get("/jobs/failed")
    async def get_failed_jobs(limit: int = Query(default=20, ge=1, le=200)) -> Any:
        return control_plane.failed_jobs(limit)

    @runtime_ops.get("/permissions/audit")
    async def get_permission_audit(
        limit: int = Query(default=50, ge=1, le=500),
    ) -> Any:
        return control_plane.permission_audit(limit)

    @runtime_ops.get("/subagents/reports")
    async def get_subagent_reports(
        query: str = Query(default="recent delegation"),
        top_k: int = Query(default=10, ge=1, le=100),
    ) -> Any:
        return control_plane.subagent_reports(query=query, top_k=top_k)

    @runtime_ops.get("/schedules")
    async def get_schedules() -> Any:
        return {"schedules": control_plane.list_schedules()}

    @runtime_ops.delete("/schedules/{schedule_id}")
    async def delete_schedule(schedule_id: str) -> Any:
        return control_plane.cancel_schedule(schedule_id)

    @runtime_ops.put("/schedules/{schedule_id}/enabled")
    async def put_schedule_enabled(schedule_id: str, payload: ScheduleToggleRequest) -> Any:
        return control_plane.toggle_schedule(schedule_id, payload.enabled)

    @runtime_ops.post("/schedules/{schedule_id}/run-now")
    async def post_schedule_run_now(schedule_id: str) -> Any:
        """Force-trigger a schedule immediately, regardless of its next-run time.

        Dispatches in the background (does not block on the agent turn); returns
        ``{"ok": true, "schedule_id": ...}`` once dispatch is confirmed, or
        ``{"ok": false, ...}`` if the schedule id is unknown or scheduling is
        unavailable (no active session).
        """
        return control_plane.run_schedule_now(schedule_id)

    @config.get("")
    async def get_config() -> Any:
        return control_plane.get_config()

    @config.put("/provider")
    async def put_provider(payload: ProviderRequest) -> Any:
        return control_plane.update_provider(payload.model_dump(mode="python"))

    @config.post("/provider/validate")
    async def post_provider_validate(payload: ProviderRequest) -> Any:
        return control_plane.validate_provider(payload.model_dump(mode="python"))

    @config.put("/permissions")
    async def put_permissions(payload: PermissionsRequest) -> Any:
        return control_plane.update_permissions(payload.model_dump(mode="python"))

    @config.put("/memory")
    async def put_memory(payload: MemoryRequest) -> Any:
        return control_plane.update_memory(payload.model_dump(mode="python"))

    # G1-T3 — PUT /config/limits (spend caps)
    @config.put("/limits")
    async def put_limits(payload: LimitsRequest) -> Any:
        """Persist per-task and daily spend caps.

        Body: ``{"per_task_cap_usd": 1.0, "daily_cap_usd": 5.0}``
        """
        return control_plane.update_limits(payload.model_dump(mode="python"))

    # G1-T3 — POST /config/permissions/folders (add allowed folder)
    @config.post("/permissions/folders")
    async def post_allowed_folder(payload: AllowedFolderRequest) -> Any:
        """Append a folder path to the allowed_paths list and persist to device-permissions.og."""
        return control_plane.add_allowed_folder(payload.path)

    # G1-T3 — POST /config/permissions/commands (add allowed command)
    @config.post("/permissions/commands")
    async def post_allowed_command(payload: AllowedCommandRequest) -> Any:
        """Append a command to the allowed_commands list and persist to device-permissions.og."""
        return control_plane.add_allowed_command(payload.command)

    # T2b — DELETE /config/permissions/folders (remove allowed folder)
    @config.delete("/permissions/folders")
    async def delete_allowed_folder(payload: AllowedFolderRequest) -> Any:
        """Remove a folder path from the allowed_paths list and persist to device-permissions.og."""
        return await anyio.to_thread.run_sync(
            lambda: control_plane.remove_allowed_folder(payload.path)
        )

    # T2b — DELETE /config/permissions/commands (remove allowed command)
    @config.delete("/permissions/commands")
    async def delete_allowed_command(payload: AllowedCommandRequest) -> Any:
        """Remove a command from the allowed_commands list and persist to device-permissions.og."""
        return await anyio.to_thread.run_sync(
            lambda: control_plane.remove_allowed_command(payload.command)
        )

    # ---- Multi-provider + routing admin routes ----

    @config.get("/providers")
    async def get_providers() -> Any:
        """Return all configured providers (secrets masked)."""
        return await anyio.to_thread.run_sync(lambda: control_plane.list_providers())

    @config.post("/providers")
    async def post_provider(payload: ProviderUpsertRequest) -> Any:
        """Add a new named provider."""
        name = (payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="name is required")
        import re as _re

        if not _re.match(r"^[A-Za-z0-9_-]+$", name):
            raise HTTPException(status_code=422, detail="invalid provider name")
        spec = payload.model_dump(mode="python", exclude={"name"}, exclude_none=True)
        return await anyio.to_thread.run_sync(
            lambda: control_plane.add_or_update_provider(name, spec)
        )

    @config.put("/providers/{name}")
    async def put_provider_named(name: str, payload: ProviderUpsertRequest) -> Any:
        """Update (or create) a named provider."""
        import re as _re

        if not _re.match(r"^[A-Za-z0-9_-]+$", name):
            raise HTTPException(status_code=422, detail="invalid provider name")
        spec = payload.model_dump(mode="python", exclude={"name"}, exclude_none=True)
        return await anyio.to_thread.run_sync(
            lambda: control_plane.add_or_update_provider(name, spec)
        )

    @config.delete("/providers/{name}")
    async def delete_provider(name: str) -> Any:
        """Remove a named provider."""
        import re as _re

        if not _re.match(r"^[A-Za-z0-9_-]+$", name):
            raise HTTPException(status_code=422, detail="invalid provider name")
        return await anyio.to_thread.run_sync(lambda: control_plane.remove_provider(name))

    @config.post("/providers/{name}/test-connection")
    async def post_provider_test(name: str) -> Any:
        """Best-effort connectivity test for a provider."""
        import re as _re

        if not _re.match(r"^[A-Za-z0-9_-]+$", name):
            raise HTTPException(status_code=422, detail="invalid provider name")
        return await anyio.to_thread.run_sync(lambda: control_plane.test_provider_connection(name))

    @config.post("/providers/probe")
    async def post_provider_probe(payload: ProviderUpsertRequest) -> Any:
        """Probe an unsaved provider spec: connectivity + available models.

        Returns ``{ok, detail, models}`` so the add/edit dialog can verify a key
        and populate a model picker before the provider is saved.
        """
        spec = payload.model_dump(mode="python", exclude_none=True)
        return await anyio.to_thread.run_sync(lambda: control_plane.probe_provider(spec))

    @config.get("/routing")
    async def get_routing() -> Any:
        """Return the capability routing matrix (synthesized when absent)."""
        return await anyio.to_thread.run_sync(lambda: control_plane.get_routing())

    @config.put("/routing")
    async def put_routing(payload: RoutingUpdateRequest) -> Any:
        """Persist the capability routing matrix (hot-reload — no restart)."""
        return await anyio.to_thread.run_sync(
            lambda: control_plane.set_routing(payload.default_model, payload.capabilities)
        )

    @config.post("/routing/validate")
    async def post_routing_validate(payload: RoutingUpdateRequest) -> Any:
        """Validate a routing config without persisting it.

        Returns ``{"ok": true, "issues": [], "warnings": []}`` on success or
        ``{"ok": false, "issues": [...], "warnings": [...]}`` on failure.
        Always returns HTTP 200 — the ``ok`` field signals validity.
        """
        return await anyio.to_thread.run_sync(
            lambda: control_plane.validate_routing(payload.default_model, payload.capabilities)
        )

    @config.post("/routing/rollback")
    async def post_routing_rollback() -> Any:
        """Restore the last-known-good routing config."""
        return await anyio.to_thread.run_sync(lambda: control_plane.rollback_routing())

    @config.get("/routing/audit")
    async def get_routing_audit(limit: int = 50) -> Any:
        """Return recent routing-change audit records (newest first)."""
        return await anyio.to_thread.run_sync(lambda: control_plane.get_routing_audit(limit=limit))

    @config.get("/models/all")
    async def get_models_all() -> Any:
        """Return model ids per configured provider."""
        return await anyio.to_thread.run_sync(lambda: control_plane.list_all_models())

    @setup.get("")
    async def get_setup() -> Any:
        return control_plane.setup_state()

    @setup.post("/apply")
    async def post_setup_apply(payload: SetupApplyRequest) -> Any:
        return control_plane.apply_setup(payload.model_dump(mode="python"))

    # OpenAI-compatible facade — lets users point Open WebUI / LibreChat / any
    # OpenAI client at Hachi. Maps the latest user message to an auto-managed
    # agent session (the agent keeps its own conversation memory).
    openai_compat = APIRouter(tags=["openai"], dependencies=protected_dependencies)
    openai_limiter = RateLimiter(_int_env("HACHI_OPENAI_RATE_LIMIT", 60), 60.0)

    @openai_compat.post("/v1/chat/completions")
    async def openai_chat_completions(payload: OpenAIChatRequest, request: Request) -> Any:
        # H6: resolve the caller's identity so a facade session created below is
        # stamped with an owner, same as the normal POST /sessions route.
        caller_hash = _require_auth(request)
        prompt = _last_user_text(payload.messages)
        if not prompt:
            raise HTTPException(status_code=400, detail="no user message content")
        # BB-58: key the rate limiter per-principal (the same caller_hash H6 uses
        # for session ownership) instead of one shared global bucket — otherwise
        # one caller exhausting the limit locks out every other caller too.
        # ``caller_hash`` is None in no-auth mode; fall back to a fixed key there
        # since there is no notion of distinct principals without auth.
        rate_key = caller_hash or "anonymous"
        if not openai_limiter.allow(rate_key):
            raise HTTPException(status_code=429, detail="rate limit exceeded; slow down")

        # BB-58: validate (not silently ignore) the requested model. When the
        # control plane has allowlist data (list_all_models — the same data that
        # powers GET /config/models/all), reject unrecognized model ids instead
        # of silently substituting a default. When no allowlist data is wired
        # (handler not attached), fail open — nothing to validate against.
        requested_model = (payload.model or "").strip()
        if requested_model:
            try:
                all_models = await anyio.to_thread.run_sync(control_plane.list_all_models)
            except Exception:
                all_models = {}
            known_models: set[str] = set()
            if isinstance(all_models, dict):
                for ids in all_models.values():
                    if isinstance(ids, list):
                        known_models.update(str(i) for i in ids)
            if known_models and requested_model not in known_models:
                raise HTTPException(
                    status_code=400,
                    detail=f"model '{requested_model}' is not recognized or allowed",
                )

        chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created_ts = int(time.time())
        model_name = payload.model or "hachi"

        if not payload.stream:
            # Full agent turn is synchronous — run in a thread so the event loop stays free.
            result = await anyio.to_thread.run_sync(
                lambda: control_plane.complete_chat(prompt, owner_token_hash=caller_hash)
            )
            reply = result.get("response", "")
            return {
                "id": chat_id,
                "object": "chat.completion",
                "created": created_ts,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }

        # Streaming path: forward text.stream.delta events as OpenAI SSE chunks.
        # Each chunk carries one text fragment so clients can render incrementally.
        async def _openai_event_stream() -> AsyncIterator[str]:
            # Create/get the session before starting the turn so we can read its events.
            session_key = f"openai-{chat_id}"
            session_id: str = await anyio.to_thread.run_sync(
                lambda: control_plane.get_or_create_session(
                    session_key, owner_token_hash=caller_hash
                )
            )

            # Snapshot the event cursor so only events from THIS turn are forwarded.
            initial = control_plane.read_session_events(session_id=session_id, after=0, limit=10000)
            cursor = max((e["sequence"] for e in initial.get("events", [])), default=0)

            # OpenAI streaming: role chunk first, then content deltas.
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant"},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
                + "\n\n"
            )

            # Run the full agent turn in a background task.
            turn_done: asyncio.Event = asyncio.Event()

            async def _run_turn() -> None:
                try:
                    await anyio.to_thread.run_sync(
                        lambda: control_plane.send_message(session_id=session_id, prompt=prompt)
                    )
                finally:
                    turn_done.set()

            turn_task: asyncio.Task[None] = asyncio.create_task(_run_turn())
            # MED-002: event-driven wake instead of fixed 0.05 s busy-poll.
            _sse_wake = asyncio.Event()
            _sse_wake.set()  # fire immediately on first iteration

            async def _sse_trigger() -> None:
                while True:
                    await asyncio.sleep(0.05)
                    _sse_wake.set()

            _sse_trigger_task: asyncio.Task[None] = asyncio.create_task(_sse_trigger())
            try:
                while True:
                    await _sse_wake.wait()
                    _sse_wake.clear()

                    if await request.is_disconnected():
                        turn_task.cancel()
                        # P1-4: also cancel the worker thread, not just the coroutine.
                        control_plane.interrupt(session_id)
                        return

                    batch = control_plane.read_session_events(
                        session_id=session_id, after=cursor, limit=200
                    )
                    events = batch.get("events", [])

                    for event in events:
                        cursor = event["sequence"]
                        if event.get("event_type") == "text.stream.delta":
                            text = (event.get("payload") or {}).get("text", "")
                            if text:
                                yield (
                                    "data: "
                                    + json.dumps(
                                        {
                                            "id": chat_id,
                                            "object": "chat.completion.chunk",
                                            "created": created_ts,
                                            "model": model_name,
                                            "choices": [
                                                {
                                                    "index": 0,
                                                    "delta": {"content": text},
                                                    "finish_reason": None,
                                                }
                                            ],
                                        }
                                    )
                                    + "\n\n"
                                )

                    if turn_done.is_set() and not events:
                        break
            finally:
                _sse_trigger_task.cancel()
                try:
                    await _sse_trigger_task
                except asyncio.CancelledError:
                    pass
                if not turn_task.done():
                    turn_task.cancel()
                    try:
                        await turn_task
                    except asyncio.CancelledError:
                        pass

            # Finish chunk signals end of stream.
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                )
                + "\n\n"
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _openai_event_stream(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    @openai_compat.get("/v1/models")
    async def openai_models() -> Any:
        data: list[dict[str, Any]] = []
        try:
            models = control_plane.models()
            for item in models if isinstance(models, list) else []:
                model_id = item.get("id") if isinstance(item, dict) else str(item)
                if model_id:
                    data.append({"id": model_id, "object": "model", "owned_by": "hachi"})
        except Exception:
            pass
        if not data:
            data = [{"id": "hachi", "object": "model", "owned_by": "hachi"}]
        return {"object": "list", "data": data}

    # Generic inbound webhook: any platform (Slack Events, Discord, Twilio SMS, a
    # custom form) can POST a message and reach the agent, with per-sender session
    # continuity. Bespoke adapters are optional sugar on top of this.
    channels_router = APIRouter(tags=["channels"], dependencies=protected_dependencies)
    # Per-sender abuse protection for the externally-reachable webhook.
    channel_limiter = RateLimiter(_int_env("HACHI_CHANNEL_RATE_LIMIT", 30), 60.0)
    channel_allowlist = _parse_allowlist(os.environ.get("HACHI_CHANNEL_ALLOWLIST"))

    @channels_router.post("/channels/{channel}/inbound")
    async def channel_inbound(
        channel: str, payload: ChannelInboundRequest, request: Request
    ) -> Any:
        # H6: resolve the caller's identity (the webhook's bearer token, not the
        # attacker-controlled sender_id) so the facade session for this
        # channel:sender key is stamped with a real owner.
        caller_hash = _require_auth(request)
        if not payload.text.strip():
            raise HTTPException(status_code=400, detail="text is required")
        sender = payload.sender_id
        # Optional allowlist accepts either a bare sender id or "channel:sender".
        if channel_allowlist and not (
            sender in channel_allowlist or f"{channel}:{sender}" in channel_allowlist
        ):
            raise HTTPException(status_code=403, detail="sender is not allowed")
        session_key = f"{channel}:{sender}"
        # MED-003: key the rate limiter on client IP (not user-supplied sender_id) so
        # an attacker cannot bypass limits by cycling through sender values.  We keep
        # session_key for session continuity but limit by IP+channel.
        client_ip = (request.client.host if request.client else "unknown") or "unknown"
        rate_key = f"{channel}:{client_ip}"
        if not channel_limiter.allow(rate_key):
            raise HTTPException(status_code=429, detail="rate limit exceeded; slow down")
        # H10: wrap inbound webhook text in the untrusted-content data envelope,
        # matching the treatment applied by the polling ChannelRouter (channels/router.py).
        # guard_untrusted is unconditional per SEC-002 — it always frames the content
        # as data even when no injection is detected.
        source_label = f"channel:{channel} sender:{sender}"
        guarded_text, _flagged = guard_untrusted(payload.text, source=source_label)
        # Full agent turn is synchronous — run in a thread so the event loop stays free.
        result = await anyio.to_thread.run_sync(
            lambda: control_plane.complete_chat(
                guarded_text, session_key=session_key, owner_token_hash=caller_hash
            )
        )
        return {
            "channel": channel,
            "recipient_id": sender,
            "reply": result.get("response", ""),
        }

    # UC-PERM-006: Approvals inbox REST surface.
    # These endpoints expose the pending-permission queue so that the web
    # companion and other clients can approve/deny agent actions.
    # Both routes are protected by the same auth dependency as all other routes.
    approvals_router = APIRouter(
        prefix="/approvals", tags=["approvals"], dependencies=protected_dependencies
    )

    @approvals_router.get("")
    async def get_approvals() -> Any:
        """List all pending permission requests.

        Returns:
            A JSON object ``{"pending": [...]}`` with every unresolved request
            from the approval registry.  Each entry includes ``expiresAt``
            (MED-021) — an ISO-8601 timestamp so that the frontend countdown
            timer can render.
        """
        if not _APPROVALS_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Approvals module not yet available — Agent A module pending.",
            )
        import datetime as _dt

        # MED-021: annotate each pending request with a conservative expiresAt.
        # The real per-request timeout is tracked inside RegistryApprover; here
        # we use a 60 s window that covers the default approval timeout.  Forward-
        # compatible: if the registry ever adds expiresAt itself, we skip injection.
        _default_ttl_s = 60
        _now = _dt.datetime.now(_dt.UTC)
        _expires_at = (_now + _dt.timedelta(seconds=_default_ttl_s)).isoformat()
        pending = get_approval_registry().list_pending()
        for item in pending:
            if "expiresAt" not in item:
                item["expiresAt"] = _expires_at
        return {"pending": pending}

    @approvals_router.post("/{request_id}")
    async def post_approval_decision(
        request_id: str,
        payload: ApprovalActionRequest,
    ) -> Any:
        """Resolve a pending permission request.

        Args:
            request_id: The opaque ID from the pending-request list.
            payload: ``{"action": "approve"|"deny"|"allow_once", "rationale": "..."}``

        Returns:
            ``{"resolved": true}`` on success.

        Raises:
            404: When ``request_id`` is not found in the registry.
            422: When ``action`` is not a valid :class:`PermissionDecision` action.
        """
        if not _APPROVALS_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Approvals module not yet available — Agent A module pending.",
            )
        valid_actions = {"approve", "deny", "allow_once"}
        if payload.action not in valid_actions:
            raise HTTPException(
                status_code=422,
                detail=f"action must be one of: {', '.join(sorted(valid_actions))}",
            )
        decision = PermissionDecision(action=payload.action, rationale=payload.rationale)
        resolved = get_approval_registry().resolve(request_id, decision)
        if not resolved:
            raise HTTPException(status_code=404, detail=f"Unknown request_id: {request_id}")
        return {"resolved": True}

    # ==========================================
    # Web UI routes (#1–#6)
    # ==========================================

    skills_router = APIRouter(tags=["skills"], dependencies=protected_dependencies)
    memory_router = APIRouter(
        prefix="/memory", tags=["memory"], dependencies=protected_dependencies
    )
    og_router = APIRouter(prefix="/og", tags=["og"], dependencies=protected_dependencies)
    authoring_router = APIRouter(
        prefix="/authoring", tags=["authoring"], dependencies=protected_dependencies
    )
    spend_router = APIRouter(tags=["spend"], dependencies=protected_dependencies)

    @skills_router.get("/skills")
    async def get_skills() -> Any:
        """Return the .og skill inventory list."""
        return control_plane.skills()

    # G1-T6 — GET /skills/kennel (available skills to install)
    @skills_router.get("/skills/kennel")
    async def get_kennel() -> Any:
        """Return the available skills catalogue (kennel) for browsing and installation."""
        return control_plane.kennel()

    # G1-T6 — POST /skills/add (install a skill)
    @skills_router.post("/skills/add")
    async def post_skill_add(payload: SkillAddRequest) -> Any:
        """Install a skill from the kennel by id.

        Body: ``{"kennel_id": "..."}``
        """
        return control_plane.add_skill(payload.kennel_id)

    @memory_router.get("")
    async def get_memory() -> Any:
        """Return grouped memory facts, blocked items, and proposed changes."""
        return control_plane.memory()

    @memory_router.get("/recall")
    async def get_memory_recall(
        query: str = Query(..., min_length=1),
        top_k: int = Query(default=8, ge=1, le=50),
    ) -> Any:
        """Return semantic memory recall hits for the given query."""
        return control_plane.memory_recall(query=query, top_k=top_k)

    @memory_router.post("/facts")
    async def post_memory_fact(payload: MemoryFactAddRequest) -> Any:
        """Add a fact to a vault collection.

        Body: ``{"group": "user_profile", "text": "..."}``
        Returns: ``{"id": "<fact_id>"}``
        """
        return control_plane.add_memory_fact(group=payload.group, text=payload.text)

    @memory_router.delete("/facts/{fact_id}")
    async def delete_memory_fact(fact_id: str) -> Any:
        """Delete a fact from the vault by its content-hash id.

        Returns: ``{"ok": true}``
        """
        return control_plane.delete_memory_fact(fact_id=fact_id)

    @og_router.get("/graph")
    async def get_og_graph() -> Any:
        """Return the ObjectGraph node graph with per-pass token estimates."""
        return control_plane.og_graph()

    @authoring_router.get("/targets")
    async def get_authoring_targets() -> Any:
        """List editable .og and config files in the workspace."""
        return control_plane.authoring_targets()

    @authoring_router.get("/targets/{name}")
    async def get_authoring_target(name: str) -> Any:
        """Return the source text for a single editable target."""
        return control_plane.authoring_target(name)

    @authoring_router.post("/targets/{name}/generate")
    async def post_authoring_generate(name: str, payload: AuthoringGenerateRequest) -> Any:
        """Generate a proposed patch for the named target via the LLM (G1-T2 / CRIT-002).

        Runs the blocking LLM call off the event loop via anyio.to_thread.run_sync.
        Returns a real unified diff (old vs proposed) and the proposed content.
        Pending content is stored server-side so /apply can write it without
        the client having to re-send the full body.

        Body: ``{"prompt": "describe the change you want"}``
        Response: ``{"diff": [["" | "add" | "del", "<line>"], ...]}``
        """
        prompt = payload.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=422, detail="prompt is required")
        result = await anyio.to_thread.run_sync(
            lambda: control_plane.authoring_generate(name, prompt)
        )
        return result

    @authoring_router.post("/targets/{name}/apply")
    async def post_authoring_apply(name: str) -> Any:
        """Apply the pending patch to the target and trigger a skill-engine re-index."""
        return await anyio.to_thread.run_sync(lambda: control_plane.authoring_apply(name))

    @authoring_router.post("/targets/{name}/revert")
    async def post_authoring_revert(name: str) -> Any:
        """Revert the most recently applied patch for the target."""
        return await anyio.to_thread.run_sync(lambda: control_plane.authoring_revert(name))

    # CONTRACT-AUTHORING-SAVE — POST /authoring/targets/{name}/source
    @authoring_router.post("/targets/{name}/source")
    async def post_authoring_save_source(name: str, payload: AuthoringSourceSaveRequest) -> Any:
        """Persist manually edited .og content for the named target.

        Validates the target name (path-traversal guard), parses the content as a
        valid ObjectGraph for .og files (returns 4xx on parse failure without overwriting),
        and writes atomically.

        Body: ``{"content": "<full .og text>"}``
        Response: ``{"ok": true, "name": "<target-name>"}``
        """
        content = payload.content
        if not content.strip():
            raise HTTPException(status_code=422, detail="content cannot be empty")
        return await anyio.to_thread.run_sync(
            lambda: control_plane.authoring_save_source(name, content)
        )

    @spend_router.get("/spend")
    async def get_spend(session_id: str | None = Query(default=None)) -> Any:
        """Return per-turn token/cost rows, compaction events, and model totals."""
        return control_plane.spend(session_id=session_id)

    @spend_router.get("/spend/daily")
    async def get_spend_daily() -> Any:
        """Return today's accumulated spend from the daily ledger plus configured caps."""
        return control_plane.spend_daily()

    @system.put("/capabilities/{cap_id}/enabled")
    async def put_capability_enabled(
        cap_id: str,
        payload: CapabilityToggleRequest,
        _auth: None = Depends(_require_auth),
    ) -> Any:
        """Toggle a capability on/off and persist to global config."""
        return control_plane.set_capability_enabled(cap_id, payload.enabled)

    # ==========================================
    # OAuth 2.0 integration routes
    # ==========================================

    integrations_router = APIRouter(
        prefix="/integrations",
        tags=["integrations"],
        dependencies=protected_dependencies,
    )
    # Callback does NOT carry the auth dependency — the browser popup calls it directly
    # and does not have the Bearer token.  State validation provides CSRF protection.
    integrations_callback_router = APIRouter(prefix="/integrations", tags=["integrations"])

    @integrations_router.get("")
    async def get_integrations() -> Any:
        """List all connectors with their auth_type, configured, connected, and status fields.

        Issue 5: the Tavily/search connector entry also carries ``fallback_active``
        (True when no web_search provider is registered, so browse_web/Playwright is the
        active fallback). The frontend reads this off GET /integrations to show a
        "web search unavailable — using Playwright fallback" notice. Computed here so
        GET /integrations and the POST /credentials response agree.
        """
        from hachi.integrations.oauth_flow import all_connector_statuses

        statuses = await anyio.to_thread.run_sync(all_connector_statuses)

        fallback_active = True
        try:
            from hachi.gateway.shared_services import ProcessSharedServices

            _shared = ProcessSharedServices.instance()
            if _shared is not None:
                _pr = getattr(_shared, "provider_registry", None)
                if _pr is not None and hasattr(_pr, "get_search"):
                    fallback_active = _pr.get_search() is None
        except Exception:
            pass

        for entry in statuses:
            if isinstance(entry, dict) and entry.get("id") == "tavily":
                entry["fallback_active"] = fallback_active
        return statuses

    @integrations_router.post("/{connector_id}/oauth/start")
    async def post_oauth_start(connector_id: str) -> Any:
        """Begin the OAuth2 flow for the given connector.

        Returns ``{"authorization_url": "<provider-authorize-url>"}`` so the
        frontend can open it in a popup window.

        Returns HTTP 404 for unknown connectors, HTTP 409 when the connector's
        client credentials (env vars) are not configured on this machine.
        """
        import re

        from hachi.integrations.oauth_flow import oauth_start

        if not re.match(r"^[a-z0-9_-]+$", connector_id):
            return _error_response(400, "invalid_connector_id", "Connector id is not valid")

        try:
            result = oauth_start(connector_id)
        except ValueError as exc:
            return _error_response(404, "unknown_connector", str(exc))
        except LookupError as exc:
            return _error_response(
                409,
                "credentials_not_configured",
                str(exc),
            )
        return result

    @integrations_callback_router.get("/oauth/callback")
    async def get_oauth_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> Any:
        """OAuth2 callback — provider redirects the user's browser popup here.

        Validates the CSRF state, exchanges the code for tokens, stores them,
        then returns a small HTML page that:
        - postMessages ``{type: "hachi_oauth_done", id: "<id>", ok: true/false}``
          to the opener (the Hachi frontend).
        - Closes the popup window.

        This route is intentionally NOT protected by the Bearer auth dependency
        because the provider redirects the user's browser here directly.
        CSRF protection is provided by the ``state`` parameter.
        """
        from fastapi.responses import HTMLResponse

        from hachi.integrations.oauth_flow import (
            _callback_html_error,
            _callback_html_ok,
            oauth_callback,
        )

        if error:
            # Provider signalled an error (e.g. user denied consent).
            safe_error = str(error)[:200]
            html = _callback_html_error(
                "",
                f"The provider returned an error: {safe_error}. Please try again.",
            )
            return HTMLResponse(content=html, status_code=400)

        if not code or not state:
            html = _callback_html_error(
                "",
                "Missing code or state parameter. Please start the OAuth flow again.",
            )
            return HTMLResponse(content=html, status_code=400)

        connector_id, ok, err_msg = await anyio.to_thread.run_sync(
            lambda: oauth_callback(str(code), str(state))
        )
        if ok:
            # BB-11: auto-enable the capability so tools are registered on next boot.
            # Silently swallow errors (handler absent in tests; unknown cap id is non-fatal).
            try:
                control_plane.set_capability_enabled(connector_id, True)
            except Exception:
                pass
            html = _callback_html_ok(connector_id)
            return HTMLResponse(content=html, status_code=200)
        else:
            html = _callback_html_error(connector_id, err_msg)
            return HTMLResponse(content=html, status_code=400)

    @integrations_router.post("/{connector_id}/disconnect")
    async def post_disconnect(connector_id: str) -> Any:
        """Revoke and delete stored OAuth2 tokens for a connector.

        Returns ``{"connected": false, "connector_id": "<id>", ...status...}``.
        Returns HTTP 404 for unknown connectors.
        """
        import re

        from hachi.integrations.connector_registry import get_connector
        from hachi.integrations.oauth_flow import connector_status, oauth_disconnect

        if not re.match(r"^[a-z0-9_-]+$", connector_id):
            return _error_response(400, "invalid_connector_id", "Connector id is not valid")

        connector = get_connector(connector_id)
        if connector is None:
            return _error_response(404, "unknown_connector", f"Unknown connector: {connector_id!r}")

        result = await anyio.to_thread.run_sync(lambda: oauth_disconnect(connector_id))
        status_info = connector_status(connector_id)
        return {**result, **status_info}

    @integrations_router.post("/{connector_id}/credentials")
    async def post_credentials(connector_id: str, payload: dict[str, Any]) -> Any:
        """Store apikey credentials for a connector.

        Body: ``{"fields": {"<key>": "<value>", ...}}``

        Only keys declared in the connector's ``credential_fields`` are accepted.
        Returns the updated connector status dict (same shape as ``GET /integrations``
        entries) so the frontend can update the card immediately without re-fetching.

        Returns HTTP 400 for invalid connector id format.
        Returns HTTP 404 for unknown connectors.
        Returns HTTP 422 for undeclared field keys or empty values.
        """
        import re

        from hachi.integrations.connector_registry import get_connector
        from hachi.integrations.oauth_flow import (
            connector_status,
            store_apikey_credential,
        )

        if not re.match(r"^[a-z0-9_-]+$", connector_id):
            return _error_response(400, "invalid_connector_id", "Connector id is not valid")

        connector = get_connector(connector_id)
        if connector is None:
            return _error_response(404, "unknown_connector", f"Unknown connector: {connector_id!r}")

        if connector.auth_type != "apikey":
            return _error_response(
                422,
                "wrong_auth_type",
                f"Connector {connector_id!r} uses {connector.auth_type!r} auth, not apikey",
            )

        fields_payload = payload.get("fields")
        if not isinstance(fields_payload, dict):
            return _error_response(422, "invalid_payload", 'Body must be {"fields": {...}}')

        allowed_keys = {f["key"] for f in connector.credential_fields}
        for key, value in fields_payload.items():
            if key not in allowed_keys:
                return _error_response(
                    422,
                    "unknown_field",
                    f"Field key {key!r} is not declared for connector {connector_id!r}. "
                    f"Allowed keys: {sorted(allowed_keys)}",
                )
            if not isinstance(value, str) or not value.strip():
                return _error_response(
                    422,
                    "empty_value",
                    f"Value for field {key!r} must be a non-empty string",
                )

        def _store_all() -> None:
            for key, value in fields_payload.items():
                store_apikey_credential(connector_id, key, value.strip())
            # Issue 5 — Tavily-first: when the Tavily connector is configured via the UI,
            # also persist [search] provider = "tavily" to settings.toml so the search
            # provider activates at next boot without manual config edits.
            # Contract C-SEARCHFALLBACK: the search.provider field drives auto-registration
            # in registry.py (another lane); we only persist the TOML value here.
            if connector_id == "tavily":
                try:
                    from hachi.core.config_loader import (
                        load_effective_config,
                        write_global_config,
                    )

                    _cfg = load_effective_config()
                    if _cfg.search.provider != "tavily":
                        _new_search = _cfg.search.model_copy(update={"provider": "tavily"})
                        _new_cfg = _cfg.model_copy(update={"search": _new_search})
                        write_global_config(_new_cfg)
                        _log.info(
                            "post_credentials: persisted [search] provider='tavily'"
                            " to settings.toml"
                        )
                except Exception:
                    # Non-fatal: credential is stored, TOML update is best-effort.
                    _log.warning(
                        "post_credentials: failed to persist [search] provider for tavily",
                        exc_info=True,
                    )

        await anyio.to_thread.run_sync(_store_all)

        # BB-11: live-reload search tools when Tavily credentials are stored so the
        # web_search tool activates in the CURRENT session without a restart.
        if connector_id == "tavily":
            try:
                await anyio.to_thread.run_sync(control_plane.reload_search_tools)
            except Exception:
                pass  # non-fatal; tools activate on next boot regardless

        # Issue 5 — expose search fallback status for the UI (contract C-SEARCHFALLBACK).
        # ``fallback_active=True`` means no SearchProvider is registered and browse_web
        # (Playwright) is the current fallback.  The frontend uses this to show a
        # "web search unavailable" badge on the Tavily integration card.
        _fallback_active = True
        try:
            from hachi.gateway.shared_services import ProcessSharedServices

            _shared = ProcessSharedServices.instance()
            if _shared is not None:
                # A ProviderRegistry on the shared services has a registered search
                # provider when Tavily is active; absence means fallback is in use.
                _pr = getattr(_shared, "provider_registry", None)
                if _pr is not None and hasattr(_pr, "get_search"):
                    _fallback_active = _pr.get_search() is None
        except Exception:
            pass

        status_info = await anyio.to_thread.run_sync(lambda: connector_status(connector_id))
        return {
            "id": connector.id,
            "name": connector.name,
            "category": connector.category,
            "fallback_active": _fallback_active,
            **status_info,
        }

    @integrations_router.post("/{connector_id}/credentials/test")
    async def post_credentials_test(connector_id: str) -> Any:
        """Validate a connector's stored credentials with a bounded live probe.

        Issue 6b (contract C-CREDTEST). Returns ``{"ok": bool, "message": str}``.
        Never echoes the secret and never raises — a failed or timed-out probe yields
        ``ok: false`` with a short message. Connectors without a cheap probe report
        ``ok: true`` with a "stored; live test not available" message so the UI still
        confirms the credential was saved.
        """
        import re

        from hachi.integrations.connector_registry import get_connector

        if not re.match(r"^[a-z0-9_-]+$", connector_id):
            return _error_response(400, "invalid_connector_id", "Connector id is not valid")
        connector = get_connector(connector_id)
        if connector is None:
            return _error_response(404, "unknown_connector", f"Unknown connector: {connector_id!r}")

        def _resolve_secret(*names: str) -> str | None:
            # Vault first, then environment (canonical + UPPER) — never logged.
            try:
                from hachi.core.credential_vault import CredentialVault

                _v = CredentialVault()
                for n in names:
                    val = _v.get_token(n)
                    if val:
                        return str(val)
            except Exception:
                pass
            for n in names:
                val = os.environ.get(n) or os.environ.get(n.upper())
                if val:
                    return val
            return None

        def _probe() -> dict[str, Any]:
            try:
                if connector_id == "tavily":
                    # BB-14: the credential dialog stores under the namespaced key
                    # "apikey.tavily.tavily_api_key"; check it first, then the bare
                    # name and env. (Reading only "tavily_api_key" made Test
                    # Connection always report "No Tavily API key stored" even
                    # right after the key was saved.)
                    key = _resolve_secret("apikey.tavily.tavily_api_key", "tavily_api_key")
                    if not key:
                        return {"ok": False, "message": "No Tavily API key stored."}
                    import httpx

                    resp = httpx.post(
                        "https://api.tavily.com/search",
                        json={"api_key": key, "query": "ping", "max_results": 1},
                        timeout=8.0,
                    )
                    if resp.status_code == 200:
                        return {
                            "ok": True,
                            "message": "Tavily reachable — API key is valid.",
                        }
                    if resp.status_code in (401, 403):
                        return {"ok": False, "message": "Tavily rejected the API key."}
                    return {
                        "ok": False,
                        "message": f"Tavily returned HTTP {resp.status_code}.",
                    }
                if connector_id == "telegram":
                    token = _resolve_secret("telegram_bot_token")
                    if not token:
                        return {"ok": False, "message": "No Telegram bot token stored."}
                    import httpx

                    resp = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8.0)
                    if resp.status_code == 200 and resp.json().get("ok"):
                        name = resp.json().get("result", {}).get("username", "bot")
                        return {
                            "ok": True,
                            "message": f"Telegram bot @{name} reachable.",
                        }
                    return {"ok": False, "message": "Telegram rejected the bot token."}
                # Generic: confirm a credential is present; no live probe available.
                from hachi.integrations.oauth_flow import connector_status

                st = connector_status(connector_id)
                if st.get("status") in {"connected", "configured"}:
                    return {
                        "ok": True,
                        "message": "Credential stored; live test not available for this connector.",
                    }
                return {
                    "ok": False,
                    "message": "No credential configured for this connector.",
                }
            except Exception as exc:  # never leak secrets or stack traces to the client
                return {"ok": False, "message": f"Test failed: {type(exc).__name__}"}

        return await anyio.to_thread.run_sync(_probe)

    @integrations_router.delete("/{connector_id}/credentials")
    async def delete_credentials(connector_id: str) -> Any:
        """Clear all stored apikey credentials for a connector.

        Returns the updated connector status dict.

        Returns HTTP 400 for invalid connector id format.
        Returns HTTP 404 for unknown connectors.
        Returns HTTP 422 if the connector is not an apikey connector.
        """
        import re

        from hachi.integrations.connector_registry import get_connector
        from hachi.integrations.oauth_flow import (
            clear_apikey_credentials,
            connector_status,
        )

        if not re.match(r"^[a-z0-9_-]+$", connector_id):
            return _error_response(400, "invalid_connector_id", "Connector id is not valid")

        connector = get_connector(connector_id)
        if connector is None:
            return _error_response(404, "unknown_connector", f"Unknown connector: {connector_id!r}")

        if connector.auth_type != "apikey":
            return _error_response(
                422,
                "wrong_auth_type",
                f"Connector {connector_id!r} uses {connector.auth_type!r} auth, not apikey",
            )

        await anyio.to_thread.run_sync(lambda: clear_apikey_credentials(connector_id))

        status_info = await anyio.to_thread.run_sync(lambda: connector_status(connector_id))
        return {
            "id": connector.id,
            "name": connector.name,
            "category": connector.category,
            **status_info,
        }

    # ==========================================
    # Durable Runs routes (Initiative D)
    # ==========================================

    runs_router = APIRouter(prefix="/runs", tags=["runs"], dependencies=protected_dependencies)

    def _check_run_ownership(run_session_id: str, caller_hash: str | None) -> None:
        """H6: apply the same owner filter that ``/sessions`` already enforces.

        A durable run belongs to whichever session created it — reuse
        ``_check_session_ownership`` against ``run.session_id`` so a caller who
        doesn't own the run's session gets the identical 403 policy (NULL owner /
        no-auth mode = allowed, for backward compat with legacy/ownerless runs).
        """
        _check_session_ownership(run_session_id, caller_hash)

    @runs_router.get("", summary="List recent durable runs")
    async def get_runs(request: Request, limit: int = Query(default=100, ge=1, le=500)) -> Any:
        """Return recent durable runs across all sessions the caller owns, newest first."""
        from hachi.core.runtime.state import RunStateView
        from hachi.core.runtime.store import RunStateStore

        caller_hash = _require_auth(request)
        store = RunStateStore()
        runs = store.list_all(limit=limit)
        if caller_hash is not None:
            runs = [
                r
                for r in runs
                if (owner := control_plane.get_session_owner(r.session_id)) is None
                or secrets.compare_digest(owner, caller_hash)
            ]
        return {"runs": [RunStateView.from_run_state(r).model_dump() for r in runs]}

    @runs_router.get("/{run_id}", summary="Get a durable run by ID")
    async def get_run(run_id: str, request: Request) -> Any:
        """Return a single RunState by run_id.  404 if not found."""
        from hachi.core.runtime.state import RunStateView
        from hachi.core.runtime.store import RunStateStore

        store = RunStateStore()
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        _check_run_ownership(run.session_id, _require_auth(request))
        return RunStateView.from_run_state(run).model_dump()

    @runs_router.post("/{run_id}/wake", summary="Wake a WAITING run")
    async def post_run_wake(
        run_id: str, request: Request, body: dict[str, Any] | None = None
    ) -> Any:
        """Wake a WAITING run by resolving its wait condition.

        The run transitions WAITING→RUNNING and the resumed turn is started in the
        background via the job queue (durable, survives restart).

        Returns ``{"status": "waking", "run_id": "..."}`` immediately; the actual
        resume happens asynchronously.  If the run is not WAITING, returns 409.
        """
        from hachi.core.runtime.state import RunStatus
        from hachi.core.runtime.store import RunStateStore
        from hachi.core.runtime.waits import get_wait_registry

        body = body or {}
        result_payload: dict[str, Any] = body.get("result", {}) if isinstance(body, dict) else {}
        source: str = body.get("source", "webhook") if isinstance(body, dict) else "webhook"

        store = RunStateStore()
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        _check_run_ownership(run.session_id, _require_auth(request))
        if run.status != RunStatus.WAITING:
            raise HTTPException(
                status_code=409,
                detail=f"Run {run_id!r} is {run.status.value!r}, not 'waiting'",
            )

        # Resolve via WaitConditionRegistry (idempotent)
        registry = get_wait_registry()
        wake_key = run.wait.key if run.wait else run_id
        resolved_id = registry.resolve(wake_key, result_payload)

        if resolved_id is None and run.wait is not None:
            # Key not in registry (e.g., after restart) — fall through to direct dispatch
            pass

        # Dispatch resume_run as a durable job
        try:
            from hachi.jobs import Job, JobStatus

            job = Job(
                job_id="",
                name=f"resume_run.{run_id}",
                handler_name="resume_run",
                payload={"run_id": run_id, "result": result_payload, "source": source},
                status=JobStatus.PENDING,
            )
            control_plane.job_queue.enqueue(job)
        except Exception as exc:
            _log.warning("post_run_wake: failed to enqueue resume job for %r: %s", run_id, exc)
            # Fall back to inline attempt
            try:
                from hachi.core.runtime.resume import resume_run

                await anyio.to_thread.run_sync(lambda: resume_run(run_id, result_payload))
            except Exception as resume_exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Resume failed: {resume_exc}",
                ) from resume_exc

        return {"status": "waking", "run_id": run_id, "source": source}

    @runs_router.delete("/{run_id}", summary="Cancel a durable run")
    async def delete_run(run_id: str, request: Request) -> Any:
        """Cancel a durable run (sets status to CANCELLED and disarms its wait).

        Idempotent: cancelling an already-terminal run returns 200 with the
        current status.
        """
        from hachi.core.runtime.state import RunStatus
        from hachi.core.runtime.store import RunStateStore
        from hachi.core.runtime.waits import get_wait_registry
        from hachi.core.runtime_events import now_iso

        store = RunStateStore()
        run = store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        _check_run_ownership(run.session_id, _require_auth(request))

        terminal = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
        if run.status in terminal:
            return {
                "run_id": run_id,
                "status": run.status.value,
                "note": "already terminal",
            }

        get_wait_registry().disarm(run_id)
        run = run.model_copy(update={"status": RunStatus.CANCELLED, "updated_at": now_iso()})
        store.upsert(run)
        return {"run_id": run_id, "status": RunStatus.CANCELLED.value}

    # ------------------------------------------------------------------
    # Initiative E — File / Attachment Platform routes
    # POST   /files            — multipart upload; returns FileMeta JSON
    # GET    /files            — list all file metadata records
    # GET    /files/{id}       — get FileMeta for a single file
    # GET    /files/{id}/content — stream raw bytes (FileResponse)
    # ------------------------------------------------------------------
    files_router = APIRouter(prefix="/files", tags=["files"], dependencies=protected_dependencies)

    # Max upload size guard — read from [files] settings, fallback 50 MB.
    def _files_max_bytes() -> int:
        try:
            from hachi.core.config_loader import load_effective_config

            return int(load_effective_config().files.max_size_bytes)
        except Exception:
            return 50 * 1024 * 1024

    def _files_allowed_types() -> set[str]:
        try:
            from hachi.core.config_loader import load_effective_config

            return set(load_effective_config().files.allowed_types)
        except Exception:
            return set()

    def _get_file_pipeline() -> Any:
        """Build a FilePipeline from paths (one per request; lightweight)."""
        from hachi.core.files.store import (
            FileMetaStore,
            FilePipeline,
            LocalStorageProvider,
            NoOpScanner,
        )
        from hachi.core.paths import get_hachi_paths

        paths = get_hachi_paths()
        meta_store = FileMetaStore(paths.files_db)
        storage = LocalStorageProvider(paths.blobs_dir, _files_max_bytes())
        return FilePipeline(
            meta_store=meta_store,
            storage=storage,
            scanner=NoOpScanner(),
            allowed_types=_files_allowed_types(),
            max_size_bytes=_files_max_bytes(),
        )

    def _get_file_meta_store() -> Any:
        from hachi.core.files.store import FileMetaStore
        from hachi.core.paths import get_hachi_paths

        return FileMetaStore(get_hachi_paths().files_db)

    def _get_file_storage() -> Any:
        from hachi.core.files.store import LocalStorageProvider
        from hachi.core.paths import get_hachi_paths

        return LocalStorageProvider(get_hachi_paths().blobs_dir)

    def _reject_path_traversal(file_id: str) -> None:
        """Raise 400 if *file_id* contains path traversal sequences."""
        if "/" in file_id or "\\" in file_id or ".." in file_id or not file_id:
            raise HTTPException(status_code=400, detail="Invalid file_id")

    @files_router.post("", summary="Upload a file attachment")
    async def upload_file(
        file: UploadFile = File(...),  # noqa: B008
        media_type_override: str | None = Query(default=None, alias="media_type"),
    ) -> Any:
        """Ingest a multipart file upload into the managed attachment store.

        Validates type and size BEFORE storage.  Returns :class:`FileMeta` JSON.
        A ``file.uploaded`` event is emitted after storage so the reactive
        extract-and-index pipeline fires asynchronously via the JobRegistry.
        """
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Infer MIME type: explicit override → content_type header → extension.
        effective_type = media_type_override or file.content_type or "application/octet-stream"

        # Size pre-check from Content-Length header (not authoritative but fast).
        max_bytes = _files_max_bytes()

        import io as _io

        raw = await file.read()
        if len(raw) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size ({max_bytes} bytes)",
            )

        try:
            pipeline = _get_file_pipeline()
            meta = pipeline.ingest(
                name=file.filename,
                media_type=effective_type,
                data=_io.BytesIO(raw),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # Trigger extraction synchronously as a best-effort inline step when
        # the durable-handler path is not configured (e.g. during tests).
        # In production (durable_handlers=true) the EventBus subscription does this.
        _trigger_extraction_inline(meta.file_id, meta.name, meta.media_type)

        return meta.model_dump()

    def _trigger_extraction_inline(file_id: str, name: str, media_type: str) -> None:
        """Best-effort inline extraction when the durable path is unavailable."""
        try:
            from hachi.core.runtime.job_handlers import handle_auto_extract

            handle_auto_extract(
                event_name="file.uploaded",
                event_payload={
                    "file_id": file_id,
                    "name": name,
                    "media_type": media_type,
                },
            )
        except Exception:
            pass  # Non-fatal; file stays at 'stored' until a job worker picks it up.

    @files_router.get("", summary="List all file attachments")
    async def list_files() -> Any:
        """Return all stored file metadata records, newest first."""
        store = _get_file_meta_store()
        return [m.model_dump() for m in store.list_all()]

    @files_router.get("/{file_id}", summary="Get file metadata")
    async def get_file_meta(file_id: str) -> Any:
        """Return the :class:`FileMeta` record for a single *file_id*."""
        _reject_path_traversal(file_id)
        store = _get_file_meta_store()
        meta = store.get(file_id)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"File {file_id!r} not found")
        return meta.model_dump()

    @files_router.get("/{file_id}/content", summary="Stream raw file content")
    async def get_file_content(file_id: str) -> Any:
        """Stream the raw bytes of the stored blob for *file_id*.

        Quarantined files are NOT served (404).
        """
        _reject_path_traversal(file_id)
        store = _get_file_meta_store()
        meta = store.get(file_id)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"File {file_id!r} not found")
        if meta.status == "quarantined":
            raise HTTPException(status_code=404, detail="File is not available")

        from hachi.core.paths import get_hachi_paths

        blob_path = get_hachi_paths().blobs_dir / file_id
        if not blob_path.exists():
            raise HTTPException(status_code=404, detail="Blob not found on disk")

        return FileResponse(
            path=str(blob_path),
            media_type=meta.media_type,
            filename=meta.name,
        )

    # ---- Voice router (STT/TTS provider endpoints) ----
    from hachi.gateway.voice_endpoints import (
        VoiceConfigError,
    )
    from hachi.gateway.voice_endpoints import (
        set_voice_config as _voice_set_config,
    )
    from hachi.gateway.voice_endpoints import (
        speak_stream as _voice_speak_stream,
    )
    from hachi.gateway.voice_endpoints import (
        transcribe as _voice_transcribe,
    )
    from hachi.gateway.voice_endpoints import (
        voice_config as _voice_config,
    )

    voice_router = APIRouter(prefix="/voice", tags=["voice"], dependencies=protected_dependencies)

    _MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB hard ceiling for audio uploads

    @voice_router.post("/transcribe", summary="Transcribe audio via STT provider")
    async def route_voice_transcribe(audio: UploadFile = File(...)) -> Any:  # noqa: B008
        """Transcribe a multipart audio upload to text via the configured STT backend."""
        if audio.filename is None:
            raise HTTPException(status_code=400, detail="Filename is required")
        # Bounded read — prevents memory exhaustion from oversized uploads.
        raw = await audio.read(_MAX_AUDIO_BYTES + 1)
        if len(raw) > _MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio exceeds 25 MB limit")
        content_type = audio.content_type or "audio/webm"
        try:
            result = await anyio.to_thread.run_sync(
                lambda: _voice_transcribe(raw, filename=audio.filename, content_type=content_type)
            )
        except VoiceConfigError as exc:
            return _error_response(503, "voice_not_configured", str(exc))
        except Exception as exc:  # noqa: BLE001
            _log.warning("STT transcription failed: %s", exc)
            return _error_response(
                500,
                "transcription_error",
                "Transcription failed, check voice provider configuration",
            )
        return result

    @voice_router.post("/speak", summary="Synthesize text via TTS provider")
    async def route_voice_speak(body: VoiceSpeakBody) -> Any:
        """Synthesize text to audio via the configured TTS backend.

        Uses :func:`~hachi.gateway.voice_endpoints.speak_stream` to pipe bytes
        through a generator so the first bytes reach the client before the full
        clip is produced (FIX P1).  Falls back to the buffered path automatically
        for providers that don't support streaming.
        """
        try:
            chunk_iter, media_type = await anyio.to_thread.run_sync(
                lambda: _voice_speak_stream(
                    body.text,
                    voice=body.voice,
                    model=body.model,
                    fmt=body.format,
                    provider=body.provider,
                )
            )
        except VoiceConfigError as exc:
            return _error_response(503, "voice_not_configured", str(exc))
        except Exception as exc:  # noqa: BLE001
            _log.warning("TTS synthesis failed: %s", exc)
            return _error_response(
                500,
                "synthesis_error",
                "Synthesis failed, check voice provider configuration",
            )
        return StreamingResponse(
            chunk_iter,
            media_type=media_type,
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    @voice_router.get("/config", summary="Get voice configuration")
    async def route_voice_config() -> Any:
        """Return the current voice provider config summary for the UI."""
        return await anyio.to_thread.run_sync(_voice_config)

    @voice_router.put("/config", summary="Update voice configuration")
    async def route_voice_set_config(patch: dict[str, Any]) -> Any:
        """Persist voice config fields and return the updated summary."""
        try:
            return await anyio.to_thread.run_sync(lambda: _voice_set_config(patch))
        except Exception as exc:  # noqa: BLE001
            return _error_response(500, "config_write_error", str(exc))

    # ==========================================
    # Eval loop — interaction read/rating (E1)
    # ==========================================

    interactions_router = APIRouter(
        prefix="/interactions",
        tags=["interactions"],
        dependencies=protected_dependencies,
    )

    @interactions_router.get("", response_model=InteractionListResponse)
    async def get_interactions(
        request: Request,
        session_id: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> InteractionListResponse:
        """Return interaction_log rows newest-first, optionally scoped to one session.

        Ownership rules (mirrors ``list_sessions``):
        - If ``session_id`` is supplied: ownership-check that session before querying.
        - If not supplied: return rows across all sessions owned by the caller
          (legacy NULL-owner sessions included for back-compat); no-auth returns all.

        Args:
            session_id: Optional session filter.
            limit: Maximum rows to return (1–500; default 100).
        """
        caller_hash = _require_auth(request)
        store = _resolve_session_store()
        if store is None:
            raise HTTPException(status_code=503, detail="session store unavailable")

        if session_id is not None:
            # Ownership-check before querying to avoid leaking row existence.
            _check_session_ownership(session_id, caller_hash)
            rows = store.get_interactions(session_id=session_id, limit=limit)
        else:
            # Pull all rows then filter to owned sessions.
            rows = store.get_interactions(session_id=None, limit=limit)
            if caller_hash is not None:

                def _owned_session(sid: str) -> bool:
                    owner = control_plane.get_session_owner(sid)
                    return owner is None or secrets.compare_digest(owner, caller_hash)

                rows = [r for r in rows if _owned_session(r.get("session_id") or "")]

        records = [InteractionRecord(**row) for row in rows]
        return InteractionListResponse(interactions=records)

    @interactions_router.put("/{interaction_id}/rating", response_model=RatingResponse)
    async def put_interaction_rating(
        interaction_id: str,
        payload: RatingRequest,
        request: Request,
    ) -> RatingResponse:
        """Set the thumbs-up / thumbs-down rating (and optional notes) for a turn.

        Ownership check: looks up the row's ``session_id`` first, then verifies the
        caller owns that session before allowing the write.

        Returns 404 if ``interaction_id`` does not exist.
        """
        caller_hash = _require_auth(request)
        store = _resolve_session_store()
        if store is None:
            raise HTTPException(status_code=503, detail="session store unavailable")

        # Look up the row to discover its session_id for the ownership check.
        existing = store.get_interactions(session_id=None, limit=10_000)
        row = next((r for r in existing if r.get("id") == interaction_id), None)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Interaction {interaction_id!r} not found")

        # Ownership-check the owning session before mutating.
        row_session_id: str = row.get("session_id") or ""
        if row_session_id:
            _check_session_ownership(row_session_id, caller_hash)

        updated = store.set_interaction_rating(
            interaction_id, rating=payload.rating, notes=payload.notes
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Interaction {interaction_id!r} not found")
        return RatingResponse(ok=True)

    app.include_router(integrations_router)
    app.include_router(integrations_callback_router)
    app.include_router(system)
    app.include_router(sessions)
    app.include_router(runtime_ops)
    app.include_router(config)
    app.include_router(setup)
    app.include_router(openai_compat)
    app.include_router(channels_router)
    app.include_router(approvals_router)
    app.include_router(skills_router)
    app.include_router(memory_router)
    app.include_router(og_router)
    app.include_router(authoring_router)
    app.include_router(spend_router)
    app.include_router(runs_router)
    app.include_router(files_router)
    app.include_router(voice_router)
    app.include_router(interactions_router)

    if _auth_enabled:
        # Inject the bearer security scheme into the exported OpenAPI spec so
        # frontend clients and tools like Swagger UI know auth is required.
        def _custom_openapi() -> dict[str, Any]:
            if app.openapi_schema:
                return app.openapi_schema
            from fastapi.openapi.utils import get_openapi

            schema = get_openapi(
                title=app.title,
                version=app.version,
                routes=app.routes,
            )
            schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
                "type": "http",
                "scheme": "bearer",
            }
            for path_item in schema.get("paths", {}).values():
                for operation in path_item.values():
                    if not isinstance(operation, dict):
                        continue
                    operation.setdefault("security", [{"BearerAuth": []}])
                    operation.setdefault("responses", {}).setdefault(
                        "401", {"description": "Missing or invalid bearer token"}
                    )
            app.openapi_schema = schema
            return schema

        app.openapi = _custom_openapi  # type: ignore[method-assign]

    # Mount the pre-built frontend as a static SPA AFTER all API routes so that
    # API paths always win.
    #
    # P-33: `html=True` alone does NOT give client-side routing a history
    # fallback — it only resolves directory-like paths. Every SPA route
    # (/conversation, /memory, …) therefore returned 404 on refresh or direct
    # link, because there is no matching file on disk. `_SPAStaticFiles` falls
    # back to index.html for unknown non-API paths, which is what the router
    # expects. The comment here previously claimed `html=True` already did this;
    # it did not, and the test that "covered" it only asserted the string
    # "Hachi" appeared — which the JSON descriptor at "/" also satisfied.
    if frontend_dist is not None:
        _dist = Path(frontend_dist)
        if _dist.is_dir():
            app.mount("/", _SPAStaticFiles(directory=str(_dist), html=True), name="frontend")
            _log.info("Frontend mounted from %s", _dist)
        else:
            _log.warning("frontend_dist '%s' is not a directory — skipping static mount", _dist)

    return app
