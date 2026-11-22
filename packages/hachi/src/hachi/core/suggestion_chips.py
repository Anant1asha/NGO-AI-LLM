"""Suggestion chips — post-setup first-magic prompts.

Chips guide new users toward high-value actions within 5 minutes of install.
They are displayed after onboarding completes and prioritise workflow-creation
paths (Composer preview) alongside quick-win queries.

The caller selects chips from ``DEFAULT_CHIPS`` using ``chips_for_context()``
which filters by available integrations and whether a workflow already exists.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SuggestionChip:
    """A single suggestion chip shown to the user post-setup.

    Attributes:
        text:        The prompt text shown to the user.  When clicked/submitted
                     it is sent as a chat message verbatim.
        category:    Broad category: "utility", "workflow", "integration".
        integration: Optional integration required (e.g. ``"gmail"``, ``"slack"``).
                     Empty string means no specific integration needed.
        composer:    True when this chip is designed to walk the user into the
                     Workflow Composer preview flow.
        description: Tooltip-style explanation (shown in UI hover or TUI side text).
    """

    text: str
    category: str = "utility"
    integration: str = ""
    composer: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# Default chip library
# ---------------------------------------------------------------------------

DEFAULT_CHIPS: list[SuggestionChip] = [
    # Workflow / Composer chips (highest value — walk user into Composer)
    SuggestionChip(
        text="Set up a morning briefing for me — weather, emails, and calendar for today",
        category="workflow",
        composer=True,
        description="Creates a scheduled morning briefing workflow via Composer.",
    ),
    SuggestionChip(
        text="Create a workflow that summarises my Slack mentions every evening at 6pm",
        category="workflow",
        integration="slack",
        composer=True,
        description="Scheduled Slack digest via Composer.",
    ),
    SuggestionChip(
        text="Set up a daily expense summary from my Gmail receipts",
        category="workflow",
        integration="gmail",
        composer=True,
        description="Receipt-sweeper workflow via Composer.",
    ),
    SuggestionChip(
        text="Create a weekly review workflow that writes to Notion every Friday at 5pm",
        category="workflow",
        integration="notion",
        composer=True,
        description="Weekly review via Composer, saved to Notion.",
    ),
    # Integration quick-wins
    SuggestionChip(
        text="What emails did I miss today? Summarise them.",
        category="integration",
        integration="gmail",
        description="Gmail inbox triage — reads and summarises today's emails.",
    ),
    SuggestionChip(
        text="What meetings do I have this week?",
        category="integration",
        integration="calendar",
        description="Google Calendar weekly view.",
    ),
    SuggestionChip(
        text="Show me my urgent Slack messages from today",
        category="integration",
        integration="slack",
        description="Slack urgent-message filter.",
    ),
    SuggestionChip(
        text="What's in my Notion inbox?",
        category="integration",
        integration="notion",
        description="Notion page / database overview.",
    ),
    # Pure utility (no integration required)
    SuggestionChip(
        text="What's the weather like in Tokyo right now?",
        category="utility",
        description="Live weather via the weather skill.",
    ),
    SuggestionChip(
        text="Convert 500 USD to EUR",
        category="utility",
        description="Currency conversion via the currency skill.",
    ),
    SuggestionChip(
        text="Summarise the Wikipedia article on large language models",
        category="utility",
        description="Wikipedia summarisation skill.",
    ),
    SuggestionChip(
        text="What's the latest news in AI this week?",
        category="utility",
        description="Web search + summarisation.",
    ),
]


# ---------------------------------------------------------------------------
# Context-aware selection
# ---------------------------------------------------------------------------


def chips_for_context(
    available_integrations: set[str] | None = None,
    max_chips: int = 5,
    *,
    prioritise_composer: bool = True,
) -> list[SuggestionChip]:
    """Return a curated list of chips appropriate for the user's current context.

    Args:
        available_integrations:  Set of integration IDs the user has configured
                                 (e.g. ``{"gmail", "slack"}``).  Pass ``None``
                                 to skip integration filtering (show all).
        max_chips:               Maximum number of chips to return.
        prioritise_composer:     If True, Composer-opening chips appear first.

    Returns:
        An ordered list of up to ``max_chips`` chips, Composer-first when
        ``prioritise_composer`` is True.
    """
    if available_integrations is None:
        candidates = list(DEFAULT_CHIPS)
    else:
        candidates = [
            c
            for c in DEFAULT_CHIPS
            if not c.integration or c.integration in available_integrations
        ]

    if prioritise_composer:
        composer_chips = [c for c in candidates if c.composer]
        other_chips = [c for c in candidates if not c.composer]
        candidates = composer_chips + other_chips

    return candidates[:max_chips]


# ---------------------------------------------------------------------------
# Text rendering (for CLI and Telegram)
# ---------------------------------------------------------------------------


def render_chips_text(
    chips: list[SuggestionChip],
    *,
    header: str = "Try one of these to get started:",
) -> str:
    """Return a plain-text rendering of the chips suitable for CLI output.

    Each chip is numbered so the user can refer to it by number.
    """
    if not chips:
        return ""
    lines = [header]
    for i, chip in enumerate(chips, 1):
        lines.append(f"  {i}.  {chip.text}")
    return "\n".join(lines)
