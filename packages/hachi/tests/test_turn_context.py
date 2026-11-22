from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from hachi.core.turn_context import TurnContext


def test_turn_context_is_frozen_and_composes_prompt() -> None:
    context = TurnContext.build(
        turn_id="turn-1",
        session_id="session-1",
        user_input="hello",
        system_prompt_base="base prompt",
        active_skill="analyst",
        user_profile_snapshot="user profile facts",
        agent_profile_snapshot="agent profile facts",
        recalled_context="recalled facts",
        max_iterations=7,
        surface="cli",
    )

    assert context.turn_id == "turn-1"
    assert context.session_id == "session-1"
    assert context.max_iterations == 7
    assert "base prompt" in context.system_prompt
    assert "user profile facts" in context.system_prompt
    assert "agent profile facts" in context.system_prompt
    assert "recalled facts" in context.system_prompt

    with pytest.raises(FrozenInstanceError):
        context.user_input = "changed"  # type: ignore[misc]


def test_turn_context_build_returns_independent_instances() -> None:
    first = TurnContext.build(
        turn_id="turn-1",
        session_id="session-1",
        user_input="first",
        system_prompt_base="base one",
        recalled_context="first recall",
    )
    second = TurnContext.build(
        turn_id="turn-2",
        session_id="session-1",
        user_input="second",
        system_prompt_base="base two",
        recalled_context="second recall",
    )

    assert first is not second
    assert first.turn_id == "turn-1"
    assert second.turn_id == "turn-2"
    assert first.recalled_context == "first recall"
    assert second.recalled_context == "second recall"
