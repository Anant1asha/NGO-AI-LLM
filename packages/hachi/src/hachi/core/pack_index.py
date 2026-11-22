"""Pack index: Homebrew-tap-model catalog for discovering .ogpack skill packs.

The index is a TOML file (``index.toml``) served from a GitHub repository.  The
default index lives at ``hachi-community/hachi-packs`` (configurable).

Format::

    [[packs]]
    id          = "google-workspace"
    name        = "Google Workspace"
    description = "Gmail, Calendar, Drive skills for Hachi"
    source      = "hachi-community/google-workspace@v1.0.0"
    semver      = "1.0.0"
    scopes      = ["gmail.read", "calendar.read"]
    author      = "Hachi Team"
    sha256      = "optional-content-hash"
    signature   = "optional-minisign-sig"

The local cache lives at ``<state_dir>/pack_index.toml``.  It is refreshed on
demand (``pack index refresh``) or lazily when it is older than 24 hours.
"""

from __future__ import annotations

import hashlib
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hachi.core.net_guard import validate_outbound_url

DEFAULT_INDEX_URL = (
    "https://raw.githubusercontent.com/hachi-community/hachi-packs/main/index.toml"
)
INDEX_CACHE_FILENAME = "pack_index.toml"
INDEX_TTL_SECONDS = 86_400  # 24 hours


@dataclass(frozen=True, slots=True)
class PackIndexEntry:
    """A single pack listed in the community index."""

    id: str
    name: str = ""
    description: str = ""
    source: str = ""
    semver: str = ""
    scopes: tuple[str, ...] = ()
    author: str = ""
    sha256: str = ""
    signature: str = ""


@dataclass
class PackIndex:
    """The full parsed pack index."""

    packs: list[PackIndexEntry] = field(default_factory=list)
    fetched_at: str = ""

    def search(self, query: str) -> list[PackIndexEntry]:
        """Return packs whose id, name, or description contain ``query`` (case-insensitive)."""
        q = query.lower()
        return [
            p
            for p in self.packs
            if q in p.id.lower() or q in p.name.lower() or q in p.description.lower()
        ]

    def get(self, pack_id: str) -> PackIndexEntry | None:
        """Look up a pack by its exact id."""
        return next((p for p in self.packs if p.id == pack_id), None)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_index_toml(data: bytes | str) -> PackIndex:
    """Parse an index.toml into a :class:`PackIndex`.

    Unknown top-level keys and unknown entry keys are silently ignored.
    """
    raw: dict[str, Any]
    if isinstance(data, str):
        raw = tomllib.loads(data)
    else:
        raw = tomllib.loads(data.decode("utf-8"))

    entries: list[PackIndexEntry] = []
    for item in raw.get("packs", []):
        if not isinstance(item, dict):
            continue
        pack_id = str(item.get("id", "")).strip()
        if not pack_id:
            continue
        scopes_raw = item.get("scopes", [])
        scopes = tuple(str(s) for s in scopes_raw if isinstance(s, str))
        entries.append(
            PackIndexEntry(
                id=pack_id,
                name=str(item.get("name", "")),
                description=str(item.get("description", "")),
                source=str(item.get("source", "")),
                semver=str(item.get("semver", "")),
                scopes=scopes,
                author=str(item.get("author", "")),
                sha256=str(item.get("sha256", "")),
                signature=str(item.get("signature", "")),
            )
        )
    return PackIndex(packs=entries)


# ---------------------------------------------------------------------------
# Fetch and cache
# ---------------------------------------------------------------------------


def _cache_path(state_dir: Path) -> Path:
    return state_dir / INDEX_CACHE_FILENAME


def _is_cache_fresh(cache: Path) -> bool:
    if not cache.exists():
        return False
    import time

    return (time.time() - cache.stat().st_mtime) < INDEX_TTL_SECONDS


def fetch_pack_index(
    state_dir: Path,
    *,
    url: str = DEFAULT_INDEX_URL,
    force: bool = False,
) -> PackIndex:
    """Return the pack index, using a local cache when fresh.

    Args:
        state_dir:  Hachi state directory (cache file lives here).
        url:        URL of the remote ``index.toml``.
        force:      If True, bypass the cache and always re-download.
    """
    cache = _cache_path(state_dir)

    if not force and _is_cache_fresh(cache):
        return parse_index_toml(cache.read_bytes())

    try:
        raw = _download(url)
    except Exception as exc:
        if cache.exists():
            return parse_index_toml(cache.read_bytes())
        raise RuntimeError(f"Cannot fetch pack index from {url}: {exc}") from exc

    state_dir.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    return parse_index_toml(raw)


def _download(url: str) -> bytes:
    """Fetch raw bytes from a pack-index URL with SSRF protection (ADV-005).

    Validates the host (blocks private/loopback/link-local addresses) and refuses
    HTTP redirects so an attacker-controlled open redirect cannot pivot to an
    internal endpoint. Extracted as a seam so ``fetch_pack_index``'s cache/fallback
    logic can be exercised without real network I/O.
    """
    ok, reason = validate_outbound_url(url)
    if not ok:
        raise RuntimeError(f"Pack index URL blocked by security policy: {reason}")

    class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        """Refuse all HTTP redirects to prevent SSRF via open redirect."""

        def redirect_request(  # type: ignore[override]
            self,
            req: urllib.request.Request,
            fp: object,
            code: int,
            msg: str,
            headers: object,
            newurl: str,
        ) -> None:
            raise RuntimeError(
                f"Pack index fetch refused HTTP redirect (code {code}) to {newurl!r}. "
                "Supply a direct URL without redirects."
            )

    opener = urllib.request.build_opener(_NoRedirectHandler)
    req = urllib.request.Request(url, headers={"User-Agent": "hachi/pack-index"})
    with opener.open(req, timeout=10) as resp:  # noqa: S310
        return resp.read()


def load_cached_index(state_dir: Path) -> PackIndex | None:
    """Return the cached index without hitting the network, or None if absent."""
    cache = _cache_path(state_dir)
    if not cache.exists():
        return None
    try:
        return parse_index_toml(cache.read_bytes())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Signature verification (optional)
# ---------------------------------------------------------------------------


def verify_index_entry_sha256(entry: PackIndexEntry, archive_bytes: bytes) -> bool:
    """Return True if the entry's sha256 matches the archive bytes.

    If the entry has no sha256, returns True (no verification required).
    """
    if not entry.sha256:
        return True
    actual = hashlib.sha256(archive_bytes).hexdigest()
    return actual == entry.sha256
