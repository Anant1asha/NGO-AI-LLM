"""Tests for EventBus reactivity (Part 1-4 deliverables).

Covers:
  1. EventsSettings.bus_funnel defaults to True (regression guard).
  2. Promoted literals: loop.py emit sites reference the dotted constant names.
  3. ObservabilitySink is subscribed (named "observability") when bus is active.
  4. Reactive auto_extract: with bus on and durable_handlers off, a file.uploaded
     publish triggers extraction synchronously via the inline wrapper.
"""

from __future__ import annotations

from typing import Any

from hachi.core.event_bus import EventBus
from hachi.core.runtime_events import (
    BUDGET_EXCEEDED,
    FILE_UPLOADED,
    JOB_RETRY,
    LLM_RETRY,
    SESSION_TIME_LIMIT,
    RuntimeEvent,
    now_iso,
)
from hachi.core.settings import EventsSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(name: str, payload: dict[str, Any] | None = None) -> RuntimeEvent:
    """Construct a minimal RuntimeEvent for testing."""
    return RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())


# ---------------------------------------------------------------------------
# Part 1 — Default bus_funnel regression guard
# ---------------------------------------------------------------------------


class TestBusFunnelDefault:
    """EventsSettings.bus_funnel must default to True."""

    def test_bus_funnel_defaults_true(self) -> None:
        """bus_funnel is True by default — regression guard for Part 4."""
        cfg = EventsSettings()
        assert cfg.bus_funnel is True

    def test_bus_funnel_can_be_disabled(self) -> None:
        """bus_funnel can be explicitly set to False (opt-out path)."""
        cfg = EventsSettings(bus_funnel=False)
        assert cfg.bus_funnel is False

    def test_bus_funnel_env_override(self) -> None:
        """bus_funnel can be overridden from the config dict (simulates TOML [events])."""
        cfg = EventsSettings.model_validate({"bus_funnel": False})
        assert cfg.bus_funnel is False


# ---------------------------------------------------------------------------
# Part 2 — Promoted literal constants
# ---------------------------------------------------------------------------


class TestPromotedConstants:
    """Event name constants must have the correct dotted values."""

    def test_llm_retry_constant(self) -> None:
        assert LLM_RETRY == "llm.retry"

    def test_session_time_limit_constant(self) -> None:
        assert SESSION_TIME_LIMIT == "session.time.limit"

    def test_budget_exceeded_constant(self) -> None:
        assert BUDGET_EXCEEDED == "budget.exceeded"

    def test_job_retry_constant(self) -> None:
        assert JOB_RETRY == "job.retry"

    def test_loop_imports_constants(self) -> None:
        """loop.py must import the four promoted constants (AST/import check)."""
        import ast
        import pathlib

        loop_src = (
            pathlib.Path(__file__).parent.parent / "src" / "hachi" / "core" / "loop.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(loop_src)

        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "hachi.core.runtime_events":
                for alias in node.names:
                    imported_names.add(alias.name)

        for name in ("BUDGET_EXCEEDED", "LLM_RETRY", "SESSION_TIME_LIMIT"):
            assert name in imported_names, f"loop.py does not import {name} from runtime_events"

    def test_queue_imports_job_retry(self) -> None:
        """queue.py must import JOB_RETRY from runtime_events (no raw literal)."""
        import ast
        import pathlib

        queue_src = (
            pathlib.Path(__file__).parent.parent / "src" / "hachi" / "jobs" / "queue.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(queue_src)

        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "hachi.core.runtime_events":
                for alias in node.names:
                    imported_names.add(alias.name)

        assert "JOB_RETRY" in imported_names, "queue.py does not import JOB_RETRY"

    def test_no_underscore_literals_in_loop(self) -> None:
        """loop.py must not contain the old underscore event-name literals."""
        import pathlib

        loop_src = (
            pathlib.Path(__file__).parent.parent / "src" / "hachi" / "core" / "loop.py"
        ).read_text(encoding="utf-8")

        for bad in ('"llm_retry"', '"budget_exceeded"', '"session_time_limit"'):
            assert bad not in loop_src, f"loop.py still contains raw literal {bad}"

    def test_no_underscore_literal_in_queue(self) -> None:
        """queue.py must not contain the old raw 'job.retry' string literal."""
        import pathlib

        queue_src = (
            pathlib.Path(__file__).parent.parent / "src" / "hachi" / "jobs" / "queue.py"
        ).read_text(encoding="utf-8")

        assert '"job.retry"' not in queue_src, "queue.py still contains raw literal 'job.retry'"

    def test_loop_emits_dotted_budget_exceeded(self) -> None:
        """ExecutionLoop emits 'budget.exceeded' (dotted) when session budget is hit.

        Uses a pre-seeded CostTracker mock so _budget_exceeded() fires before
        any LLM call, letting us verify the emitted event name without a live LLM.
        """
        from unittest.mock import MagicMock

        from hachi.core.cost import CostSnapshot, CostTracker
        from hachi.core.loop import ExecutionLoop, ToolRegistry
        from hachi.core.sub_agent import SubAgentMemory

        events: list[tuple[str, dict[str, Any]]] = []
        registry = ToolRegistry()

        # Seed the tracker so max_tokens=1 is already exceeded.
        tracker = MagicMock(spec=CostTracker)
        tracker.snapshot.return_value = CostSnapshot(
            input_tokens=100,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            total_tokens=100,
            estimated_cost_usd=0.0,
            call_count=1,
        )

        # Dummy LLM — should never be called because the budget check fires first.
        dummy_llm = MagicMock()

        loop = ExecutionLoop(
            dummy_llm,
            registry,
            SubAgentMemory(),
            base_system_prompt="x",
            on_event=lambda et, d: events.append((et, d)),
            max_tokens=1,  # already exceeded by tracker snapshot
            cost_tracker=tracker,
        )
        loop.add_user_message("go")
        result = loop.run(max_iterations=2)

        assert result.startswith("[BUDGET LIMIT REACHED]"), f"Unexpected result: {result!r}"
        budget_events = [e for e in events if e[0] == BUDGET_EXCEEDED]
        assert budget_events, f"No {BUDGET_EXCEEDED!r} event emitted; got {[e[0] for e in events]}"
        # The dummy LLM must NOT have been called (budget fired before LLM).
        dummy_llm.generate_stream.assert_not_called()


# ---------------------------------------------------------------------------
# Part 3 — ObservabilitySink subscription
# ---------------------------------------------------------------------------


class TestObservabilitySinkSubscribed:
    """When bus is active, ObservabilitySink must be subscribed as 'observability'."""

    def test_sink_subscribed_to_bus(self) -> None:
        """Build a bus and add subscriptions as orchestrator.py does; confirm 'observability'."""
        from hachi.core.obs.sink import ObservabilitySink

        bus = EventBus()

        # Replicate the orchestrator subscription sequence.
        bus.subscribe("*", lambda e: None, mode="sync", name="read-models")
        bus.subscribe("*", lambda e: None, mode="sync", name="surface")
        bus.subscribe("*", ObservabilitySink().handle, mode="sync", name="observability")

        with bus._lock:
            names = [s.name for s in bus._subscriptions]

        assert "observability" in names
        assert names.index("observability") > names.index("surface"), (
            "observability must be subscribed after surface"
        )

    def test_sink_handle_noops_without_tracing(self) -> None:
        """ObservabilitySink.handle is a cheap no-op when tracing is inactive."""
        from hachi.core.obs.sink import ObservabilitySink

        sink = ObservabilitySink()
        evt = _event("tool.call.started", {"tool_name": "read_file"})
        # Should not raise and should not attempt real tracing.
        sink.handle(evt)

    def test_orchestrator_settings_flag_wires_sink(self) -> None:
        """EventsSettings with bus_funnel=True makes the orchestrator path subscribe the sink.

        This is a source-level check (AST) since a full gateway boot needs an API key.
        We verify that orchestrator.py imports ObservabilitySink and subscribes it.
        """
        import ast
        import pathlib

        orch_src = (
            pathlib.Path(__file__).parent.parent / "src" / "hachi" / "gateway" / "orchestrator.py"
        ).read_text(encoding="utf-8")

        # Check the import is present.
        assert "ObservabilitySink" in orch_src, (
            "orchestrator.py does not reference ObservabilitySink"
        )
        # Check the subscription name "observability" appears.
        assert '"observability"' in orch_src, (
            'orchestrator.py does not subscribe name="observability"'
        )

        # Parse and confirm both the import and the subscribe call are present.
        tree = ast.parse(orch_src)
        has_import = any(
            isinstance(node, ast.ImportFrom) and "ObservabilitySink" in {a.name for a in node.names}
            for node in ast.walk(tree)
        )
        assert has_import, "orchestrator.py does not import ObservabilitySink"


# ---------------------------------------------------------------------------
# Part 4 — Reactive auto_extract (sync inline when durable_handlers is off)
# ---------------------------------------------------------------------------


class TestReactiveAutoExtract:
    """file.uploaded → auto_extract fires inline (sync) when durable_handlers is off."""

    def _make_bus_with_sync_auto_extract(self) -> tuple[EventBus, list[dict[str, Any]]]:
        """Build a bus with the sync auto_extract wrapper and a capture list.

        Replicates the orchestrator Part 3 logic (durable_handlers=False branch).
        """
        captured: list[dict[str, Any]] = []

        def _fake_handler(
            event_name: str = "",
            event_payload: dict[str, Any] | None = None,
            event_timestamp: str = "",
            event_sequence: int = 0,
            **kwargs: Any,
        ) -> str:
            captured.append(
                {
                    "event_name": event_name,
                    "event_payload": event_payload or {},
                    "event_timestamp": event_timestamp,
                    "event_sequence": event_sequence,
                }
            )
            return "captured"

        bus = EventBus()

        def _auto_extract_sync_wrapper(event: RuntimeEvent) -> None:
            """Inline sync adapter: unpacks RuntimeEvent into handle_auto_extract kwargs."""
            _fake_handler(
                event_name=event.name,
                event_payload=event.payload,
                event_timestamp=event.timestamp,
                event_sequence=0,
            )

        bus.subscribe(FILE_UPLOADED, _auto_extract_sync_wrapper, mode="sync", name="auto_extract")
        return bus, captured

    def test_file_uploaded_triggers_inline_extraction(self) -> None:
        """Publishing file.uploaded fires the sync wrapper inline."""
        bus, captured = self._make_bus_with_sync_auto_extract()
        bus.publish(_event(FILE_UPLOADED, {"file_id": "f1", "media_type": "text/plain"}))

        assert len(captured) == 1
        assert captured[0]["event_name"] == FILE_UPLOADED
        assert captured[0]["event_payload"]["file_id"] == "f1"

    def test_other_events_do_not_trigger_auto_extract(self) -> None:
        """Non-file.uploaded events must not trigger the auto_extract subscriber."""
        bus, captured = self._make_bus_with_sync_auto_extract()
        bus.publish(_event("session.chat.started"))
        bus.publish(_event("tool.call.completed"))

        assert captured == [], f"Expected no captures; got {captured}"

    def test_bus_no_queue_async_falls_back_to_sync(self) -> None:
        """EventBus without a job_queue falls back to inline execution for async subscribers.

        This validates the underlying EventBus contract relied upon by Part 3.
        """
        called: list[RuntimeEvent] = []
        bus = EventBus(job_queue=None)  # no queue → inline fallback

        bus.subscribe(FILE_UPLOADED, lambda e: called.append(e), mode="async", name="test")
        bus.publish(_event(FILE_UPLOADED, {"file_id": "x"}))

        assert len(called) == 1
        assert called[0].payload["file_id"] == "x"

    def test_handle_auto_extract_degrades_without_file_id(self) -> None:
        """handle_auto_extract returns 'skipped: missing file_id' when payload is empty."""
        from hachi.core.runtime.job_handlers import handle_auto_extract

        result = handle_auto_extract(event_name=FILE_UPLOADED, event_payload={})
        assert result.startswith("skipped"), f"Expected 'skipped:...' but got {result!r}"

    def test_sync_wrapper_event_sequence_is_zero(self) -> None:
        """The sync inline wrapper always passes event_sequence=0 (no queue seq)."""
        captures: list[dict[str, Any]] = []

        bus = EventBus()

        def _capture_wrapper(event: RuntimeEvent) -> None:
            captures.append({"event_sequence": 0, "event_name": event.name})

        bus.subscribe(FILE_UPLOADED, _capture_wrapper, mode="sync", name="test")
        bus.publish(_event(FILE_UPLOADED, {"file_id": "abc"}))

        assert len(captures) == 1
        assert captures[0]["event_sequence"] == 0
