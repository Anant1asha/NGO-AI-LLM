"""Span-name constants, attribute-key constants, and the PII allowlist.

Single source of truth for all observability identifiers used by the loop,
sink, envelope, and middleware.  Importing this module from ``core/`` is
safe; it has no runtime-heavy imports.

Usage
-----
.. code-block:: python

    from hachi.core.obs.spans import SPAN_AGENT_TURN, ALLOWED_SPAN_ATTRS
    with tracing.span(SPAN_AGENT_TURN, **{ATTR_TURN_ID: turn_id}):
        ...
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Span names
# ---------------------------------------------------------------------------

SPAN_HTTP_REQUEST: str = "http.request"
SPAN_AGENT_TURN: str = "agent.turn"
SPAN_PROMPT_BUILD: str = "prompt.build"
SPAN_MEMORY_RECALL: str = "memory.recall"
SPAN_TOOL_CALL: str = "tool.call"
SPAN_LLM_GENERATE: str = "llm.generate"
SPAN_PERMISSION_CHECK: str = "permission.check"
SPAN_SUBAGENT: str = "agent.delegate"
SPAN_RESPONSE_VALIDATE: str = "response.validate"

# ---------------------------------------------------------------------------
# Attribute key constants
# ---------------------------------------------------------------------------

ATTR_TURN_ID: str = "hachi.turn_id"
ATTR_SESSION_ID: str = "hachi.session_id"
ATTR_TRACE_ID: str = "hachi.trace_id"
ATTR_OTEL_TRACE_ID: str = "hachi.otel_trace_id"
ATTR_SURFACE: str = "hachi.surface"
ATTR_PRINCIPAL: str = "hachi.principal"
ATTR_TOOL: str = "tool"
ATTR_TOOL_NAME: str = "tool_name"
ATTR_MODEL: str = "model"
ATTR_ROLE: str = "role"
ATTR_STATUS: str = "status"
ATTR_DURATION: str = "duration"
ATTR_ITERATIONS: str = "iterations"
ATTR_ERROR: str = "error"
ATTR_HTTP_METHOD: str = "http.method"
ATTR_HTTP_ROUTE: str = "http.route"
ATTR_HTTP_STATUS: str = "http.status_code"

# ---------------------------------------------------------------------------
# PII allowlist — only these keys may appear as span / envelope attributes.
# The sink and from_runtime_event filter all attributes through this set.
# ---------------------------------------------------------------------------

ALLOWED_SPAN_ATTRS: frozenset[str] = frozenset(
    {
        # Hachi correlation ids
        ATTR_TURN_ID,
        ATTR_SESSION_ID,
        ATTR_TRACE_ID,
        ATTR_OTEL_TRACE_ID,
        ATTR_SURFACE,
        ATTR_PRINCIPAL,
        # Tool / model / routing
        ATTR_TOOL,
        ATTR_TOOL_NAME,
        ATTR_MODEL,
        ATTR_ROLE,
        ATTR_STATUS,
        ATTR_DURATION,
        ATTR_ITERATIONS,
        ATTR_ERROR,
        # HTTP
        ATTR_HTTP_METHOD,
        ATTR_HTTP_ROUTE,
        ATTR_HTTP_STATUS,
        # Metric labels (safe to repeat as span attrs)
        "surface",
        "capability",
        "kind",
        "provider",
        "feature",
        # Well-known OTel semconv
        "service.name",
        "code.filepath",
        "code.lineno",
        # Numeric token / cost fields (values are numbers, not text)
        "hachi.tokens.input",
        "hachi.tokens.output",
        "hachi.tokens.cache_read",
        "hachi.tokens.cache_creation",
        "hachi.cost.usd",
        # Backward-compat legacy keys the sink already forwards
        "hachi.trace_id",
        "hachi.session_id",
        "hachi.turn_id",
    }
)

# Keys that must NEVER appear as span attributes, envelope fields, or envelope
# metadata — even if present in a RuntimeEvent payload.  The list covers prompt
# bodies, retrieved memory bodies, raw credentials, and generic *_body/*_content
# patterns emitted by orchestrator.py (e.g. prompt_preview at line ~1605).
DENY_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "prompt_preview",
        "prompt",
        "user_input",
        "messages",
        "input",
        "authorization",
        "bearer",
        "token",
        "api_key",
        "secret",
        "password",
        "credential",
        "response_body",
        "request_body",
        "memory_body",
        "retrieved_content",
        "memory_content",
        "document_content",
        "chunk_content",
    }
)

# Pattern suffixes that trigger denial regardless of the full key name.
# Applied in from_runtime_event when iterating unknown payload fields.
_DENY_SUFFIXES: tuple[str, ...] = ("_body", "_content", "_preview", "_token", "_secret")
_DENY_PREFIXES: tuple[str, ...] = ("raw_", "plain_")


def is_denied_metadata_key(key: str) -> bool:
    """Return True if *key* must never appear in exported telemetry.

    Args:
        key: Payload key to check.

    Returns:
        True when the key matches the deny list or deny-suffix patterns.
    """
    k = key.lower()
    if k in DENY_METADATA_KEYS:
        return True
    if k in ("authorization", "bearer", "token", "secret", "password", "credential"):
        return True
    for suffix in _DENY_SUFFIXES:
        if k.endswith(suffix):
            return True
    for prefix in _DENY_PREFIXES:
        if k.startswith(prefix):
            return True
    return False
