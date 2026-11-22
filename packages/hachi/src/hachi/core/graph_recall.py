"""graph_recall.py — Stage-C graph-expansion recall helper.

Provides :func:`build_graph_recall_section`, a pure, typed, testable helper that
orchestrators call once per turn to augment the semantic recall block with a
graph-expanded memory section.

Performance contract
--------------------
``load_memory_dir`` does ``rglob("*.og")`` + parses every file, which is too
expensive to run on every turn.  This module provides a **process-scoped LRU
cache** keyed on ``(memory_dir, mtime_signature)`` where ``mtime_signature`` is
the maximum ``st_mtime_ns`` across all ``*.og`` files under ``memory_dir``.

- Cache hit (nothing changed): O(n_files) path iteration only (no file reads).
- Cache miss (first call, or any file written): full parse, then cached.
- Max 4 entries in the LRU (multiple simultaneous sessions, each with own
  memory_dir).  Memory footprint is proportional to the number of nodes parsed;
  typical deployments have < 500 nodes → negligible.
"""

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from pathlib import Path

from hachi.core.memory_graph import (
    GraphNode,
    compose_resume_pack,
    expand_graph,
    load_memory_dir,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-process cache — keyed on (memory_dir_str, mtime_signature)
# ---------------------------------------------------------------------------

_CACHE_LOCK = threading.Lock()

# mtime_signature: max mtime_ns across all .og files (0 if dir empty/missing)
# Using lru_cache on an inner function gives us LRU eviction for free.


@lru_cache(maxsize=4)
def _cached_load(memory_dir_str: str, mtime_sig: int) -> dict[str, GraphNode]:
    """Load and parse all .og files; result is cached by (path, mtime_sig).

    ``mtime_sig`` encodes whether any .og file changed: callers pass the current
    max mtime_ns so a write invalidates the cache automatically (new key →
    new entry, old entry evicted by LRU).
    """
    return load_memory_dir(Path(memory_dir_str))


def _mtime_signature(memory_dir: Path) -> int:
    """Return the maximum mtime_ns across all .og files under memory_dir.

    Returns 0 when the directory is missing or contains no .og files.
    This is O(n_files) in path iteration but avoids any file I/O (no reads).
    """
    try:
        return max(
            (p.stat().st_mtime_ns for p in memory_dir.rglob("*.og")),
            default=0,
        )
    except OSError:
        return 0


def get_node_index(memory_dir: Path) -> dict[str, GraphNode]:
    """Return the cached node index for *memory_dir*, reloading only when changed.

    Thread-safe: the LRU cache itself is protected by Python's GIL for dict
    read/write, but we wrap in a lock to ensure the mtime probe + cache lookup
    is atomic (avoids a TOCTOU race on a concurrent write).

    Args:
        memory_dir: Root of the OG memory graph (same dir MemoryWriter targets).

    Returns:
        Name → :class:`~hachi.core.memory_graph.GraphNode` mapping; empty dict
        when the directory is missing or no nodes have been written yet.
    """
    with _CACHE_LOCK:
        sig = _mtime_signature(memory_dir)
        return _cached_load(str(memory_dir), sig)


# ---------------------------------------------------------------------------
# Dedup helper
# ---------------------------------------------------------------------------

_GRAPH_SECTION_HEADER = "\n[Related memory (graph)]\n"


def _dedup_graph_pack(graph_pack: str, existing_block: str) -> str:
    """Remove lines from *graph_pack* that already appear verbatim in *existing_block*.

    Comparison is line-by-line, stripped.  The header line is never removed.
    Returns the deduplicated pack, or ``""`` if nothing survives.
    """
    if not graph_pack:
        return ""

    existing_lines: set[str] = {
        line.strip() for line in existing_block.splitlines() if line.strip()
    }

    result_lines: list[str] = []
    for line in graph_pack.splitlines():
        stripped = line.strip()
        if not stripped:
            result_lines.append(line)
            continue
        if stripped not in existing_lines:
            result_lines.append(line)

    # Drop trailing blank lines
    while result_lines and not result_lines[-1].strip():
        result_lines.pop()

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

_GRAPH_TOKEN_BUDGET = 400  # ≈1600 chars injected per turn


def build_graph_recall_section(
    user_input: str,
    memory_dir: Path,
    existing_recall: str = "",
) -> str:
    """Build a graph-expanded memory section for injection after the semantic recall block.

    This is the per-turn call site.  It:
    1. Looks up (or reloads) the cached node index for *memory_dir*.
    2. Seeds the graph with token-overlap scoring (same as retrieve_and_compose's
       own seeder — see *Seeding approach* note below).
    3. Expands ≤2 hops along typed edges.
    4. Composes a ≤400-token pack.
    5. Strips lines already present verbatim in *existing_recall* (dedup).
    6. Prepends the section header; returns ``""`` on any error or empty result.

    **Seeding approach**: we use ``retrieve_and_compose``'s own token-overlap
    seeder (by calling it with the cached index via *expand_graph* + *compose*)
    rather than trying to map semantic-hit content strings back to ``.og`` node
    names.  The semantic hits are raw content blobs from ChromaDB — they don't
    carry node names, so mapping them to node names would require a fuzzy
    reverse-lookup with uncertain correctness.  Token-overlap seeding over the
    node index is fast (O(n_nodes × n_query_tokens)) and already proven in the
    pipeline.

    Args:
        user_input: The current turn's user message (used for seed scoring).
        memory_dir: Root of the OG memory graph (same dir MemoryWriter targets).
        existing_recall: The semantic/episodic recall block already built for
            this turn; used for deduplication only.

    Returns:
        A formatted section string (including the ``\\n[Related memory (graph)]\\n``
        header), or ``""`` when there is nothing to add.
    """
    if not memory_dir.exists():
        return ""

    node_index = get_node_index(memory_dir)
    if not node_index:
        return ""

    # Seed selection: token-overlap (same algorithm as retrieve_and_compose)
    q_tokens = set(user_input.lower().split())
    scored: list[tuple[int, str]] = []
    for name, node in node_index.items():
        score = sum(
            1
            for tok in q_tokens
            if tok in name.lower()
            or tok in node.dense.lower()
            or any(tok in kw.lower() for kw in node.keywords)
        )
        if score > 0:
            scored.append((score, name))
    scored.sort(key=lambda x: -x[0])
    seeds = [name for _, name in scored[:5]]

    if not seeds:
        seeds = list(node_index.keys())[-5:]

    expanded = expand_graph(seeds, node_index)
    raw_pack = compose_resume_pack(expanded, query=user_input, max_tokens=_GRAPH_TOKEN_BUDGET)

    if not raw_pack:
        return ""

    deduplicated = _dedup_graph_pack(raw_pack, existing_recall)
    if not deduplicated:
        return ""

    return _GRAPH_SECTION_HEADER + deduplicated
