"""memory_graph.py — P3-01 M2: Stage-C graph expansion + resume-pack composer.

Stage-C pipeline:
  1. Caller provides seed nodes from MemoryIndex (top-k FTS5 hits).
  2. ``expand_graph()`` walks ≤2 hops along typed edges, applying suppression rules:
       - ``supersedes`` replaces the superseded node (stale truth filtered from output).
       - open ``task`` nodes of any seeded ``project`` are always joined.
       - ``caused_by`` chains attach to any blocked task.
  3. ``compose_resume_pack()`` renders the expanded node set into ≤600 tokens
     for injection into the dynamic prompt tail.

Edge vocabulary (from 04-memory-redesign.md §5):
  about, involves, decided_in, supersedes, caused_by, led_to, blocks, blocked_by, next
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum number of nodes after Stage-C expansion.
_MAX_EXPANDED = 12

# Edge types followed during expansion (excludes `supersedes` — handled separately).
_TRAVERSAL_EDGES = {
    "about",
    "involves",
    "caused_by",
    "led_to",
    "blocks",
    "blocked_by",
    "next",
    "decided_in",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A resolved memory node with its typed edges parsed out."""

    name: str
    role: str          # fact | preference | task | event | person | ...
    dense: str
    keywords: list[str] = field(default_factory=list)
    status: str = ""   # open | done | blocked (for task nodes)
    edges: dict[str, list[str]] = field(default_factory=dict)
    # Name this node supersedes (if any).
    supersedes: list[str] = field(default_factory=list)
    source_file: str = ""


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

_EDGE_RE = re.compile(r"->?\s*\[:(\w+)=([^\]]+)\]")
_NODE_BLOCK_RE = re.compile(
    r"::node\[(?P<name>[^\]]+)\]\n(?P<body>(?:->.*\n)*)", re.MULTILINE
)
_DENSE_RE = re.compile(r"::dense\n(?P<text>[^\n:][^\n]*(?:\n[^\n:][^\n]*)*)", re.MULTILINE)


def parse_memory_file(og_path: Path) -> list[GraphNode]:
    """Parse an .og memory file into a list of GraphNode objects."""
    try:
        text = og_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Extract dense blocks by name
    dense_map: dict[str, str] = {}
    # Split by ::node boundaries to assign dense blocks
    sections = re.split(r"(?=::node\[)", text)
    for section in sections:
        m_node = re.match(r"::node\[([^\]]+)\]", section)
        m_dense = re.search(r"::dense\n(.+?)(?=::|$)", section, re.DOTALL)
        if m_node and m_dense:
            name = m_node.group(1).strip()
            dense_map[name] = m_dense.group(1).strip().replace("\n", " ")[:300]

    nodes: list[GraphNode] = []
    for m in _NODE_BLOCK_RE.finditer(text):
        name = m.group("name").strip()
        body = m.group("body")

        role = "fact"
        status = ""
        edges: dict[str, list[str]] = {}
        supersedes: list[str] = []
        keywords: list[str] = []

        for em in _EDGE_RE.finditer(body):
            key = em.group(1).strip()
            val = em.group(2).strip()
            if key == "role":
                role = val
            elif key == "status":
                status = val
            elif key == "keywords":
                keywords = [k.strip() for k in val.split(",") if k.strip()]
            elif key == "supersedes":
                supersedes.append(val)
            elif key in _TRAVERSAL_EDGES:
                edges.setdefault(key, []).append(val)

        nodes.append(GraphNode(
            name=name,
            role=role,
            dense=dense_map.get(name, ""),
            keywords=keywords,
            status=status,
            edges=edges,
            supersedes=supersedes,
            source_file=str(og_path),
        ))

    return nodes


def load_memory_dir(memory_dir: Path) -> dict[str, GraphNode]:
    """Load all .og files from *memory_dir* into a name→GraphNode map."""
    index: dict[str, GraphNode] = {}
    for og_file in memory_dir.rglob("*.og"):
        for node in parse_memory_file(og_file):
            index[node.name] = node
    return index


# ---------------------------------------------------------------------------
# Stage-C expansion
# ---------------------------------------------------------------------------


def expand_graph(
    seed_names: list[str],
    node_index: dict[str, GraphNode],
    max_nodes: int = _MAX_EXPANDED,
) -> list[GraphNode]:
    """Expand seed nodes by walking ≤2 hops along typed edges.

    Rules (from 04-memory-redesign.md §4.2):
    - ``supersedes`` replaces the superseded node: the old node is **filtered out**
      of the result set (stale truth removed, still kept on disk).
    - Open ``task`` nodes belonging to any seeded ``project`` node are always joined.
    - ``caused_by`` chains attach to any blocked task (depth-limited to 2 hops).
    - Maximum *max_nodes* total nodes in the expanded set.

    Args:
        seed_names: Names of the initial top-k nodes from retrieval.
        node_index: Full name → GraphNode map loaded from memory files.
        max_nodes: Hard cap on the expanded result set size.

    Returns:
        Ordered list of GraphNode objects; seeds appear first.
    """
    superseded: set[str] = set()
    seen: set[str] = set()
    result: list[GraphNode] = []

    def _add(name: str, *, hop: int) -> None:
        if name in seen or len(result) >= max_nodes:
            return
        node = node_index.get(name)
        if node is None:
            return
        seen.add(name)
        # Collect nodes this one supersedes — mark them suppressed.
        for old in node.supersedes:
            superseded.add(old)
        result.append(node)
        if hop >= 2:
            return
        # Walk traversal edges (1 more hop)
        for edge_type, targets in node.edges.items():
            if edge_type in _TRAVERSAL_EDGES:
                for t in targets:
                    _add(t, hop=hop + 1)

    # Pass 1: seeds
    for name in seed_names:
        _add(name, hop=0)

    # Pass 2: auto-join open task nodes of any seeded project
    project_slugs = {n.name for n in result if n.role in ("fact", "project")}
    for node in list(node_index.values()):
        if node.role == "task" and node.status == "open":
            for edge_type, targets in node.edges.items():
                if edge_type == "about" and any(t in project_slugs for t in targets):
                    _add(node.name, hop=1)

    # Filter out superseded nodes
    return [n for n in result if n.name not in superseded]


# ---------------------------------------------------------------------------
# Resume-pack composer
# ---------------------------------------------------------------------------

_ROLE_LABEL: dict[str, str] = {
    "fact": "Fact",
    "task": "Task",
    "decision": "Decision",
    "event": "Event",
    "person": "Person",
    "preference": "Preference",
    "rule": "Rule",
    "project": "Project",
    "insight": "Insight",
    "artifact": "Artifact",
}


def compose_resume_pack(
    nodes: list[GraphNode],
    query: str = "",
    max_tokens: int = 600,
) -> str:
    """Render a Stage-C expanded node set into a concise memory-pack string.

    Targets ≤600 tokens for injection into the dynamic prompt tail.  The format
    is designed to be transparent to the model: each line is self-describing.

    Args:
        nodes: Expanded GraphNode list from ``expand_graph()``.
        query: Original user query (shown as context header when non-empty).
        max_tokens: Approximate character budget (1 token ≈ 4 chars).

    Returns:
        A formatted memory-pack string, or an empty string if *nodes* is empty.
    """
    if not nodes:
        return ""

    char_budget = max_tokens * 4
    lines: list[str] = []

    if query:
        lines.append(f"[Memory: relevant to \"{query[:80]}\"]")

    for node in nodes:
        label = _ROLE_LABEL.get(node.role, node.role.capitalize())
        status_tag = f" ({node.status})" if node.status else ""
        header = f"[{label}{status_tag}: {node.name}]"

        # Dense summary
        dense = node.dense.strip()
        if dense:
            body_lines = [f"  {dense}"]
        else:
            body_lines = []

        # Key edges (about / involves / blocks)
        for edge_type in ("about", "involves", "blocks", "blocked_by", "supersedes"):
            targets = node.edges.get(edge_type, [])
            for t in targets[:2]:  # at most 2 targets per edge type
                body_lines.append(f"  {edge_type}={t}")

        candidate = "\n".join([header] + body_lines)
        if len("\n".join(lines)) + len(candidate) + 2 > char_budget:
            lines.append("[… more memory nodes omitted to stay within budget]")
            break
        lines.append(candidate)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience: full pipeline
# ---------------------------------------------------------------------------


def retrieve_and_compose(
    query: str,
    memory_dir: Path,
    top_k_seeds: int = 5,
    max_tokens: int = 600,
) -> str:
    """Load memory dir, search for seeds, expand, and compose a resume-pack.

    This is the all-in-one entry point for the orchestrator to call at session
    resume / context-switch to inject relevant memory into the prompt tail.

    Args:
        query: User query or session topic for seed retrieval.
        memory_dir: Root of the ``memory/`` data directory.
        top_k_seeds: Number of seed nodes from FTS5 retrieval.
        max_tokens: Token budget for the composed pack.

    Returns:
        Formatted resume-pack string, or ``""`` if memory is empty or unavailable.
    """
    if not memory_dir.exists():
        return ""

    node_index = load_memory_dir(memory_dir)
    if not node_index:
        return ""

    # Simple seed selection: nodes whose name or dense contains query tokens.
    q_tokens = set(query.lower().split())
    scored: list[tuple[int, str]] = []
    for name, node in node_index.items():
        score = sum(
            1 for tok in q_tokens
            if tok in name.lower() or tok in node.dense.lower()
            or any(tok in kw.lower() for kw in node.keywords)
        )
        if score > 0:
            scored.append((score, name))
    scored.sort(key=lambda x: -x[0])
    seeds = [name for _, name in scored[:top_k_seeds]]

    if not seeds:
        # Fallback: return the most recent nodes (last-written first)
        seeds = list(node_index.keys())[-top_k_seeds:]

    expanded = expand_graph(seeds, node_index)
    return compose_resume_pack(expanded, query=query, max_tokens=max_tokens)
