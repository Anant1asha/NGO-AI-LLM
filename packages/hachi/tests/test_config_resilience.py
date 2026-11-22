"""Tests for config robustness: malformed config falls back, writes are atomic."""

from __future__ import annotations

from pathlib import Path

from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.paths import HachiPaths


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def test_malformed_config_falls_back_to_defaults(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.global_config_toml.write_text("totally ][ not = valid toml", encoding="utf-8")

    # Must NOT raise — every command that loads config would otherwise crash.
    cfg = load_effective_config(paths=paths)
    assert cfg.provider.kind  # defaults are present


def test_write_global_config_is_atomic(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    cfg = load_effective_config(paths=paths)
    write_global_config(cfg, paths=paths)

    assert paths.global_config_toml.exists()
    # No leftover temp file from the atomic os.replace.
    tmp = paths.global_config_toml.with_name(f"{paths.global_config_toml.name}.tmp")
    assert not tmp.exists()
    # And the result is reloadable.
    assert load_effective_config(paths=paths).provider.kind == cfg.provider.kind
