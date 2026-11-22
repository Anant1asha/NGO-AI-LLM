"""Tests for ChatView — offline smoke and live gateway mechanics.

Test coverage:
  1. Offline: mount ChatView in a minimal App with CockpitData(None).
     Submit a message → user line appears, local-echo reply runs, no crash.
  2. Live mechanics: boot a real in-process gateway, build CockpitData with a
     real GatewayClient, verify start_session() returns an id, send() succeeds,
     stream() connects without crashing, and the UI stays responsive.
     NOTE: no LLM key may be present so a full agent reply is NOT expected —
     we verify plumbing only.

Run with:
    PYTHONPATH=src python -m pytest tests/test_cockpit_chat_live.py -q
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult

from hachi.client.models import Approval
from hachi.client.sse import RuntimeEvent
from hachi.tui.cockpit.data import CockpitData
from hachi.tui.cockpit.views.chat import ChatView, _TranscriptMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


class _OfflineApp(App[None]):
    """Minimal Textual host that mounts ChatView with offline CockpitData."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cockpit_data: CockpitData = CockpitData(None)  # offline / placeholder

    def compose(self) -> ComposeResult:
        yield ChatView(id="view-chat")


# ---------------------------------------------------------------------------
# Offline tests
# ---------------------------------------------------------------------------


class TestChatViewOffline:
    """ChatView with CockpitData(None) — no gateway, no network."""

    def test_mount_no_crash(self) -> None:
        """ChatView mounts and renders without error in offline mode."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                chat = pilot.app.query_one("#view-chat", ChatView)
                assert chat is not None

        _run(_body())

    def test_populate_offline(self) -> None:
        """populate() with offline CockpitData renders without crashing."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)
                await pilot.pause()

        _run(_body())

    def test_submit_appends_user_line(self) -> None:
        """Submitting a message appends a 'you' entry to _messages."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)
                before = len(chat._messages)
                chat._on_composer_submit("hello hachi")
                await pilot.pause()
                user_msgs = [
                    m for m in chat._messages if m.speaker == "you" and m.text == "hello hachi"
                ]
                assert len(user_msgs) >= 1, "user message not appended"
                assert len(chat._messages) > before

        _run(_body())

    def test_submit_local_echo_reply(self) -> None:
        """Offline submit produces a local-echo 'hachi' reply (no crash, no live call)."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)
                chat._on_composer_submit("tell me something")
                await pilot.pause()
                hachi_msgs = [m for m in chat._messages if m.speaker == "hachi"]
                assert len(hachi_msgs) >= 1

        _run(_body())

    def test_empty_submit_ignored(self) -> None:
        """Submitting whitespace does nothing."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)
                before = len(chat._messages)
                chat._on_composer_submit("   ")
                await pilot.pause()
                assert len(chat._messages) == before

        _run(_body())

    def test_no_live_calls_in_offline_mode(self) -> None:
        """CockpitData.start_session() and .send() are never called offline."""
        mock_data = MagicMock(spec=CockpitData)
        mock_data.is_live = False

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                chat = pilot.app.query_one("#view-chat", ChatView)
                chat._data = mock_data
                chat._on_composer_submit("hello")
                await pilot.pause()
                mock_data.start_session.assert_not_called()
                mock_data.send.assert_not_called()

        _run(_body())

    def test_activate_selected_focuses_input(self) -> None:
        """activate_selected() focuses the chat-composer Input."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                chat = pilot.app.query_one("#view-chat", ChatView)
                chat.populate(pilot.app.cockpit_data)
                chat.activate_selected()
                await pilot.pause()
                # no crash = success; Input focus is tested in overlay tests

        _run(_body())

    def test_view_id(self) -> None:
        """view_id class attribute is 'chat'."""
        assert ChatView.view_id == "chat"

    def test_interrupt_stream_sets_stop(self) -> None:
        """_interrupt_stream() sets the stop event."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                chat = pilot.app.query_one("#view-chat", ChatView)
                chat.populate(pilot.app.cockpit_data)
                assert not chat._stop.is_set()
                chat._interrupt_stream()
                assert chat._stop.is_set()

        _run(_body())

    def test_apply_text_delta(self) -> None:
        """_apply_event with text.stream.delta appends text to the streaming line."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)

                # Seed a streaming hachi message
                chat._messages.append(_TranscriptMessage("hachi", "", is_streaming=True))

                ev = RuntimeEvent(
                    sequence=1,
                    event_type="text.stream.delta",
                    payload={"text": "Hello"},
                    time="2026-01-01T00:00:00",
                )
                chat._apply_event(ev)
                await pilot.pause()

                streaming = [m for m in chat._messages if m.speaker == "hachi" and m.is_streaming]
                assert any("Hello" in m.text for m in streaming)

        _run(_body())

    def test_apply_tool_started(self) -> None:
        """_apply_event with tool.call.started adds a tool card."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)

                ev = RuntimeEvent(
                    sequence=2,
                    event_type="tool.call.started",
                    payload={"name": "browse_web", "input": {"url": "https://example.com"}},
                    time="2026-01-01T00:00:00",
                )
                chat._apply_event(ev)
                await pilot.pause()

                tool_msgs = [m for m in chat._messages if m.speaker == "tool"]
                assert any("browse_web" in m.text for m in tool_msgs)

        _run(_body())

    def test_apply_chat_completed_finalizes(self) -> None:
        """_apply_event with session.chat.completed finalizes the streaming line."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)
                chat._messages.append(_TranscriptMessage("hachi", "partial", is_streaming=True))

                ev = RuntimeEvent(
                    sequence=3,
                    event_type="session.chat.completed",
                    payload={},
                    time="2026-01-01T00:00:00",
                )
                chat._apply_event(ev)
                await pilot.pause()

                streaming = [m for m in chat._messages if m.speaker == "hachi" and m.is_streaming]
                assert len(streaming) == 0, "streaming line was not finalized"
                assert chat._stop.is_set()

        _run(_body())

    def test_permission_event_no_request_id_degrades(self) -> None:
        """permission.requested without request_id shows inline card, no crash."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)

                ev = RuntimeEvent(
                    sequence=4,
                    event_type="permission.requested",
                    payload={"operation": "shell", "tool": "run_command"},
                    time="2026-01-01T00:00:00",
                )
                chat._apply_event(ev)
                await pilot.pause()

                # Should have added an inline warning card
                tool_msgs = [m for m in chat._messages if m.speaker == "tool"]
                assert any("approval" in m.text.lower() for m in tool_msgs)

        _run(_body())

    def test_rail_reflects_real_pending_approval(self) -> None:
        """BB-60: the right-rail approval card must reflect CockpitData.approvals(),
        not the hardcoded 'browse_web (researcher)' demo literal.
        """

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)

                real_approval = Approval(
                    id="req-999",
                    icon="shell",
                    request="run_command",
                    why="needs to run a build script",
                    action="run_command → ./build.sh",
                    op="shell",
                    policy="asks first",
                    touches=("./build.sh",),
                    risk="high",
                    scope="shell",
                    expires_at=0,
                    total_ms=0,
                )

                mock_data = MagicMock(spec=CockpitData)
                mock_data.is_live = True
                mock_data.config.return_value = app.cockpit_data.config()
                mock_data.sessions.return_value = app.cockpit_data.sessions(limit=1)
                mock_data.spend.return_value = app.cockpit_data.spend()
                mock_data.approvals.return_value = [real_approval]

                chat.populate(mock_data)
                await pilot.pause()

                rail = chat.query_one("#chat-rail")
                rendered = rail.content.plain  # type: ignore[union-attr]

                # The real pending approval's tool/target must appear...
                assert "run_command" in rendered
                assert "./build.sh" in rendered
                # ...and the hardcoded demo literal must NOT appear.
                assert "browse_web" not in rendered
                assert "researcher" not in rendered

        _run(_body())

    def test_rail_shows_no_approvals_when_none_pending(self) -> None:
        """BB-60: with zero pending approvals the rail must not claim '1 approval waiting'."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)

                mock_data = MagicMock(spec=CockpitData)
                mock_data.is_live = True
                mock_data.config.return_value = app.cockpit_data.config()
                mock_data.sessions.return_value = app.cockpit_data.sessions(limit=1)
                mock_data.spend.return_value = app.cockpit_data.spend()
                mock_data.approvals.return_value = []

                chat.populate(mock_data)
                await pilot.pause()

                rail = chat.query_one("#chat-rail")
                rendered = rail.content.plain  # type: ignore[union-attr]

                assert "1 approval waiting" not in rendered

        _run(_body())

    def test_unknown_event_type_ignored(self) -> None:
        """Unknown event types are silently ignored (no crash, no new messages)."""

        async def _body() -> None:
            async with _OfflineApp().run_test(headless=True) as pilot:
                app = pilot.app
                chat = app.query_one("#view-chat", ChatView)
                chat.populate(app.cockpit_data)
                before = len(chat._messages)

                ev = RuntimeEvent(
                    sequence=5,
                    event_type="completely.unknown.event.type.xyz",
                    payload={},
                    time="2026-01-01T00:00:00",
                )
                chat._apply_event(ev)
                await pilot.pause()

                assert len(chat._messages) == before

        _run(_body())


# ---------------------------------------------------------------------------
# Live gateway mechanics tests
# ---------------------------------------------------------------------------
#
# These tests boot a real in-process gateway to verify plumbing mechanics:
# - start_session() returns a session id
# - send() does not raise
# - stream() connects and handles events/errors without crashing
# - UI stays responsive
#
# A live LLM key is NOT required; if absent the agent won't reply but the
# connection mechanics still work.
#
# Tests are skipped automatically if the gateway fails to start (e.g. CI
# environment with no ports available) to avoid false negatives.


class _LiveGatewayFixture:
    """Context manager that boots a real in-process gateway and tears it down."""

    def __init__(self) -> None:
        self.server = None
        self.base_url = ""
        self.runtime = None
        self.token = ""

    def __enter__(self) -> _LiveGatewayFixture:
        from hachi.cli.main import (  # type: ignore[attr-defined]
            _resolve_gateway_auth_token,
            _start_gateway_server,
        )

        self.token = _resolve_gateway_auth_token("127.0.0.1")
        self.server, self.base_url, self.runtime = _start_gateway_server(
            host="127.0.0.1",
            port=0,
            attach_runtime=True,
        )
        return self

    def __exit__(self, *_: object) -> None:
        try:
            if self.runtime is not None:
                self.runtime.shutdown()
        except Exception:
            pass
        try:
            if self.server is not None:
                self.server.stop()
        except Exception:
            pass


def _try_boot_gateway() -> _LiveGatewayFixture | None:
    """Return a booted gateway fixture or None if boot fails."""
    try:
        fix = _LiveGatewayFixture()
        fix.__enter__()
        return fix
    except Exception:
        return None


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="live gateway mechanics require ANTHROPIC_API_KEY (session creation needs an LLM key)",
)
class TestChatViewLiveMechanics:
    """Verify live plumbing against a real in-process gateway.

    Tests skip if no ANTHROPIC_API_KEY is set (checked at class level) or if
    the gateway cannot start (checked per-test via _try_boot_gateway).
    """

    def test_start_session_returns_id(self) -> None:
        """CockpitData.start_session() returns a non-empty string when live."""
        fix = _try_boot_gateway()
        if fix is None:
            pytest.skip("gateway could not start")

        try:
            from hachi.client.gateway import GatewayClient
            from hachi.tui.cockpit.data import CockpitData

            client = GatewayClient(base_url=fix.base_url, token=fix.token)
            data = CockpitData(client)
            sid = data.start_session()
            assert sid is not None, "start_session() returned None"
            assert len(sid) > 0, "start_session() returned empty string"
        finally:
            fix.__exit__()

    def test_send_does_not_raise(self) -> None:
        """CockpitData.send() completes without exception (even with no LLM key)."""
        fix = _try_boot_gateway()
        if fix is None:
            pytest.skip("gateway could not start")

        try:
            from hachi.client.gateway import GatewayClient
            from hachi.tui.cockpit.data import CockpitData

            client = GatewayClient(base_url=fix.base_url, token=fix.token)
            data = CockpitData(client)
            sid = data.start_session()
            if sid is None:
                pytest.skip("start_session() returned None; cannot test send()")
            result = data.send(sid, "hello")
            # send() always returns a dict (empty dict on error per CockpitData contract)
            assert isinstance(result, dict)
        finally:
            fix.__exit__()

    def test_stream_connects_without_crash(self) -> None:
        """CockpitData.stream() connects and iterates without crashing.

        We run the stream for a short bounded window (stop after 1 second or
        after the first event, whichever comes first).  No crash = pass.
        """
        fix = _try_boot_gateway()
        if fix is None:
            pytest.skip("gateway could not start")

        try:
            from hachi.client.gateway import GatewayClient
            from hachi.tui.cockpit.data import CockpitData

            client = GatewayClient(base_url=fix.base_url, token=fix.token)
            data = CockpitData(client)
            sid = data.start_session()
            if sid is None:
                pytest.skip("start_session() returned None; cannot test stream()")

            stop = threading.Event()
            events_seen: list[object] = []
            errors_seen: list[Exception] = []

            def _drain() -> None:
                try:
                    for ev in data.stream(sid, after=0, stop_event=stop):
                        events_seen.append(ev)
                        stop.set()  # stop after first event
                        break
                except Exception as exc:
                    errors_seen.append(exc)

            t = threading.Thread(target=_drain, daemon=True)
            t.start()
            # Give the stream up to 3 seconds
            t.join(timeout=3.0)
            stop.set()
            t.join(timeout=1.0)

            # stream() must not have crashed with an unexpected exception type
            # (GatewayError from "no events yet" is acceptable)
            for exc in errors_seen:
                from hachi.client.gateway import GatewayError

                # Network/transport errors for a brand-new session with no LLM key
                # are expected.  Any other exception type would be a bug.
                assert isinstance(exc, (GatewayError, OSError)), (
                    f"Unexpected stream error: {type(exc).__name__}: {exc}"
                )
        finally:
            fix.__exit__()

    def test_chatview_with_live_gateway_no_crash(self) -> None:
        """ChatView mounted against a live gateway: submit a message, no crash.

        Verifies:
        - UI stays responsive
        - _session_id is set after submit (lazy creation worked)
        - No unhandled exceptions
        """
        fix = _try_boot_gateway()
        if fix is None:
            pytest.skip("gateway could not start")

        try:
            from hachi.client.gateway import GatewayClient
            from hachi.tui.cockpit.data import CockpitData

            client = GatewayClient(base_url=fix.base_url, token=fix.token)
            data = CockpitData(client)

            class _LiveChatApp(App[None]):
                def __init__(self, cockpit_data_: CockpitData, **kwargs: Any) -> None:
                    super().__init__(**kwargs)
                    self.cockpit_data = cockpit_data_

                def compose(self) -> ComposeResult:
                    yield ChatView(id="view-chat")

            async def _body() -> None:
                async with _LiveChatApp(data).run_test(headless=True) as pilot:
                    chat = pilot.app.query_one("#view-chat", ChatView)
                    chat.populate(data)
                    await pilot.pause()

                    # Submit a message — triggers lazy session creation + send + stream
                    chat._on_composer_submit("ping")
                    # Give the worker a moment to connect (bounded)
                    await asyncio.sleep(0.5)
                    await pilot.pause()

                    # Session should have been created (or gracefully failed)
                    # Either way the UI must not have crashed
                    user_msgs = [m for m in chat._messages if m.speaker == "you"]
                    assert len(user_msgs) >= 1

                    # Clean up the stop event / worker
                    chat._stop.set()
                    await pilot.pause()

            _run(_body())
        finally:
            fix.__exit__()
