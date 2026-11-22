# 18 — File / Attachment Platform

> Phase 2 / Gate B. Initiative **E**. The one genuinely greenfield platform; designed to copy
> existing patterns (`MemoryProvider`, `SecretStore`, `CheckpointManager`). Seams are `file:line`.

## 1. Problem

No file/blob storage, no upload pipeline, no gateway upload routes
(`fastapi_app.py` has no `UploadFile`/`FileResponse`/`multipart`). Local read/write
(`os_tools.py:634`), Google Docs/Drive, and pptx-generation exist but there is no managed store
nor content extraction for PDF/DOCX/CSV/XLSX.

## 2. Contract

```python
# core/files/store.py
class FileMeta(BaseModel):
    file_id: str            # sha256 content hash (mirrors memory_vault fact-id convention)
    name: str; media_type: str; size: int
    status: Literal["received","validated","stored","extracted","indexed","quarantined","failed"]
    created_at: str; extracted_text_ref: str | None = None

class StorageProvider(Protocol):           # where bytes live
    def put(self, file_id: str, data: BinaryIO) -> None: ...   # streaming
    def open(self, file_id: str) -> BinaryIO: ...
    def delete(self, file_id: str) -> None: ...

class ContentExtractor(Protocol):          # bytes → text, per media type
    def supports(self, media_type: str) -> bool: ...
    def extract(self, data: BinaryIO, media_type: str) -> str: ...

class VirusScanHook(Protocol):             # the brief's "real integration point"
    def scan(self, file_id: str, data: BinaryIO) -> ScanResult: ...   # default: NoOpScanner (allow)

class FilePipeline:                        # orchestrates the stages
    def ingest(self, name: str, media_type: str, data: BinaryIO) -> FileMeta: ...
```

## 3. Pipeline (the brief's E stages)

```
Upload → Validate(type/size) → VirusScanHook → StorageProvider.put → metadata(FileMeta)
       → ContentExtractor.extract → [optional] index into MemoryVault (RRF seam) → agent-available
```

Each stage is durable-job-friendly: heavy stages (extract, index) run as **`JobRegistry`
handlers** ([16](16-durable-execution.md)) — `file.uploaded`/`file.extracted` events
([12](12-event-architecture.md)) drive reactive extraction. Streaming `put`/`open` for large
files; a size cap bounds in-memory work.

## 4. One implementation

- **`LocalStorageProvider`** — bytes under `paths.blobs_dir` (new property in `paths.py:19`),
  atomic temp-file + `os.replace` (the `CheckpointManager` technique, `checkpoints.py:43`).
- **`ContentExtractor`s** — zero-dep first: `text/plain`, `text/csv`, code files, JSON. Optional
  extras (`pypdf`, `python-docx`, `openpyxl`) behind a `files` extra in `pyproject.toml`,
  registered only when installed (graceful "extractor not available" otherwise — mirrors the
  voice keyless-degradation pattern).
- **`NoOpScanner`** default `VirusScanHook` (allow-all) — the *interface* is the deliverable; a
  real ClamAV/cloud scanner is a drop-in later. Failures route files to `quarantined`.
- **`FileMetaStore`** — SQLite `files` table via the shared `apply_migrations` helper
  ([25](25-migration-strategy.md)).

## 5. Agent surface & RAG seam

`tools/file_tools.py` (new): `attach_file`, `list_attachments`, `read_attachment`,
`search_attachments`. Gateway: `POST /files` (multipart, `response_model=FileMeta`),
`GET /files`, `GET /files/{id}`, `GET /files/{id}/content`. Indexing reuses the **RRF fusion
seam** (`memory_vault.py:785`): extracted text chunks index into a new `attachments` Chroma
collection and merge through the existing `semantic_search` — no caller changes.

## 6. What it touches

`core/files/*` (new); `tools/file_tools.py` (new); `core/paths.py:19` (`blobs_dir`,
`files_db`); `gateway/fastapi_app.py` (upload/list/get/content routes — first binary routes);
`pyproject.toml` (`files` optional extra); `core/settings.py` (`[files]`: max size, allowed
types, storage backend, scan hook).

## 7. What could break (and the guard)

- **First binary routes** widen the attack surface. *Guard:* strict type/size validation before
  storage; virus-scan hook in the path; extracted text is `guard_untrusted`-wrapped before the
  model; permission-gated like `os_tools`.
- **Optional extractor deps absent** → graceful "not available". *Guard:* tested degradation;
  no hard import at module top.
- **New `files` table** on existing installs. *Guard:* additive via `apply_migrations`; a fresh
  install and an upgrade both get the table (closes debt D9 for this store).

## 8. Deferred (seam only, per §4a)

Cloud/object storage (`StorageProvider` is the seam); archive extraction; OCR; the RAG **index
build at scale** (the *chunk-and-index* path is built; large-corpus ingestion tuning is later);
chunked/resumable uploads beyond the size cap; thumbnailing.
