"""
ObjectGraph Skill Engine

This module is the brain indexer for Hachi. On boot, it scans the user's ~/.hachi/skills/
directory, parses every .og file, and builds a fast in-memory index. When the agent receives
a user query, it uses this engine to find the exact skill node it needs without loading
all skills into the context window.

Phase 4 additions:
    - Usage Tracking: Every load_skill call records a timestamp and increments the
      use_count in a persistent JSON file (~/.hachi/brain/skill_usage.json).
    - Stale Detection: get_stale_skills() returns skills not used in N days.
    - Analytics: get_usage_report() returns full lifecycle stats for all skills.

This is the core architectural advantage over agents like OpenClaw — instead of dumping
every skill into the system prompt (which bloats tokens and causes hallucination),
we provide surgical, O(1) keyword-based retrieval.
"""

import bisect
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from hachi.core import og_history
from hachi.core.atomic_io import atomic_write_json, quarantine_corrupt_file
from hachi.core.paths import get_hachi_paths
from hachi.og_engine.parser import (
    OGChangelogEntry,
    OGFile,
    OGFileMeta,
    OGNode,
    parse_og_file,
)
from hachi.og_engine.serializer import index_entry_for_node, serialize_og_file
from hachi.og_engine.skill_md import skill_md_to_og

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retrieval helpers: stopword-guarded tokenization + BM25 ranking
# ---------------------------------------------------------------------------

_NONWORD_RE = re.compile(r"[^\w]")

# Common English function words that add noise to skill queries.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "i",
        "we",
        "you",
        "he",
        "she",
        "it",
        "they",
        "them",
        "their",
        "this",
        "that",
        "these",
        "those",
        "and",
        "or",
        "but",
        "not",
        "no",
        "nor",
        "so",
        "for",
        "with",
        "from",
        "to",
        "at",
        "in",
        "on",
        "by",
        "of",
        "as",
        "can",
        "could",
        "will",
        "would",
        "should",
        "may",
        "might",
        "must",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "what",
        "how",
        "when",
        "where",
        "who",
        "why",
        "please",
        "help",
        "me",
        "my",
        "your",
    }
)

# Minimum token length to index/query (excludes single-char noise).
_MIN_TOKEN_LEN = 2

# C4 fix: minimum length for a token to act as a PREFIX source (distinct from
# _MIN_TOKEN_LEN, which governs exact-match indexing). A 2-3 char indexed token
# (e.g. "cap" from the keyword "market cap") over-matched as a prefix of unrelated
# longer words (e.g. "capacitor"), producing false positives on negative probes.
# Exact-match indexing via _MIN_TOKEN_LEN is untouched — short exact keywords like
# "qr" still work; only prefix-matching eligibility is raised.
_MIN_PREFIX_SOURCE_LEN = 4


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words, remove stopwords.

    Indexes node name + keywords as individual tokens for BM25 retrieval.
    Omits stopwords so short function words don't pollute query matching.
    """
    tokens = _NONWORD_RE.sub(" ", text.lower()).split()
    return [t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in _STOPWORDS]


# ---------------------------------------------------------------------------

# Upper bound (in estimated tokens) on a node's ::dense block. The dense block is
# the Pass-2 routing summary — if it grows into a paragraph it defeats the format.
DENSE_TOKEN_BUDGET = 30

# Default heavy blocks rendered by a Pass-3 load when the agent does not request
# a specific subset. Execution-critical content only — low-value asides (note,
# example, reference) are opt-in to keep loads lean.
DEFAULT_LOAD_BLOCKS: tuple[str, ...] = (
    "warning",
    "full",
    "steps",
    "code",
    "table",
    "assertions",
)

# Every renderable block, in stable priority order. Requesting "all" expands to this.
ALL_BLOCKS: tuple[str, ...] = (
    "warning",
    "dense",
    "summary",
    "full",
    "steps",
    "code",
    "table",
    "list",
    "example",
    "note",
    "reference",
    "assertions",
    "edges",
)


def estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate (~4 chars/token).

    Used for the Pass-2 block-cost manifest and the token-savings benchmark.
    Intentionally dependency-free so it works identically in CI and offline.

    Args:
        text: The string to measure.

    Returns:
        An approximate token count (minimum 1 for any non-empty string).
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _lint_result(path: Path, node_count: int, issues: list[dict[str, str]]) -> dict[str, Any]:
    """Assemble a lint report with an error/warning/info summary and an ``ok`` verdict."""
    errors = sum(1 for i in issues if i["level"] == "error")
    warnings = sum(1 for i in issues if i["level"] == "warning")
    info = sum(1 for i in issues if i["level"] == "info")
    return {
        "file": str(path),
        "ok": errors == 0,
        "node_count": node_count,
        "issues": issues,
        "summary": {"errors": errors, "warnings": warnings, "info": info},
    }


def lint_og_file(filepath: str | Path) -> dict[str, Any]:
    """Lint a single ``.og`` skill file for structural quality and token efficiency.

    Checks that authored/community skills follow the conventions the 3-pass loader
    relies on: every node is routable (has an ``::index`` entry + keywords), carries a
    within-budget ``::dense`` block for cheap Pass-2 peeking, has real Pass-3 content,
    and declares no dangling ``::index`` entries. Cross-file ``requires`` are reported
    as info (they may resolve elsewhere in the library), not errors.

    Returns:
        A report dict: ``file``, ``ok`` (no errors), ``node_count``, ``issues``
        (each ``{level, node, code, message}``), and a ``summary`` count map.
        ``ok`` is False only when there are errors; warnings are advisory.
    """
    path = Path(filepath)
    issues: list[dict[str, str]] = []

    def add(level: str, node: str, code: str, message: str) -> None:
        issues.append({"level": level, "node": node, "code": code, "message": message})

    if not path.exists():
        add("error", "*", "missing-file", f"File not found: {path}")
        return _lint_result(path, 0, issues)

    try:
        og = parse_og_file(str(path))
    except Exception as e:
        add("error", "*", "parse-error", f"Failed to parse: {e}")
        return _lint_result(path, 0, issues)

    nodes = og.nodes
    node_names = {n.name for n in nodes}
    index_ids = {e.node_id for e in og.index}

    if not nodes:
        add("error", "*", "no-nodes", "No ::node blocks found - file defines no skills.")

    for entry in og.index:
        if entry.node_id not in node_names:
            add(
                "warning",
                entry.node_id,
                "dangling-index",
                f"::index lists '{entry.node_id}' but no matching ::node exists.",
            )

    _SKILL_ROLES = frozenset({"skill", "native_integration"})

    for node in nodes:
        is_skill = node.role in _SKILL_ROLES
        structural_level = "error" if is_skill else "warning"

        if node.name not in index_ids:
            add(
                structural_level,
                node.name,
                "missing-index",
                "Node has no ::index entry - it won't be routable in Pass 1.",
            )
        if not node.keywords:
            add(
                "warning",
                node.name,
                "no-keywords",
                "Node has no keywords - it won't surface in search_skills.",
            )
        if not node.dense.strip():
            add(
                structural_level,
                node.name,
                "missing-dense",
                "Node has no ::dense block - Pass 2 (cheap peek) falls back to heavier blocks.",
            )
        else:
            tokens = estimate_tokens(node.dense)
            if tokens > DENSE_TOKEN_BUDGET:
                add(
                    structural_level,
                    node.name,
                    "dense-over-budget",
                    f"::dense is ~{tokens} tokens; budget is {DENSE_TOKEN_BUDGET}. Compress it.",
                )
        has_content = any(
            [
                node.full.strip(),
                node.steps,
                node.code_blocks,
                node.table.strip(),
                node.list_items,
                node.summary.strip(),
            ]
        )
        if not has_content:
            add(
                "info",
                node.name,
                "empty-node",
                "Node has metadata but no Pass-3 content (full/steps/code/table).",
            )
        for dep in node.requires:
            if dep not in node_names:
                add(
                    "info",
                    node.name,
                    "external-requires",
                    f"requires '{dep}' is not defined in this file "
                    "(ensure it exists elsewhere in your skill library).",
                )

    return _lint_result(path, len(nodes), issues)


class SkillEngine:
    """Central registry, retrieval engine, and lifecycle manager for .og skills.

    Maintains a persistent usage database (JSON) that tracks how often each
    skill is loaded, when it was first/last used, and whether it has gone stale.

    Scope enforcement is applied at query time via ``agent_role``. Nodes with
    ``scope="all"`` or ``scope="public"`` are always visible. Nodes with any
    other scope (e.g. ``"orchestrator"``, ``"admin"``) are only returned when
    ``agent_role`` matches that scope. The default ``"all"`` therefore exposes
    only publicly-visible nodes — callers that need elevated scopes (e.g. the
    main orchestrator reading ``brain.og``) must pass their role explicitly.
    """

    def __init__(self, agent_role: str = "*", node_cap: int = 5000) -> None:
        """Initialise the engine.

        Args:
            agent_role: The role of the agent that will query this engine.
                Nodes whose ``scope`` does not match this role (or ``"all"`` /
                ``"public"``) are hidden from all query results.

                Special values:

                - ``"*"`` (the default) bypasses all scope checks — every node
                  is returned.  Use this for CLI diagnostic tools (``skill
                  show``, ``skill search``, ``doctor``, etc.) where the human
                  user should see the full library.
                - ``"orchestrator"`` sees ``scope=all/public`` AND
                  ``scope=orchestrator`` nodes (brain.og identity + rules).
                  Pass this in :func:`create_agent_session` for the main
                  session engine.
                - Any other value (e.g. ``"analyst"``) sees only
                  ``scope=all/public`` nodes, hiding orchestrator-internal
                  nodes from worker sub-agents.
            node_cap: Maximum number of nodes allowed in a single .og file.
                Files that exceed this cap are rejected loudly (recorded in
                ``failed_files``) to prevent OOM from malicious or corrupt
                skill files.  Default: 5000.
        """
        self._agent_role = agent_role
        # Nodes are keyed by qualified ID: "<file-stem>:<node-name>".
        # Use _resolve_name() to look up by bare name (unambiguous) or qualified ID.
        self._nodes: dict[str, OGNode] = {}  # qualified_id -> OGNode
        self._keyword_index: dict[str, list[str]] = {}  # keyword -> [qualified_id, ...]
        # Bare-name → qualified-ID mapping for unambiguous resolution (migration shim).
        self._bare_name_index: dict[str, list[str]] = {}  # bare_name -> [qualified_id, ...]
        self._files: dict[str, OGFile] = {}  # filepath -> OGFile (file-level metadata + index)
        self._skills_dir: Path | None = None  # root dir; where authored skills are written
        self._skipped_files: list[dict[str, str]] = []  # legacy compat: mirrors _failed_files

        # BM25 retrieval structures (populated by load_file)
        self._token_index: dict[str, list[str]] = {}  # word token → [qualified_id, ...]
        self._df: dict[str, int] = {}  # document frequency: token → number of docs containing it
        self._doc_len: dict[str, int] = {}  # qualified_id → number of indexed tokens
        # Sorted view of _token_index keys for O(log V) prefix search via bisect.
        # Rebuilt lazily after load_file mutates _token_index (see _rebuild_sorted_tokens).
        self._sorted_tokens: list[str] = []
        self._sorted_tokens_dirty: bool = False  # True when _token_index has new keys

        # Phase 4: Persistent usage tracking (platformdirs state_dir)
        _paths = get_hachi_paths()
        self._usage_path = _paths.skill_usage_json
        self._usage: dict[str, dict[str, Any]] = self._load_usage()
        # Usage-write debounce: skip the disk write when a flush already happened
        # within _usage_flush_interval seconds.  The first call after boot (or after
        # the interval expires) always flushes so tests and one-shot runs see the file.
        self._usage_last_flush: float = 0.0  # monotonic time of last successful _save_usage
        self._usage_flush_interval: float = 30.0  # seconds between successive writes
        self._usage_lock: threading.Lock = threading.Lock()

        # UC-SKILL-003: Files that failed to parse are collected here so doctor/lint
        # can surface them as "N files failed to parse" instead of silently dropping them.
        # Each entry is a (Path, reason_str) tuple.
        self._failed_files: list[tuple[Path, str]] = []

        # ADV-025: Hard cap on nodes per file to prevent OOM from malicious .og files.
        # Configurable via the constructor; default is intentionally generous but bounded.
        self._node_cap: int = node_cap

        # M7: Pass-depth counters — incremented on each search/peek/resolve call.
        # Thread-safe via GIL (int increment); reset between benchmark runs.
        self._pass1_count: int = 0  # search() invocations
        self._pass2_count: int = 0  # peek() invocations
        self._pass3_count: int = 0  # resolve_node() invocations

        # P3-04: optional embedding-rank collection (ChromaDB cosine similarity).
        # None unless enable_embedding_rank() is called or HACHI_EMBEDDING_RANK=1.
        self._emb_collection: Any = None  # chromadb.Collection | None

    def _is_visible(self, node: OGNode) -> bool:
        """Return True when this node is accessible to the engine's agent role.

        ``scope="all"`` and ``scope="public"`` are always accessible.
        Any other scope (e.g. ``"orchestrator"``, ``"admin"``) is only
        accessible when ``self._agent_role`` exactly matches it.  The special
        role ``"*"`` bypasses all checks — used by CLI diagnostic tools.
        """
        if self._agent_role == "*":
            return True
        return node.scope in ("all", "public", self._agent_role)

    def _is_skill_node(self, node: OGNode) -> bool:
        """Return True if this node should appear in skill *search* results.

        brain.og nodes are identity/config, not capabilities — exclude them from
        the skill search surface so ``peek_skill("identity")`` stops rouletting.
        """
        if node.source_file:
            return Path(node.source_file).name.lower() != "brain.og"
        return True

    def _rebuild_sorted_tokens(self) -> None:
        """Rebuild the sorted token list from ``_token_index`` keys.

        Called lazily before a prefix search when new tokens were added since the last
        rebuild.  Sorting is O(V log V) but amortised over many queries; in practice
        ``load_directory`` is called once at boot and searches happen repeatedly.
        """
        self._sorted_tokens = sorted(self._token_index.keys())
        self._sorted_tokens_dirty = False

    def _prefix_matched_qids(self, qt: str) -> set[str]:
        """Return all qualified node IDs reachable via prefix-of-``qt`` tokens.

        A token in ``_token_index`` qualifies when it is:
        - at least ``_MIN_PREFIX_SOURCE_LEN`` characters long (C4: distinct from
          the shorter ``_MIN_TOKEN_LEN`` used for exact-match indexing — a 2-3
          char token is too short a prefix source and over-matches unrelated
          longer words),
        - a proper prefix of ``qt`` (tok != qt, and qt.startswith(tok)).

        Uses a sorted token list + ``bisect`` for O(log V) range entry instead of the
        original O(V) full-scan.  Results are identical to the naïve scan.

        Args:
            qt: A single query token (already lower-cased and stopword-filtered).

        Returns:
            Set of qualified node IDs that match any prefix token.
        """
        if self._sorted_tokens_dirty:
            self._rebuild_sorted_tokens()

        result: set[str] = set()
        tokens = self._sorted_tokens
        if not tokens:
            return result

        # All potential prefix tokens start at or after the minimum prefix of qt.
        # Use qt itself as the upper bound because a prefix must be strictly shorter.
        min_prefix = qt[:_MIN_PREFIX_SOURCE_LEN]
        lo = bisect.bisect_left(tokens, min_prefix)
        for i in range(lo, len(tokens)):
            tok = tokens[i]
            # Once the token sorts past qt, no further token can be a prefix of qt.
            if tok >= qt:
                break
            if len(tok) >= _MIN_PREFIX_SOURCE_LEN and qt.startswith(tok):
                result.update(self._token_index[tok])
        return result

    def _resolve_name(self, name: str) -> str | None:
        """Resolve a node name (bare or qualified) to a qualified ID.

        - ``"file-stem:node-name"`` → direct lookup (qualified).
        - ``"node-name"`` → unambiguous bare-name lookup via ``_bare_name_index``.
          Returns None if the bare name is absent or ambiguous (multiple files).

        Args:
            name: Bare node name or qualified ``stem:name`` identifier.

        Returns:
            The qualified ID string, or None if unresolvable.
        """
        if ":" in name:
            return name if name in self._nodes else None
        matches = self._bare_name_index.get(name, [])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            logger.debug(
                "Ambiguous bare name '%s' matches %d nodes (%s) — use qualified ID",
                name,
                len(matches),
                ", ".join(matches[:3]),
            )
        return None

    def with_role(self, agent_role: str) -> "SkillEngine":
        """Return a lightweight read-only view of this engine with a different role.

        The view shares the same underlying node/keyword/file data (no copy) but
        applies scope-filtering for ``agent_role`` on all queries.  Safe for
        concurrent use — the view never mutates shared state.

        Typical use: build one orchestrator-level engine at session boot, then
        create per-sub-agent views with ``engine.with_role(role)`` so each
        sub-agent only sees the skill nodes appropriate to its scope.

        Args:
            agent_role: The role to enforce.  ``"*"`` bypasses all checks;
                ``"orchestrator"`` additionally reveals ``scope=orchestrator``
                nodes; any other value sees only ``scope=all/public`` nodes.

        Returns:
            A new ``SkillEngine`` instance sharing data with this one, with
            ``_agent_role`` set to ``agent_role``.
        """
        view = SkillEngine.__new__(SkillEngine)
        view.__dict__.update(self.__dict__)
        view._agent_role = agent_role
        return view

    def load_directory(self, skills_dir: Path):
        """
        Scan a directory for .og files and index all nodes found within them.

        Args:
            skills_dir: The path to the skills directory (e.g., ~/.hachi/skills/).
        """
        self._skills_dir = skills_dir
        if not skills_dir.exists() or not skills_dir.is_dir():
            return

        for og_file in skills_dir.glob("**/*.og"):
            self.load_file(og_file)

        # P3-04: auto-enable embedding rank when env flag is set.
        import os as _os

        if _os.environ.get("HACHI_EMBEDDING_RANK", "").strip() == "1":
            self.enable_embedding_rank()

    def load_file(self, filepath: Path):
        """
        Parse a single .og file and add its nodes and file-level metadata to the index.

        Stores the full OGFile object (with ::meta, ::index, ::schema, ::changelog)
        alongside individual nodes for granular retrieval.

        Security hardening (ADV-011, ADV-025):
        - Node-count cap: files exceeding ``_node_cap`` are rejected to prevent OOM.
        - Guard scan: ``::full`` and ``::dense`` content of each node is screened
          by :func:`hachi.core.memory_guard.scan` before indexing. Flagged nodes
          are quarantined (marked ``_quarantined=True``) and not served to the LLM.
        - Parse failures (UC-SKILL-003): recorded in ``_failed_files`` so doctor/lint
          can surface them rather than silently dropping the skill.

        Args:
            filepath: Absolute path to the .og file.
        """
        # Deferred import keeps startup fast and avoids circular deps.
        from hachi.core.memory_guard import scan as _guard_scan

        def _record_failure(path: Path, reason: str) -> None:
            """Add to both the new typed list and the legacy dict list."""
            self._failed_files.append((path, reason))
            self._skipped_files.append({"file": str(path), "error": reason})

        try:
            og_file = parse_og_file(str(filepath))
        except Exception as e:
            # UC-SKILL-003: parse failure is now recorded in _failed_files, NOT just
            # a warning log that vanishes silently.
            reason = str(e)
            logger.warning("Failed to parse %s: %s", filepath, reason)
            _record_failure(filepath, reason)
            return

        # ADV-025: Reject files whose node count exceeds the configured cap.
        if len(og_file.nodes) > self._node_cap:
            reason = (
                f"node count {len(og_file.nodes)} exceeds cap {self._node_cap}; "
                "file rejected to prevent resource exhaustion"
            )
            logger.error("Skill file rejected — %s: %s", filepath, reason)
            _record_failure(filepath, reason)
            return

        self._files[str(filepath)] = og_file
        file_stem = filepath.stem

        for node in og_file.nodes:
            qualified_id = f"{file_stem}:{node.name}"

            # Hard collision guard: same stem+name from two different files means
            # the library has an unresolvable ambiguity — error loudly.
            if qualified_id in self._nodes:
                existing = self._nodes[qualified_id]
                logger.error(
                    "Node ID collision: '%s' already loaded from '%s'; "
                    "ignoring duplicate from '%s'. Rename one of the nodes.",
                    qualified_id,
                    existing.source_file,
                    filepath,
                )
                _record_failure(
                    filepath,
                    f"collision: '{qualified_id}' already loaded from '{existing.source_file}'",
                )
                continue

            # ADV-011: Screen ::full and ::dense content before indexing.
            # ::code and ::assertion blocks are deliberately NOT evaluated here —
            # they remain inert text.  Only the prose blocks that reach the LLM
            # context window need scanning.
            combined_prose = "\n".join(filter(None, [node.full, node.dense, node.summary]))
            if combined_prose:
                is_safe, threat_id = _guard_scan(combined_prose)
                if not is_safe:
                    logger.warning(
                        "Skill node '%s' in '%s' flagged by guard scan (%s); "
                        "node quarantined and will not be served to the LLM.",
                        node.name,
                        filepath,
                        threat_id,
                    )
                    _record_failure(
                        filepath,
                        f"node '{node.name}' quarantined: guard scan flagged '{threat_id}'",
                    )
                    # Mark on the node object so callers can inspect it, but do NOT
                    # add it to the searchable index.
                    object.__setattr__(node, "_quarantined", True) if False else None
                    # Use model_copy to tag the node as quarantined without mutation.
                    node = node.model_copy(
                        update={
                            "warning": (
                                f"[QUARANTINED: {threat_id}] "
                                + (node.warning or "Node blocked by security scan.")
                            )
                        }
                    )
                    # Store in _files for doctor inspection but skip the search index.
                    continue

            self._nodes[qualified_id] = node

            # Bare-name index for unambiguous backward-compat resolution
            if node.name not in self._bare_name_index:
                self._bare_name_index[node.name] = []
            self._bare_name_index[node.name].append(qualified_id)

            # Index every keyword → qualified ID for fast lookup
            for kw in node.keywords:
                kw_lower = kw.lower()
                if kw_lower not in self._keyword_index:
                    self._keyword_index[kw_lower] = []
                if qualified_id not in self._keyword_index[kw_lower]:
                    self._keyword_index[kw_lower].append(qualified_id)

            # BM25 token index: tokenize name + keywords, track DF and doc length
            bm25_text = node.name.replace("_", " ") + " " + " ".join(node.keywords)
            tokens = _tokenize(bm25_text)
            self._doc_len[qualified_id] = len(tokens)
            unique_tokens_this_doc: set[str] = set()
            for tok in tokens:
                self._token_index.setdefault(tok, []).append(qualified_id)
                if tok not in unique_tokens_this_doc:
                    self._df[tok] = self._df.get(tok, 0) + 1
                    unique_tokens_this_doc.add(tok)

        # Also index keywords from ::index entries for file-level routing
        for entry in og_file.index:
            # Index entries may reference bare names; qualify them if possible
            entry_qid = f"{file_stem}:{entry.node_id}"
            for kw in entry.keywords:
                kw_lower = kw.lower()
                if kw_lower not in self._keyword_index:
                    self._keyword_index[kw_lower] = []
                if entry_qid not in self._keyword_index[kw_lower]:
                    self._keyword_index[kw_lower].append(entry_qid)
                # Augment BM25 token index with ::index keywords so nodes that
                # declare keywords only in ::index (e.g. brain.og) are reachable.
                if entry_qid in self._nodes:
                    for tok in _tokenize(kw_lower):
                        existing_toks = self._token_index.get(tok, [])
                        if entry_qid not in existing_toks:
                            self._token_index.setdefault(tok, []).append(entry_qid)
                            self._df[tok] = self._df.get(tok, 0) + 1
                            self._doc_len[entry_qid] = self._doc_len.get(entry_qid, 0) + 1

        # Mark the sorted-token cache as stale so the next search() rebuilds it.
        self._sorted_tokens_dirty = True

    # ------------------------------------------------------------------
    # UC-SKILL-003: Parse-failure reporting
    # ------------------------------------------------------------------

    @property
    def failed_files(self) -> list[tuple[Path, str]]:
        """Return the list of files that failed to load, as (path, reason) tuples.

        UC-SKILL-003: Parse failures and security quarantines are no longer silently
        discarded. Callers (``doctor``, ``skill list``, CLI diagnostics) should inspect
        this list to report "N files failed to parse" with the reason for each.

        Returns:
            A list of ``(Path, reason_string)`` tuples in load order.
        """
        return list(self._failed_files)

    def get_parse_failures(self) -> list[dict[str, str]]:
        """Return parse/quarantine failures as serialisable dicts for CLI/doctor use.

        Returns:
            A list of ``{"file": str, "reason": str}`` dicts.
        """
        return [{"file": str(p), "reason": r} for p, r in self._failed_files]

    def search(self, query: str) -> list[dict[str, str]]:
        """
        Search the skill index by keyword matching against a natural language query.
        Returns a lightweight list of matching node summaries (name + role + keywords)
        so the agent can decide which skill to load in full.

        Args:
            query: A natural language query or keyword string from the agent.

        Returns:
            A list of dicts with 'name', 'role', 'keywords', and 'source_file' for each match,
            ranked by BM25 relevance score descending.
        """
        self._pass1_count += 1
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        N = len(self._doc_len)
        if N == 0:
            return []
        avg_dl = sum(self._doc_len.values()) / N
        k1, b = 1.5, 0.75

        # Collect candidates via token index.  For each query token, also check
        # prefix-match (e.g. "deployment" → "deploy") so stemming-style recall works.
        # HIGH-014: prefix search uses bisect on _sorted_tokens for O(log V) lookup
        # instead of the prior O(V) full dict-key scan.
        #
        # PERF-11: build prefix_qids_per_token in the same pass so _prefix_matched_qids
        # is called exactly once per query token (was called twice: once here for
        # candidate collection and again below for the BM25 scoring dict).
        candidate_qids: set[str] = set()
        prefix_qids_per_token: dict[str, set[str]] = {}
        for qt in query_tokens:
            for qid in self._token_index.get(qt, []):
                candidate_qids.add(qid)
            # Prefix match: index token is a prefix of the query token (O(log V))
            pqids = self._prefix_matched_qids(qt)
            prefix_qids_per_token[qt] = pqids
            candidate_qids.update(pqids)

        if not candidate_qids:
            return []

        # BM25 scoring — binary TF (presence) per token per doc
        scores: dict[str, float] = {}
        for qid in candidate_qids:
            node = self._nodes.get(qid)
            if node is None or not self._is_visible(node) or not self._is_skill_node(node):
                continue

            dl = self._doc_len.get(qid, 0)
            score = 0.0
            for qt in query_tokens:
                # Determine whether this query token matches anything in this doc
                tf = 1 if qt in self._token_index and qid in self._token_index[qt] else 0
                if tf == 0:
                    # Check prefix-matched tokens using pre-computed bisect result (O(1))
                    if qid in prefix_qids_per_token[qt]:
                        tf = 1
                if tf == 0:
                    continue

                # Use DF of the actual matched token (exact or closest prefix)
                df = self._df.get(qt, len(self._token_index.get(qt, [])))
                df = max(df, 1)
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                norm = k1 * (1 - b + b * dl / max(avg_dl, 1))
                score += idf * tf * (k1 + 1) / (tf + norm)

            if score > 0:
                scores[qid] = score

        # P3-04: Hybrid rank — merge BM25 and cosine (RRF) when embedding rank is on.
        emb_scores = self._embedding_search(query) if self._emb_collection is not None else {}
        if emb_scores and scores:
            # Reciprocal Rank Fusion: rank both lists independently and merge.
            k = 60  # standard RRF constant
            bm25_ranked = sorted(scores, key=lambda q: -scores[q])
            emb_ranked = sorted(emb_scores, key=lambda q: -emb_scores[q])
            rrf: dict[str, float] = {}
            for rank, qid in enumerate(bm25_ranked, 1):
                rrf[qid] = rrf.get(qid, 0.0) + 1.0 / (k + rank)
            for rank, qid in enumerate(emb_ranked, 1):
                rrf[qid] = rrf.get(qid, 0.0) + 1.0 / (k + rank)
            final_scores = rrf
        elif emb_scores:
            final_scores = emb_scores
        else:
            final_scores = scores

        # Sort by final score descending; use priority as a tiebreaker so nodes
        # with identical relevance respect their ::traverse priority annotation.
        _PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}

        def _sort_key(qid: str) -> tuple[float, int]:
            final_score = -final_scores[qid]  # negate: lower = better (descending sort)
            priority_rank = _PRIORITY_ORDER.get(
                (self._nodes[qid].traverse or {}).get("priority", "normal"), 1
            )
            return (final_score, priority_rank)

        sorted_qids = sorted(final_scores, key=_sort_key)
        results = []
        for qid in sorted_qids:
            node = self._nodes.get(qid)
            if node is not None:
                results.append(
                    {
                        "name": node.name,
                        "role": node.role,
                        "keywords": ", ".join(node.keywords),
                        "source_file": node.source_file,
                    }
                )
        return results

    # ==========================================
    # P3-04: Embedding-rank (hybrid BM25 + cosine)
    # ==========================================

    def enable_embedding_rank(self, collection_name: str = "og_skill_index") -> None:
        """Build (or refresh) a ChromaDB cosine-similarity collection over all loaded nodes.

        Off by default — call explicitly or set ``HACHI_EMBEDDING_RANK=1``.
        ChromaDB is already a transitive dependency (via memory_vault) so no
        new packages are required.

        Each node's document is ``"<name> <keywords> <dense_summary>"``.
        """
        try:
            import chromadb  # type: ignore[import-untyped]
            from chromadb.config import Settings  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("P3-04: chromadb not installed; embedding rank unavailable")
            return

        from hachi.core.paths import get_hachi_paths

        db_path = str(get_hachi_paths().state_dir / "og_skill_embeddings")
        client = chromadb.PersistentClient(
            path=db_path, settings=Settings(anonymized_telemetry=False)
        )
        col = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Upsert all visible skill nodes.
        ids, docs = [], []
        for qid, node in self._nodes.items():
            if not self._is_skill_node(node):
                continue
            doc = f"{node.name} {' '.join(node.keywords)} {node.dense or ''}"
            ids.append(qid)
            docs.append(doc)

        if ids:
            col.upsert(ids=ids, documents=docs)
        self._emb_collection = col
        logger.debug("P3-04: embedding index built (%d nodes)", len(ids))

    def _embedding_search(self, query: str, top_k: int = 10) -> dict[str, float]:
        """Query the Chroma cosine collection; return {qid: score} in [0, 1].

        Returns an empty dict if embedding rank is not enabled or query fails.
        """
        if self._emb_collection is None:
            return {}
        try:
            results = self._emb_collection.query(
                query_texts=[query],
                n_results=min(top_k, max(1, len(self._nodes))),
                include=["distances"],
            )
            ids = results.get("ids", [[]])[0]
            dists = results.get("distances", [[]])[0]
            # Chroma cosine distance ∈ [0, 2]; convert to similarity ∈ [0, 1].
            return {
                qid: max(0.0, 1.0 - (dist / 2.0))
                for qid, dist in zip(ids, dists, strict=False)
                if dist is not None and qid in self._nodes
            }
        except Exception:
            logger.debug("P3-04: embedding search failed", exc_info=True)
            return {}

    def list_all_skills(self) -> list[dict[str, str]]:
        """
        Return a summary of every loaded skill node visible to this engine's role.

        Nodes whose scope does not match the engine's ``agent_role`` are silently
        omitted, so the caller only sees skills it is allowed to use.

        Returns:
            A list of dicts with 'name', 'role', and 'keywords' for each
            accessible loaded node.
        """
        results = []
        for node in self._nodes.values():
            if not self._is_visible(node):
                continue
            results.append(
                {
                    "name": node.name,
                    "role": node.role,
                    "keywords": ", ".join(node.keywords),
                }
            )
        return results

    def get_node(self, name: str) -> OGNode | None:
        """
        Retrieve the full OGNode by its exact name.

        Nodes outside the engine's agent role scope are treated as if they
        do not exist (returns ``None``), so RBAC enforcement is consistent
        whether a caller uses the tool path or the direct accessor.

        Args:
            name: The node identifier (e.g., 'deploy_to_prod').

        Returns:
            The full OGNode or None if not found or not accessible.
        """
        qid = self._resolve_name(name)
        if qid is None:
            return None
        node = self._nodes.get(qid)
        if node is None or not self._is_visible(node):
            return None
        return node

    def get_all_nodes(self) -> list[OGNode]:
        """Return all indexed skill nodes visible to this engine's agent role."""
        return [n for n in self._nodes.values() if self._is_visible(n)]

    # ------------------------------------------------------------------
    # M7: Pass-depth counters
    # ------------------------------------------------------------------

    def get_usage_counters(self) -> dict[str, int]:
        """Return M7 pass-depth counters accumulated since last reset."""
        return {
            "pass1_search": self._pass1_count,
            "pass2_peek": self._pass2_count,
            "pass3_resolve": self._pass3_count,
        }

    def reset_usage_counters(self) -> None:
        """Reset M7 pass-depth counters to zero (call before a benchmark run)."""
        self._pass1_count = 0
        self._pass2_count = 0
        self._pass3_count = 0

    def peek(self, names: list[str]) -> dict[str, Any]:
        """Pass 2: return the compressed view of one or more nodes.

        This is the cheap middle step of the 3-pass model. For each requested
        node it returns only the ``dense`` summary (the ~15-token compression),
        any ``warning`` (warnings always surface), the names of required
        dependencies, and a manifest of which heavy blocks exist and roughly how
        many tokens each would cost in a full load. It deliberately does NOT
        return ``full``/``steps``/``code`` bodies — the agent reads this to
        decide whether a Pass-3 ``load_skill`` is even necessary.

        Args:
            names: One or more node identifiers to peek at.

        Returns:
            A dict mapping each requested name to its compressed view, or to an
            ``{"error": ...}`` entry if the node is unknown.
        """
        self._pass2_count += 1
        result: dict[str, Any] = {}
        for name in names:
            qid = self._resolve_name(name)
            node = self._nodes.get(qid) if qid else None
            if not node or not self._is_visible(node):
                result[name] = {"error": f"Skill '{name}' not found."}
                continue

            available: dict[str, int] = {}
            if node.full:
                available["full"] = estimate_tokens(node.full)
            if node.steps:
                available["steps"] = estimate_tokens("\n".join(node.steps))
            if node.code_blocks:
                available["code"] = estimate_tokens("\n".join(node.code_blocks.values()))
            if node.table:
                available["table"] = estimate_tokens(node.table)
            if node.list_items:
                available["list"] = estimate_tokens("\n".join(node.list_items))
            if node.example:
                available["example"] = estimate_tokens(node.example)
            if node.assertions:
                available["assertions"] = estimate_tokens("\n".join(node.assertions))
            if node.note:
                available["note"] = estimate_tokens(node.note)
            if node.reference:
                available["reference"] = estimate_tokens(str(node.reference))

            result[name] = {
                "dense": node.dense or node.summary or "",
                "warning": node.warning,
                "requires": list(node.requires),
                "available_blocks": available,
                "traverse": node.traverse or {},
            }
        return result

    def resolve_node(self, name: str, blocks: list[str] | None = None) -> str:
        """Pass 3: render a single node's heavy content, optionally a subset.

        Renders only the requested ``blocks`` (or :data:`DEFAULT_LOAD_BLOCKS`
        when none are given). Passing ``["all"]`` expands to :data:`ALL_BLOCKS`.

        Unlike the previous implementation, this does NOT recursively expand the
        ``->[:requires]`` dependency tree. Dependencies are listed by name in a
        footer so the agent can choose to ``load_skill`` them only if needed —
        this is what makes loading selective instead of an all-or-nothing dump.

        Args:
            name: The node identifier.
            blocks: Optional list of block names to render (e.g. ``["steps"]``),
                or ``["all"]`` for everything. Defaults to the execution set.

        Returns:
            A formatted string containing only the requested content.
        """
        self._pass3_count += 1
        qid = self._resolve_name(name)
        node = self._nodes.get(qid) if qid else None
        if not node or not self._is_visible(node):
            return f"Error: Skill '{name}' not found in the loaded skills."

        selected = list(blocks) if blocks else list(DEFAULT_LOAD_BLOCKS)
        if "all" in selected:
            selected = list(ALL_BLOCKS)
        want = set(selected)

        sections = [f"=== SKILL: {node.name} (role: {node.role}) ==="]

        if "warning" in want and node.warning:
            sections.append(f"\n⚠️ WARNING: {node.warning}")
        if "dense" in want and node.dense:
            sections.append(f"\n--- Summary (dense) ---\n{node.dense}")
        if "summary" in want and node.summary:
            sections.append(f"\n--- Summary ---\n{node.summary}")
        if "full" in want and node.full:
            sections.append(f"\n--- Full Details ---\n{node.full}")
        if "steps" in want and node.steps:
            sections.append("\n--- Steps ---")
            for i, step in enumerate(node.steps, 1):
                sections.append(f"  {i}. {step}")
        if "code" in want:
            for lang, code in node.code_blocks.items():
                sections.append(f"\n--- Code [{lang}] ---\n{code}")
        if "table" in want and node.table:
            sections.append(f"\n--- Data ---\n{node.table}")
        if "list" in want and node.list_items:
            sections.append("\n--- Items ---")
            for item in node.list_items:
                sections.append(f"  {item}")
        if "example" in want and node.example:
            sections.append(f"\n--- Example ---\n{node.example}")
        if "note" in want and node.note:
            sections.append(f"\n--- Note ---\n{node.note}")
        if "reference" in want and node.reference:
            ref_parts = [f"{k}: {v}" for k, v in node.reference.items()]
            sections.append("\n--- Reference ---\n" + "\n".join(ref_parts))
        if "assertions" in want and node.assertions:
            sections.append("\n--- MANDATORY ASSERTIONS (run these before proceeding) ---")
            for assertion in node.assertions:
                sections.append(f"  - {assertion}")
            sections.append(
                f'  Call check_skill_assertions(name="{node.name}", params=...) with your '
                "intended parameter values before executing this skill's steps."
            )
        if "edges" in want and node.edges:
            sections.append("\n--- Relationships ---")
            for edge in node.edges:
                sections.append(f"  {edge}")

        # Dependency footer — names only. The agent expands these on demand
        # rather than the engine pulling the whole tree at full content.
        deps = list(node.requires)
        for edge_line in node.edges:
            if "[:requires]" in edge_line:
                dep_id = edge_line.split("]")[-1].strip()
                if dep_id and dep_id not in deps:
                    deps.append(dep_id)
        if deps:
            sections.append(
                "\n--- Dependencies (call load_skill on these only if needed) ---\n"
                f"  {', '.join(deps)}"
            )

        return "\n".join(sections)

    def resolve_context(self, name: str) -> str:
        """Pass 3 with default blocks — the behavioral context for a skill node.

        Thin wrapper over :meth:`resolve_node` that renders the execution-default
        block set. Kept for backward compatibility with existing callers.

        Args:
            name: The node identifier.

        Returns:
            A formatted string containing the node's execution-critical content.
        """
        return self.resolve_node(name)

    # ==========================================
    # Skill Authoring (agent-written .og skills)
    # ==========================================

    @staticmethod
    def _slugify(name: str) -> str:
        """Turn an arbitrary skill name into a safe snake_case identifier.

        Also doubles as path-traversal defence: every non-alphanumeric character
        (including ``/``, ``\\`` and ``.``) is collapsed to ``_``, so the result
        can never escape the target directory when used as a filename.
        """
        slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
        return slug or "skill"

    @staticmethod
    def validate_dense(dense: str) -> tuple[bool, int]:
        """Check a dense block against the token budget.

        Returns ``(ok, token_count)``. A dense block is the compressed Pass-2
        summary; oversized ones are rejected so authored skills stay efficient.
        """
        count = estimate_tokens(dense)
        return count <= DENSE_TOKEN_BUDGET, count

    def upsert_skill(
        self,
        *,
        name: str,
        keywords: list[str],
        dense: str,
        full: str = "",
        steps: list[str] | None = None,
        code: str = "",
        code_language: str = "text",
        warning: str = "",
        assertions: list[str] | None = None,
        requires: list[str] | None = None,
        role: str = "skill",
        scope: str = "all",
        domain: str = "",
        reason: str = "",
        skills_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Create or refine an .og skill and hot-load it into the live index.

        Writes a single-node ObjectGraph file to ``<skills_dir>/learned/<slug>.og``,
        then immediately parses and indexes it so the skill is usable in the same
        session. If the file already exists, this is treated as a refinement: the
        changelog gains an ``updated`` entry and the version's patch number is
        bumped. The ``dense`` block is validated against the token budget first —
        an oversized block is rejected without writing anything.

        Args:
            name: Human/skill name; slugified into the node id and filename.
            keywords: Routing keywords for Pass-1 search.
            dense: Compressed Pass-2 summary (must fit the token budget).
            full: Full Pass-3 prose.
            steps: Ordered execution steps.
            code: A single code block body (optional).
            code_language: Language tag for the code block.
            warning: Critical callout.
            assertions: Validation conditions to run before proceeding.
            requires: Names of skills this one depends on.
            role: Node role (default "skill").
            scope: Access scope (default "all").
            domain: Pipe-separated domain tags for the file meta.
            reason: Short description recorded in the changelog.
            skills_dir: Override the target dir (defaults to the loaded skills dir).

        Returns:
            A status dict: ``status`` is ``created``/``updated``/``rejected``/``error``.
        """
        ok, dense_tokens = self.validate_dense(dense)
        if not ok:
            return {
                "status": "rejected",
                "reason": (
                    f"dense block is ~{dense_tokens} tokens; budget is {DENSE_TOKEN_BUDGET}. "
                    "Compress it to a few pipe-separated keywords (no full sentences)."
                ),
                "dense_tokens": dense_tokens,
            }

        target_dir = skills_dir or self._skills_dir
        if target_dir is None:
            return {"status": "error", "reason": "no skills directory configured"}

        learned_dir = target_dir / "learned"
        learned_dir.mkdir(parents=True, exist_ok=True)
        slug = self._slugify(name)
        path = learned_dir / f"{slug}.og"
        is_update = path.exists()

        node = OGNode(
            name=slug,
            source_file=str(path),
            role=role,
            scope=scope,
            keywords=[kw.strip() for kw in keywords if kw.strip()],
            requires=[r.strip() for r in (requires or []) if r.strip()],
            dense=dense,
            full=full,
            steps=list(steps or []),
            code_blocks={code_language: code} if code else {},
            warning=warning,
            assertions=list(assertions or []),
        )

        today = datetime.now(UTC).date().isoformat()
        if is_update:
            existing = parse_og_file(str(path))
            changelog = list(existing.changelog)
            changelog.append(
                OGChangelogEntry(
                    date=today,
                    action="updated",
                    target=f"node[{slug}]",
                    description=reason or "refined by agent",
                )
            )
            version = self._bump_patch(existing.meta.version or "1.0.0")
            created = existing.meta.created or today
        else:
            changelog = [
                OGChangelogEntry(
                    date=today,
                    action="added",
                    target=f"node[{slug}]",
                    description=reason or "authored by agent",
                )
            ]
            version = "1.0.0"
            created = today

        meta = OGFileMeta(
            title=name,
            version=version,
            author="hachi-agent",
            created=created,
            updated=today,
            domain=domain,
            scope=scope,
        )
        og = OGFile(
            source_file=str(path),
            meta=meta,
            index=[index_entry_for_node(node)],
            changelog=changelog,
            nodes=[node],
        )

        serialized = serialize_og_file(og)

        # Atomic write: serialize to a sibling temp file then os.replace so a
        # crash mid-write cannot leave a truncated/corrupt .og file on disk.
        tmp_fd, tmp_path_str = tempfile.mkstemp(
            prefix=f"_{slug}_", suffix=".og.tmp", dir=path.parent
        )
        _tmp_fd_closed = False
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                fh.write(serialized)
                _tmp_fd_closed = True  # os.fdopen context manager closed the fd

            # M2: lint the tmp file BEFORE promoting it. Governance claims
            # ("lint bounds what the agent may write") were previously honor-system
            # for save_skill — lint only ran *after* the write and only surfaced
            # warnings/info, so a lint-invalid skill (e.g. no ::dense block) would
            # still land on disk and get hot-loaded. Reject on any lint error instead.
            pre_report = lint_og_file(tmp_path_str)
            pre_errors = [i for i in pre_report["issues"] if i["level"] == "error"]
            if pre_errors:
                Path(tmp_path_str).unlink(missing_ok=True)
                return {
                    "status": "rejected",
                    "reason": "skill failed lint validation",
                    "lint_errors": [f"{i['code']}: {i['message']}" for i in pre_errors],
                }

            os.replace(tmp_path_str, path)
        except Exception:
            # Ensure the raw fd is closed before we try to unlink on Windows.
            if not _tmp_fd_closed:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            # Best-effort cleanup: remove the temp file if replace failed.
            try:
                Path(tmp_path_str).unlink(missing_ok=True)
            except OSError:
                pass
            raise

        self.load_file(path)  # hot-load so the skill is usable immediately

        # Record this revision in the append-only version history sidecar.
        # history_dir sits at <skills_dir>/.og-history/ — outside agent-writable paths.
        try:
            og_history.record_version(
                slug,
                serialized,
                author="agent",
                summary=reason or ("updated" if is_update else "created"),
                skills_dir=target_dir,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("og_history: failed to record version for %r: %s", slug, exc)

        # Lint the just-written skill and surface advisory feedback so the agent
        # can self-correct on its next refinement (the quality side of the
        # self-improvement loop). Dense budget + index are already guaranteed
        # above, so what remains is searchability/content/dependency hygiene.
        report = lint_og_file(path)
        advisories = [
            f"{issue['code']}: {issue['message']}"
            for issue in report["issues"]
            if issue["level"] in ("warning", "info")
        ]

        result: dict[str, Any] = {
            "status": "updated" if is_update else "created",
            "name": slug,
            "path": str(path),
            "version": version,
            "dense_tokens": dense_tokens,
        }
        if advisories:
            result["lint_advisories"] = advisories
        return result

    @staticmethod
    def _bump_patch(version: str) -> str:
        """Increment the patch component of a semver string (best-effort)."""
        parts = version.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except (ValueError, IndexError):
            return version

    def import_skill_md(self, path: Path, skills_dir: Path | None = None) -> dict[str, Any]:
        """Import a SKILL.md (Agent Skills) file as an .og skill and hot-load it.

        Bridges the community SKILL.md ecosystem into Hachi's token-efficient
        format: the frontmatter + markdown body are converted to an ObjectGraph
        node, written to ``<skills_dir>/imported/<slug>.og``, and indexed so the
        skill is immediately usable via search/peek/load.

        Args:
            path: Path to the SKILL.md (or any .md skill) file.
            skills_dir: Override the target dir (defaults to the loaded skills dir).

        Returns:
            A status dict: ``status`` is ``imported`` or ``error``.
        """
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            return {"status": "error", "reason": str(e)}

        target_dir = skills_dir or self._skills_dir
        if target_dir is None:
            return {"status": "error", "reason": "no skills directory configured"}

        og = skill_md_to_og(text, fallback_name=path.stem)
        node = og.nodes[0]
        imported_dir = Path(target_dir) / "imported"
        imported_dir.mkdir(parents=True, exist_ok=True)
        out_path = imported_dir / f"{node.name}.og"
        out_path.write_text(serialize_og_file(og), encoding="utf-8")
        self.load_file(out_path)  # hot-load so the skill is usable immediately

        return {
            "status": "imported",
            "name": node.name,
            "path": str(out_path),
            "keywords": node.keywords,
        }

    def export_skill(self, name: str) -> str | None:
        """Serialize a single loaded skill node back to ``.og`` text (or None)."""
        qid = self._resolve_name(name)
        node = self._nodes.get(qid) if qid else None
        if not node:
            return None
        og = OGFile(
            meta=OGFileMeta(title=name, version="1.0.0", author="hachi-export"),
            index=[index_entry_for_node(node)],
            nodes=[node],
        )
        return serialize_og_file(og)

    def get_file_index(self, filepath: str) -> str:
        """Return the formatted ::index routing table for a specific .og file.

        This is designed for injection into a sub-agent's system prompt so it
        has a complete, token-efficient map of the file's contents (~30 tokens)
        before reading any node bodies.

        Args:
            filepath: The absolute path to the .og file.

        Returns:
            A formatted index string, or empty string if no index exists.
        """
        og_file = self._files.get(filepath)
        if og_file:
            return og_file.get_index_prompt()
        return ""

    def get_file_meta(self, filepath: str) -> dict[str, str] | None:
        """Return the ::meta block for a specific .og file.

        Args:
            filepath: The absolute path to the .og file.

        Returns:
            A dict of metadata fields, or None if the file is not loaded.
        """
        og_file = self._files.get(filepath)
        if og_file and og_file.meta:
            return og_file.meta.model_dump()
        return None

    def get_file_changelog(self, filepath: str) -> list[dict[str, str]]:
        """Return the ::changelog entries for a specific .og file.

        Enables delta loading: agents check only the changelog to discover
        what changed since their last read.

        Args:
            filepath: The absolute path to the .og file.

        Returns:
            A list of changelog entry dicts.
        """
        og_file = self._files.get(filepath)
        if og_file and og_file.changelog:
            return [e.model_dump() for e in og_file.changelog]
        return []

    def get_node_changelog(self, name: str) -> dict[str, Any] | None:
        """Return a skill node's version + changelog for delta-loading.

        This realizes the ObjectGraph "delta load" idea: instead of re-reading a
        skill's heavy content to find out whether it changed, an agent that loaded
        the skill earlier can check just its current version and changelog entries
        (a few tokens) and decide whether a fresh ``load_skill`` is even warranted.

        Args:
            name: The exact skill node id.

        Returns:
            A dict with ``name``, ``version``, ``updated``, and ``changelog``
            (list of entry dicts), or ``None`` if the node is unknown.
        """
        qid = self._resolve_name(name)
        node = self._nodes.get(qid) if qid else None
        if not node:
            return None
        filepath = node.source_file
        meta = self.get_file_meta(filepath) or {}
        return {
            "name": name,
            "version": meta.get("version", ""),
            "updated": meta.get("updated", ""),
            "changelog": self.get_file_changelog(filepath),
        }

    def get_traverse_hints(self, name: str) -> dict[str, Any] | None:
        """Return the ``::traverse`` hints for a skill node.

        Traverse hints guide how the agent (or the engine) should navigate the
        skill graph when loading this node:

        - ``priority`` — ``"high"`` / ``"normal"`` / ``"low"``; controls where
          this node appears in ``search()`` results.
        - ``entry`` — preferred starting node when this skill acts as a subgraph
          root (e.g. ``entry: auth`` tells the agent to load ``auth`` first).
        - ``depth`` — maximum edge-follow depth (e.g. ``depth: 2``).

        Args:
            name: The exact skill node id.

        Returns:
            A dict with ``name`` + all traverse key/value pairs, or ``None``
            if the node is unknown.  Returns an empty ``traverse`` dict if the
            node exists but has no ``::traverse`` block.
        """
        qid = self._resolve_name(name)
        node = self._nodes.get(qid) if qid else None
        if not node:
            return None
        return {
            "name": name,
            "traverse": dict(node.traverse or {}),
        }

    @staticmethod
    def _direct_deps(node: OGNode) -> list[str]:
        """Combine a node's ``requires`` field with any ``->[:requires] <id>`` edges.

        Mirrors the dependency extraction in :meth:`resolve_node`'s footer so both
        agree on what a skill directly depends on.
        """
        deps = list(node.requires)
        for edge_line in node.edges:
            if "[:requires]" in edge_line:
                dep_id = edge_line.split("]")[-1].strip()
                if dep_id and dep_id not in deps:
                    deps.append(dep_id)
        return deps

    def get_dependency_chain(self, name: str, max_depth: int = 10) -> dict[str, Any] | None:
        """Resolve a skill's transitive ``requires`` dependency chain.

        Realizes ObjectGraph's typed dependency-aware traversal: from a skill node,
        walk its ``requires`` / ``->[:requires]`` edges to discover every prerequisite
        skill the agent should ``load_skill`` before executing — without loading any
        heavy content. Shared dependencies are visited once; back-edges are reported as
        a cycle rather than looping forever.

        Args:
            name: The exact skill node id.
            max_depth: Safety bound on traversal depth.

        Returns:
            ``{name, direct, chain, missing, has_cycle}`` where ``direct`` is the
            immediate dependencies, ``chain`` is the ordered transitive closure
            (excluding the root), ``missing`` are referenced deps not currently
            loaded, and ``has_cycle`` flags a dependency loop. ``None`` if unknown.
        """
        root_qid = self._resolve_name(name)
        if root_qid is None or root_qid not in self._nodes:
            return None

        direct = self._direct_deps(self._nodes[root_qid])
        chain: list[str] = []
        missing: list[str] = []
        visited: set[str] = set()
        has_cycle = False

        def walk(current: str, depth: int, path: frozenset[str]) -> None:
            nonlocal has_cycle
            cur_qid = self._resolve_name(current)
            node = self._nodes.get(cur_qid) if cur_qid else None
            if node is None or depth > max_depth:
                return
            for dep in self._direct_deps(node):
                if dep in path:  # back-edge into the current path → cycle
                    has_cycle = True
                    continue
                if dep in visited:  # already resolved on another branch (diamond)
                    continue
                visited.add(dep)
                dep_qid = self._resolve_name(dep)
                if dep_qid and dep_qid in self._nodes:
                    chain.append(dep)
                    walk(dep, depth + 1, path | {dep})
                elif dep not in missing:
                    missing.append(dep)

        walk(name, 0, frozenset({name}))
        return {
            "name": name,
            "direct": direct,
            "chain": chain,
            "missing": missing,
            "has_cycle": has_cycle,
        }

    def get_skill_graph(self) -> dict[str, Any]:
        """Build the whole-library dependency graph from typed ``requires`` edges.

        Aggregates every loaded node into an adjacency structure with entry-point
        roots (nothing requires them), missing dependencies (referenced but not
        loaded), and any dependency cycles — the data behind ``skill graph`` and
        the Mermaid/DOT visualizations.

        Returns:
            ``{skill_count, edge_count, edges, roots, missing, cyclic, nodes}``
            where ``nodes`` is ``[{name, role, direct, missing, has_cycle}]`` and
            ``edges`` is ``[[from, to], ...]``.
        """
        names = sorted(node.name for node in self.get_all_nodes())
        roles = {node.name: node.role for node in self.get_all_nodes()}
        nodes: list[dict[str, Any]] = []
        edges: list[list[str]] = []
        depended_on: set[str] = set()
        missing: set[str] = set()
        cyclic: list[str] = []

        for name in names:
            chain = self.get_dependency_chain(name) or {}
            direct = list(chain.get("direct", []))
            nodes.append(
                {
                    "name": name,
                    "role": roles.get(name, ""),
                    "direct": direct,
                    "missing": list(chain.get("missing", [])),
                    "has_cycle": bool(chain.get("has_cycle", False)),
                }
            )
            for dep in direct:
                edges.append([name, dep])
                if dep in roles:
                    depended_on.add(dep)
                else:
                    missing.add(dep)
            if chain.get("has_cycle"):
                cyclic.append(name)

        roots = [name for name in names if name not in depended_on]
        return {
            "skill_count": len(names),
            "edge_count": len(edges),
            "edges": edges,
            "roots": roots,
            "missing": sorted(missing),
            "cyclic": cyclic,
            "nodes": nodes,
        }

    def get_nodes_by_role(self, role: str) -> list[OGNode]:
        """
        Retrieve all nodes matching a specific role that are visible to the engine's
        agent role.  Used by the IntegrationRuntime to find 'env' and 'integration'
        nodes; also used by the doctor command to count MCP server declarations.

        Args:
            role: The role to filter by (e.g., 'env', 'integration', 'skill').

        Returns:
            A list of OGNode objects matching the given role.
        """
        return [n for n in self._nodes.values() if n.role == role and self._is_visible(n)]

    @property
    def node_count(self) -> int:
        """Return the number of indexed skill nodes visible to this engine's role."""
        if self._agent_role == "*":
            return len(self._nodes)
        return sum(1 for n in self._nodes.values() if self._is_visible(n))

    # ==========================================
    # Skill Lifecycle & Usage Tracking
    # ==========================================

    def _load_usage(self) -> dict[str, dict[str, Any]]:
        """Load the usage database from disk. Returns empty dict on error."""
        try:
            if self._usage_path.exists():
                return json.loads(self._usage_path.read_text(encoding="utf-8"))
        except Exception:
            # BB-51: quarantine the unparseable file BEFORE returning the empty
            # default, so the next _save_usage() can't silently clobber it.
            logger.warning("Failed to load skill usage DB, starting fresh")
            quarantine_corrupt_file(self._usage_path)
        return {}

    def _save_usage(self) -> None:
        """Persist the usage database to disk and reset the debounce timer."""
        with self._usage_lock:
            snapshot = dict(self._usage)
            self._usage_last_flush = time.monotonic()
        try:
            atomic_write_json(self._usage_path, snapshot)
        except Exception:
            logger.warning("Failed to persist skill usage DB")

    def record_use(self, name: str) -> None:
        """Record a skill load event. Called by the execution loop on load_skill.

        Updates use_count, last_used, and first_used timestamps.  Writes are
        debounced: the JSON file is flushed at most once per
        ``_usage_flush_interval`` seconds.  The first call after boot (or after
        the interval expires) always writes immediately so one-shot invocations
        and tests observe the file on disk.  Call ``flush_usage()`` to force an
        immediate sync regardless of the timer (e.g. at process shutdown).

        Args:
            name: The exact skill node name that was loaded.
        """
        now = datetime.now(UTC).isoformat()
        with self._usage_lock:
            entry = self._usage.setdefault(
                name,
                {
                    "use_count": 0,
                    "first_used": now,
                    "last_used": now,
                },
            )
            entry["use_count"] += 1
            entry["last_used"] = now
            elapsed = time.monotonic() - self._usage_last_flush
            should_flush = elapsed >= self._usage_flush_interval
        if should_flush:
            self._save_usage()

    def flush_usage(self) -> None:
        """Force an immediate flush of pending usage writes to disk.

        Call at process shutdown (or in tests) to ensure no writes are lost.
        """
        self._save_usage()

    def get_stale_skills(self, stale_days: int = 30) -> list[dict[str, Any]]:
        """Return skills that haven't been used within the given threshold.

        A skill is "stale" if it has usage records but last_used is older
        than stale_days ago. Skills with no usage records are considered
        "never used" and returned separately.

        Args:
            stale_days: Number of days of inactivity before a skill is stale.

        Returns:
            List of dicts with name, last_used, use_count, and days_inactive.
        """
        cutoff = datetime.now(UTC) - timedelta(days=stale_days)
        stale = []

        for qid, node in self._nodes.items():
            if not self._is_visible(node):
                continue
            # Usage tracking keyed by bare name for backward compat with persisted JSON
            entry = self._usage.get(node.name) or self._usage.get(qid)
            if not entry:
                stale.append(
                    {
                        "name": node.name,
                        "last_used": None,
                        "use_count": 0,
                        "days_inactive": None,
                        "status": "never_used",
                    }
                )
                continue

            try:
                last = datetime.fromisoformat(entry["last_used"])
                if last < cutoff:
                    days = (datetime.now(UTC) - last).days
                    stale.append(
                        {
                            "name": node.name,
                            "last_used": entry["last_used"],
                            "use_count": entry["use_count"],
                            "days_inactive": days,
                            "status": "stale",
                        }
                    )
            except (ValueError, KeyError):
                continue

        return stale

    def get_usage_report(self) -> dict[str, Any]:
        """Generate a full usage analytics report for all loaded skills.

        Returns:
            A dict with total_skills, tracked_skills, top_skills (sorted by use_count),
            stale_skills, and never_used counts.
        """
        tracked = []
        for name, entry in self._usage.items():
            qid = self._resolve_name(name)
            node = self._nodes.get(qid) if qid else None
            if node is not None and self._is_visible(node):
                tracked.append(
                    {
                        "name": node.name,  # always bare name for display
                        "use_count": entry.get("use_count", 0),
                        "first_used": entry.get("first_used"),
                        "last_used": entry.get("last_used"),
                    }
                )

        tracked.sort(key=lambda x: x["use_count"], reverse=True)

        stale = self.get_stale_skills()
        never_used = [s for s in stale if s["status"] == "never_used"]

        return {
            "total_skills": self.node_count,
            "tracked_skills": len(tracked),
            "never_used_count": len(never_used),
            "stale_count": len([s for s in stale if s["status"] == "stale"]),
            "top_skills": tracked[:10],
        }

    def get_skill_inventory(self) -> list[dict[str, Any]]:
        """Return a per-node inventory of every loaded skill with usage stats.

        Unlike ``get_usage_report`` (which only surfaces the top-10 tracked
        skills), this lists ALL nodes — joining each node's metadata with its
        usage record — so a UI can show the full loaded-skills picture. Sorted
        by use_count desc, then name. ``last_used`` is ``None`` for never-used
        skills.
        """
        inventory: list[dict[str, Any]] = []
        for qid, node in self._nodes.items():
            if not self._is_visible(node):
                continue
            entry = (self._usage.get(node.name) or self._usage.get(qid)) or {}
            inventory.append(
                {
                    "name": node.name,
                    "role": node.role,
                    "keyword_count": len(node.keywords),
                    "use_count": int(entry.get("use_count", 0) or 0),
                    "last_used": entry.get("last_used"),
                }
            )
        inventory.sort(key=lambda item: (-item["use_count"], item["name"]))
        # BB-34: deduplicate by name — keep the first (highest use_count) entry.
        # Two .og files can define nodes with the same name but different qids;
        # the UI uses name as the React key so duplicates cause key collisions.
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in inventory:
            if item["name"] not in seen:
                seen.add(item["name"])
                deduped.append(item)
        return deduped
