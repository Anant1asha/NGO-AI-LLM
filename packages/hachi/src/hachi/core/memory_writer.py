"""
MemoryWriter — P2-05 M1 write-side: serialise typed nodes to memory/*.og files.

Nodes are written in the OG format that MemoryIndex (P2-04) can immediately
index, so the read path (semantic_search via RRF) sees new facts on the next
turn without any conversion step.

File routing by node role:
  preference  → profile.og
  rule        → agent.og         (behavioral corrections the user gave the agent)
  fact        → projects/<slug>.og  (workspace/technical facts, or core_memory.og fallback)
  event       → journal/<session-id>.og
  task        → projects/<slug>.og  (tasks are project-scoped)
  person      → people/<name-slug>.og
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MemoryNode:
    """A typed memory node ready to be written to an .og file."""

    name: str
    role: str  # fact | preference | event | rule | task | person
    dense: str
    keywords: list[str] = field(default_factory=list)
    session_id: str = ""
    project_slug: str = ""
    person_slug: str = ""
    # P3-01: typed edge declarations (written as ->[:key=value] lines in the .og block)
    edges: list[str] = field(default_factory=list)
    # Optional status field used by task nodes ("open" | "done" | "blocked")
    status: str = ""


# ---------------------------------------------------------------------------
# OG serialisation helpers
# ---------------------------------------------------------------------------

_UNSAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _slugify(text: str, max_len: int = 48) -> str:
    """Convert arbitrary text into a safe OG node-name / file-stem slug."""
    slug = _UNSAFE_NAME_RE.sub("-", text.lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len] or "node"


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _node_block(node: MemoryNode, session_id: str = "") -> str:
    """Render a single OG ``::node`` block for the given node."""
    kw = ", ".join(node.keywords) if node.keywords else node.role
    lines: list[str] = [
        f"::node[{node.name}]",
        f"->[:role={node.role}]",
        f"->[:keywords={kw}]",
    ]
    if session_id or node.session_id:
        lines.append(f"->[:evidence=session:{node.session_id or session_id}]")
    if node.status:
        lines.append(f"->[:status={node.status}]")
    # P3-01: write typed edge declarations
    for edge in node.edges:
        # Normalise: ensure ->[:key=value] format
        e = edge.strip()
        if e and not e.startswith("->"):
            e = f"->[:about={e}]"
        if e:
            lines.append(e)
    lines += [
        f"->[:updated={_ts()}]",
        "::dense",
        node.dense,
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File routing
# ---------------------------------------------------------------------------


def _route(node: MemoryNode, memory_dir: Path) -> Path:
    """Return the .og file path for this node."""
    role = node.role
    if role == "preference":
        return memory_dir / "profile.og"
    if role == "rule":
        return memory_dir / "agent.og"
    if role == "person":
        slug = node.person_slug or _slugify(node.dense.split()[0] if node.dense else "person")
        return memory_dir / "people" / f"{slug}.og"
    if role == "event":
        session = node.session_id or "unknown"
        return memory_dir / "journal" / f"{session}.og"
    # fact / task → projects/<slug> or core fallback
    if node.project_slug:
        return memory_dir / "projects" / f"{node.project_slug}.og"
    return memory_dir / "core_memory.og"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


class MemoryWriter:
    """Appends typed MemoryNode objects to the correct memory/*.og files.

    Each call to write_nodes():
    1. Groups nodes by their target file.
    2. Reads existing node IDs from each file to avoid duplicates.
    3. Appends new nodes only.
    4. Optionally triggers an index refresh on the attached MemoryIndex.
    """

    def __init__(self, memory_dir: Path, graph_index: Any = None) -> None:
        self._memory_dir = memory_dir
        self._graph_index = graph_index  # optional MemoryIndex; refreshed after writes

    def write_fact(self, content: str, category: str = "workspace_state") -> str:
        """Convenience: write a single unstructured fact as a ``fact`` node.

        Used by ``FTS5MemoryProvider.upsert()`` to persist raw facts to .og files.

        Args:
            content:  The fact text to persist.
            category: Organisational tag (written as a keyword).

        Returns:
            The node name (content-addressed slug).
        """
        import hashlib

        node_name = "fact-" + hashlib.sha256(content.encode()).hexdigest()[:12]
        node = MemoryNode(
            name=node_name,
            role="fact",
            dense=content[:200],
            keywords=[category],
        )
        self.write_nodes([node])
        return node_name

    def write_nodes(
        self,
        nodes: list[MemoryNode],
        session_id: str = "",
        by_agent: str = "",
    ) -> int:
        """Write nodes to their respective .og files. Returns the count written.

        Args:
            nodes:      Nodes to persist.
            session_id: Session ID stamped on ``evidence=session:<id>`` edges.
            by_agent:   P4-01 provenance — when non-empty, appends a
                        ``->[:by=agent:<by_agent>]`` edge to every node so
                        the memory gardener can trace which sub-agent wrote it.
        """
        if not nodes:
            return 0

        # P4-01: inject provenance edge into each node before routing.
        if by_agent:
            provenance_edge = f"->[:by=agent:{by_agent}]"
            nodes = [
                MemoryNode(
                    name=n.name,
                    role=n.role,
                    dense=n.dense,
                    keywords=n.keywords,
                    session_id=n.session_id,
                    project_slug=n.project_slug,
                    person_slug=n.person_slug,
                    edges=list(n.edges) + [provenance_edge],
                    status=n.status,
                )
                for n in nodes
            ]

        # Group by target file
        by_file: dict[Path, list[MemoryNode]] = {}
        for node in nodes:
            target = _route(node, self._memory_dir)
            by_file.setdefault(target, []).append(node)

        written = 0
        for target_path, file_nodes in by_file.items():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            existing_ids = _read_node_ids(target_path)

            new_blocks: list[str] = []
            for node in file_nodes:
                if node.name in existing_ids:
                    # Update dense content of existing node by rewriting the block
                    _update_dense(target_path, node)
                    written += 1
                else:
                    new_blocks.append(_node_block(node, session_id))
                    written += 1

            if new_blocks:
                _append_blocks(target_path, new_blocks)

        if written and self._graph_index is not None:
            try:
                self._graph_index.refresh()
            except Exception:
                logger.debug("MemoryWriter: index refresh failed after write", exc_info=True)

        logger.debug("MemoryWriter: wrote %d nodes to %d files", written, len(by_file))
        return written

    def write_episode(
        self, session_id: str, summary: str, keywords: list[str] | None = None
    ) -> None:
        """Write a session-close episode node to journal/<session_id>.og."""
        node = MemoryNode(
            name=f"episode-{session_id}",
            role="event",
            dense=summary,
            keywords=keywords if keywords else ["session", "episode"],
            session_id=session_id,
        )
        self.write_nodes([node], session_id=session_id)


# ---------------------------------------------------------------------------
# Low-level file helpers
# ---------------------------------------------------------------------------

_NODE_ID_RE = re.compile(r"^::node\[([^\]]+)\]", re.MULTILINE)


def _read_node_ids(path: Path) -> set[str]:
    """Return the set of node names already present in an .og file."""
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    return {m.group(1) for m in _NODE_ID_RE.finditer(text)}


def _append_blocks(path: Path, blocks: list[str]) -> None:
    """Append new OG node blocks to the file, creating it with a ::meta header if new."""
    if not path.exists():
        header = f"::meta\n  title: {path.stem.replace('-', ' ').title()}\n  version: 1.0.0\n\n"
    else:
        header = ""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "\n" if existing and not existing.endswith("\n\n") else ""
    path.write_text(
        existing + separator + header + "\n".join(blocks),
        encoding="utf-8",
    )


def _update_dense(path: Path, node: MemoryNode) -> None:
    """Replace the ::dense content of an existing node in-place."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    # Find the node block and replace its ::dense section
    pattern = re.compile(
        rf"(::node\[{re.escape(node.name)}\][^\n]*(?:\n(?!::node)[^\n]*)*\n::dense\n)([^\n]*)",
        re.DOTALL,
    )
    new_text = pattern.sub(lambda m: m.group(1) + node.dense, text, count=1)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
