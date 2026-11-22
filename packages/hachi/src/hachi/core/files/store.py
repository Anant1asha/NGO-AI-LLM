"""File / Attachment Platform — core store (Initiative E, Slice 2.4).

Implements:
- ``FileMeta``            — Pydantic model for file metadata.
- ``StorageProvider``     — Protocol: streaming put/open/delete.
- ``LocalStorageProvider``— Bytes under ``paths.blobs_dir``, atomic os.replace.
- ``ContentExtractor``    — Protocol: bytes → extracted text, per media type.
- ``TextExtractor``       — Zero-dep extractor for text/plain, text/csv, JSON, code.
- ``VirusScanHook``       — Protocol: scan before storage.
- ``NoOpScanner``         — Default allow-all scanner.
- ``ScanResult``          — Scan outcome dataclass.
- ``FileMetaStore``       — SQLite ``files`` table via ``apply_migrations``.
- ``FilePipeline``        — Orchestrates Validate → Scan → Store → emit file.uploaded.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from hachi.core.migrations import apply_migrations
from hachi.core.runtime_events import FILE_UPLOADED, RuntimeEvent, now_iso

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Size / type constants
# ---------------------------------------------------------------------------

# Hard upload ceiling — default 50 MB.  Overridden by FileSettings.max_size_bytes.
_DEFAULT_MAX_SIZE_BYTES: int = 50 * 1024 * 1024

# Media types that are trivially extractable by the zero-dep text extractor.
_TEXT_MEDIA_TYPES: frozenset[str] = frozenset(
    {
        "text/plain",
        "text/csv",
        "text/html",
        "text/markdown",
        "text/x-python",
        "text/x-javascript",
        "text/x-typescript",
        "text/x-java-source",
        "text/x-c",
        "text/x-c++",
        "text/x-ruby",
        "text/x-go",
        "text/x-rust",
        "text/x-shellscript",
        "application/json",
        "application/x-yaml",
        "application/yaml",
        "application/toml",
        "application/x-toml",
    }
)

# ---------------------------------------------------------------------------
# FileMeta
# ---------------------------------------------------------------------------

FileStatus = Literal[
    "received", "validated", "stored", "extracted", "indexed", "quarantined", "failed"
]


class FileMeta(BaseModel):
    """Metadata record for a managed file attachment.

    ``file_id`` is the SHA-256 hex-digest of the raw file bytes — identical
    content deduplicates automatically, mirroring the ``memory_vault`` fact-id
    convention.
    """

    model_config = ConfigDict(extra="ignore")

    file_id: str = Field(description="SHA-256 hex-digest of the raw bytes.")
    name: str = Field(description="Original filename supplied by the caller.")
    media_type: str = Field(description="MIME type (e.g. 'text/plain', 'application/pdf').")
    size: int = Field(description="File size in bytes.")
    status: FileStatus = Field(default="received")
    created_at: str = Field(default_factory=now_iso)
    extracted_text_ref: str | None = Field(
        default=None,
        description="Path to the extracted-text sidecar, relative to blobs_dir.",
    )


# ---------------------------------------------------------------------------
# ScanResult
# ---------------------------------------------------------------------------


@dataclass
class ScanResult:
    """Outcome of a virus/malware scan."""

    safe: bool
    threat: str | None = None
    scanner: str = "NoOpScanner"


# ---------------------------------------------------------------------------
# Protocol definitions
# ---------------------------------------------------------------------------


class StorageProvider(Protocol):
    """Where raw bytes live.  Implementations must be streaming-safe."""

    def put(self, file_id: str, data: IO[bytes]) -> None:
        """Write *data* stream under *file_id*.  Atomic where possible."""
        ...

    def open(self, file_id: str) -> IO[bytes]:
        """Return an open binary stream for *file_id*."""
        ...

    def delete(self, file_id: str) -> None:
        """Remove *file_id* from the store.  No-op if not present."""
        ...


class ContentExtractor(Protocol):
    """Convert binary file content to plain text."""

    def supports(self, media_type: str) -> bool:
        """Return True when this extractor handles *media_type*."""
        ...

    def extract(self, data: IO[bytes], media_type: str) -> str:
        """Read from *data* and return extracted plain text."""
        ...


class VirusScanHook(Protocol):
    """Security hook invoked before a file is stored."""

    def scan(self, file_id: str, data: IO[bytes]) -> ScanResult:
        """Scan *data* for threats; rewind the stream before returning."""
        ...


# ---------------------------------------------------------------------------
# LocalStorageProvider
# ---------------------------------------------------------------------------

_CHUNK = 64 * 1024  # 64 KB streaming chunk


class LocalStorageProvider:
    """Disk-backed blob store under ``blobs_dir``.

    Writes use the atomic temp-file + ``os.replace`` technique from
    :class:`~hachi.core.checkpoints.CheckpointManager` so a crash mid-write
    never leaves a corrupt partial file.
    """

    def __init__(self, blobs_dir: Path, max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES) -> None:
        """
        Args:
            blobs_dir:      Root directory for raw blobs.
            max_size_bytes: Hard cap on any single file (enforced in ``put``).
        """
        self._dir = blobs_dir
        self._max_size = max_size_bytes
        self._dir.mkdir(parents=True, exist_ok=True)

    def _blob_path(self, file_id: str) -> Path:
        """Resolve the on-disk path for *file_id*, rejecting path traversal."""
        # Strip any directory separators — file_id must be a flat hex string.
        safe = Path(file_id).name
        if safe != file_id or not safe:
            raise ValueError(f"Invalid file_id (path traversal rejected): {file_id!r}")
        return self._dir / safe

    def put(self, file_id: str, data: IO[bytes]) -> None:
        """Stream *data* to disk under *file_id*, atomically.

        Raises:
            ValueError: If *file_id* contains path-traversal sequences.
            OSError:    If the write fails.
        """
        dest = self._blob_path(file_id)
        self._dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=self._dir, prefix=".tmp_", delete=False, suffix=".part"
        ) as tmp:
            tmp_path = Path(tmp.name)
            written = 0
            while True:
                chunk = data.read(_CHUNK)
                if not chunk:
                    break
                if written + len(chunk) > self._max_size:
                    tmp_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"File exceeds maximum allowed size ({self._max_size} bytes)"
                    )
                tmp.write(chunk)
                written += len(chunk)
        os.replace(tmp_path, dest)
        logger.debug("LocalStorageProvider.put: %s (%d bytes)", file_id, written)

    def open(self, file_id: str) -> IO[bytes]:
        """Open *file_id* for streaming read.

        Raises:
            FileNotFoundError: If the blob does not exist.
            ValueError:        If *file_id* contains path-traversal sequences.
        """
        path = self._blob_path(file_id)
        return path.open("rb")

    def delete(self, file_id: str) -> None:
        """Remove *file_id*.  No-op if not present."""
        try:
            self._blob_path(file_id).unlink()
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# NoOpScanner
# ---------------------------------------------------------------------------


class NoOpScanner:
    """Default virus scanner — allows all files (interface only).

    A real ClamAV / cloud scanner is a drop-in replacement.
    """

    def scan(self, file_id: str, data: IO[bytes]) -> ScanResult:
        """Always return safe.  Stream position is NOT changed."""
        return ScanResult(safe=True, threat=None, scanner="NoOpScanner")


# ---------------------------------------------------------------------------
# TextExtractor (zero-dep)
# ---------------------------------------------------------------------------


class TextExtractor:
    """Zero-dependency content extractor for plain-text and JSON files.

    Supports: text/plain, text/csv, text/html, text/markdown, code files,
    application/json, application/x-yaml, application/toml, etc.
    """

    def supports(self, media_type: str) -> bool:
        """Return True for all media types handled without optional deps."""
        base = media_type.split(";")[0].strip().lower()
        return base in _TEXT_MEDIA_TYPES

    def extract(self, data: IO[bytes], media_type: str) -> str:
        """Decode bytes as UTF-8 (replacing errors) and return the text."""
        raw = data.read()
        return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Optional extractors (pypdf, python-docx, openpyxl)
# ---------------------------------------------------------------------------


def _build_extractor_chain() -> list[ContentExtractor]:
    """Build the extractor chain, registering optional deps when installed.

    Hard imports MUST NOT appear at module top; this function is only called
    at runtime, so a missing extra just omits the extractor gracefully.
    """
    chain: list[ContentExtractor] = [TextExtractor()]

    # --- pypdf (PDF) ---
    try:
        import pypdf  # noqa: PLC0415

        class _PdfExtractor:
            def supports(self, media_type: str) -> bool:
                return media_type.split(";")[0].strip().lower() == "application/pdf"

            def extract(self, data: IO[bytes], media_type: str) -> str:
                reader = pypdf.PdfReader(data)
                parts = []
                for page in reader.pages:
                    parts.append(page.extract_text() or "")
                return "\n".join(parts)

        chain.append(_PdfExtractor())
        logger.debug("FilePlatform: pypdf extractor registered")
    except ImportError:
        logger.debug("FilePlatform: pypdf not installed — PDF extraction unavailable")

    # --- python-docx (DOCX) ---
    try:
        import docx  # noqa: PLC0415

        class _DocxExtractor:
            def supports(self, media_type: str) -> bool:
                base = media_type.split(";")[0].strip().lower()
                return base in {
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/msword",
                }

            def extract(self, data: IO[bytes], media_type: str) -> str:
                doc = docx.Document(data)
                return "\n".join(p.text for p in doc.paragraphs)

        chain.append(_DocxExtractor())
        logger.debug("FilePlatform: python-docx extractor registered")
    except ImportError:
        logger.debug("FilePlatform: python-docx not installed — DOCX extraction unavailable")

    # --- openpyxl (XLSX) ---
    try:
        import openpyxl  # noqa: PLC0415

        class _XlsxExtractor:
            def supports(self, media_type: str) -> bool:
                base = media_type.split(";")[0].strip().lower()
                return base in {
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.ms-excel",
                }

            def extract(self, data: IO[bytes], media_type: str) -> str:
                wb = openpyxl.load_workbook(data, read_only=True, data_only=True)
                lines = []
                for ws in wb.worksheets:
                    lines.append(f"# Sheet: {ws.title}")
                    for row in ws.iter_rows(values_only=True):
                        lines.append("\t".join("" if v is None else str(v) for v in row))
                return "\n".join(lines)

        chain.append(_XlsxExtractor())
        logger.debug("FilePlatform: openpyxl extractor registered")
    except ImportError:
        logger.debug("FilePlatform: openpyxl not installed — XLSX extraction unavailable")

    return chain


def find_extractor(
    chain: list[ContentExtractor], media_type: str
) -> ContentExtractor | None:
    """Return the first extractor in *chain* that supports *media_type*."""
    base = media_type.split(";")[0].strip().lower()
    for ext in chain:
        if ext.supports(base):
            return ext
    return None


# ---------------------------------------------------------------------------
# FileMetaStore (SQLite)
# ---------------------------------------------------------------------------

_FILES_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file_id            TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    media_type         TEXT NOT NULL,
    size               INTEGER NOT NULL,
    status             TEXT NOT NULL DEFAULT 'received',
    created_at         TEXT NOT NULL,
    extracted_text_ref TEXT
)
"""

_FILES_MIGRATIONS: list[tuple[str, str]] = [
    # Future additive columns go here.
    # (column_name, "TYPE DEFAULT value")
]


class FileMetaStore:
    """SQLite-backed metadata store for the file attachment platform.

    Uses the shared :func:`~hachi.core.migrations.apply_migrations` helper so
    both fresh installs and upgrades receive the ``files`` table without an
    explicit migration version counter.
    """

    def __init__(self, db_path: Path) -> None:
        """
        Args:
            db_path: Path to the SQLite database file.  Created if absent.
        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        conn = self._connect()
        try:
            conn.execute(_FILES_SCHEMA)
            conn.commit()
            # Run additive migrations (idempotent at every boot).
            apply_migrations(conn, "files", _FILES_MIGRATIONS)
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, meta: FileMeta) -> None:
        """Insert or replace *meta* in the ``files`` table."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO files
                    (file_id, name, media_type, size, status, created_at, extracted_text_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meta.file_id,
                    meta.name,
                    meta.media_type,
                    meta.size,
                    meta.status,
                    meta.created_at,
                    meta.extracted_text_ref,
                ),
            )

    def get(self, file_id: str) -> FileMeta | None:
        """Return the :class:`FileMeta` for *file_id*, or ``None``."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE file_id = ?", (file_id,)
            ).fetchone()
        if row is None:
            return None
        return FileMeta(**dict(row))

    def list_all(self) -> list[FileMeta]:
        """Return all file records, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM files ORDER BY created_at DESC"
            ).fetchall()
        return [FileMeta(**dict(r)) for r in rows]

    def update_status(
        self,
        file_id: str,
        status: FileStatus,
        extracted_text_ref: str | None = None,
    ) -> None:
        """Update *status* (and optionally *extracted_text_ref*) for *file_id*."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE files
                SET status = ?, extracted_text_ref = COALESCE(?, extracted_text_ref)
                WHERE file_id = ?
                """,
                (status, extracted_text_ref, file_id),
            )


# ---------------------------------------------------------------------------
# FilePipeline
# ---------------------------------------------------------------------------


class FilePipeline:
    """Orchestrates the file ingest pipeline.

    Stages (inline): Validate → VirusScanHook → StorageProvider.put → FileMeta(stored)
                     → emit ``file.uploaded``.

    Heavy stages (extract, index) are dispatched as durable :class:`~hachi.jobs.Job`
    handlers via the ``JobRegistry`` reactive subscription on ``file.uploaded``.

    Args:
        meta_store:    Where FileMeta records are persisted.
        storage:       Where raw bytes live.
        scanner:       Virus/malware scan hook (default: :class:`NoOpScanner`).
        event_bus:     Optional :class:`~hachi.core.event_bus.EventBus` for reactive
                       ``file.uploaded`` dispatch.  When ``None``, reactive extraction
                       is skipped.
        allowed_types: Set of allowed MIME base types.  Empty = allow all.
        max_size_bytes: Hard size cap.  Default 50 MB.
    """

    def __init__(
        self,
        meta_store: FileMetaStore,
        storage: StorageProvider,
        *,
        scanner: VirusScanHook | None = None,
        event_bus: Any = None,
        allowed_types: set[str] | None = None,
        max_size_bytes: int = _DEFAULT_MAX_SIZE_BYTES,
    ) -> None:
        self._meta = meta_store
        self._storage = storage
        self._scanner = scanner or NoOpScanner()
        self._bus = event_bus
        self._allowed_types = allowed_types or set()
        self._max_size = max_size_bytes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sha256_stream(self, data: IO[bytes]) -> tuple[str, int, bytes]:
        """Hash *data* in streaming chunks.

        Returns (hex_digest, byte_count, raw_bytes).  This is the only place
        where bytes accumulate in memory — but we enforce the size cap here so
        unbounded files are rejected before growing large.
        """
        h = hashlib.sha256()
        size = 0
        buf = io.BytesIO()
        while True:
            chunk = data.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > self._max_size:
                raise ValueError(
                    f"File exceeds maximum allowed size ({self._max_size} bytes)"
                )
            h.update(chunk)
            buf.write(chunk)
        return h.hexdigest(), size, buf.getvalue()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def ingest(self, name: str, media_type: str, data: IO[bytes]) -> FileMeta:
        """Ingest a file through the pipeline and return its :class:`FileMeta`.

        Status transitions: received → validated → stored (inline).
        Extract/index transitions (extracted / indexed) happen reactively via
        the ``file.uploaded`` event → JobRegistry handler.

        Args:
            name:       Original filename.
            media_type: MIME type string (e.g. ``'text/plain'``).
            data:       Binary stream.  Need not be seekable; consumed once.

        Returns:
            The persisted :class:`FileMeta` at ``stored`` status.

        Raises:
            ValueError: Oversized file, disallowed media type, or path traversal
                        detected in the file_id.
        """
        base_type = media_type.split(";")[0].strip().lower()

        # 1. Type validation (before storage).
        if self._allowed_types and base_type not in self._allowed_types:
            raise ValueError(
                f"Media type not allowed: {base_type!r}. "
                f"Allowed: {sorted(self._allowed_types)}"
            )

        # 2. Hash + size check (streams once; size cap enforced in _sha256_stream).
        file_id, size, raw = self._sha256_stream(data)

        # 3. Build preliminary metadata at 'received'.
        meta = FileMeta(
            file_id=file_id,
            name=name,
            media_type=base_type,
            size=size,
            status="received",
        )
        self._meta.save(meta)

        # 4. Virus / malware scan.
        scan_stream = io.BytesIO(raw)
        result = self._scanner.scan(file_id, scan_stream)
        if not result.safe:
            meta = meta.model_copy(update={"status": "quarantined"})
            self._meta.save(meta)
            logger.warning(
                "FilePipeline: quarantined %r — threat=%r scanner=%r",
                file_id,
                result.threat,
                result.scanner,
            )
            return meta

        # 5. Store bytes atomically.
        self._meta.update_status(file_id, "validated")
        store_stream = io.BytesIO(raw)
        self._storage.put(file_id, store_stream)
        meta = meta.model_copy(update={"status": "stored"})
        self._meta.update_status(file_id, "stored")

        # 6. Emit file.uploaded (triggers reactive extraction via JobRegistry).
        if self._bus is not None:
            event = RuntimeEvent(
                name=FILE_UPLOADED,
                payload={
                    "file_id": file_id,
                    "name": name,
                    "media_type": base_type,
                    "size": size,
                },
                timestamp=now_iso(),
            )
            try:
                self._bus.publish(event)
            except Exception:
                logger.exception("FilePipeline: event bus publish failed for %r", file_id)

        logger.info(
            "FilePipeline.ingest: %r stored (file_id=%r size=%d media_type=%r)",
            name,
            file_id,
            size,
            base_type,
        )
        return meta
