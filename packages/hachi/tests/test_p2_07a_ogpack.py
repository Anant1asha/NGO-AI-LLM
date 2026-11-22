"""P2-07a: .ogpack format, installer, consent sheets, scope enforcement.

Tests:
- parse_pack_toml: id, semver, scopes, fs_paths, sha256s, schedule_budget
- render_consent_sheet: fresh install and update labelling
- render_scope_diff: empty when no widening, non-empty when wider
- install_ogpack_from_dir: copies .og files, writes metadata, verifies checksums
- list_ogpacks: reflects installed pack info
- remove_ogpack: removes directory, returns True; missing returns False
- get_installed_manifest: round-trips the manifest through pack.toml
- scope enforcement: widened_scopes / widened_fs_paths correctness
- OgPackManifest.scope_ids: returns frozenset of scope id strings
- CLI pack commands are registered
"""

from __future__ import annotations

import hashlib
import tarfile
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_toml(
    pack_id: str = "test-pack",
    semver: str = "1.0.0",
    scopes: list[str] | None = None,
    fs_paths: list[str] | None = None,
    sha256s: dict[str, str] | None = None,
    schedule_budget: dict | None = None,
    description: str = "A test pack",
    author: str = "Test Author",
) -> str:
    lines = [
        f'id = "{pack_id}"',
        f'semver = "{semver}"',
        f'description = "{description}"',
        f'author = "{author}"',
    ]
    if scopes:
        scopes_str = ", ".join(f'"{s}"' for s in scopes)
        lines.append(f"scopes = [{scopes_str}]")
    if fs_paths:
        paths_str = ", ".join(f'"{p}"' for p in fs_paths)
        lines.append(f"fs_paths = [{paths_str}]")
    if sha256s:
        lines.append("[sha256s]")
        for k, v in sha256s.items():
            lines.append(f'"{k}" = "{v}"')
    if schedule_budget:
        lines.append("[schedule_budget]")
        for k, v in schedule_budget.items():
            lines.append(f"{k} = {v}")
    return "\n".join(lines)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _make_pack_dir(tmp_path: Path, toml_content: str, og_files: dict[str, str]) -> Path:
    """Create a pack directory with pack.toml and .og files."""
    pack_dir = tmp_path / "pack_src"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.toml").write_text(toml_content, encoding="utf-8")
    for name, content in og_files.items():
        f = pack_dir / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    return pack_dir


# ---------------------------------------------------------------------------
# parse_pack_toml tests
# ---------------------------------------------------------------------------


def test_parse_pack_toml_minimal():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml('id = "my-pack"')
    assert m.id == "my-pack"
    assert m.semver == "0.0.0"
    assert m.scopes == ()
    assert m.fs_paths == ()
    assert m.sha256s == {}


def test_parse_pack_toml_full_fields():
    from hachi.core.og_pack import parse_pack_toml

    toml = _make_toml(
        pack_id="google-workspace",
        semver="2.1.0",
        scopes=["gmail.read", "calendar.write"],
        fs_paths=["/home/user/docs"],
        schedule_budget={"max_runs_per_day": 5, "max_cost_per_run": 0.05},
        description="Google workspace pack",
        author="Hachi Team",
    )
    m = parse_pack_toml(toml)
    assert m.id == "google-workspace"
    assert m.semver == "2.1.0"
    assert len(m.scopes) == 2
    scope_ids = {s.id for s in m.scopes}
    assert scope_ids == {"gmail.read", "calendar.write"}
    assert m.fs_paths == ("/home/user/docs",)
    assert m.schedule_budget.max_runs_per_day == 5
    assert m.schedule_budget.max_cost_per_run == pytest.approx(0.05)
    assert m.description == "Google workspace pack"
    assert m.author == "Hachi Team"


def test_parse_pack_toml_missing_id_raises():
    from hachi.core.og_pack import parse_pack_toml

    with pytest.raises(ValueError, match="id"):
        parse_pack_toml('semver = "1.0.0"')


def test_parse_pack_toml_accepts_bytes():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(b'id = "byte-pack"\nsemver = "0.1.0"')
    assert m.id == "byte-pack"


def test_parse_pack_toml_unknown_keys_ignored():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml('id = "x"\nfuture_field = "ignored"')
    assert m.id == "x"


def test_parse_pack_toml_sha256s():
    from hachi.core.og_pack import parse_pack_toml

    toml = textwrap.dedent("""\
        id = "hash-pack"
        [sha256s]
        "skill.og" = "abc123"
    """)
    m = parse_pack_toml(toml)
    assert m.sha256s == {"skill.og": "abc123"}


# ---------------------------------------------------------------------------
# OgPackManifest scope helpers
# ---------------------------------------------------------------------------


def test_scope_ids_returns_frozenset():
    from hachi.core.og_pack import OgPackManifest, PackScope

    m = OgPackManifest(
        id="x",
        scopes=(
            PackScope(id="gmail.read", description=""),
            PackScope(id="slack.send", description=""),
        ),
    )
    assert m.scope_ids() == frozenset({"gmail.read", "slack.send"})


def test_widened_scopes_detects_new_permissions():
    from hachi.core.og_pack import OgPackManifest, PackScope

    old = OgPackManifest(
        id="pack",
        semver="1.0.0",
        scopes=(PackScope(id="gmail.read", description=""),),
    )
    new = OgPackManifest(
        id="pack",
        semver="2.0.0",
        scopes=(
            PackScope(id="gmail.read", description=""),
            PackScope(id="gmail.send", description=""),
        ),
    )
    assert old.widened_scopes(new) == frozenset({"gmail.send"})


def test_widened_scopes_empty_when_no_change():
    from hachi.core.og_pack import OgPackManifest, PackScope

    old = OgPackManifest(id="p", scopes=(PackScope(id="gmail.read", description=""),))
    new = OgPackManifest(id="p", scopes=(PackScope(id="gmail.read", description=""),))
    assert old.widened_scopes(new) == frozenset()


def test_widened_fs_paths():
    from hachi.core.og_pack import OgPackManifest

    old = OgPackManifest(id="p", fs_paths=("/home/user",))
    new = OgPackManifest(id="p", fs_paths=("/home/user", "/etc/secrets"))
    assert old.widened_fs_paths(new) == frozenset({"/etc/secrets"})


# ---------------------------------------------------------------------------
# Consent sheet rendering
# ---------------------------------------------------------------------------


def test_render_consent_sheet_shows_pack_id():
    from hachi.core.og_pack import OgPackManifest, render_consent_sheet

    m = OgPackManifest(id="my-pack", semver="1.0.0", description="A pack")
    sheet = render_consent_sheet(m)
    assert "my-pack" in sheet
    assert "1.0.0" in sheet
    assert "Install" in sheet


def test_render_consent_sheet_update_label():
    from hachi.core.og_pack import OgPackManifest, render_consent_sheet

    m = OgPackManifest(id="my-pack", semver="2.0.0")
    sheet = render_consent_sheet(m, update=True)
    assert "Update" in sheet


def test_render_consent_sheet_shows_scopes():
    from hachi.core.og_pack import OgPackManifest, PackScope, render_consent_sheet

    m = OgPackManifest(
        id="x",
        scopes=(PackScope(id="gmail.read", description="Read Gmail messages and labels"),),
    )
    sheet = render_consent_sheet(m)
    assert "gmail.read" in sheet
    assert "Read Gmail" in sheet


def test_render_consent_sheet_no_scopes_friendly():
    from hachi.core.og_pack import OgPackManifest, render_consent_sheet

    m = OgPackManifest(id="x")
    sheet = render_consent_sheet(m)
    assert "No integration scopes" in sheet


def test_render_consent_sheet_shows_schedule_budget():
    from hachi.core.og_pack import OgPackManifest, ScheduleBudget, render_consent_sheet

    m = OgPackManifest(
        id="x",
        schedule_budget=ScheduleBudget(max_runs_per_day=3, max_cost_per_run=0.02),
    )
    sheet = render_consent_sheet(m)
    assert "3" in sheet
    assert "0.0200" in sheet


def test_render_consent_sheet_no_code_execution_note():
    from hachi.core.og_pack import OgPackManifest, render_consent_sheet

    m = OgPackManifest(id="x")
    sheet = render_consent_sheet(m)
    assert "no install-time code execution" in sheet.lower()


# ---------------------------------------------------------------------------
# Scope diff rendering
# ---------------------------------------------------------------------------


def test_render_scope_diff_empty_when_no_widening():
    from hachi.core.og_pack import OgPackManifest, PackScope, render_scope_diff

    scope = PackScope(id="gmail.read", description="")
    old = OgPackManifest(id="p", semver="1.0.0", scopes=(scope,))
    new = OgPackManifest(id="p", semver="1.1.0", scopes=(scope,))
    assert render_scope_diff(old, new) == ""


def test_render_scope_diff_shows_new_scope():
    from hachi.core.og_pack import OgPackManifest, PackScope, render_scope_diff

    old = OgPackManifest(
        id="p", semver="1.0.0", scopes=(PackScope(id="gmail.read", description=""),)
    )
    new = OgPackManifest(
        id="p",
        semver="2.0.0",
        scopes=(
            PackScope(id="gmail.read", description=""),
            PackScope(id="gmail.send", description="Send email on your behalf"),
        ),
    )
    diff = render_scope_diff(old, new)
    assert "gmail.send" in diff
    assert "1.0.0" in diff
    assert "2.0.0" in diff


def test_render_scope_diff_shows_new_fs_path():
    from hachi.core.og_pack import OgPackManifest, render_scope_diff

    old = OgPackManifest(id="p", fs_paths=("/home",))
    new = OgPackManifest(id="p", fs_paths=("/home", "/var/data"))
    diff = render_scope_diff(old, new)
    assert "/var/data" in diff


# ---------------------------------------------------------------------------
# Install from dir
# ---------------------------------------------------------------------------


def test_install_ogpack_from_dir_copies_og_files(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_dir

    og_content = "::index\n- skill\n::dense\nskill = Skill node\n"
    pack_dir = _make_pack_dir(
        tmp_path,
        _make_toml("demo-pack"),
        {"skill.og": og_content},
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    manifest, files = install_ogpack_from_dir(pack_dir, skills_dir, confirm=False)

    assert manifest.id == "demo-pack"
    assert len(files) == 1
    installed_og = skills_dir / "packs" / "demo-pack" / "skill.og"
    assert installed_og.exists()
    assert installed_og.read_text(encoding="utf-8") == og_content


def test_install_ogpack_from_dir_writes_metadata(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_dir, list_ogpacks

    pack_dir = _make_pack_dir(
        tmp_path,
        _make_toml("meta-pack", scopes=["gmail.read"]),
        {"a.og": "content"},
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    install_ogpack_from_dir(pack_dir, skills_dir, source="local/path", confirm=False)

    packs = list_ogpacks(skills_dir)
    assert any(p.id == "meta-pack" for p in packs)
    p = next(p for p in packs if p.id == "meta-pack")
    assert "gmail.read" in p.scope_ids


def test_install_ogpack_from_dir_checksum_fails_on_mismatch(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_dir

    toml = textwrap.dedent("""\
        id = "checksum-pack"
        [sha256s]
        "skill.og" = "badhash"
    """)
    pack_dir = _make_pack_dir(tmp_path, toml, {"skill.og": "hello"})
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    with pytest.raises(ValueError, match="integrity check failed"):
        install_ogpack_from_dir(pack_dir, skills_dir, confirm=False)


def test_install_ogpack_from_dir_passes_valid_checksum(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_dir

    og_content = b"::index\n- test\n"
    h = _sha256(og_content)
    toml = textwrap.dedent(f"""\
        id = "hash-ok-pack"
        [sha256s]
        "skill.og" = "{h}"
    """)
    pack_dir = _make_pack_dir(tmp_path, toml, {})
    (pack_dir / "skill.og").write_bytes(og_content)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    manifest, files = install_ogpack_from_dir(pack_dir, skills_dir, confirm=False)
    assert manifest.id == "hash-ok-pack"
    assert len(files) == 1


def test_install_ogpack_no_pack_toml_raises(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_dir

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        install_ogpack_from_dir(empty_dir, skills_dir, confirm=False)


# ---------------------------------------------------------------------------
# Install from archive
# ---------------------------------------------------------------------------


def test_install_ogpack_from_archive(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_archive

    pack_dir = _make_pack_dir(tmp_path, _make_toml("archive-pack"), {"b.og": "data"})
    archive = tmp_path / "archive-pack.ogpack"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(pack_dir, arcname="archive-pack")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    manifest, files = install_ogpack_from_archive(archive, skills_dir, confirm=False)
    assert manifest.id == "archive-pack"
    assert len(files) == 1


def test_install_from_archive_no_pack_toml_raises(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_archive

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    archive = tmp_path / "bad.ogpack"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(empty_dir, arcname="empty")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        install_ogpack_from_archive(archive, skills_dir, confirm=False)


# ---------------------------------------------------------------------------
# list_ogpacks / remove_ogpack / get_installed_manifest
# ---------------------------------------------------------------------------


def test_list_ogpacks_empty_when_none_installed(tmp_path):
    from hachi.core.og_pack import list_ogpacks

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    assert list_ogpacks(skills_dir) == []


def test_list_ogpacks_after_install(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_dir, list_ogpacks

    pack_dir = _make_pack_dir(tmp_path, _make_toml("listed-pack", semver="3.0.0"), {"x.og": "x"})
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    install_ogpack_from_dir(pack_dir, skills_dir, confirm=False)

    packs = list_ogpacks(skills_dir)
    ids = [p.id for p in packs]
    assert "listed-pack" in ids
    p = next(p for p in packs if p.id == "listed-pack")
    assert p.semver == "3.0.0"
    assert p.og_file_count == 1


def test_remove_ogpack_found(tmp_path):
    from hachi.core.og_pack import install_ogpack_from_dir, remove_ogpack

    pack_dir = _make_pack_dir(tmp_path, _make_toml("to-remove"), {"y.og": "y"})
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    install_ogpack_from_dir(pack_dir, skills_dir, confirm=False)

    result = remove_ogpack("to-remove", skills_dir)
    assert result is True
    assert not (skills_dir / "packs" / "to-remove").exists()


def test_remove_ogpack_not_found(tmp_path):
    from hachi.core.og_pack import remove_ogpack

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    result = remove_ogpack("nonexistent", skills_dir)
    assert result is False


def test_get_installed_manifest_round_trip(tmp_path):
    from hachi.core.og_pack import get_installed_manifest, install_ogpack_from_dir

    pack_dir = _make_pack_dir(
        tmp_path,
        _make_toml("round-trip", semver="1.2.3", scopes=["slack.read"]),
        {"z.og": "z"},
    )
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    install_ogpack_from_dir(pack_dir, skills_dir, confirm=False)

    manifest = get_installed_manifest("round-trip", skills_dir)
    assert manifest is not None
    assert manifest.id == "round-trip"
    assert manifest.semver == "1.2.3"
    assert any(s.id == "slack.read" for s in manifest.scopes)


def test_get_installed_manifest_missing_returns_none(tmp_path):
    from hachi.core.og_pack import get_installed_manifest

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    assert get_installed_manifest("does-not-exist", skills_dir) is None


# ---------------------------------------------------------------------------
# Scope-diff on update shows widening
# ---------------------------------------------------------------------------


def test_scope_diff_printed_when_update_widens(tmp_path, capsys):
    from hachi.core.og_pack import install_ogpack_from_dir, parse_pack_toml

    old_toml = _make_toml("evolving", semver="1.0.0", scopes=["gmail.read"])
    new_toml = _make_toml("evolving", semver="2.0.0", scopes=["gmail.read", "gmail.send"])

    old_dir = _make_pack_dir(tmp_path / "v1", old_toml, {"a.og": "v1"})
    new_dir = _make_pack_dir(tmp_path / "v2", new_toml, {"a.og": "v2"})

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    install_ogpack_from_dir(old_dir, skills_dir, confirm=False)
    old_manifest = parse_pack_toml(old_toml)

    install_ogpack_from_dir(new_dir, skills_dir, confirm=True, old_manifest=old_manifest)
    captured = capsys.readouterr()
    assert "gmail.send" in captured.out


# ---------------------------------------------------------------------------
# CLI pack commands are registered
# ---------------------------------------------------------------------------


def test_pack_cli_install_registered():
    from hachi.cli.main import ogpack_app

    names = {c.name or c.callback.__name__ for c in ogpack_app.registered_commands}
    assert any("install" in n for n in names)


def test_pack_cli_list_registered():
    from hachi.cli.main import ogpack_app

    names = {c.name or c.callback.__name__ for c in ogpack_app.registered_commands}
    assert any("list" in n for n in names)


def test_pack_cli_remove_registered():
    from hachi.cli.main import ogpack_app

    names = {c.name or c.callback.__name__ for c in ogpack_app.registered_commands}
    assert any("remove" in n for n in names)


def test_pack_cli_update_registered():
    from hachi.cli.main import ogpack_app

    names = {c.name or c.callback.__name__ for c in ogpack_app.registered_commands}
    assert any("update" in n for n in names)


def test_pack_app_added_to_main_app():
    from hachi.cli.main import app

    group_names = {g.name for g in app.registered_groups}
    assert "pack" in group_names
