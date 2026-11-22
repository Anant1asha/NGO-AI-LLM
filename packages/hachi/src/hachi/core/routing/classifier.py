"""Turn complexity classifier for hot-path model tiering (P1-2).

Maps a single user turn to a :class:`~hachi.core.routing.capability.Capability`
using cheap lexical heuristics — no extra LLM call.  The result is a *routing hint*,
not a correctness gate: a wrong classification degrades routing quality, not output.

Rules (evaluated top-to-bottom; first match wins):

1. **LONG_CONTEXT** — estimated token count ≥ 4 000  (roughly 16 000 chars), or
   the prompt explicitly mentions large documents / files ("entire file", "full doc",
   "whole codebase", "all pages", etc.).
2. **CODING** — prompt contains a code fence (`` ``` ``), or two or more
   coding-specific keywords: ``def``, ``class``, ``import``, ``function``,
   ``implement``, ``refactor``, ``debug``, ``bug``, ``error``, ``exception``,
   ``syntax``, ``compile``, ``build``, ``test``, ``unittest``, ``pytest``,
   ``lint``, ``type hint``, ``type annotation``.
3. **REASONING** — multi-step / analytical cues: ``step by step``, ``explain``,
   ``analyse`` / ``analyze``, ``compare``, ``evaluate``, ``pros and cons``,
   ``trade-off``, ``why``, ``reasoning``, ``cause``, ``because``, ``therefore``,
   ``conclusion``, ``summarize`` / ``summarise`` — but only when the prompt is at
   least 200 characters (short "why?" questions don't warrant a reasoning upgrade).
4. **SUMMARIZATION** — contains ``summarize``, ``summarise``, ``tl;dr``,
   ``key points``, ``main points``, or ``abstract``.
5. **GENERAL** (default) — all other turns.

Note: ``GENERAL`` is not a member of :class:`Capability`; callers should treat it as
a sentinel and fall back to :attr:`~hachi.core.routing.router.ModelRouter.default_client`.
The function returns a ``Capability`` **or** the string literal ``"general"``.
Returning a string keeps the classifier dependency-free (no import of Capability needed
at the call site).
"""

from __future__ import annotations

import re

from hachi.core.routing.capability import Capability

# ---------------------------------------------------------------------------
# Token-length heuristic: assume ~4 chars per token (rough but fast).
# ---------------------------------------------------------------------------
_CHARS_PER_TOKEN = 4
_LONG_CONTEXT_TOKEN_THRESHOLD = 4_000  # tokens
_LONG_CONTEXT_CHAR_THRESHOLD = _LONG_CONTEXT_TOKEN_THRESHOLD * _CHARS_PER_TOKEN

# Minimum prompt length (chars) before the REASONING rule fires.
_REASONING_MIN_CHARS = 200

_LONG_CONTEXT_PHRASES: tuple[str, ...] = (
    "entire file",
    "full document",
    "whole document",
    "full doc",
    "whole codebase",
    "all pages",
    "full transcript",
    "entire transcript",
    "full report",
    "entire report",
    "whole file",
)

_CODING_KEYWORDS: frozenset[str] = frozenset(
    {
        "def ",
        "class ",
        "import ",
        "function",
        "implement",
        "refactor",
        "debug",
        " bug",
        " error",
        "exception",
        "syntax",
        "compile",
        "build ",
        " test",
        "unittest",
        "pytest",
        " lint",
        "type hint",
        "type annotation",
    }
)
_CODING_KEYWORD_THRESHOLD = 2  # at least this many hits to route as CODING

_REASONING_PHRASES: tuple[str, ...] = (
    "step by step",
    "step-by-step",
    "explain ",
    "explain,",
    "explain.",
    "analyse",
    "analyze",
    "compare",
    "evaluate",
    "pros and cons",
    "trade-off",
    "trade off",
    "why ",
    "reasoning",
    " cause ",
    "because",
    "therefore",
    "conclusion",
    "summarize",
    "summarise",
)

_SUMMARIZATION_PHRASES: tuple[str, ...] = (
    "summarize",
    "summarise",
    "tl;dr",
    "tldr",
    "key points",
    "main points",
    " abstract",
)

# Pre-compile the code-fence pattern once.
_CODE_FENCE_RE = re.compile(r"```")


def classify_turn_capability(user_input: str) -> Capability:
    """Classify *user_input* into the most appropriate :class:`Capability`.

    This is a pure function (no I/O, no LLM calls).  It returns a
    :class:`~hachi.core.routing.capability.Capability` to pass to
    :meth:`~hachi.core.routing.router.ModelRouter.select`.

    The mapping is deliberately conservative: prefer misclassifying a
    REASONING turn as GENERAL over wrongly routing a simple greeting to a
    heavyweight model.

    Args:
        user_input: The raw user message for this turn.  May be empty.

    Returns:
        The best-guess :class:`Capability` for routing purposes.
        Falls back to :attr:`Capability.SUMMARIZATION` for summarise-style
        prompts, :attr:`Capability.REASONING` for analytical multi-step
        prompts, :attr:`Capability.CODING` for code-heavy prompts,
        :attr:`Capability.LONG_CONTEXT` for very long inputs, and
        :attr:`Capability.REASONING` as the general-conversational fallback
        (every Anthropic model supports REASONING; using it as the default
        ensures the widest set of candidates in the router).
    """
    if not user_input:
        # Empty turns: use the safe general-reasoning default.
        return Capability.REASONING

    lower = user_input.lower()
    char_count = len(user_input)

    # Rule 1 — LONG_CONTEXT
    if char_count >= _LONG_CONTEXT_CHAR_THRESHOLD:
        return Capability.LONG_CONTEXT
    for phrase in _LONG_CONTEXT_PHRASES:
        if phrase in lower:
            return Capability.LONG_CONTEXT

    # Rule 2 — CODING
    if _CODE_FENCE_RE.search(user_input):
        return Capability.CODING
    coding_hits = sum(1 for kw in _CODING_KEYWORDS if kw in lower)
    if coding_hits >= _CODING_KEYWORD_THRESHOLD:
        return Capability.CODING

    # Rule 4 — SUMMARIZATION (checked before REASONING to avoid confusion:
    # "summarize" is a REASONING phrase too, so we give it its own tier)
    for phrase in _SUMMARIZATION_PHRASES:
        if phrase in lower:
            return Capability.SUMMARIZATION

    # Rule 3 — REASONING (only for longer prompts to avoid over-routing terse questions)
    if char_count >= _REASONING_MIN_CHARS:
        for phrase in _REASONING_PHRASES:
            if phrase in lower:
                return Capability.REASONING

    # Default: route as REASONING — every model supports it and it's the widest net.
    return Capability.REASONING
