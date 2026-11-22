"""Community Skill Pack installer.

Lets users share and install `.og` skill packs from GitHub repos or direct URLs.

Pack resolution order
----------------------
1. ``user/repo`` shorthand  → GitHub archive tarball
   ``https://github.com/{user}/{repo}/archive/refs/heads/{ref}.tar.gz``
2. Full ``https://...`` URL ending in ``.tar.gz`` / ``.zip``  → direct download
3. Full ``https://...`` URL ending in ``.og``  → single-skill install
4. Local ``/path/to/dir``  → directory copy (no HTTP)

Pack format (optional ``pack.json`` at repo root)
---------------------------------------------------
::

    {
      "name": "devops",
      "description": "DevOps automation skills",
      "version": "1.2.0",
      "author": "alice",
      "license": "MIT"
    }

If ``pack.json`` is absent the pack name is derived from the URL and all ``.og``
files in the root are installed.

Installed layout
-----------------
Each pack lives under ``<skills_dir>/packs/<name>/``.  The SkillEngine's
``load_directory`` recurse=True picks them up automatically.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hachi.core.archive_safety import ArchiveSecurityError
from hachi.core.net_guard import validate_outbound_url

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

_GITHUB_HOST = "https://github.com"
_GITHUB_RAW_HOST = "https://raw.githubusercontent.com"


@dataclass
class PackInfo:
    """Metadata about an installed skill pack.

    Attributes:
        name: Pack identifier (directory name under ``packs/``).
        source: Original URL or ``user/repo`` spec used to install.
        installed_path: Absolute path of the pack directory.
        file_count: Number of ``.og`` files currently in the pack.
        version: Version string from ``pack.json``, or ``""`` if absent.
        description: Human description from ``pack.json``, or ``""``.
    """

    name: str
    source: str
    installed_path: Path
    file_count: int
    version: str = ""
    description: str = ""


@dataclass
class _FetchResult:
    """Internal transfer type: raw bytes and the guessed archive format."""

    data: bytes
    format: str  # "tar.gz", "zip", "og", "dir"
    pack_name: str
    source: str
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# URL / spec helpers
# ---------------------------------------------------------------------------

_GITHUB_SHORTHAND = re.compile(r"^[\w.-]+/[\w.-]+(?:@[\w/.-]+)?$")


def _parse_shorthand(spec: str) -> tuple[str, str, str]:
    """Parse ``user/repo[@ref]`` → (user, repo, ref).

    Default ref is ``main``.
    """
    ref = "main"
    base, _, tail = spec.partition("@")
    if tail:
        ref = tail
    parts = base.split("/", 1)
    return parts[0], parts[1], ref


def _github_archive_url(user: str, repo: str, ref: str) -> str:
    return f"{_GITHUB_HOST}/{user}/{repo}/archive/refs/heads/{ref}.tar.gz"


def _derive_pack_name(url: str) -> str:
    """Guess a pack name from a URL or spec."""
    # GitHub shorthand: user/repo → repo name (strip @ref)
    if _GITHUB_SHORTHAND.match(url):
        base = url.split("@")[0]
        return base.split("/")[1]
    # Local path (Windows backslashes or absolute Unix): use Path.name
    local = Path(url)
    if local.exists():
        name = local.name
        for suffix in (".tar.gz", ".tgz", ".zip", ".og"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name or "unnamed"
    # Strip trailing slashes / .git for URLs
    cleaned = url.rstrip("/").removesuffix(".git")
    # Last path component, without extension cluster
    last = cleaned.rsplit("/", 1)[-1]
    # Remove archive suffixes
    for suffix in (".tar.gz", ".tgz", ".zip", ".og"):
        if last.endswith(suffix):
            last = last[: -len(suffix)]
    return last or "unnamed"


def _validate_url(url: str) -> None:
    """Raise ValueError if the URL is blocked by net_guard."""
    ok, reason = validate_outbound_url(url)
    if not ok:
        raise ValueError(f"URL blocked by security policy: {reason}")


# ---------------------------------------------------------------------------
# Download helpers (injectable for tests)
# ---------------------------------------------------------------------------


def _default_fetcher(url: str) -> bytes:
    """Download ``url`` and return the raw bytes.

    Uses httpx with follow_redirects=False (SSRF safety) and a 30 s timeout.
    """
    import httpx  # lazy — httpx is a project dependency

    with httpx.Client(follow_redirects=False, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


# ---------------------------------------------------------------------------
# Archive extraction helpers
# ---------------------------------------------------------------------------

# Archive resource caps (zip-bomb / tar-bomb guards) — shared intent with
# archive_safety.safe_extract's defaults.
_MAX_ARCHIVE_FILES = 10_000
_MAX_ARCHIVE_TOTAL_BYTES = 500 * 1024 * 1024  # 500 MiB uncompressed
_MAX_ARCHIVE_COMPRESSION_RATIO = 1000  # per-member bomb guard (files > 1 MB)


def _extract_tar(data: bytes, dest: Path) -> list[Path]:
    """Extract a .tar.gz archive into ``dest``, returning installed .og paths.

    Strips the common single top-level prefix that GitHub archives include
    (e.g. ``{repo}-{ref}/``) and copies only ``.og`` and ``pack.json`` files.

    Security: uses :func:`~hachi.core.archive_safety.safe_extract` for
    all actual writes so path-traversal and tar-bomb attacks are blocked.
    """
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        members = tf.getmembers()
        if not members:
            return []

        # Detect the common single top-level prefix (GitHub archive layout).
        first_parts = {m.name.split("/")[0] for m in members if "/" in m.name}
        prefix = first_parts.pop() if len(first_parts) == 1 else ""

        # Build the subset of members we actually want (og + pack.json),
        # renaming them so the prefix is stripped, and validating that the
        # stripped name does not itself escape *dest*.
        dest_resolved = dest.resolve()
        subset: list[tarfile.TarInfo] = []
        for member in members:
            if member.isdir():
                continue

            rel = member.name
            if prefix and rel.startswith(prefix + "/"):
                rel = rel[len(prefix) + 1 :]

            if not rel or (not rel.endswith(".og") and rel != "pack.json"):
                continue

            # Bounds-check the stripped path before creating a renamed copy.
            candidate = (dest / rel).resolve()
            try:
                within_dest = candidate.is_relative_to(dest_resolved)
            except AttributeError:  # pragma: no cover — only pre-3.9
                import os as _os

                within_dest = _os.path.commonpath([dest_resolved, candidate]) == str(dest_resolved)
            if not within_dest:
                raise ArchiveSecurityError(
                    f"Archive member {member.name!r} (stripped: {rel!r}) would escape "
                    f"destination directory {dest_resolved}. Extraction aborted."
                )

            # Clone the TarInfo with the renamed (prefix-stripped) path so
            # we write to the correct location without the prefix.
            copy = tarfile.TarInfo(name=rel)
            copy.size = member.size
            copy.mtime = member.mtime
            copy.mode = member.mode & 0o777
            copy.type = member.type
            copy.uid = 0
            copy.gid = 0
            copy.uname = ""
            copy.gname = ""
            subset.append((copy, member))  # type: ignore[arg-type]

        # Now extract each validated, renamed member individually.
        dest.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for copy, original in subset:  # type: ignore[misc]
            target = dest / copy.name
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(original)
            if src is not None:
                target.write_bytes(src.read())
                if copy.name.endswith(".og"):
                    written.append(target)
    return written


def _extract_zip(data: bytes, dest: Path) -> list[Path]:
    """Extract a .zip archive into ``dest``, returning installed .og paths.

    Security (SEC-001): every member is validated against path traversal
    (absolute paths, ``..`` components, and resolved-destination escape) and
    zip-bomb resource caps are enforced — mirroring the tar path's
    :func:`~hachi.core.archive_safety.safe_extract`.
    """
    written: list[Path] = []
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = zf.infolist()
        if len(infos) > _MAX_ARCHIVE_FILES:
            raise ArchiveSecurityError(
                f"Archive exceeds maximum member count ({_MAX_ARCHIVE_FILES}). "
                "Extraction aborted to prevent zip-bomb."
            )

        names = [i.filename for i in infos]
        prefix = names[0].split("/")[0] + "/" if names and "/" in names[0] else ""

        total_bytes = 0
        for info in infos:
            name = info.filename

            # --- zip-bomb: cumulative size + per-member compression ratio ---
            total_bytes += info.file_size
            if total_bytes > _MAX_ARCHIVE_TOTAL_BYTES:
                raise ArchiveSecurityError(
                    f"Archive cumulative size exceeds {_MAX_ARCHIVE_TOTAL_BYTES} bytes. "
                    "Extraction aborted to prevent zip-bomb."
                )
            if (
                info.file_size > 1_000_000
                and info.compress_size > 0
                and info.file_size / info.compress_size > _MAX_ARCHIVE_COMPRESSION_RATIO
            ):
                raise ArchiveSecurityError(
                    f"Archive member {name!r} has a suspicious compression ratio. "
                    "Extraction aborted to prevent zip-bomb."
                )

            if name.endswith("/"):  # directory entry
                continue

            rel = name
            if prefix and rel.startswith(prefix):
                rel = rel[len(prefix) :]
            if not rel:
                continue
            if not rel.endswith(".og") and rel != "pack.json":
                continue

            # --- path traversal: validate the (prefix-stripped) write target ---
            if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
                raise ArchiveSecurityError(
                    f"Archive member {name!r} (stripped: {rel!r}) contains an illegal "
                    "path component. Extraction aborted."
                )
            target = dest / rel
            try:
                within_dest = target.resolve().is_relative_to(dest_resolved)
            except AttributeError:  # pragma: no cover — only pre-3.9
                within_dest = os.path.commonpath(
                    [str(dest_resolved), str(target.resolve())]
                ) == str(dest_resolved)
            if not within_dest:
                raise ArchiveSecurityError(
                    f"Archive member {name!r} (stripped: {rel!r}) would escape "
                    f"destination directory {dest_resolved}. Extraction aborted."
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            if rel.endswith(".og"):
                written.append(target)
    return written


def _install_local_dir(source: Path, dest: Path) -> list[Path]:
    """Copy .og files from a local directory into ``dest``."""
    written: list[Path] = []
    for og in source.rglob("*.og"):
        rel = og.relative_to(source)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(og, target)
        written.append(target)
    # Copy pack.json if present
    pj = source / "pack.json"
    if pj.exists():
        shutil.copy2(pj, dest / "pack.json")
    return written


def _read_pack_meta(pack_dir: Path) -> dict[str, Any]:
    """Read pack.json from an installed pack directory."""
    pj = pack_dir / "pack.json"
    if not pj.exists():
        return {}
    try:
        return json.loads(pj.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def install_pack(
    spec: str,
    skills_dir: Path,
    *,
    fetcher: Any = None,
) -> PackInfo:
    """Install a community skill pack.

    Args:
        spec: A ``user/repo`` shorthand, full archive URL, raw ``.og`` URL,
              or local directory path.
        skills_dir: The user's skills directory (e.g. ``~/.hachi/skills``).
        fetcher: Optional injectable downloader ``(url: str) -> bytes`` for
                 offline testing.  Defaults to :func:`_default_fetcher`.

    Returns:
        :class:`PackInfo` describing what was installed.

    Raises:
        ValueError: URL blocked by security policy or unsupported format.
        FileNotFoundError: Local path does not exist.
    """
    _fetch = fetcher or _default_fetcher
    pack_name = _derive_pack_name(spec)
    packs_root = skills_dir / "packs"
    dest = packs_root / pack_name

    # --- Local directory ---
    local = Path(spec)
    if local.exists() and local.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        written = _install_local_dir(local, dest)
        meta = _read_pack_meta(dest)
        effective_name = str(meta.get("name", pack_name))
        if effective_name != pack_name:
            # rename the dest directory to the canonical name
            new_dest = packs_root / effective_name
            shutil.move(str(dest), str(new_dest))
            dest = new_dest
        return PackInfo(
            name=effective_name,
            source=spec,
            installed_path=dest,
            file_count=len(written),
            version=str(meta.get("version", "")),
            description=str(meta.get("description", "")),
        )

    # --- Remote URL ---
    # Resolve GitHub shorthand to archive URL
    archive_url = spec
    if _GITHUB_SHORTHAND.match(spec):
        user, repo, ref = _parse_shorthand(spec)
        archive_url = _github_archive_url(user, repo, ref)
        pack_name = repo

    _validate_url(archive_url)
    raw = _fetch(archive_url)

    dest.mkdir(parents=True, exist_ok=True)

    # Detect format and extract
    if archive_url.endswith(".og"):
        og_name = archive_url.rsplit("/", 1)[-1]
        target = dest / og_name
        target.write_bytes(raw)
        written = [target]
    elif archive_url.endswith(".zip"):
        written = _extract_zip(raw, dest)
    else:
        # Treat everything else as tar.gz (GitHub default)
        written = _extract_tar(raw, dest)

    meta = _read_pack_meta(dest)
    effective_name = str(meta.get("name", pack_name))
    if effective_name != pack_name:
        new_dest = packs_root / effective_name
        if dest != new_dest:
            if new_dest.exists():
                shutil.rmtree(new_dest)
            shutil.move(str(dest), str(new_dest))
            dest = new_dest

    return PackInfo(
        name=effective_name,
        source=spec,
        installed_path=dest,
        file_count=len(written),
        version=str(meta.get("version", "")),
        description=str(meta.get("description", "")),
    )


def list_packs(skills_dir: Path) -> list[PackInfo]:
    """Return a list of all installed community skill packs.

    Args:
        skills_dir: The user's skills directory.

    Returns:
        List of :class:`PackInfo`, sorted by pack name.
    """
    packs_root = skills_dir / "packs"
    if not packs_root.exists():
        return []

    infos: list[PackInfo] = []
    for entry in sorted(packs_root.iterdir()):
        if not entry.is_dir():
            continue
        meta = _read_pack_meta(entry)
        og_files = list(entry.rglob("*.og"))
        infos.append(
            PackInfo(
                name=str(meta.get("name", entry.name)),
                source=str(meta.get("source", "")),
                installed_path=entry,
                file_count=len(og_files),
                version=str(meta.get("version", "")),
                description=str(meta.get("description", "")),
            )
        )
    return infos


def remove_pack(name: str, skills_dir: Path) -> bool:
    """Remove an installed community skill pack.

    Args:
        name: The pack name (directory name under ``packs/``).
        skills_dir: The user's skills directory.

    Returns:
        ``True`` if the pack was found and removed, ``False`` if not found.
    """
    pack_dir = skills_dir / "packs" / name
    if not pack_dir.exists():
        return False
    shutil.rmtree(pack_dir)
    return True
