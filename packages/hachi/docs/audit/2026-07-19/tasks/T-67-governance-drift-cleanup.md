# T-67 · Delete the `TOKOBOROS_*` shim, close the two core `.env` bypasses, and sweep the fictional-team CI comments

|  |  |
|---|---|
| **Source finding** | CF-17 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~2 days |
| **Difficulty** | Low (mechanical) for parts 1 and 3 · Medium for part 2 (one existing test legitimately changes) |
| **Files you will touch** | `src/hachi/cli/main.py`, `src/hachi/core/llm.py`, `src/hachi/core/oauth.py`, `scripts/preflight.py`, `scripts/check_bans.py` (new), `.github/workflows/ci.yml`, `tests/test_cli_creds_and_og.py`, `tests/test_oauth.py`, `tests/test_dotenv_hermeticity.py`, `docs/bug-bank.md` |

---

## 1. Brief

Three of the repo's own written rules are broken by the repo itself. A `TOKOBOROS_*` env
shim runs at CLI import despite an explicit repo-level ban on exactly that; **two** core
modules read `.env` from the current working directory past the `HACHI_DISABLE_DOTENV_AUTOLOAD`
gate that BB-2 says confines dotenv to the CLI edge; and CI carries comments addressed to
"the owning team" and "other agents this session" — teams that do not exist — attached to
gates that are consequently non-blocking.

When you are done: the shim is gone and a **blocking** preflight step makes the ban
mechanical instead of advisory; both core dotenv readers honour the gate; and every CI
comment describes reality, with a deliberate decision recorded for each gate that stays
non-blocking.

## 2. Why this matters

**Guardrails only work if they bind the guardian.** This repo's differentiator is that its
rules are *mechanical* — import-linter blocks layering drift, the push-lock blocks pushes,
the eval harness blocks regressions. That mechanism is the product's credibility. Every
rule that is written but not enforced teaches the next contributor — human or agent — that
the walls are decorative, and a wall that is decorative in one place gets treated as
decorative everywhere.

Note the shape of each of the three: a ban with no check got violated; a gate with one
enforcement point got bypassed at two others; a comment written for an imagined org
outlived the fiction. None of these is a bug a user hits. All three are the mechanism by
which the *next* user-facing bug ships. If your fix ends with "I deleted the code" and not
"...and the ban is now checked by the gate", you have done half the task.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The ban — [CLAUDE.md](../../../../CLAUDE.md) "Out of scope", lines 87-88

```markdown
- **`tokoboros` compatibility shims** — explicitly removed; do not reintroduce. Tracked
  code/docs stay tokoboros-free.
```

### 3.2 The violation — `cli/main.py:151-184`, module scope

```python
# ---------------------------------------------------------------------------
# Task 6d — TOKOBOROS_ → HACHI_ back-compat shim
# ---------------------------------------------------------------------------

_logger = logging.getLogger(__name__)

_TOKOBOROS_RENAMES: dict[str, str] = {
    "TOKOBOROS_STT_API_KEY": "HACHI_STT_API_KEY",
    "TOKOBOROS_TTS_API_KEY": "HACHI_TTS_API_KEY",
    "TOKOBOROS_SMTP_USER": "HACHI_SMTP_USER",
    "TOKOBOROS_SMTP_PASSWORD": "HACHI_SMTP_PASSWORD",
    "TOKOBOROS_SMTP_HOST": "HACHI_SMTP_HOST",
    "TOKOBOROS_SMTP_PORT": "HACHI_SMTP_PORT",
    "TOKOBOROS_SMTP_FROM": "HACHI_SMTP_FROM",
}


def _apply_tokoboros_shim() -> None:
    """Copy deprecated TOKOBOROS_* env vars to their HACHI_* equivalents.

    Only copies when the old var is present and the new var is NOT already set.
    Logs a deprecation warning for each migrated key so operators know to
    update their environment.
    """
    for old, new in _TOKOBOROS_RENAMES.items():
        if old in os.environ and new not in os.environ:
            os.environ[new] = os.environ[old]
            _logger.warning(
                "Deprecated env var %r — rename to %r in your .env or environment.",
                old,
                new,
            )


_apply_tokoboros_shim()
```

Exact anchors: dict `_TOKOBOROS_RENAMES` at `:156-164` · function `_apply_tokoboros_shim`
at `:167-181` · **module-level invocation at `:184`**, which runs on **every**
`import hachi.cli.main` — including inside the test suite, and including the cold-start
resume path (`core/runtime/resume.py:124` does `import hachi.cli.main as _main_mod`).

`_logger` at `:154` is used **only** by the shim — check before deleting it
(`rg -n "_logger" src/hachi/cli/main.py`).

### 3.3 ⚠️ `tokoboros` legitimately appears elsewhere — do NOT grep for the bare word

A naive `grep -i tokoboros` ban would fire on three **correct** uses:

| Anchor | Code | Why it is legitimate |
|---|---|---|
| `gateway/workspace.py:19` | `_LEGACY_BRAND_TOKEN = "tokoboros"` | Self-heals a user's on-disk `brain.og` that still carries the old brand. Also `:50` (docstring) and `:86` (log line). |
| `pyproject.toml:150` | `norecursedirs = ["tokoboros", ...]` | BB-7 — a directory junction makes the suite collect twice without it. |
| `tests/test_workspace_brand_heal.py` | fixture content, 6 sites | Tests the self-heal above. |
| `tests/conftest.py:99` | comment | Explains an `os.environ` diff-restore quirk. |

The ban must target the **env-var shim shape**, not the brand word. The discriminating
pattern is `TOKOBOROS_` — uppercase with a trailing underscore. Verified today:

```
TOKOBOROS_        →  docs/DECISIONS.md (3)   src/hachi/cli/main.py (11)   tests/test_cli_creds_and_og.py (12)
```

### 3.4 The gate is enforced in exactly ONE place — `cli/main.py:107-135`

```python
def _load_dotenv_into_environ(dotenv_path: Path) -> None:
    """Merge a .env file into os.environ (existing vars are NOT overwritten).
    ...
    Set ``HACHI_DISABLE_DOTENV_AUTOLOAD=1`` to skip the merge entirely. The pytest
    harness sets this in ``tests/conftest.py`` so the suite never pulls the
    developer's real provider keys into the process ...
    """
    if os.environ.get("HACHI_DISABLE_DOTENV_AUTOLOAD", "").strip() == "1":
        return
```

`rg -n "HACHI_DISABLE_DOTENV_AUTOLOAD" src/` returns **exactly two hits, both in this one
function** (`:114` docstring, `:120` the check). No other module in `src/` consults it.

The CLI edge merges two files into `os.environ`: `cli/main.py:138`
(`_load_dotenv_into_environ(Path.cwd() / ".env")`) and `cli/main.py:146`
(the config-dir `.env`).

### 3.5 Bypass #1 — `core/llm.py:67-69`, inside `_resolve_api_key` (`:55`)

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

`_read_dotenv` is at `core/llm.py:40-52`. Neither consults the gate.

**This function has zero test coverage** — `rg -n "llm\._resolve_api_key" tests/` returns
nothing. (The `_resolve_api_key` hits in `tests/test_search_platform.py` and
`tests/test_web_gui_diag.py` are a *different* function,
`core/providers/tavily_provider.py:35`, which reads only the secret store and
`os.environ` — it is **not** a third bypass.)

### 3.6 Bypass #2 — `core/oauth.py:27-41` and `:44-69`. **The audit missed this one.**

```python
def _read_dotenv_value(path: Path, key: str) -> str | None:
    """Return the value of *key* from a simple ``KEY=VALUE`` .env file, or None."""
    ...


def _resolve_env(name: str) -> str | None:
    """Resolve a credential env var **lazily, at call time**.
    ...
    """
    val = os.environ.get(name)
    if val:
        return val
    candidates = [Path.cwd() / ".env"]
    try:
        from hachi.core.paths import get_hachi_paths

        candidates.append(get_hachi_paths().config_dir / ".env")
    except Exception:
        pass
    for path in candidates:
        val = _read_dotenv_value(path, name)
        if val:
            return val
    return None
```

`_resolve_env` is the resolver for `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`. It reads
**two** `.env` files (CWD at `:58`, config-dir at `:62`) and consults the gate for neither.

> **A fix that only touches `llm.py` leaves this open.** Both readers, or neither.

### 3.7 CI comments addressed to teams that do not exist

`.github/workflows/ci.yml:87-93` — **bandit, non-blocking**:

```yaml
      - name: SAST — bandit (medium+ severity)
        run: uv run bandit -r src -ll --exit-zero
        # exit-zero: bandit findings are currently medium only (0 high) and are
        # pre-existing in src/ (owned by other agents this session). We surface the
        # report but do not block until the owning team has triaged each finding.
        # Change to omit --exit-zero once src/ medium findings are resolved.
```

`.github/workflows/ci.yml:112-119` — **ruff. ⚠️ The comment is stale in a second way:**

```yaml
      # T1.3: ruff is now a hard gate on every push and PR.
      # Pre-existing ruff state (2026-06-19): 1 error in src/hachi/core/browser.py
      # (F401 unused import) and 3 in tests/ (I001, F401 x2).  These must be fixed
      # before this gate will pass green on main.  They are trivial auto-fixable
      # errors; the owning team should run `uv run ruff check --fix src tests`
      # and commit the result.
      - name: Lint (ruff)
        run: uv run ruff check src tests
```

There is **no** `continue-on-error` here — this gate **already blocks**, and the four
errors it describes were fixed long ago (preflight's `ruff check` step is green today).
The whole comment block is dead history.

`.github/workflows/ci.yml:121-133` — **mypy full tree, non-blocking**. A third
fictional-owner comment the audit did not list:

```yaml
      # T1.3: mypy on the full src tree is still non-blocking on main because there
      # are 483 pre-existing errors across 64 files (chromadb typing issues in
      # memory_vault.py, og_engine/engine.py annotation gaps, community_packs.py).
      # These are NOT caused by this session's changes and are outside our ownership
      # scope (owned by source agents).  Making this blocking today would turn main
      # red immediately for unrelated debt.
      # Strategy: the scoped strict gate (mypy-strict-gate.ini) IS blocking on PRs
      # and covers 48 files that are already clean.  The full-tree check here is
      # advisory on both main and PRs — it records the error count trend over time.
      # Full burn-down is tracked as a Phase 3 sustained effort.
```

Its numbers are also stale: the real counts today are **471 errors in 66 files**, and the
gate covers **40** files, not 48. Fixing those numbers is
[T-69](T-69-mypy-burndown-ratchet.md)'s job — here you fix only the *fiction*
("our ownership scope", "owned by source agents").

There are **two effective contributors on this repo. There are no teams.**

## 4. Reproduce the failure

Every part of this is mechanically checkable. Run from the repo root.

```bash
# ---- Part 1: the banned shim is present and RUNS at import ----
git grep -n "TOKOBOROS_" -- src/ tests/
python -c "import os; os.environ['TOKOBOROS_SMTP_HOST']='shim-ran'; \
           import hachi.cli.main; print('HACHI_SMTP_HOST =', os.environ.get('HACHI_SMTP_HOST'))"

# ---- Part 2: the gate is honoured in exactly one place ----
rg -n "HACHI_DISABLE_DOTENV_AUTOLOAD" src/          # expect: 2 hits, both cli/main.py
rg -n "Path.cwd\(\) / \".env\"" src/                # expect: cli/main.py, core/llm.py, core/oauth.py

# ---- Part 3: gates that do not gate ----
rg -n "own(ing|ed|ership)|other agents|this session" .github/workflows/ci.yml
rg -n "exit-zero|continue-on-error" .github/workflows/ci.yml
```

**You will see now:**

- Part 1 — hits in `src/hachi/cli/main.py` (11) and `tests/test_cli_creds_and_og.py` (12);
  the python one-liner prints `HACHI_SMTP_HOST = shim-ran`, proving the banned shim
  executes on a bare import.
- Part 2 — `HACHI_DISABLE_DOTENV_AUTOLOAD` appears only at `cli/main.py:114` and `:120`;
  `Path.cwd() / ".env"` appears in **three** files, two of which are core.
- Part 3 — four "owning team" comment sites (`:91`, `:92`, `:116`, `:124-125`).

**You should see after the fix:**

- Part 1 — `git grep -n "TOKOBOROS_"` returns **no hits under `src/`**; the one-liner
  prints `HACHI_SMTP_HOST = None`; `uv run python scripts/check_bans.py` exits 0.
- Part 2 — `rg -n "HACHI_DISABLE_DOTENV_AUTOLOAD" src/` returns hits in **three** modules.
- Part 3 — the grep for owning-team language returns nothing.

**Direct proof that the core bypass is live** (a dotenv value reaching a core resolver
while the gate is set — the exact thing BB-2 forbids):

```bash
mkdir -p /tmp/hachi-bypass && cd /tmp/hachi-bypass
printf 'GOOGLE_CLIENT_ID=leaked-from-cwd\n' > .env
HACHI_DISABLE_DOTENV_AUTOLOAD=1 python -c \
  "from hachi.core import oauth; print(oauth._resolve_env('GOOGLE_CLIENT_ID'))"
```

Today this prints `leaked-from-cwd` **with the gate explicitly set to 1**. After the fix it
prints `None`. (On Windows use a scratch dir under `%TEMP%`; the point is only that the CWD
contains a `.env`.)

## 5. What "fixed" looks like

### Part 1 — delete the shim, then make the ban mechanical

The shim goes entirely: `cli/main.py:150-184` (comment banner, `_TOKOBOROS_RENAMES`,
`_apply_tokoboros_shim`, the module-level call). Keep `_logger` only if something else uses
it.

Then add `scripts/check_bans.py`, modelled exactly on the existing `scripts/check_adrs.py`
(stdlib only, never imports the product, `ROOT = Path(__file__).resolve().parent.parent`,
returns `1` on violations, `raise SystemExit(main())`):

```python
#!/usr/bin/env python
"""Ban-lint — the repo's written bans, made mechanical (CF-17).

A ban with no check is advice. This is the check. It enforces the bans recorded in
CLAUDE.md "Out of scope" against tracked source, so a reintroduction fails the gate
instead of surviving until the next audit.

Stdlib only — never imports the product.
"""
BANS: list[tuple[str, str, tuple[str, ...], str]] = [
    (
        "tokoboros-env-shim",
        r"TOKOBOROS_[A-Z0-9_]+",
        ("src", "scripts"),
        "CLAUDE.md bans tokoboros compatibility shims. Use HACHI_* directly.",
    ),
]
```

Scope it to `src/` and `scripts/` and match `TOKOBOROS_[A-Z0-9_]+`, **not** the bare brand
word — see §3.3 for the three legitimate uses it must not fire on. Walk `.py`/`.toml`/`.yml`
files under those roots with `Path.rglob`; skip `__pycache__`.

Wire it into `scripts/preflight.py` **as a blocking step**, next to the other Phase-2/3
rails. Note `run_step` resolves `cmd[0]` via `shutil.which`, so a raw `grep`/`rg` argv would
be unportable — invoke Python, exactly like the neighbouring steps:

```python
    Step("ban-lint (reintroduced shims)", [["uv", "run", "python", "scripts/check_bans.py"]]),
```

Place it near `Step("skill-lint (.og)", ...)` at `preflight.py:81` — it is fast, so it
belongs early. Mirror it into `.github/workflows/ci.yml` in the Guardrails block that starts
at `:142`.

**Blocking from day one**, not advisory: its baseline is zero the moment you delete the
shim, and the other rails are advisory only because their baselines are not yet clean.

### Part 2 — both core readers honour the gate

Add a single shared helper rather than duplicating the check. It belongs in `core/paths.py`
(already imported by both modules, no new edge, and `core/paths.py` is on the mypy strict
gate so it stays typed):

```python
def dotenv_autoload_disabled() -> bool:
    """True when HACHI_DISABLE_DOTENV_AUTOLOAD=1 forbids reading .env files.

    BB-2: .env belongs at the CLI edge. Core resolvers may read it lazily as a
    local-dev convenience, but must fall silent when the harness (or an operator)
    disables autoload — otherwise a hermetic process still picks up ambient creds.
    """
    return os.environ.get("HACHI_DISABLE_DOTENV_AUTOLOAD", "").strip() == "1"
```

- `core/llm.py:67-69` → return `None` instead of reading, when disabled.
- `core/oauth.py:58-68` → skip the `candidates` loop entirely, when disabled.
- `cli/main.py:120` → call the helper instead of re-reading the env var, so there is one
  definition of the rule.

**Keep the lazy `.env` read.** Do not delete it. `core/oauth.py:44-54`'s docstring records
exactly why it exists:

> *"the previous module-level `os.environ.get(...)` ran exactly once when this module was
> first imported ... and every Google tool failed with 'Missing GOOGLE_CLIENT_ID' despite
> being correctly configured."*

That is a real, fixed bug. BB-2 forbids **import-time** autoload in core and wants the
harness to be able to opt out — it does not forbid a gated, call-time read. Honour the gate;
keep the capability.

### Part 3 — CI comments describe reality

- **ruff (`:112-117`)** — delete the whole stale block. Replace with one line:
  `# Hard gate on every push and PR. Baseline is clean; mirrored by scripts/preflight.py.`
- **bandit (`:87-93`)** — remove "owned by other agents this session" and "the owning team".
  Then make the call: either keep `--exit-zero` with an honest reason
  (`# Advisory: N medium findings, 0 high. Ratchet to blocking when the medium count hits zero.`)
  **and record the current N**, or drop `--exit-zero` if `uv run bandit -r src -ll` is
  already clean. **Check first** — do not assume.
- **mypy full tree (`:121-130`)** — remove "outside our ownership scope (owned by source
  agents)". Keep it advisory (that is [T-69](T-69-mypy-burndown-ratchet.md)'s subject) but
  point at the ratchet instead of at a team. Leave the stale 483/64/48 numbers for T-69, or
  correct them to 471/66/40 in passing — say which you did in the commit message.

## 6. Steps

1. Write the §7 tests and watch them **fail**. All three.
2. Delete `cli/main.py:150-184`. Check whether `_logger` (`:154`) has other users before
   removing it.
3. Delete `TestTokoborosShim` (`tests/test_cli_creds_and_og.py:270-327`) and the two
   now-dead imports at `:17` and `:19`. Update the module docstring at `:1`, which names
   "Task 6d TOKOBOROS shim". **See §9 — this is a contract change, not a weakened test.**
4. Write `scripts/check_bans.py`. Run it — it must exit 0 now that the shim is gone, and
   exit 1 if you temporarily paste the shim back.
5. Add the blocking `ban-lint` step to `scripts/preflight.py` (near `:81`) and to
   `.github/workflows/ci.yml` (Guardrails block, from `:142`).
6. Add `dotenv_autoload_disabled()` to `core/paths.py`.
7. Apply it at `core/llm.py:67-69`, `core/oauth.py:58-68`, and `cli/main.py:120`.
8. Amend `tests/test_oauth.py:139` — see §12, it will go red and it is *supposed* to.
9. Sweep the three CI comment blocks. Decide the bandit gate explicitly.
10. Run the FULL `uv run python scripts/preflight.py` and report real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

Two of the three parts get a real pytest test; the third gets a lint script. **Do not force
a fake unit test for the CI comments** — a comment sweep has no runtime behaviour to assert.
Its check is a human reading the diff, plus grep (2) in §4.

### 7a — the ban is mechanical

- **File:** `tests/test_governance_bans.py` (**new**)
- **Test name:** `test_no_tokoboros_env_shim_in_src`
- **It must assert:** the real tracked tree contains no `TOKOBOROS_*` env-var shim — run the
  same scanner the gate runs, against the real files, not a fixture.
- **It must FAIL before your fix** with 11 reported hits in `src/hachi/cli/main.py`.

### 7b — both core readers honour the gate

- **File:** `tests/test_dotenv_hermeticity.py` (**existing** — it already owns this subject;
  do not start a new file)
- **Test names:** `test_llm_resolve_api_key_honours_disable_flag`,
  `test_oauth_resolve_env_honours_disable_flag`
- **It must assert:** with `HACHI_DISABLE_DOTENV_AUTOLOAD=1` and a real `.env` on disk in the
  CWD, each core resolver returns `None`. Assert **observed resolution**, not that a mock
  was called.
- **It must FAIL before your fix** with `AssertionError: assert 'from-dotenv' is None`.

```python
# sketch — adapt to the repo's existing fixtures
import pytest


def test_no_tokoboros_env_shim_in_src() -> None:
    """CLAUDE.md bans tokoboros shims; the ban must be mechanical, not advisory.

    Regression: a TOKOBOROS_* -> HACHI_* env shim was reintroduced at cli/main.py
    module scope after the hard rename and survived because nothing checked.
    """
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_bans.py")],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"ban-lint reported violations:\n{proc.stdout}"


def test_llm_resolve_api_key_honours_disable_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """BB-2: with autoload disabled, core must NOT read .env from the CWD."""
    from hachi.core import llm

    (tmp_path / ".env").write_text("HACHI_TEST_ONLY_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HACHI_TEST_ONLY_KEY", raising=False)
    monkeypatch.setenv("HACHI_DISABLE_DOTENV_AUTOLOAD", "1")

    assert llm._resolve_api_key("HACHI_TEST_ONLY_KEY") is None


def test_llm_resolve_api_key_still_reads_dotenv_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The capability is kept — only gated. Guards against over-deleting."""
    from hachi.core import llm

    (tmp_path / ".env").write_text("HACHI_TEST_ONLY_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HACHI_TEST_ONLY_KEY", raising=False)
    monkeypatch.setenv("HACHI_DISABLE_DOTENV_AUTOLOAD", "0")

    assert llm._resolve_api_key("HACHI_TEST_ONLY_KEY") == "from-dotenv"


def test_oauth_resolve_env_honours_disable_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The reader the audit missed. A fix that only touches llm.py leaves this open."""
    from hachi.core import oauth

    (tmp_path / ".env").write_text("GOOGLE_CLIENT_ID=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.setenv("HACHI_DISABLE_DOTENV_AUTOLOAD", "1")

    assert oauth._resolve_env("GOOGLE_CLIENT_ID") is None
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> `test_llm_resolve_api_key_still_reads_dotenv_when_enabled` is the exception — it passes
> today and must **keep** passing. It exists to stop you deleting the fallback instead of
> gating it.

## 8. Acceptance criteria

- [ ] The §7 tests exist; `test_no_tokoboros_env_shim_in_src` and both `honours_disable_flag` tests failed before the fix.
- [ ] `git grep -n "TOKOBOROS_" -- src/` returns **nothing**.
- [ ] `python -c "import os; os.environ['TOKOBOROS_SMTP_HOST']='x'; import hachi.cli.main; print(os.environ.get('HACHI_SMTP_HOST'))"` prints `None`.
- [ ] `scripts/check_bans.py` exists, exits 0, and exits 1 when the shim is pasted back (verify by hand).
- [ ] `ban-lint` is a **blocking** step in both `scripts/preflight.py` and `.github/workflows/ci.yml`.
- [ ] `rg -n "HACHI_DISABLE_DOTENV_AUTOLOAD" src/` shows the flag honoured in `core/llm.py`, `core/oauth.py`, and `cli/main.py` (via the shared helper).
- [ ] The lazy `.env` fallback still works when the flag is `0` — `test_llm_resolve_api_key_still_reads_dotenv_when_enabled` passes.
- [ ] `rg -n "own(ing|ed|ership)|other agents|this session" .github/workflows/ci.yml` returns **nothing**.
- [ ] Every remaining non-blocking CI gate carries an honest, dated reason and a ratchet condition.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not remove the `gateway/workspace.py` brand self-heal** (`:19`, `:50`, `:86`) or its
  tests. It reads the legacy token out of a *user's on-disk file* — that is data migration,
  not a compatibility shim, and deleting it strands existing users. Same for
  `pyproject.toml:150` `norecursedirs` (BB-7).
- **Do not start the mypy burn-down.** You are correcting the CI comment's *fiction*, not its
  numbers. The 471/66/40 figures and the ratchet belong to
  [T-69](T-69-mypy-burndown-ratchet.md).
- **Do not fix the bandit findings.** Decide the gate's blocking status and record the real
  count. Fixing medium-severity SAST findings is a separate, larger task.
- **Do not add more bans to `check_bans.py` than the one CLAUDE.md actually states.** A
  ban-lint that encodes bans nobody agreed to is the same failure mode in reverse.
- **Do not delete the `.env` fallback from core.** Gate it. See §5 Part 2 for the
  bug it fixed.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
  Deleting `TestTokoborosShim` is the one sanctioned removal: it tests a feature being
  deliberately removed under a repo-level ban. **Say so explicitly in the commit message.**
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite.** The shim executed on every `import hachi.cli.main` — which happens
in far more tests than the six that name it, including the cold-start resume path. And the
dotenv change affects credential resolution across the whole suite. A scoped run will not
surface either. Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — A banned compat shim and two `.env` bypasses survived because nothing checked

- **Symptom:** `TOKOBOROS_*` env vars were still silently copied to `HACHI_*` on every
  `import hachi.cli.main`, years after the hard rename and despite an explicit
  repo-level ban. Separately, `HACHI_DISABLE_DOTENV_AUTOLOAD=1` did not stop core from
  reading a CWD `.env`: two core resolvers read it directly.
- **Root cause:** Both rules were written in prose only. The tokoboros ban lived in
  CLAUDE.md with no gate step, so a later commit reintroduced the shim and CI stayed
  green. The dotenv gate was implemented as a local `if` inside
  `cli/main._load_dotenv_into_environ` rather than as a shared predicate, so
  `core/llm._resolve_api_key` and `core/oauth._resolve_env` — added later, independently —
  each grew their own ungated `Path.cwd() / ".env"` read.
- **Fix:** Deleted the shim and added `scripts/check_bans.py` as a BLOCKING preflight/CI
  step matching `TOKOBOROS_[A-Z0-9_]+` in `src/`+`scripts/` (deliberately not the bare
  brand word — `gateway/workspace.py`'s legacy-brain.og self-heal and `pyproject.toml`'s
  `norecursedirs` are legitimate). Added `core.paths.dotenv_autoload_disabled()` as the
  single definition of the gate and applied it at all three read sites.
- **Avoid:** a ban that is not a gate step is advice, and it will be violated. When you
  write "do not do X" in CLAUDE.md, add the check in the same commit. And when a rule has
  a second reader, make the rule a shared predicate — never a local `if`.
- **Locked by:** `tests/test_governance_bans.py` — `test_no_tokoboros_env_shim_in_src`;
  `tests/test_dotenv_hermeticity.py` — `test_llm_resolve_api_key_honours_disable_flag`,
  `test_oauth_resolve_env_honours_disable_flag`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **⚠️ `tests/test_oauth.py:139-148` `test_resolve_falls_back_to_project_dotenv` WILL go red,
  and that is correct.** It writes a `.env`, `chdir`s to it, and asserts
  `oauth._resolve_env("HACHI_TEST_ONLY_KEY") == "dotenv-value"` — while
  `tests/conftest.py:44` sets `HACHI_DISABLE_DOTENV_AUTOLOAD=1` for the whole suite. Amend
  it to opt in explicitly with `monkeypatch.setenv("HACHI_DISABLE_DOTENV_AUTOLOAD", "0")`,
  exactly as `tests/test_dotenv_hermeticity.py:49` already does. That is a **test
  amendment for a changed contract**, not a weakening — note it in the commit message.
  Its sibling at `:130-136` (`test_env_var_takes_precedence_over_dotenv`) keeps passing:
  the env var wins before the dotenv branch is reached.
- **`tests/conftest.py:44` uses `setdefault`, not `setenv`.** An operator who exports
  `HACHI_DISABLE_DOTENV_AUTOLOAD=0` before running pytest gets the *unhermetic* path. Your
  new tests must set the flag explicitly with `monkeypatch.setenv` rather than relying on
  the conftest default.
- **`scripts/preflight.py`'s `run_step` resolves `cmd[0]` via `shutil.which`.** A step whose
  argv starts with `grep` or `rg` fails with `` `grep` not found on PATH `` on a stock
  Windows box. Invoke `["uv", "run", "python", "scripts/check_bans.py"]` like every other
  script-backed step.
- **`.github/workflows/ci.yml` line numbers shift as you delete comment blocks.** Do part 3
  bottom-up (mypy `:121`, then ruff `:112`, then bandit `:87`) so earlier anchors stay valid.
- **Do not `import hachi` from `scripts/check_bans.py`.** Every script under `scripts/` is
  stdlib-only by convention (`check_adrs.py` says so in its docstring) — the gate must run
  even when the package is broken.
- **`cli/main.py` is a collision hotspot** (5,524 lines; also touched by T-03, T-04, T-41,
  T-55). Land this before or after those, not concurrently.
