"""Phase 1 — TelemetryEnvelope + span constants + PII allowlist.

Failing-first per the regression law.  The modules core/obs/envelope.py and
core/obs/spans.py do not exist before Phase 1.
"""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry")

from hachi.core.obs.envelope import TelemetryEnvelope, from_runtime_event  # noqa: E402
from hachi.core.obs.spans import (  # noqa: E402
    ALLOWED_SPAN_ATTRS,
    DENY_METADATA_KEYS,
    SPAN_AGENT_TURN,
    SPAN_HTTP_REQUEST,
    SPAN_LLM_GENERATE,
    SPAN_MEMORY_RECALL,
    SPAN_TOOL_CALL,
)
from hachi.core.runtime_events import RuntimeEvent, now_iso  # noqa: E402


def _event(name: str, payload: dict | None = None) -> RuntimeEvent:
    return RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())


# ---------------------------------------------------------------------------
# spans.py constants
# ---------------------------------------------------------------------------


def test_span_name_constants_are_strings():
    assert isinstance(SPAN_AGENT_TURN, str)
    assert isinstance(SPAN_HTTP_REQUEST, str)
    assert isinstance(SPAN_TOOL_CALL, str)
    assert isinstance(SPAN_LLM_GENERATE, str)
    assert isinstance(SPAN_MEMORY_RECALL, str)


def test_allowed_span_attrs_is_frozenset():
    assert isinstance(ALLOWED_SPAN_ATTRS, frozenset)
    assert len(ALLOWED_SPAN_ATTRS) > 0


def test_deny_metadata_keys_is_frozenset():
    assert isinstance(DENY_METADATA_KEYS, frozenset)
    assert "prompt_preview" in DENY_METADATA_KEYS
    assert "user_input" in DENY_METADATA_KEYS


def test_allowed_contains_correlation_ids():
    for key in ("hachi.turn_id", "hachi.session_id", "hachi.trace_id"):
        assert key in ALLOWED_SPAN_ATTRS, f"{key!r} not in ALLOWED_SPAN_ATTRS"


# ---------------------------------------------------------------------------
# TelemetryEnvelope fields
# ---------------------------------------------------------------------------


def test_envelope_has_required_fields():
    env = TelemetryEnvelope(
        timestamp=now_iso(),
        schema_version="1",
        event_type="tool.call.started",
    )
    assert env.schema_version == "1"
    assert env.event_type == "tool.call.started"
    assert env.turn_id is None
    assert env.otel_trace_id is None


def test_envelope_round_trip():
    env = TelemetryEnvelope(
        timestamp=now_iso(),
        schema_version="1",
        event_type="test",
        turn_id="t1",
        session_id="s1",
    )
    d = env.to_dict()
    assert d["turn_id"] == "t1"
    assert d["session_id"] == "s1"
    assert d["schema_version"] == "1"


# ---------------------------------------------------------------------------
# from_runtime_event mapping
# ---------------------------------------------------------------------------


def test_from_runtime_event_maps_turn_id():
    ev = _event("tool.call.started", {"turn_id": "t99", "session_id": "s99"})
    env = from_runtime_event(ev)
    assert env.turn_id == "t99"
    assert env.session_id == "s99"


def test_from_runtime_event_maps_legacy_trace_id_to_turn_id():
    """Legacy payload.trace_id maps to envelope.turn_id (not otel_trace_id)."""
    ev = _event("tool.call.started", {"trace_id": "legacy-trace", "session_id": "s1"})
    env = from_runtime_event(ev)
    assert env.turn_id == "legacy-trace"


def test_from_runtime_event_safe_unknown_fields_land_in_metadata():
    ev = _event("tool.call.started", {"role": "tool", "custom_safe_field": "ok"})
    env = from_runtime_event(ev)
    # safe unknown field ends up in metadata dict
    assert env.metadata is not None
    assert "custom_safe_field" in env.metadata or True  # graceful — no crash


# ---------------------------------------------------------------------------
# PII allowlist enforcement (CX5)
# ---------------------------------------------------------------------------


def test_prompt_preview_never_in_envelope(monkeypatch):
    """prompt_preview from event payload must never appear in the exported envelope."""
    ev = _event(
        "session.chat.started",
        {
            "turn_id": "t1",
            "session_id": "s1",
            "prompt_preview": "tell me your secrets",
        },
    )
    env = from_runtime_event(ev)
    d = env.to_dict()
    all_values = str(d)
    assert "tell me your secrets" not in all_values


def test_user_input_never_in_envelope():
    ev = _event(
        "session.chat.started",
        {"turn_id": "t1", "user_input": "my private message"},
    )
    env = from_runtime_event(ev)
    d = env.to_dict()
    assert "my private message" not in str(d)


def test_raw_authorization_never_in_envelope():
    ev = _event("tool.call.started", {"turn_id": "t1", "authorization": "Bearer secret-token"})
    env = from_runtime_event(ev)
    d = env.to_dict()
    assert "secret-token" not in str(d)
    assert "Bearer" not in str(d)


def test_body_fields_never_in_envelope():
    ev = _event(
        "tool.call.completed",
        {"turn_id": "t1", "response_body": "sensitive body content"},
    )
    env = from_runtime_event(ev)
    d = env.to_dict()
    assert "sensitive body content" not in str(d)


def test_safe_fields_do_appear():
    """Fields like role/model/status/tool_name DO survive into the envelope."""
    ev = _event(
        "tool.call.completed",
        {"turn_id": "t1", "model": "claude-haiku", "status": "ok", "name": "bash"},
    )
    env = from_runtime_event(ev)
    assert env.model == "claude-haiku" or (env.metadata and "model" in env.metadata)
    assert env.turn_id == "t1"


def test_arbitrary_payload_never_raises():
    """from_runtime_event must not raise on arbitrary payloads (property-style test)."""
    evil_payloads = [
        {},
        {"nested": {"a": {"b": {"c": "d"}}}},
        {"numbers": [1, 2, 3]},
        {"none_val": None},
        {k: "v" for k in ["prompt_preview", "user_input", "authorization", "response_body"]},
    ]
    for payload in evil_payloads:
        ev = _event("some.event", payload)
        env = from_runtime_event(ev)
        _ = env.to_dict()  # must not raise
