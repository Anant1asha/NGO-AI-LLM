# T-13 · Feature-liveness smoke — make "shipped but dead" impossible to regress

|  |  |
|---|---|
| **Source finding** | CF-1 recommendation (b) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P0 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | **[T-04](T-04-kennel-pack-store.md), [T-05](T-05-routing-cost-warnings-arity.md), [T-06](T-06-memory-settings-reach-vault.md), [T-07](T-07-eval-reports-config-section.md), [T-08](T-08-memory-gardener.md), [T-09](T-09-file-extracted-shared-bus.md), [T-10](T-10-shared-session-store.md), [T-11](T-11-auto-memory-key-resolution.md), [T-12](T-12-provider-kinds-schema.md)** — *do not start until they have landed* |
| **Blocks** | nothing |
| **Effort** | ~2–3 days |
| **Difficulty** | High (needs design judgement — read §5 and §9) |
| **Files you will touch** | `tests/test_feature_liveness.py` (new), `scripts/preflight.py`, `docs/bug-bank.md` |

---

## 1. Brief

This is CF-1's **structural** fix. The other nine tasks repair nine dead features; this
one makes the tenth impossible to ship. It is a dedicated pytest suite that boots a real
session and asserts, for each formerly-dead feature, that it is *live* — then a blocking
step in `scripts/preflight.py` so the gate catches the next one.

When you are done, `uv run python scripts/preflight.py` fails if any of the nine features
silently reverts to inert.

## 2. Why this matters

CF-1's finding is not "eight bugs". It is: **~4,100 tests pass while the product ships
broken promises, because the tests verify units, not wiring.** Every one of the nine
features had green unit tests. The kennel had `tests/test_p2_12_agent_packs.py` (green,
orphaned) *and* `tests/test_g1_wave1.py` (green, stubbed). Neither could fail while the
feature was completely dead.

A liveness smoke is the only test shape that can catch this class, because it asserts on
the *composition* — the thing no unit test owns. Without it, T-04 through T-12 are nine
point fixes and the next feature lands dark.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 There is no boot-time wiring test today

```bash
grep -rln "boot_agent(" tests/
# tests/test_cold_start_resume.py
# tests/test_gateway_runtime_validation.py
```

Both **fake** it. `tests/test_cold_start_resume.py:12-17` states so explicitly:

```
* resume_run → _do_resume → _InProcessGatewayRuntime.rehydrate_session →
  _boot_session_agent → boot_agent(resume_session_id=<sid>) is called.
* The test's fake boot_agent captures the resume_session_id argument and
  builds a _ScriptedAgent that loads the prior messages from the REAL store.
```

**No test in the repo calls the real `boot_agent`.** That is the gap. It is also why this
task is 2–3 days and not 4 hours: you are building the first one.

### 3.2 The existing eval harness is the WRONG home for this

> **Important design finding — state this in your PR so nobody re-litigates it.**

`src/hachi/core/eval/` (`corpus.py`, `replay.py`, `report.py`, `runner.py`,
`scheduled_report.py`), driven by `hachi eval run`, is a **loop-mechanics** suite.
`src/hachi/core/eval/corpus.py:1-11`:

```python
"""Curated regression corpus of deterministic replay cases for ``hachi eval run``.

Purpose
-------
This corpus is a **loop-mechanics regression suite** — it protects the ReAct loop's
control flow (tool dispatch, multi-step sequencing, error handling, iteration cap,
output assembly) against refactors.  It does NOT test model decision quality: the LLM
transport is entirely scripted (``ScriptedLLMClient``), so pass/fail reflects whether
the production ``ExecutionLoop`` behaves correctly given a fixed sequence of responses —
not whether the model makes good decisions.
"""

The 14 covered invariants (`corpus.py:20-35`) are all turn-level: tool dispatch, error
recovery, iteration cap, output assembly.

**Feature-liveness is boot-time WIRING, not loop mechanics.** A `ReplayCase` scripts LLM
responses and asserts on a `TurnTrajectory`; it has no vocabulary for "is the vault
carrying the configured settings" or "does `ProcessSharedServices` have a
`session_store`". Bolting liveness onto the corpus means inventing a second assertion
model inside a harness designed for a different question — **do not spend a day trying.**

It belongs as a **dedicated pytest suite plus a `scripts/preflight.py` step.**

### 3.3 The gate you will extend

`scripts/preflight.py:62-140`. The `Step` dataclass at `:62-71`:

```python
@dataclass
class Step:
    """One gate check. `cmds` is a sequence of argv lists run in order; the step
    fails if any command exits non-zero (or its executable is missing)."""

    name: str
    cmds: list[list[str]]
    blocking: bool = True
    in_quick: bool = True
    needs_frontend: bool = False
```

`STEPS` is ordered fast-to-slow (`:74-140`). Existing entries to model on:

```python
    Step("skill-lint (.og)", [["uv", "run", "python", "scripts/lint_skills.py"]]),
    Step("eval regression", [["uv", "run", "hachi", "eval", "run"]]),
    Step("pytest (full suite)", [["uv", "run", "pytest", "-q"]], in_quick=False),
```

### 3.4 The boot-time obstacles you must design around

**(a) `boot_agent` constructs an LLM client unguarded.**
`src/hachi/gateway/orchestrator.py:2881-2883`:

```python
    # 6. Initialize the LLM Provider
    secret_store = create_default_secret_store()
    client = create_llm_client(provider_config, secret_store=secret_store, max_tokens=max_tokens)
```

With `kind = "anthropic"` and no key, `AnthropicClient.__init__` **raises**
(`core/llm.py:269-271`):

```python
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be provided or set in the environment.")
```

`OpenAICompatibleClient` accepts `api_key: str | None = None` (`core/llm.py:421-432`) and
constructs an `httpx.Client` **without making a request**. So `kind = "ollama"` gives a
key-free, network-free boot. There is a second construction at `:2892-2894` for
sub-agents — same provider config, same conclusion.

**(b) `get_hachi_paths()` has no environment override.** `src/hachi/core/paths.py:117-124`:

```python
def get_hachi_paths() -> HachiPaths:
    dirs = PlatformDirs(appname=APP_NAME, appauthor=False, ensure_exists=False)
    return HachiPaths(
        config_dir=Path(dirs.user_config_path),
        ...
    )
```

An unguarded `boot_agent()` in a test **writes into the developer's real `~/.hachi`**. The
established pattern is `patch("<module>.get_hachi_paths", return_value=fake_paths)` —
used ~12 times in `tests/test_backup_restore.py` (e.g. `:86`). Note `orchestrator.py`
imports the name at module level (`:46`), so the patch target is
`hachi.gateway.orchestrator.get_hachi_paths` — patching `hachi.core.paths.get_hachi_paths`
will **not** take effect there.

**(c) `ProcessSharedServices` leaks across tests.** `tests/conftest.py:75-90` autouse-clears
`_INSTANCES` before every test; `:117-131` `shutdown_all()`s at session end. Read that
file's module docstring (`:1-32`) before writing anything that boots.

## 4. Reproduce the failure

There is nothing to reproduce: this task adds a missing check rather than fixing a defect.

The **absence** is what you verify, and it is one command:

```bash
grep -rln "boot_agent(" tests/
```

**You will see now:** two files, both of which substitute a fake `boot_agent` (§3.1).
**You should see after the fix:** `tests/test_feature_liveness.py` in that list, calling
the real one.

Confirm the gate has no liveness step:

```bash
grep -n "liveness" scripts/preflight.py    # -> no output today
```

## 5. What "fixed" looks like

### 5.1 One suite, one boot, N assertions

`tests/test_feature_liveness.py` — a module-scoped fixture that boots **one** real session
into a `tmp_path` profile, and one small test per formerly-dead feature reading from it.
One boot, because booting is the expensive part; separate tests, because a single mega-test
tells you "something is dead" instead of *which*.

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path
from unittest.mock import patch

import pytest

from hachi.core.paths import HachiPaths


@pytest.fixture(scope="module")
def live_session(tmp_path_factory):
    """Boot a REAL session into an isolated profile. No network, no API key.

    provider.kind = "ollama" so create_llm_client returns an OpenAICompatibleClient,
    which accepts api_key=None and makes no request at construction time (§3.4a).
    memory.backend = "chroma" because T-06's assertion needs a real vault.
    """
    root = tmp_path_factory.mktemp("liveness")
    paths = HachiPaths(
        config_dir=root / "config",
        data_dir=root / "data",
        cache_dir=root / "cache",
        state_dir=root / "state",
    )
    # Write the settings.toml this profile boots from — see §5.3 for the contents.
    ...
    with patch("hachi.gateway.orchestrator.get_hachi_paths", return_value=paths):
        from hachi.gateway.orchestrator import boot_agent

        session = boot_agent()
        try:
            yield session, paths
        finally:
            session.shutdown()
```

`tests/conftest.py`'s autouse `_reset_process_shared_services` is **function-scoped** and
will clear `_INSTANCES` between your tests even though the fixture is module-scoped. Decide
deliberately: either make the fixture function-scoped (slower, simpler, safer) or capture
whatever you need from `ProcessSharedServices` **during** the boot fixture. Do not fight
conftest.

### 5.2 The checklist — one assertion per task

| # | Task | Assert |
|---|---|---|
| 1 | [T-04](T-04-kennel-pack-store.md) | `runtime.get_kennel()` returns ≥ 5 items whose ids include the shipped pack directory names, each with a non-empty `description` and `version`. |
| 2 | [T-05](T-05-routing-cost-warnings-arity.md) | `validate_routing(registry, policy)` with a capability pinned to a model ≥ 3× the `default_model` price returns non-empty `warnings`. *(Pure function — no boot needed; keep it in the suite so the checklist is complete.)* |
| 3 | [T-06](T-06-memory-settings-reach-vault.md) | `ProcessSharedServices.instance().vault.decay_half_life_days` equals the value in the profile's `settings.toml`. |
| 4 | [T-07](T-07-eval-reports-config-section.md) | `"eval_reports" in ResolvedConfig.model_fields`, **and** `load_config()` over a profile containing `[eval_reports]` round-trips the section. |
| 5 | [T-08](T-08-memory-gardener.md) | **Depends on T-08's decision.** Option B (recommended): assert no production module references `memory_gardener` and `AgentSession` has no `snapshot_gardener_diffs`. Option A: assert the schedule thread is running and `pending_diffs.json` is written after a forced tick. **Read T-08's outcome before writing this one.** |
| 6 | [T-09](T-09-file-extracted-shared-bus.md) | Subscribe to `ProcessSharedServices.instance().event_bus`, call `_emit_file_extracted(...)`, assert the subscriber received `file.extracted`. *(Requires `[events] bus_funnel = true` in the profile — see §5.3.)* |
| 7 | [T-10](T-10-shared-session-store.md) | `ProcessSharedServices.instance().session_store is not None`, **and** `fastapi_app._resolve_session_store()` returns that identical object. |
| 8 | [T-11](T-11-auto-memory-key-resolution.md) | With **no** `ANTHROPIC_API_KEY` in `os.environ` but a key present in the profile's `.env`, `memory_vault._get_llm_client()` returns a client. **See §5.4 — this one has a trap.** |
| 9 | [T-12](T-12-provider-kinds-schema.md) | `ResolvedConfig.model_validate({"provider": {"kind": k}})` succeeds for every kind `create_llm_client` implements. |

Every assertion reads **live objects or real files**. If an assertion can pass against a
mock, it does not belong here — that is what the unit suites are for.

Name each test after its task so a failure points at the spec:
`test_liveness_t04_kennel_lists_bundled_packs`, `test_liveness_t10_shared_session_store`, …

### 5.3 The profile

Write a `settings.toml` into the fixture's `config_dir` that turns on exactly what the
assertions need, and nothing else:

```toml
[provider]
kind = "ollama"          # key-free, no network at construction (§3.4a)
model = "llama3"

[memory]
backend = "chroma"       # T-06 needs a real vault
decay_half_life_days = 30.0
recall_distance_max = 0.42
core_memory_max_entries = 77

[events]
bus_funnel = true        # T-09 needs a shared EventBus (orchestrator.py:2727-2730)

[eval_reports]
enabled = false          # presence is what T-07 asserts, not activation
```

Keep it minimal and comment **why** each key is there — the next reader will otherwise
"tidy" one away and silently disable an assertion.

### 5.4 The T-11 trap — do not plant the key in the environment

The obvious way to make `boot_agent` happy is `ANTHROPIC_API_KEY=test`. **That would void
assertion 8**, whose entire point is that the key is resolvable *without* the env var.

Resolve it by construction:

- `provider.kind = "ollama"` means `boot_agent` never needs an Anthropic key at all
  (§3.4a).
- For assertion 8, write `ANTHROPIC_API_KEY=sk-not-a-real-key` into a `.env` **inside the
  test's temp cwd** and `monkeypatch.chdir` there — `_resolve_api_key` reads
  `Path.cwd() / ".env"` (`core/llm.py:68`).
- Assert `_get_llm_client()` is not `None`. It constructs an `anthropic.Anthropic`
  client, which makes **no** network call at construction.
- Reset `memory_vault._llm_client_instance` first — it is a memoised module global
  (`memory_vault.py:294-296`) and a prior test may have populated it.

### 5.5 Wire it into the gate

Add to `scripts/preflight.py` `STEPS`, **before** the slow full-pytest step and after
`eval regression`:

```python
    Step(
        "feature liveness (boot smoke)",
        [["uv", "run", "pytest", "-q", "tests/test_feature_liveness.py"]],
        blocking=True,
    ),
```

Leave `in_quick=True` **only if** the suite runs in well under ~30 s; boot is not free.
Measure it and decide — an inner loop nobody runs because it is slow protects nothing.
Say the measured wall time in your PR.

## 6. Steps

1. Confirm all of T-04 … T-12 have landed. **Read T-08's recorded decision** — assertion 5
   depends on it.
2. Write the `live_session` fixture and get a real `boot_agent()` to complete against a
   `tmp_path` profile with **no network and no API key**. This is the bulk of the work; do
   it before writing any assertion.
3. Add the nine assertions from §5.2, one test each, named after their task.
4. Run the suite with every T-0x fix reverted one at a time (`git stash` a single fix)
   and confirm the corresponding assertion — and only that one — fails. **This is the
   step that proves the smoke works.** Report the results in your PR.
5. Add the `Step` to `scripts/preflight.py` (§5.5). Measure the wall time.
6. Run `uv run python scripts/preflight.py`. Report real counts.
7. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**

This task's deliverable *is* a test suite, so Rule 2 applies at one remove: **step 4 above
is your "watch it fail"**. A liveness assertion that has never been observed failing is
indistinguishable from an assertion that cannot fail — which is exactly how the nine dead
features shipped with green tests.

- **File:** `tests/test_feature_liveness.py` (new)
- **Test names:** `test_liveness_t04_*` … `test_liveness_t12_*` (nine)
- **Each must assert:** a live object, a real file, or a real HTTP/bus delivery — never a
  mock's recorded call.
- **Each must FAIL** when its corresponding T-0x fix is reverted. Verify all nine
  individually and record the observed failure message for each in the PR description.

```python
# sketch — one assertion, showing the shape
def test_liveness_t10_shared_session_store(live_session) -> None:
    from hachi.gateway.fastapi_app import _resolve_session_store
    from hachi.gateway.shared_services import ProcessSharedServices

    shared = ProcessSharedServices.instance()
    assert shared is not None, "no shared services after a real boot (BB-6)"
    assert shared.session_store is not None, (
        "boot_agent created a SessionStore but never attached it to the shared "
        "singleton — every 'prefer shared store' branch is dead again (T-10)"
    )
    assert _resolve_session_store() is shared.session_store
```

Write every assertion message like that one: name the task, and say what a human should
conclude. This suite exists to be read by whoever it fails on.

> If an assertion passes with its fix reverted, the assertion is wrong. Do not ship it.

## 8. Acceptance criteria

- [ ] `tests/test_feature_liveness.py` exists with one named test per T-04 … T-12.
- [ ] Each of the nine was **observed failing** with its fix reverted; the failure
      messages are recorded in the PR.
- [ ] The suite boots a **real** `boot_agent()` — it is the third entry in
      `grep -rln "boot_agent(" tests/`, and the only one that does not fake it.
- [ ] The suite requires **no network and no API key**: it passes with
      `ANTHROPIC_API_KEY` unset and no internet.
- [ ] The suite writes nothing outside `tmp_path` (verify: run it, then confirm your real
      `~/.hachi` data dir is unmodified).
- [ ] `scripts/preflight.py` has a blocking `feature liveness (boot smoke)` step, and its
      measured wall time is stated in the PR.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not add these as eval-corpus cases.** §3.2 explains why in detail: the corpus is a
  loop-mechanics suite driven by a `ScriptedLLMClient`, with no vocabulary for boot
  wiring. This is the single most likely way to waste a day on this task.
- **Do not make the suite hit the network or require a key.** BB-2 (`.env` autoload stays
  at the CLI edge) and BB-6 (`ProcessSharedServices` is `None` before a session boots) are
  both live constraints here. A smoke that needs credentials will be skipped in CI and
  protect nothing.
- **Do not add assertions for features outside T-04 … T-12.** The suite's value is that
  every assertion maps to a spec with a bug-bank entry. A grab-bag of "things that seem
  important" rots. Extending it later is a deliberate act with its own task.
- **Do not turn this into an integration-test framework.** No HTTP server, no
  `_start_gateway_server`, no fixtures other code will import. One fixture, nine tests,
  one file.
- **Do not fix anything you discover while writing it.** If an assertion fails for a
  reason other than its T-0x fix being absent, you have found a *new* dead feature — file
  it, do not fix it here.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. **In particular, do not add a test-only
  dependency** (e.g. a mock HTTP server) — this suite needs none.

## 10. Verify

```bash
uv run pytest -q tests/test_feature_liveness.py    # the new suite alone, and time it
uv run python scripts/preflight.py --quick         # inner loop
uv run python scripts/preflight.py                 # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done — and for this task
specifically, a green suite that has never been seen red is not evidence.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — ~4,100 green tests could not detect eight completely dead features

- **Symptom:** eight shipped features were inert in production while the full suite
  passed: the kennel installed nothing, routing cost warnings were always empty, three
  `[memory]` settings were ignored, `[eval_reports]` was stripped from config,
  MemoryGardener never ran, `file.extracted` reached nobody, the shared `session_store`
  was never assigned, and auto-memory was a no-op for non-env-var users.
- **Root cause:** the suite verified **units**, never **wiring**. Both kennel test files
  were green while the feature was 100% dead — one tested the pack module directly
  (which no production code imported), the other stubbed the gateway handler
  (`_app(get_kennel=lambda: stub)`). No test in the repo called the real `boot_agent`;
  the two files that mentioned it substituted a fake. Combined with the
  `except Exception: pass` / `getattr(x, "field", None)` idiom at feature boundaries,
  there was no mechanism — test or runtime — by which a dead feature could announce
  itself.
- **Fix:** added `tests/test_feature_liveness.py` — a boot-time smoke that starts a REAL
  session against an isolated `tmp_path` profile with no network and no API key, and
  asserts one live property per formerly-dead feature — and wired it into
  `scripts/preflight.py` as a blocking step. Each assertion was verified to fail with its
  corresponding fix reverted.
- **Avoid:** a unit test that constructs the subject itself, or stubs the handler under
  test, proves nothing about whether production reaches it. When you ship a feature, add
  one assertion that the COMPOSITION ROOT wires it — and prove the assertion fails
  without the wiring. "Tests pass" is not "the feature works". Feature-liveness is boot
  wiring, not loop mechanics: it belongs in this suite, NOT in the `hachi eval run`
  corpus, which scripts the LLM transport and asserts on turn trajectories.
- **Locked by:** `tests/test_feature_liveness.py` — the whole file; `scripts/preflight.py`
  step "feature liveness (boot smoke)"
```

## 12. Known traps

- **BB-2:** `.env` autoload belongs at the CLI edge, never the core import path.
  `tests/conftest.py:38-46` sets `HACHI_DISABLE_DOTENV_AUTOLOAD=1` for the whole suite,
  specifically so a developer's real keys do not leak into tests and flip
  import-time skip guards. **Do not defeat it.** The T-11 assertion creates its own `.env`
  under `tmp_path` and `chdir`s there (§5.4).
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — your assertions
  must run *after* the fixture's `boot_agent()`, and `instance()` returning `None` means
  the boot failed, not that the feature is absent. Assert that distinction.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. The profile uses
  `backend = "chroma"` for T-06, so a real `PersistentClient` opens — always under
  `tmp_path`.
- **BB-5:** `paths.workspace_dir` does not exist — construct `HachiPaths` with
  `config_dir` / `data_dir` / `cache_dir` / `state_dir` and use the derived properties.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- `tests/conftest.py:75-90` clears `ProcessSharedServices._INSTANCES` **before every
  test** (function-scoped autouse). A module-scoped boot fixture will be silently
  disconnected from `instance()` by the time your second test runs. Decide this
  explicitly (§5.1) — it is the most likely source of a confusing "passes alone, fails in
  the suite" result.
- `tests/conftest.py:50-53` raises the gateway client timeout to 90 s for tests because a
  cold boot with skill indexing + ChromaDB init is slow on Windows. Expect your fixture to
  take seconds, not milliseconds; that is why §5.5 asks you to measure before choosing
  `in_quick`.
- On Windows, an unclosed SQLite/WAL handle blocks `tmp_path` cleanup and surfaces as a
  confusing teardown error. Always `session.shutdown()` in the fixture's `finally`.
