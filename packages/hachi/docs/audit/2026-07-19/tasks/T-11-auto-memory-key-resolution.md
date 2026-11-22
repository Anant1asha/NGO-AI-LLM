# T-11 · Resolve the auto-memory API key the way chat does — and stop marking skips as success

|  |  |
|---|---|
| **Source finding** | CF-1 #8 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P0 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~4–6 hours |
| **Difficulty** | Medium |
| **Files you will touch** | `src/hachi/core/memory.py`, `src/hachi/core/memory_vault.py`, `src/hachi/core/runtime/job_handlers.py`, `src/hachi/jobs/queue.py` *(or the read model — see §5.3)*, `tests/test_auto_memory_key_resolution.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

Background fact extraction ("auto-memory") is gated **twice** on the literal
`ANTHROPIC_API_KEY` environment variable. The chat path does not do that — it resolves
through the secret store and then `_resolve_api_key`, which also reads a project `.env`.
So a user whose key lives in the keyring or in `.env` gets working chat and **silently
zero auto-memory**.

Worse, when it skips, the job is marked **COMPLETED** and emits `job.completed`. Nothing
reaches `jobs/failed`, so the product's "failures are visible in the jobs surface" promise
is false for this entire class.

When you are done: the key is resolved through the same chain chat uses, and a `skipped:*`
outcome is **distinguishable from success** in the jobs surface.

## 2. Why this matters

> **This is a recurrence.** **BB-40** — *"Automatic background fact-extraction
> ('auto-memory') was a complete, silent no-op"* — is the same failure one layer up, and
> its recorded Fix says the gate was changed *"from `if not os.environ.get("ANTHROPIC_API_KEY")`
> to `if llm_client is None`"*. **That change is not in the code.** `core/memory.py:222`
> still reads the env var, and `git log -L 218,228:src/hachi/core/memory.py` shows exactly
> one commit touching those lines — the original introduction. The bug-bank entry
> describes a fix that was never applied. Say so explicitly in your PR: a bug bank whose
> entries do not match the code is worse than no bug bank.

Auto-memory is the feature that means the user never has to say "remember this". It is
central to the product pitch. Failing it silently for every non-env-var user — including
everyone who followed the secure-storage path the product itself offers — is precisely
the "report success, degrade silently" thesis contradiction CF-1 names.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Gate 1 — inside `extract_facts`

`src/hachi/core/memory.py:218-224` (function `extract_facts`, def at `:182`):

```python
    import os

    from hachi.core.llm import Message as _LLMMessage

    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.debug("extract_facts: ANTHROPIC_API_KEY not set — skipping")
        return "skipped:no_api_key"
```

This gate is **redundant as well as wrong**: both callers already gate on the client.
`MemoryManager._run_fact_extraction` (`core/memory.py:650-653`):

```python
        client = self._resolve_llm_client()
        if client is None:
            logger.debug("Skipping fact extraction: no LLM client available")
            return
```

and `handle_extract_fact` (`core/runtime/job_handlers.py:185-192`) does the same. The
function *receives a working `llm_client`* and then refuses to use it because of an env
var. That is exactly what BB-40 says was fixed.

### 3.2 Gate 2 — the client factory the memory path uses

`src/hachi/core/memory_vault.py:294-305` — `_get_llm_client`:

```python
    global _llm_client_instance
    if _llm_client_instance is not None:
        return _llm_client_instance
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    with _llm_client_lock:
        # Double-checked locking: re-check after acquiring the lock.
        if _llm_client_instance is None:
            from hachi.core.llm import AnthropicClient

            _llm_client_instance = AnthropicClient(timeout=30.0)
    return _llm_client_instance
```

This is the gate that makes `client` `None` in the first place. It is reached from
`build_job_context` (`job_handlers.py:93-96`) and from
`MemoryManager._resolve_llm_client` (`core/memory.py:1367-1371`) whenever no client was
injected.

### 3.3 The contrast — how chat resolves the key

`src/hachi/core/llm.py:859-882` — `create_llm_client`:

```python
    api_key: str | None = None
    if api_key_ref and secret_store is not None:
        api_key = secret_store.get(str(api_key_ref))
    if not api_key:
        api_key = _resolve_api_key(api_key_env)

    if kind == "anthropic":
        # Always prefer ANTHROPIC_API_KEY for this kind so a misconfigured
        # api_key_ref (e.g. the legacy default "OPENAI_API_KEY") doesn't shadow it.
        kind_key = _resolve_api_key("ANTHROPIC_API_KEY") or api_key
        return AnthropicClient(api_key=kind_key, model=model, max_tokens=max_tokens)
```

**The resolver you must call is `_resolve_api_key`** — `src/hachi/core/llm.py:55-69`:

```python
def _resolve_api_key(api_key_env: str | None, explicit_api_key: str | None = None) -> str | None:
    """Resolve provider API key from explicit value, env var, then local project .env."""
    if explicit_api_key:
        return explicit_api_key
    if not api_key_env:
        return None

    env_name = str(api_key_env)
    from_env = os.environ.get(env_name)
    if from_env:
        return from_env

    # Fallback for local dev: allow project-level .env without requiring shell export.
    dotenv_values = _read_dotenv(Path.cwd() / ".env")
    return dotenv_values.get(env_name)
```

Three sources — explicit, env, project `.env` — plus the secret store above it. The
memory path checks **one**. `boot_agent` builds the chat client with
`create_default_secret_store()` (`orchestrator.py:2882-2883`), so the secret-store branch
is live in production.

### 3.4 Skips are recorded as COMPLETED

`src/hachi/core/runtime/job_handlers.py:176-192`:

```python
    if ctx.vault is None:
        logger.warning(
            "handle_extract_fact: vault not available (ChromaDB not configured?) — skipping. "
            "session=%r text_len=%d", session_id, len(text),
        )
        return "skipped:no_vault"

    if ctx.llm_client is None:
        logger.warning(
            "handle_extract_fact: LLM client not available (ANTHROPIC_API_KEY not set?) — "
            "skipping. session=%r text_len=%d", session_id, len(text),
        )
        return "skipped:no_llm_client"
```

The handler **returns a string; it never raises**. `src/hachi/jobs/queue.py:434-450` then
records it as a success:

```python
            duration = (datetime.now(UTC) - start_time).total_seconds()
            result = JobResult(
                status=JobStatus.COMPLETED,
                output=output,
                duration_seconds=duration,
            )
            logger.debug(f"Job {job.name} completed in {duration:.2f}s")
            self.on_job_event(
                "job.completed",
                {...},
            )
```

Nothing ever reaches the `JobStatus.FAILED` branch at `:420-433`, so the audit's
"failures visible in jobs/failed" promise is false for this whole class.

### 3.5 The COMPLETED-on-skip is deliberate — do not just flip it

`src/hachi/core/runtime/job_handlers.py:154-157`:

```python
    Graceful degradation: if vault OR llm_client cannot be resolved (API key absent,
    ChromaDB not installed, etc.) the handler logs a WARNING and returns a
    ``"skipped:..."`` status — it does NOT raise.  A raise would mark the job FAILED
    and trigger an unhelpful retry loop on every restart.
```

That reasoning is sound. **Do not turn skips into raises.** The fix is (a) stop skipping,
and (b) make the skip *visible as a skip*.

### 3.6 Layering constraint

`src/hachi/core/memory_vault.py:320-327`:

```python
# NOTE — layering: this module (hachi.core.memory_vault) must NOT import
# hachi.gateway (the import-linter "engine must not import the gateway
# service" contract forbids it and has no ignore entry for this module).
```

`hachi.core.llm` and `hachi.core.secret_store` are **core → core** and therefore fine.
`create_default_secret_store` lives at `src/hachi/core/secret_store.py:485`.

## 4. Reproduce the failure

Directly reproducible — this is the whole bug in three lines:

```bash
uv run python -c "
import os
os.environ.pop('ANTHROPIC_API_KEY', None)
from hachi.core.memory_vault import _get_llm_client
print('memory client ->', _get_llm_client())
"
```

**You will see now:** `memory client -> None` — even on a machine where the key is in the
keyring or in `./.env`, i.e. where chat works fine.
**You should see after the fix:** an `AnthropicClient` instance whenever the key is
resolvable by any of the mechanisms chat uses; `None` only when it truly is not.

Prove the asymmetry against a project `.env` in a scratch directory (do **not** commit
it, and use a throwaway value):

```bash
printf 'ANTHROPIC_API_KEY=sk-not-a-real-key\n' > .env
uv run python -c "
import os
os.environ.pop('ANTHROPIC_API_KEY', None)
from hachi.core.llm import _resolve_api_key
from hachi.core.memory_vault import _get_llm_client
print('chat path  ->', bool(_resolve_api_key('ANTHROPIC_API_KEY')))   # True
print('memory path->', _get_llm_client() is not None)                 # False today
"
rm .env
```

The **COMPLETED-on-skip** half is also code-readable: `handle_extract_fact` returns a
`str` on every skip path (`:166`, `:183`, `:192`) and `jobs/queue.py:434-440` maps a
non-raising handler to `JobStatus.COMPLETED` unconditionally. There is no code path from
`"skipped:*"` to `JobStatus.FAILED`.

## 5. What "fixed" looks like

### 5.1 Gate 2 — resolve through the same chain chat uses

`src/hachi/core/memory_vault.py:294-305`:

```python
    global _llm_client_instance
    if _llm_client_instance is not None:
        return _llm_client_instance

    # Resolve the key the same way the chat path does (core/llm.py create_llm_client):
    # secret store first, then _resolve_api_key (explicit -> env var -> project .env).
    # Checking os.environ["ANTHROPIC_API_KEY"] alone made auto-memory a silent no-op for
    # every user who stored their key in the keyring or a .env — see BB-40 and its
    # successor. Layering: core->core imports only; NEVER import hachi.gateway here.
    from hachi.core.llm import _resolve_api_key

    api_key: str | None = None
    try:
        from hachi.core.secret_store import create_default_secret_store

        api_key = create_default_secret_store().get("ANTHROPIC_API_KEY")
    except Exception:
        logger.warning(
            "_get_llm_client: secret store lookup failed; falling back to env/.env",
            exc_info=True,
        )
    api_key = api_key or _resolve_api_key("ANTHROPIC_API_KEY")

    if not api_key:
        logger.warning(
            "_get_llm_client: no Anthropic API key resolvable from the secret store, "
            "ANTHROPIC_API_KEY, or a project .env — background memory operations "
            "(auto-memory) are DISABLED for this process"
        )
        return None

    with _llm_client_lock:
        if _llm_client_instance is None:
            from hachi.core.llm import AnthropicClient

            _llm_client_instance = AnthropicClient(api_key=api_key, timeout=30.0)
    return _llm_client_instance
```

**Verify the secret-store key name before you write it.** `create_default_secret_store()`
is at `core/secret_store.py:485`; check what key the onboarding/settings flow stores the
Anthropic key under (`api_key_ref` in provider config) rather than assuming
`"ANTHROPIC_API_KEY"`. Reading the wrong key would reproduce this bug in a new costume.

`AnthropicClient` already takes `api_key` (`core/llm.py:252-258`) and raises `ValueError`
if it is neither passed nor in the env (`:270-271`) — passing the resolved key
explicitly is what makes the keyring path work.

### 5.2 Gate 1 — delete the redundant env check

`src/hachi/core/memory.py:222-224` → delete. The `llm_client` parameter is the correct
signal, and both callers already enforce it. If you want belt-and-braces, replace it with:

```python
    if llm_client is None:
        logger.warning("extract_facts: called with llm_client=None — skipping")
        return "skipped:no_llm_client"
```

This is the change BB-40 already claims to have made (§2).

### 5.3 Make `skipped:*` distinguishable from success (required)

Today a skip and a real extraction are both `job.completed` with a free-text `output`.
The UI cannot tell them apart. **Do not** convert skips to `FAILED` (§3.5). Pick the
smallest change that makes the distinction machine-readable, in this order of preference:

1. **Preferred — a distinct event.** In `jobs/queue.py`'s success path
   (`:434-450`), when `output` is a `str` starting with `"skipped:"`, emit
   `job.skipped` (add the constant to `core/runtime_events.py` alongside `JOB_COMPLETED`
   at `:49`) with a `reason` field carrying the suffix, and keep the durable status
   `COMPLETED`. Status semantics unchanged; observability fixed. **BB-4 does not apply**
   (no route change), but check whether the frontend's job feed switches on event name —
   if it does, an unknown event must degrade gracefully.
2. **Otherwise — a structured payload field.** Add `"skipped": True, "skip_reason": "<suffix>"`
   to the existing `job.completed` payload. Cheaper, less discoverable.

Whichever you choose, the acceptance test in §7 asserts the distinction is observable
from outside the handler.

### 5.4 The warnings are already there — keep them, sharpen the text

`job_handlers.py:177-182` and `:186-191` already `logger.warning`. Fix the misleading
parenthetical: `"(ANTHROPIC_API_KEY not set?)"` should name all three resolution
sources now that all three are checked. BB-40's autopsy called out that exact
"misleading message that pointed nowhere near the real cause".

## 6. Steps

1. Write the regression tests from §7 first. Run them. Watch them fail.
2. Confirm the secret-store key name used for the Anthropic key (§5.1).
3. Rewrite `_get_llm_client` (`memory_vault.py:294-305`) per §5.1.
4. Delete/replace the env gate in `extract_facts` (`memory.py:222-224`) per §5.2.
5. Implement the skip-visibility change per §5.3.
6. Sharpen the two warning strings in `job_handlers.py`.
7. Run the tests. Watch them pass.
8. Run `uv run python scripts/preflight.py`. Report real counts.
9. Add the bug-bank entry (§11) **and** correct BB-40's Fix section to record that its
   `extract_facts` change never landed.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_auto_memory_key_resolution.py` (new)
- **Test names:** `test_memory_llm_client_resolves_key_from_project_dotenv`,
  `test_extract_facts_does_not_gate_on_the_env_var`,
  `test_skipped_extraction_is_distinguishable_from_success`
- **It must assert:** real observed behaviour — that a client is produced when the key is
  reachable **only** via `.env` (or the secret store), that `extract_facts` proceeds when
  handed a working client with no env var set, and that a skip is externally
  distinguishable from a success.
- **It must FAIL before your fix** with:
  `AssertionError: assert None is not None` on the first, and
  `AssertionError: assert 'skipped:no_api_key' != 'skipped:no_api_key'` (i.e. the
  function returned the skip sentinel despite a working client) on the second.

```python
# sketch — adapt to the repo's existing fixtures
import os

import pytest


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    """The whole point: the key must NOT be in os.environ."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # _get_llm_client memoises into a module global — reset it or the test is order-dependent.
    import hachi.core.memory_vault as mv
    monkeypatch.setattr(mv, "_llm_client_instance", None, raising=False)


def test_memory_llm_client_resolves_key_from_project_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test-not-real\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)          # _resolve_api_key reads Path.cwd() / ".env"

    from hachi.core.memory_vault import _get_llm_client

    client = _get_llm_client()
    assert client is not None, (
        "auto-memory refused to build a client although the key is resolvable via .env — "
        "the same key the chat path (create_llm_client) accepts"
    )


def test_extract_facts_does_not_gate_on_the_env_var():
    from hachi.core.memory import extract_facts

    class _Client:
        model = "claude-haiku-4-5"
        def generate(self, *a, **kw):   # shape it like the real client's return
            raise AssertionError("reached the LLM — that is the point; assert before this")

    class _Vault:
        def upsert_fact(self, *a, **kw): return "id"

    result = extract_facts("a long enough exchange to pass the length gate", vault=_Vault(),
                           llm_client=_Client(), memory_writer=None)
    assert result != "skipped:no_api_key", (
        "extract_facts refused a working injected client because ANTHROPIC_API_KEY "
        "was not in os.environ (BB-40's documented fix was never applied)"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The second sketch is deliberately rough — shape `_Client.generate` against the real
`BaseLLMClient` contract in `core/llm.py`, and assert on *"did not return the env-var skip
sentinel"* rather than on a full extraction, so the test stays about the gate.

For the third test, drive a real `handle_extract_fact` through the queue with no vault
(`"skipped:no_vault"`) and assert the emitted event / payload distinguishes it from a
successful run — via the `on_job_event` callback, not by inspecting the handler's return
value.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and failed before the fix.
- [ ] `grep -rn 'os.environ.get("ANTHROPIC_API_KEY")' src/hachi/core/memory.py src/hachi/core/memory_vault.py`
      returns nothing (both gates are gone).
- [ ] With the key **only** in a project `.env` (or the secret store), `_get_llm_client()`
      returns a client.
- [ ] With **no** key resolvable anywhere, `_get_llm_client()` returns `None` **and** logs
      a `logger.warning` naming all three sources.
- [ ] A `skipped:*` job outcome is observable from outside the handler (distinct event or
      structured payload field) — a UI can tell it apart from a real extraction.
- [ ] Skips are still `JobStatus.COMPLETED` — no retry loop was introduced (§3.5).
- [ ] `memory_vault.py` still imports nothing from `hachi.gateway` (`uv run lint-imports`
      passes).
- [ ] BB-40's Fix section is corrected to record that its `extract_facts` change never
      landed.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not turn `skipped:*` into a raise / `JobStatus.FAILED`.** `job_handlers.py:154-157`
  documents why: it produces an unhelpful retry loop on every restart. Make it
  *visible*, not *failing*.
- **Do not make auto-memory work for non-Anthropic providers.** `_get_llm_client` builds
  an `AnthropicClient` by design; giving background memory full provider parity
  (Ollama/Groq/OpenRouter) means routing the memory path through `create_llm_client` with
  the user's provider config, which is a real design change with cost and quality
  implications. **Note it as a follow-up; do not build it here.** This task is: resolve
  the Anthropic key the same way chat does.
- **Do not import `hachi.gateway` from `memory_vault.py`** — explicitly forbidden at
  `memory_vault.py:320-327` and enforced by the import-linter contract at
  `pyproject.toml:213-237`. `core.llm` and `core.secret_store` are fine.
- **Do not add `.env` autoload to a core import path** — see BB-2 and §12. You are
  calling `_resolve_api_key` *at call time*, which reads `.env` lazily. That is the
  allowed shape.
- **Do not refactor the `_llm_client_instance` singleton** (MED-022 exists to stop the
  memory pipeline building four clients per turn). Keep the double-checked locking.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). `tests/test_durable_fact_extraction.py`
  injects `_vault_factory`/`_llm_client_factory` throughout; keep those seams intact and
  **add** a no-factory case rather than converting the existing ones.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run lint-imports                          # layering — memory_vault must not reach the gateway
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

**Also edit BB-40 itself** — its Fix section claims a change to `extract_facts` that was
never applied. Correct it to point at this entry.

```markdown
### BB-N — Auto-memory still gated on the raw ANTHROPIC_API_KEY env var (BB-40 half-fix), and skips reported as success

- **Symptom:** background fact extraction wrote nothing for any user whose Anthropic key
  lived in the OS keyring/secret store or in a project `.env` — while chat worked fine
  for the same user with the same key. The jobs surface showed every one of those turns
  as a COMPLETED `extract_fact` job; nothing appeared under `jobs/failed`.
- **Root cause:** two independent env-var gates.
  (1) `core/memory_vault.py` `_get_llm_client()` returned `None` unless
  `os.environ["ANTHROPIC_API_KEY"]` was set, ignoring the secret store and
  `_resolve_api_key`'s project-`.env` fallback that `core/llm.py create_llm_client`
  (the chat path) uses.
  (2) `core/memory.py` `extract_facts()` re-checked the same env var and returned
  `"skipped:no_api_key"` even when handed a working `llm_client` — **BB-40's recorded
  Fix says this exact gate was changed to `if llm_client is None`, but the change was
  never applied**; `git log -L` shows the line unmodified since its introduction.
  Compounding both: `handle_extract_fact` returns `"skipped:..."` strings instead of
  raising (deliberately, to avoid a restart retry loop), and `jobs/queue.py` maps any
  non-raising handler to `JobStatus.COMPLETED` + `job.completed` — so a skip was
  indistinguishable from a successful extraction to every consumer.
- **Fix:** `_get_llm_client` now resolves via the secret store then `_resolve_api_key`
  (explicit -> env -> project `.env`) and passes the resolved key to `AnthropicClient`
  explicitly; the redundant env gate in `extract_facts` was replaced with an
  `llm_client is None` check; a `skipped:*` outcome now emits a distinct
  `job.skipped` signal carrying the reason, while the durable status stays COMPLETED.
- **Avoid:** never gate a feature on a raw `os.environ[...]` read when the product has a
  credential-resolution chain — grep for how the primary path resolves the same secret
  and call that. And when a bug-bank entry records a fix, verify the fix is in the code
  before trusting the entry: BB-40's second half was documented but never landed.
- **Locked by:** `tests/test_auto_memory_key_resolution.py` —
  `test_memory_llm_client_resolves_key_from_project_dotenv`
```

## 12. Known traps

- **BB-2:** `.env` autoload belongs at the CLI edge, never in the core import path.
  Adding a top-level `.env` load to a core module previously turned the suite red across
  unrelated tests and was reverted. `_resolve_api_key` reads `.env` **lazily at call
  time** — that is the sanctioned shape. Do not hoist it to import time.
  `tests/conftest.py:38-46` sets `HACHI_DISABLE_DOTENV_AUTOLOAD=1` for the whole suite so
  the developer's real keys never leak into tests; your tests must create their own
  `.env` under `tmp_path` and `monkeypatch.chdir` into it.
- **BB-40** is the direct predecessor — read it in full before starting.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb` — `build_job_context` reaches
  the vault, and a wiped chromadb native extension poisons the rest of the process.
- `_llm_client_instance` is a **module global** memoised across calls
  (`memory_vault.py:294-296`). A test that runs after any test which populated it will see
  a stale client. Reset it with `monkeypatch.setattr` (as sketched) — never assign the
  global directly.
- `tests/conftest.py:93-114` snapshots and restores `os.environ` per test; use
  `monkeypatch.delenv`/`setenv`, never bare `os.environ[...] = ...`.
- `AnthropicClient.__init__` raises `ValueError` when it has neither an explicit key nor
  the env var (`core/llm.py:270-271`) — so passing the resolved key explicitly is
  load-bearing, not cosmetic.
