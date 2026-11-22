"""Observability event sink — stamps attributes onto the active OTel span.

Phase 2 contract (see docs/DECISIONS.md):
The sink is an **attribute stamper**, not a span emitter.  It attaches
correlation ids and well-known payload fields onto the *currently active* span
as attributes and span-events.  It never opens or closes spans itself.

Rationale: the waterfall is owned by ``with span(...)`` wrappers at the work
seams (``orchestrator._chat_impl``, ``loop.py`` tool/llm spans, Phase 4
middleware).  Marker spans emitted by the sink created zero-duration spans that
double-counted with the real ``agent.turn`` root — removed in Phase 2.

When ``events.bus_funnel=false``, direct spans still give the waterfall; only
this sink-based attribute enrichment is unavailable (boot logs a warning).

The sink must NOT re-enter ``bus.publish()`` — it only records span attributes.

Secrets: the event taxonomy's redaction already strips secrets from event
payloads before they reach this sink; the explicit allowlist in
:mod:`hachi.core.obs.spans` provides a second defence for the generic
metadata path.
"""

from __future__ import annotations

import logging
from typing import Any

from hachi.core.obs.spans import ALLOWED_SPAN_ATTRS
from hachi.core.runtime_events import RuntimeEvent

logger = logging.getLogger(__name__)

# Events that are meaningful to stamp onto the active span.
# All 9 original events are kept; the difference is that we now stamp
# *onto the active span* instead of opening a throwaway marker span.
_SPAN_EVENTS: frozenset[str] = frozenset(
    {
        "tool.call.started",
        "tool.call.completed",
        "llm.generate",
        "session.chat.started",
        "session.chat.completed",
        "subagent.started",
        "subagent.completed",
        "provider.failover",
        "model.routed",
    }
)

# Span-event name override: maps bus event names to the span-event name stamped
# onto the active span.  Same vocabulary as the old _SPAN_NAMES mapping.
_SPAN_EVENT_NAMES: dict[str, str] = {
    "session.chat.started": "agent.turn.start",
    "session.chat.completed": "agent.turn.end",
}


class ObservabilitySink:
    """Subscribes to the EventBus and stamps attributes onto the active OTel span.

    Designed to be registered once at boot:

    .. code-block:: python

        sink = ObservabilitySink()
        bus.subscribe("*", sink.handle, mode="sync", name="observability")

    The sink is safe to create even when OTel is not configured; in that case
    :meth:`handle` is a very cheap no-op (one function-call + ``is_active()``
    check).

    Phase 2 design: spans are created where work happens (``with span(...)``
    wrappers); the sink only enriches them.  When no span is active the sink
    is a no-op for the attribute-stamping step (``add_span_attributes`` is
    already a no-op on the invalid/norecording span).
    """

    def handle(self, event: RuntimeEvent) -> None:
        """Handle a single RuntimeEvent from the bus.

        Stamps attributes onto the currently active span.  Never blocks.
        Exceptions are caught and logged — never propagated into the bus.

        Args:
            event: The runtime event to mirror.
        """
        try:
            self._handle_safe(event)
        except Exception:  # pragma: no cover — defensive catch
            logger.debug(
                "ObservabilitySink: error processing event %r — skipped",
                event.name,
                exc_info=True,
            )

    def _handle_safe(self, event: RuntimeEvent) -> None:
        from hachi.core import tracing

        if not tracing.is_active():
            return

        if event.name not in _SPAN_EVENTS:
            return

        span_event_name = _SPAN_EVENT_NAMES.get(event.name, event.name)
        attrs: dict[str, Any] = {}

        # Carry correlation ids from the event payload (stamped upstream).
        for key in ("trace_id", "session_id", "turn_id"):
            val = event.payload.get(key)
            if isinstance(val, str):
                attrs[f"hachi.{key}"] = val

        # Carry well-known payload fields as span attributes (allowlist).
        for key in ("role", "model", "status", "duration", "iterations"):
            val = event.payload.get(key)
            if isinstance(val, str | bool | int | float):
                attr_key = f"hachi.{key}" if f"hachi.{key}" in ALLOWED_SPAN_ATTRS else key
                attrs[attr_key] = val

        tool_name = event.payload.get("name")
        if isinstance(tool_name, str):
            attrs["tool_name"] = tool_name

        # Stamp attributes onto the currently active span.
        if attrs:
            tracing.add_span_attributes(**attrs)

        # Add a span-event so the event name is visible in trace UIs.
        tracing.add_span_event(span_event_name, **attrs)
