"""Regression tests for BB-51: JSON state stores must not self-wipe on a torn
write, and a corrupt read must not cascade into an overwrite of good data.

Covers the shared :func:`hachi.core.atomic_io.atomic_write_json` /
:func:`hachi.core.atomic_io.quarantine_corrupt_file` helpers and their use at
every JSON-state write site: ``secret_store.py``'s ``_MetadataStore`` and
``EncryptedFileSecretStore``, ``onboarding.py``'s ``OnboardingService``, and
the OG engine's skill-usage tracker.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hachi.core.atomic_io import atomic_write_json, quarantine_corrupt_file
from hachi.core.onboarding import OnboardingService, OnboardingState
from hachi.core.paths import HachiPaths
from hachi.core.secret_store import EncryptedFileSecretStore, _MetadataStore
from hachi.og_engine.engine import SkillEngine


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


# ---------------------------------------------------------------------------
# atomic_write_json — unit tests
# ---------------------------------------------------------------------------


class TestAtomicWriteJson:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        atomic_write_json(target, {"a": 1})
        assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "state.json"
        atomic_write_json(target, {"a": 1})
        assert target.exists()

    def test_crash_mid_write_leaves_original_file_intact(self, tmp_path: Path) -> None:
        """The key regression: simulate a crash/kill during the write step and
        confirm the ORIGINAL file survives untouched (proving the write went to
        a temp file first, not in-place)."""
        target = tmp_path / "state.json"
        target.write_text(json.dumps({"good": "data"}), encoding="utf-8")

        with patch("os.replace", side_effect=OSError("simulated crash mid-write")):
            with pytest.raises(OSError):
                atomic_write_json(target, {"bad": "new"})

        # Original file must be untouched — the crash happened before the
        # atomic rename, so the old good data must still be there.
        assert json.loads(target.read_text(encoding="utf-8")) == {"good": "data"}

    def test_no_leftover_tmp_file_after_crash(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        target.write_text(json.dumps({"good": "data"}), encoding="utf-8")

        with patch("os.replace", side_effect=OSError("simulated crash mid-write")):
            with pytest.raises(OSError):
                atomic_write_json(target, {"bad": "new"})

        leftovers = list(tmp_path.glob(".*state.json*.tmp"))
        assert leftovers == []


# ---------------------------------------------------------------------------
# quarantine_corrupt_file
# ---------------------------------------------------------------------------


class TestQuarantineCorruptFile:
    def test_quarantines_unparseable_file(self, tmp_path: Path) -> None:
        target = tmp_path / "state.json"
        target.write_text("{not-valid-json", encoding="utf-8")

        result = quarantine_corrupt_file(target)

        assert result is not None
        assert not target.exists()
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "{not-valid-json"
        assert ".corrupt-" in result.name

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        target = tmp_path / "does_not_exist.json"
        assert quarantine_corrupt_file(target) is None


# ---------------------------------------------------------------------------
# secret_store.py: _MetadataStore — self-wipe regression
# ---------------------------------------------------------------------------


class TestMetadataStoreSelfWipe:
    def test_corrupt_read_does_not_get_silently_clobbered_by_next_write(
        self, tmp_path: Path
    ) -> None:
        """BB-51 core regression: a corrupt metadata file must be preserved
        (quarantined), not silently overwritten with empty state on the very
        next write that happens to follow a corrupt read."""
        metadata_path = tmp_path / "secrets_metadata.json"
        original_good_content = json.dumps(
            {"slack.bot_token": {"name": "slack.bot_token", "backend": "keyring"}}
        )
        # Simulate a torn write from a prior crash: valid JSON prefix, cut off.
        metadata_path.write_text(
            original_good_content[: len(original_good_content) // 2], encoding="utf-8"
        )

        store = _MetadataStore(metadata_path)
        # A read against the corrupt file (e.g. via `all()`) must quarantine it.
        assert store.all() == []

        # The corrupt content must still exist somewhere on disk (quarantined),
        # not have been overwritten with `{}` by the read-triggered load.
        corrupt_backups = list(tmp_path.glob("secrets_metadata.json.corrupt-*"))
        assert len(corrupt_backups) == 1
        assert (
            corrupt_backups[0].read_text(encoding="utf-8")
            == (original_good_content[: len(original_good_content) // 2])
        )

    def test_write_after_crash_is_atomic(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "secrets_metadata.json"
        store = _MetadataStore(metadata_path)
        store.upsert("token.one", {"name": "token.one", "backend": "keyring"})

        with patch("os.replace", side_effect=OSError("simulated crash")):
            with pytest.raises(OSError):
                store.upsert("token.two", {"name": "token.two", "backend": "keyring"})

        # Original write (token.one) must survive a crash during the second write.
        rows = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert "token.one" in rows
        assert "token.two" not in rows


# ---------------------------------------------------------------------------
# secret_store.py: EncryptedFileSecretStore — self-wipe regression
# ---------------------------------------------------------------------------


class TestEncryptedFileSecretStoreSelfWipe:
    def test_corrupt_blob_is_quarantined_not_silently_clobbered(self, tmp_path: Path) -> None:
        file_path = tmp_path / "secrets.enc"
        file_path.write_text("{not-valid-json-at-all", encoding="utf-8")

        store = EncryptedFileSecretStore(file_path=file_path, passphrase="test-pass")
        # Triggers _read_blob() -> parse error path.
        assert store.get("anything") is None

        corrupt_backups = list(tmp_path.glob("secrets.enc.corrupt-*"))
        assert len(corrupt_backups) == 1

    def test_write_after_crash_leaves_previous_secret_intact(self, tmp_path: Path) -> None:
        file_path = tmp_path / "secrets.enc"
        store = EncryptedFileSecretStore(file_path=file_path, passphrase="test-pass")
        store.set("api.key", "first-value")

        with patch("os.replace", side_effect=OSError("simulated crash")):
            with pytest.raises(OSError):
                store.set("api.key", "second-value")

        # Re-read must still find the first value — a torn write must not
        # have replaced the file with a half-written / empty blob.
        assert store.get("api.key") == "first-value"


# ---------------------------------------------------------------------------
# onboarding.py: OnboardingService — self-wipe regression
# ---------------------------------------------------------------------------


class TestOnboardingStateSelfWipe:
    def test_corrupt_state_is_quarantined_not_silently_clobbered(self, tmp_path: Path) -> None:
        paths = _paths(tmp_path)
        paths.state_dir.mkdir(parents=True, exist_ok=True)
        paths.onboarding_state_file.write_text("{not-valid-json", encoding="utf-8")

        service = OnboardingService(paths=paths)
        state = service.resume_state()
        assert state == OnboardingState()

        corrupt_backups = list(paths.state_dir.glob("onboarding_state.json.corrupt-*"))
        assert len(corrupt_backups) == 1

    def test_write_after_crash_leaves_previous_state_intact(self, tmp_path: Path) -> None:
        paths = _paths(tmp_path)
        service = OnboardingService(paths=paths)

        good_state = OnboardingState(selected_tier="recommended", completed_steps=["provider"])
        service.save_state(good_state)

        bad_state = OnboardingState(selected_tier="power", completed_steps=["provider", "safety"])
        with patch("os.replace", side_effect=OSError("simulated crash")):
            with pytest.raises(OSError):
                service.save_state(bad_state)

        reloaded = service.resume_state()
        assert reloaded.selected_tier == "recommended"
        assert reloaded.completed_steps == ["provider"]


# ---------------------------------------------------------------------------
# og_engine/engine.py: skill_usage.json — self-wipe regression
# ---------------------------------------------------------------------------


class TestSkillUsageSelfWipe:
    def test_corrupt_usage_db_is_quarantined_not_silently_clobbered(self, tmp_path: Path) -> None:
        usage_path = tmp_path / "skill_usage.json"
        usage_path.write_text("{not-valid-json", encoding="utf-8")

        engine = SkillEngine()
        engine._usage_path = usage_path
        engine._usage = engine._load_usage()
        assert engine._usage == {}

        corrupt_backups = list(tmp_path.glob("skill_usage.json.corrupt-*"))
        assert len(corrupt_backups) == 1

    def test_write_after_crash_leaves_previous_usage_intact(self, tmp_path: Path) -> None:
        usage_path = tmp_path / "skill_usage.json"
        engine = SkillEngine()
        engine._usage_path = usage_path
        engine._usage = {"skill.one": {"use_count": 3}}
        engine._save_usage()

        engine._usage = {"skill.one": {"use_count": 3}, "skill.two": {"use_count": 1}}
        with patch("os.replace", side_effect=OSError("simulated crash")):
            engine._save_usage()  # must not raise — best-effort persist, but must not corrupt

        on_disk = json.loads(usage_path.read_text(encoding="utf-8"))
        assert on_disk == {"skill.one": {"use_count": 3}}
