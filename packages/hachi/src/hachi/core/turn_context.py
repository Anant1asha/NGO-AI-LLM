"""
Turn Context — Immutable per-request execution state

This module provides TurnContext, which captures all the immutable state needed
for a single turn of agent execution. Instead of mutating shared loop state
(base_system_prompt), each turn gets its own frozen context snapshot.

Benefits:
    - Thread-safe: no mutation of shared state
    - Traceable: full execution context is captured once at turn start
    - Testable: can pass context through mock pipelines
    - Serializable: can be logged and replayed for debugging
"""

import datetime
from dataclasses import dataclass

from hachi.core.prompt_composer import compose as _compose_prompt


# CPython 3.14 note: frozen+slots dataclasses raise TypeError (not FrozenInstanceError)
# for assignments to *undeclared* attributes; declared-field mutation still raises
# FrozenInstanceError correctly.  This is a CPython quirk, not user-visible at runtime.
@dataclass(frozen=True, slots=True)
class TurnContext:
    """
    Immutable execution context for a single agent turn.

    Captures all the dynamic/static state needed to run the LLM + tools
    in a single turn, preventing mutations to shared ExecutionLoop state.
    """

    # Turn identity
    turn_id: str
    session_id: str
    timestamp: str  # ISO format

    # User input for this turn
    user_input: str

    # Composed system prompt (time-aware, memory-aware, frozen for this turn)
    system_prompt: str

    # Prompt-cache-aware split of ``system_prompt``: ``cacheable_system`` is the
    # stable prefix (brain/.og/perms + session-frozen profiles) that carries the
    # cache breakpoint; ``dynamic_system`` is the per-turn tail (time, recalled
    # context) that must sit AFTER the breakpoint so it never invalidates the cache.
    cacheable_system: str = ""
    dynamic_system: str = ""

    # Workspace state snapshots (frozen at turn start)
    active_skill: str | None = None
    user_profile_snapshot: str | None = None
    agent_profile_snapshot: str | None = None
    recalled_context: str | None = None

    # Execution parameters
    max_iterations: int = 15

    # Origin metadata (for audit/tracing)
    surface: str = "cli"  # "cli", "tui", "web", "webhook", etc.
    source_ip: str | None = None

    @classmethod
    def build(
        cls,
        turn_id: str,
        session_id: str,
        user_input: str,
        system_prompt_base: str,
        *,
        active_skill: str | None = None,
        user_profile_snapshot: str | None = None,
        agent_profile_snapshot: str | None = None,
        recalled_context: str | None = None,
        max_iterations: int = 15,
        surface: str = "cli",
        source_ip: str | None = None,
    ) -> "TurnContext":
        """
        Factory method to build a TurnContext with proper timestamp and composition.

        Args:
            turn_id: Unique identifier for this turn (UUID or sequence)
            session_id: The session this turn belongs to
            user_input: The user's input for this turn
            system_prompt_base: Base system prompt (brain.og + skills + perms)
            active_skill: Current skill name if any
            user_profile_snapshot: User profile facts captured for this turn
            agent_profile_snapshot: Agent profile facts captured for this turn
            recalled_context: Pre-fetched context from memory
            max_iterations: Max loop iterations for this turn
            surface: Where this request originated (for audit)
            source_ip: Originating IP if remote (for audit)

        Returns:
            A fully initialized immutable TurnContext.
        """
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()

        # Delegate to PromptComposer for cache-aware prompt assembly.
        # cacheable_system: stable prefix (brain/.og/perms + session-frozen profiles)
        #   — carries the cache breakpoint, read from cache (0.1x) on every turn.
        # dynamic_system: per-turn tail (time header + recalled context)
        #   — must sit AFTER the breakpoint so it never invalidates the cache.
        cacheable_system, dynamic_system = _compose_prompt(
            stable_base=system_prompt_base,
            user_profile_snapshot=user_profile_snapshot,
            agent_profile_snapshot=agent_profile_snapshot,
            recalled_context=recalled_context,
        )

        # Full prompt keeps the stable content first (model reads instructions
        # before per-turn context); also the single-block fallback path then caches.
        # Guard against a trailing \n\n when dynamic_system is empty (LOW-017).
        if dynamic_system:
            composed_prompt = f"{cacheable_system}\n\n{dynamic_system}"
        else:
            composed_prompt = cacheable_system

        return cls(
            turn_id=turn_id,
            session_id=session_id,
            timestamp=timestamp,
            user_input=user_input,
            system_prompt=composed_prompt,
            cacheable_system=cacheable_system,
            dynamic_system=dynamic_system,
            active_skill=active_skill,
            user_profile_snapshot=user_profile_snapshot,
            agent_profile_snapshot=agent_profile_snapshot,
            recalled_context=recalled_context,
            max_iterations=max_iterations,
            surface=surface,
            source_ip=source_ip,
        )
