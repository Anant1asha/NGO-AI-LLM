# T-58 · Retire `IntegrationRuntime`; make `UniversalRestAdapter` the one declarative-integration mechanism

|  |  |
|---|---|
| **Source finding** | CF-14 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High (needs design judgement — read §5 and §9) |
| **Files you will touch** | `src/hachi/core/integrations.py`, `src/hachi/gateway/orchestrator.py`, `src/hachi/core/rest_adapter.py`, `tests/test_integration_runtime_credentials.py` (new), `docs/bug-bank.md` |
| **See also** | `T-72-og-spec-executable-surface.md` — `role=env` is one of the undocumented executable `.og` tags |

---

## 1. Brief

Three mechanisms turn declarative `.og` content into live tools: the legacy
`IntegrationRuntime` (`core/integrations.py`, 319 lines), the native integrations
package (`src/hachi/integrations/`), and `UniversalRestAdapter`
(`core/rest_adapter.py`, 359 lines). All three are constructed at every session boot.

The legacy one **handles credentials in plaintext**: it parses `KEY=VALUE` lines out of
an `.og` file's `::dense` block into a flat in-memory dict and hands them to
`smtplib.login()`. It has no vault, no redaction, no secret store, and it reports
failures with bare `print()`. When you are done, that mechanism is gone or fenced, and
declarative integrations resolve credentials through `CredentialVault` like the REST
adapter already does.

## 2. Why this matters

**Retire it because of the credential handling, not because three is more than one.**
That framing decides the fix: a consolidation that preserves the plaintext `_env` dict
"for compatibility" has missed the point entirely.

`UniversalRestAdapter` already demonstrates what good looks like in this exact
codebase: it takes a `CredentialVault` (`core/rest_adapter.py:73`), interpolates
`{token_name}` placeholders from the vault into headers at request time
(`:240-244`), refuses to interpolate a secret into a URL (`:237-238`), and strips
provider-secret patterns out of outbound params and bodies via
`_redact_mapping_secrets` (`:30-50`). `IntegrationRuntime` predates all of that and
never caught up — the same repo, two eras, both live.

Secondly: `IntegrationRuntime` is the reason `role=env` exists as an executable `.og`
tag, and that tag is **completely absent from the spec** (see
`T-72-og-spec-executable-surface.md`). So today a `.og` file can carry live SMTP
credentials in cleartext, be loaded automatically by any pack install, and no spec a
reviewer could read would tell them that block is executable.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The three mechanisms

| Mechanism | Anchor | Lines | Credentials |
|---|---|---:|---|
| Legacy `IntegrationRuntime` | `core/integrations.py:32` | 319 | **plaintext dict from `.og`** |
| Native integrations | `src/hachi/integrations/` | — | `CredentialVault` / `SecretStore` |
| `UniversalRestAdapter` | `core/rest_adapter.py:64` | 359 | `CredentialVault` |

### 3.2 The plaintext credential store — `core/integrations.py:39-43`

```python
    def __init__(self):
        self._env: dict[str, str] = {}  # Flat key-value credential store
        self._connections: dict[str, Any] = {}  # integration_name -> live connection object
        self._handlers: dict[str, Callable] = {}  # integration_name -> callable tool function
        self._integration_nodes: dict[str, OGNode] = {}
```

Filled by `load_env_node` (`:49-63`), which splits `KEY=VALUE` straight out of a
`role=env` node's `::dense` block:

```python
    def load_env_node(self, node: OGNode):
        """
        Ingest credentials from a role=env node's ::dense block.
        Parses key=value pairs and merges them into the flat credential store.
        ...
        """
        for line in node.dense.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                self._env[key.strip()] = value.strip()
```

Read back raw by `get_credential` (`:65-75`):

```python
    def get_credential(self, key: str) -> str | None:
        ...
        return self._env.get(key)
```

**No vault. No redaction. No secret store.** And it is not theoretical — `_setup_smtp`
(`:142-173`) uses it to authenticate:

```python
        email_address = self._env.get(email_key, "")
        password = self._env.get(password_key, "")

        if not email_address or not password:
            return False

        # Establish persistent SMTP connection
        server = smtplib.SMTP(host, port, timeout=30)
        if use_tls:
            server.starttls()
        server.login(email_address, password)
```

So a mail password lives in cleartext in an `.og` file on disk, in a plain dict in
process memory, and passes through `smtplib.login`.

### 3.3 It runs on every boot — `gateway/orchestrator.py:2818-2827`

This is **not** dead code:

```python
    # 3. Initialize the Integration Runtime (direct SMTP/HTTP connections)
    integrations = IntegrationRuntime()
    integration_count = 0

    for node in skill_engine.get_nodes_by_role("env"):
        integrations.load_env_node(node)

    for node in skill_engine.get_nodes_by_role("integration"):
        if integrations.setup_integration(node):
            integration_count += 1
```

The `skill_engine` has already globbed `**/*.og` under the skills dir
(`og_engine/engine.py:551`, invoked at `gateway/orchestrator.py:2804`), so **any**
`.og` file anywhere in the tree — including one installed by a pack — contributes
`env` and `integration` nodes to this loop. Cross-reference
[T-56](T-56-pack-consent-every-install-path.md): today one of the install paths that
feeds this loop has no consent gate at all.

`IntegrationRuntime` is referenced from exactly three places in `src/`:
`gateway/orchestrator.py:37` (import), `:525` (a `BootDeps`-style parameter), and
`:2819` (construction). That bounds the blast radius.

### 3.4 `print()` instead of logging — 5 sites in `core/integrations.py`

```
:101-103   print(f"  [integration] Unknown type '{integration_type}' for {node.name}, skipping.")
:106       print(f"  [integration] Failed to setup {node.name}: {e}")
:208       print(f"  [smtp] {node.name} connected as {email_address}")
:228       print(f"  [http] Missing base_url for {node.name}.")
:273       print(f"  [http] {node.name} connected to {base_url}")
```

`:208` prints an email address to stdout at every boot. Under the Textual TUI, stray
stdout writes corrupt the render; in the gateway they land wherever the process's
stdout goes, uncontrolled by the logging config. And `:105-107` swallows *every*
exception during setup into a printed line and a `False` return — a broken integration
degrades silently, which is the CF-1 pattern.

### 3.5 What the good mechanism does instead

`UniversalRestAdapter.__init__` (`core/rest_adapter.py:70-81`) takes a vault; it is
constructed with a real one at `gateway/orchestrator.py:3108-3109`:

```python
    credential_vault = CredentialVault(secret_store=secret_store)
    rest_adapter = UniversalRestAdapter(tool_registry, credential_vault)
```

Secrets are resolved **at request time**, never stored in the adapter
(`core/rest_adapter.py:240-247`):

```python
                            if self.vault:
                                vault_val = self.vault.get_token(vault_key)
                                if vault_val:
                                    v = v.replace(f"{{{vault_key}}}", vault_val)
                                    secret_interpolated = True
```

and `_redact_mapping_secrets` (`:30-50`) strips provider-secret patterns out of any
params/body the model constructed. Same repo. Same layer. Different decade.

### 3.6 The spec says nothing about any of it

```bash
grep -c "role=env\|::api\|::tool\|::config" docs/reference/objectgraph-spec.md   # -> 0
```

Zero. The tags `IntegrationRuntime` and `UniversalRestAdapter` both execute are
undocumented. That is the whole of `T-72-og-spec-executable-surface.md`; this task
supplies the "and one of them takes cleartext passwords" half of the argument.

## 4. Reproduce the failure

The credential handling is provable from a shell; the *consequence* needs a test.

```bash
# 1. No vault, no redaction, no secret store in the legacy runtime. Expect: no hits.
grep -n "vault\|Vault\|secret_store\|redact" src/hachi/core/integrations.py

# 2. The good one has all three. Expect: many hits.
grep -c "vault\|Vault\|redact" src/hachi/core/rest_adapter.py

# 3. print() instead of logging. Expect: 5 hits, no logger.
grep -n "print(" src/hachi/core/integrations.py
grep -c "logging\|logger" src/hachi/core/integrations.py

# 4. It is live, not dead. Expect: import + param + construction in the boot path.
grep -rn "IntegrationRuntime" src/ --include=*.py
```

**You will see now:** (1) **nothing** — the legacy runtime has no credential
infrastructure at all; (2) a double-digit count; (3) five `print()` calls and **zero**
logging references; (4) three hits, all in `gateway/orchestrator.py`, including the
construction at `:2819` inside `boot_agent`.

**You should see after the fix:** grep (1) returns vault usage (or the module is gone),
and grep (3) returns no `print(`.

**End-to-end confirmation is not worth building.** Exercising `_setup_smtp` for real
means standing up an SMTP server and putting a live password in a test fixture — do not
do that. The §7 test drives `load_env_node` / `get_credential` directly, which is where
the defect actually lives.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> `IntegrationRuntime` supports two types: `smtp` and `http` (`setup_integration`,
> `core/integrations.py:92-99`). `UniversalRestAdapter` can replace the `http` half
> outright — it is strictly better at exactly that job. It **cannot** replace `smtp`:
> there is no HTTP under an SMTP conversation. So decide what happens to SMTP:
>
> **(a) Delete the runtime; move SMTP credentials to the vault — RECOMMENDED.**
> `role=integration type=http` nodes are handled by `UniversalRestAdapter`;
> `type=smtp` keeps a small dedicated handler, but `auth_password_key` resolves through
> `CredentialVault.get_token()` instead of the `.og`-sourced `_env` dict. `role=env`
> nodes stop being a credential source and are either ignored with a loud deprecation
> warning or rejected outright.
> *For:* kills the plaintext path, keeps the capability, one credential story across
> all declarative integrations. *Against:* it is a **breaking change** for any user
> whose `env.og` currently holds a working SMTP password — they must re-enter it. That
> needs a migration message, not silence (see §6 step 6).
>
> **(b) Keep the runtime, swap only its credential source.** Leave `load_env_node`
> parsing but have it *store into the vault* rather than a dict, and have
> `get_credential` read from the vault.
> *For:* smallest behavioural change; no user re-entry. *Against:* it **imports
> cleartext from a file into the vault**, which makes the `.og` file the durable
> plaintext source of truth. That is worse than the status quo — it launders the
> problem. Do not choose this.
>
> **(c) Fence it: keep the runtime, but refuse `role=env` credentials from any file
> outside the user's own skills root** (i.e. reject them from installed packs).
> *For:* removes the pack-supplied-credential attack surface without breaking existing
> local setups; ships in a day. *Against:* the plaintext-on-disk problem remains for
> the user's own files.
>
> **Recommendation: (a), with (c) as the interim if you cannot ship the migration in
> this cycle.** The rest of this spec assumes (a). If you choose otherwise, say so in
> the commit message and adapt §6/§7.

Target state:

1. `role=env` is no longer a credential source. `load_env_node` either disappears or
   becomes:

   ```python
   def load_env_node(self, node: OGNode) -> None:
       """DEPRECATED — role=env credential blocks are no longer honoured.

       Credentials must live in the credential vault. Emits a warning naming the
       offending file so the user can migrate, and stores nothing.
       """
   ```

   The warning must go through `logging`, and must **not** echo the values.

2. SMTP credentials resolve through the vault:

   ```python
   class IntegrationRuntime:
       def __init__(self, vault: CredentialVault | None = None) -> None:
           self._vault = vault
   ```

   `_setup_smtp` (`:142`) reads `auth_password_key` from `self._vault.get_token(...)`,
   mirroring `rest_adapter.py:241`.

3. `type=http` integrations are handled by `UniversalRestAdapter`. The `_setup_http`
   path (`:228-273`) is deleted, not duplicated.

4. All five `print()` calls become `logger.debug` / `logger.warning`, and the
   swallow-everything `except Exception` at `:105-107` logs with `exc_info=True` instead
   of printing the bare message. `:208` must stop printing the email address entirely.

5. `gateway/orchestrator.py:2819` constructs the runtime **with** the credential vault.
   Note the ordering problem: the vault is currently built at `:3108`, ~290 lines
   *after* the runtime at `:2819`. Moving the vault construction earlier is part of the
   work; do not create a second `CredentialVault`.

6. Observable outcome: a `.og` file containing a `role=env` node with a password does
   not put that password anywhere except a log line saying it was ignored.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. Add a `logger = logging.getLogger(__name__)` to `core/integrations.py` and convert
   all five `print()` sites (§3.4). Drop the email address from `:208`. Commit this
   alone — it is independently reviewable and independently valuable.
3. Move the `CredentialVault` construction in `gateway/orchestrator.py` from `:3108` to
   before `:2819`, and thread it into `IntegrationRuntime(...)`. Verify nothing between
   those lines depends on the vault *not* existing yet.
4. Change `_setup_smtp` (`:142-173`) to resolve `auth_email_key` / `auth_password_key`
   through the vault, falling back to **nothing** — not to `_env`.
5. Make `load_env_node` a no-op that warns, naming the source file. Keep the method and
   its docstring history (Rule 3: don't delete comments) — mark it deprecated in place.
6. Emit a one-time, actionable migration message at boot when an ignored `role=env`
   node is found: which file, which keys, and the exact command to store them in the
   vault. A silent break here is the CF-1 failure mode.
7. Delete `_setup_http` (`:228-273`) and route `type=http` through the existing
   `rest_apis` registration. Confirm with `grep -rn "type.*http" tests/` that no test
   depends on the deleted handler before you remove it.
8. Run the regression test — it must now pass.
9. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_integration_runtime_credentials.py` (**new**)
- **Test names:** `test_role_env_node_is_not_a_credential_source` and
  `test_integration_runtime_emits_no_stdout`
- **It must assert:** the real, observed behaviour — that a password present in a
  `role=env` node's `::dense` block is **not** retrievable from the runtime afterwards,
  and that setup writes nothing to stdout. Assert on `get_credential`'s return value and
  on `capsys`, not on a mock.
- **It must FAIL before your fix** with:
  - test 1: `AssertionError: role=env node leaked 'hunter2' into the runtime's credential store`
  - test 2: `AssertionError: IntegrationRuntime wrote to stdout: '  [integration] Unknown type ...'`

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

from hachi.core.integrations import IntegrationRuntime
from hachi.og_engine.parser import OGNode


def _env_node() -> OGNode:
    """A role=env node carrying a secret in its ::dense block."""
    return OGNode(
        name="creds",
        role="env",
        dense="GMAIL_ADDRESS=me@example.com\nGMAIL_APP_PASSWORD=hunter2\n",
    )


def test_role_env_node_is_not_a_credential_source() -> None:
    """A password in a .og file must never become a live credential.

    Regression: load_env_node() split KEY=VALUE out of a role=env node's ::dense
    block into a plain dict (`self._env`), and _setup_smtp passed the result
    straight to smtplib.login(). No vault, no redaction, no secret store — and
    the boot path loads EVERY .og under the skills dir, including pack-installed
    ones.
    """
    runtime = IntegrationRuntime()
    runtime.load_env_node(_env_node())

    leaked = runtime.get_credential("GMAIL_APP_PASSWORD")
    assert leaked is None, (
        f"role=env node leaked {leaked!r} into the runtime's credential store. "
        "Credentials must come from the CredentialVault, not from a .og file."
    )


def test_integration_runtime_emits_no_stdout(capsys) -> None:
    """Integration setup must log, not print (TUI-safe, config-controlled)."""
    runtime = IntegrationRuntime()
    node = OGNode(name="thing", role="integration", config={"type": "nonsense"})
    runtime.setup_integration(node)

    captured = capsys.readouterr()
    assert captured.out == "", (
        f"IntegrationRuntime wrote to stdout: {captured.out!r}. "
        "Stray stdout corrupts the Textual TUI render and escapes the logging config."
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Check the `OGNode` constructor signature against `og_engine/parser.py` first — if
> `dense` / `config` are not constructor kwargs in this version, build the node through
> the parser instead of hand-constructing it, and say so in a comment.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_role_env_node_is_not_a_credential_source` failed before the fix.
- [ ] `grep -n "print(" src/hachi/core/integrations.py` returns **nothing**.
- [ ] `grep -n "self._env" src/hachi/core/integrations.py` returns nothing, or only a deprecation shim that stores nothing.
- [ ] `_setup_smtp` resolves credentials via `CredentialVault`, and there is exactly **one** `CredentialVault(...)` construction in `gateway/orchestrator.py`.
- [ ] A boot that encounters a `role=env` node logs an actionable migration warning naming the file — and does **not** log the values.
- [ ] `grep -n "_setup_http" src/hachi/core/integrations.py` returns nothing (option (a)).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch `src/hachi/integrations/` (the native package).** It is the third
  mechanism named in CF-14 and it is the adjacent thing you will drift into — it is
  also the *correct* one, already on the vault, and it is where the OAuth consolidation
  lands ([T-57](T-57-oauth-consolidation.md)). Two people editing that package in the
  same cycle is how you get a merge conflict on a credential path. Stay in
  `core/integrations.py` and the one boot block that constructs it.
- **Do not update `docs/reference/objectgraph-spec.md` here.** Documenting `role=env`
  is `T-72-og-spec-executable-surface.md`, and the spec decision (document the tag vs.
  mark it internal) should be made once, for all the executable tags together — not
  incidentally, by whoever happens to be deleting a credential path. Leave a note.
- **Do not "improve" `UniversalRestAdapter` while you are in there.** Its SSRF
  allowlist, secret-interpolation guard and outbound redaction are load-bearing
  security code with their own tests. Route to it; do not edit it.
- **Do not silently drop working SMTP setups.** If a user has a functioning
  `env.og`-based mail integration, an upgrade that quietly stops sending mail is
  exactly the "dead feature reporting success" pattern this audit exists to end. The
  migration warning in step 6 is a requirement, not a nicety.
- **Do not put a real credential in a test fixture**, and do not stand up an SMTP
  server. `hunter2` in a `.og` string is fine; anything that could be a live secret is
  not (the repo has a secret-scan hook, and it is right to).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Run the **full** suite. `IntegrationRuntime` is constructed inside `boot_agent`
(`gateway/orchestrator.py:2819`), so every test that boots a session touches it, far
beyond the obviously-named integration tests. Moving the `CredentialVault` construction
earlier in `boot_agent` (step 3) is the highest-risk edit in this task — it reorders a
boot sequence that ~11 progress steps depend on. Report the **actual** pass/fail counts.
"Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `.og` files were a plaintext credential source for the legacy IntegrationRuntime

- **Symptom:** A `role=env` node's `::dense` block could carry `GMAIL_APP_PASSWORD=…` in cleartext; `boot_agent` loaded every `.og` under the skills dir (including pack-installed ones) and passed the value to `smtplib.login()`. Setup failures printed to stdout, corrupting the Textual render and escaping the logging config.
- **Root cause:** `core/integrations.py` predates the credential vault. `IntegrationRuntime.load_env_node` parsed KEY=VALUE into `self._env: dict[str, str]  # Flat key-value credential store`, `get_credential` returned it raw, and `_setup_smtp` consumed it directly. `grep -n "vault|secret_store|redact" src/hachi/core/integrations.py` returned nothing — while the sibling `UniversalRestAdapter` in the same layer resolved secrets from `CredentialVault` at request time and redacted outbound params.
- **Fix:** `role=env` is no longer a credential source (deprecated no-op + migration warning naming the file, never the values); SMTP credentials resolve through `CredentialVault`; `type=http` integrations route to `UniversalRestAdapter`; all five `print()` sites became logger calls.
- **Avoid:** when a newer subsystem in the same layer already solves a cross-cutting concern (secrets, redaction, logging), an older sibling that solves it differently is a *defect*, not a style difference. Grep the old module for the new module's safety primitives before assuming parity.
- **Locked by:** `tests/test_integration_runtime_credentials.py` — `test_role_env_node_is_not_a_credential_source`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. The `skill_engine`
  at `gateway/orchestrator.py:2798-2804` has a fallback for exactly this; do not assume
  shared services exist when you move the vault construction earlier.
- **Boot ordering is load-bearing.** `boot_agent` emits numbered progress events
  (`"index": 4, "total": 11` at `:2810-2815`, `"step": "mcp", "index": 5` at `:2829-2837`).
  If you move work between steps, keep the indices consistent or the UI's boot progress
  bar jumps.
- **`get_nodes_by_role` is the seam.** `og_engine/engine.py:1682` documents it as
  "Used by the IntegrationRuntime to find 'env' and 'integration' nodes". If you delete
  the runtime entirely, check whether anything else calls it before removing the method.
- **Import layering:** `pyproject.toml` `[tool.importlinter]` blocks
  `hachi.core` → `hachi.gateway`. `core/integrations.py` may import
  `hachi.core.credential_vault` (that is how `core/rest_adapter.py:17` does it). Do not
  reach for anything in `hachi.gateway` from inside `core/integrations.py`.
- **`capsys` and the TUI.** If `test_integration_runtime_emits_no_stdout` passes
  trivially, check you are actually reaching the `print` — `setup_integration` returns
  early on an unknown type *after* printing (`:100-104`), which is the branch the test
  targets.
