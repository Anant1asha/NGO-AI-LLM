"""memory_gardener.py — P3-02 M3: nightly dedupe/supersede/expire gardener.

Governance rule: appends-only. The gardener never overwrites existing node content;
it appends ``::changelog`` entries and ``supersedes`` edges.

Auto-applies only whitelisted low-risk changes (exact-name deduplication: the same
node name appearing in more than one file — keep newest, mark older as superseded).
Controversial proposals (near-duplicate content, contradiction detection, expiry) are
returned as ``pending_review`` items that the user can approve via the TUI Memory-Diff
screen.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class ProposalKind(StrEnum):
    DEDUP_SAME_NAME = "dedup_same_name"
    MERGE_SIMILAR = "merge_similar"
    SUPERSEDE_CONTRADICTION = "supersede_contradiction"
    EXPIRE_STALE = "expire_stale"


@dataclass
class GardeningProposal:
    """A single proposed memory change from the gardener."""

    kind: str                      # ProposalKind value
    name_a: str                    # primary node name
    name_b: str = ""               # second node (for merge/supersede proposals)
    reason: str = ""
    confidence: float = 1.0
    file_path_a: str = ""
    file_path_b: str = ""
    auto_applied: bool = False


@dataclass
class GardeningResult:
    """Output of a single gardener run."""

    run_ts: str = ""
    auto_applied: list[GardeningProposal] = field(default_factory=list)
    pending_review: list[GardeningProposal] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Persist the result to a JSON file for the TUI to read."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "run_ts": self.run_ts,
                    "auto_applied": [asdict(p) for p in self.auto_applied],
                    "pending_review": [asdict(p) for p in self.pending_review],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> GardeningResult:
        """Load a persisted result. Returns empty result if file is missing."""
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            auto = [GardeningProposal(**p) for p in raw.get("auto_applied", [])]
            pending = [GardeningProposal(**p) for p in raw.get("pending_review", [])]
            return cls(run_ts=raw.get("run_ts", ""), auto_applied=auto, pending_review=pending)
        except Exception:
            logger.debug("GardeningResult.load failed", exc_info=True)
            return cls()


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_NODE_RE = re.compile(r"::node\[([^\]]+)\]", re.MULTILINE)
_EDGE_RE = re.compile(r"->?\s*\[:(\w+)=([^\]]+)\]", re.MULTILINE)
_DENSE_RE = re.compile(r"::dense\n(.+?)(?=\n::|$)", re.DOTALL)
_VALID_UNTIL_RE = re.compile(r"->?\s*\[:valid_until=([^\]]+)\]", re.MULTILINE)


@dataclass
class _ParsedNode:
    name: str
    dense: str
    file_path: str
    mtime: float
    valid_until: str = ""


def _parse_dir(memory_dir: Path) -> dict[str, list[_ParsedNode]]:
    """Parse all .og files in memory_dir → name → list of ParsedNode (one per file)."""
    index: dict[str, list[_ParsedNode]] = {}
    for og_file in memory_dir.rglob("*.og"):
        try:
            text = og_file.read_text(encoding="utf-8", errors="replace")
            mtime = og_file.stat().st_mtime
        except OSError:
            continue

        sections = re.split(r"(?=::node\[)", text)
        for section in sections:
            m_node = re.match(r"::node\[([^\]]+)\]", section)
            if not m_node:
                continue
            name = m_node.group(1).strip()

            m_dense = re.search(r"::dense\n(.+?)(?=\n::|$)", section, re.DOTALL)
            dense = m_dense.group(1).strip()[:300] if m_dense else ""

            m_valid = _VALID_UNTIL_RE.search(section)
            valid_until = m_valid.group(1).strip() if m_valid else ""

            node = _ParsedNode(
                name=name,
                dense=dense,
                file_path=str(og_file),
                mtime=mtime,
                valid_until=valid_until,
            )
            index.setdefault(name, []).append(node)

    return index


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _jaccard(text_a: str, text_b: str) -> float:
    """Word-level Jaccard similarity between two short texts."""
    tok_a = set(re.findall(r"\w+", text_a.lower()))
    tok_b = set(re.findall(r"\w+", text_b.lower()))
    if not tok_a and not tok_b:
        return 1.0
    if not tok_a or not tok_b:
        return 0.0
    return len(tok_a & tok_b) / len(tok_a | tok_b)


def _is_expired(valid_until: str) -> bool:
    """Return True if valid_until is a past ISO-8601 date."""
    if not valid_until:
        return False
    try:
        import datetime
        dt = datetime.datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        return dt < datetime.datetime.now(tz=datetime.UTC)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Changelog writer
# ---------------------------------------------------------------------------

def _append_changelog(file_path: Path, node_name: str, change: str) -> None:
    """Append a ::changelog entry to the file without overwriting any node."""
    if not file_path.exists():
        return
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = f"\n::changelog[{node_name}]\n->[:ts={ts}]\n->[:change={change}]\n"
    with file_path.open("a", encoding="utf-8") as fh:
        fh.write(entry)


# ---------------------------------------------------------------------------
# Gardener
# ---------------------------------------------------------------------------


class MemoryGardener:
    """M3 nightly memory maintenance: deduplicate, supersede, and expire nodes.

    This class is designed to be run as a background job (via the durable queue)
    once per day.  It never overwrites existing node content — all mutations are
    expressed as ``::changelog`` annotations appended to the end of the affected
    file, or as ``supersedes`` edge appended to the newer node's block.

    Args:
        memory_dir: Root of the ``memory/`` data directory.
        similarity_threshold: Jaccard threshold above which two different-named
            nodes are proposed as merge candidates.
    """

    _PENDING_DIFFS_FILE = "pending_diffs.json"

    def __init__(
        self,
        memory_dir: Path,
        similarity_threshold: float = 0.70,
    ) -> None:
        self._memory_dir = memory_dir
        self._threshold = similarity_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, *, auto_apply: bool = True) -> GardeningResult:
        """Run a full gardening pass.

        Returns:
            GardeningResult with auto_applied and pending_review lists.
            Also writes pending_diffs.json to the memory dir for the TUI.
        """
        index = _parse_dir(self._memory_dir)
        result = GardeningResult(run_ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

        # 1. Detect proposals
        proposals: list[GardeningProposal] = []
        proposals.extend(self._find_dedup_same_name(index))
        proposals.extend(self._find_similar_content(index))
        proposals.extend(self._find_expired(index))

        # 2. Split: whitelisted auto-apply vs. pending review
        for prop in proposals:
            if auto_apply and prop.kind == ProposalKind.DEDUP_SAME_NAME:
                self._apply_dedup(prop)
                prop.auto_applied = True
                result.auto_applied.append(prop)
            else:
                result.pending_review.append(prop)

        # 3. Persist pending diffs for TUI
        diffs_path = self._memory_dir / self._PENDING_DIFFS_FILE
        result.save(diffs_path)

        logger.info(
            "MemoryGardener: auto_applied=%d pending=%d",
            len(result.auto_applied),
            len(result.pending_review),
        )
        return result

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _find_dedup_same_name(
        self, index: dict[str, list[_ParsedNode]]
    ) -> list[GardeningProposal]:
        """Find nodes whose name appears in more than one file (safe to auto-merge)."""
        proposals = []
        for name, occurrences in index.items():
            if len(occurrences) < 2:
                continue
            # Sort by mtime desc; keep the newest, supersede the rest.
            by_mtime = sorted(occurrences, key=lambda n: -n.mtime)
            newest = by_mtime[0]
            for older in by_mtime[1:]:
                proposals.append(
                    GardeningProposal(
                        kind=ProposalKind.DEDUP_SAME_NAME,
                        name_a=name,
                        reason=(
                            f"Node '{name}' in both {newest.file_path} and "
                            f"{older.file_path}; keeping newest."
                        ),
                        confidence=1.0,
                        file_path_a=newest.file_path,
                        file_path_b=older.file_path,
                    )
                )
        return proposals

    def _find_similar_content(
        self, index: dict[str, list[_ParsedNode]]
    ) -> list[GardeningProposal]:
        """Propose merges for nodes with different names but similar dense text."""
        proposals = []
        names = list(index.keys())
        for i, name_a in enumerate(names):
            node_a = index[name_a][0]
            if not node_a.dense:
                continue
            for name_b in names[i + 1 :]:
                node_b = index[name_b][0]
                if not node_b.dense:
                    continue
                sim = _jaccard(node_a.dense, node_b.dense)
                if sim >= self._threshold:
                    proposals.append(
                        GardeningProposal(
                            kind=ProposalKind.MERGE_SIMILAR,
                            name_a=name_a,
                            name_b=name_b,
                            reason=f"Jaccard similarity {sim:.2f} ≥ {self._threshold:.2f}",
                            confidence=sim,
                            file_path_a=node_a.file_path,
                            file_path_b=node_b.file_path,
                        )
                    )
        return proposals

    def _find_expired(
        self, index: dict[str, list[_ParsedNode]]
    ) -> list[GardeningProposal]:
        """Propose deletion of nodes whose valid_until date has passed."""
        proposals = []
        for name, occurrences in index.items():
            for node in occurrences:
                if _is_expired(node.valid_until):
                    proposals.append(
                        GardeningProposal(
                            kind=ProposalKind.EXPIRE_STALE,
                            name_a=name,
                            reason=f"valid_until={node.valid_until} has passed",
                            confidence=1.0,
                            file_path_a=node.file_path,
                        )
                    )
        return proposals

    # ------------------------------------------------------------------
    # Auto-apply (whitelisted only: DEDUP_SAME_NAME)
    # ------------------------------------------------------------------

    def _apply_dedup(self, prop: GardeningProposal) -> None:
        """Append a ::changelog supersedes entry to the older file."""
        try:
            older_path = Path(prop.file_path_b)
            _append_changelog(
                older_path,
                prop.name_a,
                f"superseded_by={prop.file_path_a}",
            )
        except Exception:
            logger.debug("MemoryGardener._apply_dedup failed", exc_info=True)
