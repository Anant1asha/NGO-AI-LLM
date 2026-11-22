"""
Memory Provider Interface

Abstract base class that defines the contract for all memory backends.
Enables swapping ChromaDB for alternative backends (Qdrant, Pinecone, Honcho)
without touching core agent code.

The default implementation (ChromaMemoryProvider) wraps the existing MemoryVault,
ensuring zero behavioral change while enabling future extensibility.

Lifecycle hooks:
    initialize()     — called once at boot
    upsert()         — store a fact
    search()         — semantic retrieval
    delete()         — remove a fact
    sync_turn()      — called after every completed turn (optional)
    on_session_end() — called at shutdown (optional)
    shutdown()       — cleanup resources (optional)
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hachi.core.settings import MemorySettings


class MemoryProvider(ABC):
    """Abstract memory backend interface.

    Subclass this to create custom memory backends. Only upsert, search,
    delete, and initialize are required — all lifecycle hooks have no-op
    defaults so backends only implement what they need.
    """

    @abstractmethod
    def initialize(self, brain_dir: str) -> None:
        """Initialize the backend storage.

        Args:
            brain_dir: The base directory for persistent storage.
        """

    @abstractmethod
    def upsert(self, content: str, category: str = "workspace_state") -> str:
        """Store an atomic fact. Returns the fact ID or an error string.

        Args:
            content: The fact text to persist.
            category: Organizational tag for filtering.

        Returns:
            The unique fact ID, or a 'BLOCKED:<reason>' string on rejection.
        """

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic similarity search.

        Args:
            query: Natural language query to match against stored facts.
            top_k: Maximum number of results to return.

        Returns:
            Ranked list of fact dicts with id, content, category, timestamp, raw_content.
        """

    @abstractmethod
    def delete(self, fact_id: str) -> bool:
        """Remove a fact by ID.

        Args:
            fact_id: The unique identifier of the fact to remove.

        Returns:
            True if deletion succeeded.
        """

    def sync_turn(self, user_content: str, assistant_content: str) -> None:  # noqa: B027
        """Optional: called after every completed turn for background extraction."""

    def on_session_end(self, messages: list[Any]) -> None:  # noqa: B027
        """Optional: called at shutdown for end-of-session processing."""

    def shutdown(self) -> None:  # noqa: B027
        """Optional: release resources."""


class ChromaMemoryProvider(MemoryProvider):
    """Default provider that wraps the existing MemoryVault.

    This adapter ensures backward compatibility — the entire Phase 1-3
    memory system works through this provider without any behavioral change.
    """

    def __init__(self, vault: Any = None) -> None:
        """Initialize with an optional pre-existing vault.

        Args:
            vault: An existing MemoryVault instance. If None, one will be
                   created during initialize().
        """
        self._vault: Any = vault

    @property
    def vault(self) -> Any:
        """Direct access to the underlying MemoryVault for tools that need it."""
        return self._vault

    def initialize(
        self,
        brain_dir: str,
        *,
        recall_distance_max: float | None = None,
        core_memory_max_entries: int | None = None,
        decay_half_life_days: float | None = None,
    ) -> None:
        """Create a MemoryVault if one wasn't provided at construction time.

        Args:
            brain_dir: Base directory for the ChromaDB persistent store.
            recall_distance_max: Optional cosine-distance ceiling for recall
                filtering (Issue 10). ``None`` keeps the MemoryVault default.
            core_memory_max_entries: Optional soft cap on the ``core_memory``
                collection (Issue 10). ``None`` keeps the MemoryVault default.
            decay_half_life_days: Optional recency-decay half-life in days (M2).
                ``None`` disables decay (MemoryVault default). Only re-ranks
                relevance-gated recall; never applies to user_profile or
                get_recent_facts.
        """
        if self._vault is None:
            from hachi.core.memory_vault import MemoryVault

            _kwargs: dict[str, Any] = {"brain_dir": brain_dir}
            if recall_distance_max is not None:
                _kwargs["recall_distance_max"] = recall_distance_max
            if core_memory_max_entries is not None:
                _kwargs["core_memory_max_entries"] = core_memory_max_entries
            if decay_half_life_days is not None:
                _kwargs["decay_half_life_days"] = decay_half_life_days
            self._vault = MemoryVault(**_kwargs)

    def upsert(self, content: str, category: str = "workspace_state") -> str:
        """Delegate to MemoryVault.upsert_fact()."""
        result: str = self._vault.upsert_fact(content, category)
        return result

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Delegate to MemoryVault.semantic_search()."""
        results: list[dict[str, Any]] = self._vault.semantic_search(query, top_k)
        return results

    def delete(self, fact_id: str) -> bool:
        """Delegate to MemoryVault.delete_fact()."""
        result: bool = self._vault.delete_fact(fact_id)
        return result

    def sync_turn(self, user_content: str, assistant_content: str) -> None:
        """No-op — sync_turn is handled by MemoryManager.sync_turn() already."""
        pass

    def shutdown(self) -> None:
        """ChromaDB PersistentClient handles its own cleanup."""
        pass


class InMemoryProvider(MemoryProvider):
    """Lightweight in-process memory provider with no external dependencies.

    Facts are stored in a plain list; search uses simple keyword overlap
    scoring. Data is NOT persisted across process restarts.

    Useful for:
    - Unit tests / CI (no ChromaDB process required)
    - Minimal deployments that don't need durable semantic memory
    - Rapid prototyping
    """

    def __init__(self) -> None:
        self._facts: list[dict[str, Any]] = []

    def initialize(self, brain_dir: str) -> None:
        """No-op — in-memory needs no disk setup."""

    def upsert(self, content: str, category: str = "workspace_state") -> str:
        """Store a fact; returns a new UUID as the fact ID."""
        fact_id = str(uuid.uuid4())
        self._facts.append(
            {
                "id": fact_id,
                "content": content,
                "raw_content": content,
                "category": category,
                "timestamp": "",
            }
        )
        return fact_id

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Keyword-overlap search (no embeddings); returns top_k results ranked by term hits."""
        query_terms = set(query.lower().split())
        if not query_terms:
            return []

        scored: list[tuple[int, dict[str, Any]]] = []
        for fact in self._facts:
            text_terms = set(fact["content"].lower().split())
            score = len(query_terms & text_terms)
            if score > 0:
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:top_k]]

    def delete(self, fact_id: str) -> bool:
        """Remove a fact by ID."""
        before = len(self._facts)
        self._facts = [f for f in self._facts if f["id"] != fact_id]
        return len(self._facts) < before

    def shutdown(self) -> None:
        """Clear all in-memory facts."""
        self._facts.clear()


class FTS5MemoryProvider(MemoryProvider):
    """FTS5-only memory provider — no ChromaDB required.

    Reads from ``.og`` memory files via a MemoryIndex (FTS5 + graph expansion).
    Writes new facts as ``.og`` nodes via MemoryWriter.  Chroma is never
    initialized, making this backend viable in offline / lightweight environments.

    Wired automatically when ``memory.backend = "fts5_only"`` in config.
    """

    def __init__(self) -> None:
        self._graph_index: Any = None
        self._memory_writer: Any = None
        self._brain_dir: str = ""

    def initialize(self, brain_dir: str) -> None:
        """Record brain_dir for lazy index/writer creation."""
        self._brain_dir = brain_dir

    def attach_graph_index(self, index: Any) -> None:
        """Bind the FTS5 MemoryIndex so search() can delegate to it."""
        self._graph_index = index

    def attach_memory_writer(self, writer: Any) -> None:
        """Bind the MemoryWriter so upsert() persists facts to .og files."""
        self._memory_writer = writer

    def upsert(self, content: str, category: str = "workspace_state") -> str:
        """Write a fact as an .og node via MemoryWriter; returns node ID."""
        if self._memory_writer is not None:
            try:
                result = self._memory_writer.write_fact(content, category=category)
                return str(result)
            except Exception:
                pass
        # Fallback: return a UUID so callers don't crash on None.
        return str(uuid.uuid4())

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """FTS5 similarity search via the attached MemoryIndex."""
        if self._graph_index is None:
            return []
        try:
            results: list[dict[str, Any]] = self._graph_index.search(query, top_k=top_k)
            return results
        except Exception:
            return []

    def delete(self, fact_id: str) -> bool:
        """Not supported for file-based facts; always returns False."""
        return False

    def shutdown(self) -> None:
        """No resources to release."""


def resolve_provider(memory_settings: MemorySettings) -> MemoryProvider:
    """Factory: return the correct MemoryProvider for the configured backend.

    Called once at orchestrator boot.  Keeps provider selection out of the
    orchestrator so backends can be swapped without touching boot logic.

    Args:
        memory_settings: The ``memory`` section of the resolved config.

    Returns:
        An *uninitialized* provider.  The caller must call ``initialize()``
        before the first ``upsert()`` / ``search()`` call.
    """
    backend = (memory_settings.backend or "chroma").strip().lower()
    if backend == "in_memory":
        return InMemoryProvider()
    if backend == "fts5_only":
        return FTS5MemoryProvider()
    # Default: ChromaDB-backed vault.
    return ChromaMemoryProvider()
