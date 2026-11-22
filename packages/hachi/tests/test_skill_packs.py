"""Tests for the community skill pack system.

Covers:
1.  _derive_pack_name — GitHub shorthand, archive URL, .og URL
2.  _parse_shorthand — user/repo, user/repo@ref
3.  install_pack — local directory (no network)
4.  install_pack — local dir with pack.json renames pack to canonical name
5.  install_pack — tar.gz bytes (offline, injected fetcher)
6.  install_pack — tar.gz GitHub shorthand (injected fetcher)
7.  install_pack — .zip bytes (offline, injected fetcher)
8.  install_pack — single .og file URL (injected fetcher)
9.  install_pack — SSRF blocked URL raises ValueError
10. list_packs — empty packs dir
11. list_packs — lists installed packs
12. remove_pack — removes existing pack
13. remove_pack — returns False for unknown pack
14. CLI: skill pack list (empty)
15. CLI: skill pack install from local dir
16. CLI: skill pack install --json
17. CLI: skill pack remove
18. CLI: skill pack install failure exits 1
19. CLI: skill pack list --json
"""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.core.community_packs import (
    _derive_pack_name,
    _parse_shorthand,
    install_pack,
    list_packs,
    remove_pack,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tar_gz(files: dict[str, str], prefix: str = "repo-main") -> bytes:
    """Build an in-memory tar.gz with the given relative paths → content."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            raw = content.encode()
            info = tarfile.TarInfo(name=f"{prefix}/{name}")
            info.size = len(raw)
            tf.addfile(info, io.BytesIO(raw))
    return buf.getvalue()


def _make_zip(files: dict[str, str], prefix: str = "repo-main") -> bytes:
    """Build an in-memory zip with the given relative paths → content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(f"{prefix}/{name}", content)
    return buf.getvalue()


def _simple_og(name: str) -> str:
    return f"::node[{name}]\n->[:keywords={name}]\n\n::dense\n{name}\n"


# ---------------------------------------------------------------------------
# 1. _derive_pack_name
# ---------------------------------------------------------------------------


def test_derive_pack_name_github_shorthand() -> None:

    assert _derive_pack_name("alice/devops-skills") == "devops-skills"


def test_derive_pack_name_github_with_ref() -> None:

    assert _derive_pack_name("alice/devops-skills@v2") == "devops-skills"


def test_derive_pack_name_archive_url() -> None:

    assert (
        _derive_pack_name("https://github.com/alice/skills/archive/refs/heads/main.tar.gz")
        == "main"
    )


def test_derive_pack_name_og_url() -> None:

    assert _derive_pack_name("https://example.com/my_skill.og") == "my_skill"


# ---------------------------------------------------------------------------
# 2. _parse_shorthand
# ---------------------------------------------------------------------------


def test_parse_shorthand_default_ref() -> None:
    user, repo, ref = _parse_shorthand("alice/devops-skills")
    assert user == "alice"
    assert repo == "devops-skills"
    assert ref == "main"


def test_parse_shorthand_custom_ref() -> None:
    user, repo, ref = _parse_shorthand("alice/devops-skills@v2")
    assert user == "alice"
    assert repo == "devops-skills"
    assert ref == "v2"


# ---------------------------------------------------------------------------
# 3. install_pack — local directory
# ---------------------------------------------------------------------------


def test_install_local_dir(tmp_path: Path) -> None:
    src = tmp_path / "mypkg"
    src.mkdir()
    (src / "skill_a.og").write_text(_simple_og("skill_a"), encoding="utf-8")
    (src / "skill_b.og").write_text(_simple_og("skill_b"), encoding="utf-8")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    info = install_pack(str(src), skills_dir)
    assert info.name == "mypkg"
    assert info.file_count == 2
    assert (info.installed_path / "skill_a.og").exists()
    assert (info.installed_path / "skill_b.og").exists()


# ---------------------------------------------------------------------------
# 4. install_pack — local dir with pack.json renames pack
# ---------------------------------------------------------------------------


def test_install_local_dir_with_pack_json(tmp_path: Path) -> None:
    src = tmp_path / "rawdir"
    src.mkdir()
    (src / "skill_a.og").write_text(_simple_og("skill_a"), encoding="utf-8")
    (src / "pack.json").write_text(
        json.dumps({"name": "canonical-name", "version": "2.0.0", "description": "Test"}),
        encoding="utf-8",
    )

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    info = install_pack(str(src), skills_dir)
    assert info.name == "canonical-name"
    assert info.version == "2.0.0"
    assert info.description == "Test"
    assert info.file_count == 1
    assert (skills_dir / "packs" / "canonical-name" / "skill_a.og").exists()


# ---------------------------------------------------------------------------
# 5. install_pack — tar.gz via injected fetcher
# ---------------------------------------------------------------------------


def test_install_from_tarball(tmp_path: Path) -> None:
    data = _make_tar_gz({"alpha.og": _simple_og("alpha"), "beta.og": _simple_og("beta")})
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    info = install_pack(
        "https://example.com/mypack.tar.gz",
        skills_dir,
        fetcher=lambda url: data,
    )
    assert info.file_count == 2
    assert (info.installed_path / "alpha.og").exists()


# ---------------------------------------------------------------------------
# 6. install_pack — GitHub shorthand (injected fetcher)
# ---------------------------------------------------------------------------


def test_install_github_shorthand(tmp_path: Path) -> None:
    data = _make_tar_gz({"skill_a.og": _simple_og("skill_a")}, prefix="devops-skills-main")
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    captured_url: list[str] = []

    def fake_fetch(url: str) -> bytes:
        captured_url.append(url)
        return data

    info = install_pack("alice/devops-skills", skills_dir, fetcher=fake_fetch)
    assert info.name == "devops-skills"
    assert "alice/devops-skills/archive" in captured_url[0]
    assert info.file_count == 1


# ---------------------------------------------------------------------------
# 7. install_pack — zip (injected fetcher)
# ---------------------------------------------------------------------------


def test_install_from_zip(tmp_path: Path) -> None:
    data = _make_zip({"gamma.og": _simple_og("gamma")})
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    info = install_pack(
        "https://example.com/pack.zip",
        skills_dir,
        fetcher=lambda url: data,
    )
    assert info.file_count == 1
    assert (info.installed_path / "gamma.og").exists()


# ---------------------------------------------------------------------------
# 8. install_pack — single .og URL
# ---------------------------------------------------------------------------


def test_install_single_og_url(tmp_path: Path) -> None:
    og_content = _simple_og("single_skill")
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    info = install_pack(
        "https://example.com/single_skill.og",
        skills_dir,
        fetcher=lambda url: og_content.encode(),
    )
    assert info.file_count == 1
    assert (info.installed_path / "single_skill.og").exists()


# ---------------------------------------------------------------------------
# 9. install_pack — SSRF blocked URL
# ---------------------------------------------------------------------------


def test_install_ssrf_blocked_raises(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    with pytest.raises(ValueError, match="blocked"):
        install_pack(
            "https://127.0.0.1:8080/evil.tar.gz",
            skills_dir,
            fetcher=lambda url: b"",
        )


# ---------------------------------------------------------------------------
# 10. list_packs — empty
# ---------------------------------------------------------------------------


def test_list_packs_empty(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    assert list_packs(skills_dir) == []


# ---------------------------------------------------------------------------
# 11. list_packs — lists installed packs
# ---------------------------------------------------------------------------


def test_list_packs_with_packs(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    pack_a = skills_dir / "packs" / "pack_a"
    pack_b = skills_dir / "packs" / "pack_b"
    pack_a.mkdir(parents=True)
    pack_b.mkdir(parents=True)
    (pack_a / "s.og").write_text(_simple_og("s"), encoding="utf-8")
    (pack_b / "t.og").write_text(_simple_og("t"), encoding="utf-8")
    (pack_b / "u.og").write_text(_simple_og("u"), encoding="utf-8")

    packs = list_packs(skills_dir)
    names = [p.name for p in packs]
    assert "pack_a" in names
    assert "pack_b" in names
    assert next(p for p in packs if p.name == "pack_b").file_count == 2


# ---------------------------------------------------------------------------
# 12. remove_pack — existing pack
# ---------------------------------------------------------------------------


def test_remove_pack_existing(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    pack_dir = skills_dir / "packs" / "mypack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "s.og").write_text(_simple_og("s"), encoding="utf-8")

    assert remove_pack("mypack", skills_dir) is True
    assert not pack_dir.exists()


# ---------------------------------------------------------------------------
# 13. remove_pack — unknown pack
# ---------------------------------------------------------------------------


def test_remove_pack_unknown(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    assert remove_pack("does_not_exist", skills_dir) is False


# ---------------------------------------------------------------------------
# 14. CLI: skill pack list (empty)
# ---------------------------------------------------------------------------


def test_cli_pack_list_empty(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["skill", "pack", "list"])
    assert result.exit_code == 0, result.output
    assert "No community packs" in result.output


# ---------------------------------------------------------------------------
# 15. CLI: skill pack install from local dir
# ---------------------------------------------------------------------------


def test_cli_pack_install_local(tmp_path: Path) -> None:
    src = tmp_path / "mypkg"
    src.mkdir()
    (src / "skill_x.og").write_text(_simple_og("skill_x"), encoding="utf-8")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["skill", "pack", "install", str(src)])
    assert result.exit_code == 0, result.output
    assert "Installed" in result.output
    assert "mypkg" in result.output


# ---------------------------------------------------------------------------
# 16. CLI: skill pack install --json
# ---------------------------------------------------------------------------


def test_cli_pack_install_json(tmp_path: Path) -> None:
    src = tmp_path / "jsonpkg"
    src.mkdir()
    (src / "s.og").write_text(_simple_og("s"), encoding="utf-8")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["skill", "pack", "install", str(src), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["name"] == "jsonpkg"
    assert data["file_count"] == 1


# ---------------------------------------------------------------------------
# 17. CLI: skill pack remove
# ---------------------------------------------------------------------------


def test_cli_pack_remove(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    pack_dir = skills_dir / "packs" / "mypkg"
    pack_dir.mkdir(parents=True)
    (pack_dir / "s.og").write_text(_simple_og("s"), encoding="utf-8")

    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["skill", "pack", "remove", "mypkg"])
    assert result.exit_code == 0, result.output
    assert "Removed" in result.output
    assert not pack_dir.exists()


# ---------------------------------------------------------------------------
# 18. CLI: skill pack install failure exits 1
# ---------------------------------------------------------------------------


def test_cli_pack_install_failure(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(
            app,
            ["skill", "pack", "install", "https://127.0.0.1/bad.tar.gz"],
        )
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# 19. CLI: skill pack list --json
# ---------------------------------------------------------------------------


def test_cli_pack_list_json(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    pack_dir = skills_dir / "packs" / "alpha"
    pack_dir.mkdir(parents=True)
    (pack_dir / "s.og").write_text(_simple_og("s"), encoding="utf-8")
    (pack_dir / "pack.json").write_text(
        json.dumps({"name": "alpha", "version": "1.0", "description": "Alpha pack"}),
        encoding="utf-8",
    )

    with patch("hachi.gateway.workspace.get_skills_dir", return_value=skills_dir):
        result = runner.invoke(app, ["skill", "pack", "list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["name"] == "alpha"
    assert data[0]["version"] == "1.0"
