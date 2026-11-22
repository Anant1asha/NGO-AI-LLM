"""Hardening tests for Calendar (UC-CAL-001..005) and Tasks (UC-TASK-001..003).

All HTTP is replaced by a FakeGoogleClient — no real OAuth or network required.
Approval gating is exercised via a fake require_approval on the client.
"""

from __future__ import annotations

from typing import Any

from hachi.integrations.google.calendar import CalendarService
from hachi.integrations.google.tasks import TasksService

# ---------------------------------------------------------------------------
# Fake HTTP client
# ---------------------------------------------------------------------------


class FakeGoogleClient:
    """Injectable stand-in for GoogleHTTPClient."""

    def __init__(self, approval_result: tuple[bool, str] = (True, "approved")) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self._responses: dict[str, Any] = {}
        self._approval_result = approval_result

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
        return self._approval_result


def _cal(client: FakeGoogleClient | None = None) -> CalendarService:
    return CalendarService(client=client or FakeGoogleClient())  # type: ignore[arg-type]


def _tasks(client: FakeGoogleClient | None = None) -> TasksService:
    return TasksService(client=client or FakeGoogleClient())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# UC-CAL-005 — delete_event requires approval
# ---------------------------------------------------------------------------


def test_delete_event_denied_makes_no_api_call() -> None:
    """When approval is denied, the Google API must NOT be called."""
    client = FakeGoogleClient(approval_result=(False, "User declined"))
    result = _cal(client).delete_event("evt-abc")
    assert "not approved" in result.lower() or "⛔" in result
    deletes = [c for c in client.calls if c[0] == "DELETE"]
    assert not deletes, "DELETE was called despite approval being denied"


def test_delete_event_approved_calls_api() -> None:
    """When approval is granted, the Google API should be called."""
    client = FakeGoogleClient(approval_result=(True, "approved"))
    result = _cal(client).delete_event("evt-xyz")
    assert "deleted" in result.lower()
    deletes = [c for c in client.calls if c[0] == "DELETE"]
    assert deletes and "evt-xyz" in deletes[0][1]


# ---------------------------------------------------------------------------
# UC-TASK-003 — delete_task requires approval
# ---------------------------------------------------------------------------


def test_delete_task_denied_makes_no_api_call() -> None:
    """When approval is denied, the Google Tasks API must NOT be called."""
    client = FakeGoogleClient(approval_result=(False, "Denied by policy"))
    result = _tasks(client).delete_task("task-123")
    assert "not approved" in result.lower() or "⛔" in result
    deletes = [c for c in client.calls if c[0] == "DELETE"]
    assert not deletes, "DELETE was called despite approval being denied"


def test_delete_task_approved_calls_api() -> None:
    """When approval is granted, the task should be deleted."""
    client = FakeGoogleClient(approval_result=(True, "approved"))
    result = _tasks(client).delete_task("task-456")
    assert "deleted" in result.lower()
    deletes = [c for c in client.calls if c[0] == "DELETE"]
    assert deletes and "task-456" in deletes[0][1]


# ---------------------------------------------------------------------------
# UC-CAL-002 — invalid datetime and end-before-start rejected
# ---------------------------------------------------------------------------


def test_create_event_invalid_start_datetime_rejected() -> None:
    client = FakeGoogleClient()
    result = _cal(client).create_calendar_event(
        title="Bad Date",
        start_time_iso="2026-13-01T10:00:00Z",  # month 13 — invalid
        end_time_iso="2026-12-01T11:00:00Z",
    )
    assert "❌" in result or "invalid" in result.lower()
    assert not client.calls  # no API call should have been made


def test_create_event_not_a_date_rejected() -> None:
    client = FakeGoogleClient()
    result = _cal(client).create_calendar_event(
        title="Junk",
        start_time_iso="not-a-date",
        end_time_iso="2026-06-15T11:00:00Z",
    )
    assert "❌" in result or "invalid" in result.lower()
    assert not client.calls


def test_create_event_end_before_start_rejected() -> None:
    client = FakeGoogleClient()
    result = _cal(client).create_calendar_event(
        title="Backward",
        start_time_iso="2026-06-15T12:00:00Z",
        end_time_iso="2026-06-15T10:00:00Z",  # end before start
    )
    assert "❌" in result or "after" in result.lower()
    assert not client.calls


def test_update_event_end_before_start_rejected() -> None:
    client = FakeGoogleClient()
    result = _cal(client).update_event(
        "evt1",
        start_time_iso="2026-06-15T18:00:00Z",
        end_time_iso="2026-06-15T09:00:00Z",  # end before start
    )
    assert "❌" in result or "after" in result.lower()
    assert not client.calls


# ---------------------------------------------------------------------------
# UC-CAL-003 — invalid RRULE rejected
# ---------------------------------------------------------------------------


def test_create_recurring_event_invalid_rrule_rejected() -> None:
    client = FakeGoogleClient()
    result = _cal(client).create_recurring_event(
        title="Bad Rule",
        start_time_iso="2026-06-15T10:00:00Z",
        end_time_iso="2026-06-15T11:00:00Z",
        recurrence_rule="RRULE:FREQ=NONSENSE",  # invalid FREQ value
    )
    assert "❌" in result or "invalid" in result.lower()
    assert not client.calls


def test_create_recurring_event_missing_freq_rejected() -> None:
    client = FakeGoogleClient()
    result = _cal(client).create_recurring_event(
        title="No Freq",
        start_time_iso="2026-06-15T10:00:00Z",
        end_time_iso="2026-06-15T11:00:00Z",
        recurrence_rule="RRULE:INTERVAL=2",  # missing FREQ
    )
    assert "❌" in result or "invalid" in result.lower()
    assert not client.calls


def test_create_recurring_event_valid_rrule_accepted() -> None:
    client = FakeGoogleClient()
    client.add_response(
        "POST",
        "/calendar/v3/calendars/primary/events",
        {"htmlLink": "https://cal.example.com/e/1"},
    )
    result = _cal(client).create_recurring_event(
        title="Weekly Sync",
        start_time_iso="2026-06-15T10:00:00+05:30",
        end_time_iso="2026-06-15T10:30:00+05:30",
        recurrence_rule="RRULE:FREQ=WEEKLY;BYDAY=MO",
    )
    assert "Recurring event created" in result
    assert client.calls  # API was called


# ---------------------------------------------------------------------------
# UC-TASK-002 — invalid due date rejected
# ---------------------------------------------------------------------------


def test_create_task_invalid_due_date_rejected() -> None:
    client = FakeGoogleClient()
    result = _tasks(client).create_task("Write specs", due_date_iso="2026-06-32")
    assert "❌" in result or "invalid" in result.lower()
    assert not client.calls


def test_create_task_valid_due_date_accepted() -> None:
    client = FakeGoogleClient()
    client.add_response("POST", "/tasks/v1/lists/@default/tasks", {"id": "tid1"})
    result = _tasks(client).create_task("Ship it", due_date_iso="2026-06-30")
    assert "tid1" in result
    _, _, kwargs = client.calls[0]
    assert kwargs["json_data"]["due"] == "2026-06-30T00:00:00Z"


def test_update_task_invalid_due_date_rejected() -> None:
    client = FakeGoogleClient()
    result = _tasks(client).update_task("t1", due_date_iso="not-a-date")
    assert "❌" in result or "invalid" in result.lower()
    assert not client.calls


# ---------------------------------------------------------------------------
# UC-CAL-001 — non-UTC timezone honored in create payload
# ---------------------------------------------------------------------------


def test_create_event_timezone_honored_in_payload() -> None:
    """The explicit timezone should appear in start/end timeZone fields."""
    client = FakeGoogleClient()
    client.add_response("POST", "/calendar/v3/calendars/primary/events", {"htmlLink": ""})
    _cal(client).create_calendar_event(
        title="IST Meeting",
        start_time_iso="2026-06-15T10:00:00+05:30",
        end_time_iso="2026-06-15T11:00:00+05:30",
        timezone="Asia/Kolkata",
    )
    post = [c for c in client.calls if c[0] == "POST"][0]
    event_body = post[2].get("json_data", {})
    assert event_body["start"]["timeZone"] == "Asia/Kolkata"
    assert event_body["end"]["timeZone"] == "Asia/Kolkata"


def test_create_recurring_event_timezone_honored() -> None:
    """The explicit timezone should appear in start/end of a recurring event."""
    client = FakeGoogleClient()
    client.add_response("POST", "/calendar/v3/calendars/primary/events", {"htmlLink": ""})
    _cal(client).create_recurring_event(
        title="Daily Standup",
        start_time_iso="2026-06-15T09:00:00-05:00",
        end_time_iso="2026-06-15T09:15:00-05:00",
        recurrence_rule="RRULE:FREQ=DAILY",
        timezone="America/Chicago",
    )
    post = [c for c in client.calls if c[0] == "POST"][0]
    event_body = post[2].get("json_data", {})
    assert event_body["start"]["timeZone"] == "America/Chicago"
    assert event_body["end"]["timeZone"] == "America/Chicago"


def test_create_event_invalid_attendee_email_rejected() -> None:
    """UC-CAL-001: invalid attendee emails should be caught before the API call."""
    client = FakeGoogleClient()
    result = _cal(client).create_calendar_event(
        title="Bad Attendee",
        start_time_iso="2026-06-15T10:00:00Z",
        end_time_iso="2026-06-15T11:00:00Z",
        attendees=["alice@example.com", "not-an-email"],
    )
    assert "❌" in result or "invalid" in result.lower()
    assert not client.calls


# ---------------------------------------------------------------------------
# UC-TASK-001 — pagination token surfaced
# ---------------------------------------------------------------------------


def test_list_tasks_next_page_token_surfaced() -> None:
    """When the API returns a nextPageToken, it should appear in the output."""
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/tasks/v1/lists/@default/tasks",
        {
            "items": [{"id": "t1", "title": "First task", "status": "needsAction"}],
            "nextPageToken": "TOKEN_XYZ",
        },
    )
    result = _tasks(client).list_tasks()
    assert "TOKEN_XYZ" in result
    assert "more" in result.lower() or "next" in result.lower() or "page" in result.lower()


def test_list_tasks_page_token_sent_to_api() -> None:
    """Providing a page_token should forward it to the API params."""
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/tasks/v1/lists/@default/tasks",
        {"items": [{"id": "t2", "title": "Second page", "status": "needsAction"}]},
    )
    _tasks(client).list_tasks(page_token="TOKEN_XYZ")
    _, _, kwargs = client.calls[0]
    assert kwargs["params"].get("pageToken") == "TOKEN_XYZ"


def test_list_tasks_no_next_token_when_last_page() -> None:
    """When there is no nextPageToken, the result should not mention pagination."""
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/tasks/v1/lists/@default/tasks",
        {"items": [{"id": "t3", "title": "Only task", "status": "needsAction"}]},
    )
    result = _tasks(client).list_tasks()
    assert "TOKEN" not in result
    assert "page_token" not in result
