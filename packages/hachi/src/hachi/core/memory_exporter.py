"""memory_exporter.py — P4-06 M4: Chroma → .og files migration.

Converts the five Chroma collections (core_memory, user_profile, agent_profile,
delegation_log, memory_quarantine) into .og files under a ``memory/`` directory
so the FTS5-only backend can take over as the canonical store.

Migration is **additive**: existing .og files are never overwritten; facts are
appended as new ``::node`` blocks if their SHA-256 ID is not already present.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Category → role mapping for the .og node schema
_CATEGORY_TO_ROLE = {
    "name": "preference",
    "role": "preference",
    "preference": "preference",
    "habit": "preference",
    "relationship": "preference",
    "timezone": "preference",
    "style": "preference",
    "identity": "preference",
    "directive": "preference",
    "workspace_state": "fact",
    "auto_synced": "fact",
    "auto_flushed_context": "fact",
    "architecture": "fact",
    "decision": "fact",
    "task": "task",
    "event": "event",
    "delegation": "fact",
    "quarantined": "fact",
}


@dataclass
class ExportResult:
    """Summary of a Chroma→files migration run."""

    run_ts: str = ""
    exported: int = 0
    skipped_existing: int = 0
    errors: int = 0
    output_files: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"ExportResult(exported={self.exported}, "
            f"skipped={self.skipped_existing}, errors={self.errors}, "
            f"files={len(self.output_files)})"
        )


def chroma_to_files(
    vault: Any,
    memory_dir: Path,
    *,
    dry_run: bool = False,
) -> ExportResult:
    """Export all Chroma collections to .og files in ``memory_dir``.

    Each Chroma collection maps to an output file:
    - ``core_memory``     → ``memory_dir/journal/chroma_export.og``
    - ``user_profile``    → ``memory_dir/profile.og``
    - ``agent_profile``   → ``memory_dir/agent.og``
    - ``delegation_log``  → ``memory_dir/journal/delegations.og``
    - ``memory_quarantine`` → ``memory_dir/journal/quarantine.og``

    Args:
        vault: A ``MemoryVault`` instance (Chroma must be running).
        memory_dir: Destination directory for .og files.
        dry_run: If True, log what would be written but don't touch disk.

    Returns:
        An ``ExportResult`` with counts and file paths.
    """
    result = ExportResult(run_ts=datetime.datetime.now(datetime.UTC).isoformat())
    memory_dir = Path(memory_dir)

    # Collection → output file mapping
    collection_map = [
        ("collection", memory_dir / "journal" / "chroma_export.og", "core_memory"),
        ("user_collection", memory_dir / "profile.og", "user_profile"),
        ("agent_profile", memory_dir / "agent.og", "agent_profile"),
        ("delegation_collection", memory_dir / "journal" / "delegations.og", "delegation_log"),
        ("quarantine_collection", memory_dir / "journal" / "quarantine.og", "quarantine"),
    ]

    for attr_name, out_path, title in collection_map:
        collection = getattr(vault, attr_name, None)
        if collection is None:
            continue
        try:
            rows = collection.get()
        except Exception as exc:
            logger.warning("chroma_to_files: could not read %s: %s", attr_name, exc)
            result.errors += 1
            continue

        ids = rows.get("ids") or []
        docs = rows.get("documents") or []
        metas = rows.get("metadatas") or []

        if not ids:
            continue

        # Load already-present node IDs from the destination file to skip dupes.
        existing_ids: set[str] = set()
        if out_path.exists():
            for line in out_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("::node["):
                    nid = line[7 : line.index("]")]
                    existing_ids.add(nid)

        new_blocks: list[str] = []
        for i, doc_id in enumerate(ids):
            if _safe_node_name(doc_id) in existing_ids:
                result.skipped_existing += 1
                continue
            doc = docs[i] if i < len(docs) else ""
            meta = metas[i] if i < len(metas) else {}
            category = meta.get("category", "workspace_state")
            ts = meta.get("timestamp", "")
            role = _CATEGORY_TO_ROLE.get(category, "fact")
            # Sanitize to a safe node name
            node_name = _safe_node_name(doc_id)
            block = _build_node_block(
                node_name=node_name,
                content=doc,
                role=role,
                category=category,
                ts=ts,
            )
            new_blocks.append(block)
            result.exported += 1

        if new_blocks and not dry_run:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            header_needed = not out_path.exists()
            with out_path.open("a", encoding="utf-8") as fh:
                if header_needed:
                    fh.write(_file_header(title))
                fh.write("\n".join(new_blocks) + "\n")
            if str(out_path) not in result.output_files:
                result.output_files.append(str(out_path))
        elif new_blocks and dry_run:
            logger.info(
                "DRY RUN: would write %d blocks to %s", len(new_blocks), out_path
            )

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _safe_node_name(raw: str) -> str:
    """Convert a Chroma SHA-256 ID to a short, safe node name."""
    return "chroma-" + raw[:12]


def _build_node_block(
    *,
    node_name: str,
    content: str,
    role: str,
    category: str,
    ts: str,
) -> str:
    """Render a single ``::node`` .og block from a Chroma fact."""
    updated = ts or datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Truncate dense to ~100 chars for compliance
    dense = content[:100].replace("\n", " ").strip()
    keywords = _extract_keywords(content)
    kw_str = ", ".join(keywords)
    return (
        f"\n::node[{node_name}]\n"
        f"->[:role={role}]\n"
        f"->[:category={category}]\n"
        f"->[:keywords={kw_str}]\n"
        f"->[:updated={updated}]\n"
        f"->[:evidence=chroma_export]\n"
        f"::dense\n"
        f"{dense}\n"
    )


def _file_header(title: str) -> str:
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    return f"::meta\n  title: {title} (exported {ts})\n  source: chroma_export\n\n"


def _extract_keywords(content: str, max_kw: int = 5) -> list[str]:
    """Extract top-N significant words from content as keywords."""
    _STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "is", "are", "was", "were", "be", "been", "by", "with", "from",
        "this", "that", "it", "i", "you", "we", "they", "my", "your", "our",
        "has", "have", "had", "not", "no", "can", "will", "do", "does",
    }
    words = [
        w.strip(".,;:!?\"'()[]{}").lower()
        for w in content.split()
        if len(w) > 3
    ]
    seen: list[str] = []
    for w in words:
        if w not in _STOPWORDS and w not in seen:
            seen.append(w)
        if len(seen) >= max_kw:
            break
    return seen
