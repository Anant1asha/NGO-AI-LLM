# T-07 · Register `[eval_reports]` on `ResolvedConfig` so the documented section stops being rejected

|  |  |
|---|---|
| **Source finding** | CF-1 #4 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~1 hour |
| **Difficulty** | Low (mechanical) — one field, one test |
| **Files you will touch** | `src/hachi/core/settings.py`, `settings.example.toml`, `tests/test_eval_report_config.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

`EvalReportSettings` exists, the weekly failure-report daemon exists, `boot_agent` reads
`config.get("eval_reports", {})` — but `ResolvedConfig` has **no `eval_reports` field**,
and its `model_config = ConfigDict(extra="ignore")` silently drops the whole section
during validation. Worse, the loader then **warns the user that their own documented key
is unknown**, and under `HACHI_CONFIG_STRICT=1` it *raises* — so a user who follows the
documented configuration and turns on strict mode gets a hard boot failure.

When you are done, one field on `ResolvedConfig` makes `[eval_reports] enabled = true`
work, the spurious unknown-key warning disappears, and the section is documented in
`settings.example.toml`.

## 2. Why this matters

This is the cheapest of the eight dead features and the clearest illustration of the
class: every individual piece was built and tested, and the one line that connects them
was never written. The schema is the wiring. A settings model that is not registered on
`ResolvedConfig` is not a setting — it is a data class nobody can reach.

The sharp edge makes it worse than inert: the loader actively tells the user they made a
mistake (`"contains unknown top-level key(s): eval_reports"`) for doing exactly what
`docs/DECISIONS.md` told them to do. That is the "report success / blame the user"
failure mode CF-1 is about, inverted.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The settings model exists

`src/hachi/core/settings.py:246-268` — `EvalReportSettings`:

```python
class EvalReportSettings(BaseModel):
    """Optional ``[eval_reports]`` config section — weekly failure-report automation.

    When ``enabled=True`` the gateway boots a resident daemon thread that wakes
    every ``interval_seconds`` (default: one week), reads the interaction_log via
    the live :class:`~hachi.core.session_store.SessionStore`, builds a failure
    report, and writes both ``eval-report-<stamp>.md`` and
    ``eval-report-<stamp>.json`` to ``state_dir/eval-reports/``.
    ...
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    interval_seconds: int = 604800  # 1 week
    limit: int = 1000
```

### 3.2 `ResolvedConfig` has no field for it

`src/hachi/core/settings.py:428-462`. The full field list is `meta`, `provider`,
`providers`, `agent`, `permissions`, `limits`, `memory`, `capabilities`, `channels`,
`routing`, `voice`, `events`, `jobs`, `observability`, `search`, `files`, `retention`,
`mcp_servers`. **No `eval_reports`.**

`:429`:

```python
class ResolvedConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
```

`extra="ignore"` is what makes the drop silent.

**The precedent is right there in the same class** — `mcp_servers` at `:458-462` carries
a comment describing this exact bug:

```python
    # [mcp_servers.<name>] sections — Model Context Protocol servers registered via the
    # UI/CLI. Kept as raw dicts (parsed by MCPServerConfig.from_toml_entry at boot) so the
    # section survives model_dump() — without this field it was silently dropped and
    # TOML-registered MCP servers never loaded.
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
```

Someone hit this once, fixed it for `mcp_servers`, and documented the mechanism —
without generalising the check.

### 3.3 Where the section is dropped

`src/hachi/core/config_loader.py:295-299`:

```python
    merged = defaults
    for layer in (global_config, project, env, cli):
        merged = _deep_merge(merged, layer)

    return ResolvedConfig.model_validate(merged)
```

The user's `[eval_reports]` table survives every merge layer and dies at
`model_validate`.

### 3.4 The loader then blames the user

`src/hachi/core/config_loader.py:27-29`:

```python
def _known_config_keys() -> frozenset[str]:
    """Return the set of top-level key names declared on ResolvedConfig."""
    return frozenset(ResolvedConfig.model_fields.keys())
```

`src/hachi/core/config_loader.py:81-92`, inside `_warn_unknown_keys`:

```python
    known = _known_config_keys()
    unknown = sorted(set(parsed.keys()) - known)
    if not unknown:
        return
    msg = (
        f"settings file {path} contains unknown top-level key(s): "
        f"{', '.join(unknown)}. "
        "These keys are ignored. Check for typos or consult settings.example.toml."
    )
    if strict:
        raise ValueError(msg)
    logger.warning(msg)
```

Called from `_read_toml` at `:146`. **`strict` is set from the environment** at `:124`:

```python
    strict = strict or bool(os.environ.get("HACHI_CONFIG_STRICT"))
```

So `HACHI_CONFIG_STRICT=1` + a documented `[eval_reports]` section = `ValueError` at
config load. That is the sharp edge.

### 3.5 Boot therefore always sees `{}`

`src/hachi/gateway/orchestrator.py:3671-3680`:

```python
    # ------------------------------------------------------------------
    # E5 — Weekly failure-report scheduler (opt-in, default off).
    # Mirrors _start_timeout_sweep: daemon thread, sleep loop, never raises.
    # Gated by [eval_reports] enabled = true in settings.toml.
    # ------------------------------------------------------------------
    _eval_cfg = EvalReportSettings.model_validate(config.get("eval_reports", {}))
    if _eval_cfg.enabled:
        _start_eval_report_scheduler(
            session_store, get_hachi_paths(), _eval_cfg, emit_runtime_event
        )
```

The `config` dict here is the post-`ResolvedConfig` dump — `boot_agent` gets it from
`load_config()` at `orchestrator.py:2666`, which is
`src/hachi/gateway/workspace.py:145-151`:

```python
def load_config() -> dict:
    """
    Loads the effective Hachi configuration.
    Falls back to defaults if not found.
    """
    ensure_workspace()
    return load_effective_config().model_dump(mode="python", exclude_none=True)
```

So `config.get("eval_reports", {})` is **always `{}`**, `enabled` is always `False`, and
the daemon never starts.

### 3.6 Documented as shipped

- `docs/DECISIONS.md:2025-2029`:

  > Boot wiring in `orchestrator.boot_agent` reads `config.get("eval_reports", {})` and calls
  > `_start_eval_report_scheduler` only when `enabled=True`.  Nothing runs unless the operator
  > adds `[eval_reports] enabled = true` to `settings.toml`.

- `docs/AUDIT.md:131` describes the same opt-in daemon as delivered.
- `settings.example.toml` has **no** `[eval_reports]` section at all
  (`grep -n eval_report settings.example.toml` → no output), so the only place a user
  can learn the key is `docs/DECISIONS.md` — which gives them the exact string that
  triggers the warning.

## 4. Reproduce the failure

Both halves are directly reproducible.

**The section is dropped:**

```bash
uv run python -c "
from hachi.core.settings import ResolvedConfig
c = ResolvedConfig.model_validate({'eval_reports': {'enabled': True, 'interval_seconds': 60}})
print('eval_reports survived?', 'eval_reports' in c.model_dump())
"
```

**You will see now:** `eval_reports survived? False`
**You should see after the fix:** `eval_reports survived? True`

**The user is warned about their own documented key:**

```bash
# write a settings file containing only the documented section, then load it
printf '[eval_reports]\nenabled = true\n' > "$TMPDIR/settings.toml"    # adapt path on Windows
uv run python -c "
import logging, pathlib
logging.basicConfig(level=logging.WARNING)
from hachi.core.config_loader import _read_toml
_read_toml(pathlib.Path(r'<path to that file>'), primary=True)
"
```

**You will see now:**

```
WARNING:hachi.core.config_loader:settings file ...settings.toml contains unknown top-level key(s): eval_reports. These keys are ignored. Check for typos or consult settings.example.toml.
```

**You should see after the fix:** no warning.

Add `strict=True` (or `HACHI_CONFIG_STRICT=1`) to the same call to see it become a
`ValueError` — that is the boot-failure path.

## 5. What "fixed" looks like

One field on `ResolvedConfig`, placed with the other optional sections (after
`retention`, before `mcp_servers`):

```python
    # Optional [eval_reports] section — absent = daemon off (opt-in, default False).
    eval_reports: EvalReportSettings = Field(default_factory=EvalReportSettings)
```

Use `Field(default_factory=...)` **not** `| None = None`, matching `events`, `jobs`,
`observability`, `search`, `files`, and `retention`. The model's own defaults already
express "off" (`enabled: bool = False`), so a defaulted instance is correct and
`boot_agent`'s `config.get("eval_reports", {})` keeps working unchanged.

Then document it in `settings.example.toml` (it is the file the warning text points users
at). Follow the existing commented-out convention used for `[provider] kind` variants:

```toml
# ---------------------------------------------------------------------------
# Weekly failure-report automation (opt-in, default off).
# When enabled, a resident daemon writes eval-report-<stamp>.md / .json into
# <state_dir>/eval-reports/ every `interval_seconds`.
# ---------------------------------------------------------------------------
# [eval_reports]
# enabled = true
# interval_seconds = 604800   # 1 week
# limit = 1000
```

**Make the failure loud (required by this task's Definition of Done).** The mechanism
that hid this — a settings model with no `ResolvedConfig` field — is invisible by
construction, so the "loud" half here is a *test*, not a log line: see §8's cross-link to
**T-02**. If you want a runtime signal as well, add a single line next to
`orchestrator.py:3676`:

```python
    if _eval_cfg.enabled:
        logger.info("[eval_reports] enabled — weekly failure-report daemon starting")
        _start_eval_report_scheduler(...)
```

That is enough to distinguish "I enabled it and it didn't start" from "I enabled it and
the config never arrived".

## 6. Steps

1. Write the regression test from §7 first. Run it. Watch it fail.
2. Add the `eval_reports` field to `ResolvedConfig` (`src/hachi/core/settings.py`,
   in the `:428-462` block).
3. Add the commented `[eval_reports]` block to `settings.example.toml`.
4. Add the `logger.info` at `orchestrator.py:3677`.
5. Run the test. Watch it pass.
6. Run `uv run python scripts/preflight.py`. Report real counts.
7. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_eval_report_config.py` (new)
- **Test names:** `test_eval_reports_section_survives_resolved_config`,
  `test_eval_reports_is_not_an_unknown_key`
- **It must assert:** that the values survive a real `ResolvedConfig.model_validate` →
  `model_dump()` round-trip (the exact path `load_config()` takes), and that
  `_warn_unknown_keys` does not flag the section.
- **It must FAIL before your fix** with:
  `KeyError: 'eval_reports'` (or `AssertionError: assert 'eval_reports' in {...}`) on the
  first, and `ValueError: settings file ... contains unknown top-level key(s): eval_reports`
  on the second.

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path

import pytest

from hachi.core.config_loader import _warn_unknown_keys
from hachi.core.settings import ResolvedConfig


def test_eval_reports_section_survives_resolved_config() -> None:
    raw = {"eval_reports": {"enabled": True, "interval_seconds": 3600, "limit": 50}}
    cfg = ResolvedConfig.model_validate(raw)

    # boot_agent reads the model_dump()'d dict, not the model — assert on that path.
    dumped = cfg.model_dump(mode="python", exclude_none=True)
    assert "eval_reports" in dumped, (
        "the [eval_reports] section was dropped by ConfigDict(extra='ignore') — "
        "ResolvedConfig has no field for it"
    )
    assert dumped["eval_reports"]["enabled"] is True
    assert dumped["eval_reports"]["interval_seconds"] == 3600


def test_eval_reports_is_not_an_unknown_key(tmp_path: Path) -> None:
    # strict=True turns the warning into a raise — this is the HACHI_CONFIG_STRICT path.
    _warn_unknown_keys({"eval_reports": {"enabled": True}}, tmp_path / "settings.toml", strict=True)
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The second test asserts by *not raising*. That is deliberate: it is the exact user-facing
symptom (documented key rejected) and it fails loudly today.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and failed before the fix.
- [ ] `"eval_reports" in ResolvedConfig.model_fields` is `True`.
- [ ] A `settings.toml` containing only `[eval_reports]\nenabled = true` loads with **no**
      unknown-key warning, and does not raise under `HACHI_CONFIG_STRICT=1`.
- [ ] `settings.example.toml` documents the section, and still parses
      (`tomllib.loads`) — see the cross-link below.
- [ ] `boot_agent` logs a line when the daemon starts.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

> **Cross-link — this bug class gets permanently locked by
> [T-02](T-02-settings-example-toml.md).** The CF-3 task (make `settings.example.toml`
> valid TOML) adds a test asserting `tomllib.loads(example)`
> succeeds **and** that the parsed keys are a subset of `ResolvedConfig.model_fields`.
> That subset assertion is what catches *"a documented section with no schema field"*
> forever. If T-02 has already landed when you start, adding your example-file block
> without the `ResolvedConfig` field will fail its test — which is exactly right.
> Coordinate: land the schema field, then the example block.

## 9. Out of scope — do NOT

- **Do not enable the daemon by default.** `enabled: bool = False` is a settled decision
  (`docs/DECISIONS.md:2025-2029`: *"Opt-in, default off"*). You are making the switch
  reachable, not flipping it.
- **Do not touch `core/eval/scheduled_report.py` or `_start_eval_report_scheduler`.** They
  are covered by 54 existing tests; the finding is purely that the config never arrives.
  If you find a bug in the daemon while testing, file it — do not fix it here.
- **Do not audit `ResolvedConfig` for other missing sections.** You will be tempted; the
  systematic answer is [T-02](T-02-settings-example-toml.md)'s subset test, not a manual
  sweep in this diff.
- **Do not change `extra="ignore"` to `extra="forbid"`.** That would turn every unknown
  key into a hard validation error at every layer and is a much larger behavioural
  decision than this task.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — `[eval_reports]` was documented, implemented, and rejected by the config schema

- **Symptom:** adding the documented `[eval_reports] enabled = true` to `settings.toml`
  did nothing — the weekly failure-report daemon never started — AND the loader logged
  "contains unknown top-level key(s): eval_reports". With `HACHI_CONFIG_STRICT=1` the
  same documented config raised `ValueError` and failed the boot outright.
- **Root cause:** `EvalReportSettings` existed and `boot_agent` read
  `config.get("eval_reports", {})`, but `ResolvedConfig` declared no `eval_reports`
  field. `model_config = ConfigDict(extra="ignore")` therefore dropped the section at
  `config_loader.load_effective_config`'s `ResolvedConfig.model_validate(merged)`, so the
  post-dump dict boot reads never contained it and `enabled` was always `False`. The same
  absence made `_known_config_keys()` (which derives from
  `ResolvedConfig.model_fields`) classify the user's key as unknown. `mcp_servers`
  carries a comment describing this exact mechanism from a previous occurrence.
- **Fix:** added `eval_reports: EvalReportSettings = Field(default_factory=EvalReportSettings)`
  to `ResolvedConfig`, documented the section in `settings.example.toml`, and added a
  boot log line when the daemon starts.
- **Avoid:** a settings model is not a setting until it is a field on `ResolvedConfig`.
  With `extra="ignore"`, an unregistered section is dropped silently AND reported to the
  user as their typo. Whenever you add a `*Settings` model, add the `ResolvedConfig`
  field in the same commit and assert the round-trip in a test.
- **Locked by:** `tests/test_eval_report_config.py` —
  `test_eval_reports_section_survives_resolved_config`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- `HACHI_CONFIG_STRICT` is read from the environment inside `_read_toml`
  (`config_loader.py:124`) **and** inside `load_effective_config` (`:274`). If your shell
  has it set, unrelated config tests will behave differently. `tests/conftest.py:93-114`
  snapshots and restores `os.environ` per test, so set it with `monkeypatch`, never
  directly.
- `load_config()` returns `model_dump(mode="python", exclude_none=True)`. With
  `exclude_none=True`, a `None`-valued field vanishes from the dict — another reason to
  use `default_factory` rather than an `| None` field.
- **BB-5:** `paths.workspace_dir` does not exist — use `get_hachi_paths().state_dir` (the
  daemon writes to `state_dir/eval-reports/`).
