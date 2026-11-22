"""Durable job handlers for background work (Initiative D — JobRegistry activation).

Handlers are registered under stable names so jobs survive process restarts.
Each handler receives keyword arguments from the serialisable payload dict
(no live closures).

JobContext is a lightweight service locator rebuilt from the payload for each
handler invocation — avoiding closure capture of live runtime state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class JobContext:
    """Service locator for durable job handlers.

    Built from a serialisable ``{session_id, ...}`` payload so handlers can
    reconstruct all necessary services without live closure capture.
    """

    session_id: str | None = None
    # Lazily resolved services — populated by build_job_context
    vault: Any = None
    memory_manager: Any = None
    # P1-5: LLM client reconstructed from config for durable fact-extraction.
    llm_client: Any = None
    # P1-5: MemoryWriter reconstructed from paths for the M1 typed-node path.
    memory_writer: Any = None


def build_job_context(
    payload: dict[str, Any],
    *,
    _llm_client_factory: Any = None,
    _vault_factory: Any = None,
    _memory_writer_factory: Any = None,
) -> JobContext:
    """Reconstruct a JobContext from a serialisable payload dict.

    Imports are deferred to avoid circular dependencies at module load time.
    Services that are unavailable (e.g., vault not configured, API key missing)
    are left as None — handlers are expected to guard against None.

    The ``_llm_client_factory``, ``_vault_factory``, and ``_memory_writer_factory``
    keyword arguments are injection points for tests.  When provided they are called
    with no arguments and their return value is used instead of the real service.
    This avoids monkeypatching module globals and keeps tests hermetic.

    Args:
        payload:                 Serialisable job payload dict (``session_id``, etc.).
        _llm_client_factory:     Optional 0-arg callable that returns a fake LLM client.
        _vault_factory:          Optional 0-arg callable that returns a fake vault.
        _memory_writer_factory:  Optional 0-arg callable that returns a fake MemoryWriter.

    Returns:
        A populated :class:`JobContext` (any unresolvable services remain ``None``).
    """
    session_id = payload.get("session_id")
    ctx = JobContext(session_id=session_id)

    # --- vault ---
    if _vault_factory is not None:
        try:
            ctx.vault = _vault_factory()
        except Exception:
            logger.debug("build_job_context: injected vault factory failed")
    else:
        try:
            from hachi.core.memory_vault import get_memory_vault

            ctx.vault = get_memory_vault()
        except Exception:
            logger.debug("build_job_context: memory vault not available")

    # --- LLM client (P1-5) ---
    # Reconstructed from app config so fact-extraction survives a restart.
    # Uses the same module-level shared client that MemoryVault already uses
    # (memory_vault._get_llm_client), which is stateless and safe to call from any
    # process that has ANTHROPIC_API_KEY in its environment.
    if _llm_client_factory is not None:
        try:
            ctx.llm_client = _llm_client_factory()
        except Exception:
            logger.debug("build_job_context: injected LLM client factory failed")
    else:
        try:
            from hachi.core.memory_vault import _get_llm_client

            ctx.llm_client = _get_llm_client()
        except Exception:
            logger.debug("build_job_context: LLM client not available")

    # --- MemoryWriter for the M1 typed path (P1-5) ---
    # Only constructed when the caller signals typed=True in the payload, because
    # MemoryWriter opens .og files on disk and is non-trivial to build.
    typed = bool(payload.get("typed"))
    if typed:
        if _memory_writer_factory is not None:
            try:
                ctx.memory_writer = _memory_writer_factory()
            except Exception:
                logger.debug("build_job_context: injected MemoryWriter factory failed")
        else:
            try:
                from hachi.core.memory_writer import MemoryWriter
                from hachi.core.paths import get_hachi_paths

                paths = get_hachi_paths()
                ctx.memory_writer = MemoryWriter(paths.memory_dir)
            except Exception:
                logger.debug(
                    "build_job_context: MemoryWriter not available — falling back to flat path"
                )

    return ctx


# ---------------------------------------------------------------------------
# Handler: extract_fact
# ---------------------------------------------------------------------------


def handle_extract_fact(
    session_id: str = "",
    text: str = "",
    typed: bool = False,
    group: str = "core_memory",
    _llm_client_factory: Any = None,
    _vault_factory: Any = None,
    _memory_writer_factory: Any = None,
    **_kwargs: Any,
) -> str:
    """Durable handler for background fact extraction into the memory vault.

    P1-5: This handler is now REAL — it rebuilds vault + LLM client from config via
    ``build_job_context`` so jobs survive a process restart.  No closures or live
    runtime state are captured in the job payload.

    Service resolution order (all lazy, guarded):
      1. vault    — ``get_memory_vault()`` (ChromaDB, reconstructed from paths).
      2. llm_client — ``memory_vault._get_llm_client()`` (AnthropicClient built from
                      ANTHROPIC_API_KEY; the same module-level singleton used by the
                      vault's own LLM calls).
      3. memory_writer — ``MemoryWriter(paths.memory_dir)`` only when ``typed=True``;
                         omitted on the flat-JSON path to avoid unnecessary I/O.

    Graceful degradation: if vault OR llm_client cannot be resolved (API key absent,
    ChromaDB not installed, etc.) the handler logs a WARNING and returns a
    ``"skipped:..."`` status — it does NOT raise.  A raise would mark the job FAILED
    and trigger an unhelpful retry loop on every restart.

    Injection points (for tests — pass as keyword args):
      _llm_client_factory:     0-arg callable returning a fake LLM client.
      _vault_factory:          0-arg callable returning a fake vault.
      _memory_writer_factory:  0-arg callable returning a fake MemoryWriter.
    """
    if not text:
        logger.debug("handle_extract_fact: empty text — skipping")
        return "skipped:empty_text"

    payload: dict[str, Any] = {"session_id": session_id, "typed": typed}
    ctx = build_job_context(
        payload,
        _llm_client_factory=_llm_client_factory,
        _vault_factory=_vault_factory,
        _memory_writer_factory=_memory_writer_factory,
    )

    if ctx.vault is None:
        logger.warning(
            "handle_extract_fact: vault not available (ChromaDB not configured?) — skipping. "
            "session=%r text_len=%d",
            session_id,
            len(text),
        )
        return "skipped:no_vault"

    if ctx.llm_client is None:
        logger.warning(
            "handle_extract_fact: LLM client not available (ANTHROPIC_API_KEY not set?) — "
            "skipping. session=%r text_len=%d",
            session_id,
            len(text),
        )
        return "skipped:no_llm_client"

    try:
        from hachi.core.memory import extract_facts

        result: str = extract_facts(
            text,
            vault=ctx.vault,
            llm_client=ctx.llm_client,
            memory_writer=ctx.memory_writer,
            session_id=session_id or "",
        )
        logger.debug("handle_extract_fact: completed session=%r result=%r", session_id, result)
        return result
    except Exception as exc:
        # Catch-all so a transient LLM error doesn't permanently fail the job.
        # The exception is logged at WARNING (not ERROR) so operators see it without
        # triggering high-severity alerts for routine API hiccups.
        logger.warning(
            "handle_extract_fact: extraction failed session=%r — %s",
            session_id,
            exc,
            exc_info=True,
        )
        return f"error:{type(exc).__name__}"


# ---------------------------------------------------------------------------
# Handler: generate_title
# ---------------------------------------------------------------------------


def handle_generate_title(
    session_id: str = "",
    user_message: str = "",
    assistant_message: str = "",
    **_kwargs: Any,
) -> str:
    """Durable handler for background session title generation.

    Replaces the former ``func=`` closure in orchestrator.py so title jobs survive restart.

    The durable path does NOT have an LLM client in the serializable payload, so
    it uses :func:`~hachi.core.session_titler.fallback_title` (deterministic
    truncation of the first user message line) rather than an LLM call.  This is
    an acceptable degradation: the goal is a non-empty title on restart, not a
    perfect one.  If an LLM-generated title was produced and stored *before* the
    restart, ``set_session_title`` is idempotent and the stored title wins.

    Payload keys (serializable):
        session_id:        Target session.
        user_message:      First user turn text (primary signal for title).
        assistant_message: First assistant reply (used as context).
    """
    if not session_id or not user_message:
        logger.debug("handle_generate_title: missing session_id or user_message — skipping")
        return "skipped"
    try:
        from hachi.core.session_store import SessionStore
        from hachi.core.session_titler import fallback_title

        # Durable context: no LLM client available; use deterministic fallback.
        title = fallback_title(user_message)
        if title:
            store = SessionStore()
            store.set_session_title(session_id, title)
            logger.debug("handle_generate_title: set title %r for session %r", title, session_id)
        return title or "no title generated"
    except Exception as exc:
        logger.error("handle_generate_title: failed — %s", exc)
        raise


# ---------------------------------------------------------------------------
# Handler: auto_extract (reactive file pipeline seam — A8)
# ---------------------------------------------------------------------------


def handle_auto_extract(
    event_name: str = "",
    event_payload: dict[str, Any] | None = None,
    event_timestamp: str = "",
    event_sequence: int = 0,
    **_kwargs: Any,
) -> str:
    """Reactive handler for ``file.uploaded`` events (Initiative E, Slice 2.4).

    Runs the ContentExtractor pipeline on the uploaded file:
      1. Resolve FileMetaStore + LocalStorageProvider from paths.
      2. Find the first ContentExtractor that supports the file's media_type.
      3. Extract text, guard_untrusted-wrap it, store as a sidecar (.txt) blob.
      4. Update FileMeta status → ``extracted`` (or ``stored`` on degradation).
      5. Emit ``file.extracted`` via a fresh EventBus publish (no queue to avoid
         recursion).
      6. Optionally index extracted chunks into the ``attachments`` Chroma
         collection when ``[files] index_on_extract = true`` in settings.

    Failures in any step are logged; the handler always returns a status string
    so the JobRegistry marks the job completed (not failed), preventing spurious
    retries on configuration-level mismatches (e.g. extractor unavailable).
    """
    payload = event_payload or {}
    file_id: str = payload.get("file_id", "")
    media_type: str = payload.get("media_type", "")
    name: str = payload.get("name", "")

    if not file_id:
        logger.warning("handle_auto_extract: missing file_id in payload — skipping")
        return "skipped: missing file_id"

    logger.info(
        "handle_auto_extract: processing file_id=%r name=%r media_type=%r seq=%d",
        file_id,
        name,
        media_type,
        event_sequence,
    )

    try:
        from hachi.core.files.store import (
            FileMetaStore,
            LocalStorageProvider,
            _build_extractor_chain,
            find_extractor,
        )
        from hachi.core.paths import get_hachi_paths
        from hachi.core.untrusted_content import guard_untrusted

        paths = get_hachi_paths()
        meta_store = FileMetaStore(paths.files_db)
        storage = LocalStorageProvider(paths.blobs_dir)
        chain = _build_extractor_chain()
        extractor = find_extractor(chain, media_type)

        if extractor is None:
            logger.info(
                "handle_auto_extract: no extractor for media_type=%r (file_id=%r) "
                "— file stays at 'stored'",
                media_type,
                file_id,
            )
            return f"degraded:no_extractor:{file_id}"

        # Open the blob for extraction.
        with storage.open(file_id) as blob_stream:
            raw_text = extractor.extract(blob_stream, media_type)

        # Wrap extracted text with guard_untrusted before it can reach the model.
        guarded_text, flagged = guard_untrusted(raw_text, source=f"file:{name or file_id}")
        if flagged:
            logger.warning(
                "handle_auto_extract: guard_untrusted flagged possible injection in %r",
                file_id,
            )

        # Store guarded text as a sidecar blob under "<file_id>.txt".
        import io as _io

        sidecar_id = f"{file_id}.txt"
        storage.put(sidecar_id, _io.BytesIO(guarded_text.encode("utf-8")))
        meta_store.update_status(file_id, "extracted", extracted_text_ref=sidecar_id)

        logger.info(
            "handle_auto_extract: extracted %d chars from %r → sidecar %r",
            len(guarded_text),
            file_id,
            sidecar_id,
        )

        # Optionally index into 'attachments' Chroma collection (RAG seam).
        _try_index_attachment(file_id, name, raw_text, guarded_text)

        # Emit file.extracted event.
        _emit_file_extracted(file_id, name, media_type, sidecar_id)

        return f"extracted:{file_id}"

    except Exception as exc:
        logger.error("handle_auto_extract: failed for file_id=%r — %s", file_id, exc, exc_info=True)
        # Mark as failed in the meta store (best-effort).
        try:
            from hachi.core.files.store import FileMetaStore
            from hachi.core.paths import get_hachi_paths

            FileMetaStore(get_hachi_paths().files_db).update_status(file_id, "failed")
        except Exception:
            pass
        return f"error:{file_id}:{exc}"


def _try_index_attachment(file_id: str, name: str, raw_text: str, guarded_text: str) -> None:
    """Index extracted text chunks into the ``attachments`` Chroma collection.

    Uses the RRF fusion seam (memory_vault.py:785) — inserted into a
    separate ``attachments`` collection so ``semantic_search`` can merge it
    without any caller changes.  Skipped gracefully when chromadb is
    unavailable or ``[files] index_on_extract = false``.
    """
    try:
        from hachi.core.config_loader import load_effective_config

        cfg = load_effective_config()
        if not getattr(cfg.files, "index_on_extract", True):
            return
    except Exception:
        pass  # Default: index when we can

    try:
        import chromadb  # type: ignore[import-untyped]

        from hachi.core.paths import get_hachi_paths

        paths = get_hachi_paths()
        client = chromadb.PersistentClient(path=str(paths.chroma_dir / "attachments"))
        coll = client.get_or_create_collection(
            "attachments",
            metadata={"description": "File attachment extracted text chunks"},
        )
        # Simple whole-doc chunk (chunking at scale is deferred per §8).
        chunk_id = f"{file_id}:0"
        coll.upsert(
            ids=[chunk_id],
            documents=[raw_text[:8000]],  # Chroma default embedding window
            metadatas=[{"file_id": file_id, "name": name, "chunk": 0}],
        )
        logger.debug("handle_auto_extract: indexed chunk %r into attachments collection", chunk_id)
    except ImportError:
        logger.debug("handle_auto_extract: chromadb not available — skipping index")
    except Exception:
        logger.debug("handle_auto_extract: index failed (non-fatal)", exc_info=True)


def _emit_file_extracted(file_id: str, name: str, media_type: str, sidecar_id: str) -> None:
    """Publish ``file.extracted`` via a fresh in-process EventBus call."""
    try:
        from hachi.core.event_bus import EventBus
        from hachi.core.runtime_events import FILE_EXTRACTED, RuntimeEvent, now_iso

        # Fresh bus with no subscribers — publish propagates to any wired bus
        # only if it was injected.  We re-use the shared _shared bus when
        # available (best-effort; not required for correctness).
        bus: Any = None
        try:
            from hachi.gateway.orchestrator import _shared  # type: ignore[attr-defined]

            bus = getattr(_shared, "event_bus", None)
        except Exception:
            pass

        if bus is None:
            bus = EventBus()

        event = RuntimeEvent(
            name=FILE_EXTRACTED,
            payload={
                "file_id": file_id,
                "name": name,
                "media_type": media_type,
                "sidecar_id": sidecar_id,
            },
            timestamp=now_iso(),
        )
        bus.publish(event)
    except Exception:
        logger.debug("_emit_file_extracted: publish failed (non-fatal)", exc_info=True)


# ---------------------------------------------------------------------------
# Handler: resume_run (wake a WAITING run)
# ---------------------------------------------------------------------------


def handle_resume_run(
    run_id: str = "",
    result: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> str:
    """Durable handler to resume a WAITING run.

    Dispatched by WaitConditionRegistry.resolve() → job queue so the wake is
    durable and survives a restart between wake scheduling and execution.
    """
    if not run_id:
        logger.warning("handle_resume_run: missing run_id")
        return "error: missing run_id"
    result = result or {}
    try:
        from hachi.core.runtime.resume import resume_run

        resume_run(run_id, result)
        return f"resumed:{run_id}"
    except Exception as exc:
        logger.error("handle_resume_run: failed to resume %r — %s", run_id, exc)
        raise
