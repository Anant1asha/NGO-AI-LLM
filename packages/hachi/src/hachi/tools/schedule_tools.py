"""Scheduling tools — let the agent set up proactive, recurring tasks.

These expose the :class:`~hachi.jobs.scheduler.Scheduler` to the LLM so it can
schedule work to run later or on a recurring basis (cron / interval / one-shot),
delivered to chat or a webhook. A separate runner (the ``hachi schedule
run-due`` command or a daemon) actually fires due schedules through the agent.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from hachi.core.loop import ToolRegistry
from hachi.jobs.scheduler import Scheduler


def _make_schedule_task(scheduler: Scheduler) -> Callable[..., str]:
    def schedule_task(
        name: str,
        task: str,
        kind: str,
        cron: str | None = None,
        interval_seconds: int | None = None,
        run_at: str | None = None,
        deliver_to: str = "chat",
        webhook_url: str | None = None,
    ) -> str:
        try:
            schedule = scheduler.add(
                name=name,
                task=task,
                kind=kind,
                cron=cron,
                interval_seconds=interval_seconds,
                run_at=run_at,
                deliver_to=deliver_to,
                webhook_url=webhook_url,
            )
        except ValueError as e:
            return json.dumps({"status": "error", "reason": str(e)})
        return json.dumps(
            {
                "status": "scheduled",
                "schedule_id": schedule.schedule_id,
                "name": schedule.name,
                "next_run": schedule.next_run,
            },
            indent=2,
        )

    return schedule_task


def _make_list_schedules(scheduler: Scheduler) -> Callable[[], str]:
    def list_schedules() -> str:
        items = [
            {
                "schedule_id": s.schedule_id,
                "name": s.name,
                "kind": s.kind.value,
                "task": s.task,
                "next_run": s.next_run,
                "enabled": s.enabled,
                "run_count": s.run_count,
            }
            for s in scheduler.list_schedules()
        ]
        if not items:
            return "No schedules are configured."
        return json.dumps(items, indent=2)

    return list_schedules


def _make_cancel_schedule(scheduler: Scheduler) -> Callable[[str], str]:
    def cancel_schedule(schedule_id: str) -> str:
        ok = scheduler.cancel(schedule_id)
        return json.dumps(
            {"status": "cancelled" if ok else "not_found", "schedule_id": schedule_id}
        )

    return cancel_schedule


SCHEDULE_TASK_SCHEMA = {
    "name": "create_schedule",
    "description": (
        "Create a proactive schedule — run a task later or on a recurring basis without the user "
        "having to ask each time. Use for reminders, daily briefings, periodic checks, etc. "
        "Choose kind='cron' with a 5-field cron expression (e.g. '0 9 * * 1-5' = weekdays 9am), "
        "kind='interval' with interval_seconds, or kind='once' with run_at (ISO datetime). The "
        "`task` is the instruction you'll be given when it fires. Times are UTC."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Short human-readable schedule name."},
            "task": {
                "type": "string",
                "description": "The instruction to execute when the schedule fires.",
            },
            "kind": {
                "type": "string",
                "enum": ["cron", "interval", "once"],
                "description": "Recurrence type.",
            },
            "cron": {"type": "string", "description": "5-field cron expression (kind='cron')."},
            "interval_seconds": {
                "type": "integer",
                "description": "Seconds between runs (kind='interval').",
            },
            "run_at": {
                "type": "string",
                "description": "ISO datetime for a one-shot run (kind='once').",
            },
            "deliver_to": {
                "type": "string",
                "enum": ["chat", "webhook", "log"],
                "description": "Where the result is delivered (default chat).",
            },
            "webhook_url": {
                "type": "string",
                "description": "Webhook URL when deliver_to='webhook'.",
            },
        },
        "required": ["name", "task", "kind"],
    },
}

LIST_SCHEDULES_SCHEMA = {
    "name": "list_schedules",
    "description": "List all configured proactive schedules and when each next runs.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

CANCEL_SCHEDULE_SCHEMA = {
    "name": "delete_schedule",
    "description": (
        "Delete (cancel/remove) a proactive schedule by its schedule_id. "
        "Also callable as cancel_schedule. Use list_schedules first to find the id."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "schedule_id": {"type": "string", "description": "The id of the schedule to cancel."}
        },
        "required": ["schedule_id"],
    },
}


_CANCEL_ALIAS_SCHEMA = {
    **CANCEL_SCHEDULE_SCHEMA,
    "name": "cancel_schedule",
    "description": "Alias for delete_schedule — cancel a proactive schedule by its schedule_id.",
}


def register_schedule_tools(registry: ToolRegistry, scheduler: Scheduler) -> None:
    """Mount the scheduling tools onto the provided ToolRegistry."""
    registry.register(SCHEDULE_TASK_SCHEMA, _make_schedule_task(scheduler))
    registry.register(LIST_SCHEDULES_SCHEMA, _make_list_schedules(scheduler))
    registry.register(CANCEL_SCHEDULE_SCHEMA, _make_cancel_schedule(scheduler))
    registry.register(_CANCEL_ALIAS_SCHEMA, _make_cancel_schedule(scheduler))
