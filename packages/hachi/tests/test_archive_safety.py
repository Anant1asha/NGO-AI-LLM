"""Regression tests for archive path-traversal and tar-bomb protection.

ADV-010 / ADV-025 / UAT meta-risk MR-4.

These tests exercise the MANUAL guards in ``safe_extract`` directly.  They do
NOT rely on the Python 3.12+ ``data_filter`` default — every assertion targets
the hand-written member validation code, so the suite is safe on 3.11–3.14.
"""

from __future__ import annotations

import io
import os
import tarfile
from pathlib import Path

import pytest

from hachi.core.archive_safety import ArchiveSecurityError, safe_extract

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tar(members: list[tuple[str, bytes, int | None]]) -> tarfile.TarFile:
    """Build an in-memory TarFile from a list of (name, content, tarfile_type) tuples.

    tarfile_type defaults to tarfile.REGTYPE when None.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content, ttype in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.type = ttype if ttype is not None else tarfile.REGTYPE
            tf.addfile(info, io.BytesIO(content))
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r:gz")


def _make_safe_tar(files: dict[str, str]) -> tarfile.TarFile:
    """Build an in-memory TarFile with normal regular-file members."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in files.items():
            raw = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(raw)
            tf.addfile(info, io.BytesIO(raw))
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r:gz")


# ---------------------------------------------------------------------------
# 1. Path traversal — dot-dot member
# ---------------------------------------------------------------------------


def test_dotdot_traversal_raises(tmp_path: Path) -> None:
    """A member with '../../evil.og' must be rejected before any file is written."""
    dest = tmp_path / "dest"
    dest.mkdir()
    evil_outside = tmp_path / "evil.og"

    with _make_tar([("../../evil.og", b"pwned", None)]) as tf:
        with pytest.raises(ArchiveSecurityError, match=r"\.\."):
            safe_extract(tf, dest)

    # No file must have been created outside dest.
    assert not evil_outside.exists(), "Traversal attack succeeded — file escaped dest!"
    assert list(dest.rglob("*")) == [], "No files should be written on attack."


# ---------------------------------------------------------------------------
# 2. Path traversal — absolute path member
# ---------------------------------------------------------------------------


def test_absolute_path_member_raises(tmp_path: Path) -> None:
    """A member with an absolute path must be rejected."""
    dest = tmp_path / "dest"
    dest.mkdir()

    # Use a platform-appropriate absolute path name in the tarball.
    abs_name = "/tmp/evil" if os.name != "nt" else "C:\\evil"

    with _make_tar([(abs_name, b"pwned", None)]) as tf:
        with pytest.raises(ArchiveSecurityError, match="absolute"):
            safe_extract(tf, dest)

    assert list(dest.rglob("*")) == []


# ---------------------------------------------------------------------------
# 3. Symlink member rejected
# ---------------------------------------------------------------------------


def test_symlink_member_raises(tmp_path: Path) -> None:
    """A symlink member must be rejected."""
    dest = tmp_path / "dest"
    dest.mkdir()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="link_to_evil")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        info.size = 0
        tf.addfile(info, io.BytesIO(b""))
    buf.seek(0)

    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        with pytest.raises(ArchiveSecurityError, match="symlink"):
            safe_extract(tf, dest)

    assert list(dest.rglob("*")) == []


# ---------------------------------------------------------------------------
# 4. Tar-bomb: too many members
# ---------------------------------------------------------------------------


def test_tar_bomb_file_count_raises(tmp_path: Path) -> None:
    """An archive exceeding max_files must be rejected (tar-bomb guard)."""
    dest = tmp_path / "dest"
    dest.mkdir()

    # Build a tar with 5 tiny files but set max_files=3.
    files = {f"file_{i}.og": f"content {i}" for i in range(5)}
    with _make_safe_tar(files) as tf:
        with pytest.raises(ArchiveSecurityError, match="member count"):
            safe_extract(tf, dest, max_files=3)

    # At most max_files files should have been written before the abort.
    written = list(dest.rglob("*"))
    assert len(written) < 5, "Extraction should have been aborted before all files were written."


# ---------------------------------------------------------------------------
# 5. Normal (safe) archive extracts correctly
# ---------------------------------------------------------------------------


def test_safe_archive_extracts(tmp_path: Path) -> None:
    """A well-formed archive with no traversal extracts all files intact."""
    dest = tmp_path / "dest"
    dest.mkdir()

    files = {
        "skill_a.og": "::node[skill_a]\n->[:keywords=a]\n",
        "subdir/skill_b.og": "::node[skill_b]\n->[:keywords=b]\n",
        "pack.toml": '[pack]\nid = "test"\n',
    }

    with _make_safe_tar(files) as tf:
        safe_extract(tf, dest)

    assert (dest / "skill_a.og").read_text(encoding="utf-8") == files["skill_a.og"]
    expected_b = files["subdir/skill_b.og"]
    assert (dest / "subdir" / "skill_b.og").read_text(encoding="utf-8") == expected_b
    assert (dest / "pack.toml").read_text(encoding="utf-8") == files["pack.toml"]


# ---------------------------------------------------------------------------
# 6. Resolved-path escape via deceptive relative name
# ---------------------------------------------------------------------------


def test_resolved_escape_via_relative_name_raises(tmp_path: Path) -> None:
    """A member whose resolved path escapes dest (e.g. via a crafted name) is rejected."""
    dest = tmp_path / "dest"
    dest.mkdir()

    # Construct a name that after joining with dest resolves outside it.
    # e.g.  dest / "a/../../../evil"  resolves above tmp_path on any OS.
    with _make_tar([("a/../../../evil_escape.og", b"pwned", None)]) as tf:
        with pytest.raises(ArchiveSecurityError):
            safe_extract(tf, dest)

    # Confirm nothing was written.
    assert list(dest.rglob("*")) == []
    evil = tmp_path.parent / "evil_escape.og"
    assert not evil.exists()


# ---------------------------------------------------------------------------
# 7. Tar-bomb: byte-size limit
# ---------------------------------------------------------------------------


def test_tar_bomb_byte_limit_raises(tmp_path: Path) -> None:
    """An archive whose cumulative size exceeds max_total_bytes must be rejected."""
    dest = tmp_path / "dest"
    dest.mkdir()

    # 3 files × 100 bytes = 300 bytes; set limit to 150 bytes.
    files = {f"f{i}.og": "x" * 100 for i in range(3)}
    with _make_safe_tar(files) as tf:
        with pytest.raises(ArchiveSecurityError, match="cumulative size"):
            safe_extract(tf, dest, max_total_bytes=150)
