"""ConversationMemory — narrow interface between ExecutionLoop and memory backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class IterationState:
    """Snapshot returned by prepare_for_turn(), consumed by the loop."""

    compacted: bool  # True if skill-switch compaction ran
    old_skill: str  # Skill that was compacted away (or "unknown")
    tool_results_cleared: int  # Count of stale tool results cleared
    history_repaired: int  # Count of orphaned tool_use blocks repaired


@runtime_checkable
class ConversationMemory(Protocol):
    """Minimal interface the ExecutionLoop requires from any memory backend."""

    @property
    def history(self) -> list[object]: ...

    @property
    def active_skill(self) -> str | None: ...

    def add_message(self, message: object) -> None: ...

    def prepare_for_turn(self) -> IterationState:
        """Run compaction, clearing, repair; return state snapshot for the loop."""
        ...

    def complete_task(self, user_query: str, result: str) -> None:
        """Finish the current task: sync facts and log to ledger."""
        ...

    def signal_skill_switch(self, new_skill_name: str) -> None: ...
