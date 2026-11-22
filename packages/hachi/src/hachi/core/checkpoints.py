"""File checkpoints / rollback — an undo buffer for agent file mutations.

Before the agent overwrites (or creates) a file, the current state is snapshotted
here. ``rollback`` restores the most recent snapshot — letting a non-technical
user safely undo a mistaken edit. Snapshots are disk-backed so undo survives a
restart within the workspace.

Design: each ``snapshot`` records whether the target existed and (if so) a copy
of its bytes. ``rollback`` pops the latest matching record and restores it
(re-writing the old bytes, or deleting a file that didn't exist before).
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class CheckpointManager:
    """Disk-backed snapshot/restore buffer for file mutations."""

    def __init__(self, base_dir: Path):
        self._base = Path(base_dir)
        self._snaps_dir = self._base / "snapshots"
        self._index_path = self._base / "index.json"
        self._lock = threading.Lock()

    def _load_index(self) -> list[dict[str, Any]]:
        if not self._index_path.exists():
            return []
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_index(self, index: list[dict[str, Any]]) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        tmp = self._index_path.with_name(f"{self._index_path.name}.tmp")
        tmp.write_text(json.dumps(index, indent=2), encoding="utf-8")
        tmp.replace(self._index_path)

    def snapshot(self, path: str | Path, *, label: str = "") -> str | None:
        """Record the current state of ``path`` before it is mutated.

        Returns the checkpoint id, or ``None`` if the target is a directory (only
        files are snapshotted).
        """
        target = Path(path)
        if target.exists() and target.is_dir():
            return None

        with self._lock:
            self._snaps_dir.mkdir(parents=True, exist_ok=True)
            snap_id = uuid.uuid4().hex[:12]
            existed = target.exists() and target.is_file()
            content_ref: str | None = None
            if existed:
                snap_file = self._snaps_dir / f"{snap_id}.bin"
                snap_file.write_bytes(target.read_bytes())
                content_ref = snap_file.name

            index = self._load_index()
            index.append(
                {
                    "id": snap_id,
                    "path": str(target.resolve()),
                    "existed": existed,
                    "content_ref": content_ref,
                    "label": label,
                    "ts": datetime.now(UTC).isoformat(),
                }
            )
            self._save_index(index)
            return snap_id

    def rollback(self, path: str | Path | None = None) -> dict[str, Any]:
        """Restore (and consume) the most recent snapshot, optionally for one path."""
        with self._lock:
            index = self._load_index()
            target_resolved = str(Path(path).resolve()) if path is not None else None

            for i in range(len(index) - 1, -1, -1):
                record = index[i]
                if target_resolved is not None and record["path"] != target_resolved:
                    continue

                file_path = Path(record["path"])
                if record["existed"] and record["content_ref"]:
                    snap_file = self._snaps_dir / record["content_ref"]
                    if snap_file.exists():
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_bytes(snap_file.read_bytes())
                        snap_file.unlink(missing_ok=True)
                    outcome = "restored"
                else:
                    # File was created by the agent (didn't exist before) — undo = delete.
                    if file_path.exists():
                        file_path.unlink()
                    outcome = "removed"

                index.pop(i)
                self._save_index(index)
                return {"status": outcome, "path": str(file_path)}

        return {"status": "no_checkpoint", "path": str(path) if path else None}

    def count(self) -> int:
        with self._lock:
            return len(self._load_index())

    def prune_old_snapshots(self, older_than_days: int = 30) -> int:
        """Remove checkpoint entries (and their snapshot files) older than ``older_than_days``.

        Entries are matched by the ``ts`` ISO timestamp written at snapshot time.
        Fresh entries and entries with unparseable timestamps are preserved.
        Returns the number of entries removed.
        """
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        removed = 0
        with self._lock:
            index = self._load_index()
            surviving = []
            for entry in index:
                try:
                    ts = datetime.fromisoformat(entry["ts"])
                    if ts < cutoff:
                        # Delete the snapshot file if present.
                        ref = entry.get("content_ref")
                        if ref:
                            snap_file = self._snaps_dir / ref
                            snap_file.unlink(missing_ok=True)
                        removed += 1
                        continue
                except Exception:
                    pass
                surviving.append(entry)
            if removed:
                self._save_index(surviving)
        return removed
