"""Google Calendar Service Plugin."""

from __future__ import annotations

import datetime
import zoneinfo

from hachi.core.idempotency import make_idempotency_key
from hachi.core.loop import ToolRegistry
from hachi.core.validators import (
    validate_emails,
    validate_iso_datetime,
    validate_rrule,
    validate_time_range,
)
from hachi.integrations.google.service import GoogleService

# Fall back to UTC if the local timezone cannot be resolved.
_DEFAULT_TZ = "UTC"


def _local_timezone() -> str:
    """Return the local IANA timezone name, or UTC if it cannot be determined."""
    try:
        # Prefer zoneinfo.available_timezones lookup via datetime
        key = datetime.datetime.now().astimezone().tzinfo
        if hasattr(key, "key"):  # ZoneInfo objects expose .key
            return key.key  # type: ignore[union-attr]
        # Last resort: UTC
        return _DEFAULT_TZ
    except Exception:
        return _DEFAULT_TZ


class CalendarService(GoogleService):
    @property
    def required_scopes(self) -> list[str]:
        # calendar.events: create/update/delete events
        # calendar.readonly: needed for freeBusy queries (/calendar/v3/freeBusy)
        return [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.readonly",
        ]

    @staticmethod
    def _dt_field(iso: str, timezone: str = "") -> dict[str, str]:
        """Build a Calendar API dateTime object with an explicit timeZone.

        Google requires a named timeZone for recurring events even when the dateTime
        string already contains an offset or trailing 'Z'.  Including it for all
        event types is safe and avoids 400s on RRULE requests.

        Args:
            iso:      ISO-8601 datetime string.
            timezone: IANA timezone name to embed.  Falls back to the caller's
                      configured/local timezone, then UTC.
        """
        tz_name = timezone if timezone else _local_timezone()
        return {"dateTime": iso, "timeZone": tz_name}

    def create_calendar_event(
        self,
        title: str,
        start_time_iso: str,
        end_time_iso: str,
        description: str = "",
        create_meet_link: bool = False,
        attendees: list[str] | None = None,
        timezone: str = "",
    ) -> str:
        """Creates a Google Calendar event, optionally attaching a Google Meet link.

        Args:
            title:           Event title.
            start_time_iso:  Start time in ISO-8601 format.
            end_time_iso:    End time in ISO-8601 format.
            description:     Optional event description.
            create_meet_link: Attach a Google Meet link if True.
            attendees:       Optional list of attendee email addresses.
            timezone:        IANA timezone name (e.g. "America/New_York").  Defaults
                             to the system local timezone.
        """
        from typing import Any as _Any

        # UC-CAL-002: validate start/end datetimes and the range.
        ok_range, range_or_err = validate_time_range(start_time_iso, end_time_iso)
        if not ok_range:
            return f"❌ Invalid time range: {range_or_err}"

        # UC-CAL-001: validate attendee emails.
        normalized_attendees: list[str] | None = None
        if attendees:
            ok_emails, emails_or_err = validate_emails(attendees)
            if not ok_emails:
                return f"❌ {emails_or_err}"
            normalized_attendees = emails_or_err  # type: ignore[assignment]

        tz = timezone if timezone else _local_timezone()

        event: dict[str, _Any] = {
            "summary": title,
            "description": description,
            "start": self._dt_field(start_time_iso, tz),
            "end": self._dt_field(end_time_iso, tz),
        }

        if normalized_attendees:
            event["attendees"] = [{"email": email} for email in normalized_attendees]

        params: dict[str, _Any] = {}
        if create_meet_link:
            import uuid

            event["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
            params["conferenceDataVersion"] = 1

        response = self.client.post(
            "/calendar/v3/calendars/primary/events",
            params=params,
            json_data=event,
            # Key on the logical event (not the body — a Meet requestId is a random uuid),
            # so a retried create does not produce a duplicate event/invite.
            idempotency_key=make_idempotency_key(
                "calendar.create_event", title, f"{start_time_iso}\x00{end_time_iso}"
            ),
        )
        link = response.get("htmlLink", "")
        meet_link = response.get("hangoutLink", "")

        result = f"Event created successfully! Link: {link}"
        if meet_link:
            result += f"\nGoogle Meet Link: {meet_link}"

        return result

    def get_upcoming_events(self, max_results: int = 5) -> str:
        """Gets the next upcoming calendar events."""
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat() + "Z"

        response = self.client.get(
            "/calendar/v3/calendars/primary/events",
            params={
                "timeMin": now,
                "maxResults": max_results,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        events = response.get("items", [])

        if not events:
            return "No upcoming events found."

        result = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            result.append(f"[{start}] {e.get('summary', 'Busy')}")

        return "\n".join(result)

    def find_free_time(
        self,
        duration_minutes: int = 60,
        days_ahead: int = 3,
        timezone: str = "",
    ) -> str:
        """Scans the calendar to find the next available time slot.

        Args:
            duration_minutes: Desired meeting length in minutes.
            days_ahead:       How many calendar days to look ahead.
            timezone:         IANA timezone for interpreting working hours.  Defaults
                              to the system local timezone.
        """
        # UC-CAL-004: use the caller's timezone rather than blind UTC.
        tz_name = timezone if timezone else _local_timezone()
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except (zoneinfo.ZoneInfoNotFoundError, KeyError):
            tz_name = _DEFAULT_TZ
            tz = datetime.UTC

        now_local = datetime.datetime.now(tz)
        time_min = now_local.isoformat()
        time_max = (now_local + datetime.timedelta(days=days_ahead)).isoformat()

        response = self.client.post(
            "/calendar/v3/freeBusy",
            json_data={
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": "primary"}],
                "timeZone": tz_name,
            },
        )

        calendars = response.get("calendars", {})
        primary = calendars.get("primary", {})
        busy_slots = primary.get("busy", [])

        # Simplified logic: If there are no busy slots, now is free.
        if not busy_slots:
            return (
                f"The calendar is completely free for the next {days_ahead} days "
                f"starting from {time_min} ({tz_name})."
            )

        return (
            f"Busy slots found ({tz_name}): {busy_slots}. Please pick a time outside these windows."
        )

    def update_event(
        self,
        event_id: str,
        summary: str | None = None,
        start_time_iso: str | None = None,
        end_time_iso: str | None = None,
        timezone: str = "",
    ) -> str:
        """Updates an existing calendar event.

        Args:
            event_id:       ID of the event to update.
            summary:        New event title (optional).
            start_time_iso: New start time in ISO-8601 format (optional).
            end_time_iso:   New end time in ISO-8601 format (optional).
            timezone:       IANA timezone name to embed in updated times (optional).
        """
        # UC-CAL-002: validate datetimes if provided.
        if start_time_iso:
            ok, result_or_err = validate_iso_datetime(start_time_iso)
            if not ok:
                return f"❌ Invalid start_time_iso: {result_or_err}"
        if end_time_iso:
            ok, result_or_err = validate_iso_datetime(end_time_iso)
            if not ok:
                return f"❌ Invalid end_time_iso: {result_or_err}"
        if start_time_iso and end_time_iso:
            ok_range, range_or_err = validate_time_range(start_time_iso, end_time_iso)
            if not ok_range:
                return f"❌ Invalid time range: {range_or_err}"

        tz = timezone if timezone else _local_timezone()

        # First, fetch the existing event
        event = self.client.get(f"/calendar/v3/calendars/primary/events/{event_id}")

        if summary:
            event["summary"] = summary
        if start_time_iso:
            event["start"] = self._dt_field(start_time_iso, tz)
        if end_time_iso:
            event["end"] = self._dt_field(end_time_iso, tz)

        response = self.client.patch(
            f"/calendar/v3/calendars/primary/events/{event_id}", json_data=event
        )
        link = response.get("htmlLink", "")
        return f"Event updated successfully! Link: {link}"

    def delete_event(self, event_id: str) -> str:
        """Deletes a calendar event (requires approval).

        Args:
            event_id: ID of the event to delete.
        """
        # UC-CAL-005: gate behind approval before deleting.
        ok, reason = self.require_approval(
            action="delete_event",
            summary=f"Delete calendar event {event_id}",
            detail=f"This will permanently remove event id={event_id} from Google Calendar.",
        )
        if not ok:
            return f"⛔ Action not approved: {reason}"

        self.client.delete(f"/calendar/v3/calendars/primary/events/{event_id}")
        return f"Event {event_id} has been deleted."

    def create_recurring_event(
        self,
        title: str,
        start_time_iso: str,
        end_time_iso: str,
        recurrence_rule: str,
        description: str = "",
        attendees: list[str] | None = None,
        create_meet_link: bool = False,
        timezone: str = "",
    ) -> str:
        """Creates a recurring Google Calendar event using an RFC 5545 RRULE.

        Common recurrence_rule examples:
          - Daily:         RRULE:FREQ=DAILY
          - Every weekday: RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR
          - Weekly Monday: RRULE:FREQ=WEEKLY;BYDAY=MO
          - Monthly 1st:   RRULE:FREQ=MONTHLY;BYDAY=1MO
          - Until a date:  RRULE:FREQ=DAILY;UNTIL=20261231T235959Z
          - N occurrences: RRULE:FREQ=WEEKLY;COUNT=10

        Args:
            title:            Event title.
            start_time_iso:   Start time in ISO-8601 format.
            end_time_iso:     End time in ISO-8601 format.
            recurrence_rule:  RFC 5545 RRULE string.
            description:      Optional event description.
            attendees:        Optional attendee email addresses.
            create_meet_link: Attach a Google Meet link if True.
            timezone:         IANA timezone name (e.g. "America/New_York").
        """
        from typing import Any as _Any

        # UC-CAL-002: validate start/end range.
        ok_range, range_or_err = validate_time_range(start_time_iso, end_time_iso)
        if not ok_range:
            return f"❌ Invalid time range: {range_or_err}"

        # UC-CAL-003: validate RRULE.
        ok_rrule, rrule_or_err = validate_rrule(recurrence_rule)
        if not ok_rrule:
            return f"❌ Invalid recurrence rule: {rrule_or_err}"

        # Normalize: ensure RRULE: prefix is present for the API.
        normalized_rule = recurrence_rule
        if not normalized_rule.startswith("RRULE:"):
            normalized_rule = f"RRULE:{normalized_rule}"

        # UC-CAL-001: validate attendee emails.
        normalized_attendees: list[str] | None = None
        if attendees:
            ok_emails, emails_or_err = validate_emails(attendees)
            if not ok_emails:
                return f"❌ {emails_or_err}"
            normalized_attendees = emails_or_err  # type: ignore[assignment]

        tz = timezone if timezone else _local_timezone()

        event: dict[str, _Any] = {
            "summary": title,
            "description": description,
            "start": self._dt_field(start_time_iso, tz),
            "end": self._dt_field(end_time_iso, tz),
            "recurrence": [normalized_rule],
        }

        if normalized_attendees:
            event["attendees"] = [{"email": e} for e in normalized_attendees]

        params: dict[str, _Any] = {}
        if create_meet_link:
            import uuid

            event["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
            params["conferenceDataVersion"] = 1

        response = self.client.post(
            "/calendar/v3/calendars/primary/events",
            params=params,
            json_data=event,
            # Key includes the RRULE so a retried create can't duplicate the series.
            idempotency_key=make_idempotency_key(
                "calendar.create_recurring",
                title,
                f"{start_time_iso}\x00{end_time_iso}\x00{normalized_rule}",
            ),
        )
        link = response.get("htmlLink", "")
        meet_link = response.get("hangoutLink", "")
        result = f"Recurring event created! Rule: {normalized_rule}  Link: {link}"
        if meet_link:
            result += f"\nMeet: {meet_link}"
        return result

    def get_events_for_date(self, date_iso: str, max_results: int = 20) -> str:
        """Return all calendar events that fall on a given date (YYYY-MM-DD).

        Used by the day-planning tool to fetch what's scheduled on a specific day.
        """
        time_min = f"{date_iso}T00:00:00Z"
        time_max = f"{date_iso}T23:59:59Z"

        response = self.client.get(
            "/calendar/v3/calendars/primary/events",
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": max_results,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        events = response.get("items", [])
        if not events:
            return f"No events scheduled for {date_iso}."

        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end = e["end"].get("dateTime", e["end"].get("date", ""))
            # Show only the time portion for readability.
            start_t = start[11:16] if len(start) > 10 else start
            end_t = end[11:16] if len(end) > 10 else end
            attendee_count = len(e.get("attendees", []))
            attend_note = f" ({attendee_count} attendees)" if attendee_count else ""
            meet = " 📹" if e.get("hangoutLink") else ""
            lines.append(
                f"{start_t}–{end_t}  {e.get('summary', 'Busy')}{attend_note}{meet}"
                f"  [id={e.get('id', '')}]"
            )
        return "\n".join(lines)

    def register_tools(self, registry: ToolRegistry) -> None:
        """Register Google Calendar tools into the agent's tool registry."""
        registry.register(
            {
                "name": "google_create_event",
                "description": "Schedule a Google Calendar event. Time must be in ISO 8601 format.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title of the event"},
                        "start_time_iso": {
                            "type": "string",
                            "description": "Start time in ISO format INCLUDING the local timezone "
                            "offset (e.g., 2026-05-01T23:30:00+05:30)",
                        },
                        "end_time_iso": {
                            "type": "string",
                            "description": "End time in ISO format INCLUDING the local timezone "
                            "offset (e.g., 2026-05-02T00:30:00+05:30)",
                        },
                        "description": {"type": "string"},
                        "create_meet_link": {
                            "type": "boolean",
                            "description": "If true, automatically generates and attaches a "
                            "Google Meet video conference link.",
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of email addresses to invite",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone name (e.g. 'America/New_York'). "
                            "Defaults to system local timezone.",
                        },
                    },
                    "required": ["title", "start_time_iso", "end_time_iso"],
                },
            },
            self.create_calendar_event,
        )

        registry.register(
            {
                "name": "google_list_events",
                "description": "Get the user's upcoming Google Calendar events.",
                "input_schema": {
                    "type": "object",
                    "properties": {"max_results": {"type": "integer"}},
                },
            },
            self.get_upcoming_events,
        )

        registry.register(
            {
                "name": "google_find_free_time",
                "description": "Analyze the calendar to find free time slots. Returns a list of "
                "busy periods to avoid.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration of the meeting in minutes",
                        },
                        "days_ahead": {
                            "type": "integer",
                            "description": "How many days ahead to check",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone name for interpreting working hours "
                            "(e.g. 'Europe/London'). Defaults to system local timezone.",
                        },
                    },
                },
            },
            self.find_free_time,
        )

        registry.register(
            {
                "name": "google_update_event",
                "description": "Reschedule or rename an existing calendar event. You must provide "
                "the exact event_id.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "description": "The ID of the event to update",
                        },
                        "summary": {"type": "string", "description": "New title (optional)"},
                        "start_time_iso": {
                            "type": "string",
                            "description": "New start time in ISO format (optional)",
                        },
                        "end_time_iso": {
                            "type": "string",
                            "description": "New end time in ISO format (optional)",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone name to embed in updated times.",
                        },
                    },
                    "required": ["event_id"],
                },
            },
            self.update_event,
        )

        registry.register(
            {
                "name": "google_delete_event",
                "description": "Cancel/Delete a calendar event. Requires user approval.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "description": "The ID of the event to delete",
                        }
                    },
                    "required": ["event_id"],
                },
            },
            self.delete_event,
        )

        registry.register(
            {
                "name": "google_create_recurring_event",
                "description": (
                    "Create a recurring Google Calendar event using an RFC 5545 RRULE. "
                    "Use this for standing meetings, daily standups, weekly reviews, etc. "
                    "Common recurrence_rule examples — "
                    "daily: 'RRULE:FREQ=DAILY', "
                    "every weekday: 'RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR', "
                    "weekly on Monday: 'RRULE:FREQ=WEEKLY;BYDAY=MO', "
                    "10 occurrences: 'RRULE:FREQ=WEEKLY;COUNT=10', "
                    "until a date: 'RRULE:FREQ=DAILY;UNTIL=20261231T235959Z'."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Event title."},
                        "start_time_iso": {
                            "type": "string",
                            "description": "Start time with timezone offset "
                            "(e.g. 2026-06-09T10:00:00+05:30).",
                        },
                        "end_time_iso": {
                            "type": "string",
                            "description": "End time with timezone offset.",
                        },
                        "recurrence_rule": {
                            "type": "string",
                            "description": "RFC 5545 RRULE string "
                            "(e.g. 'RRULE:FREQ=WEEKLY;BYDAY=MO').",
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional event description / agenda.",
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Email addresses to invite.",
                        },
                        "create_meet_link": {
                            "type": "boolean",
                            "description": "Attach a Google Meet link to every occurrence.",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone name (e.g. 'Asia/Kolkata'). "
                            "Defaults to system local timezone.",
                        },
                    },
                    "required": ["title", "start_time_iso", "end_time_iso", "recurrence_rule"],
                },
            },
            self.create_recurring_event,
        )

        registry.register(
            {
                "name": "google_get_events_for_date",
                "description": (
                    "Fetch all calendar events on a specific date (YYYY-MM-DD). "
                    "Use this to see what's scheduled before planning a day."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date_iso": {
                            "type": "string",
                            "description": "The date to query in YYYY-MM-DD format.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum events to return (default 20).",
                        },
                    },
                    "required": ["date_iso"],
                },
            },
            self.get_events_for_date,
        )
