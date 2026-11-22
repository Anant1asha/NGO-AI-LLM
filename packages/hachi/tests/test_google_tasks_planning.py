"""Offline tests for Google Tasks and Day-Planning services.

Uses the same FakeGoogleClient pattern as test_google_integrations.py.
No real OAuth or network calls; all HTTP is captured and stubbed.
"""

from __future__ import annotations

from typing import Any  # noqa: UP035

from hachi.core.loop import ToolRegistry
from hachi.integrations.google.calendar import CalendarService
from hachi.integrations.google.planning import PlanningService
from hachi.integrations.google.tasks import TasksService

# ---------------------------------------------------------------------------
# Shared fake client (mirrors test_google_integrations.FakeGoogleClient)
# ---------------------------------------------------------------------------


class FakeGoogleClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self._responses: dict[str, Any] = {}

    def add_response(self, method: str, endpoint: str, data: Any = None) -> None:
        self._responses[f"{method.upper()}:{endpoint}"] = data or {}

    def _record(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        self.calls.append((method.upper(), endpoint, kwargs))
        key = f"{method.upper()}:{endpoint}"
        if key in self._responses:
            return self._responses[key]
        for k, v in self._responses.items():
            m, ep = k.split(":", 1)
            if m == method.upper() and endpoint.startswith(ep):
                return v
        return {}

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        return self._record("GET", endpoint, params=params)

    def post(
        self,
        endpoint: str,
        json_data: dict | None = None,
        params: dict | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict:
        # idempotency_key accepted (the real client dedups on it) but not recorded, so
        # existing .calls assertions stay stable.
        return self._record("POST", endpoint, json_data=json_data, params=params)

    def patch(
        self, endpoint: str, json_data: dict | None = None, params: dict | None = None
    ) -> dict:
        return self._record("PATCH", endpoint, json_data=json_data, params=params)

    def delete(self, endpoint: str, params: dict | None = None) -> None:
        self._record("DELETE", endpoint, params=params)

    def require_approval(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Always approve in unit tests — approval gating is tested in hardening suite."""
        return (True, "auto-approved in test")


def _tasks(client: FakeGoogleClient | None = None) -> TasksService:
    return TasksService(client=client or FakeGoogleClient())  # type: ignore[arg-type]


def _planning(client: FakeGoogleClient | None = None) -> PlanningService:
    return PlanningService(client=client or FakeGoogleClient())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TasksService — list_task_lists
# ---------------------------------------------------------------------------


def test_list_task_lists_empty() -> None:
    client = FakeGoogleClient()
    client.add_response("GET", "/tasks/v1/users/@me/lists", {"items": []})
    assert "No task lists" in _tasks(client).list_task_lists()


def test_list_task_lists_returns_titles() -> None:
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/tasks/v1/users/@me/lists",
        {"items": [{"id": "tid1", "title": "Work"}, {"id": "tid2", "title": "Personal"}]},
    )
    result = _tasks(client).list_task_lists()
    assert "Work" in result
    assert "Personal" in result


# ---------------------------------------------------------------------------
# TasksService — list_tasks
# ---------------------------------------------------------------------------


def test_list_tasks_empty() -> None:
    client = FakeGoogleClient()
    client.add_response("GET", "/tasks/v1/lists/@default/tasks", {"items": []})
    assert "No tasks" in _tasks(client).list_tasks()


def test_list_tasks_shows_title_and_status() -> None:
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/tasks/v1/lists/@default/tasks",
        {
            "items": [
                {"id": "t1", "title": "Write tests", "status": "needsAction"},
                {"id": "t2", "title": "Ship it", "status": "completed"},
            ]
        },
    )
    result = _tasks(client).list_tasks(show_completed=True)
    assert "Write tests" in result
    assert "Ship it" in result
    assert "✓" in result  # completed indicator
    assert "○" in result  # pending indicator


def test_list_tasks_shows_due_date() -> None:
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/tasks/v1/lists/@default/tasks",
        {
            "items": [
                {
                    "id": "t1",
                    "title": "Review PR",
                    "status": "needsAction",
                    "due": "2026-06-10T00:00:00Z",
                }
            ]
        },
    )
    result = _tasks(client).list_tasks()
    assert "2026-06-10" in result


# ---------------------------------------------------------------------------
# TasksService — create_task
# ---------------------------------------------------------------------------


def test_create_task_posts_to_api() -> None:
    client = FakeGoogleClient()
    client.add_response("POST", "/tasks/v1/lists/@default/tasks", {"id": "new-task-id"})
    result = _tasks(client).create_task("Deploy to prod")
    assert "Deploy to prod" in result
    assert "new-task-id" in result
    method, endpoint, kwargs = client.calls[0]
    assert method == "POST"
    assert kwargs["json_data"]["title"] == "Deploy to prod"


def test_create_task_appends_T_to_bare_date() -> None:
    client = FakeGoogleClient()
    client.add_response("POST", "/tasks/v1/lists/@default/tasks", {"id": "x"})
    _tasks(client).create_task("Do thing", due_date_iso="2026-07-01")
    _, _, kwargs = client.calls[0]
    assert "T" in kwargs["json_data"]["due"]


# ---------------------------------------------------------------------------
# TasksService — complete / delete / update
# ---------------------------------------------------------------------------


def test_complete_task_patches_status() -> None:
    client = FakeGoogleClient()
    result = _tasks(client).complete_task("t1")
    assert "completed" in result.lower()
    method, endpoint, kwargs = client.calls[0]
    assert method == "PATCH"
    assert kwargs["json_data"]["status"] == "completed"


def test_delete_task_calls_delete() -> None:
    client = FakeGoogleClient()
    result = _tasks(client).delete_task("t1")
    assert "deleted" in result.lower()
    assert client.calls[0][0] == "DELETE"


def test_update_task_nothing_to_update() -> None:
    client = FakeGoogleClient()
    result = _tasks(client).update_task("t1")
    assert "Nothing to update" in result
    assert not client.calls  # no HTTP call made


def test_update_task_patches_title() -> None:
    client = FakeGoogleClient()
    _tasks(client).update_task("t1", title="New name")
    method, endpoint, kwargs = client.calls[0]
    assert method == "PATCH"
    assert kwargs["json_data"]["title"] == "New name"


# ---------------------------------------------------------------------------
# TasksService — tool registration
# ---------------------------------------------------------------------------


def test_tasks_registers_expected_tools() -> None:
    registry = ToolRegistry()
    svc = _tasks()
    svc.register_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert "google_list_task_lists" in names
    assert "google_list_tasks" in names
    assert "google_create_task" in names
    assert "google_complete_task" in names
    assert "google_update_task" in names
    assert "google_delete_task" in names


# ---------------------------------------------------------------------------
# CalendarService — new tools (imported here to keep tests alongside Tasks)
# ---------------------------------------------------------------------------


def _cal(client: FakeGoogleClient | None = None) -> CalendarService:
    return CalendarService(client=client or FakeGoogleClient())  # type: ignore[arg-type]


def test_create_recurring_event_sends_rrule() -> None:
    client = FakeGoogleClient()
    client.add_response(
        "POST",
        "/calendar/v3/calendars/primary/events",
        {"htmlLink": "https://cal.example.com/e/1"},
    )
    result = _cal(client).create_recurring_event(
        title="Weekly Standup",
        start_time_iso="2026-06-09T10:00:00+05:30",
        end_time_iso="2026-06-09T10:30:00+05:30",
        recurrence_rule="RRULE:FREQ=WEEKLY;BYDAY=MO",
    )
    assert "Recurring event created" in result
    assert "RRULE:FREQ=WEEKLY;BYDAY=MO" in result
    _, _, kwargs = client.calls[0]
    assert "RRULE:FREQ=WEEKLY;BYDAY=MO" in kwargs["json_data"]["recurrence"]


def test_get_events_for_date_empty() -> None:
    client = FakeGoogleClient()
    client.add_response("GET", "/calendar/v3/calendars/primary/events", {"items": []})
    result = _cal(client).get_events_for_date("2026-06-09")
    assert "No events" in result


def test_get_events_for_date_formats_time() -> None:
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/calendar/v3/calendars/primary/events",
        {
            "items": [
                {
                    "summary": "Q3 Review",
                    "start": {"dateTime": "2026-06-09T14:00:00Z"},
                    "end": {"dateTime": "2026-06-09T15:00:00Z"},
                    "id": "ev1",
                }
            ]
        },
    )
    result = _cal(client).get_events_for_date("2026-06-09")
    assert "Q3 Review" in result
    assert "14:00" in result
    assert "15:00" in result


def test_calendar_registers_new_tools() -> None:
    registry = ToolRegistry()
    svc = _cal()
    svc.register_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert "google_create_recurring_event" in names
    assert "google_get_events_for_date" in names


# ---------------------------------------------------------------------------
# PlanningService — plan_my_day
# ---------------------------------------------------------------------------


def _plan_client_with_full_data() -> FakeGoogleClient:
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/calendar/v3/calendars/primary/events",
        {
            "items": [
                {
                    "summary": "Standup",
                    "start": {"dateTime": "2026-06-09T09:00:00Z"},
                    "end": {"dateTime": "2026-06-09T09:30:00Z"},
                    "id": "ev1",
                }
            ]
        },
    )
    client.add_response(
        "GET",
        "/gmail/v1/users/me/messages",
        {
            "messages": [{"id": "m1"}],
            "resultSizeEstimate": 1,
        },
    )
    client.add_response(
        "GET",
        "/gmail/v1/users/me/messages/m1",
        {
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Urgent: server down"},
                    {"name": "From", "value": "ops@example.com"},
                ]
            }
        },
    )
    client.add_response(
        "GET",
        "/tasks/v1/lists/@default/tasks",
        {"items": [{"id": "t1", "title": "Fix the bug", "status": "needsAction"}]},
    )
    return client


def test_plan_my_day_contains_all_sections() -> None:
    client = _plan_client_with_full_data()
    result = _planning(client).plan_my_day(date_iso="2026-06-09")
    assert "Calendar" in result
    assert "Standup" in result
    assert "Inbox" in result
    assert "Urgent: server down" in result
    assert "Tasks" in result
    assert "Fix the bug" in result


def test_plan_my_day_skips_email_when_disabled() -> None:
    client = _plan_client_with_full_data()
    result = _planning(client).plan_my_day(date_iso="2026-06-09", include_email=False)
    assert "Inbox" not in result


def test_plan_my_day_skips_tasks_when_disabled() -> None:
    client = _plan_client_with_full_data()
    result = _planning(client).plan_my_day(date_iso="2026-06-09", include_tasks=False)
    assert "Tasks" not in result


def test_plan_my_day_defaults_to_today() -> None:
    import datetime

    client = _plan_client_with_full_data()
    _planning(client).plan_my_day()  # no date_iso
    today = datetime.date.today().isoformat()
    # The calendar API should have been called with today's date in timeMin.
    cal_call = next(
        (c for c in client.calls if "/calendar/v3/calendars/primary/events" in c[1]), None
    )
    assert cal_call is not None
    params = cal_call[2].get("params", {})
    assert today in str(params.get("timeMin", ""))


def test_planning_registers_plan_my_day_tool() -> None:
    registry = ToolRegistry()
    svc = _planning()
    svc.register_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert "google_plan_my_day" in names


# ---------------------------------------------------------------------------
# GoogleIntegrationHub — all services present
# ---------------------------------------------------------------------------


def test_hub_includes_tasks_and_planning_tools() -> None:
    """Verify the hub wires TasksService and PlanningService without importing OAuth."""
    from unittest.mock import MagicMock, patch

    from hachi.core.loop import ToolRegistry

    fake_client = MagicMock()
    fake_client.oauth = MagicMock()
    fake_client.scopes = []

    with (
        patch("hachi.integrations.google.client.GoogleHTTPClient", return_value=fake_client),
        patch("hachi.core.oauth.OAuthManager"),
    ):
        from hachi.integrations.google import GoogleIntegrationHub

        hub = GoogleIntegrationHub()
        registry = ToolRegistry()
        hub.register_tools(registry)

    names = {s["name"] for s in registry.get_schemas()}
    assert "google_create_task" in names
    assert "google_plan_my_day" in names
    assert "google_create_recurring_event" in names
