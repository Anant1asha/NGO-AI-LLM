from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Protocol, TypedDict

import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from hachi.core.atomic_io import atomic_write_json, quarantine_corrupt_file
from hachi.core.paths import HachiPaths, ensure_directories, get_hachi_paths

logger = logging.getLogger(__name__)


class SecretMetadata(TypedDict, total=False):
    name: str
    backend: str
    updated_at: str
    labels: dict[str, str]


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str, metadata: SecretMetadata | None = None) -> None: ...

    def delete(self, name: str) -> None: ...

    def list_metadata(self) -> list[SecretMetadata]: ...

    def healthcheck(self) -> dict[str, str]: ...


class _MetadataStore:
    def __init__(self, metadata_path: Path):
        self._path = metadata_path

    def _load(self) -> dict[str, SecretMetadata]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            # BB-51: quarantine the unparseable file BEFORE returning the empty
            # default, so the next _save() can't silently clobber it with {}.
            quarantine_corrupt_file(self._path)
        return {}

    def _save(self, payload: dict[str, SecretMetadata]) -> None:
        atomic_write_json(self._path, payload)

    def upsert(self, name: str, metadata: SecretMetadata) -> None:
        payload = self._load()
        payload[name] = metadata
        self._save(payload)

    def delete(self, name: str) -> None:
        payload = self._load()
        payload.pop(name, None)
        self._save(payload)

    def all(self) -> list[SecretMetadata]:
        payload = self._load()
        rows: list[SecretMetadata] = []
        for key, value in payload.items():
            item = dict(value)
            item.setdefault("name", key)
            rows.append(item)
        return rows


# Conservative byte budget for each keyring credential blob.
# Windows Credential Manager caps the blob at CRED_MAX_CREDENTIAL_BLOB_SIZE = 2560 bytes.
# keyring encodes the password as UTF-16-LE (2 bytes per BMP char, 4 for surrogates).
# 2048 bytes leaves comfortable headroom and means ~1024 BMP chars per chunk.
_MAX_KEYRING_BLOB_BYTES: int = 2048

# Sentinel that prefixes the manifest VALUE when a secret has been chunked.
# MUST be NUL-free: Windows Credential Manager truncates credential NAMES at the first
# NUL (LPWSTR semantics), so a NUL-bearing chunk key would collapse every chunk onto the
# same truncated name and corrupt the data (verified on Windows). The marker is distinctive
# enough that no real secret value (JSON/JWT/base64/API key) starts with it, and get()
# additionally requires the suffix to parse as an int before treating it as a manifest.
_CHUNK_SENTINEL_PREFIX: str = "__hachi_chunked_v1__"

# Infix appended to the secret name to derive each chunk's keyring username.
# MUST be NUL-free (see above). Real secret names here are connector ids / env-var names
# (e.g. "oauth2:google", "ANTHROPIC_API_KEY") — none contain this infix, so a chunk key
# cannot collide with a real secret name.
_CHUNK_KEY_INFIX: str = "__hachi_chunk_v1__"


def _chunk_key(name: str, index: int) -> str:
    """Return the keyring username for chunk *index* of secret *name*."""
    return f"{name}{_CHUNK_KEY_INFIX}{index}"


def _make_manifest(chunk_count: int) -> str:
    """Return the manifest string stored under the top-level key when chunked."""
    return f"{_CHUNK_SENTINEL_PREFIX}{chunk_count}"


def _parse_manifest(value: str) -> int | None:
    """Return chunk count if *value* is a chunk manifest, else None."""
    if value.startswith(_CHUNK_SENTINEL_PREFIX):
        try:
            return int(value[len(_CHUNK_SENTINEL_PREFIX) :])
        except ValueError:
            pass
    return None


def _split_into_chunks(value: str, max_bytes: int) -> list[str]:
    """Split *value* into chunks whose UTF-16-LE encoding is ≤ *max_bytes* bytes each.

    Surrogate-safe: never splits inside a surrogate pair (code points U+10000…U+10FFFF
    require a high+low surrogate pair in UTF-16-LE; always 4 bytes together).
    """
    chunks: list[str] = []
    current_chars: list[str] = []
    current_bytes: int = 0

    for ch in value:
        ch_bytes = len(ch.encode("utf-16-le"))
        if current_bytes + ch_bytes > max_bytes and current_chars:
            chunks.append("".join(current_chars))
            current_chars = [ch]
            current_bytes = ch_bytes
        else:
            current_chars.append(ch)
            current_bytes += ch_bytes

    if current_chars:
        chunks.append("".join(current_chars))

    return chunks


class KeyringSecretStore:
    """Keyring-backed secret store with transparent chunking for large values.

    Windows Credential Manager imposes a hard 2560-byte limit on credential blobs
    (encoded UTF-16-LE).  Values that exceed :data:`_MAX_KEYRING_BLOB_BYTES` are
    automatically split across multiple credential entries and transparently
    reassembled on read, so callers never see the limit.
    """

    def __init__(
        self,
        service_name: str = "hachi",
        metadata_store: _MetadataStore | None = None,
    ):
        self._service_name = service_name
        self._metadata = metadata_store

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _kget(self, username: str) -> str | None:
        """Raw keyring read."""
        return keyring.get_password(self._service_name, username)

    def _kset(self, username: str, value: str) -> None:
        """Raw keyring write."""
        keyring.set_password(self._service_name, username, value)

    def _kdel(self, username: str) -> None:
        """Raw keyring delete (swallows missing-entry errors)."""
        try:
            keyring.delete_password(self._service_name, username)
        except Exception:
            pass

    def _delete_all_chunks(self, name: str, chunk_count: int) -> None:
        """Delete all chunk entries for *name* (does not touch the manifest key)."""
        for i in range(chunk_count):
            self._kdel(_chunk_key(name, i))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, name: str) -> str | None:
        """Return the secret stored under *name*, reassembling chunks if needed."""
        raw = self._kget(name)
        if raw is None:
            return None
        chunk_count = _parse_manifest(raw)
        if chunk_count is None:
            # Un-chunked value (including pre-existing entries written before this fix).
            return raw
        # Chunked path: read and concatenate all chunks.
        parts: list[str] = []
        for i in range(chunk_count):
            part = self._kget(_chunk_key(name, i))
            if part is None:
                # Corrupt state: a chunk is missing.  Return None so the caller
                # treats this as a missing secret rather than returning garbage.
                return None
            parts.append(part)
        return "".join(parts)

    def set(self, name: str, value: str, metadata: SecretMetadata | None = None) -> None:
        """Store *value* under *name*, chunking transparently if needed.

        Overwrites any existing entry (chunked or un-chunked) and cleans up stale
        chunk entries from a previous larger value so no orphans are left behind.
        """
        # Read the current manifest (if any) so we can delete stale chunks later.
        current_raw = self._kget(name)
        current_chunk_count: int | None = None
        if current_raw is not None:
            current_chunk_count = _parse_manifest(current_raw)

        value_bytes = len(value.encode("utf-16-le"))
        if value_bytes <= _MAX_KEYRING_BLOB_BYTES:
            # Fits in one entry — store directly.
            self._kset(name, value)
            # Clean up any stale chunks from a previous larger value.
            if current_chunk_count is not None:
                self._delete_all_chunks(name, current_chunk_count)
        else:
            # Needs chunking.
            chunks = _split_into_chunks(value, _MAX_KEYRING_BLOB_BYTES)
            new_chunk_count = len(chunks)
            # Write chunks first, then the manifest (so a partial write leaves no
            # manifest pointing to missing chunks).
            for i, chunk in enumerate(chunks):
                self._kset(_chunk_key(name, i), chunk)
            self._kset(name, _make_manifest(new_chunk_count))
            # Clean up stale chunks beyond the new count (handles shrink-then-grow).
            if current_chunk_count is not None and current_chunk_count > new_chunk_count:
                for i in range(new_chunk_count, current_chunk_count):
                    self._kdel(_chunk_key(name, i))

        if self._metadata is not None:
            item: SecretMetadata = {
                "name": name,
                "backend": "keyring",
                "labels": (metadata or {}).get("labels", {}),
            }
            self._metadata.upsert(name, item)

    def delete(self, name: str) -> None:
        """Delete *name* and any associated chunk entries."""
        raw = self._kget(name)
        if raw is not None:
            chunk_count = _parse_manifest(raw)
            if chunk_count is not None:
                self._delete_all_chunks(name, chunk_count)
        self._kdel(name)
        if self._metadata is not None:
            self._metadata.delete(name)

    def list_metadata(self) -> list[SecretMetadata]:
        """Return stored metadata rows (empty if no metadata store configured)."""
        if self._metadata is None:
            return []
        return self._metadata.all()

    def healthcheck(self) -> dict[str, str]:
        """Probe the keyring with a small value that always fits the blob limit."""
        probe_name = "hachi.health.probe"
        probe_value = "ok"
        try:
            keyring.set_password(self._service_name, probe_name, probe_value)
            observed = keyring.get_password(self._service_name, probe_name)
            keyring.delete_password(self._service_name, probe_name)
            if observed != probe_value:
                return {"status": "degraded", "reason": "keyring probe mismatch"}
            return {"status": "ok", "backend": "keyring"}
        except Exception as exc:
            return {"status": "unavailable", "backend": "keyring", "reason": str(exc)}


class EncryptedFileSecretStore:
    def __init__(
        self, file_path: Path, passphrase: str | None, metadata_store: _MetadataStore | None = None
    ):
        self._file_path = file_path
        self._passphrase = passphrase
        self._metadata = metadata_store

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=390000,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))

    def _read_blob(self) -> dict[str, str]:
        if not self._file_path.exists():
            return {"salt": "", "payload": ""}
        try:
            return json.loads(self._file_path.read_text(encoding="utf-8"))
        except Exception:
            # BB-51: quarantine the unparseable blob BEFORE returning the empty
            # default, so the next _encrypt_all() can't silently clobber it.
            quarantine_corrupt_file(self._file_path)
            return {"salt": "", "payload": ""}

    def _decrypt_all(self) -> dict[str, str]:
        if not self._passphrase:
            raise RuntimeError("Encrypted fallback requires HACHI_SECRET_PASSPHRASE")

        blob = self._read_blob()
        salt_b64 = blob.get("salt", "")
        payload_b64 = blob.get("payload", "")
        if not salt_b64 or not payload_b64:
            return {}

        salt = base64.b64decode(salt_b64.encode("utf-8"))
        key = self._derive_key(self._passphrase, salt)
        cipher = Fernet(key)
        plaintext = cipher.decrypt(payload_b64.encode("utf-8")).decode("utf-8")
        data = json.loads(plaintext)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}

    def _encrypt_all(self, payload: dict[str, str]) -> None:
        if not self._passphrase:
            raise RuntimeError("Encrypted fallback requires HACHI_SECRET_PASSPHRASE")

        # MED-006: generate a fresh random salt on every write so that two
        # ciphertexts of the same plaintext are never identical and the old
        # ciphertext is no longer useful once a new one has been written.
        salt = os.urandom(16)

        key = self._derive_key(self._passphrase, salt)
        cipher = Fernet(key)
        ciphertext = cipher.encrypt(json.dumps(payload).encode("utf-8"))

        atomic_write_json(
            self._file_path,
            {
                "salt": base64.b64encode(salt).decode("utf-8"),
                "payload": ciphertext.decode("utf-8"),
                "fingerprint": hashlib.sha256(ciphertext).hexdigest(),
            },
        )

    def get(self, name: str) -> str | None:
        return self._decrypt_all().get(name)

    def set(self, name: str, value: str, metadata: SecretMetadata | None = None) -> None:
        payload = self._decrypt_all()
        payload[name] = value
        self._encrypt_all(payload)
        if self._metadata is not None:
            item: SecretMetadata = {
                "name": name,
                "backend": "encrypted_file",
                "labels": (metadata or {}).get("labels", {}),
            }
            self._metadata.upsert(name, item)

    def delete(self, name: str) -> None:
        payload = self._decrypt_all()
        payload.pop(name, None)
        self._encrypt_all(payload)
        if self._metadata is not None:
            self._metadata.delete(name)

    def list_metadata(self) -> list[SecretMetadata]:
        if self._metadata is None:
            return []
        return self._metadata.all()

    def healthcheck(self) -> dict[str, str]:
        if not self._passphrase:
            return {
                "status": "unavailable",
                "backend": "encrypted_file",
                "reason": "HACHI_SECRET_PASSPHRASE is not set",
            }
        try:
            probe = "hachi.health.probe"
            self.set(probe, "ok")
            observed = self.get(probe)
            self.delete(probe)
            if observed != "ok":
                return {
                    "status": "degraded",
                    "backend": "encrypted_file",
                    "reason": "probe mismatch",
                }
            return {"status": "ok", "backend": "encrypted_file"}
        except Exception as exc:
            return {"status": "unavailable", "backend": "encrypted_file", "reason": str(exc)}


class CompositeSecretStore:
    def __init__(self, primary: SecretStore, fallback: SecretStore):
        self._primary = primary
        self._fallback = fallback

    def get(self, name: str) -> str | None:
        try:
            primary_value = self._primary.get(name)
        except Exception:
            primary_value = None
        if primary_value is not None:
            return primary_value
        try:
            return self._fallback.get(name)
        except Exception:
            return None

    def set(self, name: str, value: str, metadata: SecretMetadata | None = None) -> None:
        """Write *value* to the primary store, falling back to the secondary on any write error.

        The healthcheck uses a small probe value that always fits the keyring blob
        limit, so it can succeed even when the real value is too large.  This method
        therefore catches write-time errors (e.g. WinError 1783 on large blobs if the
        chunking layer were ever bypassed) and falls back gracefully instead of 500ing.

        If the fallback also fails (e.g. ``HACHI_SECRET_PASSPHRASE`` is unset) its
        ``RuntimeError`` propagates — the message is actionable and must not be swallowed.
        """
        primary_status = self._primary.healthcheck().get("status")
        if primary_status == "ok":
            try:
                self._primary.set(name, value, metadata)
                return
            except Exception as exc:
                logger.warning(
                    "secret_store: primary rejected %r (%s); falling back to secondary",
                    name,
                    exc,
                )
        self._fallback.set(name, value, metadata)

    def delete(self, name: str) -> None:
        self._primary.delete(name)
        self._fallback.delete(name)

    def list_metadata(self) -> list[SecretMetadata]:
        metadata: dict[str, SecretMetadata] = {}
        fallback_rows: list[SecretMetadata]
        primary_rows: list[SecretMetadata]
        try:
            fallback_rows = self._fallback.list_metadata()
        except Exception:
            fallback_rows = []
        try:
            primary_rows = self._primary.list_metadata()
        except Exception:
            primary_rows = []

        for row in fallback_rows + primary_rows:
            metadata[row.get("name", "")] = row
        return [row for _, row in sorted(metadata.items()) if row.get("name")]

    def healthcheck(self) -> dict[str, str]:
        primary = self._primary.healthcheck()
        if primary.get("status") == "ok":
            return {"status": "ok", "backend": primary.get("backend", "primary")}

        fallback = self._fallback.healthcheck()
        if fallback.get("status") == "ok":
            return {"status": "ok", "backend": fallback.get("backend", "fallback")}

        return {
            "status": "unavailable",
            "reason": (
                f"primary={primary.get('reason', 'n/a')}; fallback={fallback.get('reason', 'n/a')}"
            ),
        }


def create_default_secret_store(paths: HachiPaths | None = None) -> SecretStore:
    paths = paths or get_hachi_paths()
    ensure_directories(paths)

    metadata = _MetadataStore(paths.secrets_metadata_file)
    keyring_store = KeyringSecretStore(service_name="hachi", metadata_store=metadata)
    fallback = EncryptedFileSecretStore(
        file_path=paths.secrets_fallback_file,
        passphrase=os.environ.get("HACHI_SECRET_PASSPHRASE"),
        metadata_store=metadata,
    )
    return CompositeSecretStore(keyring_store, fallback)
