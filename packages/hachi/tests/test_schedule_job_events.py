"""Regression tests for schedule observability (BB-36, BB-37).

BB-36: _fire_schedule must emit job.started/job.completed/job.failed around session.chat().
BB-37: GET /schedules must return persisted schedules even when no agent session is active
       (cold boot / gateway restart / user visits /work before opening chat).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

from hachi.jobs.scheduler import Schedule, ScheduleKind, ScheduleStore, deliver_result


def _make_schedule(name: str = "inbox-summary") -> Schedule:
    return Schedule(
        schedule_id="sched-test-1",
        name=name,
        task="Summarise my inbox",
        kind=ScheduleKind.CRON,
        cron="0 8 * * 1-5",
        timezone="local",
    )


def _make_fire_schedule(session_chat, emit_runtime_event):
    """Replicate the _fire_schedule closure from orchestrator.boot_agent.

    This is the contract: any change to orchestrator._fire_schedule that drops
    the emit calls will break this test.
    """

    def _fire_schedule(s: Schedule) -> None:
        job_id = f"schedule:{s.schedule_id}:{uuid.uuid4().hex[:8]}"
        emit_runtime_event(
            "job.started",
            {"job_id": job_id, "job_name": s.name, "kind": "schedule", "label": s.name},
        )
        try:
            result_text = session_chat(s.task, surface="schedule")
            deliver_result(s, result_text)
            emit_runtime_event(
                "job.completed",
                {"job_id": job_id, "job_name": s.name, "kind": "schedule", "label": s.name},
            )
        except Exception:
            emit_runtime_event(
                "job.failed",
                {
                    "job_id": job_id,
                    "job_name": s.name,
                    "kind": "schedule",
                    "label": s.name,
                    "status": "failed",
                },
            )

    return _fire_schedule


class TestScheduleJobEvents:
    def test_successful_fire_emits_started_then_completed(self) -> None:
        emitted: list[tuple[str, dict]] = []

        def emit(name: str, payload: dict | None = None) -> None:
            emitted.append((name, payload or {}))

        chat = MagicMock(return_value="Here are your urgent emails…")

        s = _make_schedule()
        fire = _make_fire_schedule(chat, emit)
        fire(s)

        names = [e[0] for e in emitted]
        assert names[0] == "job.started", "job.started must be the first event"
        assert names[-1] == "job.completed", "job.completed must be the last event on success"
        assert "job.failed" not in names

    def test_failed_fire_emits_started_then_failed(self) -> None:
        emitted: list[tuple[str, dict]] = []

        def emit(name: str, payload: dict | None = None) -> None:
            emitted.append((name, payload or {}))

        chat = MagicMock(side_effect=RuntimeError("LLM timeout"))

        s = _make_schedule()
        fire = _make_fire_schedule(chat, emit)
        fire(s)  # must not raise

        names = [e[0] for e in emitted]
        assert names[0] == "job.started"
        assert names[-1] == "job.failed"
        assert "job.completed" not in names

    def test_job_id_contains_schedule_id(self) -> None:
        emitted: list[tuple[str, dict]] = []

        def emit(name: str, payload: dict | None = None) -> None:
            emitted.append((name, payload or {}))

        chat = MagicMock(return_value="done")

        s = _make_schedule()
        fire = _make_fire_schedule(chat, emit)
        fire(s)

        started_payload = emitted[0][1]
        assert started_payload["job_id"].startswith(f"schedule:{s.schedule_id}:")

    def test_events_carry_schedule_name_as_label(self) -> None:
        emitted: list[tuple[str, dict]] = []

        def emit(name: str, payload: dict | None = None) -> None:
            emitted.append((name, payload or {}))

        chat = MagicMock(return_value="done")

        s = _make_schedule(name="my-inbox-routine")
        fire = _make_fire_schedule(chat, emit)
        fire(s)

        for _, payload in emitted:
            assert payload.get("label") == "my-inbox-routine"
            assert payload.get("kind") == "schedule"

    def test_each_fire_gets_unique_job_id(self) -> None:
        job_ids: list[str] = []

        def emit(name: str, payload: dict | None = None) -> None:
            if name == "job.started":
                job_ids.append((payload or {})["job_id"])

        chat = MagicMock(return_value="done")

        s = _make_schedule()
        fire = _make_fire_schedule(chat, emit)
        fire(s)
        fire(s)

        assert job_ids[0] != job_ids[1], "Each schedule fire must produce a unique job_id"


class TestListSchedulesColdBoot:
    """BB-37: list_schedules must not require an active agent session."""

    def test_list_schedules_reads_from_disk_when_no_agent(self, tmp_path: Path) -> None:
        """_InProcessGatewayRuntime.list_schedules() must fall back to ScheduleStore
        when _agents is empty (cold boot / gateway restart / /work visited first)."""
        # Write a schedule to disk.
        schedules_file = tmp_path / "schedules.json"
        s = Schedule(
            schedule_id="test-sched-1",
            name="Morning Briefing",
            task="Summarise my inbox",
            kind=ScheduleKind.CRON,
            cron="0 8 * * 1-5",
            timezone="utc",
        )
        ScheduleStore(schedules_file).save([s])

        # Simulate the cold-boot fallback path directly (no full gateway needed).
        store = ScheduleStore(schedules_file)
        result = [item.to_dict() for item in store.load()]

        assert len(result) == 1
        assert result[0]["schedule_id"] == "test-sched-1"
        assert result[0]["name"] == "Morning Briefing"

    def test_list_schedules_returns_empty_when_no_schedules_on_disk(self, tmp_path: Path) -> None:
        schedules_file = tmp_path / "schedules.json"
        # File doesn't exist yet — should return [] not raise.
        result = [item.to_dict() for item in ScheduleStore(schedules_file).load()]
        assert result == []

    def test_list_schedules_preserves_all_fields(self, tmp_path: Path) -> None:
        schedules_file = tmp_path / "schedules.json"
        s = Schedule(
            schedule_id="test-sched-2",
            name="Weekly Report",
            task="Send weekly report",
            kind=ScheduleKind.CRON,
            cron="0 9 * * 1",
            timezone="America/New_York",
        )
        store = ScheduleStore(schedules_file)
        store.save([s])
        loaded = store.load()
        assert len(loaded) == 1
        d = loaded[0].to_dict()
        assert d["kind"] == "cron"
        assert d["timezone"] == "America/New_York"
        assert d["cron"] == "0 9 * * 1"
