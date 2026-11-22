"""P2-07b: Pack index — Homebrew-tap-model curated catalog.

Tests:
- parse_index_toml: round-trips id/name/description/source/semver/scopes/sha256
- PackIndex.search: matches by id, name, description; case-insensitive; empty query
- PackIndex.get: found and not-found cases
- fetch_pack_index: uses local cache when fresh; re-downloads when forced
- load_cached_index: returns None when absent; returns parsed index when present
- verify_index_entry_sha256: matches correct hash; rejects bad hash; passes when empty
- CLI search / index commands are registered
"""

from __future__ import annotations

import hashlib
import textwrap
import time
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_INDEX_TOML = textwrap.dedent("""\
    [[packs]]
    id = "google-workspace"
    name = "Google Workspace"
    description = "Gmail, Calendar, Drive skills"
    source = "hachi-community/google-workspace@v1.0.0"
    semver = "1.0.0"
    scopes = ["gmail.read", "calendar.read"]
    author = "Hachi Team"
    sha256 = "abc123"

    [[packs]]
    id = "slack-integration"
    name = "Slack"
    description = "Slack messaging skills"
    source = "hachi-community/slack@v0.9.0"
    semver = "0.9.0"
    scopes = ["slack.read", "slack.send"]
    author = "Community"
""")


# ---------------------------------------------------------------------------
# parse_index_toml tests
# ---------------------------------------------------------------------------


def test_parse_index_toml_empty():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml("")
    assert index.packs == []


def test_parse_index_toml_no_packs_key():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml("title = 'index'")
    assert index.packs == []


def test_parse_index_toml_single_pack():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    assert len(index.packs) == 2
    first = index.packs[0]
    assert first.id == "google-workspace"
    assert first.name == "Google Workspace"
    assert first.description == "Gmail, Calendar, Drive skills"
    assert first.semver == "1.0.0"
    assert first.sha256 == "abc123"


def test_parse_index_toml_scopes():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    first = index.packs[0]
    assert "gmail.read" in first.scopes
    assert "calendar.read" in first.scopes


def test_parse_index_toml_skips_entry_without_id():
    from hachi.core.pack_index import parse_index_toml

    toml = textwrap.dedent("""\
        [[packs]]
        name = "No ID Pack"
        description = "Missing id field"

        [[packs]]
        id = "valid-pack"
        name = "Valid"
    """)
    index = parse_index_toml(toml)
    assert len(index.packs) == 1
    assert index.packs[0].id == "valid-pack"


def test_parse_index_toml_accepts_bytes():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML.encode("utf-8"))
    assert len(index.packs) == 2


def test_parse_index_toml_unknown_keys_ignored():
    from hachi.core.pack_index import parse_index_toml

    toml = '[[packs]]\nid = "x"\nfuture_field = "ignored"'
    index = parse_index_toml(toml)
    assert index.packs[0].id == "x"


# ---------------------------------------------------------------------------
# PackIndex.search
# ---------------------------------------------------------------------------


def test_search_by_id():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    results = index.search("google")
    assert len(results) == 1
    assert results[0].id == "google-workspace"


def test_search_by_name():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    results = index.search("Slack")
    assert any(r.id == "slack-integration" for r in results)


def test_search_by_description():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    results = index.search("messaging")
    assert any(r.id == "slack-integration" for r in results)


def test_search_case_insensitive():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    assert index.search("GOOGLE") == index.search("google")


def test_search_no_match_returns_empty():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    assert index.search("nonexistent-xyz") == []


def test_search_empty_query_returns_all():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    assert len(index.search("")) == 2


# ---------------------------------------------------------------------------
# PackIndex.get
# ---------------------------------------------------------------------------


def test_get_found():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    entry = index.get("slack-integration")
    assert entry is not None
    assert entry.id == "slack-integration"


def test_get_not_found():
    from hachi.core.pack_index import parse_index_toml

    index = parse_index_toml(SAMPLE_INDEX_TOML)
    assert index.get("does-not-exist") is None


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def test_load_cached_index_returns_none_when_absent(tmp_path):
    from hachi.core.pack_index import load_cached_index

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    assert load_cached_index(state_dir) is None


def test_load_cached_index_returns_parsed_index(tmp_path):
    from hachi.core.pack_index import load_cached_index

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "pack_index.toml").write_text(SAMPLE_INDEX_TOML, encoding="utf-8")
    index = load_cached_index(state_dir)
    assert index is not None
    assert len(index.packs) == 2


def test_fetch_pack_index_uses_cache_when_fresh(tmp_path):
    from hachi.core.pack_index import INDEX_CACHE_FILENAME, fetch_pack_index

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    cache = state_dir / INDEX_CACHE_FILENAME
    cache.write_text(SAMPLE_INDEX_TOML, encoding="utf-8")

    # _download must NOT be called when the cache is fresh.
    with patch("hachi.core.pack_index._download") as mock_dl:
        index = fetch_pack_index(state_dir, url="http://fake.example/index.toml")
        mock_dl.assert_not_called()

    assert len(index.packs) == 2


def test_fetch_pack_index_force_bypasses_cache(tmp_path):
    from hachi.core.pack_index import INDEX_CACHE_FILENAME, fetch_pack_index

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    cache = state_dir / INDEX_CACHE_FILENAME
    cache.write_text(SAMPLE_INDEX_TOML, encoding="utf-8")

    with patch(
        "hachi.core.pack_index._download",
        return_value=SAMPLE_INDEX_TOML.encode("utf-8"),
    ):
        index = fetch_pack_index(state_dir, url="http://fake/index.toml", force=True)

    assert len(index.packs) == 2


def test_fetch_pack_index_falls_back_to_cache_on_error(tmp_path):
    from hachi.core.pack_index import INDEX_CACHE_FILENAME, INDEX_TTL_SECONDS, fetch_pack_index

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    cache = state_dir / INDEX_CACHE_FILENAME
    cache.write_text(SAMPLE_INDEX_TOML, encoding="utf-8")

    # Make the cache appear stale.
    old_time = time.time() - INDEX_TTL_SECONDS - 1
    import os

    os.utime(cache, (old_time, old_time))

    with patch("hachi.core.pack_index._download", side_effect=OSError("network down")):
        index = fetch_pack_index(state_dir, url="http://fake/index.toml")

    assert len(index.packs) == 2


def test_fetch_pack_index_raises_when_no_cache_and_network_fails(tmp_path):
    from hachi.core.pack_index import fetch_pack_index

    state_dir = tmp_path / "state"
    state_dir.mkdir()

    with patch("hachi.core.pack_index._download", side_effect=OSError("network down")):
        with pytest.raises(RuntimeError, match="Cannot fetch"):
            fetch_pack_index(state_dir, url="http://fake/index.toml", force=True)


# ---------------------------------------------------------------------------
# SHA-256 verification
# ---------------------------------------------------------------------------


def test_verify_sha256_correct():
    from hachi.core.pack_index import PackIndexEntry, verify_index_entry_sha256

    content = b"skill content"
    digest = hashlib.sha256(content).hexdigest()
    entry = PackIndexEntry(id="x", sha256=digest)
    assert verify_index_entry_sha256(entry, content) is True


def test_verify_sha256_mismatch():
    from hachi.core.pack_index import PackIndexEntry, verify_index_entry_sha256

    entry = PackIndexEntry(id="x", sha256="badhash")
    assert verify_index_entry_sha256(entry, b"anything") is False


def test_verify_sha256_no_hash_always_passes():
    from hachi.core.pack_index import PackIndexEntry, verify_index_entry_sha256

    entry = PackIndexEntry(id="x", sha256="")
    assert verify_index_entry_sha256(entry, b"anything") is True


# ---------------------------------------------------------------------------
# CLI command registration
# ---------------------------------------------------------------------------


def test_ogpack_search_registered():
    from hachi.cli.main import ogpack_app

    names = {c.name or c.callback.__name__ for c in ogpack_app.registered_commands}
    assert any("search" in n for n in names)


def test_ogpack_index_subapp_registered():
    from hachi.cli.main import ogpack_app

    group_names = {g.name for g in ogpack_app.registered_groups}
    assert "index" in group_names
