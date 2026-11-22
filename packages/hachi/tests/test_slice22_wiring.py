"""Slice 2.2 wiring gate tests.

Three integration gates:
  1. FUNNEL-IDENTICAL  — EventBus funnel produces byte-identical on_event call sequence
                         (names + payloads + legacy aliases + order) vs the old direct-call path.
  2. GATE-DURABLE      — A durable handler_name= job survives a SQLiteJobQueue restart;
                         the new queue instance picks it up and executes it.
  3. A4-SWEEP          — A WAITING run with timeout_at in the past is swept by _sweep_once()
                         and a resume_run job is enqueued, without relying on wall-clock sleep.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pytest

from hachi.core.event_bus import EventBus
from hachi.core.runtime_events import RuntimeEvent, adapt_event, now_iso
from hachi.jobs import Job, JobRegistry, JobStatus, JobWorker, SQLiteJobQueue
from hachi.jobs.queue import InMemoryJobQueue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(name: str, payload: dict[str, Any] | None = None) -> RuntimeEvent:
    return RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())


# ---------------------------------------------------------------------------
# Gate 1: FUNNEL-IDENTICAL
#
# The bus-backed emit path must produce exactly the same on_event call sequence
# (names, payloads, ordering) as the direct-call path for the same event script.
# ---------------------------------------------------------------------------


class TestFunnelIdentical:
    """EventBus funnel produces byte-identical on_event call sequence."""

    def _direct_path_calls(
        self,
        events: list[tuple[str, dict[str, Any]]],
        is_relay: bool = False,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Simulate the OLD direct-call emit/relay path; return (name, payload) list."""
        calls: list[tuple[str, dict[str, Any]]] = []
        read_model_names: list[str] = []

        def on_event(name: str, payload: dict[str, Any]) -> None:  # noqa: ANN001
            calls.append((name, payload))

        def emit_runtime_event(name: str, payload: dict[str, Any] | None = None) -> None:
            ev = RuntimeEvent(name=name, payload=payload or {}, timestamp="T")
            read_model_names.append(ev.name)  # read_models.append_event
            on_event(ev.name, ev.payload)

        def relay_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
            for envelope in adapt_event(event_type, payload):
                ev = envelope.primary
                read_model_names.append(ev.name)
                on_event(ev.name, ev.payload)
                for alias in envelope.legacy_aliases:
                    on_event(alias, ev.payload)

        for name, payload in events:
            if is_relay:
                relay_event(name, payload)
            else:
                emit_runtime_event(name, payload)

        return calls

    def _bus_path_calls(
        self,
        events: list[tuple[str, dict[str, Any]]],
        is_relay: bool = False,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Simulate the NEW bus-backed path; return (name, payload) list."""
        calls: list[tuple[str, dict[str, Any]]] = []
        read_model_names: list[str] = []

        bus = EventBus()

        def _read_models_sink(event: RuntimeEvent) -> None:
            read_model_names.append(event.name)

        def _surface_sink(event: RuntimeEvent) -> None:
            calls.append((event.name, event.payload))

        bus.subscribe("*", _read_models_sink, mode="sync", name="read-models")
        bus.subscribe("*", _surface_sink, mode="sync", name="surface")

        def emit_runtime_event(name: str, payload: dict[str, Any] | None = None) -> None:
            ev = RuntimeEvent(name=name, payload=payload or {}, timestamp="T")
            bus.publish(ev)

        def relay_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
            for envelope in adapt_event(event_type, payload):
                bus.publish(envelope.primary)
                # Aliases: surface-only (not read_models), matching old behavior.
                for alias in envelope.legacy_aliases:
                    alias_ev = RuntimeEvent(
                        name=alias,
                        payload=envelope.primary.payload,
                        timestamp=envelope.primary.timestamp,
                    )
                    calls.append((alias_ev.name, alias_ev.payload))

        for name, payload in events:
            if is_relay:
                relay_event(name, payload)
            else:
                emit_runtime_event(name, payload)

        return calls

    def test_emit_sequence_identical(self) -> None:
        """emit_runtime_event: bus path produces identical on_event call list."""
        script: list[tuple[str, dict[str, Any]]] = [
            ("boot.progress", {"step": "permissions"}),
            ("boot.complete", {"skills": 5}),
            ("session.chat.started", {"session_id": "s1"}),
            ("session.chat.completed", {"session_id": "s1"}),
        ]
        direct = self._direct_path_calls(script, is_relay=False)
        via_bus = self._bus_path_calls(script, is_relay=False)
        assert direct == via_bus, f"Mismatch:\ndirect={direct}\nvia_bus={via_bus}"

    def test_relay_sequence_identical_primary_events(self) -> None:
        """relay_event: primary event names match between direct and bus paths."""
        # relay_event translates legacy names; verify the primary event names agree.
        script: list[tuple[str, dict[str, Any]]] = [
            ("tool_call", {"name": "read_file", "input": {"path": "/tmp/x"}}),
            ("tool_result", {"name": "read_file", "result": "content"}),
            ("thinking", {"iteration": 1}),
        ]
        direct = self._direct_path_calls(script, is_relay=True)
        via_bus = self._bus_path_calls(script, is_relay=True)
        assert direct == via_bus, f"Mismatch:\ndirect={direct}\nvia_bus={via_bus}"

    def test_relay_aliases_delivered_to_surface(self) -> None:
        """relay_event: legacy aliases reach on_event in both paths."""
        # "tool_call" produces a primary "tool.call.started" and alias "tool_call".
        script: list[tuple[str, dict[str, Any]]] = [
            ("tool_call", {"name": "bash", "input": {}}),
        ]
        direct = self._direct_path_calls(script, is_relay=True)
        via_bus = self._bus_path_calls(script, is_relay=True)
        # Both paths must deliver both the primary and the alias.
        direct_names = [n for n, _ in direct]
        bus_names = [n for n, _ in via_bus]
        assert "tool.call.started" in direct_names
        assert "tool_call" in direct_names
        assert direct_names == bus_names

    def test_exception_in_subscriber_does_not_stall(self) -> None:
        """Bus wraps bad sync subscribers; other subscribers still run."""
        results: list[str] = []

        bus = EventBus()
        bus.subscribe("*", lambda e: (_ for _ in ()).throw(RuntimeError("bad")), mode="sync")
        bus.subscribe("*", lambda e: results.append(e.name), mode="sync")

        bus.publish(_event("test.event"))
        assert results == ["test.event"]


# ---------------------------------------------------------------------------
# Gate 2: GATE-DURABLE
#
# A job with handler_name= enqueued into SQLiteJobQueue survives a restart:
# a new SQLiteJobQueue over the same db file finds the job and the worker
# executes it via the registry.
# ---------------------------------------------------------------------------


class TestGateDurable:
    """A durable handler_name= job survives SQLiteJobQueue restart."""

    def test_job_survives_restart_and_executes(self, tmp_path: Path) -> None:
        db = tmp_path / "jobs.db"

        executed: list[dict[str, Any]] = []

        def my_handler(session_id: str = "", value: str = "", **kw: Any) -> str:
            executed.append({"session_id": session_id, "value": value})
            return "ok"

        # --- Process 1: enqueue a durable job ---
        q1 = SQLiteJobQueue(db_path=db)
        job = Job(
            job_id="",
            name="test_job",
            handler_name="my_handler",
            payload={"session_id": "sess-1", "value": "hello"},
            status=JobStatus.PENDING,
        )
        job_id = q1.enqueue(job)
        q1.shutdown()

        # --- "Restart": open a NEW queue on the same db ---
        q2 = SQLiteJobQueue(db_path=db)
        registry = JobRegistry()
        registry.register("my_handler", my_handler)

        worker = JobWorker(q2, registry=registry)
        ran = worker.execute_one()

        assert ran, "Worker should have executed the job"
        assert len(executed) == 1
        assert executed[0] == {"session_id": "sess-1", "value": "hello"}

        # Verify status is terminal in the DB.
        loaded = q2.get_job(job_id)
        assert loaded is not None
        assert loaded.status == JobStatus.COMPLETED

    def test_func_only_job_discarded_on_restart(self, tmp_path: Path) -> None:
        """func= only jobs do not survive a restart — the callable is in-memory only.

        On graceful ``shutdown()`` an instance drops its own un-drained func rows,
        and any that leak are swept by ``_recover_running`` once stale. Either way
        a fresh instance has nothing pending it cannot dispatch.
        """
        db = tmp_path / "jobs_func.db"

        # Enqueue a func= job (no handler_name).
        q1 = SQLiteJobQueue(db_path=db)
        job = Job(
            job_id="",
            name="func_job",
            func=lambda: None,  # live callable — not serializable
            status=JobStatus.PENDING,
        )
        q1.enqueue(job)
        q1.shutdown()  # drops q1's own un-drained func rows

        # Restart: nothing pending for the new instance to (mis)handle.
        q2 = SQLiteJobQueue(db_path=db)
        pending = q2.get_pending(limit=10)
        assert len(pending) == 0, f"Expected 0 pending after discard, got {len(pending)}"


# ---------------------------------------------------------------------------
# Gate 3: A4-SWEEP
#
# _sweep_once() detects a WAITING run with timeout_at in the past and enqueues
# a resume_run job.  Deterministic — no wall-clock sleep.
# ---------------------------------------------------------------------------


class TestA4Sweep:
    """Scheduler timeout sweep wakes timed-out WAITING runs."""

    def test_sweep_enqueues_resume_job_for_timed_out_run(self, tmp_path: Path) -> None:
        from hachi.core.runtime.state import RunState, RunStatus, WaitCondition, WaitKind
        from hachi.core.runtime.store import RunStateStore
        from hachi.gateway.orchestrator import _sweep_once

        db = tmp_path / "runs.db"
        store = RunStateStore(db_path=db)

        past = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)).isoformat()
        run = RunState(
            run_id="run-timed-out-001",
            session_id="sess-x",
            status=RunStatus.WAITING,
            wait=WaitCondition(
                kind=WaitKind.EVENT,
                key="file.uploaded",
                created_at=now_iso(),
                timeout_at=past,
            ),
            resume_cursor=1,
            payload={},
            updated_at=now_iso(),
        )
        store.upsert(run)

        # Use an InMemoryJobQueue to capture enqueued jobs without SQLite.
        queue = InMemoryJobQueue()

        # Inject "now" = 10 minutes after the timeout to ensure past < now.
        now = datetime.datetime.now(datetime.UTC)
        swept = _sweep_once(queue, now=now, store=store)

        assert "run-timed-out-001" in swept, f"Expected run swept, got swept={swept}"

        # Verify a resume_run job was enqueued.
        pending = queue.get_pending(limit=10)
        assert len(pending) == 1
        job = pending[0]
        assert job.handler_name == "resume_run"
        assert job.payload["run_id"] == "run-timed-out-001"
        assert job.payload["result"]["reason"] == "timeout"

    def test_sweep_skips_run_without_timeout(self, tmp_path: Path) -> None:
        from hachi.core.runtime.state import RunState, RunStatus, WaitCondition, WaitKind
        from hachi.core.runtime.store import RunStateStore
        from hachi.gateway.orchestrator import _sweep_once

        db = tmp_path / "runs2.db"
        store = RunStateStore(db_path=db)

        run = RunState(
            run_id="run-no-timeout-001",
            session_id="sess-y",
            status=RunStatus.WAITING,
            wait=WaitCondition(
                kind=WaitKind.USER,
                key="approval-xyz",
                created_at=now_iso(),
                timeout_at=None,  # no timeout
            ),
            resume_cursor=0,
            payload={},
            updated_at=now_iso(),
        )
        store.upsert(run)

        queue = InMemoryJobQueue()
        now = datetime.datetime.now(datetime.UTC)
        swept = _sweep_once(queue, now=now, store=store)

        assert swept == [], f"Expected nothing swept, got {swept}"
        assert queue.get_pending(limit=10) == []

    def test_sweep_skips_run_not_yet_timed_out(self, tmp_path: Path) -> None:
        from hachi.core.runtime.state import RunState, RunStatus, WaitCondition, WaitKind
        from hachi.core.runtime.store import RunStateStore
        from hachi.gateway.orchestrator import _sweep_once

        db = tmp_path / "runs3.db"
        store = RunStateStore(db_path=db)

        future = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)).isoformat()
        run = RunState(
            run_id="run-future-001",
            session_id="sess-z",
            status=RunStatus.WAITING,
            wait=WaitCondition(
                kind=WaitKind.TIME,
                key=future,
                created_at=now_iso(),
                timeout_at=future,
            ),
            resume_cursor=0,
            payload={},
            updated_at=now_iso(),
        )
        store.upsert(run)

        queue = InMemoryJobQueue()
        now = datetime.datetime.now(datetime.UTC)
        swept = _sweep_once(queue, now=now, store=store)

        assert swept == [], f"Run not yet timed out should not be swept, got {swept}"


# ---------------------------------------------------------------------------
# Handler correction gate
# ---------------------------------------------------------------------------


class TestHandlerCorrections:
    """Verify the handler corrections match documented behavior."""

    def test_generate_title_uses_fallback_title_not_llm(self) -> None:
        """handle_generate_title uses fallback_title (no LLM) in durable path."""
        from hachi.core.runtime.job_handlers import handle_generate_title
        from hachi.core.session_titler import fallback_title

        # Patch SessionStore at the source module level (it's imported lazily inside
        # handle_generate_title, so we patch hachi.core.session_store.SessionStore).
        with pytest.MonkeyPatch().context() as mp:
            stored: list[tuple[str, str]] = []

            class _FakeStore:
                def set_session_title(self, sid: str, title: str) -> None:
                    stored.append((sid, title))

            mp.setattr("hachi.core.session_store.SessionStore", _FakeStore, raising=True)
            result = handle_generate_title(
                session_id="s1",
                user_message="Fix the login bug",
                assistant_message="I'll fix it now",
            )

        expected = fallback_title("Fix the login bug")
        assert result == expected
        assert stored == [("s1", expected)]

    def test_extract_fact_is_real_and_degrades_gracefully(self) -> None:
        # P1-5 made handle_extract_fact a real durable handler; with no vault/LLM
        # resolvable in the test env it must degrade gracefully (status string,
        # never crash, never the old "seam:" placeholder).
        from hachi.core.runtime.job_handlers import handle_extract_fact

        result = handle_extract_fact(session_id="s2", text="The user prefers dark mode")
        assert isinstance(result, str)
        assert not result.startswith("seam:")
        # Degrades to a skipped/error status — vault or LLM client unavailable in CI.
        assert result.startswith(("skipped:", "error:"))

    def test_extract_fact_skips_empty_text(self) -> None:
        from hachi.core.runtime.job_handlers import handle_extract_fact

        result = handle_extract_fact(session_id="s3", text="")
        assert result == "skipped:empty_text"

    def test_auto_extract_is_real_and_degrades_gracefully(self) -> None:
        # Slice 2.4 (Files) made handle_auto_extract a real extractor; with no
        # extractor for an empty media_type it must degrade gracefully (status
        # string, never crash, never the old "seam:" placeholder).
        from hachi.core.runtime.job_handlers import handle_auto_extract

        result = handle_auto_extract(
            event_name="file.uploaded",
            event_payload={"file_id": "f42"},
            event_sequence=1,
        )
        assert isinstance(result, str)
        assert "f42" in result
        assert not result.startswith("seam:")
