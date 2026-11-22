# T-57 · Consolidate the two OAuth stacks — and fix the one-way token bridge first

|  |  |
|---|---|
| **Source finding** | CF-14 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 (but §3.7 is a real bug — see §5, it can land alone) |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 week (the §3.7 bug fix alone: ~half a day) |
| **Difficulty** | High (needs design judgement — read §5 and §9) |
| **Files you will touch** | `src/hachi/core/oauth.py`, `src/hachi/integrations/oauth_flow.py`, `tests/test_oauth.py`, `docs/bug-bank.md` |

---

## 1. Brief

Hachi has two complete OAuth implementations: `core/oauth.py` (362 lines, loopback
browser flow, used by the agent's Google client) and `integrations/oauth_flow.py`
(870 lines, gateway-redirect connector flow, used by the web UI). Token exchange,
refresh, load, save, authorize-URL construction and callback handling are each
implemented **twice**, and the two stacks store tokens under **different vault key
prefixes**.

A one-line fallback bridges them for *reads* only. That asymmetry is not cosmetic: the
first time the agent silently refreshes a web-UI-authenticated token, the two stores
permanently diverge (§3.7). When you are done, refresh writes back to the key it read
from, and the duplicated primitives have one canonical implementation.

## 2. Why this matters

Two OAuth stacks means every OAuth bug gets fixed once and remains broken once. It
already happened: BB-10 patched the read path (`core/oauth.py:210-214`) and BB-11
patched capability enablement (`gateway/orchestrator.py:313-322`), and both are
*one-directional* patches over the same underlying split. Neither fixed the write path,
because the write path's brokenness is invisible until a token expires — an hour after
anyone would be testing.

Credentials are the highest-consequence state in the product. A user who clicks
"Disconnect" in the web UI has made a security decision, and the system must actually
carry it out — today it deletes one of the two copies (§3.8). If your fix leaves two
key namespaces holding two independently-aged copies of the same Google grant, you have
not fixed this.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The duplicated primitives

| Concern | `core/oauth.py` (362 L) | `integrations/oauth_flow.py` (870 L) |
|---|---|---|
| Token exchange | `OAuthManager._exchange_token` `:150` | `_exchange_code` `:448` |
| Refresh | `OAuthManager._refresh_google_token` `:340` | `_refresh_token` `:530` |
| Load | `OAuthManager.get_token` `:201` | `OAuthTokenStore.load` `:191` |
| Save | `OAuthManager.save_token` `:222` | `OAuthTokenStore.save` `:204` |
| Authorize URL | `_run_google_browser_flow` `:265` | `_build_authorize_url` `:421` |
| Callback | `OAuthCallbackHandler` `:82` (local `BaseHTTPRequestHandler`) | `oauth_callback` `:642` (gateway route) |
| Key naming | `_key` `:137` → `"oauth.<provider>"` | `_token_key` `:174` → `"oauth2.<connector>"` |

The key-naming divergence is the root of everything below:

```python
    @staticmethod                        # core/oauth.py:136-138
    def _key(provider: str) -> str:
        return f"oauth.{provider}"
```

```python
_TOKEN_KEY_PREFIX = "oauth2."            # integrations/oauth_flow.py:171

def _token_key(connector_id: str) -> str:    # :174-175
    return f"{_TOKEN_KEY_PREFIX}{connector_id}"
```

### 3.2 Bridge 1 — BB-10, a read-only fallback (`core/oauth.py:210-214`)

```python
        raw = self._store.get(self._key(provider))
        if not raw:
            # BB-10: web UI stores tokens under "oauth2.<provider>"; fall back
            # so web-authenticated sessions are visible to the agent.
            raw = self._store.get(f"oauth2.{provider}")
```

### 3.3 Bridge 2 — BB-11, force-enable a capability (`gateway/orchestrator.py:313-322`)

```python
        # BB-11: if the config flag is off but the user already connected via the web UI
        # (token stored under "oauth2.<cap_id>"), treat the capability as enabled so
        # tools are registered without requiring a manual config edit or re-auth.
        if not enabled:
            try:
                from hachi.integrations.oauth_flow import OAuthTokenStore

                enabled = OAuthTokenStore().is_connected(cap_id)
            except Exception:
                pass
```

### 3.4 Which stack is actually live

Both. This is not a dead-code cleanup.

- `core/oauth.py` is the **agent's** path: `OAuthManager` is constructed at
  `integrations/google/client.py:40` and `get_google_credentials` is called at
  `client.py:55` and `:244`, plus `cli/main.py:4390`/`:4411` for `hachi google-auth`.
- `integrations/oauth_flow.py` is the **web UI's** path: `oauth_start` `:609`,
  `oauth_callback` `:642`, `oauth_disconnect` `:672`, `connector_status` `:698`.

### 3.5 …with one exception: `_refresh_token` is dead

`grep -rn "_refresh_token" src/` returns exactly **one** hit — the definition at
`integrations/oauth_flow.py:530`. **Zero callers.** The connector stack never refreshes
a token. Only `core/oauth.py`'s `_refresh_google_token` runs in production, and it is
reached from the agent's Google client.

This matters for §3.7: it means there is exactly one live refresh path, and it writes
to exactly one prefix.

### 3.6 What `is_connected` actually checks

```python
    def is_connected(self, connector_id: str) -> bool:      # oauth_flow.py:222-224
        """Return True iff a token is stored (does not validate expiry)."""
        return self.load(connector_id) is not None
```

Presence only. `connector_status` (`:698`) consumes it at `:747`:

```python
    if connector.auth_type == "oauth2":
        connected = _token_store.is_connected(connector_id)
```

### 3.7 ⚠️ NEW BUG the review missed — the bridge is ONE-WAY and forks token state

`get_token` reads `oauth2.*` as a fallback (§3.2). But `_refresh_google_token`
(`core/oauth.py:340-362`) writes back via `save_token` at `:360`:

```python
        old_token_data["expires_at"] = time.time() + data.get("expires_in", 3600)
        self.save_token("google", old_token_data)
```

and `save_token` (`:222-231`) **always** targets `self._key(provider)` — the `oauth.`
prefix, unconditionally:

```python
    def save_token(self, provider: str, token_data: dict):
        """Save a token to secure storage with metadata."""
        metadata = {
            "name": self._key(provider),
            ...
        }
        self._store.set(self._key(provider), json.dumps(token_data), metadata=metadata)
```

**The read falls back; the write never does.** Trace the lifecycle:

1. User connects Google in the web UI → `oauth_callback` → `_token_store.save`
   (`oauth_flow.py:667`) → vault key **`oauth2.google`**.
2. Agent needs Google → `GoogleClient` (`integrations/google/client.py:40`) →
   `OAuthManager.get_token("google")` → miss on `oauth.google` → BB-10 fallback reads
   **`oauth2.google`**. Works.
3. Token expires (~1 h) → `get_google_credentials` refreshes →
   `_refresh_google_token` → `save_token` → writes **`oauth.google`**.
4. From now on step 2 hits `oauth.google` first and **never reads `oauth2.google`
   again**. That copy is frozen at its step-1 value forever — and §3.5 proves nothing
   else will ever refresh it.

The two stores now hold two different tokens for the same grant, with different
`expires_at` values, and no code reconciles them. Because `is_connected` only tests
presence (§3.6), the web UI keeps rendering "connected" and never notices — so this
does not visibly break the status pill. What it breaks is *coherence*: everything that
inspects the `oauth2.*` copy is looking at a stale snapshot.

### 3.8 The disconnect consequence

`oauth_disconnect` (`integrations/oauth_flow.py:672-695`) revokes and deletes exactly
one key:

```python
    token_data = _token_store.load(connector_id)
    if token_data is not None and connector.revoke_url:
        _revoke_token(connector, token_data)

    _token_store.delete(connector_id)
```

`_token_store` is the `oauth2.*` store. After the §3.7 fork, "Disconnect" revokes the
**stale** token and deletes the **stale** copy, leaving the agent's live copy sitting
in the vault under `oauth.google`. Whether the agent can still *use* it depends on
whether the provider treats the revocation as grant-wide — but the local credential
the user asked to remove is still on disk either way. Be precise about this in the bug
bank entry: the verified claim is "the copy is not deleted", not "the agent keeps
working".

## 4. Reproduce the failure

The fork is provable by code reading and by a unit test; it is **not** cleanly
reproducible from a shell, because triggering it requires a real expired Google token.
Say so rather than inventing a command.

```bash
# 1. The read has a fallback. Expect: one hit, the BB-10 comment block.
grep -n "oauth2\." src/hachi/core/oauth.py

# 2. The write has none. Expect: every store.set target is self._key(...).
grep -n "_store.set\|def save_token\|def _key" src/hachi/core/oauth.py

# 3. Only one refresh path is live. Expect: exactly ONE hit — the definition.
grep -rn "_refresh_token" src/ --include=*.py

# 4. Both stacks are otherwise live.
grep -rn "OAuthManager\|OAuthTokenStore" src/ --include=*.py | grep -v "^src/hachi/core/oauth.py\|^src/hachi/integrations/oauth_flow.py"
```

**You will see now:** (1) the fallback read at `:214`; (2) a single `self._store.set`
at `:231` keyed on `_key(provider)` with no fallback branch; (3) one hit — the dead
`_refresh_token` definition; (4) `OAuthManager` in `integrations/google/client.py` and
`cli/main.py`, `OAuthTokenStore` in `gateway/orchestrator.py`.

Combined with the §3.7 trace, that proves the write-back lands on the other key.

**You should see after the fix:** grep (2) shows `save_token` resolving the key it
actually loaded from, and the new test in §7 passing.

**The decisive proof is the §7 test**, which drives the real `OAuthManager` against an
in-memory secret store and asserts on the store's keys after a refresh. Write it first.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> This task has **two halves with different risk profiles**, and you should decide up
> front whether to ship them together.
>
> **Half A — fix the one-way bridge (§3.7).** Small, testable, no cross-module
> refactor, and it stops credential state from forking today. **Recommendation: land
> this first, as its own commit**, even if half B slips. It is a bug fix under
> [CLAUDE.md](../../../../CLAUDE.md) Rule 2 and deserves its own failing test and its
> own bug-bank entry.
>
> **Half B — consolidate the stacks.** Pick one:
>
> **(b1) `oauth_flow` primitives canonical — RECOMMENDED, and the review's own call.**
> `core/oauth.py` keeps its loopback browser flow (which `oauth_flow` genuinely does
> not have) but delegates *storage* to `OAuthTokenStore` and *exchange* to
> `_exchange_code`. One key namespace: `oauth2.*`. One-time migration reads any
> surviving `oauth.<p>` and rewrites it.
> *For:* `oauth_flow` is the newer, better-factored stack — it has a state store with
> TTL (`OAuthStateStore` `:114`), a connector registry, revocation, and a separate
> apikey namespace (`_apikey_vault_key` `:238`). *Against:* `core/oauth.py` is on the
> agent's hot path via `integrations/google/client.py`; a storage change there is felt
> by every Google tool call.
>
> **(b2) `core/oauth.py` canonical.** *Against:* it is Google-only by construction
> (`_google_client_id` `:72`, `_require_google_client_id` `:141`, `get_google_credentials`
> `:233`) and has no connector abstraction. You would be re-adding what `oauth_flow`
> already has. Do not choose this.
>
> **(b3) Leave both, formalise the bridge.** Make the fallback bidirectional and
> document the two namespaces as intentional. *For:* smallest diff. *Against:* this is
> exactly the "generational layering" CF-14 names, and it doubles the surface every
> future OAuth change must touch. Acceptable only as an explicit, dated interim.
>
> **Recommendation: A now, then b1.** The rest of this spec assumes it.

Target state — half A:

1. `OAuthManager` remembers which key satisfied the read, and writes back to it:

   ```python
   def _resolve_key(self, provider: str) -> str:
       """Return the vault key holding this provider's token.

       Prefers the agent prefix ("oauth.<p>"); falls back to the web-UI prefix
       ("oauth2.<p>") when only that one exists (BB-10). Returns the agent
       prefix when neither exists, so a fresh authorisation lands there.
       """
   ```

   `get_token` and `save_token` both route through it. The invariant to hold:
   **a refresh writes to the key the token was read from.** No new prefix, no dual
   write, no copying between namespaces — one key per grant.

2. Non-goal for half A: unifying the prefixes. That is half B, and doing it here
   makes the regression test unable to distinguish "fixed" from "moved".

Target state — half B (b1): `core/oauth.py` keeps `_build_pkce` (`:192`),
`OAuthCallbackHandler` (`:82`) and `_run_google_browser_flow` (`:265`); its
`_exchange_token` / `get_token` / `save_token` / `_key` are deleted in favour of
`oauth_flow`'s. `_refresh_token` (`oauth_flow.py:530`) — currently dead — becomes the
single live refresh, and `_refresh_google_token` is deleted.

## 6. Steps

**Half A (do this first, commit separately):**

1. Write `test_refresh_writes_back_to_the_key_it_read_from` from §7 and watch it **fail**.
2. Add `OAuthManager._resolve_key(provider)` implementing the §5 rule.
3. Route `get_token` (`core/oauth.py:201`) through it, preserving the BB-10 behaviour
   exactly — `tests/test_oauth.py:185` (`test_get_token_finds_web_ui_oauth2_prefix`)
   must keep passing untouched.
4. Route `save_token` (`:222`) through it, including the `metadata["name"]` field at
   `:225` — that name is what shows up in vault listings, so a mismatch there is a
   quiet UX bug.
5. Run the new test — it must now pass. Run `uv run pytest tests/test_oauth.py -q`.
6. Add the bug-bank entry (§11) and commit: `fix(oauth): refresh writes back to the key it read from`.

**Half B (separate commits, one primitive at a time):**

7. Delete the dead `_refresh_token` (`oauth_flow.py:530`) **or** wire it as the single
   refresh — do not leave it dead after touching this file (§9 has the caveat).
8. Replace `OAuthManager`'s storage calls with `OAuthTokenStore`, then delete `_key`.
9. Replace `_exchange_token` with `_exchange_code`, keeping `_exchange_token`'s
   superior error messages (`core/oauth.py:162-189` decodes `invalid_client` /
   `redirect_uri_mismatch` / `invalid_grant` into actionable hints — that is real user
   value, do not drop it).
10. One-time migration on read: if `oauth.<p>` exists and `oauth2.<p>` does not, copy
    and delete. Put it behind an explicit function with its own test.
11. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_oauth.py` (**existing** — add beside
  `test_get_token_finds_web_ui_oauth2_prefix` at `:185`, which is this bug's sibling)
- **Test name:** `test_refresh_writes_back_to_the_key_it_read_from`
- **It must assert:** the real, observed vault contents after a refresh — that the key
  the token was loaded from now holds the *new* access token, and that no second,
  divergent copy was created. Assert on `_MemorySecretStore._items`, not on a mock's
  call args: the finding is about which key ends up holding what.
- **It must FAIL before your fix** with something like
  `AssertionError: token under 'oauth2.google' is stale: got 'ya29.web-ui-token', expected 'ya29.refreshed'`
  — because today the refresh lands on `oauth.google` and leaves `oauth2.google` at its
  original value.

```python
# sketch — adapt to the repo's existing fixtures (_MemorySecretStore is at tests/test_oauth.py:11)
import json
import time


def test_refresh_writes_back_to_the_key_it_read_from(monkeypatch) -> None:
    """A refresh must update the key the token was loaded from.

    Regression: get_token() fell back to the web-UI prefix "oauth2.<p>" (BB-10)
    but save_token() always wrote "oauth.<p>". After the first silent refresh of a
    web-UI-authenticated token the two vault keys held two different tokens with
    two different expiries, and nothing ever reconciled them.
    """
    store = _MemorySecretStore()
    stale = {
        "access_token": "ya29.web-ui-token",
        "refresh_token": "1//refresh",
        "scope": "openid email",
        "expires_at": time.time() - 3600,        # already expired
    }
    store.set("oauth2.google", json.dumps(stale))

    monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: "cid")
    monkeypatch.setattr("hachi.core.oauth._google_client_secret", lambda: None)
    monkeypatch.setattr(
        OAuthManager,
        "_exchange_token",
        staticmethod(lambda payload: {"access_token": "ya29.refreshed", "expires_in": 3600}),
    )

    manager = OAuthManager(secret_store=store)
    token = manager.get_google_credentials(["openid", "email"])
    assert token == "ya29.refreshed"

    refreshed = json.loads(store.get("oauth2.google") or "{}")
    assert refreshed.get("access_token") == "ya29.refreshed", (
        "token under 'oauth2.google' is stale: the refresh wrote to a different key, "
        "forking credential state between the agent and the web UI."
    )
    # And it must not have created a second, divergent copy.
    assert store.get("oauth.google") is None, (
        "refresh created a second copy under 'oauth.google'; one grant must live "
        "under exactly one vault key."
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Two things commonly make it pass for the wrong reason: (a) the scopes check at
> `core/oauth.py:242-247` short-circuits and never refreshes — make sure `expires_at`
> is in the past *and* the requested scopes are a subset of the stored `scope` string;
> (b) `_exchange_token` is a `@staticmethod`, so patch it as one.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and it failed before the fix.
- [ ] `tests/test_oauth.py::test_get_token_finds_web_ui_oauth2_prefix` still passes, **unmodified**.
- [ ] After a refresh, exactly one vault key holds the grant — verified by asserting the other key is absent, not by inspection.
- [ ] `grep -n "_store.set" src/hachi/core/oauth.py` shows the key coming from the resolver, not from `_key(provider)` directly.
- [ ] (Half B only) `grep -rn "_refresh_token" src/` no longer shows a definition with zero callers.
- [ ] (Half B only) `grep -rn '"oauth\.' src/hachi/` shows no remaining token-key construction (the two `cli/main.py:4703`/`:4712` hits are *event names*, not vault keys — leave them).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not "fix" `oauth_disconnect` to also delete `oauth.google` (§3.8).** It is the
  obvious adjacent thing and it is the wrong fix: once half A lands there is only one
  key per grant and the extra delete becomes dead defensive code. If half B slips past
  a release, file it separately with its own test.
- **Do not extend the BB-11 bridge** (`gateway/orchestrator.py:313-322`). Making
  capability enablement also consult `oauth.*` deepens the coupling this task is
  removing. Leave it; it becomes correct for free once there is one namespace.
- **Do not touch the apikey namespace.** `_apikey_vault_key` (`oauth_flow.py:238-252`)
  is deliberately separate from `oauth2.*` and its docstring says why. It is not part
  of this finding.
- **Do not delete `OAuthCallbackHandler` or `_run_google_browser_flow`.** The loopback
  flow is the only way `hachi google-auth` works headless-CLI; `oauth_flow` cannot
  replace it (it needs a running gateway to receive the redirect).
- **Do not drop `_exchange_token`'s error hints** (`core/oauth.py:171-189`) when
  collapsing onto `_exchange_code`. Those messages turn an opaque 400 into an
  actionable instruction; losing them is a real regression that no test will catch.
- **Do not rotate or re-issue any real credential** while testing. Use
  `_MemorySecretStore`.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Run the **full** suite. Credential resolution is reached from the Google integration,
the CLI, capability registration at boot (`gateway/orchestrator.py:320`) and the
connector status endpoints — `tests/test_oauth.py`, `tests/test_oauth_integrations.py`
and `tests/test_google_integrations.py` all touch it, and boot-time capability
enablement is exercised well outside those three. Report the **actual** pass/fail
counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — OAuth refresh wrote to a different vault key than it read from

- **Symptom:** After a user connected Google in the web UI, the agent worked — then, roughly an hour later (first token refresh), the web UI's copy of the token silently froze. The vault held two tokens for one grant with two different `expires_at` values, and "Disconnect" in the web UI revoked and deleted only the stale one, leaving the agent's copy on disk.
- **Root cause:** Two OAuth stacks with two key prefixes: `core/oauth.py` `_key()` → `oauth.<p>`, `integrations/oauth_flow.py` `_token_key()` → `oauth2.<p>`. BB-10 added a *read* fallback in `get_token` (`core/oauth.py:214`) but `save_token` (`:231`) always wrote `_key(provider)`. So `_refresh_google_token`'s write-back (`:360`) landed on the other key. Nothing refreshed the `oauth2.*` copy afterwards — `oauth_flow._refresh_token` has zero callers.
- **Fix:** `OAuthManager` resolves the key once (`_resolve_key`) and both `get_token` and `save_token` use it, so a refresh updates the key the token was read from. One grant, one key.
- **Avoid:** a read fallback without a matching write fallback forks state. If you add a compatibility read for a second storage key, fix the write in the same commit — or the bug reappears on the first mutation, hours later, where no one is looking.
- **Locked by:** `tests/test_oauth.py` — `test_refresh_writes_back_to_the_key_it_read_from`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-2 / credentials are lazy.** No interactive credential prompt may run at Textual
  boot, and there is no `.env` autoload in the core import path. `core/oauth.py` already
  respects this via `_resolve_env` (`:44`) / `_read_dotenv_value` (`:27`) at *call* time.
  Do not hoist credential resolution to module import while refactoring.
- **`_google_client_id()` is read late on purpose** — `tests/test_oauth.py:118`
  (`test_client_id_set_after_import_is_resolved`) pins that a client id set *after*
  import is still picked up. A refactor that caches it at construction breaks that test,
  and the test is right.
- **`_token_store` is a module-level singleton** (`oauth_flow.py:228`). Tests that need
  an isolated store must construct `OAuthTokenStore(secret_store=...)` explicitly rather
  than relying on patching the singleton — and anything you move onto that singleton
  inherits the same test-isolation problem.
- **Import layering:** `pyproject.toml` `[tool.importlinter]` forbids `hachi.core` and
  `hachi.integrations` from importing `hachi.gateway`. `core/oauth.py` importing
  `hachi.integrations.oauth_flow` is a **core → integrations** edge — check the
  contracts before you add it; the existing bridge at `gateway/orchestrator.py:318`
  deliberately sits in the gateway layer, pointing downward, for exactly this reason.
- **The expiry check has a 60 s skew buffer** (`core/oauth.py:247`:
  `time.time() < token_data.get("expires_at", 0) - 60`). A test token that expires
  "now" will not trigger a refresh — push `expires_at` comfortably into the past.
