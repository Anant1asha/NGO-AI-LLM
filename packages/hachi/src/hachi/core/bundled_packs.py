"""Bundled packs shipped with Hachi.

These packs live inside the installed package under ``hachi/packs/``.
:func:`list_bundled_packs` enumerates them; :func:`install_bundled_pack` copies
a single pack into the user's skills directory (with consent sheet generation).
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from hachi.core.og_pack import (
    OgPackManifest,
    install_ogpack_from_dir,
    parse_pack_toml,
    render_consent_sheet,
)


def _bundled_packs_root() -> Path:
    """Return the path to the ``hachi/packs/`` directory in the package."""
    try:
        ref = importlib.resources.files("hachi") / "packs"
        return Path(str(ref))
    except Exception:
        return Path(__file__).parent.parent / "packs"


def list_bundled_pack_dirs() -> list[Path]:
    """Return a list of pack directories shipped with this installation."""
    root = _bundled_packs_root()
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "pack.toml").exists()
    )


def list_bundled_manifests() -> list[OgPackManifest]:
    """Return parsed manifests for all bundled packs."""
    manifests: list[OgPackManifest] = []
    for pack_dir in list_bundled_pack_dirs():
        try:
            m = parse_pack_toml((pack_dir / "pack.toml").read_bytes())
            manifests.append(m)
        except Exception:
            pass
    return manifests


def install_bundled_pack(
    pack_id: str,
    skills_dir: Path,
    *,
    confirm: bool = False,
) -> tuple[OgPackManifest, list[str]] | None:
    """Install a specific bundled pack into ``skills_dir``.

    Args:
        pack_id:    The pack id to install (matches the directory name).
        skills_dir: User's skills directory.
        confirm:    If True, print the scope diff on update (consent already shown by caller).

    Returns:
        (manifest, installed_files) on success; None if the pack does not exist.
    """
    root = _bundled_packs_root()
    pack_dir = root / pack_id
    if not pack_dir.exists():
        return None
    return install_ogpack_from_dir(pack_dir, skills_dir, confirm=confirm)


def get_bundled_consent_sheet(pack_id: str) -> str:
    """Return the consent sheet string for a bundled pack, or '' if not found."""
    root = _bundled_packs_root()
    toml_path = root / pack_id / "pack.toml"
    if not toml_path.exists():
        return ""
    try:
        manifest = parse_pack_toml(toml_path.read_bytes())
        return render_consent_sheet(manifest)
    except Exception:
        return ""
