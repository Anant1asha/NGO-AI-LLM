"""
Session Title Generation

Derives a short, human-readable title for a session from its opening exchange.

Titles make ``hachi session list`` scannable: instead of a wall of opaque
16-char IDs, each session shows what it was actually about. Generation is
best-effort — a model call produces a concise title, and a deterministic
fallback (the first line of the user's message, trimmed) is used whenever no
LLM client is available or the call fails. Generation never raises.
"""

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hachi.core.cost import CostTracker
    from hachi.core.llm import BaseLLMClient

logger = logging.getLogger(__name__)

#: Hard cap on stored title length. Keeps ``session list`` rows on one line.
MAX_TITLE_CHARS = 72

UNTITLED = "Untitled session"

_TITLE_SYSTEM_PROMPT = (
    "You write a short, specific title for a conversation between a user and an AI "
    "agent, based on its opening exchange. Respond with ONLY the title: no quotes, "
    "no trailing punctuation, no preamble or explanation. Use Title Case, keep it "
    "to 8 words or fewer, and capture the user's actual intent (e.g. "
    "'Fix Failing Login Tests', 'Plan Q3 Marketing Budget')."
)


def _truncate(text: str) -> str:
    """Trim *text* to ``MAX_TITLE_CHARS``, adding an ellipsis when shortened."""
    text = text.strip()
    if len(text) > MAX_TITLE_CHARS:
        return text[: MAX_TITLE_CHARS - 1].rstrip() + "…"
    return text


def fallback_title(user_message: str) -> str:
    """Deterministic title used when no LLM is available or generation fails.

    Takes the first non-empty line of the user's first message, collapses
    whitespace, and truncates. Always returns a non-empty string.
    """
    for line in (user_message or "").splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            return _truncate(cleaned)
    return UNTITLED


def _clean_title(raw: str) -> str:
    """Normalise a model-produced title: first line, no wrapping quotes or trailing
    punctuation, length-capped. Returns "" if nothing usable remains."""
    for line in (raw or "").splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        # Strip a single layer of wrapping quotes the model sometimes adds.
        if len(candidate) >= 2 and candidate[0] in "\"'" and candidate[-1] == candidate[0]:
            candidate = candidate[1:-1].strip()
        candidate = re.sub(r"[.!?,;:\s]+$", "", candidate).strip()
        if candidate:
            return _truncate(candidate)
    return ""


def generate_title(
    user_message: str,
    assistant_message: str = "",
    llm_client: "BaseLLMClient | None" = None,
    cost_tracker: "CostTracker | None" = None,
) -> str:
    """Produce a concise title for a session from its first exchange.

    Args:
        user_message: The user's first message (the primary signal).
        assistant_message: The agent's first reply, used as extra context.
        llm_client: Provider client for the title call. When ``None``, or when
            the call fails, a deterministic :func:`fallback_title` is returned.
        cost_tracker: Optional :class:`~hachi.core.cost.CostTracker`. When
            provided, the token usage from the title-generation LLM call is
            recorded so it is counted in the session cost totals. The model
            used is the one returned by the LLM response object.

    Returns:
        A non-empty, length-capped title string. Never raises.
    """
    user_message = (user_message or "").strip()
    if not user_message:
        return UNTITLED
    if llm_client is None:
        return fallback_title(user_message)

    # Imported lazily so this module stays import-light for callers that only
    # need fallback_title (e.g. the SessionStore migration path).
    from hachi.core.llm import Message

    prompt = f"User: {user_message[:600]}"
    assistant_message = (assistant_message or "").strip()
    if assistant_message:
        prompt += f"\nAgent: {assistant_message[:300]}"
    prompt += "\n\nTitle:"

    try:
        response = llm_client.generate(
            messages=[Message(role="user", content=prompt)],
            system_prompt=_TITLE_SYSTEM_PROMPT,
        )
        # Record token usage via the cost tracker when one is provided so that
        # title-generation cost is counted in session/daily spend totals.
        if cost_tracker is not None and hasattr(response, "usage") and response.usage is not None:
            try:
                model_id = getattr(response, "model", "") or getattr(llm_client, "model", "")
                cost_tracker.record(str(model_id), response.usage, feature="titling")
            except Exception as track_exc:
                logger.debug("generate_title: cost tracking failed: %s", track_exc)
        title = _clean_title(response.content or "")
        return title or fallback_title(user_message)
    except Exception as exc:  # network / SDK / provider errors must never bubble up
        logger.debug("Title generation failed, falling back to truncation: %s", exc)
        return fallback_title(user_message)
