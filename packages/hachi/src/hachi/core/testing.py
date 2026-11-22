"""Test-support adapters for core protocols. Import only in tests."""

from __future__ import annotations

from hachi.core.conversation_memory import ConversationMemory, IterationState
from hachi.core.llm import Message


class InMemoryConversationMemory:
    """Minimal ConversationMemory for unit tests — no ChromaDB, no threads, no queues."""

    def __init__(self) -> None:
        self._history: list[Message] = []
        self._active_skill: str | None = None
        self._complete_task_calls: list[tuple[str, str]] = []

    @property
    def history(self) -> list[Message]:
        """The current conversation history."""
        return self._history

    @property
    def active_skill(self) -> str | None:
        """Currently active skill name."""
        return self._active_skill

    def add_message(self, message: Message) -> None:
        """Append a message to the history."""
        self._history.append(message)

    def prepare_for_turn(self) -> IterationState:
        """No housekeeping for test backends — return a zero-state snapshot."""
        return IterationState(
            compacted=False, old_skill="", tool_results_cleared=0, history_repaired=0
        )

    def complete_task(self, user_query: str, result: str) -> None:
        """Record the call for test assertions."""
        self._complete_task_calls.append((user_query, result))

    def signal_skill_switch(self, new_skill_name: str) -> None:
        """Track the active skill."""
        self._active_skill = new_skill_name


# Sanity check: InMemoryConversationMemory must satisfy the Protocol at import time.
assert isinstance(InMemoryConversationMemory(), ConversationMemory), (
    "InMemoryConversationMemory does not satisfy the ConversationMemory Protocol"
)
