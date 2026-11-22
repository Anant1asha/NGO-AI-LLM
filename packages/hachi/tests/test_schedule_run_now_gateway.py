"""Tests for AgentSession.run_schedule_now + the gateway route wired to it (BB-36).

Covers the Work-screen "Run now" force-trigger:
  1. AgentSession.run_schedule_now dispatches inline when there is no job queue.
  2. AgentSession.run_schedule_now enqueues a background job when a queue exists
     (mirrors the ``func=`` closure pattern used by ``_enqueue_title_job``).
  3. Unknown schedule id / no scheduler / no schedule runner -> False, no dispatch.
  4. POST /schedules/{id}/run-now round-trips through GatewayControlPlane.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app
from hachi.gateway.orchestrator import AgentSession
from hachi.jobs.scheduler import Schedule, ScheduleKind, Scheduler, ScheduleStore


def _fake_scheduler(schedule: Schedule | None) -> MagicMock:
    sched = MagicMock(spec=Scheduler)
    sched.get.return_value = schedule
    sched.run_now.return_value = schedule is not None
    return sched


def _fake_schedule(schedule_id: str = "sched-1") -> Schedule:
    return Schedule(
        schedule_id=schedule_id,
        name="daily-summary",
        task="Summarize the news.",
        kind=ScheduleKind.CRON,
        cron="0 9 * * *",
    )


def _session_with(
    *,
    scheduler: Any,
    fire: Any,
    job_queue: Any = None,
) -> AgentSession:
    sess = AgentSession.__new__(AgentSession)
    sess._scheduler = scheduler
    sess._job_queue = job_queue
    sess._session_id = "sess-1"
    runner = MagicMock()
    runner._fire = fire
    sess._schedule_runner = runner
    return sess


# ---------------------------------------------------------------------------
# AgentSession.run_schedule_now
# ---------------------------------------------------------------------------


def test_run_schedule_now_inline_when_no_job_queue() -> None:
    schedule = _fake_schedule()
    scheduler = _fake_scheduler(schedule)
    fire = MagicMock()
    sess = _session_with(scheduler=scheduler, fire=fire, job_queue=None)

    ok = sess.run_schedule_now("sched-1")

    assert ok is True
    scheduler.get.assert_called_once_with("sched-1")
    scheduler.run_now.assert_called_once_with("sched-1", fire)


def test_run_schedule_now_enqueues_background_job_when_queue_present() -> None:
    schedule = _fake_schedule()
    scheduler = _fake_scheduler(schedule)
    fire = MagicMock()
    job_queue = MagicMock()
    sess = _session_with(scheduler=scheduler, fire=fire, job_queue=job_queue)

    ok = sess.run_schedule_now("sched-1")

    assert ok is True
    # Dispatch must go through the job queue, not execute synchronously here.
    job_queue.enqueue.assert_called_once()
    scheduler.run_now.assert_not_called()

    # Executing the enqueued job's func performs the real fire+mark_fired dispatch.
    enqueued_job = job_queue.enqueue.call_args[0][0]
    assert enqueued_job.func is not None
    enqueued_job.func()
    scheduler.run_now.assert_called_once_with("sched-1", fire)


def test_run_schedule_now_unknown_id_returns_false_no_dispatch() -> None:
    scheduler = _fake_scheduler(None)
    fire = MagicMock()
    job_queue = MagicMock()
    sess = _session_with(scheduler=scheduler, fire=fire, job_queue=job_queue)

    ok = sess.run_schedule_now("does-not-exist")

    assert ok is False
    job_queue.enqueue.assert_not_called()
    scheduler.run_now.assert_not_called()


def test_run_schedule_now_no_scheduler_returns_false() -> None:
    sess = AgentSession.__new__(AgentSession)
    sess._scheduler = None
    sess._job_queue = None

    assert sess.run_schedule_now("anything") is False


def test_run_schedule_now_no_schedule_runner_returns_false() -> None:
    schedule = _fake_schedule()
    scheduler = _fake_scheduler(schedule)
    sess = AgentSession.__new__(AgentSession)
    sess._scheduler = scheduler
    sess._job_queue = None
    # No _schedule_runner attribute at all (never boots proactive scheduling).

    assert sess.run_schedule_now("sched-1") is False
    scheduler.run_now.assert_not_called()


def test_run_schedule_now_end_to_end_with_real_scheduler(tmp_path) -> None:
    """Integration: a real Scheduler + real Schedule, fake fire callback."""
    real_scheduler = Scheduler(ScheduleStore(tmp_path / "schedules.json"))
    s = real_scheduler.add(name="daily", task="say hi", kind="cron", cron="0 9 * * *")
    fire_calls: list[Schedule] = []
    sess = _session_with(scheduler=real_scheduler, fire=fire_calls.append, job_queue=None)

    ok = sess.run_schedule_now(s.schedule_id)

    assert ok is True
    assert fire_calls == [s]
    assert real_scheduler.get(s.schedule_id).run_count == 1


# ---------------------------------------------------------------------------
# POST /schedules/{id}/run-now gateway route
# ---------------------------------------------------------------------------


def test_post_schedule_run_now_calls_control_plane_handler() -> None:
    stub = MagicMock(return_value={"ok": True, "schedule_id": "sched-1"})
    cp = GatewayControlPlane(run_schedule_now=stub)
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.post("/schedules/sched-1/run-now")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "schedule_id": "sched-1"}
    stub.assert_called_once_with("sched-1")


def test_post_schedule_run_now_returns_ok_false_when_not_attached() -> None:
    cp = GatewayControlPlane()  # run_schedule_now not wired
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        response = client.post("/schedules/sched-1/run-now")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
