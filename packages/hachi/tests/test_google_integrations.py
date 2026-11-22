"""Offline tests for Gmail and Google Calendar service layer + tool classification.

HTTP is replaced by a FakeGoogleClient that captures calls and returns canned
responses — no real OAuth or network access required.
"""

from __future__ import annotations

from typing import Any

from hachi.core.loop import ToolRegistry
from hachi.integrations.google.calendar import CalendarService
from hachi.integrations.google.gmail import GmailService

# ---------------------------------------------------------------------------
# Fake HTTP client (no OAuth, no network)
# ---------------------------------------------------------------------------


class FakeGoogleClient:
    """Injectable stand-in for GoogleHTTPClient.

    Pre-set responses with ``add_response(method, endpoint, data)``; call
    ``calls`` to inspect what the service posted/got.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self._responses: dict[str, Any] = {}

    def add_response(self, method: str, endpoint: str, data: Any = None) -> None:
        self._responses[f"{method.upper()}:{endpoint}"] = data or {}

    def _record(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        self.calls.append((method.upper(), endpoint, kwargs))
        key = f"{method.upper()}:{endpoint}"
        # Exact match first, then prefix match.
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


# ---------------------------------------------------------------------------
# Gmail tests
# ---------------------------------------------------------------------------


def _gmail(client: FakeGoogleClient | None = None) -> GmailService:
    return GmailService(client=client or FakeGoogleClient())  # type: ignore[arg-type]


def test_gmail_list_emails_empty_inbox():
    client = FakeGoogleClient()
    client.add_response("GET", "/gmail/v1/users/me/messages", {"messages": []})
    svc = _gmail(client)
    result = svc.list_recent_emails()
    assert "empty" in result.lower()


def test_gmail_list_emails_returns_sender_and_subject():
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/gmail/v1/users/me/messages",
        {"messages": [{"id": "msg1"}]},
    )
    client.add_response(
        "GET",
        "/gmail/v1/users/me/messages/msg1",
        {
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hello World"},
                    {"name": "From", "value": "alice@example.com"},
                ]
            }
        },
    )
    svc = _gmail(client)
    result = svc.list_recent_emails()
    assert "Hello World" in result
    assert "alice@example.com" in result
    assert "msg1" in result


def test_gmail_search_emails_no_results():
    client = FakeGoogleClient()
    client.add_response("GET", "/gmail/v1/users/me/messages", {"messages": []})
    svc = _gmail(client)
    result = svc.search_emails("label:important")
    assert "No emails found" in result


def test_gmail_search_emails_returns_results():
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/gmail/v1/users/me/messages",
        {"messages": [{"id": "m2"}]},
    )
    client.add_response(
        "GET",
        "/gmail/v1/users/me/messages/m2",
        {
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Invoice"},
                    {"name": "From", "value": "billing@acme.com"},
                ]
            }
        },
    )
    svc = _gmail(client)
    result = svc.search_emails("from:billing@acme.com")
    assert "Invoice" in result


def test_gmail_send_email_posts_to_correct_endpoint():
    client = FakeGoogleClient()
    svc = _gmail(client)
    result = svc.send_email("bob@example.com", "Hi", "Hello Bob")
    assert "successfully sent" in result.lower()
    sent = [c for c in client.calls if c[0] == "POST"]
    assert sent
    assert "/gmail/v1/users/me/messages/send" in sent[0][1]
    # Payload should contain base64-encoded raw email
    payload = sent[0][2].get("json_data", {})
    assert "raw" in payload


def test_gmail_send_email_with_missing_attachment_returns_error(tmp_path):
    client = FakeGoogleClient()
    svc = _gmail(client)
    result = svc.send_email("bob@example.com", "Hi", "Body", ["/no/such/file.pdf"])
    assert "not found" in result.lower() or "Failed" in result


def test_gmail_archive_email():
    client = FakeGoogleClient()
    svc = _gmail(client)
    result = svc.archive_email("msg42")
    assert "archived" in result.lower()
    mod = [c for c in client.calls if "/modify" in c[1]]
    assert mod
    labels = mod[0][2].get("json_data", {})
    assert "INBOX" in labels.get("removeLabelIds", [])


def test_gmail_mark_email_read():
    client = FakeGoogleClient()
    svc = _gmail(client)
    result = svc.mark_email_read("msg99")
    assert "read" in result.lower()
    mod = [c for c in client.calls if "/modify" in c[1]]
    assert mod
    labels = mod[0][2].get("json_data", {})
    assert "UNREAD" in labels.get("removeLabelIds", [])


def test_gmail_create_draft_posts_to_drafts():
    client = FakeGoogleClient()
    client.add_response("POST", "/gmail/v1/users/me/drafts", {"id": "d1"})
    svc = _gmail(client)
    result = svc.create_draft("to@example.com", "Draft", "body text")
    assert "d1" in result
    assert "Draft" in result or "draft" in result.lower()


def test_gmail_list_labels_returns_labels():
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/gmail/v1/users/me/labels",
        {"labels": [{"name": "INBOX", "id": "INBOX"}, {"name": "Newsletters", "id": "Label_1"}]},
    )
    svc = _gmail(client)
    result = svc.list_labels()
    assert "INBOX" in result
    assert "Newsletters" in result


def test_gmail_register_tools_names():
    registry = ToolRegistry()
    svc = _gmail()
    svc.register_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert "google_send_email" in names
    assert "google_list_emails" in names
    assert "google_search_emails" in names
    assert "google_create_draft" in names
    assert "google_reply_thread" in names
    assert "google_read_email_thread" in names
    assert "google_archive_email" in names
    assert "google_mark_email_read" in names
    assert "google_list_gmail_labels" in names
    assert "google_create_gmail_label" in names
    assert "google_categorize_email" in names
    assert "google_batch_categorize_emails" in names


def _b64(text: str) -> str:
    import base64

    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")


def test_read_email_thread_strips_html_body():
    html = (
        '<table style="width:600px"><tr><td>Hello <b>World</b></td></tr></table>'
        "<p>Sale ends soon</p>"
    )
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/gmail/v1/users/me/threads/t1",
        {
            "messages": [
                {
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "shop@example.com"},
                            {"name": "Date", "value": "Mon, 1 Jun 2026"},
                        ],
                        "mimeType": "text/html",
                        "body": {"data": _b64(html)},
                    }
                }
            ]
        },
    )
    result = _gmail(client).read_email_thread("t1")
    assert "Hello World" in result
    assert "Sale ends soon" in result
    assert "<table" not in result and "<b>" not in result


def test_read_email_thread_prefers_plain_text():
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/gmail/v1/users/me/threads/t2",
        {
            "messages": [
                {
                    "payload": {
                        "headers": [{"name": "From", "value": "a@b.com"}],
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {"mimeType": "text/plain", "body": {"data": _b64("Plain wins")}},
                            {"mimeType": "text/html", "body": {"data": _b64("<p>HTML</p>")}},
                        ],
                    }
                }
            ]
        },
    )
    result = _gmail(client).read_email_thread("t2")
    assert "Plain wins" in result
    assert "HTML" not in result


def test_read_email_thread_falls_back_to_message_on_404():
    """When the id is actually a message id, the thread endpoint 404s; recover."""

    class Fake404Client(FakeGoogleClient):
        def get(self, endpoint: str, params: dict | None = None) -> dict:
            self.calls.append(("GET", endpoint, {"params": params}))
            if "/threads/" in endpoint:
                raise RuntimeError(
                    f"Google API error 404 for {endpoint}: Requested entity was not found."
                )
            return self._responses.get(f"GET:{endpoint}", {})

    client = Fake404Client()
    client.add_response(
        "GET",
        "/gmail/v1/users/me/messages/19ebcacbaba8a3d2",
        {
            "payload": {
                "headers": [{"name": "From", "value": "news@taaft.com"}],
                "mimeType": "text/plain",
                "body": {"data": _b64("Single message body")},
            }
        },
    )
    result = _gmail(client).read_email_thread("19ebcacbaba8a3d2")
    assert "Single message body" in result
    assert "news@taaft.com" in result
    # It tried the thread endpoint first, then fell back to the message endpoint.
    assert any("/messages/19ebcacbaba8a3d2" in c[1] for c in client.calls)


# ---------------------------------------------------------------------------
# Calendar tests
# ---------------------------------------------------------------------------


def _cal(client: FakeGoogleClient | None = None) -> CalendarService:
    return CalendarService(client=client or FakeGoogleClient())  # type: ignore[arg-type]


def test_calendar_list_events_empty():
    client = FakeGoogleClient()
    client.add_response("GET", "/calendar/v3/calendars/primary/events", {"items": []})
    svc = _cal(client)
    result = svc.get_upcoming_events()
    assert "No upcoming events" in result


def test_calendar_list_events_returns_formatted():
    client = FakeGoogleClient()
    client.add_response(
        "GET",
        "/calendar/v3/calendars/primary/events",
        {
            "items": [
                {"summary": "Team Standup", "start": {"dateTime": "2026-06-10T09:00:00Z"}},
                {"summary": "Lunch", "start": {"date": "2026-06-10"}},
            ]
        },
    )
    svc = _cal(client)
    result = svc.get_upcoming_events()
    assert "Team Standup" in result
    assert "Lunch" in result
    assert "2026-06-10" in result


def test_calendar_create_event_returns_link():
    client = FakeGoogleClient()
    client.add_response(
        "POST",
        "/calendar/v3/calendars/primary/events",
        {"htmlLink": "https://calendar.google.com/event?eid=abc123"},
    )
    svc = _cal(client)
    result = svc.create_calendar_event(
        "Sprint Review", "2026-06-15T14:00:00+00:00", "2026-06-15T15:00:00+00:00"
    )
    assert "created successfully" in result.lower()
    assert "calendar.google.com" in result


def test_calendar_create_event_with_attendees():
    client = FakeGoogleClient()
    client.add_response("POST", "/calendar/v3/calendars/primary/events", {"htmlLink": ""})
    svc = _cal(client)
    svc.create_calendar_event(
        "Meeting",
        "2026-06-15T10:00:00Z",
        "2026-06-15T11:00:00Z",
        attendees=["alice@example.com", "bob@example.com"],
    )
    post = [c for c in client.calls if c[0] == "POST"][0]
    event_body = post[2].get("json_data", {})
    assert "attendees" in event_body
    emails = [a["email"] for a in event_body["attendees"]]
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails


def test_calendar_create_event_with_meet_link():
    client = FakeGoogleClient()
    client.add_response(
        "POST",
        "/calendar/v3/calendars/primary/events",
        {"htmlLink": "", "hangoutLink": "https://meet.google.com/abc-def-ghi"},
    )
    svc = _cal(client)
    result = svc.create_calendar_event(
        "Video Call",
        "2026-06-15T10:00:00Z",
        "2026-06-15T11:00:00Z",
        create_meet_link=True,
    )
    assert "meet.google.com" in result


def test_calendar_find_free_time_no_busy():
    client = FakeGoogleClient()
    client.add_response(
        "POST",
        "/calendar/v3/freeBusy",
        {"calendars": {"primary": {"busy": []}}},
    )
    svc = _cal(client)
    result = svc.find_free_time(duration_minutes=60, days_ahead=2)
    assert "free" in result.lower()


def test_calendar_find_free_time_with_busy():
    client = FakeGoogleClient()
    client.add_response(
        "POST",
        "/calendar/v3/freeBusy",
        {
            "calendars": {
                "primary": {
                    "busy": [{"start": "2026-06-15T09:00:00Z", "end": "2026-06-15T10:00:00Z"}]
                }
            }
        },
    )
    svc = _cal(client)
    result = svc.find_free_time()
    assert "Busy slots found" in result


def test_calendar_update_event():
    client = FakeGoogleClient()
    client.add_response("GET", "/calendar/v3/calendars/primary/events/evt1", {"summary": "Old"})
    client.add_response(
        "PATCH",
        "/calendar/v3/calendars/primary/events/evt1",
        {"htmlLink": "https://calendar.google.com/evt1"},
    )
    svc = _cal(client)
    result = svc.update_event("evt1", summary="New Title")
    assert "updated successfully" in result.lower()
    patch = [c for c in client.calls if c[0] == "PATCH"][0]
    assert patch[2].get("json_data", {}).get("summary") == "New Title"


def test_calendar_delete_event():
    client = FakeGoogleClient()
    svc = _cal(client)
    result = svc.delete_event("evt99")
    assert "deleted" in result.lower() or "evt99" in result
    deletes = [c for c in client.calls if c[0] == "DELETE"]
    assert deletes and "evt99" in deletes[0][1]


def test_calendar_register_tools_names():
    registry = ToolRegistry()
    svc = _cal()
    svc.register_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert "google_create_event" in names
    assert "google_list_events" in names
    assert "google_find_free_time" in names
    assert "google_update_event" in names
    assert "google_delete_event" in names


# ---------------------------------------------------------------------------
# classify() prefix_groups — google_* tools land in "google" group
# ---------------------------------------------------------------------------


def test_classify_prefix_groups_stamps_google_group():
    registry = ToolRegistry()
    client = FakeGoogleClient()
    GmailService(client=client).register_tools(registry)  # type: ignore[arg-type]
    CalendarService(client=client).register_tools(registry)  # type: ignore[arg-type]

    registry.classify(
        core_names=set(),
        group_by_name={},
        prefix_groups={"google_": "google"},
        default="integrations",
    )

    for name in {s["name"] for s in registry.get_schemas()}:
        if name.startswith("google_"):
            assert registry._groups[name] == "google", f"{name} not in 'google' group"


def test_classify_prefix_groups_does_not_override_explicit_group():
    """An explicitly-registered group should not be overwritten by prefix matching."""
    registry = ToolRegistry()
    registry.register({"name": "google_special"}, lambda: None, group="special")

    registry.classify(
        core_names=set(),
        group_by_name={},
        prefix_groups={"google_": "google"},
        default="integrations",
    )

    # "special" group was set explicitly; it should remain because classify only
    # touches tools that are still at the default "core" group.
    # (The tool was registered with group="special", not "core", so it survives.)
    assert registry._groups["google_special"] == "special"


def test_classify_longest_prefix_wins():
    registry = ToolRegistry()
    registry.register({"name": "google_gmail_special"}, lambda: None)  # starts at "core"

    registry.classify(
        core_names=set(),
        group_by_name={},
        prefix_groups={"google_": "google", "google_gmail_": "gmail"},
        default="integrations",
    )

    assert registry._groups["google_gmail_special"] == "gmail"
