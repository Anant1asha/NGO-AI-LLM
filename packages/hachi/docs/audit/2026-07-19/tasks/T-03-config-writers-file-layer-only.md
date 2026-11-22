# T-03 · Make config writers read the FILE layer only, so env overrides stop becoming permanent

|  |  |
|---|---|
| **Source finding** | CF-10 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **corrected by [CORRECTIONS.md](CORRECTIONS.md) §6 — read it before you start** |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~2-3 days |
| **Difficulty** | High (needs design judgement — read §9 and §12) |
| **Files you will touch** | `src/hachi/core/config_loader.py`, up to 13 of the 15 writer sites listed in §3.2, `src/hachi/gateway/provider_admin.py`, `tests/test_gateway_config_mutations.py`, one new/extended test file |

---

## 1. Brief

Every config writer in Hachi calls `load_effective_config()` — which merges defaults +
file + environment + CLI overrides — mutates one field, and hands the whole merged object
to `write_global_config()`, which serialises **all of it** back to `settings.toml`. So any
environment variable that happens to be set at the moment of an unrelated settings write is
**baked permanently into the user's config file**, including `HACHI_PERMISSION_TIER`. When
you are done, writers read only the *file* layer, apply their mutation to that, and write
that back — env overrides stay temporary, as the documented precedence promises.

## 2. Why this matters

Config precedence is a *promise* Hachi makes in its own docstring: "environment variables"
sit above the file and below CLI flags, i.e. they override *for this run*. This mechanism
silently converts that temporary override into durable state. That is bad for
`provider.model`. It is a **security defect** for `permissions.tier`, which is the safety
posture of an autonomous agent: a `HACHI_PERMISSION_TIER=unrestricted` set for one
debugging session, plus one innocuous "save my settings" click anywhere in the product,
permanently downgrades the user's guardrails with no prompt, no audit row, and no way to
tell it happened by looking at the UI.

The `exclude_none=True` serialisation compounds it: every non-`None` *default* is also
written, so the file accretes on every write and the user can no longer distinguish "I set
this" from "something wrote this at me".

If the fix you are about to write does not make an env var *stop* reaching the file, stop
and re-read this paragraph.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.
>
> ⚠️ Two line numbers in the source audit are **wrong** and are corrected below:
> `doc[key] = value` is at **:325** (audit said 332) and `exclude_none=True` is at **:312**
> (audit said 317).

### 3.1 The mechanism

`src/hachi/core/config_loader.py:254-299` — `load_effective_config`, the read half:

```python
def load_effective_config(
    project_dir: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
    paths: HachiPaths | None = None,
    *,
    strict: bool = False,
) -> ResolvedConfig:
    """Build the merged :class:`ResolvedConfig` from all config sources.

    Sources (lowest → highest precedence):
        built-in defaults → global settings.toml → project .hachi/settings.toml
        → environment variables / .env → cli_overrides.
    """
```

…ending in the four-layer merge at `:295-299`:

```python
    merged = defaults
    for layer in (global_config, project, env, cli):
        merged = _deep_merge(merged, layer)

    return ResolvedConfig.model_validate(merged)
```

`config_loader.py:302-333` — `write_global_config`, the write half. **This is the clobber:**

```python
def write_global_config(config: ResolvedConfig, paths: HachiPaths | None = None) -> Path:
    paths = paths or get_hachi_paths()
    ensure_directories(paths)

    if paths.global_config_toml.exists():
        doc = tomlkit.parse(paths.global_config_toml.read_text(encoding="utf-8"))
    else:
        doc = tomlkit.document()
        doc.add(tomlkit.comment("Hachi user settings"))

    payload = config.model_dump(mode="python", exclude_none=True)   # :312
    # Don't write an empty providers table — it's the default and would clutter the file.
    if not payload.get("providers"):
        payload.pop("providers", None)
    ...
    for key, value in payload.items():
        doc[key] = value                                            # :325  ← every top-level
                                                                    #        section replaced
                                                                    #        WHOLESALE
```

`tomlkit.parse` at `:307` reads the existing file, which *looks* like a merge — it is not.
`:324-325` overwrites each top-level section in its entirety with the merged-state value.
Only sections absent from `payload` survive, and `exclude_none=True` means almost nothing
is absent: every non-`None` default is present and therefore written.

### 3.2 The security consequence — env layer reaches the file

`config_loader.py:235-236`, inside `_env_overrides` (defined at `:168`):

```python
    if env_get("HACHI_PERMISSION_TIER"):
        result = _deep_merge(result, {"permissions": {"tier": env_get("HACHI_PERMISSION_TIER")}})
```

That `result` is layer 3 of 4 in the merge at `:296`. So `load_effective_config()` returns a
`ResolvedConfig` whose `permissions.tier` came from the environment — and the next
`write_global_config(config)` persists it.

`env_get` is defined at `config_loader.py:178-179`:

```python
    def env_get(name: str) -> str | None:
        return os.environ.get(name) or env_file.get(name)
```

`env_file` comes from `_read_env_file` (`config_loader.py:150`), which parses
`<project_dir>/.env`. **So a `.env` file on disk is enough to trigger this** — the operator
never has to export anything into their shell.

### 3.3 The 15 writers — corrected, complete table

Verified with `grep -rn "write_global_config" src/ --include=*.py`.

| # | Site | Notes |
|---|---|---|
| 1 | `src/hachi/channels/telegram_setup.py:103` | **missed by the audit** |
| 2 | `src/hachi/cli/main.py:724` | |
| 3 | `src/hachi/cli/main.py:790` | in the permissions/tier path — see the `# Bug 7` comment at `:792` |
| 4 | `src/hachi/cli/main.py:840` | |
| 5 | `src/hachi/cli/main.py:1623` | |
| 6 | `src/hachi/cli/main.py:1710` | |
| 7 | `src/hachi/cli/main.py:4349` | writes `cfg`, not `config` |
| 8 | `src/hachi/core/onboarding.py:526` | audit said `cli/onboarding.py` — **wrong package**. ⚠️ **KEEP MERGED** (§5) |
| 9 | `src/hachi/gateway/fastapi_app.py:2314` | Tavily connector persist |
| 10 | `src/hachi/gateway/provider_admin.py:186` | audit said `integrations/provider_admin.py` — **wrong package** |
| 11 | `src/hachi/gateway/provider_admin.py:229` | **missed by the audit** |
| 12 | `src/hachi/gateway/provider_admin.py:303` | **missed by the audit** |
| 13 | `src/hachi/gateway/voice_endpoints.py:455` | **missed by the audit** |
| 14 | `src/hachi/gateway/workspace.py:137` | audit said `core/workspace.py` — **wrong package**. ⚠️ **KEEP MERGED** (§5) |
| 15 | `src/hachi/tools/config_tools.py:721-732` | **INJECTED** — see §3.4 |

The canonical shape, `gateway/provider_admin.py:139-140`:

```python
    with _CONFIG_LOCK:
        config = load_effective_config()
```

and at `:186`, after mutation:

```python
        write_global_config(config)
```

A second common shape uses `model_copy` — `gateway/voice_endpoints.py:453-455`:

```python
    new_voice = current_voice.model_copy(update=update)
    new_config = current.model_copy(update={"voice": new_voice})
    write_global_config(new_config)
```

`model_copy` on a merged `ResolvedConfig` is still a merged `ResolvedConfig`. It does not
help.

### 3.4 The scariest one: the LLM itself can trigger a merged write

`src/hachi/tools/config_tools.py:721-733` — the mount function wires the real loader and
the real writer into an **agent-facing tool**:

```python
    from hachi.core.config_loader import load_effective_config, write_global_config

    registry.register(ADD_MCP_SERVER_SCHEMA, _make_add_mcp_server(gate))
    ...
    registry.register(
        SET_AGENT_CONFIG_SCHEMA,
        _make_set_agent_config(load_effective_config, write_global_config),
    )
```

The factory is `_make_set_agent_config` at `config_tools.py:534`, and the actual write is
inside the closure it returns, at `config_tools.py:571`:

```python
            write_config_fn(updated)
```

So `set_agent_config` — a tool **the model can call on its own initiative**, e.g. to change
`agent.name` — runs the full load-merged → write-merged cycle. An LLM changing the agent's
display name can persist an environment-derived permission tier. Whatever you do to the
other writers, do it here too.

### 3.5 The file-only loader already exists — do not write a new one

`config_loader.py:105-147` — `_read_toml`. It is used for exactly this purpose at `:279`:

```python
    global_config = _read_toml(paths.global_config_toml, primary=True, strict=strict)
```

It returns a plain `dict[str, Any]` of *only* what is in that one file — no defaults, no
env, no project layer, no CLI. That is the file layer.

**Two caveats that shape the whole implementation:**

1. It is private (`_`-prefixed). Exposing it (a thin public `read_global_config_file()`
   wrapper, or renaming) is part of this task.
2. **Do not re-validate the dict through `ResolvedConfig`.** `ResolvedConfig.model_validate(
   file_dict)` re-inflates every field with its default, and `write_global_config`'s
   `exclude_none=True` dump then writes all of them back — **reproducing exactly the bug you
   are fixing**, minus only the env layer. The dict must stay a plain dict from read,
   through mutation, to write.

### 3.6 The lock

`gateway/provider_admin.py:30`:

```python
_CONFIG_LOCK = threading.Lock()
```

It has **three** usages, not one (the audit said one): `provider_admin.py:139`, `:213`,
`:285` — each `with _CONFIG_LOCK:` wrapping a load→mutate→write sequence. The other 12
writers hold no lock at all and can lose updates against each other and against
`provider_admin`.

## 4. Reproduce the failure

This one is **not** reproducible with a single shell command, because the writers are
buried behind CLI commands and gateway routes. The honest reproduction is a short script
that drives the real loader and the real writer — this is also the skeleton of your
regression test.

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
python - <<'PY'
import os, sys, tempfile, pathlib
sys.path.insert(0, "src")

# 1. Point Hachi at a throwaway config dir and set the env override.
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["HACHI_PERMISSION_TIER"] = "unrestricted"

from hachi.core.paths import HachiPaths
from hachi.core.config_loader import load_effective_config, write_global_config

paths = HachiPaths(
    config_dir=tmp / "config", data_dir=tmp / "data",
    cache_dir=tmp / "cache", state_dir=tmp / "state",
)

# 2. Seed a settings.toml that does NOT mention the tier.
paths.config_dir.mkdir(parents=True, exist_ok=True)
paths.global_config_toml.write_text('[agent]\nname = "Hachi"\n', encoding="utf-8")

# 3. Perform a completely unrelated settings write, exactly as every writer does.
cfg = load_effective_config(paths=paths)
cfg.agent.name = "Renamed"
write_global_config(cfg, paths=paths)

print(paths.global_config_toml.read_text(encoding="utf-8"))
PY
```

**You will see now:** a `[permissions]` table in the output containing
`tier = "unrestricted"` — an environment variable has become permanent file state — plus a
large amount of default noise (`[meta]`, `[memory]`, `[events]`, `[jobs]`, `[retention]`, …)
that the user never wrote.

**You should see after the fix:** `[agent] name = "Renamed"` and nothing else. No
`[permissions]` table, no defaults.

**Code-reading proof** (in case the script drifts): `_env_overrides` folds
`HACHI_PERMISSION_TIER` into layer 3 (`config_loader.py:235-236`) → `load_effective_config`
merges all four layers into the returned object (`:295-299`) → `write_global_config`
`model_dump(exclude_none=True)` (`:312`) → `doc[key] = value` per top-level section (`:325`).
There is no provenance tracking anywhere on that path, so nothing can distinguish
"tier came from the file" from "tier came from the environment".

## 5. What "fixed" looks like

Add a public file-layer read + a dict-based write to `core/config_loader.py`. Suggested
shape (adapt names to the module's conventions):

```python
def read_global_config_file(paths: HachiPaths | None = None) -> dict[str, Any]:
    """Return ONLY what is written in the global settings.toml — no defaults,
    no environment, no project layer, no CLI overrides.

    This is what a writer must read before mutating, so that transient env
    overrides are not persisted back into the file.
    """


def write_global_config_dict(payload: dict[str, Any], paths: HachiPaths | None = None) -> Path:
    """Persist a FILE-LAYER dict verbatim. Takes the config lock internally."""
```

Converted writers then look like:

```python
    doc = read_global_config_file()                     # plain dict, file layer only
    doc.setdefault("permissions", {})["tier"] = tier    # mutate the dict, NOT a model
    write_global_config_dict(doc)
```

Keep the existing `write_global_config(config: ResolvedConfig, ...)` — it is still needed by
the two bootstrap sites below, and removing it breaks 15 tests that patch it by name (§12).

**Move `_CONFIG_LOCK` into `config_loader`** and take it inside the writer, so all writers
are serialised rather than only `provider_admin`'s three. Then **`provider_admin` should drop
its own `with _CONFIG_LOCK:` at `:139`, `:213`, `:285`** — a `threading.Lock` is *not*
reentrant, so leaving both in place is a **self-deadlock**, not merely redundant nesting.
If you prefer to keep the outer lock, the inner one must be the same lock object and you
must switch it to `threading.RLock`. Pick one; state which in the commit message.

### ⚠️ Two sites MUST KEEP merged semantics — do not convert all 15

**`src/hachi/gateway/workspace.py:136-137`:**

```python
    # Create canonical TOML config if it doesn't exist
    if not paths.global_config_toml.exists():
        write_global_config(load_effective_config(paths=paths), paths=paths)
```

This is a **first-run bootstrap**: it fires only when the file does *not* exist, and its
whole job is to materialise a starter file from the merged/default view. Converting it to
file-layer-only would write an empty document.

**`src/hachi/core/onboarding.py:526`:**

```python
        write_global_config(config, paths=self.paths)
```

The onboarding wizard *constructs* the initial config from the user's answers and persists
it as a whole. Converting it breaks the setup wizard.

A blanket conversion of all 15 sites breaks onboarding. **Convert 13. Leave these 2.** Add a
one-line comment at each of the two explaining why it is deliberately merged, so the next
reader does not "finish the job".

### The env-var check

After the fix, `HACHI_PERMISSION_TIER=unrestricted` + any write from the 13 converted sites
must leave `settings.toml` with no `permissions.tier`. That is the acceptance test.

## 6. Steps

1. **Write the regression test from §7 first.** Run it. Watch it fail.
2. Add `read_global_config_file()` to `core/config_loader.py` as a thin public wrapper over
   the existing `_read_toml` (§3.5). Do **not** write a new parser.
3. Add `write_global_config_dict(payload, paths=None)` next to `write_global_config`.
   Factor the atomic tmp-file + `os.replace` block (`config_loader.py:327-333`) so both
   share it — do not duplicate it.
4. Move `_CONFIG_LOCK` from `provider_admin.py:30` into `config_loader.py`; take it inside
   **both** writers.
5. Remove the three `with _CONFIG_LOCK:` statements in `provider_admin.py` (`:139`, `:213`,
   `:285`) — or convert the shared lock to `RLock`. Do not leave a plain `Lock` taken twice.
6. Convert the 13 non-bootstrap writers one file at a time, running the test suite between
   files. Order: `provider_admin.py` (3) → `cli/main.py` (6) → `voice_endpoints.py` →
   `fastapi_app.py` → `telegram_setup.py` → `config_tools.py`.
7. For `config_tools.py`, change what is *injected* at `:732` so `_make_set_agent_config`
   receives the file-layer pair. Its internals (`:534-571`) mutate what they are handed —
   check that the mutation code at `:537-571` works on a dict, or adapt it.
8. Add the explanatory comment at `workspace.py:137` and `onboarding.py:526`.
9. Rewrite `tests/test_gateway_config_mutations.py::test_update_permissions_persists_ask_before_rule`
   to the new contract (§12) — and say so explicitly in the commit message.
10. Full `uv run python scripts/preflight.py`, report real counts.
11. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_config_resilience.py` (existing — it already exercises
  `write_global_config` against real `HachiPaths` at `:30-33`, so the fixtures you need are
  there) **or** a new `tests/test_config_write_file_layer.py`.
  **See the warning below before choosing `tests/test_config_get_set.py`.**
- **Test name:** `test_env_override_is_not_persisted_by_unrelated_write`
- **It must assert:** after setting `HACHI_PERMISSION_TIER` in the environment and performing
  an *unrelated* settings write through a real writer, the **text of `settings.toml` on
  disk** contains no `tier` / `unrestricted`. Assert on the file's bytes, not on a returned
  object — the returned object is allowed to be merged; the *file* is not.
- **It must FAIL before your fix** with something like:
  `AssertionError: env override leaked into settings.toml: [permissions]\ntier = "unrestricted"`

### ⚠️ The test is invisible unless it SETS the env var

The bug only manifests when an env override is present. A test that does not set
`HACHI_PERMISSION_TIER` passes before *and* after the fix and proves nothing.

### ⚠️ Do not put this test in `tests/test_config_get_set.py` without checking

That file defines an env-scrubbing list at `tests/test_config_get_set.py:27-36`:

```python
_ENV_VARS = (
    "HACHI_MAX_SESSION_COST_USD",
    "HACHI_PERMISSION_TIER",
    "HACHI_MAX_TOKENS",
    ...
)
```

…consumed by `for var in _ENV_VARS:` loops at `:216`, `:236`, `:257`. If your new test ends
up inside a class or fixture that scrubs those vars, it will **delete the very variable the
test depends on** and pass vacuously. Verify by reading the surrounding scope, or place the
test elsewhere.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

from pathlib import Path

from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.paths import HachiPaths


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def test_env_override_is_not_persisted_by_unrelated_write(tmp_path: Path, monkeypatch) -> None:
    """A transient HACHI_PERMISSION_TIER must NOT be baked into settings.toml by an
    unrelated settings write.

    Config precedence promises env overrides the file *temporarily*. Writers that
    load the merged view and persist it convert that override into durable state —
    silently downgrading the agent's safety posture.
    """
    paths = _paths(tmp_path)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.global_config_toml.write_text('[agent]\nname = "Hachi"\n', encoding="utf-8")

    monkeypatch.setenv("HACHI_PERMISSION_TIER", "unrestricted")

    # An unrelated write, exactly as every converted writer performs it.
    # >>> replace with the real post-fix API once it exists <<<
    cfg = load_effective_config(paths=paths)
    cfg.agent.name = "Renamed"
    write_global_config(cfg, paths=paths)

    text = paths.global_config_toml.read_text(encoding="utf-8")
    assert "unrestricted" not in text, f"env override leaked into settings.toml:\n{text}"
    assert "[permissions]" not in text, f"unwritten section persisted:\n{text}"
    # The actual mutation still landed.
    assert "Renamed" in text
```

Add a **second** test asserting the LLM-facing path, since that is the one the review
missed entirely: drive `set_agent_config` (built via
`_make_set_agent_config`, `tools/config_tools.py:534`) with the same env var set, and assert
the same properties of the file.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, sets `HACHI_PERMISSION_TIER`, and failed before
      the fix.
- [ ] A second test covers the `set_agent_config` (LLM-triggered) write path.
- [ ] 13 of the 15 sites in §3.2 read the file layer; `gateway/workspace.py:137` and
      `core/onboarding.py:526` still read the merged view and each carries a comment saying why.
- [ ] `settings.toml` no longer accretes defaults: after a single unrelated write to a file
      containing only `[agent]`, the file contains only `[agent]` (plus the mutated section).
- [ ] `_CONFIG_LOCK` lives in `config_loader` and is taken inside the writer; `provider_admin`
      no longer double-takes a non-reentrant lock at `:139`/`:213`/`:285`.
- [ ] `tests/test_gateway_config_mutations.py::test_update_permissions_persists_ask_before_rule`
      has been **rewritten to the new contract** (not deleted, not skipped) and the commit
      message says so — see §12.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not add layer-provenance tracking to `ResolvedConfig`.** Tagging each field with the
  layer it came from is the "proper" architectural fix and it is a much larger change with
  a much larger blast radius. The file-layer read gets the same user-visible outcome. If you
  find yourself designing a `ProvenanceDict`, stop.
- **Do not change the precedence order** in `load_effective_config` (`config_loader.py:295-299`).
  The *read* path is correct. Only the *write* path is wrong.
- **Do not "clean up" the accreted defaults in an existing user's `settings.toml`.** A
  migration that prunes keys from a real user's file is a separate, riskier task.
- **Do not convert `workspace.py:137` or `onboarding.py:526`.** Re-read §5.
- **Do not re-validate the file dict through `ResolvedConfig` "for safety".** §3.5, caveat 2:
  it reproduces the bug.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. (`tomlkit` is already a dependency and is
  what `write_global_config` uses.)
- Do not fix other findings you notice in passing — note them and move on. In particular
  you will walk past **BB-25**'s territory (tier writes needing a `device-permissions.og`
  regeneration, `cli/main.py:790-796`). Leave it.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Targeted runs while converting (Windows: `python -m pytest` per BB-1):

```bash
uv run pytest tests/test_gateway_config_mutations.py tests/test_config_get_set.py \
              tests/test_config_resilience.py tests/test_provider_admin.py \
              tests/test_voice_endpoints.py tests/test_onboarding_validation.py \
              tests/test_workspace_brand_heal.py tests/test_config_tools.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**).

**No existing entry covers this mechanism.** BB-15 is a frontend `Promise.all` bug (a
`/models` rejection resetting `safety` in the UI's catch block). **BB-25** is adjacent —
`update_permissions(tier)` writing `settings.toml` without regenerating
`device-permissions.og` — but that is a *missing side-effect*, a different defect.
Cross-reference BB-25; do **not** claim to be its root cause.

```markdown
### BB-N — Any settings write baked transient env overrides (incl. HACHI_PERMISSION_TIER) permanently into settings.toml

- **Symptom:** a permission tier (or model, or token cap) set via an environment variable
  or a project `.env` for one run became permanent — it survived unsetting the variable —
  after any unrelated settings change anywhere in the CLI, gateway, or even an LLM
  `set_agent_config` tool call. `settings.toml` also grew a wall of default sections the
  user never wrote.
- **Root cause:** all 15 writers called `load_effective_config()` (defaults + file + env +
  CLI, `core/config_loader.py:295-299`) and handed the whole merged `ResolvedConfig` to
  `write_global_config()`, which `model_dump(exclude_none=True)`s it (`:312`) and replaces
  every top-level section wholesale with `doc[key] = value` (`:325`). Nothing on that path
  tracked which layer a value came from. `HACHI_PERMISSION_TIER` enters at `:235-236`, and
  `env_get` (`:178-179`) also reads a project `.env` via `_read_env_file` (`:150`), so no
  shell export was even required.
- **Fix:** writers now read the FILE layer only (public wrapper over the pre-existing
  `_read_toml`, `:105`), mutate that plain dict, and write the dict back. The dict is never
  re-validated through `ResolvedConfig` — doing so re-inflates every default and reproduces
  the bug. `_CONFIG_LOCK` moved into the writer so all writers serialise, not just
  `provider_admin`'s three. `gateway/workspace.py:137` and `core/onboarding.py:526` keep
  merged semantics deliberately — they are first-run bootstraps that *create* the file.
- **Avoid:** never persist the output of a layered/merged config resolver. Read the layer
  you own, mutate it, write it back. A writer that reads `load_effective_config()` is a bug.
- **Locked by:** `tests/test_config_resilience.py` —
  `test_env_override_is_not_persisted_by_unrelated_write`
```

## 12. Known traps

- **A test will legitimately FAIL under a correct fix — REWRITE it, do not weaken it.**
  `tests/test_gateway_config_mutations.py:304-318`,
  `test_update_permissions_persists_ask_before_rule`:

  ```python
      monkeypatch.setattr("hachi.cli.main.write_global_config", captured.append)   # :309
      ...
      # The same config object was handed to write_global_config (persisted).      # :317
      assert captured and captured[0].permissions.ask_before.delete_files is False # :318
  ```

  This **encodes the merged-write bug as the contract**: it asserts the same
  `ResolvedConfig` object is what gets persisted. After the fix, a file-layer dict is
  persisted and `captured[0].permissions` raises `AttributeError`.

  [CLAUDE.md](../../../../CLAUDE.md) Rule 2 forbids *weakening* a test to go green. It does
  not forbid *correcting* a test that asserts wrong behaviour. Rewrite it to assert the new
  contract (the persisted payload contains `permissions.ask_before.delete_files is False`
  and does **not** contain unrelated sections), and **say this explicitly in the commit
  message** so a reviewer does not read the diff as test-tampering.

- **15 tests patch the writer by NAME and will silently keep passing while testing nothing.**
  `tests/test_gateway_config_mutations.py` has 15 `monkeypatch.setattr(
  "hachi.cli.main.write_global_config", …)` sites (lines 77, 109, 132, 150, 194, 208, 250,
  261, 273, 288, 309, 325, 339, 349, 359) across 20 test functions. Also
  `tests/test_config_get_set.py:54`, `tests/test_g1_wave1.py:392`,
  `tests/test_gateway_runtime_validation.py:35` and `:46`, and
  `tests/test_provider_admin.py:58` (which patches
  `hachi.gateway.provider_admin.write_global_config`), and
  `tests/test_workspace_brand_heal.py:165`.
  If you introduce a differently-named writer and leave `write_global_config` importable,
  every one of these patches keeps succeeding against a function the code no longer calls —
  green tests, zero coverage. **After converting each file, grep its tests for the patch
  target and update it.**

- **`threading.Lock` is not reentrant.** Moving `_CONFIG_LOCK` inside the writer while
  leaving `provider_admin.py:139/:213/:285` holding it is a hard deadlock on the first
  provider write, not a slow path.

- **The lock will now be taken on the LLM tool-execution path.** `set_agent_config`
  (`config_tools.py:534`, mounted at `:732`) runs inside a tool call, which runs inside the
  execution loop, which may already be holding other locks. Trace the call path once before
  you land it and convince yourself there is no lock-ordering cycle. Note it in the commit
  message either way.

- **`tests/test_provider_admin.py:45-58`** patches both the loader and the writer via a
  helper context manager. If you change the injected pair, that helper needs updating too.

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-4:** any gateway route change ⇒ regenerate the OpenAPI spec **and** the frontend API
  types, or CI fails. You should not be changing route *shapes* here — but
  `gateway/fastapi_app.py:2314`, `gateway/voice_endpoints.py:455` and
  `gateway/provider_admin.py` are all inside route handlers, so if a response body changes,
  this applies.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots.
