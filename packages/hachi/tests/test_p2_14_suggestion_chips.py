"""P2-14: Suggestion chips — post-setup first-magic prompts.

Tests:
- SuggestionChip: dataclass fields and defaults
- DEFAULT_CHIPS: non-empty, has composer chips, has utility chips
- chips_for_context: filters by integration; max_chips respected; composer first
- chips_for_context: no integration filter returns all chips
- render_chips_text: contains chip text; numbered; has header
- render_chips_text: returns empty string for empty list
"""

from __future__ import annotations


def test_suggestion_chip_fields():
    from hachi.core.suggestion_chips import SuggestionChip

    chip = SuggestionChip(
        text="What's the weather?",
        category="utility",
        integration="",
        composer=False,
        description="A weather chip",
    )
    assert chip.text == "What's the weather?"
    assert chip.category == "utility"
    assert chip.composer is False


def test_suggestion_chip_defaults():
    from hachi.core.suggestion_chips import SuggestionChip

    chip = SuggestionChip(text="Hello")
    assert chip.category == "utility"
    assert chip.integration == ""
    assert chip.composer is False
    assert chip.description == ""


def test_default_chips_non_empty():
    from hachi.core.suggestion_chips import DEFAULT_CHIPS

    assert len(DEFAULT_CHIPS) > 0


def test_default_chips_has_composer_chips():
    from hachi.core.suggestion_chips import DEFAULT_CHIPS

    assert any(c.composer for c in DEFAULT_CHIPS)


def test_default_chips_has_utility_chips():
    from hachi.core.suggestion_chips import DEFAULT_CHIPS

    assert any(c.category == "utility" for c in DEFAULT_CHIPS)


def test_default_chips_has_workflow_chips():
    from hachi.core.suggestion_chips import DEFAULT_CHIPS

    assert any(c.category == "workflow" for c in DEFAULT_CHIPS)


def test_chips_for_context_max_chips():
    from hachi.core.suggestion_chips import chips_for_context

    chips = chips_for_context(max_chips=3)
    assert len(chips) <= 3


def test_chips_for_context_composer_first():
    from hachi.core.suggestion_chips import chips_for_context

    chips = chips_for_context(prioritise_composer=True, max_chips=10)
    composer_chips = [c for c in chips if c.composer]
    non_composer_chips = [c for c in chips if not c.composer]
    if composer_chips and non_composer_chips:
        # All composer chips should appear before any non-composer chip
        last_composer_idx = max(chips.index(c) for c in composer_chips)
        first_non_composer_idx = min(chips.index(c) for c in non_composer_chips)
        assert last_composer_idx < first_non_composer_idx


def test_chips_for_context_filters_by_integration():
    from hachi.core.suggestion_chips import chips_for_context

    # With only gmail integration, slack/notion/calendar chips should be excluded.
    chips = chips_for_context(available_integrations={"gmail"}, max_chips=20)
    for chip in chips:
        assert chip.integration in ("", "gmail"), (
            f"Expected only gmail or no-integration chips, got: {chip.integration!r}"
        )


def test_chips_for_context_no_filter_returns_all_categories():
    from hachi.core.suggestion_chips import DEFAULT_CHIPS, chips_for_context

    chips = chips_for_context(available_integrations=None, max_chips=len(DEFAULT_CHIPS))
    categories = {c.category for c in chips}
    assert "utility" in categories
    assert "workflow" in categories


def test_chips_for_context_empty_integration_set_returns_only_no_integration():
    from hachi.core.suggestion_chips import chips_for_context

    chips = chips_for_context(available_integrations=set(), max_chips=20)
    for chip in chips:
        assert chip.integration == ""


def test_render_chips_text_contains_chip_text():
    from hachi.core.suggestion_chips import SuggestionChip, render_chips_text

    chips = [SuggestionChip(text="Do something useful")]
    output = render_chips_text(chips)
    assert "Do something useful" in output


def test_render_chips_text_is_numbered():
    from hachi.core.suggestion_chips import SuggestionChip, render_chips_text

    chips = [SuggestionChip(text="First chip"), SuggestionChip(text="Second chip")]
    output = render_chips_text(chips)
    assert "1." in output
    assert "2." in output


def test_render_chips_text_has_header():
    from hachi.core.suggestion_chips import SuggestionChip, render_chips_text

    chips = [SuggestionChip(text="x")]
    output = render_chips_text(chips, header="Custom header:")
    assert "Custom header:" in output


def test_render_chips_text_empty_returns_empty():
    from hachi.core.suggestion_chips import render_chips_text

    assert render_chips_text([]) == ""


def test_chips_for_context_returns_list():
    from hachi.core.suggestion_chips import chips_for_context

    result = chips_for_context()
    assert isinstance(result, list)
    assert all(hasattr(c, "text") for c in result)
