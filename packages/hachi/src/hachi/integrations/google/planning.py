"""Day-Planning Service Plugin.

Combines Google Calendar events, Gmail unread mail, and Google Tasks into a
single structured daily plan. The agent calls this one tool instead of
chaining three separate lookups; the result is a markdown-formatted plan
block ready to read or speak aloud.
"""

from __future__ import annotations

import datetime

from hachi.core.loop import ToolRegistry
from hachi.integrations.google.service import GoogleService


def _classify_google_error(exc: BaseException) -> str:
    """Return a human-readable reason string for a Google API failure.

    Inspects the exception type and message to distinguish common failure modes:
    auth errors, insufficient scope, API not enabled, and network/unknown.
    This prevents callers from swallowing exceptions and emitting opaque
    "(unavailable)" strings that give the user no actionable information.

    Args:
        exc: The exception raised by a Google API call.

    Returns:
        A short reason string suitable for embedding in a status message,
        e.g. "insufficient Calendar scope" or "API not enabled in Google Cloud".
    """
    msg = str(exc).lower()
    # 401 / 403 usually surface via httpx.HTTPStatusError or the client wrapper
    if "401" in msg or "unauthorized" in msg or "unauthenticated" in msg:
        return "authentication error — re-run `hachi setup` to refresh OAuth token"
    if "403" in msg or "forbidden" in msg or "insufficient" in msg or "scope" in msg:
        return "insufficient scope — re-authorise with the required Google API scope"
    if "api not enabled" in msg or "accessnotconfigured" in msg or "disabled" in msg:
        return "API not enabled in Google Cloud project"
    if "quota" in msg or "rate limit" in msg or "resourceexhausted" in msg:
        return "quota exceeded — try again later"
    if "network" in msg or "connection" in msg or "timeout" in msg:
        return f"network error — {exc}"
    # Fallback: include the raw error so the user can diagnose
    return str(exc) or "unknown error"


class PlanningService(GoogleService):
    """Synthesis service: fuses calendar, mail, and tasks into a daily plan."""

    # PlanningService calls the same Google APIs as Calendar, Gmail, and Tasks
    # but does not add any *new* scopes — the shared client already holds them.
    @property
    def required_scopes(self) -> list[str]:
        return []

    # ------------------------------------------------------------------
    # Internal helpers (lightweight, no extra network calls)
    # ------------------------------------------------------------------

    def _fetch_events(self, date_iso: str) -> list[str]:
        """Return formatted calendar event lines for *date_iso*."""
        time_min = f"{date_iso}T00:00:00Z"
        time_max = f"{date_iso}T23:59:59Z"
        try:
            response = self.client.get(
                "/calendar/v3/calendars/primary/events",
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "maxResults": 20,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
            events = response.get("items", [])
        except Exception as exc:
            reason = _classify_google_error(exc)
            return [f"(calendar unavailable: {reason})"]

        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            end = e["end"].get("dateTime", e["end"].get("date", ""))
            start_t = start[11:16] if len(start) > 10 else start
            end_t = end[11:16] if len(end) > 10 else end
            attendees = e.get("attendees", [])
            attn = f" · {len(attendees)} attendees" if attendees else ""
            meet = " 📹" if e.get("hangoutLink") else ""
            lines.append(f"  {start_t}–{end_t}  **{e.get('summary', 'Busy')}**{attn}{meet}")
        return lines or ["  (no calendar events)"]

    def _fetch_unread_count_and_snippets(self, max_snippets: int = 5) -> list[str]:
        """Return a short list of unread-email summaries."""
        try:
            response = self.client.get(
                "/gmail/v1/users/me/messages",
                params={"q": "is:unread in:inbox", "maxResults": max_snippets},
            )
            messages = response.get("messages", [])
        except Exception as exc:
            reason = _classify_google_error(exc)
            return [f"(gmail unavailable: {reason})"]

        if not messages:
            return ["  (inbox clear)"]

        lines: list[str] = []
        for msg in messages[:max_snippets]:
            msg_id = msg.get("id", "")
            try:
                detail = self.client.get(
                    f"/gmail/v1/users/me/messages/{msg_id}",
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
                )
                headers = {
                    h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])
                }
                subject = headers.get("Subject", "(no subject)")[:60]
                sender = headers.get("From", "")
                # Extract just the display name or email.
                sender = sender.split("<")[0].strip().strip('"') or sender
                lines.append(f"  · **{subject}** — from {sender}")
            except Exception:
                lines.append(f"  · (message {msg_id})")
        total = response.get("resultSizeEstimate", len(messages))
        if total > max_snippets:
            lines.append(f"  … and {total - max_snippets} more unread")
        return lines

    def _fetch_pending_tasks(self, max_tasks: int = 10) -> list[str]:
        """Return pending (non-completed) task titles from the default list."""
        try:
            response = self.client.get(
                "/tasks/v1/lists/@default/tasks",
                params={"showCompleted": "false", "maxResults": max_tasks},
            )
            items = response.get("items", [])
        except Exception as exc:
            reason = _classify_google_error(exc)
            return [f"(tasks unavailable: {reason})"]

        if not items:
            return ["  (no pending tasks)"]

        lines = []
        for t in items:
            due = f" · due {t['due'][:10]}" if t.get("due") else ""
            lines.append(f"  ○ {t.get('title', '(unnamed)')}{due}")
        return lines

    # ------------------------------------------------------------------
    # Main synthesis method
    # ------------------------------------------------------------------

    def plan_my_day(
        self,
        date_iso: str = "",
        include_email: bool = True,
        include_tasks: bool = True,
        email_snippets: int = 5,
    ) -> str:
        """Generate a structured daily plan for the given date.

        Fetches calendar events, unread emails, and pending tasks in parallel
        (sequential HTTP calls) and formats them into a single markdown block
        the agent can present or build on.

        Args:
            date_iso: Date to plan (YYYY-MM-DD). Defaults to today.
            include_email: Whether to include an inbox summary.
            include_tasks: Whether to include the pending task list.
            email_snippets: Max number of unread email subjects to show.
        """
        if not date_iso:
            date_iso = datetime.date.today().isoformat()

        try:
            _d = datetime.date.fromisoformat(date_iso)
            # %-d (Linux) / %#d (Windows) strip leading zero — use a portable alternative.
            display_date = _d.strftime("%A, %B ") + str(_d.day) + _d.strftime(" %Y")
        except (ValueError, AttributeError):
            display_date = date_iso

        sections: list[str] = [f"# Daily Plan — {display_date}\n"]

        # --- Calendar ---
        sections.append("## 📅 Calendar")
        sections.extend(self._fetch_events(date_iso))
        sections.append("")

        # --- Email ---
        if include_email:
            sections.append("## 📬 Unread Inbox")
            sections.extend(self._fetch_unread_count_and_snippets(max_snippets=email_snippets))
            sections.append("")

        # --- Tasks ---
        if include_tasks:
            sections.append("## ✅ Pending Tasks")
            sections.extend(self._fetch_pending_tasks())
            sections.append("")

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            {
                "name": "google_plan_my_day",
                "description": (
                    "Generate a structured daily plan by fusing the user's Google Calendar events, "
                    "unread Gmail inbox, and pending Google Tasks into a single markdown summary. "
                    "Call this when the user asks to plan their day, see what's on today, "
                    "or get a morning briefing."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date_iso": {
                            "type": "string",
                            "description": "Date to plan in YYYY-MM-DD format. "
                            "Omit or leave empty for today.",
                        },
                        "include_email": {
                            "type": "boolean",
                            "description": "Include unread inbox summary (default true).",
                        },
                        "include_tasks": {
                            "type": "boolean",
                            "description": "Include pending task list (default true).",
                        },
                        "email_snippets": {
                            "type": "integer",
                            "description": "Max unread emails to show subject lines for "
                            "(default 5).",
                        },
                    },
                },
            },
            self.plan_my_day,
        )
