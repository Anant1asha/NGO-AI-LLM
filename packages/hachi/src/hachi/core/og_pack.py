"""OgPack (.ogpack) format: installer, consent sheets, and scope enforcement.

An .ogpack is a tar archive containing:
  - ``pack.toml``  — manifest (id, semver, scopes, sha256s, etc.)
  - ``*.og``       — skill files

Pack manifest scopes declare what tools, filesystem paths, and schedule budget
the pack requires.  Install renders a consent sheet; updates that widen scopes
re-prompt with a diff.  Skills are data — no install-time code execution path.
"""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hachi.core.archive_safety import safe_extract

# ---------------------------------------------------------------------------
# Scope vocabulary
# ---------------------------------------------------------------------------

#: Human-readable descriptions for known scope identifiers.
SCOPE_DESCRIPTIONS: dict[str, str] = {
    "gmail.read": "Read Gmail messages and labels",
    "gmail.send": "Send email on your behalf",
    "gmail.write": "Modify Gmail messages (labels, archive, delete)",
    "calendar.read": "Read Google Calendar events",
    "calendar.write": "Create and modify calendar events",
    "drive.read": "Read Google Drive files",
    "drive.write": "Create and modify Drive files",
    "notion.read": "Read Notion pages and databases",
    "notion.write": "Create and modify Notion pages",
    "slack.read": "Read Slack messages",
    "slack.send": "Post messages to Slack",
    "telegram.send": "Send Telegram messages",
    "shell.read": "Run read-only shell commands",
    "shell.write": "Run shell commands that modify the system",
    "fs.read": "Read local files",
    "fs.write": "Write local files",
    "web.browse": "Fetch web pages",
    "schedule.add": "Create scheduled tasks",
}


def describe_scope(scope: str) -> str:
    """Return a human-readable description for a scope token."""
    return SCOPE_DESCRIPTIONS.get(scope, scope)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackScope:
    """A declared scope with its human-readable label."""

    id: str
    description: str


@dataclass(frozen=True, slots=True)
class ScheduleBudget:
    """Schedule budget declared in the pack manifest."""

    max_runs_per_day: int = 0
    max_cost_per_run: float = 0.0


@dataclass(frozen=True, slots=True)
class OgPackManifest:
    """Parsed ``pack.toml`` manifest.

    Attributes:
        id:                   Unique pack identifier (e.g. ``google-workspace``).
        semver:               Pack version string.
        min_agent_version:    Minimum Hachi version required.
        scopes:               Declared tool/integration scopes.
        fs_paths:             Filesystem paths the pack may access.
        schedule_budget:      Max scheduling budget.
        sha256s:              Per-file content hashes for integrity checks.
        signature:            Optional signing artifact (sigstore/minisign).
        description:          Human-readable description.
        author:               Author name or contact.
    """

    id: str
    semver: str = "0.0.0"
    min_agent_version: str = ""
    scopes: tuple[PackScope, ...] = ()
    fs_paths: tuple[str, ...] = ()
    schedule_budget: ScheduleBudget = field(default_factory=ScheduleBudget)
    sha256s: dict[str, str] = field(default_factory=dict)
    signature: str = ""
    description: str = ""
    author: str = ""

    def scope_ids(self) -> frozenset[str]:
        return frozenset(s.id for s in self.scopes)

    def widened_scopes(self, other: OgPackManifest) -> frozenset[str]:
        """Scopes in ``other`` that are not in ``self`` — i.e., new permissions."""
        return other.scope_ids() - self.scope_ids()

    def widened_fs_paths(self, other: OgPackManifest) -> frozenset[str]:
        """FS paths in ``other`` that are not in ``self``."""
        return frozenset(other.fs_paths) - frozenset(self.fs_paths)


@dataclass
class InstalledPackRecord:
    """Record persisted for each installed pack (stored as pack.toml in the pack dir)."""

    manifest: OgPackManifest
    source: str
    install_path: Path
    file_count: int = 0


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_pack_toml(data: bytes | str) -> OgPackManifest:
    """Parse ``pack.toml`` bytes or text into :class:`OgPackManifest`.

    Accepts the TOML grammar defined in the .ogpack spec.  Unknown keys are
    silently ignored so old clients can read newer manifests.
    """
    raw: dict[str, Any]
    if isinstance(data, str):
        raw = tomllib.loads(data)
    else:
        raw = tomllib.loads(data.decode("utf-8"))

    pack_id = str(raw.get("id", ""))
    if not pack_id:
        raise ValueError("pack.toml must have an 'id' field")

    scope_raw = raw.get("scopes", [])
    scopes = tuple(
        PackScope(id=str(s), description=describe_scope(str(s)))
        for s in scope_raw
        if isinstance(s, str)
    )

    sb_raw = raw.get("schedule_budget")
    budget_raw = sb_raw if isinstance(sb_raw, dict) else {}
    budget = ScheduleBudget(
        max_runs_per_day=int(budget_raw.get("max_runs_per_day", 0)),
        max_cost_per_run=float(budget_raw.get("max_cost_per_run", 0.0)),
    )

    sha256s_raw = raw.get("sha256s", {}) if isinstance(raw.get("sha256s"), dict) else {}
    sha256s = {str(k): str(v) for k, v in sha256s_raw.items()}

    fs_paths_raw = raw.get("fs_paths", [])
    fs_paths = tuple(str(p) for p in fs_paths_raw if isinstance(p, str))

    return OgPackManifest(
        id=pack_id,
        semver=str(raw.get("semver", "0.0.0")),
        min_agent_version=str(raw.get("min_agent_version", "")),
        scopes=scopes,
        fs_paths=fs_paths,
        schedule_budget=budget,
        sha256s=sha256s,
        signature=str(raw.get("signature", "")),
        description=str(raw.get("description", "")),
        author=str(raw.get("author", "")),
    )


# ---------------------------------------------------------------------------
# Consent sheet
# ---------------------------------------------------------------------------


def render_consent_sheet(manifest: OgPackManifest, *, update: bool = False) -> str:
    """Return a human-readable consent sheet string for terminal display.

    Args:
        manifest: The pack manifest to render.
        update:   If True, label this as an update rather than a fresh install.
    """
    lines: list[str] = []
    action = "Update" if update else "Install"
    lines.append(f"\n{'─' * 60}")
    lines.append(f"  {action}: {manifest.id}  v{manifest.semver}")
    if manifest.description:
        lines.append(f"  {manifest.description}")
    if manifest.author:
        lines.append(f"  Author: {manifest.author}")
    lines.append(f"{'─' * 60}")

    if manifest.scopes:
        lines.append("\n  This pack will have access to:")
        for scope in manifest.scopes:
            lines.append(f"    ·  [{scope.id}]  {scope.description}")
    else:
        lines.append("\n  No integration scopes declared.")

    if manifest.fs_paths:
        lines.append("\n  Filesystem paths:")
        for path in manifest.fs_paths:
            lines.append(f"    ·  {path}")

    budget = manifest.schedule_budget
    if budget.max_runs_per_day or budget.max_cost_per_run:
        lines.append("\n  Schedule budget:")
        if budget.max_runs_per_day:
            lines.append(f"    ·  max {budget.max_runs_per_day} run(s) per day")
        if budget.max_cost_per_run:
            lines.append(f"    ·  max ${budget.max_cost_per_run:.4f} per run")

    lines.append("\n  Skills are data — no install-time code execution.")
    lines.append(f"{'─' * 60}\n")
    return "\n".join(lines)


def render_scope_diff(old: OgPackManifest, new: OgPackManifest) -> str:
    """Render the scope changes between two versions for update consent."""
    lines: list[str] = []
    widened_scopes = old.widened_scopes(new)
    widened_paths = old.widened_fs_paths(new)

    if not widened_scopes and not widened_paths:
        return ""

    lines.append(f"\n{'─' * 60}")
    lines.append(f"  Update widens permissions for {new.id}  v{old.semver} → v{new.semver}")
    lines.append(f"{'─' * 60}")
    if widened_scopes:
        lines.append("\n  New scopes being requested:")
        for scope_id in sorted(widened_scopes):
            lines.append(f"    +  [{scope_id}]  {describe_scope(scope_id)}")
    if widened_paths:
        lines.append("\n  New filesystem paths:")
        for path in sorted(widened_paths):
            lines.append(f"    +  {path}")
    lines.append(f"{'─' * 60}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pack directory management
# ---------------------------------------------------------------------------

_PACKS_SUBDIR = "packs"
_PACK_META_FILE = "pack.toml"
_INSTALLED_META_FILE = ".installed.toml"


def packs_dir(skills_dir: Path) -> Path:
    """Return (and create) the packs installation directory."""
    p = skills_dir / _PACKS_SUBDIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _pack_install_path(skills_dir: Path, pack_id: str) -> Path:
    return packs_dir(skills_dir) / pack_id


def _write_installed_meta(pack_dir: Path, manifest: OgPackManifest, source: str) -> None:
    """Persist install metadata alongside the pack's .og files."""
    lines = [
        f'id = "{manifest.id}"',
        f'semver = "{manifest.semver}"',
        f'source = "{source}"',
        f'description = "{manifest.description}"',
        f'author = "{manifest.author}"',
        f"scopes = [{', '.join(repr(s.id) for s in manifest.scopes)}]",
    ]
    (pack_dir / _INSTALLED_META_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_installed_meta(pack_dir: Path) -> dict[str, str]:
    """Read persisted install metadata; return {} if absent or unparseable."""
    meta_path = pack_dir / _INSTALLED_META_FILE
    if not meta_path.exists():
        toml_path = pack_dir / _PACK_META_FILE
        if toml_path.exists():
            try:
                m = parse_pack_toml(toml_path.read_bytes())
                return {"id": m.id, "semver": m.semver, "source": "", "description": m.description}
            except Exception:
                pass
        return {}
    try:
        return tomllib.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def verify_pack_checksums(pack_dir: Path, manifest: OgPackManifest) -> list[str]:
    """Return a list of integrity failures (empty = all good)."""
    failures: list[str] = []
    for filename, expected_hash in manifest.sha256s.items():
        target = pack_dir / filename
        if not target.exists():
            failures.append(f"missing: {filename}")
            continue
        actual = _file_sha256(target)
        if actual != expected_hash:
            failures.append(f"hash mismatch: {filename}")
    return failures


# ---------------------------------------------------------------------------
# Install / update
# ---------------------------------------------------------------------------


def install_ogpack_from_dir(
    source_dir: Path,
    skills_dir: Path,
    *,
    source: str = "",
    confirm: bool = True,
    old_manifest: OgPackManifest | None = None,
) -> tuple[OgPackManifest, list[str]]:
    """Install an unpacked .ogpack directory into ``skills_dir/packs/<id>/``.

    Args:
        source_dir:    Directory containing ``pack.toml`` + ``.og`` files.
        skills_dir:    The user's skills directory.
        source:        Original source URL or path (recorded in metadata).
        confirm:       If True and ``old_manifest`` provided with widened scopes,
                       print the diff (caller must handle user confirmation).
        old_manifest:  The currently-installed manifest (for update diff checks).

    Returns:
        Tuple of (manifest, list_of_installed_og_files).
    """
    toml_path = source_dir / _PACK_META_FILE
    if not toml_path.exists():
        raise FileNotFoundError(f"pack.toml not found in {source_dir}")

    manifest = parse_pack_toml(toml_path.read_bytes())

    if old_manifest is not None and confirm:
        diff = render_scope_diff(old_manifest, manifest)
        if diff:
            print(diff)

    pack_dir = _pack_install_path(skills_dir, manifest.id)
    pack_dir.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for og_file in source_dir.rglob("*.og"):
        rel = og_file.relative_to(source_dir)
        dst = pack_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(og_file, dst)
        installed.append(str(rel))

    toml_dst = pack_dir / _PACK_META_FILE
    shutil.copy2(toml_path, toml_dst)

    failures = verify_pack_checksums(pack_dir, manifest)
    if failures:
        raise ValueError(f"Pack integrity check failed: {failures}")

    _write_installed_meta(pack_dir, manifest, source)
    return manifest, installed


def install_ogpack_from_archive(
    archive_path: Path,
    skills_dir: Path,
    *,
    source: str = "",
    confirm: bool = True,
    old_manifest: OgPackManifest | None = None,
) -> tuple[OgPackManifest, list[str]]:
    """Install a .ogpack tar archive.

    Extracts to a temp dir, then delegates to :func:`install_ogpack_from_dir`.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive_path, "r:*") as tf:
            safe_extract(tf, tmp_path)
        # Look for pack.toml in the extracted tree
        pack_toml_candidates = list(tmp_path.rglob("pack.toml"))
        if not pack_toml_candidates:
            raise FileNotFoundError("No pack.toml found in .ogpack archive")
        pack_root = pack_toml_candidates[0].parent
        return install_ogpack_from_dir(
            pack_root,
            skills_dir,
            source=source,
            confirm=confirm,
            old_manifest=old_manifest,
        )


# ---------------------------------------------------------------------------
# List / remove
# ---------------------------------------------------------------------------


@dataclass
class OgPackInfo:
    """Summary of an installed pack, ready for display."""

    id: str
    semver: str
    source: str
    description: str
    og_file_count: int
    install_path: Path
    scope_ids: list[str]


def list_ogpacks(skills_dir: Path) -> list[OgPackInfo]:
    """Return a list of installed packs from ``<skills_dir>/packs/``."""
    result: list[OgPackInfo] = []
    packs_root = skills_dir / _PACKS_SUBDIR
    if not packs_root.exists():
        return result

    for pack_dir in sorted(packs_root.iterdir()):
        if not pack_dir.is_dir():
            continue
        meta = _read_installed_meta(pack_dir)
        if not meta.get("id"):
            continue
        og_count = len(list(pack_dir.rglob("*.og")))
        scope_raw = meta.get("scopes", "")
        scope_ids: list[str] = [str(s) for s in scope_raw] if isinstance(scope_raw, list) else []

        result.append(
            OgPackInfo(
                id=meta["id"],
                semver=str(meta.get("semver", "")),
                source=str(meta.get("source", "")),
                description=str(meta.get("description", "")),
                og_file_count=og_count,
                install_path=pack_dir,
                scope_ids=scope_ids,
            )
        )
    return result


def remove_ogpack(pack_id: str, skills_dir: Path) -> bool:
    """Remove an installed pack by id.

    Returns True if the pack was found and removed, False if not found.
    """
    pack_dir = _pack_install_path(skills_dir, pack_id)
    if not pack_dir.exists():
        return False
    shutil.rmtree(pack_dir)
    return True


def get_installed_manifest(pack_id: str, skills_dir: Path) -> OgPackManifest | None:
    """Return the installed manifest for a pack, or None if not installed."""
    pack_dir = _pack_install_path(skills_dir, pack_id)
    toml_path = pack_dir / _PACK_META_FILE
    if not toml_path.exists():
        return None
    try:
        return parse_pack_toml(toml_path.read_bytes())
    except Exception:
        return None
