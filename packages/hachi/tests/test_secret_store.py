from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hachi.core.secret_store import (
    _CHUNK_KEY_INFIX,
    _MAX_KEYRING_BLOB_BYTES,
    CompositeSecretStore,
    EncryptedFileSecretStore,
    KeyringSecretStore,
    _chunk_key,
    _make_manifest,
    _MetadataStore,
    _parse_manifest,
    _split_into_chunks,
)


def test_encrypted_file_secret_store_roundtrip(tmp_path: Path) -> None:
    store = EncryptedFileSecretStore(
        file_path=tmp_path / "secrets.enc",
        passphrase="test-passphrase",
    )

    store.set("slack.bot_token", "xoxb-secret")
    assert store.get("slack.bot_token") == "xoxb-secret"

    store.delete("slack.bot_token")
    assert store.get("slack.bot_token") is None


def test_encrypted_store_healthcheck_requires_passphrase(tmp_path: Path) -> None:
    store = EncryptedFileSecretStore(file_path=tmp_path / "secrets.enc", passphrase=None)
    result = store.healthcheck()
    assert result["status"] == "unavailable"


def test_composite_get_falls_back_when_keyring_get_is_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    metadata = _MetadataStore(tmp_path / "secrets_metadata.json")
    keyring_store = KeyringSecretStore(service_name="hachi-test", metadata_store=metadata)
    fallback_store = EncryptedFileSecretStore(
        file_path=tmp_path / "secrets.enc",
        passphrase="test-passphrase",
        metadata_store=metadata,
    )
    composite = CompositeSecretStore(primary=keyring_store, fallback=fallback_store)

    fallback_store.set("provider.api_key", "fallback-secret")
    monkeypatch.setattr(
        "hachi.core.secret_store.keyring.get_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("keyring unavailable")),
    )

    assert composite.get("provider.api_key") == "fallback-secret"


def test_missing_passphrase_blocks_fallback_set_when_keyring_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    metadata = _MetadataStore(tmp_path / "secrets_metadata.json")
    keyring_store = KeyringSecretStore(service_name="hachi-test", metadata_store=metadata)
    fallback_store = EncryptedFileSecretStore(
        file_path=tmp_path / "secrets.enc",
        passphrase=os.environ.get("HACHI_SECRET_PASSPHRASE"),
        metadata_store=metadata,
    )
    composite = CompositeSecretStore(primary=keyring_store, fallback=fallback_store)

    monkeypatch.setattr(
        "hachi.core.secret_store.keyring.set_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("keyring unavailable")),
    )
    monkeypatch.setattr(
        "hachi.core.secret_store.keyring.get_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("keyring unavailable")),
    )
    monkeypatch.setattr(
        "hachi.core.secret_store.keyring.delete_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("keyring unavailable")),
    )

    with pytest.raises(RuntimeError, match="HACHI_SECRET_PASSPHRASE"):
        composite.set("openai.api_key", "secret")


def test_corrupted_metadata_file_is_tolerated_and_recovers(tmp_path: Path) -> None:
    metadata_path = tmp_path / "secrets_metadata.json"
    metadata_path.write_text("{not-json", encoding="utf-8")

    metadata = _MetadataStore(metadata_path)
    assert metadata.all() == []

    metadata.upsert("token.one", {"name": "token.one", "backend": "keyring"})
    rows = metadata.all()
    assert len(rows) == 1
    assert rows[0]["name"] == "token.one"


def test_keyring_delete_metadata_desync_is_self_healed(tmp_path: Path, monkeypatch) -> None:
    metadata = _MetadataStore(tmp_path / "secrets_metadata.json")
    store = KeyringSecretStore(service_name="hachi-test", metadata_store=metadata)

    metadata.upsert("slack.bot_token", {"name": "slack.bot_token", "backend": "keyring"})
    monkeypatch.setattr(
        "hachi.core.secret_store.keyring.delete_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("missing in keyring")),
    )

    store.delete("slack.bot_token")

    assert store.list_metadata() == []


# ---------------------------------------------------------------------------
# Helpers shared by the chunking tests
# ---------------------------------------------------------------------------

# Windows Credential Manager blob limit is 2560 bytes (UTF-16-LE).
# Our budget is _MAX_KEYRING_BLOB_BYTES = 2048.  Simulate the Windows limit
# by raising OSError when the encoded password exceeds 2560 bytes.
_WIN_BLOB_LIMIT = 2560


def _make_simulated_windows_keyring(
    backing: dict[str, str],
) -> tuple[Any, Any, Any]:
    """Return (set_password, get_password, delete_password) callables backed by *backing*.

    set_password raises OSError (simulating WinError 1783) when the password's
    UTF-16-LE encoding exceeds the Windows blob limit.
    """

    def _set(service: str, username: str, password: str) -> None:
        if len(password.encode("utf-16-le")) > _WIN_BLOB_LIMIT:
            raise OSError("(1783, 'CredWrite', 'The stub received bad data')")
        backing[f"{service}/{username}"] = password

    def _get(service: str, username: str) -> str | None:
        return backing.get(f"{service}/{username}")

    def _del(service: str, username: str) -> None:
        backing.pop(f"{service}/{username}", None)

    return _set, _get, _del


def _make_store_with_simulated_windows(
    monkeypatch: pytest.MonkeyPatch,
    backing: dict[str, str],
) -> KeyringSecretStore:
    """Patch the keyring module with the simulated Windows backend and return a store."""
    _set, _get, _del = _make_simulated_windows_keyring(backing)
    monkeypatch.setattr("hachi.core.secret_store.keyring.set_password", _set)
    monkeypatch.setattr("hachi.core.secret_store.keyring.get_password", _get)
    monkeypatch.setattr("hachi.core.secret_store.keyring.delete_password", _del)
    return KeyringSecretStore(service_name="hachi-test")


# ---------------------------------------------------------------------------
# Unit tests: _split_into_chunks helper
# ---------------------------------------------------------------------------


class TestSplitIntoChunks:
    """Unit tests for the surrogate-safe chunk splitter."""

    def test_small_value_produces_single_chunk(self) -> None:
        """Values that fit in one budget chunk are returned as a single element."""
        value = "x" * 10
        chunks = _split_into_chunks(value, _MAX_KEYRING_BLOB_BYTES)
        assert chunks == [value]

    def test_exact_budget_produces_single_chunk(self) -> None:
        """Value whose UTF-16-LE size == budget produces exactly one chunk."""
        # ASCII chars are 2 bytes each in UTF-16-LE.
        value = "a" * (_MAX_KEYRING_BLOB_BYTES // 2)
        chunks = _split_into_chunks(value, _MAX_KEYRING_BLOB_BYTES)
        assert len(chunks) == 1
        assert chunks[0] == value

    def test_large_value_splits_into_multiple_chunks(self) -> None:
        """Values larger than the budget split into multiple chunks."""
        # 2050 ASCII chars → 4100 bytes → needs at least 2 chunks at 2048-byte budget.
        value = "b" * 2050
        chunks = _split_into_chunks(value, _MAX_KEYRING_BLOB_BYTES)
        assert len(chunks) >= 2
        assert "".join(chunks) == value

    def test_each_chunk_fits_within_budget(self) -> None:
        """Every produced chunk's UTF-16-LE size is ≤ the budget."""
        value = "c" * 4000
        chunks = _split_into_chunks(value, _MAX_KEYRING_BLOB_BYTES)
        for chunk in chunks:
            assert len(chunk.encode("utf-16-le")) <= _MAX_KEYRING_BLOB_BYTES

    def test_surrogate_pair_not_split(self) -> None:
        """A value made of supplementary characters (4 bytes each) is split correctly."""
        # U+1F600 (GRINNING FACE) requires a surrogate pair in UTF-16-LE (4 bytes).
        emoji = "\U0001f600"
        # Use a budget of 8 bytes (fits 2 emoji per chunk).
        value = emoji * 6  # 6 emoji, 24 bytes total → 3 chunks of 2 emoji each
        chunks = _split_into_chunks(value, 8)
        assert len(chunks) == 3
        assert "".join(chunks) == value
        for chunk in chunks:
            assert len(chunk.encode("utf-16-le")) <= 8


# ---------------------------------------------------------------------------
# KeyringSecretStore chunking: functional tests against simulated Windows
# ---------------------------------------------------------------------------


class TestKeyringChunking:
    """Tests for transparent chunking in KeyringSecretStore.

    All keyring I/O is intercepted by a simulated Windows Credential Manager
    that rejects blobs > 2560 bytes.  No real OS keyring is ever called.
    """

    # ------------------------------------------------------------------
    # Test 1: large OAuth-bundle round-trips exactly
    # ------------------------------------------------------------------

    def test_large_value_roundtrips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 4000-char value (exceeds Windows limit) round-trips through set/get."""
        backing: dict[str, str] = {}
        store = _make_store_with_simulated_windows(monkeypatch, backing)

        # Simulate an OAuth token bundle: JSON with multiple JWTs.
        big_value = "A" * 4000
        store.set("google.oauth_token", big_value)
        assert store.get("google.oauth_token") == big_value

    # ------------------------------------------------------------------
    # Test 2: small value → single keyring entry
    # ------------------------------------------------------------------

    def test_small_value_stored_as_single_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A small value is stored as a single keyring entry (not chunked)."""
        backing: dict[str, str] = {}
        store = _make_store_with_simulated_windows(monkeypatch, backing)

        store.set("api.key", "short-secret")

        # Only the main entry should exist — no chunk entries.
        chunk0_key = f"hachi-test/{_chunk_key('api.key', 0)}"
        assert chunk0_key not in backing
        # The main entry must hold the value directly (not a manifest).
        assert backing.get("hachi-test/api.key") == "short-secret"
        assert _parse_manifest(backing["hachi-test/api.key"]) is None

    # ------------------------------------------------------------------
    # Test 3: delete removes manifest + all chunks
    # ------------------------------------------------------------------

    def test_delete_chunked_removes_all_entries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Deleting a chunked secret removes the manifest and every chunk entry."""
        backing: dict[str, str] = {}
        store = _make_store_with_simulated_windows(monkeypatch, backing)

        store.set("oauth.bundle", "X" * 4000)
        # Sanity: at least 2 keys in backing (manifest + ≥1 chunk).
        assert len(backing) >= 2

        store.delete("oauth.bundle")
        # After deletion the backing dict must be empty (no orphans).
        assert backing == {}

    # ------------------------------------------------------------------
    # Test 4: backward-compat — pre-existing un-chunked entry reads correctly
    # ------------------------------------------------------------------

    def test_backward_compat_unchunked_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pre-existing un-chunked entry (written before this fix) reads correctly."""
        backing: dict[str, str] = {}
        # Directly inject a value that looks like a legacy secret (no manifest).
        backing["hachi-test/legacy.token"] = "pre-existing-value"
        store = _make_store_with_simulated_windows(monkeypatch, backing)

        assert store.get("legacy.token") == "pre-existing-value"

    # ------------------------------------------------------------------
    # Test 5a: chunked → small leaves no orphan chunks
    # ------------------------------------------------------------------

    def test_overwrite_chunked_with_small_removes_chunks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Overwriting a large (chunked) value with a small one leaves no orphan chunks."""
        backing: dict[str, str] = {}
        store = _make_store_with_simulated_windows(monkeypatch, backing)

        # First write: chunked.
        store.set("token", "Y" * 4000)
        assert len(backing) >= 2

        # Overwrite with small value.
        store.set("token", "tiny")
        # Only the main entry should remain.
        assert backing.get("hachi-test/token") == "tiny"
        # No chunk entries should survive.
        for key in list(backing):
            assert _CHUNK_KEY_INFIX not in key

    # ------------------------------------------------------------------
    # Test 5b: small → large leaves no orphans from old entry
    # ------------------------------------------------------------------

    def test_overwrite_small_with_large_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Overwriting a small value with a large one chunks correctly and round-trips."""
        backing: dict[str, str] = {}
        store = _make_store_with_simulated_windows(monkeypatch, backing)

        store.set("token", "short")
        store.set("token", "Z" * 4000)
        assert store.get("token") == "Z" * 4000

    # ------------------------------------------------------------------
    # Test 7: non-ASCII / multibyte chars round-trip
    # ------------------------------------------------------------------

    def test_multibyte_chars_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A value containing emoji (4-byte UTF-16-LE surrogates) round-trips when chunked."""
        backing: dict[str, str] = {}
        store = _make_store_with_simulated_windows(monkeypatch, backing)

        # 2000 emoji × 4 bytes each = 8000 bytes → definitely chunked.
        # Also mix in some ASCII and BMP chars to stress the splitter.
        value = ("\U0001f600" * 200 + "hello_" + "中文" * 50) * 4
        store.set("emoji.token", value)
        assert store.get("emoji.token") == value


# ---------------------------------------------------------------------------
# Test 6: CompositeSecretStore write-time fallback
# ---------------------------------------------------------------------------


class TestCompositeWriteFallback:
    """Test 6: When the primary raises on set(), the value is routed to the fallback."""

    def _make_failing_primary(self) -> MagicMock:
        """Return a mock primary whose healthcheck returns 'ok' but set() raises."""
        primary = MagicMock()
        primary.healthcheck.return_value = {"status": "ok", "backend": "keyring"}
        primary.set.side_effect = OSError("(1783, 'CredWrite', 'The stub received bad data')")
        return primary

    def test_write_falls_back_to_encrypted_file(self, tmp_path: Path) -> None:
        """Primary raises on set → value is written to encrypted-file fallback."""
        primary = self._make_failing_primary()
        fallback = EncryptedFileSecretStore(
            file_path=tmp_path / "secrets.enc",
            passphrase="test-pass",
        )
        composite = CompositeSecretStore(primary=primary, fallback=fallback)

        composite.set("oauth.token", "big-token-value")

        # Value must be retrievable.  primary.get returns None (mock default),
        # so composite.get falls through to the fallback.
        primary.get.return_value = None
        result = composite.get("oauth.token")
        assert result == "big-token-value"

    def test_fallback_error_propagates(self, tmp_path: Path) -> None:
        """If both primary and fallback fail, the fallback's RuntimeError propagates."""
        primary = self._make_failing_primary()
        # Fallback without passphrase → RuntimeError on set.
        fallback = EncryptedFileSecretStore(
            file_path=tmp_path / "secrets.enc",
            passphrase=None,
        )
        composite = CompositeSecretStore(primary=primary, fallback=fallback)

        with pytest.raises(RuntimeError, match="HACHI_SECRET_PASSPHRASE"):
            composite.set("oauth.token", "value")


# ---------------------------------------------------------------------------
# Regression guard: chunk keys MUST be NUL-free, because Windows Credential
# Manager truncates credential NAMES at the first NUL (LPWSTR semantics).
# A NUL-bearing chunk-key scheme passes a naive in-memory mock (full keys
# preserved) but corrupts data on real Windows (all chunks collapse onto the
# truncated base name). These tests model that truncation so any regression to
# a NUL-in-name scheme fails here.
# ---------------------------------------------------------------------------


def _make_truncating_windows_keyring(backing: dict[str, str]) -> tuple[Any, Any, Any]:
    """Like the simulated Windows keyring, but also TRUNCATES the username at the
    first NUL before using it as the storage key — mirroring Windows LPWSTR
    behavior where a NUL terminates the credential name."""

    def _key(service: str, username: str) -> str:
        truncated = username.split("\x00", 1)[0]  # Windows stops at the first NUL
        return f"{service}/{truncated}"

    def _set(service: str, username: str, password: str) -> None:
        if len(password.encode("utf-16-le")) > _WIN_BLOB_LIMIT:
            raise OSError("(1783, 'CredWrite', 'The stub received bad data')")
        backing[_key(service, username)] = password

    def _get(service: str, username: str) -> str | None:
        return backing.get(_key(service, username))

    def _del(service: str, username: str) -> None:
        backing.pop(_key(service, username), None)

    return _set, _get, _del


class TestKeyringChunkingNulFreeKeys:
    """Chunk keys/manifest must be NUL-free and survive Windows name truncation."""

    def test_chunk_key_and_manifest_contain_no_nul(self) -> None:
        for i in range(5):
            assert "\x00" not in _chunk_key("oauth2:google", i), (
                f"chunk key {i} contains a NUL — would truncate on Windows"
            )
        assert "\x00" not in _make_manifest(7), "manifest contains a NUL"
        assert "\x00" not in _CHUNK_KEY_INFIX, "_CHUNK_KEY_INFIX contains a NUL"

    def test_large_value_roundtrips_under_windows_name_truncation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A >2560-byte value must round-trip even when the backend truncates
        credential names at NUL. With a NUL-in-name scheme every chunk would
        collapse onto the base key and this would fail."""
        backing: dict[str, str] = {}
        _set, _get, _del = _make_truncating_windows_keyring(backing)
        monkeypatch.setattr("hachi.core.secret_store.keyring.set_password", _set)
        monkeypatch.setattr("hachi.core.secret_store.keyring.get_password", _get)
        monkeypatch.setattr("hachi.core.secret_store.keyring.delete_password", _del)
        store = KeyringSecretStore(service_name="hachi-test")

        big = "T" * 4000  # ~8000 bytes UTF-16-LE → multiple chunks
        store.set("oauth2:google", big)
        assert store.get("oauth2:google") == big

        # Manifest + each chunk must occupy a DISTINCT backing key (no collision).
        assert len(backing) >= 3, f"expected manifest + multiple chunks, got {len(backing)}"

    def test_chunked_delete_clean_under_truncation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        backing: dict[str, str] = {}
        _set, _get, _del = _make_truncating_windows_keyring(backing)
        monkeypatch.setattr("hachi.core.secret_store.keyring.set_password", _set)
        monkeypatch.setattr("hachi.core.secret_store.keyring.get_password", _get)
        monkeypatch.setattr("hachi.core.secret_store.keyring.delete_password", _del)
        store = KeyringSecretStore(service_name="hachi-test")

        store.set("oauth2:google", "T" * 4000)
        store.delete("oauth2:google")
        assert backing == {}, f"orphan entries left after delete: {list(backing)}"
        assert store.get("oauth2:google") is None


# ---------------------------------------------------------------------------
# BB-9 — Credential manager gateway API (cred: namespace)
# ---------------------------------------------------------------------------


def _make_file_store(tmp_path: Path) -> EncryptedFileSecretStore:
    meta = _MetadataStore(tmp_path / "meta.json")
    return EncryptedFileSecretStore(
        file_path=tmp_path / "secrets.enc",
        passphrase="test-pass",
        metadata_store=meta,
    )


def _patch_store(monkeypatch, store):
    monkeypatch.setattr("hachi.core.secret_store.create_default_secret_store", lambda: store)


class TestSecretStoreGatewayAPI:
    """Tests for _InProcessGatewayRuntime store_secret / list_secret_names / delete_secret."""

    def test_secret_store_api_roundtrip(self, tmp_path: Path, monkeypatch) -> None:
        store = _make_file_store(tmp_path)
        _patch_store(monkeypatch, store)
        from hachi.cli.main import _InProcessGatewayRuntime

        rt = _InProcessGatewayRuntime()
        result = rt.store_secret("ctx7key", "some-api-value")
        assert result["ok"] is True
        assert result["name"] == "ctx7key"

        names = rt.list_secret_names()
        assert "ctx7key" in names["names"]

        del_result = rt.delete_secret("ctx7key")
        assert del_result["ok"] is True

        names_after = rt.list_secret_names()
        assert "ctx7key" not in names_after["names"]

    def test_secret_list_excludes_system_secrets(self, tmp_path: Path, monkeypatch) -> None:
        """list_secret_names must never expose system keys."""
        store = _make_file_store(tmp_path)
        store.set("ANTHROPIC_API_KEY", "sk-sys")
        store.set("cred:mytoken", "user-value")
        _patch_store(monkeypatch, store)
        from hachi.cli.main import _InProcessGatewayRuntime

        rt = _InProcessGatewayRuntime()
        names = rt.list_secret_names()
        assert "mytoken" in names["names"]
        assert "ANTHROPIC_API_KEY" not in names["names"]
        assert "cred:mytoken" not in names["names"]

    def test_secret_delete_refuses_system_key(self, tmp_path: Path, monkeypatch) -> None:
        """delete_secret only ever removes cred: keys; bare system keys are unaffected."""
        store = _make_file_store(tmp_path)
        store.set("ANTHROPIC_API_KEY", "sk-sys")
        _patch_store(monkeypatch, store)
        from hachi.cli.main import _InProcessGatewayRuntime

        rt = _InProcessGatewayRuntime()
        rt.delete_secret("ANTHROPIC_API_KEY")  # targets cred:ANTHROPIC_API_KEY — no-op
        assert store.get("ANTHROPIC_API_KEY") == "sk-sys"
