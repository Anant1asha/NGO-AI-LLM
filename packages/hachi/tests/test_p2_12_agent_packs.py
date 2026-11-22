"""P2-12: Email + Meeting agents as packs.

Tests:
- inbox-sentinel/pack.toml: parses cleanly; declares gmail.read, gmail.write, slack.send
- meeting-copilot/pack.toml: parses cleanly; declares calendar.read, gmail.read, drive.write
- Both packs have schedule_budget fields
- Both pack.toml consent sheets render without error
- list_bundled_pack_dirs: returns both packs
- list_bundled_manifests: returns manifests for both packs
- install_bundled_pack: copies .og files into skills_dir
- get_bundled_consent_sheet: returns non-empty string for valid pack id
- Packs pass og_pack integrity check (no sha256s declared = passes trivially)
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Manifest parsing tests
# ---------------------------------------------------------------------------

PACK_ROOT = Path(__file__).parent.parent / "src" / "hachi" / "packs"


def _pack_toml(pack_id: str) -> bytes:
    return (PACK_ROOT / pack_id / "pack.toml").read_bytes()


def test_inbox_sentinel_pack_toml_parses():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("inbox-sentinel"))
    assert m.id == "inbox-sentinel"
    assert m.semver == "1.0.0"


def test_inbox_sentinel_declares_gmail_read():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("inbox-sentinel"))
    scope_ids = {s.id for s in m.scopes}
    assert "gmail.read" in scope_ids


def test_inbox_sentinel_declares_gmail_write():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("inbox-sentinel"))
    scope_ids = {s.id for s in m.scopes}
    assert "gmail.write" in scope_ids


def test_inbox_sentinel_declares_slack_send():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("inbox-sentinel"))
    scope_ids = {s.id for s in m.scopes}
    assert "slack.send" in scope_ids


def test_inbox_sentinel_has_schedule_budget():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("inbox-sentinel"))
    assert m.schedule_budget.max_runs_per_day > 0


def test_meeting_copilot_pack_toml_parses():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("meeting-copilot"))
    assert m.id == "meeting-copilot"
    assert m.semver == "1.0.0"


def test_meeting_copilot_declares_calendar_read():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("meeting-copilot"))
    scope_ids = {s.id for s in m.scopes}
    assert "calendar.read" in scope_ids


def test_meeting_copilot_declares_gmail_read():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("meeting-copilot"))
    scope_ids = {s.id for s in m.scopes}
    assert "gmail.read" in scope_ids


def test_meeting_copilot_declares_drive_write():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("meeting-copilot"))
    scope_ids = {s.id for s in m.scopes}
    assert "drive.write" in scope_ids


def test_meeting_copilot_has_max_cost_per_run():
    from hachi.core.og_pack import parse_pack_toml

    m = parse_pack_toml(_pack_toml("meeting-copilot"))
    assert m.schedule_budget.max_cost_per_run > 0


# ---------------------------------------------------------------------------
# Consent sheet rendering
# ---------------------------------------------------------------------------


def test_inbox_sentinel_consent_sheet_renders():
    from hachi.core.og_pack import parse_pack_toml, render_consent_sheet

    m = parse_pack_toml(_pack_toml("inbox-sentinel"))
    sheet = render_consent_sheet(m)
    assert "inbox-sentinel" in sheet
    assert "gmail.read" in sheet
    assert "no install-time code execution" in sheet.lower()


def test_meeting_copilot_consent_sheet_renders():
    from hachi.core.og_pack import parse_pack_toml, render_consent_sheet

    m = parse_pack_toml(_pack_toml("meeting-copilot"))
    sheet = render_consent_sheet(m)
    assert "meeting-copilot" in sheet
    assert "drive.write" in sheet


# ---------------------------------------------------------------------------
# Bundled packs module
# ---------------------------------------------------------------------------


def test_list_bundled_pack_dirs_includes_both_packs():
    from hachi.core.bundled_packs import list_bundled_pack_dirs

    dirs = list_bundled_pack_dirs()
    ids = {d.name for d in dirs}
    assert "inbox-sentinel" in ids
    assert "meeting-copilot" in ids


def test_list_bundled_manifests_returns_two_manifests():
    from hachi.core.bundled_packs import list_bundled_manifests

    manifests = list_bundled_manifests()
    ids = {m.id for m in manifests}
    assert "inbox-sentinel" in ids
    assert "meeting-copilot" in ids


def test_install_bundled_pack_copies_og_files(tmp_path):
    from hachi.core.bundled_packs import install_bundled_pack

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    result = install_bundled_pack("inbox-sentinel", skills_dir, confirm=False)
    assert result is not None
    manifest, files = result
    assert manifest.id == "inbox-sentinel"
    assert len(files) >= 1
    installed = skills_dir / "packs" / "inbox-sentinel"
    assert installed.exists()
    assert any(f.suffix == ".og" for f in installed.iterdir())


def test_install_bundled_pack_not_found_returns_none(tmp_path):
    from hachi.core.bundled_packs import install_bundled_pack

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    result = install_bundled_pack("nonexistent-pack", skills_dir, confirm=False)
    assert result is None


def test_get_bundled_consent_sheet_non_empty():
    from hachi.core.bundled_packs import get_bundled_consent_sheet

    sheet = get_bundled_consent_sheet("inbox-sentinel")
    assert len(sheet) > 0
    assert "inbox-sentinel" in sheet


def test_get_bundled_consent_sheet_missing_returns_empty():
    from hachi.core.bundled_packs import get_bundled_consent_sheet

    assert get_bundled_consent_sheet("no-such-pack") == ""


# ---------------------------------------------------------------------------
# .og files exist in pack directories
# ---------------------------------------------------------------------------


def test_inbox_sentinel_has_og_file():
    og_files = list((PACK_ROOT / "inbox-sentinel").glob("*.og"))
    assert len(og_files) >= 1


def test_meeting_copilot_has_og_file():
    og_files = list((PACK_ROOT / "meeting-copilot").glob("*.og"))
    assert len(og_files) >= 1
