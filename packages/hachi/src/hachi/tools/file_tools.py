"""LLM-callable file / attachment tools (Initiative E, Slice 2.4).

Registers four tools:

- ``attach_file``        — Ingest a local file path into the managed store.
- ``list_attachments``   — List all stored file attachments.
- ``read_attachment``    — Read extracted text from a stored attachment.
- ``search_attachments`` — Semantic search over extracted attachment content.

All tools are permission-gated (``PermissionGate``) like ``os_tools``.  The
``search_attachments`` tool indexes via the RRF fusion seam
(``memory_vault.py:785``) so results merge through ``semantic_search`` without
caller changes.

Design doc: docs/architecture/18-attachment-platform.md §5.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool JSON schemata
# ---------------------------------------------------------------------------

ATTACH_FILE_SCHEMA: dict[str, Any] = {
    "name": "attach_file",
    "description": (
        "Ingest a local file into the managed attachment store so it can be referenced "
        "in subsequent turns.  Returns the file's metadata including its unique file_id. "
        "Supported types: text, CSV, JSON, code, PDF (if pypdf installed), DOCX (if "
        "python-docx installed), XLSX (if openpyxl installed)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or home-relative path to the file to attach.",
            },
            "media_type": {
                "type": "string",
                "description": (
                    "MIME type override.  If omitted, inferred from the file extension."
                ),
            },
        },
        "required": ["path"],
    },
}

LIST_ATTACHMENTS_SCHEMA: dict[str, Any] = {
    "name": "list_attachments",
    "description": "List all files that have been attached in this session's store.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

READ_ATTACHMENT_SCHEMA: dict[str, Any] = {
    "name": "read_attachment",
    "description": (
        "Read the extracted text content of a previously attached file by its file_id. "
        "The text has been security-wrapped to prevent prompt injection."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The file_id returned by attach_file or list_attachments.",
            },
        },
        "required": ["file_id"],
    },
}

SEARCH_ATTACHMENTS_SCHEMA: dict[str, Any] = {
    "name": "search_attachments",
    "description": (
        "Semantic search over the content of all indexed file attachments.  Returns "
        "ranked excerpts from matching files.  Requires chromadb and at least one file "
        "to have been fully extracted (status='extracted' or 'indexed')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return (default 5, max 20).",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MIME_BY_SUFFIX: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".toml": "application/toml",
    ".py": "text/x-python",
    ".js": "text/x-javascript",
    ".ts": "text/x-typescript",
    ".java": "text/x-java-source",
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".rs": "text/x-rust",
    ".go": "text/x-go",
    ".rb": "text/x-ruby",
    ".sh": "text/x-shellscript",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
    ".htm": "text/html",
}


def _infer_media_type(path: Path) -> str:
    return _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")


def _get_pipeline() -> Any:
    """Lazily build a FilePipeline using paths from ``get_hachi_paths``."""
    from hachi.core.files.store import (
        FileMetaStore,
        FilePipeline,
        LocalStorageProvider,
        NoOpScanner,
    )
    from hachi.core.paths import get_hachi_paths

    paths = get_hachi_paths()
    meta_store = FileMetaStore(paths.files_db)
    storage = LocalStorageProvider(paths.blobs_dir)
    return FilePipeline(
        meta_store=meta_store,
        storage=storage,
        scanner=NoOpScanner(),
    )


def _get_store() -> Any:
    """Lazily open the FileMetaStore."""
    from hachi.core.files.store import FileMetaStore
    from hachi.core.paths import get_hachi_paths

    return FileMetaStore(get_hachi_paths().files_db)


def _get_storage() -> Any:
    """Lazily open the LocalStorageProvider."""
    from hachi.core.files.store import LocalStorageProvider
    from hachi.core.paths import get_hachi_paths

    return LocalStorageProvider(get_hachi_paths().blobs_dir)


# ---------------------------------------------------------------------------
# Tool implementation functions
# ---------------------------------------------------------------------------


def _attach_file(path: str, media_type: str | None = None, **_: Any) -> str:
    """Ingest *path* into the file store.

    Returns a JSON string with the FileMeta fields.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return json.dumps({"error": f"File not found: {path}"})
    if not p.is_file():
        return json.dumps({"error": f"Path is not a file: {path}"})

    mime = media_type or _infer_media_type(p)
    try:
        pipeline = _get_pipeline()
        with p.open("rb") as fh:
            meta = pipeline.ingest(name=p.name, media_type=mime, data=fh)
        return meta.model_dump_json()
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        logger.error("attach_file: unexpected error for %r — %s", path, exc, exc_info=True)
        return json.dumps({"error": f"Failed to attach file: {exc}"})


def _list_attachments(**_: Any) -> str:
    """Return a JSON array of all :class:`~hachi.core.files.store.FileMeta` records."""
    try:
        store = _get_store()
        metas = store.list_all()
        return json.dumps([m.model_dump() for m in metas])
    except Exception as exc:
        logger.error("list_attachments: error — %s", exc, exc_info=True)
        return json.dumps({"error": f"Failed to list attachments: {exc}"})


def _read_attachment(file_id: str, **_: Any) -> str:
    """Return extracted (guard_untrusted-wrapped) text for *file_id*."""
    # Reject path traversal.
    if "/" in file_id or "\\" in file_id or ".." in file_id:
        return json.dumps({"error": "Invalid file_id"})

    try:
        store = _get_store()
        meta = store.get(file_id)
        if meta is None:
            return json.dumps({"error": f"File not found: {file_id!r}"})
        if meta.status == "quarantined":
            return json.dumps({"error": "File is quarantined and cannot be read."})
        if meta.extracted_text_ref is None:
            return json.dumps(
                {
                    "status": meta.status,
                    "message": (
                        "Extracted text not yet available. "
                        f"Current status: {meta.status!r}. "
                        "Try again after extraction completes."
                    ),
                }
            )

        storage = _get_storage()
        with storage.open(meta.extracted_text_ref) as fh:
            text = fh.read().decode("utf-8", errors="replace")
        return json.dumps({"file_id": file_id, "name": meta.name, "text": text})
    except FileNotFoundError:
        return json.dumps({"error": f"Extracted text blob not found for {file_id!r}"})
    except Exception as exc:
        logger.error("read_attachment: error for %r — %s", file_id, exc, exc_info=True)
        return json.dumps({"error": f"Failed to read attachment: {exc}"})


def _search_attachments(query: str, top_k: int = 5, **_: Any) -> str:
    """Semantic search over the ``attachments`` Chroma collection."""
    top_k = min(max(int(top_k), 1), 20)
    try:
        import chromadb  # type: ignore[import-untyped]

        from hachi.core.paths import get_hachi_paths

        paths = get_hachi_paths()
        client = chromadb.PersistentClient(path=str(paths.chroma_dir / "attachments"))
        try:
            coll = client.get_collection("attachments")
        except Exception:
            return json.dumps({"results": [], "message": "No attachments indexed yet."})

        results = coll.query(query_texts=[query], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        out = []
        for doc, meta, dist in zip(docs, metas, distances, strict=False):
            out.append(
                {
                    "file_id": meta.get("file_id"),
                    "name": meta.get("name"),
                    "chunk": meta.get("chunk", 0),
                    "score": round(1.0 - float(dist), 4),
                    "excerpt": doc[:500] if doc else "",
                }
            )
        return json.dumps({"results": out})
    except ImportError:
        return json.dumps({"error": "chromadb not installed; search_attachments unavailable."})
    except Exception as exc:
        logger.error("search_attachments: error — %s", exc, exc_info=True)
        return json.dumps({"error": f"Search failed: {exc}"})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_file_tools(registry: Any, gate: Any) -> None:
    """Register file attachment tools into *registry*, gated by *gate*.

    Args:
        registry: :class:`~hachi.core.loop.ToolRegistry` instance.
        gate:     :class:`~hachi.core.permissions.PermissionGate` instance.
    """

    def _gated(fn: Any, action: str, resource_key: str = "path") -> Any:
        """Wrap *fn* with a permission gate check."""

        def _inner(**kwargs: Any) -> str:
            resource = kwargs.get(resource_key, "files")
            decision = gate.check_path(str(resource), action)
            if not decision.allowed:
                return json.dumps({"error": f"Permission denied: {decision.reason}"})
            return fn(**kwargs)

        _inner.__name__ = fn.__name__
        return _inner

    registry.register(
        ATTACH_FILE_SCHEMA,
        _gated(_attach_file, action="write", resource_key="path"),
        group="files",
    )
    registry.register(
        LIST_ATTACHMENTS_SCHEMA,
        _gated(_list_attachments, action="read", resource_key="path"),
        group="files",
    )
    registry.register(
        READ_ATTACHMENT_SCHEMA,
        _gated(_read_attachment, action="read", resource_key="file_id"),
        group="files",
    )
    registry.register(
        SEARCH_ATTACHMENTS_SCHEMA,
        _gated(_search_attachments, action="read", resource_key="query"),
        group="files",
    )
