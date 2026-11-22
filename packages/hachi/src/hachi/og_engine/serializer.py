"""ObjectGraph (.og) serializer.

The counterpart to :mod:`hachi.og_engine.parser`. Turns an :class:`OGFile`
(or a single :class:`OGNode`) back into canonical ``.og`` text that the parser
re-reads identically. This is what makes *autonomous skill authoring* possible:
the agent describes a skill it just learned, and the engine persists it as a
real, re-loadable ObjectGraph file rather than a markdown blob.

Round-trip contract: ``parse_og_file(serialize_og_file(f))`` preserves meta,
index, changelog, and every node field the serializer emits.
"""

from __future__ import annotations

from hachi.og_engine.parser import OGFile, OGIndexEntry, OGNode


def index_entry_for_node(node: OGNode, confidence: float = 1.0) -> OGIndexEntry:
    """Derive the ``::index`` routing row for a node from its own metadata."""
    return OGIndexEntry(
        node_id=node.name,
        node_type=node.role or "skill",
        scope=node.scope or "all",
        confidence=confidence,
        keywords=list(node.keywords),
    )


def _escape_block(text: str) -> str:
    """Neutralize lines that would be misparsed as ObjectGraph markers.

    A content line beginning with ``::`` or ``->[:`` would otherwise be re-read by
    the parser as a new block/edge on reload, corrupting an agent-authored skill
    (a structural-injection risk). A single leading space makes the line ordinary
    content again — the parser anchors markers at column 0.
    """
    return "\n".join(
        (" " + line) if (line.startswith("::") or line.startswith("->[:")) else line
        for line in text.split("\n")
    )


def render_node(node: OGNode) -> str:
    """Render a single :class:`OGNode` as a ``::node`` block.

    Emits metadata edges first, then content blocks in a stable canonical order.
    Only non-empty fields are written so the output stays compact.
    """
    lines: list[str] = [f"::node[{node.name}]"]

    # Metadata edges (->[:key=value]) — must come before any content block.
    if node.role:
        lines.append(f"->[:role={node.role}]")
    if node.scope:
        lines.append(f"->[:scope={node.scope}]")
    if node.keywords:
        lines.append(f"->[:keywords={', '.join(node.keywords)}]")
    if node.requires:
        lines.append(f"->[:requires={', '.join(node.requires)}]")
    if node.requires_auth:
        lines.append(f"->[:requires_auth={', '.join(node.requires_auth)}]")

    # Content blocks. Verbatim blocks are escaped so embedded text that looks like
    # an ObjectGraph marker can't inject phantom blocks/edges on reload. (steps and
    # reference lines carry an "N. " / "key: " prefix so they're already safe; the
    # edges block legitimately starts with "->" so it is left intact.)
    if node.dense:
        lines.append("::dense")
        lines.append(_escape_block(node.dense))
    if node.warning:
        lines.append("::warning")
        lines.append(_escape_block(node.warning))
    if node.summary:
        lines.append("::summary")
        lines.append(_escape_block(node.summary))
    if node.full:
        lines.append("::full")
        lines.append(_escape_block(node.full))
    if node.steps:
        lines.append("::steps")
        lines.extend(f"{i}. {step}" for i, step in enumerate(node.steps, 1))
    if node.list_items:
        lines.append("::list")
        lines.extend(_escape_block(item) for item in node.list_items)
    if node.table:
        lines.append("::table")
        lines.append(_escape_block(node.table))
    for lang, code in node.code_blocks.items():
        lines.append(f"::code[lang={lang}]")
        lines.append(_escape_block(code))
    if node.example:
        lines.append("::example")
        lines.append(_escape_block(node.example))
    if node.note:
        lines.append("::note")
        lines.append(_escape_block(node.note))
    if node.reference:
        lines.append("::reference")
        lines.extend(f"{k}: {v}" for k, v in node.reference.items())
    if node.assertions:
        lines.append("::assertion")
        lines.extend(_escape_block(a) for a in node.assertions)
    if node.edges:
        lines.append("::edges")
        lines.extend(node.edges)

    return "\n".join(lines)


def serialize_og_file(og: OGFile) -> str:
    """Render a complete :class:`OGFile` to canonical ``.og`` text."""
    blocks: list[str] = []

    meta = og.meta
    if meta and any(
        (meta.title, meta.version, meta.author, meta.created, meta.domain, meta.scope != "all")
    ):
        meta_lines = ["::meta"]
        if meta.title:
            meta_lines.append(f"  title: {meta.title}")
        if meta.version:
            meta_lines.append(f"  version: {meta.version}")
        if meta.author:
            meta_lines.append(f"  author: {meta.author}")
        if meta.created:
            meta_lines.append(f"  created: {meta.created}")
        if meta.updated:
            meta_lines.append(f"  updated: {meta.updated}")
        if meta.domain:
            meta_lines.append(f"  domain: {meta.domain}")
        if meta.scope:
            meta_lines.append(f"  scope: {meta.scope}")
        blocks.append("\n".join(meta_lines))

    if og.index:
        index_lines = ["::index", "  # node-id | type | scope | conf | keywords"]
        for entry in og.index:
            kw = ", ".join(entry.keywords)
            index_lines.append(
                f"  {entry.node_id} | {entry.node_type} | {entry.scope} | {entry.confidence} | {kw}"
            )
        blocks.append("\n".join(index_lines))

    if og.changelog:
        log_lines = ["::changelog"]
        for entry in og.changelog:
            log_lines.append(
                f"  {entry.date} | {entry.action} | {entry.target} | {entry.description}"
            )
        blocks.append("\n".join(log_lines))

    for node in og.nodes:
        blocks.append(render_node(node))

    return "\n\n".join(blocks) + "\n"
