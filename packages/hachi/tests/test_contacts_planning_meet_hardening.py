"""Hardening tests — UC-CONTACT-001/002, UC-PLAN-001, UC-MEET-001.

Covers:
  - contact delete is gated behind require_approval (UC-CONTACT-002)
  - invalid email rejected on create/update (UC-CONTACT-001)
  - invalid phone rejected on update (UC-CONTACT-001)
  - planning surfaces a failure reason instead of bare "(unavailable)" (UC-PLAN-001)
  - meet monitor does not print to stdout (UC-MEET-001)
  - meet monitor surfaces a timeout as an explicit RuntimeError (UC-MEET-001)
  - meet monitor surfaces API errors instead of swallowing them (UC-MEET-001)

All Google HTTP calls and the MemoryVault are replaced by mocks.
"""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(require_approval_return=(True, "approved")):
    """Return a mock GoogleHTTPClient with a controllable ``require_approval``."""
    client = MagicMock()
    client.require_approval.return_value = require_approval_return
    client._get_headers.return_value = {"Authorization": "Bearer fake-token"}
    return client


def _make_registry():
    """Return a minimal ToolRegistry stub that records registrations."""
    registry = MagicMock()
    registry._tools = {}

    def _register(schema, fn):
        registry._tools[schema["name"]] = fn

    registry.register.side_effect = _register
    return registry


# ---------------------------------------------------------------------------
# UC-CONTACT-002: delete must pass through require_approval
# ---------------------------------------------------------------------------


class TestContactDeleteApproval:
    def _setup(self, approved: bool):
        from hachi.integrations.google.contacts import ContactsService

        reason = "approved" if approved else "denied by user"
        client = _make_mock_client(require_approval_return=(approved, reason))
        svc = ContactsService(client)
        registry = _make_registry()
        svc.register_tools(registry)
        return registry._tools["google_delete_contact"], client

    def test_delete_blocked_when_not_approved(self):
        fn, client = self._setup(approved=False)
        result = fn(resourceName="people/c999")
        assert "⛔" in result
        assert "not approved" in result.lower() or "denied" in result.lower()
        # The actual Google API must NOT have been called
        client.delete.assert_not_called()

    def test_delete_proceeds_when_approved(self):
        fn, client = self._setup(approved=True)
        client.delete.return_value = {}
        result = fn(resourceName="people/c999")
        assert "successfully deleted" in result.lower()
        client.delete.assert_called_once()

    def test_approve_called_with_correct_action(self):
        fn, client = self._setup(approved=False)
        fn(resourceName="people/c123")
        client.require_approval.assert_called_once()
        call_kwargs = client.require_approval.call_args
        # action can be positional or keyword
        args, kwargs = call_kwargs
        action = kwargs.get("action") or (args[0] if args else None)
        assert action == "delete_contact"


# ---------------------------------------------------------------------------
# UC-CONTACT-001: email / phone validation on create and update
# ---------------------------------------------------------------------------


class TestContactValidation:
    def _setup(self):
        from hachi.integrations.google.contacts import ContactsService

        client = _make_mock_client()
        svc = ContactsService(client)
        registry = _make_registry()
        svc.register_tools(registry)
        return registry._tools

    def test_create_rejects_invalid_email(self):
        tools = self._setup()
        result = tools["google_create_contact"](name="Alice", email="not-an-email")
        assert "invalid email" in result.lower()

    def test_create_accepts_valid_email(self):
        tools = self._setup()
        tools["google_create_contact"].__self__ = None  # just call it
        client = _make_mock_client()
        from hachi.integrations.google.contacts import ContactsService

        svc = ContactsService(client)
        registry = _make_registry()
        svc.register_tools(registry)
        client.post.return_value = {}
        result = registry._tools["google_create_contact"](name="Bob", email="bob@example.com")
        assert "successfully saved" in result.lower()

    def test_update_rejects_invalid_email(self):
        tools = self._setup()
        result = tools["google_update_contact"](resourceName="people/c1", email="bad@")
        assert "invalid email" in result.lower()

    def test_update_rejects_invalid_phone(self):
        tools = self._setup()
        result = tools["google_update_contact"](resourceName="people/c1", phone="abc-not-a-phone")
        assert "invalid phone" in result.lower()

    def test_update_accepts_valid_phone_and_email(self):
        from hachi.integrations.google.contacts import ContactsService

        client = _make_mock_client()
        # Return a fake existing person for the GET call
        client.get.return_value = {
            "names": [{"givenName": "Bob"}],
            "emailAddresses": [],
            "phoneNumbers": [],
            "etag": "abc",
        }
        client.patch.return_value = {}
        svc = ContactsService(client)
        registry = _make_registry()
        svc.register_tools(registry)
        result = registry._tools["google_update_contact"](
            resourceName="people/c1",
            phone="+1 (555) 000-1234",
            email="bob@example.com",
        )
        assert "successfully updated" in result.lower()


# ---------------------------------------------------------------------------
# UC-PLAN-001: planning surfaces failure reason in unavailable messages
# ---------------------------------------------------------------------------


class TestPlanningErrorSurfacing:
    """_classify_google_error and the helper methods must produce informative strings."""

    def test_classify_401_returns_auth_hint(self):
        from hachi.integrations.google.planning import _classify_google_error

        exc = Exception("401 Unauthorized")
        reason = _classify_google_error(exc)
        assert "auth" in reason.lower() or "oauth" in reason.lower() or "setup" in reason.lower()

    def test_classify_scope_returns_scope_hint(self):
        from hachi.integrations.google.planning import _classify_google_error

        exc = Exception("403 insufficient scope for this API call")
        reason = _classify_google_error(exc)
        assert "scope" in reason.lower() or "authoris" in reason.lower()

    def test_classify_api_not_enabled(self):
        from hachi.integrations.google.planning import _classify_google_error

        exc = Exception("accessNotConfigured: API not enabled for project")
        reason = _classify_google_error(exc)
        assert "api not enabled" in reason.lower() or "google cloud" in reason.lower()

    def test_fetch_events_surfaces_reason_on_error(self):
        from hachi.integrations.google.planning import PlanningService

        client = _make_mock_client()
        client.get.side_effect = Exception("403 insufficient scope")
        svc = PlanningService(client)

        lines = svc._fetch_events("2026-06-14")
        assert len(lines) == 1
        line = lines[0]
        # Must NOT be the old bare "(calendar unavailable)"
        assert line != "(calendar unavailable)"
        # Must include the section name and a reason
        assert "calendar" in line.lower()
        assert "unavailable" in line.lower()
        # Reason is surfaced
        assert "scope" in line.lower() or "insufficient" in line.lower()

    def test_fetch_gmail_surfaces_reason_on_error(self):
        from hachi.integrations.google.planning import PlanningService

        client = _make_mock_client()
        client.get.side_effect = Exception("Network timeout")
        svc = PlanningService(client)

        lines = svc._fetch_unread_count_and_snippets()
        assert len(lines) == 1
        line = lines[0]
        assert line != "(gmail unavailable)"
        assert "gmail" in line.lower()
        assert "unavailable" in line.lower()

    def test_fetch_tasks_surfaces_reason_on_error(self):
        from hachi.integrations.google.planning import PlanningService

        client = _make_mock_client()
        client.get.side_effect = Exception("401 unauthenticated")
        svc = PlanningService(client)

        lines = svc._fetch_pending_tasks()
        assert len(lines) == 1
        line = lines[0]
        assert line != "(tasks unavailable)"
        assert "tasks" in line.lower()
        assert "unavailable" in line.lower()

    def test_plan_my_day_date_formatting_portable(self):
        """Verify the Windows-compatible day formatting still works (no %-d regression)."""
        from hachi.integrations.google.planning import PlanningService

        client = _make_mock_client()
        # All sub-calls raise so we get the unavailable lines; we only care about the header
        client.get.side_effect = Exception("network error")
        svc = PlanningService(client)

        result = svc.plan_my_day(date_iso="2026-01-05")
        # Day "5" must appear without a leading zero
        assert "January 5 2026" in result


# ---------------------------------------------------------------------------
# UC-MEET-001: meet monitor — no stdout, explicit timeout, errors surfaced
# ---------------------------------------------------------------------------


class TestMeetMonitorNoStdout:
    """Confirm that _poll_for_transcript never writes to stdout."""

    def test_poll_timeout_raises_runtimeerror_not_print(self):
        """When the meeting never starts, RuntimeError is raised (not printed)."""
        from hachi.integrations.google.meet import _poll_for_transcript

        # Use a very short timeout so the test is fast
        with (
            patch(
                "hachi.integrations.google.meet._START_TIMEOUT_SECONDS",
                2,
            ),
            patch(
                "hachi.integrations.google.meet._POLL_INTERVAL_SECONDS",
                1,
            ),
            patch("httpx.get") as mock_get,
        ):
            # Always return an empty conference records list
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"conferenceRecords": []}
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                with pytest.raises(RuntimeError) as exc_info:
                    _poll_for_transcript(
                        space_id="abc-test-xyz", headers={"Authorization": "Bearer x"}
                    )
            finally:
                sys.stdout = old_stdout

            # Nothing must have been written to stdout
            assert captured.getvalue() == "", (
                f"Expected no stdout output, got: {captured.getvalue()!r}"
            )
            # The error message must name the timeout duration
            assert "timeout" in str(exc_info.value).lower()
            assert "minutes" in str(exc_info.value).lower()

    def test_poll_http_error_raises_runtimeerror(self):
        """HTTP errors during meeting monitoring propagate as RuntimeError."""
        from hachi.integrations.google.meet import _poll_for_transcript

        with (
            patch(
                "hachi.integrations.google.meet._START_TIMEOUT_SECONDS",
                60,
            ),
            patch(
                "hachi.integrations.google.meet._POLL_INTERVAL_SECONDS",
                0,
            ),
            patch("httpx.get") as mock_get,
        ):
            # Phase 1: meeting starts immediately (return conference record on first call)
            # Phase 2: monitoring call raises HTTP error
            phase1_resp = MagicMock()
            phase1_resp.json.return_value = {
                "conferenceRecords": [{"name": "conferenceRecords/r1"}]
            }
            phase1_resp.raise_for_status.return_value = None

            phase2_resp = MagicMock()
            http_err = httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
            phase2_resp.raise_for_status.side_effect = http_err

            mock_get.side_effect = [phase1_resp, phase2_resp]

            with pytest.raises(RuntimeError) as exc_info:
                _poll_for_transcript(space_id="abc-test-xyz", headers={"Authorization": "Bearer x"})

            err_str = str(exc_info.value).lower()
            assert "api error" in err_str or "http" in err_str

    def test_google_monitor_meeting_does_not_write_stdout(self):
        """The registered tool function must not emit anything to stdout."""
        from hachi.integrations.google.meet import MeetService

        client = _make_mock_client()
        svc = MeetService(client)
        registry = _make_registry()
        svc.register_tools(registry)
        fn = registry._tools["google_monitor_meeting"]

        with (
            patch("httpx.get") as mock_probe,
            patch("threading.Thread"),
        ):
            # Probe succeeds
            probe_resp = MagicMock()
            probe_resp.raise_for_status.return_value = None
            mock_probe.return_value = probe_resp

            old_stdout = sys.stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                result = fn(meet_link="https://meet.google.com/abc-test-xyz")
            finally:
                sys.stdout = old_stdout

            # No stdout
            assert captured.getvalue() == "", (
                f"Expected no stdout output, got: {captured.getvalue()!r}"
            )
            # Returns a useful status string, not None
            assert isinstance(result, str)
            assert "abc-test-xyz" in result
            # Mentions the transcription requirement
            assert "transcri" in result.lower()

    def test_google_monitor_meeting_surfaces_auth_error(self):
        """A 403 probe response returns a clear error string — no exception leaks."""
        from hachi.integrations.google.meet import MeetService

        client = _make_mock_client()
        svc = MeetService(client)
        registry = _make_registry()
        svc.register_tools(registry)
        fn = registry._tools["google_monitor_meeting"]

        with patch("httpx.get") as mock_probe:
            err_resp = MagicMock()
            err_resp.status_code = 403
            http_exc = httpx.HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=err_resp,
            )
            mock_probe.return_value.raise_for_status.side_effect = http_exc

            result = fn(meet_link="https://meet.google.com/abc-test-xyz")

        assert "error" in result.lower()
        assert "403" in result or "workspace" in result.lower() or "access denied" in result.lower()
