"""Tests for og_history (append-only versioning) and config_loader validation.

Covers:
- og_history: record 3 versions, list returns 3 ascending, get_version returns
  correct snapshots, append-only/monotonic guarantee.
- config_loader: unknown top-level key produces a warning; HACHI_CONFIG_STRICT=1
  causes a raise; malformed TOML is handled gracefully; atomic upsert leaves no
  stray temp file (integration smoke-test).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# og_history tests
# ---------------------------------------------------------------------------
from hachi.core.og_history import get_version, list_versions, record_version


def test_record_three_versions_ascending(tmp_path: Path) -> None:
    """record_version returns monotonically increasing version numbers."""
    hdir = tmp_path / "history"

    v1 = record_version("my-skill", "content v1", "human", "initial", history_dir=hdir)
    v2 = record_version("my-skill", "content v2", "agent", "refined", history_dir=hdir)
    v3 = record_version("my-skill", "content v3", "agent", "polished", history_dir=hdir)

    assert v1 == 1
    assert v2 == 2
    assert v3 == 3


def test_list_versions_returns_three_ascending(tmp_path: Path) -> None:
    """list_versions returns metadata for all recorded versions, ascending."""
    hdir = tmp_path / "history"

    record_version("skill-x", "a", "human", "create", history_dir=hdir)
    record_version("skill-x", "b", "agent", "update", history_dir=hdir)
    record_version("skill-x", "c", "agent", "refine", history_dir=hdir)

    versions = list_versions("skill-x", history_dir=hdir)

    assert len(versions) == 3
    assert [v["version"] for v in versions] == [1, 2, 3]
    assert versions[0]["author"] == "human"
    assert versions[1]["author"] == "agent"
    assert versions[2]["summary"] == "refine"
    # Content must NOT appear in list_versions output.
    for v in versions:
        assert "content" not in v


def test_get_version_returns_correct_snapshot(tmp_path: Path) -> None:
    """get_version retrieves the exact content for each version."""
    hdir = tmp_path / "history"

    record_version("snap-skill", "alpha", "human", "v1", history_dir=hdir)
    record_version("snap-skill", "beta", "agent", "v2", history_dir=hdir)
    record_version("snap-skill", "gamma", "agent", "v3", history_dir=hdir)

    assert get_version("snap-skill", 1, history_dir=hdir) == "alpha"
    assert get_version("snap-skill", 2, history_dir=hdir) == "beta"
    assert get_version("snap-skill", 3, history_dir=hdir) == "gamma"
    assert get_version("snap-skill", 99, history_dir=hdir) is None


def test_append_only_monotonic(tmp_path: Path) -> None:
    """The JSONL file grows by exactly one line per record_version call."""
    hdir = tmp_path / "history"

    for i in range(5):
        record_version("mono", f"v{i}", "agent", f"step {i}", history_dir=hdir)

    jsonl = list(hdir.glob("*.jsonl"))
    assert len(jsonl) == 1
    lines = [ln for ln in jsonl[0].read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 5


def test_list_versions_missing_skill_returns_empty(tmp_path: Path) -> None:
    """list_versions returns [] for a skill that has never been recorded."""
    hdir = tmp_path / "history"
    hdir.mkdir()
    assert list_versions("ghost-skill", history_dir=hdir) == []


def test_sha256_recorded(tmp_path: Path) -> None:
    """Each version record includes a non-empty sha256 hex digest."""
    import hashlib

    hdir = tmp_path / "history"
    content = "test content"
    record_version("sha-skill", content, "agent", "check hash", history_dir=hdir)

    versions = list_versions("sha-skill", history_dir=hdir)
    assert len(versions) == 1
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert versions[0]["sha256"] == expected


# ---------------------------------------------------------------------------
# config_loader validation tests
# ---------------------------------------------------------------------------


def _write_toml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_unknown_top_level_key_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An unknown top-level key in settings.toml produces a WARNING log."""
    import logging

    from hachi.core.config_loader import _read_toml

    settings = tmp_path / "settings.toml"
    _write_toml(settings, '[provider]\nkind = "anthropic"\n\n[zap_unknown]\nfoo = 1\n')

    with caplog.at_level(logging.WARNING, logger="hachi.core.config_loader"):
        result = _read_toml(settings)

    assert result  # parsed successfully
    assert any("unknown top-level key" in record.message for record in caplog.records)
    assert any("zap_unknown" in record.message for record in caplog.records)


def test_unknown_key_raises_in_strict_mode(tmp_path: Path) -> None:
    """An unknown top-level key raises ValueError when strict=True."""
    from hachi.core.config_loader import _read_toml

    settings = tmp_path / "settings.toml"
    _write_toml(settings, '[provider]\nkind = "anthropic"\n\n[bad_key]\nx = 1\n')

    with pytest.raises(ValueError, match="unknown top-level key"):
        _read_toml(settings, strict=True)


def test_unknown_key_raises_via_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HACHI_CONFIG_STRICT=1 triggers strict mode without passing strict=True."""
    from hachi.core.config_loader import _read_toml

    monkeypatch.setenv("HACHI_CONFIG_STRICT", "1")
    settings = tmp_path / "settings.toml"
    _write_toml(settings, '[provider]\nkind = "anthropic"\n\n[nope]\nx = 1\n')

    with pytest.raises(ValueError, match="unknown top-level key"):
        _read_toml(settings)


def test_malformed_toml_secondary_returns_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A malformed secondary config file returns {} and logs a warning (no crash)."""
    import logging

    from hachi.core.config_loader import _read_toml

    settings = tmp_path / "bad.toml"
    settings.write_text("[[[[not valid toml", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="hachi.core.config_loader"):
        result = _read_toml(settings, primary=False)

    assert result == {}
    assert any(
        "malformed" in r.message.lower() or "ignoring" in r.message.lower()
        for r in caplog.records
    )


def test_malformed_toml_primary_logs_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A malformed primary settings file logs an ERROR (not just WARNING)."""
    import logging

    from hachi.core.config_loader import _read_toml

    settings = tmp_path / "settings.toml"
    settings.write_text("not = [valid", encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="hachi.core.config_loader"):
        result = _read_toml(settings, primary=True)

    assert result == {}
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_malformed_toml_strict_raises(tmp_path: Path) -> None:
    """A malformed TOML file raises in strict mode."""
    from hachi.core.config_loader import _read_toml

    settings = tmp_path / "settings.toml"
    settings.write_text("not = [valid", encoding="utf-8")

    with pytest.raises(tomllib.TOMLDecodeError):
        _read_toml(settings, strict=True)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission check only")
def test_world_writable_settings_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A world-writable settings.toml produces a SECURITY warning on POSIX."""
    import logging

    from hachi.core.config_loader import _read_toml

    settings = tmp_path / "settings.toml"
    _write_toml(settings, '[provider]\nkind = "anthropic"\n')
    settings.chmod(0o646)  # world-writable

    with caplog.at_level(logging.WARNING, logger="hachi.core.config_loader"):
        _read_toml(settings)

    assert any(
        "world-writable" in r.message.lower() or "SECURITY" in r.message
        for r in caplog.records
    )

    settings.chmod(0o600)  # restore so cleanup doesn't fail on some systems


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission check only")
def test_world_writable_settings_raises_strict(tmp_path: Path) -> None:
    """A world-writable settings.toml raises PermissionError under strict mode."""

    from hachi.core.config_loader import _read_toml

    settings = tmp_path / "settings.toml"
    _write_toml(settings, '[provider]\nkind = "anthropic"\n')
    settings.chmod(0o646)

    with pytest.raises(PermissionError):
        _read_toml(settings, strict=True)

    settings.chmod(0o600)


# ---------------------------------------------------------------------------
# Atomic upsert smoke-test: no stray .og.tmp files after a successful write
# ---------------------------------------------------------------------------


def test_upsert_skill_no_stray_tmp_files(tmp_path: Path) -> None:
    """After upsert_skill succeeds, no .og.tmp file remains in the learned dir."""
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(tmp_path)  # prime with an empty skills dir

    engine.upsert_skill(
        name="atomic-test-skill",
        keywords=["atomic", "test"],
        dense="atomic | test | no-tmp",
        full="Full content for atomic test.",
        reason="ci smoke-test",
        skills_dir=tmp_path,
    )

    learned_dir = tmp_path / "learned"
    tmp_files = list(learned_dir.glob("*.og.tmp"))
    assert tmp_files == [], f"Stray temp files found: {tmp_files}"

    og_file = learned_dir / "atomic_test_skill.og"
    assert og_file.exists(), "Expected .og file was not written"


def test_upsert_skill_records_history(tmp_path: Path) -> None:
    """After upsert_skill, the version history has exactly one entry."""
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_directory(tmp_path)

    engine.upsert_skill(
        name="history-test-skill",
        keywords=["history"],
        dense="history | test",
        full="Testing history recording.",
        reason="initial creation",
        skills_dir=tmp_path,
    )

    versions = list_versions("history_test_skill", skills_dir=tmp_path)
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["author"] == "agent"
    assert "initial creation" in versions[0]["summary"]
