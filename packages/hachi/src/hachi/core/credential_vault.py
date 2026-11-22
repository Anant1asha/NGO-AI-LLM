"""Credential vault backed by OS-native keychain storage with encrypted fallback."""

from __future__ import annotations

import sys
import time

from hachi.core.secret_store import SecretStore, create_default_secret_store

# LOW-013: default TTL for in-memory credential cache (seconds).
# Rotated credentials in the backing store become visible within this window.
_CACHE_TTL_SECONDS: int = 300  # 5 minutes


class CredentialVault:
    def __init__(
        self,
        secret_store: SecretStore | None = None,
        cache_ttl: int = _CACHE_TTL_SECONDS,
    ):
        self._store = secret_store or create_default_secret_store()
        self._cache: dict[str, str] = {}
        # LOW-013: per-key insertion timestamps used for TTL eviction.
        self._cache_ts: dict[str, float] = {}
        self._cache_ttl: int = cache_ttl

    def _is_cache_valid(self, token_key: str) -> bool:
        """Return True if *token_key* is in the cache and has not exceeded TTL."""
        ts = self._cache_ts.get(token_key)
        if ts is None:
            return False
        return (time.monotonic() - ts) < self._cache_ttl

    def get_token(self, token_key: str, prompt_if_missing: bool = False) -> str | None:
        """Retrieve a token by logical key, optionally prompting when missing.

        Args:
            token_key: Logical name of the credential to retrieve.
            prompt_if_missing: When True, fall back to an interactive prompt on TTY.
                Defaults to False. Non-interactive contexts (TUI, gateway, CI) must
                leave this as False and handle a missing credential explicitly.

        Raises:
            ValueError: If the credential is missing and prompt_if_missing is False,
                or if prompt_if_missing is True but stdin is not a TTY.
        """
        # LOW-013: evict stale cache entries on access so rotated credentials are
        # picked up from the backing store within cache_ttl seconds.
        if self._is_cache_valid(token_key):
            cached = self._cache.get(token_key)
            if cached:
                return cached
        else:
            # Entry is expired or absent — remove any stale entry before re-fetching.
            self._cache.pop(token_key, None)
            self._cache_ts.pop(token_key, None)

        token = self._store.get(token_key)
        if token:
            self._cache[token_key] = token
            self._cache_ts[token_key] = time.monotonic()
            return token

        if not prompt_if_missing:
            raise ValueError(f"Credential not found. Run: hachi secrets --set {token_key}")

        if not sys.stdin.isatty():
            raise ValueError("Cannot prompt for credential in non-interactive context")

        formatted_name = (
            token_key.replace("_", " ").title().replace(" Token", "").replace(" Key", "")
        )
        print("\n[Security Vault] Missing credentials detected.")
        print(f"I need your {formatted_name} token to proceed.")
        user_token = input("Paste token value: ").strip()

        if not user_token:
            raise ValueError(f"Required token '{token_key}' was not provided.")

        self.set_token(token_key, user_token)
        print("[Security Vault] Token saved via secure backend. Resuming execution...\n")
        return user_token

    def set_token(self, token_key: str, value: str) -> None:
        self._store.set(
            token_key, value, metadata={"name": token_key, "labels": {"source": "vault"}}
        )
        self._cache[token_key] = value
        self._cache_ts[token_key] = time.monotonic()

    def delete_token(self, token_key: str) -> None:
        self._store.delete(token_key)
        self._cache.pop(token_key, None)
        self._cache_ts.pop(token_key, None)

    def list_token_metadata(self) -> list[dict[str, str]]:
        rows = []
        for entry in self._store.list_metadata():
            rows.append(
                {
                    "name": str(entry.get("name", "")),
                    "backend": str(entry.get("backend", "unknown")),
                }
            )
        return rows

    def clear_all(self) -> int:
        count = 0
        for entry in self._store.list_metadata():
            name = entry.get("name")
            if not name:
                continue
            self._store.delete(name)
            self._cache.pop(str(name), None)
            self._cache_ts.pop(str(name), None)
            count += 1
        return count
