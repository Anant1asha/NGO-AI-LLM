"""Isolation tests for the Wave-3 cockpit views: ResourcesView, SettingsView, ChatView.

Each view is mounted inside a throwaway App with no other cockpit scaffolding.
``CockpitData(None)`` is used (offline / placeholder mode) so no gateway is
required and tests are fully deterministic.

Each test is synchronous and wraps its async body via ``asyncio.run()``
(matching the pattern in test_cockpit_foundation.py — no pytest-asyncio needed).

Run with:
    PYTHONPATH=src python -m pytest tests/test_cockpit_views_f.py -q
"""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Input, Static

from hachi.tui.cockpit.data import CockpitData
from hachi.tui.cockpit.views.chat import ChatView
from hachi.tui.cockpit.views.resources import ResourcesView
from hachi.tui.cockpit.views.settings import SettingsView

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine synchronously for Textual pilot tests."""
    return asyncio.run(coro)


def _static_text(widget: Static) -> str:
    """Return the rendered text content of a Static widget."""
    result = widget.render()
    # render() returns a Rich renderable; convert to plain str via repr fallback
    return str(result)


class _ResourcesApp(App[None]):
    """Minimal app containing only ResourcesView."""

    def compose(self) -> ComposeResult:
        yield ResourcesView()


class _SettingsApp(App[None]):
    """Minimal app containing only SettingsView."""

    def compose(self) -> ComposeResult:
        yield SettingsView()


class _ChatApp(App[None]):
    """Minimal app containing only ChatView."""

    def compose(self) -> ComposeResult:
        yield ChatView()


# ---------------------------------------------------------------------------
# ResourcesView tests
# ---------------------------------------------------------------------------


class TestResourcesView:
    """ResourcesView isolation tests."""

    def test_resources_populate_renders_meter_labels(self) -> None:
        """populate() should render token meter labels."""

        async def _body() -> None:
            async with _ResourcesApp().run_test() as pilot:
                view = pilot.app.query_one(ResourcesView)
                view.populate(CockpitData(None))
                await pilot.pause()
                tokens_widget = pilot.app.query_one("#res-tokens", Static)
                rendered = _static_text(tokens_widget)
                assert "tokens" in rendered.lower(), (
                    f"Missing 'tokens' in: {rendered!r}"
                )

        _run(_body())

    def test_resources_populate_renders_cost_card(self) -> None:
        """populate() should render the cost card."""

        async def _body() -> None:
            async with _ResourcesApp().run_test() as pilot:
                view = pilot.app.query_one(ResourcesView)
                view.populate(CockpitData(None))
                await pilot.pause()
                cost_widget = pilot.app.query_one("#res-cost", Static)
                rendered = _static_text(cost_widget)
                assert "cost" in rendered.lower(), (
                    f"Missing 'cost' in: {rendered!r}"
                )

        _run(_body())

    def test_resources_populate_renders_footprint_card(self) -> None:
        """populate() should render footprint card with local marker."""

        async def _body() -> None:
            async with _ResourcesApp().run_test() as pilot:
                view = pilot.app.query_one(ResourcesView)
                view.populate(CockpitData(None))
                await pilot.pause()
                footprint_widget = pilot.app.query_one("#res-footprint", Static)
                rendered = _static_text(footprint_widget)
                assert "local" in rendered.lower(), (
                    f"Missing 'local' in: {rendered!r}"
                )

        _run(_body())

    def test_resources_populate_idempotent(self) -> None:
        """Calling populate() twice must not raise."""

        async def _body() -> None:
            async with _ResourcesApp().run_test() as pilot:
                view = pilot.app.query_one(ResourcesView)
                data = CockpitData(None)
                view.populate(data)
                view.populate(data)
                await pilot.pause()

        _run(_body())


# ---------------------------------------------------------------------------
# SettingsView tests
# ---------------------------------------------------------------------------


class TestSettingsView:
    """SettingsView isolation tests."""

    def test_settings_populate_shows_provider(self) -> None:
        """populate() must show 'provider' label in content pane."""

        async def _body() -> None:
            async with _SettingsApp().run_test() as pilot:
                view = pilot.app.query_one(SettingsView)
                view.populate(CockpitData(None))
                await pilot.pause()
                content_widget = pilot.app.query_one("#settings-pane", Static)
                rendered = _static_text(content_widget)
                assert "provider" in rendered.lower(), (
                    f"Missing 'provider' in: {rendered!r}"
                )

        _run(_body())

    def test_settings_populate_shows_model(self) -> None:
        """populate() must show the model name in content pane."""

        async def _body() -> None:
            async with _SettingsApp().run_test() as pilot:
                view = pilot.app.query_one(SettingsView)
                view.populate(CockpitData(None))
                await pilot.pause()
                content_widget = pilot.app.query_one("#settings-pane", Static)
                rendered = _static_text(content_widget)
                assert "model" in rendered.lower(), (
                    f"Missing 'model' in: {rendered!r}"
                )

        _run(_body())

    def test_settings_rail_shows_all_sections(self) -> None:
        """Rail must list all five section names."""

        async def _body() -> None:
            async with _SettingsApp().run_test() as pilot:
                view = pilot.app.query_one(SettingsView)
                view.populate(CockpitData(None))
                await pilot.pause()
                rail_widget = pilot.app.query_one("#settings-rail-label", Static)
                rendered = _static_text(rail_widget)
                for section in [
                    "Provider", "Memory", "Sub-agents", "Appearance", "Setup wizard"
                ]:
                    assert section in rendered, (
                        f"Missing section {section!r} in rail: {rendered!r}"
                    )

        _run(_body())

    def test_settings_move_selection_navigates(self) -> None:
        """move_selection(1) must advance to the Memory section."""

        async def _body() -> None:
            async with _SettingsApp().run_test() as pilot:
                view = pilot.app.query_one(SettingsView)
                view.populate(CockpitData(None))
                view.move_selection(1)  # Provider(0) -> Memory(1)
                await pilot.pause()
                content_widget = pilot.app.query_one("#settings-pane", Static)
                rendered = _static_text(content_widget)
                assert "memory" in rendered.lower(), (
                    f"Missing 'memory' in: {rendered!r}"
                )

        _run(_body())

    def test_settings_move_selection_wraps(self) -> None:
        """move_selection wraps from last section back to Provider."""

        async def _body() -> None:
            async with _SettingsApp().run_test() as pilot:
                view = pilot.app.query_one(SettingsView)
                view.populate(CockpitData(None))
                # 5 steps from 0 wraps back to 0 (Provider)
                for _ in range(5):
                    view.move_selection(1)
                await pilot.pause()
                content_widget = pilot.app.query_one("#settings-pane", Static)
                rendered = _static_text(content_widget)
                assert "provider" in rendered.lower(), (
                    f"Expected Provider after wrap: {rendered!r}"
                )

        _run(_body())


# ---------------------------------------------------------------------------
# ChatView tests
# ---------------------------------------------------------------------------


class TestChatView:
    """ChatView isolation tests."""

    def test_chat_populate_shows_transcript(self) -> None:
        """populate() must render 'hachi' in the transcript."""

        async def _body() -> None:
            async with _ChatApp().run_test() as pilot:
                view = pilot.app.query_one(ChatView)
                view.populate(CockpitData(None))
                await pilot.pause()
                transcript = pilot.app.query_one("#chat-transcript", Static)
                rendered = _static_text(transcript)
                assert "hachi" in rendered.lower(), (
                    f"Missing 'hachi' in transcript: {rendered!r}"
                )

        _run(_body())

    def test_chat_populate_shows_you_voice(self) -> None:
        """populate() must render the 'you' voice in the transcript."""

        async def _body() -> None:
            async with _ChatApp().run_test() as pilot:
                view = pilot.app.query_one(ChatView)
                view.populate(CockpitData(None))
                await pilot.pause()
                transcript = pilot.app.query_one("#chat-transcript", Static)
                rendered = _static_text(transcript)
                assert "you" in rendered.lower(), (
                    f"Missing 'you' in transcript: {rendered!r}"
                )

        _run(_body())

    def test_chat_composer_exists(self) -> None:
        """ChatView must expose an Input with id='chat-composer'."""

        async def _body() -> None:
            async with _ChatApp().run_test() as pilot:
                view = pilot.app.query_one(ChatView)
                view.populate(CockpitData(None))
                await pilot.pause()
                composer = pilot.app.query_one("#chat-composer", Input)
                assert composer is not None

        _run(_body())

    def test_chat_activate_selected_focuses_composer(self) -> None:
        """activate_selected() must focus the composer Input."""

        async def _body() -> None:
            async with _ChatApp().run_test() as pilot:
                view = pilot.app.query_one(ChatView)
                view.populate(CockpitData(None))
                await pilot.pause()
                view.activate_selected()
                await pilot.pause()
                composer = pilot.app.query_one("#chat-composer", Input)
                assert composer.has_focus

        _run(_body())

    def test_chat_input_submit_appends_transcript_line(self) -> None:
        """Submitting the composer appends the user message to the transcript."""

        async def _body() -> None:
            async with _ChatApp().run_test() as pilot:
                view = pilot.app.query_one(ChatView)
                view.populate(CockpitData(None))
                await pilot.pause()
                view._on_composer_submit("what is the status?")
                await pilot.pause()
                transcript = pilot.app.query_one("#chat-transcript", Static)
                rendered = _static_text(transcript)
                assert "what is the status?" in rendered, (
                    f"Submitted message not in transcript: {rendered!r}"
                )

        _run(_body())

    def test_chat_input_submit_appends_reply(self) -> None:
        """Submitting the composer appends both user + hachi reply messages."""

        async def _body() -> None:
            async with _ChatApp().run_test() as pilot:
                view = pilot.app.query_one(ChatView)
                view.populate(CockpitData(None))
                await pilot.pause()
                initial_count = len(view._messages)
                view._on_composer_submit("hello")
                await pilot.pause()
                # user message + stub reply = +2
                assert len(view._messages) == initial_count + 2

        _run(_body())

    def test_chat_empty_submit_ignored(self) -> None:
        """Submitting an empty/whitespace string must not append anything."""

        async def _body() -> None:
            async with _ChatApp().run_test() as pilot:
                view = pilot.app.query_one(ChatView)
                view.populate(CockpitData(None))
                await pilot.pause()
                initial_count = len(view._messages)
                view._on_composer_submit("   ")
                await pilot.pause()
                assert len(view._messages) == initial_count

        _run(_body())
