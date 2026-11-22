"""Tests for the permissions-path editor (exact-token matching, not substring)."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from hachi.cli import main as cli_main


def _write_perms(tmp_path: Path, value: str) -> Path:
    pfile = tmp_path / "device-permissions.og"
    pfile.write_text(f"allowed_paths={value}\n", encoding="utf-8")
    return pfile


def test_substring_path_is_not_falsely_deduped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "show_current_permissions", lambda _c: None)
    abc = tmp_path / "abc"
    ab = tmp_path / "ab"
    abc.mkdir()
    ab.mkdir()
    pfile = _write_perms(tmp_path, str(abc.resolve()))

    # 'ab' is a path-prefix substring of 'abc' — must still be added.
    cli_main._modify_permissions_path(pfile, "allowed_paths", str(ab), "add", Console())

    tokens = [
        t.strip()
        for t in pfile.read_text(encoding="utf-8").split("allowed_paths=", 1)[1].split(",")
    ]
    assert str(abc.resolve()) in tokens
    assert str(ab.resolve()) in tokens


def test_exact_duplicate_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "show_current_permissions", lambda _c: None)
    d = tmp_path / "d"
    d.mkdir()
    pfile = _write_perms(tmp_path, str(d.resolve()))

    cli_main._modify_permissions_path(pfile, "allowed_paths", str(d), "add", Console())
    content = pfile.read_text(encoding="utf-8")
    assert content.count(str(d.resolve())) == 1  # not duplicated
