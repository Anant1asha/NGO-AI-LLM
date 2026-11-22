"""Tests for PromptComposer — pure unit tests, no filesystem or LLM."""

from hachi.core.prompt_composer import build_stable_base, compose

_BRAIN = "STABLE_BRAIN_CONTENT"


def test_build_stable_base_brain_only() -> None:
    result = build_stable_base(brain_text=_BRAIN)
    assert _BRAIN in result
    assert "ObjectGraph" not in result  # skill block only added when skill_count > 0


def test_build_stable_base_with_skills() -> None:
    result = build_stable_base(brain_text=_BRAIN, skill_count=5)
    assert "ObjectGraph" in result
    assert "5 skill(s)" in result


def test_build_stable_base_with_integrations() -> None:
    result = build_stable_base(brain_text=_BRAIN, integration_count=3)
    assert "3 live service tool(s)" in result


def test_build_stable_base_with_tool_groups() -> None:
    result = build_stable_base(brain_text=_BRAIN, tool_groups=["schedule", "browser"])
    assert "schedule" in result
    assert "browser" in result


def test_build_stable_base_no_integrations_block_when_zero() -> None:
    result = build_stable_base(brain_text=_BRAIN, integration_count=0)
    assert "Live Service" not in result


def test_build_stable_base_no_tool_groups_block_when_none() -> None:
    result = build_stable_base(brain_text=_BRAIN, tool_groups=None)
    assert "OPTIONAL TOOL GROUPS" not in result


def test_build_stable_base_with_permission_block() -> None:
    result = build_stable_base(brain_text=_BRAIN, permission_block="PERM_INJECTION")
    assert "PERM_INJECTION" in result


def test_build_stable_base_with_capability_block() -> None:
    result = build_stable_base(brain_text=_BRAIN, capability_block="CAP_STATUS")
    assert "OPTIONAL CAPABILITIES" in result
    assert "CAP_STATUS" in result


def test_compose_stable_content_in_cacheable() -> None:
    cacheable, dynamic = compose(stable_base=_BRAIN)
    assert _BRAIN in cacheable
    assert _BRAIN not in dynamic


def test_compose_time_header_in_dynamic() -> None:
    cacheable, dynamic = compose(stable_base=_BRAIN)
    assert "CURRENT TIME" in dynamic
    assert "CURRENT TIME" not in cacheable


def test_compose_recall_in_dynamic() -> None:
    cacheable, dynamic = compose(stable_base=_BRAIN, recalled_context="RECALL_PAYLOAD")
    assert "RECALL_PAYLOAD" in dynamic
    assert "RECALL_PAYLOAD" not in cacheable


def test_compose_user_profile_in_cacheable() -> None:
    cacheable, dynamic = compose(stable_base=_BRAIN, user_profile_snapshot="PROFILE_FACTS")
    assert "PROFILE_FACTS" in cacheable
    assert "PROFILE_FACTS" not in dynamic


def test_compose_agent_profile_in_cacheable() -> None:
    cacheable, dynamic = compose(stable_base=_BRAIN, agent_profile_snapshot="AGENT_FACTS")
    assert "AGENT_FACTS" in cacheable
    assert "AGENT_FACTS" not in dynamic


def test_compose_stable_split_across_repeated_calls() -> None:
    # Same inputs → same structure (time header changes but structure is consistent)
    c1, d1 = compose(stable_base=_BRAIN)
    c2, d2 = compose(stable_base=_BRAIN)
    assert _BRAIN in c1 and _BRAIN in c2
    assert "CURRENT TIME" in d1 and "CURRENT TIME" in d2


def test_turn_context_delegates_to_composer() -> None:
    """TurnContext.build() should use PromptComposer internally."""
    from hachi.core.turn_context import TurnContext

    tc = TurnContext.build(
        turn_id="t1",
        session_id="s1",
        user_input="hi",
        system_prompt_base=_BRAIN,
        recalled_context="RECALL_PAYLOAD",
        user_profile_snapshot="PROFILE_FACTS",
    )
    assert _BRAIN in tc.cacheable_system
    assert "PROFILE_FACTS" in tc.cacheable_system
    assert "CURRENT TIME" in tc.dynamic_system
    assert "RECALL_PAYLOAD" in tc.dynamic_system
