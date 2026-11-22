# T-02 · Make `settings.example.toml` parse, and lock it with a test

|  |  |
|---|---|
| **Source finding** | CF-3 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · corrected by [CORRECTIONS.md](CORRECTIONS.md) §11 |
| **Severity** | P0 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | <1 day |
| **Difficulty** | Low (mechanical) — but read §7, the test has a real trap |
| **Files you will touch** | `settings.example.toml`, `tests/test_config_loader.py` |

> **This is the recommended first task in the pack.** It is small, fully self-contained,
> reproducible in one command, and the test it adds permanently guards a whole class of
> config drift.

---

## 1. Brief

`settings.example.toml` — the file the repo tells users to copy as their config — is **not
valid TOML**. It contains 11 lines of the form `key = null`, and TOML has no null literal.
`tomllib` aborts at the first one. When you are done: the file parses, every documented
`| None` default is still visible to a reader (as a comment, not a deleted line), and a
test in `tests/test_config_loader.py` fails the build if either property regresses.

## 2. Why this matters

A user who follows the file's own header (`Copy to ~/.config/hachi/settings.toml`) and then
edits it produces a settings file that **Hachi silently discards in full**. The loader logs
an error and returns `{}` — the process keeps running on built-in defaults. Every single
setting the user wrote is inert, with no crash and no exit code to notice. The failure mode
is not "one key was ignored", it is "I configured Hachi and *nothing at all* changed", on
first-run onboarding, which is the one flow a v1 cannot fumble.

So the fix is not "make the parser happy". It is **make the example file a thing a user can
actually copy**, while keeping it honest about what the defaults are. That second half is
why §5 forbids the obvious shortcuts.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The 11 live `= null` lines

`settings.example.toml` — verified by `grep -n "null"`:

| Line | Key | Section |
|---|---|---|
| 122 | `max_daily_cost_usd` | `[limits]` |
| 126 | `max_session_cost_usd` | `[limits]` |
| 130 | `max_turn_cost_usd` | `[limits]` |
| 134 | `max_session_tokens` | `[limits]` |
| 138 | `max_turn_tokens` | `[limits]` |
| 181 | `stt_base_url` | `[voice]` |
| 197 | `tts_base_url` | `[voice]` |
| 213 | `elevenlabs_api_key_env` | `[voice]` |
| 217 | `elevenlabs_voice_id` | `[voice]` |
| 231 | `provider` | `[search]` |
| 355 | `endpoint` | (observability/exporter section) |

> The review said **ten**. It is **eleven**. Do not stop at ten.

`settings.example.toml:116-138` — the `[limits]` block, quoted verbatim:

```toml
# ---------------------------------------------------------------------------
# [limits] — cost and token safety caps (null = no cap)
# ---------------------------------------------------------------------------
[limits]
# type: float | null, default: null
# effect: rolling calendar-day total spend cap in USD; session is blocked when reached.
max_daily_cost_usd = null          # e.g. 5.0

# type: float | null, default: null
# effect: per-session cumulative spend cap in USD.
max_session_cost_usd = null        # e.g. 1.0

# type: float | null, default: null
# effect: per-turn spend cap in USD; turn is aborted when exceeded.
max_turn_cost_usd = null           # e.g. 0.10

# type: int | null, default: null
# effect: per-session token limit (input + output combined).
max_session_tokens = null          # e.g. 200000

# type: int | null, default: null
# effect: per-turn token limit.
max_turn_tokens = null             # e.g. 8192
```

### 3.2 Line 47 — the style precedent, already correct

`settings.example.toml:45-47`:

```toml
# [SENSITIVE] type: str | null, default: null
# effect: direct reference to a stored secret (use api_key_env instead when possible).
# api_key_ref = null
```

This one is **already commented out**, so `tomllib` never sees it. **Leave it exactly as
is** — it is harmless, and it is the formatting you are copying for the other 11.

### 3.3 The silent-discard path

`src/hachi/core/config_loader.py:105` — `_read_toml`:

```python
def _read_toml(
    path: Path,
    *,
    primary: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
```

`config_loader.py:128-145` — the except arm:

```python
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        if primary:
            logger.error(
                "PRIMARY settings file %s is malformed and was IGNORED. "
                "Hachi is running on built-in defaults. "
                "Fix the file or delete it to restore normal operation. "
                "Parse error: %s",
                path,
                exc,
            )
        else:
            # A corrupt secondary config must not crash every command.
            logger.warning("Ignoring malformed config %s: %s", path, exc)
        if strict:
            raise
        return {}
```

Two corrections to the review here:

- It is `logger.**error**` on the primary path (`:132`), not "a log-line warning". The
  warning at `:142` is the *secondary* (project-local) path.
- The escape hatch is real and a test can use it: `strict=True`, or the env var
  `HACHI_CONFIG_STRICT` (folded in at `config_loader.py:124`), makes `:143-144` **re-raise**
  the `TOMLDecodeError` instead of returning `{}`.

The primary global file is read with `primary=True` at `config_loader.py:279`, inside
`load_effective_config`:

```python
    global_config = _read_toml(paths.global_config_toml, primary=True, strict=strict)
```

### 3.4 `ResolvedConfig` — the target of the second assertion

`src/hachi/core/settings.py:428-462` — `ResolvedConfig`:

```python
class ResolvedConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meta: ConfigMeta = Field(default_factory=ConfigMeta)
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    permissions: PermissionsSettings = Field(default_factory=PermissionsSettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    capabilities: dict[str, CapabilityState] = Field(default_factory=dict)
    channels: ChannelSettings = Field(default_factory=ChannelSettings)
    routing: RoutingSettings | None = None
    voice: VoiceSettings | None = None
    events: EventsSettings = Field(default_factory=EventsSettings)
    jobs: JobsSettings = Field(default_factory=JobsSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    files: FileSettings = Field(default_factory=FileSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
```

(Comments elided for length — read the real file.)

### 3.5 What already exists, and what it does NOT cover

`config_loader.py:27-29` — `_known_config_keys`:

```python
def _known_config_keys() -> frozenset[str]:
    """Return the set of top-level key names declared on ResolvedConfig."""
    return frozenset(ResolvedConfig.model_fields.keys())
```

`config_loader.py:70-81` — `_warn_unknown_keys`, whose own docstring states the gap:

```python
def _warn_unknown_keys(parsed: dict[str, Any], path: Path, *, strict: bool = False) -> None:
    """Compare *parsed* TOML against known ResolvedConfig fields and warn/raise on unknowns.

    Only top-level keys are checked — sub-section extra keys are silently
    ignored by Pydantic's ``extra="ignore"`` setting on each nested model.
```

**Reuse `_known_config_keys()` for the top level.** Your test's value-add is the
**recursive** walk into sections, which nothing in the repo does today.

### 3.6 Nothing has ever machine-checked this file

`grep -rn "example\.toml" tests/` returns **nothing**. Repo-wide the only mentions are
prose in `docs/guides/configuration.md`, `docs/DECISIONS.md`, the file's own header, and
one user-facing message string at `config_loader.py:88`. The example file has never been
parsed by CI.

## 4. Reproduce the failure

Fully reproducible from a shell, in one command, from the repo root:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
python -c "import tomllib; tomllib.loads(open('settings.example.toml', encoding='utf-8').read())"
```

**You will see now:**

```
tomllib.TOMLDecodeError: Invalid value (at line 122, column 22)
```

**You should see after the fix:** no output, exit code 0.

To see the *silent discard* end-to-end (optional, but it is the actual user harm):

```bash
python - <<'PY'
import logging, tempfile, pathlib, sys
sys.path.insert(0, "src")
logging.basicConfig(level=logging.ERROR)
from hachi.core.config_loader import _read_toml
d = pathlib.Path(tempfile.mkdtemp()) / "settings.toml"
d.write_text(pathlib.Path("settings.example.toml").read_text(encoding="utf-8"), encoding="utf-8")
print("returned:", _read_toml(d, primary=True))
PY
```

**You will see now:** the `PRIMARY settings file … is malformed and was IGNORED` error, then
`returned: {}` — the process continues normally. **You should see after the fix:** the full
parsed dict and no error line.

## 5. What "fixed" looks like

For each of the **11** lines in §3.1: **comment the assignment out**, keeping the value and
the trailing example, exactly matching the line-47 precedent. E.g. line 122 becomes:

```toml
# type: float | null, default: null
# effect: rolling calendar-day total spend cap in USD; session is blocked when reached.
# max_daily_cost_usd = 5.0
```

Keep whatever inline example the line already carried (`# e.g. 5.0`) as the commented
value where one exists, so a user can uncomment a *working* line rather than uncommenting
`= null` and reintroducing the bug. Where no example value exists (e.g. `stt_base_url`),
comment it out with a plausible illustrative value or leave the key with no value in the
comment — but **never** leave a live `= null`.

**Do NOT "fix" it by:**

- **Deleting the lines.** They are the only place several `| None` defaults are documented.
  Rule 3 of [CLAUDE.md](../../../../CLAUDE.md) forbids deleting documentation you were not
  asked to delete.
- **Setting them to `0` or `""`.** This makes the example *wrong*, and dangerously so:
  in `[limits]`, `None` means **"no cap"** while `0` is a **live cap value**. Look at the
  loader's own consumers — a `0` cap and an absent cap are different program states. An
  example file that ships `max_daily_cost_usd = 0` documents a behaviour Hachi does not have.

Then add the test from §7. The test is the real deliverable; the TOML edit without the
test just resets the clock on the same bug.

## 6. Steps

1. `grep -n "= null" settings.example.toml` and confirm you get exactly 11 hits (line 47 is
   already `# api_key_ref = null`, so it will not match `= null` at the start of a value
   position — verify by eye which 11 are live).
2. **Write the test from §7 first.** Run it. Watch it fail on the `tomllib` assertion.
3. Comment out the 11 lines, one at a time, matching the line-47 style.
4. Re-run the test. The `tomllib` assertion now passes; the recursive-keys assertion should
   also pass. If it does **not**, you have found real drift — read §9 before "fixing" it.
5. Run `uv run python scripts/preflight.py --quick`.
6. Add the bug-bank entry from §11.
7. Run the full `uv run python scripts/preflight.py` and report real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_config_loader.py` (existing — append to it)
- **Test names:** `test_settings_example_toml_parses` and
  `test_settings_example_toml_keys_are_known_config_fields`
- **They must assert:** (1) `tomllib.loads()` of the real `settings.example.toml` on disk
  succeeds; (2) every key in the parsed document corresponds to a real field on
  `ResolvedConfig` or one of its nested section models, walked **recursively**.
- **Test 1 must FAIL before your fix** with:
  `tomllib.TOMLDecodeError: Invalid value (at line 122, column 22)`

### The trap that makes a naive version of test 2 pass vacuously

`ResolvedConfig` **and all 20 nested section models** carry `model_config =
ConfigDict(extra="ignore")` (21 occurrences of `extra="ignore"` in `settings.py`).
Therefore:

```python
ResolvedConfig.model_validate(parsed)   # NEVER raises on unknown keys — useless as an assertion
```

Verified empirically:

```
>>> ResolvedConfig.model_validate({'totally_bogus': {...}, 'limits': {'nope': 5}, 'eval_reports': {...}})
model_validate did NOT raise.
  bogus top-level kept?   False
  eval_reports kept?      False
  limits after nested-unknown: {'max_daily_cost_usd': None, ...}   # 'nope' silently gone
```

**You must walk `model_fields` by hand.** Do not route the assertion through
`model_validate`, and do not flip any model to `extra="forbid"` (that is a runtime
behaviour change, out of scope — see §9).

### Sections to EXEMPT from the recursion

Three fields are open-ended dicts whose **keys are chosen by the user**, so their children
must not be checked against a field list:

- `providers` — `settings.py:435`, `dict[str, ProviderSettings]`
- `capabilities` — `settings.py:440`, `dict[str, CapabilityState]`
- `mcp_servers` — `settings.py:461-462`, `dict[str, dict[str, Any]]`

(If you want to go further you may recurse into their *values* against `ProviderSettings` /
`CapabilityState`. Not required.)

### Two fields need care when recursing

`routing` (`settings.py:443`) and `voice` (`settings.py:445`) are `X | None = None` — **no
default factory**. You cannot get the nested model off an instance (it will be `None`);
resolve the annotation instead. Handling: strip `Optional`/`| None` from
`field.annotation` before asking it for `model_fields`.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

import tomllib
import types
import typing
from pathlib import Path

from pydantic import BaseModel

from hachi.core.settings import ResolvedConfig

_EXAMPLE = Path(__file__).resolve().parents[1] / "settings.example.toml"

# User-chosen keys: the section name space is open, so don't check children.
_OPEN_DICT_SECTIONS = {"providers", "capabilities", "mcp_servers"}


def test_settings_example_toml_parses() -> None:
    """The file the README tells users to copy must be valid TOML.

    A malformed primary settings file is swallowed by _read_toml (logger.error,
    returns {}), so the user's entire config is silently discarded.
    """
    tomllib.loads(_EXAMPLE.read_text(encoding="utf-8"))  # raises TOMLDecodeError if broken


def _model_for(annotation: object) -> type[BaseModel] | None:
    """Unwrap `X | None` and return X when it is a pydantic model, else None."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        for arg in typing.get_args(annotation):
            found = _model_for(arg)
            if found is not None:
                return found
    return None


def _unknown_keys(parsed: dict, model: type[BaseModel], prefix: str = "") -> list[str]:
    bad: list[str] = []
    fields = model.model_fields
    for key, value in parsed.items():
        path = f"{prefix}{key}"
        if key not in fields:
            bad.append(path)
            continue
        if key in _OPEN_DICT_SECTIONS:
            continue
        nested = _model_for(fields[key].annotation)
        if nested is not None and isinstance(value, dict):
            bad.extend(_unknown_keys(value, nested, prefix=f"{path}."))
    return bad


def test_settings_example_toml_keys_are_known_config_fields() -> None:
    """Every key documented in the example must be a real ResolvedConfig field.

    Walks model_fields by hand: ResolvedConfig and all nested section models set
    extra="ignore", so model_validate() would accept anything and assert nothing.
    """
    parsed = tomllib.loads(_EXAMPLE.read_text(encoding="utf-8"))
    unknown = _unknown_keys(parsed, ResolvedConfig)
    assert not unknown, f"settings.example.toml documents keys Hachi ignores: {unknown}"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> (Test 1 must fail. Test 2 will *error* on the same `TOMLDecodeError` before the fix,
> which is fine — but re-run it after the TOML edit and make sure it is genuinely exercising
> the recursion, e.g. by temporarily inserting a bogus `[limits] bogus_key = 1` and
> confirming it goes red.)

### Why the second assertion is worth the effort

It permanently closes the drift class where a config section is documented (or shipped)
but is **not** a `ResolvedConfig` field, so `extra="ignore"` throws it away. That class is
live in the repo today: `EvalReportSettings` exists at `settings.py:246` and
`gateway/orchestrator.py:3676` reads `config.get("eval_reports", {})`, but `eval_reports` is
**not** a field on `ResolvedConfig` — see **[T-07-eval-reports-config-section.md](T-07-eval-reports-config-section.md)**.
Once T-07 documents `[eval_reports]` in the example file, this test is what proves the
field was actually added rather than silently dropped.

## 8. Acceptance criteria

- [ ] The two regression tests from §7 exist; `test_settings_example_toml_parses` failed
      before the fix with `TOMLDecodeError … line 122`.
- [ ] `python -c "import tomllib; tomllib.loads(open('settings.example.toml', encoding='utf-8').read())"`
      exits 0.
- [ ] `grep -c "= null" settings.example.toml` reports **0** live assignments (commented
      occurrences are fine and expected).
- [ ] No key was deleted from the example file — `git diff --stat settings.example.toml`
      shows only modified lines, no net removals of documented keys.
- [ ] No `| None` default was changed to `0` or `""`.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change any `extra="ignore"` to `extra="forbid"`.** It is the obvious "real fix"
  to reach for while writing the test, and it is a **runtime behaviour change** affecting
  every config load, every gateway config mutation, and every user with a slightly-stale
  settings file. Different task, different risk profile.
- **Do not add `[eval_reports]` to `settings.example.toml`.** You will notice it is missing
  while writing the recursion. Leave it — that is
  [T-07-eval-reports-config-section.md](T-07-eval-reports-config-section.md). Adding the
  section here without adding the `ResolvedConfig` field would make your own new test fail.
- Do not touch `write_global_config` or any config writer — that is
  [T-03-config-writers-file-layer-only.md](T-03-config-writers-file-layer-only.md).
- Do not reformat, re-order, or re-wrap the rest of `settings.example.toml`. Touch the 11
  lines and nothing else.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. (`tomllib` is stdlib on the pinned Python —
  no new dep needed.)
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Scoped run while iterating (Windows: `python -m pytest` per BB-1):

```bash
uv run pytest tests/test_config_loader.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**):

```markdown
### BB-N — `settings.example.toml` was invalid TOML; copying it silently discarded the user's whole config

- **Symptom:** a user copies `settings.example.toml` to `settings.toml` as the file's own
  header instructs, edits it, and *nothing* takes effect — no crash, no non-zero exit.
- **Root cause:** 11 lines used `key = null`. TOML has no null literal, so `tomllib` aborted
  at line 122. `_read_toml(primary=True)` (`core/config_loader.py:105`) catches
  `TOMLDecodeError`, logs `logger.error`, and returns `{}` — the process continues on
  built-in defaults with the entire file ignored. Nothing in CI had ever parsed the example.
- **Fix:** commented out the 11 assignments (matching the pre-existing line-47 precedent)
  rather than deleting them or substituting `0`/`""` — `None` means "no cap" and `0` is a
  live cap, so a value substitution would document behaviour Hachi does not have.
- **Avoid:** any file the docs tell a user to copy must be parsed by a test. And when
  asserting "documented keys are real keys", walk `model_fields` by hand — `ResolvedConfig`
  and all 20 nested section models set `extra="ignore"`, so `model_validate()` accepts
  anything and asserts nothing.
- **Locked by:** `tests/test_config_loader.py` — `test_settings_example_toml_parses`,
  `test_settings_example_toml_keys_are_known_config_fields`
```

## 12. Known traps

- **The vacuous test.** Re-read §7. `ResolvedConfig.model_validate(parsed)` will never
  raise. If your keys test passes on the first try after the TOML edit, prove it works by
  temporarily adding `bogus_key = 1` under `[limits]` and confirming it goes red.
- **Count is 11, not 10.** The review undercounts. `grep -n "null" settings.example.toml`
  returns many hits including type-annotation comments (`# type: str | null`); only the
  ones that are live assignments matter.
- **Line 47 is a decoy.** `# api_key_ref = null` is already commented. Do not "fix" it, and
  do not count it in the 11.
- **`routing` and `voice` are `| None` with no default factory.** Naive recursion via an
  instance gets `None` and skips them, silently under-testing. Resolve from the annotation.
- **No test may legitimately need amending for this task.** Nothing currently asserts
  anything about `settings.example.toml`. If an existing test goes red, it is a real
  regression from your edit — investigate, do not adjust the test.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
