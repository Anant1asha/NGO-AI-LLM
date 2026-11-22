"""Behavioral tests for brain.og hard constraints.

Guards the safety and persona guardrails declared in the shipped brain.og against
accidental deletion or silent removal during prompt composition.

Design rationale:
- Tests read the REAL shipped brain.og from its canonical path in the package
  (``src/hachi/default_skills/brain.og``).  They do NOT use inline fixtures so
  that removing a line from the source file causes the assertion to fail.
- The composed-prompt tests go one step further: they verify the constraint
  survives through ``_render_brain_prompt`` / ``build_stable_base`` so that a
  composer bug that silently drops a block would also be caught.
- Substring matching is case-insensitive and looks for a few distinctive words
  per constraint rather than an exact full-line match, so trivial whitespace or
  capitalisation changes do not produce false failures.
"""

from __future__ import annotations

import pathlib

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Canonical path to the shipped brain.og — same relative anchor used by workspace.py
_BRAIN_OG_PATH = (
    pathlib.Path(__file__).parent.parent / "src" / "hachi" / "default_skills" / "brain.og"
)


def _brain_og_text() -> str:
    """Return the raw text of the shipped brain.og.

    Fails fast if the file is missing so the error message is informative.
    """
    assert _BRAIN_OG_PATH.exists(), (
        f"Shipped brain.og not found at {_BRAIN_OG_PATH}. "
        "Has the default_skills directory been moved or renamed?"
    )
    return _BRAIN_OG_PATH.read_text(encoding="utf-8")


def _composed_brain_prompt() -> str:
    """Render the shipped brain.og through the production pipeline.

    Uses the same parser + renderer path that production does
    (``parse_og_file`` → ``_render_brain_prompt`` → ``build_stable_base``),
    ensuring the full composition stack is exercised.
    """
    from hachi.core.prompt_composer import build_stable_base
    from hachi.gateway.workspace import _render_brain_prompt
    from hachi.og_engine.parser import parse_og_file

    og_file = parse_og_file(str(_BRAIN_OG_PATH))
    brain_text = _render_brain_prompt(og_file)
    # Pass through build_stable_base (brain-only, no skills) to verify the
    # composer does not strip or transform the brain content.
    return build_stable_base(brain_text=brain_text)


# ---------------------------------------------------------------------------
# SOURCE-LEVEL TESTS
# Tests that the raw brain.og still declares each hard-constraint block.
# If someone deletes the guardrail from the source file, these fail first.
# ---------------------------------------------------------------------------


def test_brain_og_file_exists() -> None:
    """Sanity check: the shipped brain.og must be present and non-empty."""
    text = _brain_og_text()
    assert len(text) > 100, "brain.og appears to be empty or truncated"


def test_brain_og_no_hallucination_rule_present() -> None:
    """brain.og must declare the no-hallucination / no-fabrication guardrail.

    Guardrail: ``::warning`` block in the ``execution-principles`` node.
    The text "NEVER hallucinate tool outputs" is the explicit ban on fabricating
    tool results.  Losing this removes the LLM's strongest instruction not to
    invent data — a critical honesty constraint.
    """
    text = _brain_og_text().lower()
    # "hallucinate" + "tool" together uniquely identify this guardrail
    assert "hallucinate" in text and "tool" in text, (
        "brain.og is missing the 'NEVER hallucinate tool outputs' guardrail "
        "(::warning in execution-principles). Deleting this allows the agent to "
        "fabricate tool results."
    )


def test_brain_og_no_claim_without_tool_use_rule_present() -> None:
    """brain.og must declare the rule against claiming completion without tool use.

    Guardrail: ``::warning`` block — "NEVER claim you completed a task without
    actually using tools".  This is the grounding constraint that prevents the
    agent from confirming success for work it never actually did.
    """
    text = _brain_og_text().lower()
    assert "claim" in text and "completed" in text and "tools" in text, (
        "brain.og is missing the 'NEVER claim completed without tools' guardrail. "
        "Removing this allows the agent to confirm tasks as done when no tool was called."
    )


def test_brain_og_destructive_command_confirmation_rule_present() -> None:
    """brain.og must declare that destructive commands require explicit confirmation.

    Guardrail: ``::full`` in the ``tool-philosophy`` node — "Never run destructive
    commands (rm -rf, format) without explicit user confirmation".
    This is the primary safeguard against irreversible filesystem damage.
    """
    text = _brain_og_text().lower()
    # "destructive" + "confirmation" together identify this constraint
    assert "destructive" in text and "confirmation" in text, (
        "brain.og is missing the destructive-command confirmation guardrail "
        "(tool-philosophy::full). Without this, the agent may run rm -rf or format "
        "commands without asking the user first."
    )


def test_brain_og_execution_engine_identity_present() -> None:
    """brain.og must declare the non-chatbot execution-engine identity.

    Guardrail: ``::full`` in the ``identity`` node — "You are NOT a chatbot.
    You are an execution engine".  This identity anchor prevents the agent from
    slipping into passive advice-giving rather than actually using tools to do work.
    """
    text = _brain_og_text().lower()
    assert "not a chatbot" in text and "execution engine" in text, (
        "brain.og is missing the 'not a chatbot / execution engine' identity guardrail. "
        "Removing this changes the agent's fundamental operating mode."
    )


def test_brain_og_skill_search_first_rule_present() -> None:
    """brain.og must declare the skill-search-before-acting routing rule.

    Guardrail: ``::full`` in ``tool-philosophy`` and ``skill-routing`` nodes —
    "ALWAYS check for relevant skills before improvising" / "Before attempting any
    non-trivial task, call search_skills".  This is the core .og competitive moat:
    without it the agent ignores its skill library and hallucinates procedures.
    """
    text = _brain_og_text().lower()
    assert "search_skills" in text or "search skills" in text, (
        "brain.og is missing the 'search skills before acting' routing rule. "
        "The skill-first lookup is the core .og differentiator — its absence means the "
        "agent will improvise rather than following tested blueprints."
    )


def test_brain_og_warning_blocks_are_hard_constraints_rule_present() -> None:
    """brain.og must declare that ::warning blocks are hard constraints.

    Guardrail: ``::full`` in ``skill-routing`` node — "When a skill has ::warning
    blocks, treat them as hard constraints — never violate them".  This meta-rule
    ensures all ::warning annotations across the entire skill library are respected.
    Removing it makes every other warning advisory rather than mandatory.
    """
    text = _brain_og_text().lower()
    assert "hard constraints" in text and "warning" in text, (
        "brain.og is missing the meta-rule that ::warning blocks are hard constraints. "
        "Without it the agent treats all safety warnings as optional suggestions."
    )


# ---------------------------------------------------------------------------
# COMPOSITION TESTS
# Tests that each guardrail survives the full render pipeline into the
# composed system prompt.  A bug in _render_brain_prompt or build_stable_base
# that silently drops a section would be caught here even if the source is fine.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def composed_prompt() -> str:
    """Render the composed prompt once for all composition tests in this module."""
    return _composed_brain_prompt()


def test_no_hallucination_rule_survives_composition(composed_prompt: str) -> None:
    """The no-hallucination guardrail must appear in the final composed prompt.

    Verifies that ``_render_brain_prompt`` and ``build_stable_base`` do not
    drop the ``::warning`` block from the ``execution-principles`` node.
    """
    text = composed_prompt.lower()
    assert "hallucinate" in text, (
        "The 'NEVER hallucinate tool outputs' constraint from brain.og was lost "
        "during prompt composition. Check _render_brain_prompt's warning-block "
        "rendering (Layer 2 — Hard Constraints)."
    )


def test_destructive_command_rule_survives_composition(composed_prompt: str) -> None:
    """The destructive-command confirmation rule must appear in the composed prompt.

    Verifies the ``::full`` content of ``tool-philosophy`` (role=rule) is
    rendered by Layer 3 of ``_render_brain_prompt``.
    """
    text = composed_prompt.lower()
    assert "destructive" in text and "confirmation" in text, (
        "The destructive-command confirmation guardrail from brain.og was lost "
        "during prompt composition. Check _render_brain_prompt's rule-node rendering."
    )


def test_execution_engine_identity_survives_composition(composed_prompt: str) -> None:
    """The non-chatbot execution-engine identity must appear in the composed prompt.

    Verifies the ``::full`` content of the ``identity`` persona node is rendered
    by Layer 1 of ``_render_brain_prompt``.
    """
    text = composed_prompt.lower()
    assert "not a chatbot" in text and "execution engine" in text, (
        "The 'not a chatbot / execution engine' identity from brain.og was lost "
        "during prompt composition. Check _render_brain_prompt's persona-node rendering."
    )


def test_hard_constraints_section_present_in_composed_prompt(
    composed_prompt: str,
) -> None:
    """The composed prompt must contain the ``--- HARD CONSTRAINTS ---`` section header.

    Verifies that ``_render_brain_prompt`` actually emits the section separator
    when warning blocks are present, not just their raw content.  This guards
    against the renderer silently skipping the warning aggregation loop.
    """
    assert "HARD CONSTRAINTS" in composed_prompt, (
        "The '--- HARD CONSTRAINTS ---' section header is missing from the composed "
        "prompt.  brain.og has ::warning blocks but _render_brain_prompt did not render "
        "them into the Hard Constraints section (Layer 2)."
    )
