from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OptionalSkillPack:
    pack_id: str
    directories: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    required_capability: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class SkillPackManifest:
    core_files: tuple[str, ...] = ()
    core_directories: tuple[str, ...] = ()
    optional_packs: dict[str, OptionalSkillPack] = field(default_factory=dict)

    def pack_for_capability(self, capability_id: str) -> OptionalSkillPack | None:
        for pack in self.optional_packs.values():
            if pack.required_capability == capability_id:
                return pack
        return None


def _default_skills_root() -> Path:
    return Path(__file__).parent.parent / "default_skills"


def _manifest_path() -> Path:
    return _default_skills_root() / "manifest.json"


def load_skill_pack_manifest(manifest_path: Path | None = None) -> SkillPackManifest:
    path = manifest_path or _manifest_path()
    if not path.exists():
        return SkillPackManifest()

    payload = json.loads(path.read_text(encoding="utf-8"))

    core = payload.get("core", {}) if isinstance(payload, dict) else {}
    optional_raw = payload.get("optional_packs", {}) if isinstance(payload, dict) else {}

    optional: dict[str, OptionalSkillPack] = {}
    if isinstance(optional_raw, dict):
        for pack_id, value in optional_raw.items():
            if not isinstance(value, dict):
                continue
            optional[pack_id] = OptionalSkillPack(
                pack_id=str(pack_id),
                directories=tuple(str(x) for x in value.get("directories", []) if str(x).strip()),
                files=tuple(str(x) for x in value.get("files", []) if str(x).strip()),
                required_capability=str(value.get("required_capability", "")),
                description=str(value.get("description", "")),
            )

    return SkillPackManifest(
        core_files=tuple(str(x) for x in core.get("files", []) if str(x).strip()),
        core_directories=tuple(str(x) for x in core.get("directories", []) if str(x).strip()),
        optional_packs=optional,
    )


def _copy_relative_entries(
    source_root: Path, target_root: Path, entries: Sequence[str]
) -> list[Path]:
    copied: list[Path] = []
    for rel in entries:
        src = source_root / rel
        dst = target_root / rel
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            copied.append(dst)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def install_core_skill_packs(
    target_skills_dir: Path, source_root: Path | None = None
) -> list[Path]:
    source = source_root or _default_skills_root()
    manifest = load_skill_pack_manifest(source / "manifest.json")
    entries = [*manifest.core_files, *manifest.core_directories]
    return _copy_relative_entries(source, target_skills_dir, entries)


def install_skill_pack(
    pack_id: str, target_skills_dir: Path, source_root: Path | None = None
) -> list[Path]:
    source = source_root or _default_skills_root()
    manifest = load_skill_pack_manifest(source / "manifest.json")
    pack = manifest.optional_packs.get(pack_id)
    if not pack:
        return []

    entries = [*pack.files, *pack.directories]
    return _copy_relative_entries(source, target_skills_dir, entries)


def ensure_enabled_skill_packs(
    target_skills_dir: Path, enabled_capabilities: Sequence[str], source_root: Path | None = None
) -> dict[str, list[Path]]:
    source = source_root or _default_skills_root()
    manifest = load_skill_pack_manifest(source / "manifest.json")
    installed: dict[str, list[Path]] = {}
    enabled = set(enabled_capabilities)

    for pack_id, pack in manifest.optional_packs.items():
        if pack.required_capability and pack.required_capability not in enabled:
            continue
        entries = [*pack.files, *pack.directories]
        installed[pack_id] = _copy_relative_entries(source, target_skills_dir, entries)

    return installed
