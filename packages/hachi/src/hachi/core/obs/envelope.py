"""TelemetryEnvelope — canonical schema unifying backend and frontend telemetry.

The envelope is a *pure view* produced at export boundaries (the sink, the
``/telemetry`` ingest route, and — in Phase 6 — the frontend SDK).  It is
not the bus wire format; ``RuntimeEvent`` stays the bus wire format.

Design constraints
------------------
- ``RuntimeEvent.payload.trace_id`` is the legacy field name for what is now
  ``turn_id`` — mapped here for backward compatibility (ADR-0005).
- ``otel_trace_id`` / ``otel_span_id`` come from the active OTel span context
  when present, and are distinct from ``turn_id``.
- Exporter-specific methods (e.g. ``to_otlp_log_record()``) must NOT live on
  this core dataclass — put them in adapter modules in ``gateway/``.
- The PII allowlist is enforced by :func:`from_runtime_event` via
  :data:`~hachi.core.obs.spans.DENY_METADATA_KEYS` /
  :func:`~hachi.core.obs.spans.is_denied_metadata_key`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hachi.core.obs.spans import is_denied_metadata_key

_SCHEMA_VERSION = "1"

# Well-known payload keys that map to top-level envelope fields.
_KNOWN_SAFE_FIELDS: dict[str, str] = {
    "turn_id": "turn_id",
    "trace_id": "turn_id",  # legacy alias — maps to turn_id, NOT otel_trace_id
    "session_id": "session_id",
    "workspace_id": "workspace_id",
    "agent_id": "agent_id",
    "principal": "principal",
    "surface": "surface",
    "severity": "severity",
    "component": "component",
    "duration_ms": "duration_ms",
    "model": "model",
    "tool": "tool",
    "name": "tool",  # tool name often stored as payload.name
    "cost_usd": "cost_usd",
    "retry": "retry",
    "stacktrace": "stacktrace",
}

# Token sub-fields that merge into envelope.tokens dict.
_TOKEN_FIELDS: frozenset[str] = frozenset(
    {"input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"}
)


@dataclass
class TelemetryEnvelope:
    """Canonical telemetry envelope for a single event or span boundary.

    All fields are optional except ``timestamp``, ``schema_version``, and
    ``event_type`` (the event name).  Unknown-but-safe payload fields land in
    ``metadata``; denied fields are silently dropped.

    Attributes:
        timestamp:        ISO-8601 event timestamp.
        schema_version:   ``"1"`` for this generation of the schema.
        event_type:       RuntimeEvent name (e.g. ``"tool.call.started"``).
        turn_id:          Hachi turn correlation id (== legacy ``trace_id``).
        otel_trace_id:    Exported OTel trace id (W3C transport; differs from turn_id).
        otel_span_id:     Exported OTel span id.
        session_id:       Session this event belongs to.
        workspace_id:     Workspace (if multi-workspace; currently single-tenant).
        agent_id:         Agent id (for sub-agent events).
        principal:        SHA-256 token hash (first 16 hex chars).
        surface:          Request origin: cli|tui|web|webhook|schedule.
        severity:         Log-level string (INFO/WARNING/ERROR).
        component:        Emitting component (e.g. ``"loop"``, ``"orchestrator"``).
        duration_ms:      Elapsed wall-clock time in milliseconds.
        model:            LLM model id.
        tool:             Tool name.
        cost_usd:         Cost for this event in USD.
        tokens:           Token breakdown dict (input/output/cache_read/cache_creation).
        retry:            Retry count (for provider errors).
        stacktrace:       Exception stacktrace string (for error events).
        metadata:         Overflow bucket for safe unknown fields.
    """

    timestamp: str
    schema_version: str
    event_type: str
    turn_id: str | None = None
    otel_trace_id: str | None = None
    otel_span_id: str | None = None
    session_id: str | None = None
    workspace_id: str | None = None
    agent_id: str | None = None
    principal: str | None = None
    surface: str | None = None
    severity: str | None = None
    component: str | None = None
    duration_ms: float | None = None
    model: str | None = None
    tool: str | None = None
    cost_usd: float | None = None
    tokens: dict[str, int] | None = None
    retry: int | None = None
    stacktrace: str | None = None
    metadata: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the envelope to a plain dict, omitting None values."""
        out: dict[str, Any] = {
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "event_type": self.event_type,
        }
        for f in (
            "turn_id",
            "otel_trace_id",
            "otel_span_id",
            "session_id",
            "workspace_id",
            "agent_id",
            "principal",
            "surface",
            "severity",
            "component",
            "duration_ms",
            "model",
            "tool",
            "cost_usd",
            "tokens",
            "retry",
            "stacktrace",
            "metadata",
        ):
            v = getattr(self, f)
            if v is not None:
                out[f] = v
        return out


def from_runtime_event(
    event: Any,
    ctx: Any = None,
    current_span: Any = None,
) -> TelemetryEnvelope:
    """Build a :class:`TelemetryEnvelope` from a :class:`~hachi.core.runtime_events.RuntimeEvent`.

    PII enforcement: keys in
    :data:`~hachi.core.obs.spans.DENY_METADATA_KEYS` or matching
    :func:`~hachi.core.obs.spans.is_denied_metadata_key` are silently dropped —
    they never appear in top-level fields or ``metadata``.

    Args:
        event:        The ``RuntimeEvent`` to convert.
        ctx:          Optional active ``TraceContext`` (for principal / surface).
        current_span: Optional active OTel span (for ``otel_trace_id`` /
                      ``otel_span_id``).  Avoids importing OTel in the hot path.

    Returns:
        A fully populated :class:`TelemetryEnvelope`.
    """
    payload: dict[str, Any] = getattr(event, "payload", {}) or {}

    env = TelemetryEnvelope(
        timestamp=getattr(event, "timestamp", ""),
        schema_version=_SCHEMA_VERSION,
        event_type=getattr(event, "name", ""),
    )

    # --- Map well-known safe fields ---
    for src_key, dst_attr in _KNOWN_SAFE_FIELDS.items():
        val = payload.get(src_key)
        if val is not None and not is_denied_metadata_key(src_key):
            # Only set if the envelope field is still None (first writer wins;
            # turn_id wins over legacy trace_id if both are present).
            if getattr(env, dst_attr) is None:
                _safe_setattr(env, dst_attr, val)

    # --- Token sub-dict ---
    token_dict: dict[str, int] = {}
    for tf in _TOKEN_FIELDS:
        v = payload.get(tf)
        if isinstance(v, int):
            token_dict[tf] = v
    if token_dict:
        env.tokens = token_dict

    # --- Inject from TraceContext if provided ---
    if ctx is not None:
        if env.session_id is None:
            env = _replace(env, session_id=getattr(ctx, "session_id", None))
        if env.principal is None:
            env = _replace(env, principal=getattr(ctx, "principal", None))
        if env.surface is None:
            env = _replace(env, surface=getattr(ctx, "surface", None))

    # --- Inject OTel ids from active span if provided ---
    if current_span is not None:
        try:
            span_ctx = current_span.get_span_context()
            if span_ctx is not None and span_ctx.is_valid:
                env = _replace(env, otel_trace_id=format(span_ctx.trace_id, "032x"))
                env = _replace(env, otel_span_id=format(span_ctx.span_id, "016x"))
        except Exception:
            pass

    # --- Unknown safe fields → metadata ---
    known_keys = set(_KNOWN_SAFE_FIELDS) | _TOKEN_FIELDS
    metadata: dict[str, Any] = {}
    for k, v in payload.items():
        if k in known_keys:
            continue
        if is_denied_metadata_key(k):
            continue
        if v is None:
            continue
        # Only forward scalar or simple types to avoid deep nesting in metadata.
        if isinstance(v, str | bool | int | float):
            metadata[k] = v
    if metadata:
        env = _replace(env, metadata=metadata)

    return env


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_setattr(env: TelemetryEnvelope, attr: str, value: Any) -> None:
    """Set a field on *env* if *value* is an appropriate scalar type."""
    if not isinstance(value, str | bool | int | float):
        return
    object.__setattr__(env, attr, value)


def _replace(env: TelemetryEnvelope, **kwargs: Any) -> TelemetryEnvelope:
    """Return a copy of *env* with the given fields replaced."""
    import dataclasses

    return dataclasses.replace(env, **kwargs)
