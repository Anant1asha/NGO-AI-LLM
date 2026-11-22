"""Safe tar archive extraction — path traversal and tar-bomb protection.

These guards are version-independent: they perform explicit member checks so
the protection is identical on Python 3.11, 3.12, and 3.14 regardless of
whether the interpreter's default ``extractall`` filter has been updated.

ADV-010 / ADV-025 remediation (UAT meta-risk MR-4).
"""

from __future__ import annotations

import os
import tarfile
from pathlib import Path

__all__ = [
    "ArchiveSecurityError",
    "safe_extract",
    "safe_extract_path",
]


class ArchiveSecurityError(Exception):
    """Raised when a tar archive member fails security validation."""


def safe_extract(
    tar: tarfile.TarFile,
    dest: Path,
    *,
    max_files: int = 10_000,
    max_total_bytes: int = 500 * 1024 * 1024,
) -> None:
    """Extract *tar* into *dest*, rejecting any unsafe member.

    This function is **version-independent**: it does not rely on the Python
    3.12+ ``filter`` parameter to ``extractall`` and is safe on 3.11+.

    Each member is validated before extraction.  The entire extraction is
    aborted (nothing further extracted) on the first violation.

    Args:
        tar:             Open :class:`tarfile.TarFile` to extract.
        dest:            Destination directory (must already exist or be
                         created by the caller).
        max_files:       Maximum number of members allowed (tar-bomb guard).
        max_total_bytes: Maximum cumulative uncompressed bytes allowed
                         (tar-bomb guard).

    Raises:
        ArchiveSecurityError: On any security violation — path traversal,
            dangerous member type, or resource-limit breach.
    """
    dest_resolved = dest.resolve()
    total_bytes = 0

    members = tar.getmembers()

    for idx, member in enumerate(members):
        # --- Tar-bomb: member count ---
        if idx >= max_files:
            raise ArchiveSecurityError(
                f"Archive exceeds maximum member count ({max_files}). "
                "Extraction aborted to prevent tar-bomb."
            )

        # --- Tar-bomb: cumulative size ---
        total_bytes += member.size
        if total_bytes > max_total_bytes:
            raise ArchiveSecurityError(
                f"Archive cumulative size exceeds {max_total_bytes} bytes. "
                "Extraction aborted to prevent tar-bomb."
            )

        # --- Path traversal: absolute path ---
        if os.path.isabs(member.name):
            raise ArchiveSecurityError(
                f"Archive member has absolute path: {member.name!r}. Extraction aborted."
            )

        # --- Path traversal: dot-dot component ---
        # Split on both POSIX and Windows separators for robustness.
        parts = member.name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ArchiveSecurityError(
                f"Archive member contains '..' component: {member.name!r}. Extraction aborted."
            )

        # --- Path traversal: resolved destination escape ---
        candidate = (dest / member.name).resolve()
        try:
            # Path.is_relative_to is available in Python 3.9+.
            within_dest = candidate.is_relative_to(dest_resolved)
        except AttributeError:  # pragma: no cover — only 3.8
            within_dest = os.path.commonpath([dest_resolved, candidate]) == str(dest_resolved)

        if not within_dest:
            raise ArchiveSecurityError(
                f"Archive member {member.name!r} would escape destination "
                f"directory {dest_resolved}. Extraction aborted."
            )

        # --- Dangerous member types ---
        # Only regular files and directories are permitted.
        if member.issym():
            raise ArchiveSecurityError(
                f"Archive member {member.name!r} is a symlink. Extraction aborted."
            )
        if member.islnk():
            raise ArchiveSecurityError(
                f"Archive member {member.name!r} is a hardlink. Extraction aborted."
            )
        if member.ischr():
            raise ArchiveSecurityError(
                f"Archive member {member.name!r} is a character device. Extraction aborted."
            )
        if member.isblk():
            raise ArchiveSecurityError(
                f"Archive member {member.name!r} is a block device. Extraction aborted."
            )
        if member.isfifo():
            raise ArchiveSecurityError(
                f"Archive member {member.name!r} is a FIFO/named pipe. Extraction aborted."
            )

        # --- Extract the validated member ---
        # As defence-in-depth, pass filter="data" where available (3.12+),
        # but the manual checks above are the primary protection.
        try:
            tar.extract(member, path=dest, filter="data")  # type: ignore[call-arg]
        except TypeError:
            # Python < 3.12: filter keyword not supported.
            tar.extract(member, path=dest)  # noqa: S202


def safe_extract_path(archive_path: Path, dest: Path, **caps: object) -> None:
    """Open *archive_path* and call :func:`safe_extract` with *dest* and *caps*.

    Args:
        archive_path: Path to the tar archive (any compression supported by
                      ``tarfile.open`` with ``"r:*"``).
        dest:         Destination directory for extraction.
        **caps:       Forwarded to :func:`safe_extract` (``max_files``,
                      ``max_total_bytes``).

    Raises:
        ArchiveSecurityError: On any security violation in the archive.
        tarfile.TarError:     On a corrupt or unreadable archive.
    """
    with tarfile.open(archive_path, "r:*") as tf:
        safe_extract(tf, dest, **caps)  # type: ignore[arg-type]
