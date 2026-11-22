"""Append-only `.og` version history sidecar.

Tier-1 append-only store — this file must live **outside** any path the agent can
reach through its normal tool registry.  The recommended location is
``<skills_dir>/.og-history/``, which is outside the ``learned/`` subtree that
``upsert_skill`` targets.

Storage format
--------------
One JSONL file per skill: ``<history_dir>/<name>.jsonl``.
Each line is a JSON object with these fields:

    {
        "version":   <int, 1-based monotonic>,
        "timestamp": "<UTC ISO-8601>",
        "author":    "human" | "agent",
        "summary":   "<short description of the change>",
        "sha256":    "<hex digest of content>",
        "content":   "<full .og file text>"
    }

Lines are only ever **appended** — existing lines are never rewritten or deleted.
This guarantees that even if the agent overwrites the live ``.og`` file it cannot
erase the history; the history file is opened only in ``"a"`` mode.

Wave-2 CLI (``hachi og rollback``) can record human-authored reverts via
``record_version(..., author="human")``.

Public API
----------
- :func:`record_version` — append a new version snapshot.
- :func:`list_versions`  — return version metadata (no content) in ascending order.
- :func:`get_version`    — retrieve the full content for a specific version number.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Sentinel used when history_dir is not supplied — callers must override this
# for the engine integration; it is only ``None`` in pure-unit-test scenarios.
_DEFAULT_HISTORY_SUBDIR = ".og-history"


def _resolve_history_dir(history_dir: Path | None, *, skills_dir: Path | None = None) -> Path:
    """Return the history directory, creating it if necessary.

    Args:
        history_dir: Explicit override (highest priority).
        skills_dir: Fallback — history will be placed at ``<skills_dir>/.og-history``.

    Returns:
        The resolved, existing :class:`pathlib.Path`.

    Raises:
        ValueError: If neither ``history_dir`` nor ``skills_dir`` is provided.
    """
    if history_dir is not None:
        resolved = history_dir
    elif skills_dir is not None:
        resolved = skills_dir / _DEFAULT_HISTORY_SUBDIR
    else:
        raise ValueError(
            "og_history: supply either history_dir or skills_dir to locate the history store."
        )
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _history_path(name: str, history_dir: Path) -> Path:
    """Return the JSONL path for *name* inside *history_dir*."""
    # Sanitise the name to be a valid filename component (same logic as engine slugify).
    import re

    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "skill"
    return history_dir / f"{slug}.jsonl"


def record_version(
    name: str,
    content: str,
    author: Literal["human", "agent"],
    summary: str,
    *,
    history_dir: Path | None = None,
    skills_dir: Path | None = None,
) -> int:
    """Append a new version snapshot to the history sidecar for *name*.

    The version number is monotonic and 1-based: it equals the count of lines
    already in the JSONL file plus one.  This function opens the file in append
    mode only — it never reads back or rewrites existing lines.

    Args:
        name: The skill name (will be slugified to form the JSONL filename).
        content: Full text content of the ``.og`` file at this revision.
        author: ``"human"`` for CLI/manual edits; ``"agent"`` for engine writes.
        summary: Short human-readable description recorded in the changelog entry.
        history_dir: Explicit path to the ``.og-history`` directory.  When
            ``None``, *skills_dir* must be provided.
        skills_dir: Parent of the default ``.og-history`` subdirectory.

    Returns:
        The new monotonic version number (``>= 1``).
    """
    hdir = _resolve_history_dir(history_dir, skills_dir=skills_dir)
    path = _history_path(name, hdir)

    # Count existing lines to derive the next version number.
    version = 1
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            version = sum(1 for ln in lines if ln.strip()) + 1
        except OSError as exc:
            logger.warning("og_history: could not count versions in %s: %s", path, exc)

    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    record = {
        "version": version,
        "timestamp": datetime.now(UTC).isoformat(),
        "author": author,
        "summary": summary,
        "sha256": sha256,
        "content": content,
    }

    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.error("og_history: failed to append version %d for %r: %s", version, name, exc)
        raise

    return version


def list_versions(
    name: str,
    *,
    history_dir: Path | None = None,
    skills_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return version metadata for *name* in ascending version order.

    Content is excluded from the returned dicts to keep memory usage bounded —
    use :func:`get_version` when you need the full snapshot.

    Args:
        name: The skill name to look up.
        history_dir: Explicit path to the ``.og-history`` directory.
        skills_dir: Fallback parent for the default ``.og-history`` subdirectory.

    Returns:
        A list of dicts, each with keys ``version``, ``timestamp``, ``author``,
        ``summary``, and ``sha256``.  Returns ``[]`` if no history exists.
    """
    try:
        hdir = _resolve_history_dir(history_dir, skills_dir=skills_dir)
    except ValueError:
        return []

    path = _history_path(name, hdir)
    if not path.exists():
        return []

    results: list[dict[str, Any]] = []
    try:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "og_history: skipping malformed line %d in %s: %s", lineno, path, exc
                )
                continue
            results.append(
                {
                    "version": record.get("version", lineno),
                    "timestamp": record.get("timestamp", ""),
                    "author": record.get("author", "unknown"),
                    "summary": record.get("summary", ""),
                    "sha256": record.get("sha256", ""),
                }
            )
    except OSError as exc:
        logger.warning("og_history: could not read %s: %s", path, exc)
        return []

    # Guarantee ascending order even if a writer appended out of order somehow.
    results.sort(key=lambda r: r["version"])
    return results


def get_version(
    name: str,
    version: int,
    *,
    history_dir: Path | None = None,
    skills_dir: Path | None = None,
) -> str | None:
    """Return the full content snapshot for *name* at *version*.

    Args:
        name: The skill name to look up.
        version: 1-based monotonic version number.
        history_dir: Explicit path to the ``.og-history`` directory.
        skills_dir: Fallback parent for the default ``.og-history`` subdirectory.

    Returns:
        The full ``.og`` text at that revision, or ``None`` if not found.
    """
    try:
        hdir = _resolve_history_dir(history_dir, skills_dir=skills_dir)
    except ValueError:
        return None

    path = _history_path(name, hdir)
    if not path.exists():
        return None

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("version") == version:
                content = record.get("content")
                return content if isinstance(content, str) else None
    except OSError as exc:
        logger.warning("og_history: could not read %s: %s", path, exc)

    return None
