"""
ObjectGraph (.og) File Parser

This module is the lexical parser for the ObjectGraph file format. It converts raw `.og` text
into structured Python objects (OGFile, OGNode) that the engine can index and the agent can consume.

Architecture:
    OGFile (file-level container)
    ├── meta       — File metadata (title, version, author, domain, scope)
    ├── index      — Query routing table (the agent's navigation map)
    ├── schema     — Domain type definitions
    ├── changelog  — Delta loading entries for diff-aware reads
    └── nodes[]    — List of OGNode objects (the actual content)

The .og format implements the 3-Pass Reading Model:
    Pass 1: Read ::index (~30 tokens) — Agent knows what exists
    Pass 2: Read ::dense blocks (~10 tokens/node) — Agent gets compressed context
    Pass 3: Read ::full blocks (complete content) — Agent gets execution details

File-Level Tags (parsed from preamble, before any ::node):
    - ::meta       — File metadata (title, version, domain, scope, checksum)
    - ::index      — Query routing table for O(1) node lookup
    - ::schema     — Domain type definitions (node-types, edge-types, scope-levels)
    - ::changelog  — Structured diff entries for delta loading

Node-Level Tags (parsed within each ::node block):
    - ::dense      — Compressed keyword summary (Pass 2)
    - ::full       — Complete human-readable prose (Pass 3)
    - ::code[lang] — Executable code blocks with language tag
    - ::steps      — Ordered sequential instructions
    - ::list       — Unordered enumerable items
    - ::table      — Structured data (never summarized)
    - ::warning    — Critical callout (always read)
    - ::note       — Informational aside (optional)
    - ::example    — Concrete illustration (skippable if known)
    - ::reference  — External link or citation
    - ::summary    — Pre-written human summary
    - ::assertion  — Executable validation condition
    - ::edges      — Typed relationship declarations
    - ::traverse   — Traversal hints (entry, depth-limit, priority)
    - ::config     — Key-value configuration block
    - ::tool       — Tool definition block for LLM registration
    - ::api[name]  — API definition block for Universal REST Adapter
"""

import json
import re

from pydantic import BaseModel, Field

# ADV-025: Maximum nesting depth allowed when parsing JSON structures inside .og files
# (::api schema/headers blocks).  Deeply-nested payloads can exhaust the call stack via
# recursive descent in json.loads; we pre-check before calling it.
_JSON_MAX_DEPTH: int = 20

# ADV-025: Maximum number of ::node blocks allowed in a single .og file when parsed
# standalone (the engine enforces its own configurable cap in load_file; this parser-level
# guard is a defence-in-depth fallback that prevents runaway memory even if the engine
# cap is bypassed by a direct parse_og_file() call).
_PARSER_NODE_CAP: int = 10_000

# ==========================================
# Data Models
# ==========================================


class OGIndexEntry(BaseModel):
    """A single row in the ::index routing table.

    Each entry maps a node ID to its type, scope, confidence score,
    and searchable keywords — enabling O(1) query routing without
    reading any node content.
    """

    node_id: str = Field(..., description="The unique node identifier this entry routes to.")
    node_type: str = Field(
        default="step", description="Content type (step, concept, warning, example, etc.)."
    )
    scope: str = Field(
        default="all", description="Access scope (all, orchestrator, worker, readonly, admin)."
    )
    confidence: float = Field(
        default=1.0,
        description="Reliability score: 1.0=verified, 0.5=experimental, <0.3=deprecated.",
    )
    keywords: list[str] = Field(
        default_factory=list, description="Searchable keywords for query matching."
    )


class OGFileMeta(BaseModel):
    """File-level metadata parsed from the ::meta block.

    Contains identity, versioning, domain classification, and integrity
    information for the entire .og file.
    """

    title: str = Field(default="", description="Human-readable title of the file.")
    version: str = Field(default="", description="Semantic version string.")
    author: str = Field(default="", description="Author or team identifier.")
    created: str = Field(default="", description="Creation date (ISO format).")
    updated: str = Field(default="", description="Last update date (ISO format).")
    domain: str = Field(
        default="", description="Pipe-separated domain tags (e.g., 'deployment|python|devops')."
    )
    scope: str = Field(default="all", description="Default access scope for the file.")
    tools: str = Field(
        default="",
        description="Pipe-separated tool prefix patterns this role needs "
        "(e.g., 'google_*|slack_*|run_terminal_command').",
    )
    min_agent_version: str = Field(default="", description="Minimum OG Reader version required.")
    checksum: str = Field(default="", description="Integrity verification hash.")


class OGChangelogEntry(BaseModel):
    """A single entry in the ::changelog block.

    Enables delta loading: agents that have previously read this file
    can check only the changelog (~30 tokens) to discover what changed,
    then fetch only the modified nodes.
    """

    date: str = Field(..., description="Date of the change (YYYY-MM-DD).")
    action: str = Field(..., description="Change type: added, updated, deprecated, removed.")
    target: str = Field(..., description="The node ID or reference that was changed.")
    description: str = Field(default="", description="Brief description of the change.")


class OGNode(BaseModel):
    """Represents a single parsed node from an .og file.

    Each node is a self-contained unit of knowledge, behavior, or integration.
    Nodes are the fundamental atomic unit of ObjectGraph — every piece of
    content lives inside a node, and every node is independently addressable.
    """

    name: str = Field(..., description="The unique identifier of the node.")
    source_file: str = Field(
        default="", description="The absolute path to the .og file this node was parsed from."
    )

    # Metadata extracted from ->[:key=value] edges
    role: str = Field(
        default="general",
        description="The functional role (e.g., 'skill', 'rule', 'integration', 'env').",
    )
    scope: str = Field(
        default="public", description="Access scope (e.g., 'public', 'private', 'internal')."
    )
    keywords: list[str] = Field(
        default_factory=list, description="Searchable keywords for O(1) routing."
    )
    requires: list[str] = Field(
        default_factory=list, description="Names of other nodes this node depends on."
    )
    requires_auth: list[str] = Field(
        default_factory=list,
        description="Auth tokens required for this node (from ->[:requires_auth=...]).",
    )

    # Content blocks (ordered by reading pass depth)
    dense: str = Field(
        default="", description="Compressed keyword summary for Pass 2 (~10-15 tokens)."
    )
    full: str = Field(default="", description="Complete human-readable prose for Pass 3.")
    summary: str = Field(default="", description="Pre-written human summary of a long node.")
    code_blocks: dict[str, str] = Field(
        default_factory=dict,
        description="Executable code blocks keyed by language (e.g., {'python': '...'}).",
    )
    steps: list[str] = Field(
        default_factory=list, description="Ordered sequence of steps the agent must follow."
    )
    list_items: list[str] = Field(default_factory=list, description="Unordered enumerable items.")
    table: str = Field(default="", description="Structured data table (never paraphrased by LLM).")
    warning: str = Field(
        default="", description="Critical callout (always read, even in dense-only passes)."
    )
    note: str = Field(default="", description="Informational aside (lower priority than warning).")
    example: str = Field(
        default="", description="Concrete illustration (skippable via skip-if-known)."
    )
    reference: dict[str, str] = Field(
        default_factory=dict, description="External link or citation (url, title, accessed)."
    )

    # Agent behaviour blocks
    assertions: list[str] = Field(
        default_factory=list, description="Executable validation conditions the agent MUST verify."
    )

    # Navigation blocks
    edges: list[str] = Field(
        default_factory=list,
        description="Typed relationship declarations (e.g., '->[:requires] install').",
    )
    traverse: dict[str, str] = Field(
        default_factory=dict, description="Traversal hints (entry, depth-limit, priority, avoid)."
    )

    # Integration blocks (for role=integration and role=env nodes)
    config: dict[str, str] = Field(
        default_factory=dict, description="Key-value configuration for integrations."
    )
    tool_def: dict[str, str] = Field(
        default_factory=dict, description="Tool definition for LLM registration."
    )

    # API definitions for Universal REST Adapter
    api_defs: dict[str, dict[str, str]] = Field(
        default_factory=dict, description="API definitions parsed from ::api[name] blocks."
    )


class OGFile(BaseModel):
    """Represents a fully parsed .og file with file-level metadata and all nodes.

    This is the top-level container returned by parse_og_file(). It separates
    file-level concerns (meta, index, schema, changelog) from node-level content,
    enabling the 3-Pass Reading Model:

        Pass 1: Agent reads OGFile.index (~30 tokens) to know what exists.
        Pass 2: Agent reads specific OGNode.dense blocks for compressed context.
        Pass 3: Agent reads OGNode.full blocks for complete execution details.
    """

    source_file: str = Field(default="", description="Absolute path to the .og file.")
    meta: OGFileMeta = Field(
        default_factory=OGFileMeta, description="File-level metadata from ::meta block."
    )
    index: list[OGIndexEntry] = Field(
        default_factory=list, description="Query routing table from ::index block."
    )
    og_schema: dict[str, str] = Field(
        default_factory=dict, description="Domain type definitions from ::schema block."
    )
    changelog: list[OGChangelogEntry] = Field(
        default_factory=list, description="Delta loading entries from ::changelog block."
    )
    nodes: list[OGNode] = Field(default_factory=list, description="All parsed content nodes.")

    def get_index_prompt(self) -> str:
        """Format the index as a compact routing table for injection into a sub-agent's system
        prompt.

        Returns a token-efficient string that gives the agent a complete map of
        the file's contents without reading any node bodies.

        Returns:
            A formatted string like:
            # node-id       | type    | scope  | conf | keywords
            install         | step    | all    | 0.99 | install, setup, pip
        """
        if not self.index:
            return ""

        lines = ["# node-id | type | scope | conf | keywords"]
        for entry in self.index:
            kw_str = ", ".join(entry.keywords)
            lines.append(
                f"  {entry.node_id} | {entry.node_type} | {entry.scope} | "
                f"{entry.confidence} | {kw_str}"
            )
        return "\n".join(lines)

    def get_node_by_id(self, node_id: str) -> OGNode | None:
        """Retrieve a specific node by its name/ID.

        Args:
            node_id: The unique identifier of the node.

        Returns:
            The matching OGNode, or None if not found.
        """
        for node in self.nodes:
            if node.name == node_id:
                return node
        return None

    def filter_by_scope(self, agent_role: str = "all") -> "OGFile":
        """Return a filtered copy of this file containing only nodes visible to the given role.

        Implements Role-Based Access Control (RBAC) at the file level. Nodes with
        scope='all' are always included. Other nodes are only included if their
        scope matches the agent_role.

        Args:
            agent_role: The role of the requesting agent (e.g., 'orchestrator', 'worker').

        Returns:
            A new OGFile with filtered nodes and index entries.
        """
        filtered_nodes = [n for n in self.nodes if n.scope in ("all", "public", agent_role)]
        filtered_index = [e for e in self.index if e.scope in ("all", agent_role)]
        return OGFile(
            source_file=self.source_file,
            meta=self.meta,
            index=filtered_index,
            og_schema=self.og_schema,
            changelog=self.changelog,
            nodes=filtered_nodes,
        )


# ==========================================
# Regex Patterns
# ==========================================

NODE_PATTERN = re.compile(r"^::node\[(.+?)\]", re.MULTILINE)
EDGE_PATTERN = re.compile(r"^->\[:(.+?)=(.+?)\]", re.MULTILINE)
BLOCK_PATTERN = re.compile(
    r"^::(dense|assertion|steps|config|tool|api|full|code|list|table|warning|note|example|reference|edges|traverse|summary|schema-def)"
    # Accept an optional trailing plural "s" OUTSIDE the capture group, so shipped
    # skills using ::assertions / ::notes / ::examples / ::tables / ::configs parse
    # to the same canonical singular block_type (group 1) the dispatch chain expects.
    # The \b still rejects unrelated longer words (e.g. ::assertionfoo).
    r"s?\b"
    r"(?:\[(.+?)\])?",
    re.MULTILINE,
)

# File-level block patterns (appear in the preamble before any ::node)
# NOTE: Use \Z (end of entire string) instead of $ because re.MULTILINE
# makes $ match end-of-line, which would prematurely terminate the capture.
META_PATTERN = re.compile(r"^::meta\s*\n(.*?)(?=^::|\Z)", re.MULTILINE | re.DOTALL)
INDEX_PATTERN = re.compile(r"^::index\s*\n(.*?)(?=^::|\Z)", re.MULTILINE | re.DOTALL)
SCHEMA_PATTERN = re.compile(r"^::schema\s*\n(.*?)(?=^::|\Z)", re.MULTILINE | re.DOTALL)
CHANGELOG_PATTERN = re.compile(r"^::changelog\s*\n(.*?)(?=^::|\Z)", re.MULTILINE | re.DOTALL)


# ==========================================
# Main Parser Entry Point
# ==========================================


def parse_og_file(filepath: str) -> OGFile:
    """Parse a single .og file into a fully structured OGFile object.

    This is the main entry point for the parser. It handles both file-level
    tags (::meta, ::index, ::schema, ::changelog) from the preamble and
    node-level tags from each ::node block.

    Args:
        filepath: The absolute path to the .og file.

    Returns:
        An OGFile object containing all parsed metadata, index, and nodes.
    """
    with open(filepath, encoding="utf-8") as f:
        raw_text = f.read()

    # Split the file into individual node sections
    node_splits = NODE_PATTERN.split(raw_text)

    # node_splits[0] is the preamble (everything before the first ::node)
    # This is where ::meta, ::index, ::schema, ::changelog live.
    # After that, it alternates: [name, body, name, body, ...]
    preamble = node_splits[0] if node_splits else ""

    # Parse file-level tags from the preamble
    og_file = OGFile(source_file=filepath)
    og_file.meta = _parse_meta(preamble)
    og_file.index = _parse_index(preamble)
    og_file.og_schema = _parse_schema(preamble)
    og_file.changelog = _parse_changelog(preamble)

    # ADV-025: Pre-check the node count using the split result to fail fast
    # without allocating node objects for millions of entries.
    raw_node_count = (len(node_splits) - 1) // 2
    if raw_node_count > _PARSER_NODE_CAP:
        raise ValueError(
            f"File contains {raw_node_count} ::node blocks which exceeds the parser "
            f"hard cap of {_PARSER_NODE_CAP}. "
            "This is likely a malformed or malicious file (ADV-025)."
        )

    # Parse all node blocks
    i = 1  # Start after preamble
    while i < len(node_splits) - 1:
        node_name = node_splits[i].strip()
        node_body = node_splits[i + 1]
        i += 2

        node = _parse_node_body(node_name, node_body, filepath)
        og_file.nodes.append(node)

    return og_file


# ==========================================
# File-Level Tag Parsers
# ==========================================


def _parse_meta(preamble: str) -> OGFileMeta:
    """Parse the ::meta block from the file preamble.

    Extracts file-level identity, versioning, and integrity metadata.

    Args:
        preamble: The raw text before the first ::node.

    Returns:
        A populated OGFileMeta object.
    """
    meta = OGFileMeta()
    match = META_PATTERN.search(preamble)
    if not match:
        return meta

    data = _parse_key_value_block(match.group(1))
    meta.title = data.get("title", "")
    meta.version = data.get("version", "")
    meta.author = data.get("author", "")
    meta.created = data.get("created", "")
    meta.updated = data.get("updated", "")
    meta.domain = data.get("domain", "")
    meta.scope = data.get("scope", "all")
    meta.tools = data.get("tools", "")
    meta.min_agent_version = data.get("min-agent-version", "")
    meta.checksum = data.get("checksum", "")
    return meta


def _parse_index(preamble: str) -> list[OGIndexEntry]:
    """Parse the ::index routing table from the file preamble.

    The index is the single most critical structure in ObjectGraph. It gives
    the agent a complete map of every node in the file (~30 tokens) so it can
    make O(1) routing decisions without reading any node content.

    Expected format (pipe-delimited):
        # node-id | type | scope | conf | query-keywords
        install   | step | all   | 0.99 | install, setup, pip

    Args:
        preamble: The raw text before the first ::node.

    Returns:
        A list of OGIndexEntry objects.
    """
    entries: list[OGIndexEntry] = []
    match = INDEX_PATTERN.search(preamble)
    if not match:
        return entries

    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("::"):
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue

        entry = OGIndexEntry(node_id=parts[0])

        if len(parts) >= 2:
            entry.node_type = parts[1]
        if len(parts) >= 3:
            entry.scope = parts[2]
        if len(parts) >= 4:
            try:
                entry.confidence = float(parts[3])
            except ValueError:
                pass
        if len(parts) >= 5:
            entry.keywords = [kw.strip() for kw in parts[4].split(",") if kw.strip()]

        entries.append(entry)

    return entries


def _parse_schema(preamble: str) -> dict[str, str]:
    """Parse the ::schema block from the file preamble.

    Contains domain type definitions (node-types, edge-types, scope-levels)
    that constrain valid values within the file.

    Args:
        preamble: The raw text before the first ::node.

    Returns:
        A dictionary of schema definitions.
    """
    match = SCHEMA_PATTERN.search(preamble)
    if not match:
        return {}
    return _parse_key_value_block(match.group(1))


def _parse_changelog(preamble: str) -> list[OGChangelogEntry]:
    """Parse the ::changelog block from the file preamble.

    Enables delta loading: agents that have previously read this file check
    only the changelog to discover what changed, then fetch only modified nodes.

    Expected format (pipe-delimited):
        2025-04-15 | added   | node[kubernetes-deploy] | New Kubernetes support
        2025-04-10 | updated | node[install]           | Added --legacy-peer-deps flag

    Args:
        preamble: The raw text before the first ::node.

    Returns:
        A list of OGChangelogEntry objects.
    """
    entries: list[OGChangelogEntry] = []
    match = CHANGELOG_PATTERN.search(preamble)
    if not match:
        return entries

    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("::"):
            continue

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue

        entry = OGChangelogEntry(
            date=parts[0],
            action=parts[1],
            target=parts[2],
            description=parts[3] if len(parts) >= 4 else "",
        )
        entries.append(entry)

    return entries


# ==========================================
# Node-Level Parser
# ==========================================


def _parse_node_body(name: str, body: str, source_file: str) -> OGNode:
    """Parse the body text of a single node into a structured OGNode.

    Extracts all metadata edges (->[:key=value]) and content blocks
    (::dense, ::full, ::code, ::steps, etc.) from the raw text between
    this ::node declaration and the next.

    Args:
        name: The node's identifier.
        body: The raw text between this ::node and the next ::node.
        source_file: The originating file path.

    Returns:
        A fully populated OGNode.
    """
    node = OGNode(name=name, source_file=source_file)

    # Extract all metadata edges
    for match in EDGE_PATTERN.finditer(body):
        key = match.group(1).strip()
        value = match.group(2).strip()

        if key == "role":
            node.role = value
        elif key == "scope":
            node.scope = value
        elif key == "keywords":
            node.keywords = [kw.strip() for kw in value.split(",")]
        elif key == "requires":
            node.requires = [req.strip() for req in value.split(",")]
        elif key == "requires_auth":
            node.requires_auth = [req.strip() for req in value.split(",")]

    # Extract content blocks
    block_positions = [
        (m.group(1), m.group(2), m.start(), m.end()) for m in BLOCK_PATTERN.finditer(body)
    ]

    for idx, (block_type, block_arg, _start, end) in enumerate(block_positions):
        if idx + 1 < len(block_positions):
            next_start = block_positions[idx + 1][2]
            block_content = _clean_block_content(body[end:next_start])
        else:
            block_content = _clean_block_content(body[end:])

        if block_type == "dense":
            node.dense = block_content
        elif block_type == "full":
            node.full = block_content
        elif block_type == "code":
            lang = block_arg.replace("lang=", "") if block_arg and "lang=" in block_arg else "text"
            node.code_blocks[lang] = block_content
        elif block_type == "list":
            node.list_items = [line.strip() for line in block_content.splitlines() if line.strip()]
        elif block_type == "table":
            node.table = block_content
        elif block_type == "warning":
            node.warning = block_content
        elif block_type == "note":
            node.note = block_content
        elif block_type == "example":
            node.example = block_content
        elif block_type == "summary":
            node.summary = block_content
        elif block_type == "reference":
            node.reference = _parse_key_value_block(block_content)
        elif block_type == "edges":
            node.edges = [line.strip() for line in block_content.splitlines() if line.strip()]
        elif block_type == "traverse":
            node.traverse = _parse_key_value_block(block_content)
        elif block_type == "assertion":
            node.assertions = [line.strip() for line in block_content.splitlines() if line.strip()]
        elif block_type == "steps":
            # Strip existing numbering (e.g., "1. Read the code" → "Read the code")
            raw_steps = [line.strip() for line in block_content.splitlines() if line.strip()]
            node.steps = [re.sub(r"^\d+\.\s*", "", step) for step in raw_steps]
        elif block_type == "config":
            node.config = _parse_key_value_block(block_content)
        elif block_type == "tool":
            node.tool_def = _parse_key_value_block(block_content)
        elif block_type == "api":
            if block_arg:
                api_def = _parse_key_value_block(block_content)
                # Strict JSON validation for LLM Tool Generation
                if "schema" in api_def:
                    try:
                        # ADV-025: guard against deeply-nested JSON before parsing.
                        _check_json_depth(api_def["schema"])
                        json.loads(api_def["schema"])
                    except json.JSONDecodeError as e:
                        raise ValueError(
                            f"Invalid JSON schema in ::api[{block_arg}] of node '{name}': {e}"
                        ) from e
                if "headers" in api_def:
                    try:
                        # ADV-025: guard against deeply-nested JSON before parsing.
                        _check_json_depth(api_def["headers"])
                        json.loads(api_def["headers"])
                    except json.JSONDecodeError as e:
                        raise ValueError(
                            f"Invalid JSON headers in ::api[{block_arg}] of node '{name}': {e}"
                        ) from e

                # Check required fields
                if "endpoint" not in api_def:
                    raise ValueError(f"Missing 'endpoint' in ::api[{block_arg}] of node '{name}'")
                if "method" not in api_def:
                    api_def["method"] = "GET"

                node.api_defs[block_arg] = api_def

    return node


def _clean_block_content(raw: str) -> str:
    """Strip noise from extracted block content.

    Removes:
        - ::end markers (explicit block terminators)
        - Comment divider lines (# ──────...)
        - Leading/trailing whitespace

    Args:
        raw: The raw text extracted between two :: block markers.

    Returns:
        Cleaned content string.
    """
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        # Skip ::end markers
        if stripped == "::end":
            continue
        # Skip decorative comment dividers (lines that are mostly ─, =, -, #)
        if stripped.startswith("#") and len(stripped) > 3:
            non_decorator = stripped.lstrip("#").strip()
            if non_decorator and all(c in "─═━─-=~ " for c in non_decorator):
                continue
        lines.append(line)
    return "\n".join(lines).strip()


# ==========================================
# ADV-025: JSON depth guard
# ==========================================


def _check_json_depth(text: str, max_depth: int = _JSON_MAX_DEPTH) -> None:
    """Raise ValueError if the JSON string nests deeper than ``max_depth``.

    We scan the raw text character-by-character rather than doing a full parse
    so that we can reject the input before recursion starts.  This is a
    defence-in-depth guard against payloads crafted to exhaust the call stack
    via Python's recursive-descent json parser.

    Args:
        text: The raw JSON string to inspect.
        max_depth: Maximum allowed nesting depth (objects + arrays combined).

    Raises:
        ValueError: If the nesting depth exceeds ``max_depth``.
    """
    depth = 0
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            depth += 1
            if depth > max_depth:
                raise ValueError(
                    f"JSON nesting depth exceeds limit of {max_depth}; "
                    "file rejected to prevent stack exhaustion (ADV-025)"
                )
        elif ch in ("}", "]"):
            depth -= 1


# ==========================================
# Shared Utilities
# ==========================================


def _parse_key_value_block(text: str) -> dict[str, str]:
    """Parse a block of key=value or key: value pairs into a dictionary.

    Supports both `key=value` and `key: value` formats.
    Lines starting with '#' are treated as comments and skipped.

    Args:
        text: The raw block content.

    Returns:
        A dictionary of parsed key-value pairs.
    """
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Try key=value first, then key: value
        if "=" in line:
            key, _, value = line.partition("=")
        elif ":" in line:
            key, _, value = line.partition(":")
        else:
            continue

        result[key.strip()] = value.strip()
    return result
