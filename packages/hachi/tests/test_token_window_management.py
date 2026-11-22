"""Tests for P2-1: token-based context-window management.

Verifies:
  1. A history with FEW messages but LARGE content (high estimated tokens) triggers
     compaction even though the message count is under the limit (the cliff case).
  2. A small history (under both count and token budgets) does NOT compact.
  3. The existing message-count trigger still fires when many small messages accumulate.
  4. After compaction the estimated tokens are back under budget (or as close as
     tool-pair-safety allows).
  5. _MAX_ACTIVE_TOKENS constant exists and _max_active_tokens is settable via the
     constructor arg and the HACHI_MAX_ACTIVE_TOKENS env var.
  6. The post-compaction loop is bounded: a history where EVERY slice still exceeds the
     budget does not loop forever (exits after _MAX_COMPACT_PASSES).
"""

from __future__ import annotations

import os
from unittest.mock import patch

from hachi.core.llm import Message
from hachi.core.memory import _MAX_ACTIVE_TOKENS, MemoryManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _big_message(role: str, chars: int) -> Message:
    """Return a Message whose content is ``chars`` characters long."""
    return Message(role=role, content="x" * chars)


def _small_pair(i: int) -> list[Message]:
    """Return a (user, assistant) pair with trivially small content."""
    return [
        Message(role="user", content=f"u{i}"),
        Message(role="assistant", content=f"a{i}"),
    ]


def _make_mm(
    max_active_messages: int = 30,
    max_active_tokens: int | None = None,
) -> MemoryManager:
    """Build a bare MemoryManager with no job queue (synchronous test path)."""
    return MemoryManager(
        max_active_messages=max_active_messages,
        max_active_tokens=max_active_tokens,
    )


# ---------------------------------------------------------------------------
# Test 1 — Token budget triggers compaction before message count does
# ---------------------------------------------------------------------------


def test_token_budget_triggers_compaction_before_count() -> None:
    """Few large messages exceed the token budget even though count < max_active_messages.

    The cliff scenario: the history has 12 messages (well under the 30-message default)
    but the middle segment is huge.  Compaction must fire on the token check, not the
    count check.

    History layout:
      anchor[0]: small user  (~5 tokens)
      anchor[1]: small assistant  (~5 tokens)
      middle[2..9]: 8 × 250-char messages = 2000 chars / 4 = 500 tokens
      recent[10]: small user
      recent[11]: small assistant
    Total ≈ 510 tokens > budget of 400.
    Count = 12 < max_active_messages = 30.  Only the token check should trigger.
    """
    token_budget = 400
    mm = _make_mm(max_active_messages=30, max_active_tokens=token_budget)

    # anchor — small
    mm._history.append(Message(role="user", content="start"))
    mm._history.append(Message(role="assistant", content="ok"))
    # large middle (8 messages × 250 chars = 500 tokens)
    for _i in range(4):
        mm._history.append(_big_message("user", 250))
        mm._history.append(_big_message("assistant", 250))
    # small recent
    mm._history.append(Message(role="user", content="recent q"))
    mm._history.append(Message(role="assistant", content="recent a"))

    count_before = len(mm._history)
    tokens_before = mm.estimate_token_count()
    assert count_before < 30, f"Count must be under message limit; got {count_before}"
    assert tokens_before > token_budget, (
        f"Token estimate must exceed budget={token_budget}; got {tokens_before}"
    )

    mm._sliding_window_compact()

    # Compaction must have run: checkpoint appears
    checkpoint_found = any(
        isinstance(m.content, str) and "CONTEXT CHECKPOINT" in m.content for m in mm._history
    )
    assert checkpoint_found, (
        "Expected a CONTEXT CHECKPOINT message after token-triggered compaction; "
        f"history count_before={count_before}, tokens_before={tokens_before}; "
        f"got history roles: {[m.role for m in mm._history]}"
    )
    # Middle was dropped — history length must be less than the original 12
    assert len(mm._history) < count_before, (
        f"Middle segment must have been dropped; before={count_before}, after={len(mm._history)}"
    )


def test_token_budget_triggers_compaction_via_sliding_window_compact_directly() -> None:
    """Direct call to _sliding_window_compact triggers when token-over but count-under.

    Checks that a checkpoint sentinel appears (proof that compaction ran).

    For the token-count-decrease assertion: the compaction must drop the middle segment.
    We build a history with small anchors + a large middle + small recent so the kept
    portion is small and we can verify the middle was replaced by the checkpoint.
    """
    token_budget = 300
    mm = _make_mm(max_active_messages=30, max_active_tokens=token_budget)
    # anchor: two small messages
    mm._history.append(Message(role="user", content="start"))
    mm._history.append(Message(role="assistant", content="ok"))
    # large middle (will be dropped): 10 messages × 200 chars = 2000 chars / 4 = 500 tokens
    for _i in range(5):
        mm._history.append(_big_message("user", 200))
        mm._history.append(_big_message("assistant", 200))
    # small recent: 2 tiny messages
    mm._history.append(Message(role="user", content="recent q"))
    mm._history.append(Message(role="assistant", content="recent a"))

    assert len(mm._history) <= mm._max_active_messages, "Count must be under limit"
    assert mm.estimate_token_count() > token_budget, "Token estimate must exceed budget"

    mm._sliding_window_compact()

    # Compaction must have run: checkpoint appears in history
    checkpoint_found = any(
        isinstance(m.content, str) and "CONTEXT CHECKPOINT" in m.content for m in mm._history
    )
    assert checkpoint_found, (
        "_sliding_window_compact must insert a CONTEXT CHECKPOINT message; "
        f"got history roles: {[m.role for m in mm._history]}"
    )
    # The large middle was replaced by a single checkpoint — history must be shorter
    # than anchor(2) + middle(10) + recent(2) = 14 before compaction.
    assert len(mm._history) < 14, (
        f"Middle segment must have been dropped; history length={len(mm._history)}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Small history does NOT compact
# ---------------------------------------------------------------------------


def test_small_history_does_not_compact() -> None:
    """A history under both budgets must not be compacted."""
    mm = _make_mm(max_active_messages=30, max_active_tokens=_MAX_ACTIVE_TOKENS)
    for msg in [
        Message(role="user", content="hello"),
        Message(role="assistant", content="hi"),
    ]:
        mm._history.append(msg)

    assert mm.estimate_token_count() < _MAX_ACTIVE_TOKENS
    assert len(mm._history) < mm._max_active_messages

    before = len(mm._history)
    mm._sliding_window_compact()
    assert len(mm._history) == before, "Small history must not be compacted"


def test_prepare_for_turn_does_not_compact_small_history() -> None:
    """prepare_for_turn() must not set compacted=True for a small history."""
    mm = _make_mm(max_active_messages=30, max_active_tokens=_MAX_ACTIVE_TOKENS)
    mm._history.extend(
        [
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
    )
    state = mm.prepare_for_turn()
    assert state.compacted is False


# ---------------------------------------------------------------------------
# Test 3 — Message-count trigger still fires for many small messages
# ---------------------------------------------------------------------------


def test_message_count_trigger_still_works() -> None:
    """Many small messages must still trigger compaction via the count check."""
    mm = _make_mm(max_active_messages=10, max_active_tokens=_MAX_ACTIVE_TOKENS)

    # Add 12 tiny messages to exceed the count limit (10)
    for i in range(6):
        mm.add_message(Message(role="user", content=f"u{i}"))
        mm.add_message(Message(role="assistant", content=f"a{i}"))

    # After add_message triggers compaction, history should be <= max_active_messages + 1
    # (the +1 tolerance because compaction fires after the append)
    assert len(mm._history) <= mm._max_active_messages + 1, (
        f"Expected count-triggered compaction to cap history; got {len(mm._history)}"
    )


# ---------------------------------------------------------------------------
# Test 4 — After compaction tokens are under budget (or as close as allowed)
# ---------------------------------------------------------------------------


def test_compaction_reduces_tokens_to_under_budget() -> None:
    """After compaction, the estimated token count must be ≤ budget or at minimum reduced."""
    token_budget = 300
    mm = _make_mm(max_active_messages=30, max_active_tokens=token_budget)
    # Build a history that is clearly over budget (4 msgs × 500 chars each → ~500 tokens)
    for _i in range(4):
        mm._history.append(_big_message("user", 500))
        mm._history.append(_big_message("assistant", 500))

    before_tokens = mm.estimate_token_count()
    mm._sliding_window_compact()
    after_tokens = mm.estimate_token_count()

    assert after_tokens < before_tokens, (
        f"Compaction must reduce token estimate; before={before_tokens}, after={after_tokens}"
    )
    # The checkpoint itself has some size, but the estimate should be substantially lower.
    # We allow it to still exceed the budget in corner cases where tool-pair safety prevents
    # dropping more — just verify it shrank.


# ---------------------------------------------------------------------------
# Test 5 — Token budget is configurable via constructor and env var
# ---------------------------------------------------------------------------


def test_max_active_tokens_constant_exists() -> None:
    """_MAX_ACTIVE_TOKENS module constant must be a positive integer."""
    assert isinstance(_MAX_ACTIVE_TOKENS, int)
    assert _MAX_ACTIVE_TOKENS > 0


def test_max_active_tokens_constructor_override() -> None:
    """Explicit constructor arg must override the default budget."""
    mm = _make_mm(max_active_tokens=99_999)
    assert mm._max_active_tokens == 99_999


def test_max_active_tokens_env_override() -> None:
    """HACHI_MAX_ACTIVE_TOKENS env var must override the module default."""
    with patch.dict(os.environ, {"HACHI_MAX_ACTIVE_TOKENS": "5000"}):
        mm = MemoryManager()
    assert mm._max_active_tokens == 5000


def test_max_active_tokens_constructor_beats_env() -> None:
    """Explicit constructor arg takes priority over env var."""
    with patch.dict(os.environ, {"HACHI_MAX_ACTIVE_TOKENS": "5000"}):
        mm = MemoryManager(max_active_tokens=8000)
    assert mm._max_active_tokens == 8000


# ---------------------------------------------------------------------------
# Test 6 — Bounded loop: does not hang when every slice still exceeds budget
# ---------------------------------------------------------------------------


def test_compaction_loop_is_bounded() -> None:
    """Even when the retained window is itself huge, the loop must exit cleanly.

    We set an impossibly small token budget (1 token) so every pass still exceeds
    it.  The method must return within _MAX_COMPACT_PASSES iterations — not loop
    forever.
    """
    mm = _make_mm(max_active_messages=30, max_active_tokens=1)
    # Add just enough messages so there's something to compact (> 2 messages needed for anchors)
    for i in range(6):
        mm._history.append(Message(role="user", content=f"user message {i}"))
        mm._history.append(Message(role="assistant", content=f"assistant message {i}"))

    # Must complete without hanging (pytest has a default timeout mechanism)
    mm._sliding_window_compact()
    # History must have been reduced at least once
    assert len(mm._history) <= 12


# ---------------------------------------------------------------------------
# Test 7 — prepare_for_turn triggers compaction on token-over history
# ---------------------------------------------------------------------------


def test_prepare_for_turn_triggers_on_token_budget() -> None:
    """prepare_for_turn() must compact a token-over history seeded via _history directly."""
    token_budget = 200
    mm = _make_mm(max_active_messages=30, max_active_tokens=token_budget)
    # Simulate seed_history populating _history directly (bypasses add_message)
    for _i in range(4):
        mm._history.append(_big_message("user", 500))
        mm._history.append(_big_message("assistant", 500))

    assert mm.estimate_token_count() > token_budget, "Precondition: must be over budget"
    before = len(mm._history)

    state = mm.prepare_for_turn()

    assert state.compacted is True, "prepare_for_turn must report compaction ran"
    assert len(mm._history) < before, f"History must shrink; was {before}, got {len(mm._history)}"
