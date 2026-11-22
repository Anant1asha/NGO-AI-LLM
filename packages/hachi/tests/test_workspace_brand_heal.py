"""Tests for the legacy-brand self-heal migration in workspace.py.

Covers _heal_legacy_brand() and its integration into ensure_workspace().
"""
from __future__ import annotations

from pathlib import Path

from hachi.gateway.workspace import _heal_legacy_brand

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_LEGACY_CONTENT = """\
# ============================================================
#  TOKOBOROS — Core Agent Brain
#  The identity, rules, and decision framework of the orchestrator.
# ============================================================
::node[identity]
->[:role=persona]
::dense
You are Tokoboros, an elite autonomous orchestrator agent.
"""

_HACHI_CONTENT = """\
# ============================================================
#  HACHI — Core Agent Brain
#  The identity, rules, and decision framework of the orchestrator.
# ============================================================
::node[identity]
->[:role=persona]
::dense
You are Hachi, an elite autonomous orchestrator agent.
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# _heal_legacy_brand unit tests
# ---------------------------------------------------------------------------


def test_heal_migrates_legacy_brain(tmp_path: Path) -> None:
    """A brain.og containing 'Tokoboros' is replaced and a .legacy-bak is created."""
    brain = tmp_path / "brain.og"
    bundled = tmp_path / "bundled_brain.og"
    _write(brain, _LEGACY_CONTENT)
    _write(bundled, _HACHI_CONTENT)

    result = _heal_legacy_brand(brain, bundled)

    assert result is True, "_heal_legacy_brand should return True when it migrates"
    assert "tokoboros" not in brain.read_text(encoding="utf-8").lower()
    assert "hachi" in brain.read_text(encoding="utf-8").lower()
    bak = brain.with_suffix(brain.suffix + ".legacy-bak")
    assert bak.exists(), ".legacy-bak backup file should be created"
    assert "tokoboros" in bak.read_text(encoding="utf-8").lower()


def test_heal_leaves_clean_brain_untouched(tmp_path: Path) -> None:
    """A brain.og that already uses Hachi is not modified."""
    brain = tmp_path / "brain.og"
    bundled = tmp_path / "bundled_brain.og"
    _write(brain, _HACHI_CONTENT)
    _write(bundled, _HACHI_CONTENT)

    result = _heal_legacy_brand(brain, bundled)

    assert result is False, "_heal_legacy_brand should return False for a clean file"
    bak = brain.with_suffix(brain.suffix + ".legacy-bak")
    assert not bak.exists(), "No backup should be created for an already-clean file"


def test_heal_skips_when_brain_absent(tmp_path: Path) -> None:
    """Returns False gracefully when the local brain.og does not exist."""
    brain = tmp_path / "brain.og"
    bundled = tmp_path / "bundled_brain.og"
    _write(bundled, _HACHI_CONTENT)

    result = _heal_legacy_brand(brain, bundled)

    assert result is False


def test_heal_skips_when_bundled_absent(tmp_path: Path) -> None:
    """Returns False gracefully when the bundled default does not exist."""
    brain = tmp_path / "brain.og"
    bundled = tmp_path / "bundled_brain.og"
    _write(brain, _LEGACY_CONTENT)

    result = _heal_legacy_brand(brain, bundled)

    assert result is False


def test_heal_does_not_overwrite_existing_bak(tmp_path: Path) -> None:
    """An existing .legacy-bak is never overwritten (idempotent repeated calls)."""
    brain = tmp_path / "brain.og"
    bundled = tmp_path / "bundled_brain.og"
    bak = brain.with_suffix(brain.suffix + ".legacy-bak")

    _write(brain, _LEGACY_CONTENT)
    _write(bundled, _HACHI_CONTENT)
    _write(bak, "# original backup content\n")

    result = _heal_legacy_brand(brain, bundled)

    assert result is True
    # The pre-existing backup must not have been overwritten
    assert "original backup content" in bak.read_text(encoding="utf-8")


def test_heal_case_insensitive_detection(tmp_path: Path) -> None:
    """Detection is case-insensitive (e.g. 'TOKOBOROS' uppercase triggers heal)."""
    brain = tmp_path / "brain.og"
    bundled = tmp_path / "bundled_brain.og"
    _write(brain, _LEGACY_CONTENT.replace("Tokoboros", "TOKOBOROS"))
    _write(bundled, _HACHI_CONTENT)

    result = _heal_legacy_brand(brain, bundled)

    assert result is True


# ---------------------------------------------------------------------------
# Integration test: ensure_workspace() calls _heal_legacy_brand
# ---------------------------------------------------------------------------


def test_ensure_workspace_heals_legacy_brain(tmp_path: Path, monkeypatch) -> None:
    """ensure_workspace() migrates a pre-rename brain.og in the config dir."""
    import hachi.gateway.workspace as ws_mod
    from hachi.core.paths import HachiPaths

    # Build a fake HachiPaths pointing at tmp_path.
    # HachiPaths.skills_dir is data_dir / "skills", so create that directory.
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    skills_dir = data_dir / "skills"
    config_dir.mkdir(parents=True)
    skills_dir.mkdir(parents=True)

    # Place a sentinel file in skills_dir so iterdir() is not empty (skips pack install)
    (skills_dir / "dummy.og").write_text("::meta\n", encoding="utf-8")

    mock_paths = HachiPaths(
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )

    # Write a legacy brain.og into the config dir
    brain_file = config_dir / "brain.og"
    brain_file.write_text(_LEGACY_CONTENT, encoding="utf-8")

    # Stub out get_hachi_paths and the helpers that touch the real filesystem
    monkeypatch.setattr(ws_mod, "get_hachi_paths", lambda: mock_paths)
    monkeypatch.setattr(ws_mod, "ensure_directories", lambda p: None)
    monkeypatch.setattr(ws_mod, "write_global_config", lambda cfg, paths: None)
    monkeypatch.setattr(ws_mod, "load_effective_config", lambda paths=None: _FakeConfig())

    ws_mod.ensure_workspace()

    healed_text = brain_file.read_text(encoding="utf-8")
    assert "tokoboros" not in healed_text.lower(), (
        "ensure_workspace() must heal a brain.og that still contains the legacy brand"
    )
    bak = brain_file.with_suffix(brain_file.suffix + ".legacy-bak")
    assert bak.exists(), ".legacy-bak must be created by ensure_workspace()"


class _FakeConfig:
    """Minimal stub so write_global_config monkeypatch is never actually called."""

    def model_dump(self, **kwargs):  # noqa: ANN201
        return {}
