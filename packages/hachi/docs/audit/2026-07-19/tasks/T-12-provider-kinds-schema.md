# T-12 · Reconcile `ProviderKind` with the providers the client factory actually implements

|  |  |
|---|---|
| **Source finding** | CF-1 (closing paragraph) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~2 hours |
| **Difficulty** | Medium (needs a policy decision — read §5 first) |
| **Files you will touch** | `src/hachi/core/settings.py`, `settings.example.toml`, `docs/guides/configuration.md`, `tests/test_provider_kinds.py` (new), `docs/bug-bank.md` — plus `src/hachi/core/config_validate.py` **only** if you pick option (c) |

---

## 1. Brief

`create_llm_client` implements two provider kinds — `gemini` and `chatgpt-web` — that the
config schema rejects. `ProviderKind` is a `Literal` that does not list them, so
`ResolvedConfig.model_validate` raises `ValidationError` on the documented config, and
`hachi doctor` independently reports `unknown provider kind`. The tracked docs at
`docs/guides/configuration.md:385` tell users both kinds are supported.

When you are done, the schema and the factory agree, `hachi doctor` stops contradicting
the documentation, and the divergence is prevented from recurring by a test.

## 2. Why this matters

A user reading `docs/guides/configuration.md` sets `kind = "gemini"` — a free-tier
provider, so this is a likely first-run path for someone without an Anthropic key — and
gets a pydantic `ValidationError` at config load. Meanwhile ~40 lines of working Gemini
client code sit in `llm.py`, unreachable through configuration.

This is a mirror image of the rest of CF-1: instead of a feature that reports success
while doing nothing, it is a feature that works but cannot be switched on. Same root
cause — **the schema is the wiring, and nobody checked that the two sides matched.**

`chatgpt-web` additionally carries a Terms-of-Service risk, which is why §5 is a decision
and not a one-liner.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The schema

`src/hachi/core/settings.py:8-10`:

```python
ProviderKind = Literal[
    "anthropic", "openai-compatible", "openrouter", "groq", "together", "deepseek", "ollama"
]
```

Seven kinds. Neither `gemini` nor `chatgpt-web` is present.

### 3.2 The factory implements both

`src/hachi/core/llm.py:896-911` — `gemini`:

```python
    if kind == "gemini":
        # Google Gemini — official OpenAI-compatible endpoint (free tier).
        # Falls back to GEMINI_API_KEY then GOOGLE_AI_API_KEY env vars.
        if not api_key:
            api_key = _resolve_api_key("GEMINI_API_KEY") or _resolve_api_key("GOOGLE_AI_API_KEY")
        resolved_base = str(base_url or _OPENAI_COMPAT_PRESETS["gemini"])
        # Default model if caller left the generic "claude-haiku-4-5" unchanged.
        if model == "claude-haiku-4-5":
            model = "gemini-2.0-flash"
        return OpenAICompatibleClient(...)
```

`src/hachi/core/llm.py:913-938` — `chatgpt-web`:

```python
    if kind == "chatgpt-web":
        # Unofficial ChatGPT web-session provider — opt-in only.
        # Requires HACHI_UNOFFICIAL=1 (see `pip install hachi-og[unofficial]`).
        if os.environ.get("HACHI_UNOFFICIAL") not in ("1", "true", "yes"):
            raise ValueError(
                "The chatgpt-web provider uses a reverse-engineered ChatGPT web API "
                "that may violate OpenAI's Terms of Service and risk account suspension.\n\n"
                ...
            )
        from hachi.core.unofficial_providers import ChatGPTWebClient
        ...
```

### 3.3 `extra="ignore"` does **not** rescue this

`ProviderSettings.kind` is a **declared field with a `Literal` type**. `extra="ignore"`
only drops *unknown keys*; an invalid *value* for a declared field is a hard
`ValidationError`. Rejection happens at
`src/hachi/core/config_loader.py:299`:

```python
    return ResolvedConfig.model_validate(merged)
```

Contrast [T-07](T-07-eval-reports-config-section.md), where an unregistered *section* is
dropped silently. Here the user gets a crash instead of silence. Both are schema/wiring
mismatches; the failure modes differ.

### 3.4 Rejection is doubled — `hachi doctor` too

`src/hachi/core/config_validate.py:12-16`:

```python
from hachi.core.settings import PermissionTier, ProviderKind

# Derived from the settings Literals so this stays in sync with the schema.
_VALID_KINDS = set(ProviderKind.__args__)
_VALID_TIERS = set(PermissionTier.__args__)
```

`:47-54`:

```python
    kind = getattr(provider, "kind", "")
    checks.append(
        _check(
            "provider_kind",
            kind in _VALID_KINDS,
            f"kind='{kind}'" if kind in _VALID_KINDS else f"unknown provider kind: {kind!r}",
        )
    )
```

Because `_VALID_KINDS` is **derived from the same `Literal`**, adding to the literal
auto-fixes `hachi doctor` — no edit needed in `config_validate.py` unless you pick
option (c) in §5.

### 3.5 The docs promise both

`docs/guides/configuration.md:385`:

> Supported provider kinds: `anthropic`, `openai-compatible`, `openrouter`, `groq`,
> `together`, `deepseek`, `ollama`, `gemini`, `chatgpt-web`.

The same file documents `GEMINI_API_KEY` (`:378`), `GOOGLE_AI_API_KEY` (`:379`),
`CHATGPT_SESSION_TOKEN` (`:380`), and `CHATGPT_ACCESS_TOKEN` (`:381`).
`settings.example.toml` mentions only `anthropic` (`:31`), `openai-compatible` (`:62`,
commented), and `ollama` (`:67`, commented).

### 3.6 Ordering subtlety — `gemini` also matches the generic preset branch

`src/hachi/core/llm.py:846-856`:

```python
_OPENAI_COMPAT_PRESETS: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "deepseek": "https://api.deepseek.com/v1",
    # Google Gemini — official OpenAI-compatible endpoint (free tier available).
    # Get a free key at https://aistudio.google.com/  (set GEMINI_API_KEY).
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}
```

`gemini` is a key here **and** has an explicit block at `:896`. The generic branch is
`if kind in _OPENAI_COMPAT_PRESETS:` at `:940`. The explicit block wins **only because it
appears first**. It does more than the generic branch — the `GEMINI_API_KEY` /
`GOOGLE_AI_API_KEY` fallback (`:899-900`) and the `gemini-2.0-flash` default model
(`:903-904`). **Flag this in your PR:** anyone who reorders `create_llm_client` silently
downgrades Gemini support. Consider a one-line comment at `:896` saying so; do not
restructure the function.

## 4. Reproduce the failure

Directly reproducible:

```bash
uv run python -c "
from hachi.core.settings import ResolvedConfig
ResolvedConfig.model_validate({'provider': {'kind': 'gemini', 'model': 'gemini-2.0-flash'}})
"
```

**You will see now:**

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ResolvedConfig
provider.kind
  Input should be 'anthropic', 'openai-compatible', 'openrouter', 'groq', 'together', 'deepseek' or 'ollama' [type=literal_error, input_value='gemini', input_type=str]
```

**You should see after the fix:** no output (validation succeeds).

The `hachi doctor` half:

```bash
uv run python -c "
from hachi.core.config_validate import _VALID_KINDS
print(sorted(_VALID_KINDS))
print('gemini accepted?', 'gemini' in _VALID_KINDS)
"
```

**You will see now:** `gemini accepted? False`
**You should see after the fix:** `True`, with no edit to `config_validate.py`.

## 5. What "fixed" looks like

> ## DECISION REQUIRED
>
> `gemini` is uncontroversial. **`chatgpt-web` is not**: it is a reverse-engineered
> client that `llm.py:916-926` says *"may violate OpenAI's Terms of Service and risk
> account suspension"*, and it is deliberately gated behind `HACHI_UNOFFICIAL=1`.
> Adding it to `ProviderKind` legitimises it as a first-class, documented,
> settings-configurable option. Choose deliberately.

### Options

| | Option | Trade-off |
|---|---|---|
| **(a)** | Add **both** to `ProviderKind` | Simplest; schema matches factory and docs exactly. But `chatgpt-web` becomes a documented `settings.toml` value — the `HACHI_UNOFFICIAL` runtime gate still fires at client construction, so the ToS warning is preserved, but the schema now implies endorsement. |
| **(b)** | Add **`gemini` only**; remove `chatgpt-web` from `ProviderKind`'s intended set and **delete it from `docs/guides/configuration.md:385`** | Honest for `gemini`, honest for the docs. But the `chatgpt-web` factory branch stays permanently unreachable via config — you have converted one lie ("supported") into another (dead code with no route in). Requires also deleting the `CHATGPT_*` env rows at `:380-381` or they document a path to nowhere. |
| **(c)** | Add **both**, and keep `chatgpt-web` **env-gated at validation** — accepted by the `Literal`, but `config_validate.validate_config` reports it as not-ok unless `HACHI_UNOFFICIAL` is set | Most precise; `hachi doctor` tells the truth about the risk. Costs a special case in `config_validate.py` and a second place where the flag is read. |

### Recommendation — **(a)**, plus a docs change

Add both to the literal:

```python
ProviderKind = Literal[
    "anthropic",
    "openai-compatible",
    "openrouter",
    "groq",
    "together",
    "deepseek",
    "ollama",
    "gemini",
    # Unofficial, opt-in: create_llm_client() raises unless HACHI_UNOFFICIAL=1 is set.
    # Listed here so the documented config validates; the ToS gate lives at the
    # client-construction boundary (core/llm.py), not in the schema.
    "chatgpt-web",
]
```

Rationale:

- **The runtime gate already does the job, and does it better than the schema could.**
  `llm.py:916-926` raises a long, explicit ToS warning at construction. A user who sets
  `kind = "chatgpt-web"` without the flag still cannot use it — they get a clear
  actionable error instead of a pydantic `literal_error` that explains nothing.
- **A schema is a description, not an endorsement.** Its job is to accept configurations
  the program can act on. Refusing to *parse* a value the program implements creates two
  sources of truth, which is the CF-1 root cause.
- **(b) trades one dishonesty for another** and orphans working code.
- **(c) is defensible** — pick it instead if the product owner wants `hachi doctor` to
  actively flag the risk. It is a ~10-line addition to `config_validate.py`; the extra
  cost is that `HACHI_UNOFFICIAL` is then read in two places, which must be kept in sync.

Then update `settings.example.toml` with a commented `gemini` block next to the existing
`ollama` one at `:67` (free tier makes it the most likely non-Anthropic first choice), and
add a ToS note beside the `chatgpt-web` line in `docs/guides/configuration.md:385` so the
docs carry the same warning the code does.

### Make the divergence loud (required)

The mechanism that produced this bug is invisible at runtime, so the "loud" half is a
**test that fails when the two lists diverge again** — §7's
`test_provider_kind_literal_covers_every_implemented_kind`. It is the permanent guard,
and it is the deliverable that matters most in this task.

## 6. Steps

1. Get the decision from §5 recorded in `docs/DECISIONS.md`.
2. Write the regression tests from §7 first. Run them. Watch them fail.
3. Extend `ProviderKind` (`src/hachi/core/settings.py:8-10`) per the chosen option.
4. Add the commented `[provider] kind = "gemini"` block to `settings.example.toml`.
5. Add the ToS note next to `chatgpt-web` in `docs/guides/configuration.md:385`.
6. Add a one-line comment at `llm.py:896` recording the ordering dependency (§3.6).
7. *(Option (c) only)* add the `HACHI_UNOFFICIAL` check to `config_validate.py`.
8. Run the tests. Watch them pass.
9. Run `uv run python scripts/preflight.py`. Report real counts.
10. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_provider_kinds.py` (new)
- **Test names:** `test_documented_provider_kinds_validate`,
  `test_provider_kind_literal_covers_every_implemented_kind`
- **It must assert:** that a real `ResolvedConfig.model_validate` accepts each documented
  kind, and — the durable one — that **every `kind == "..."` branch in `create_llm_client`
  has a corresponding `ProviderKind` member**, derived by parsing the source rather than
  by a hardcoded list.
- **It must FAIL before your fix** with:
  `pydantic_core._pydantic_core.ValidationError: ... Input should be 'anthropic', ... [type=literal_error, input_value='gemini']`
  and `AssertionError: create_llm_client implements kinds absent from ProviderKind: ['chatgpt-web', 'gemini']`.

```python
# sketch — adapt to the repo's existing fixtures
import ast
import inspect

import pytest

from hachi.core.settings import ProviderKind, ResolvedConfig


@pytest.mark.parametrize(
    "kind",
    ["anthropic", "openai-compatible", "openrouter", "groq", "together",
     "deepseek", "ollama", "gemini", "chatgpt-web"],   # docs/guides/configuration.md:385
)
def test_documented_provider_kinds_validate(kind: str) -> None:
    cfg = ResolvedConfig.model_validate({"provider": {"kind": kind}})
    assert cfg.provider.kind == kind


def test_provider_kind_literal_covers_every_implemented_kind() -> None:
    """The schema must accept every kind create_llm_client can actually build.

    Parses `if kind == "...":` comparisons out of create_llm_client so this stays true
    when someone adds a provider branch without touching settings.py.
    """
    import hachi.core.llm as llm

    tree = ast.parse(inspect.getsource(llm.create_llm_client))
    implemented = {
        node.comparators[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "kind"
        and isinstance(node.ops[0], ast.Eq)
        and isinstance(node.comparators[0], ast.Constant)
        and isinstance(node.comparators[0].value, str)
    }
    declared = set(ProviderKind.__args__)
    missing = sorted(implemented - declared)
    assert not missing, f"create_llm_client implements kinds absent from ProviderKind: {missing}"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

Print `implemented` once while developing and eyeball it — the AST walk should find
`anthropic`, `ollama`, `gemini`, `chatgpt-web`. It will **not** find the
`_OPENAI_COMPAT_PRESETS` members (they use `in`, not `==`), which is fine: those are
already in the literal. If you prefer, extend the walk to cover the `in` branch as well
and union the preset dict's keys.

**Do not assert the reverse direction** (`declared - implemented`): `openai-compatible`
is legitimately handled by the fall-through, so a strict two-way equality would fail for
the wrong reason. Read the tail of `create_llm_client` before deciding.

## 8. Acceptance criteria

- [ ] The decision from §5 is recorded in `docs/DECISIONS.md`.
- [ ] The regression tests from §7 exist, and failed before the fix.
- [ ] `ResolvedConfig.model_validate({"provider": {"kind": "gemini"}})` succeeds.
- [ ] `'gemini' in hachi.core.config_validate._VALID_KINDS` is `True` **without** editing
      `config_validate.py` (it derives from the literal).
- [ ] `settings.example.toml` documents the `gemini` block and still parses
      (`tomllib.loads`) — cross-check with [T-02](T-02-settings-example-toml.md), the CF-3
      example-config task.
- [ ] `docs/guides/configuration.md:385` carries a ToS note beside `chatgpt-web`.
- [ ] The ordering dependency at `llm.py:896` is commented.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not remove `chatgpt-web` from `core/llm.py`.** `docs/strategy/08-roadmap.md:41` and
  `docs/strategy/01-architecture-review.md:260` track "move `chatgpt-web` to an opt-in
  extra" as a separate, breaking, changelog-worthy item. That is not this task.
- **Do not weaken the `HACHI_UNOFFICIAL` gate.** It stays exactly as written at
  `llm.py:916-926`, whichever option you pick. Adding the kind to the schema must not
  make the provider usable without the flag — assert that in a test if you touch it.
- **Do not restructure `create_llm_client`.** The `gemini` block wins by ordering (§3.6);
  reordering or "simplifying" the branch chain silently changes behaviour. Comment it,
  do not refactor it.
- **Do not add a new provider.** You are reconciling two existing lists.
- **Do not audit the rest of the config schema for divergence.** Tempting, and wrong
  scope — the T-02 example-config test and this task's AST test are the systematic
  answers.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. (`ChatGPTWebClient` lives behind the
  `unofficial` extra and is imported lazily at `llm.py:927` — keep it that way.)

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
### BB-N — Two implemented provider kinds were rejected by the config schema

- **Symptom:** setting `[provider] kind = "gemini"` (documented at
  `docs/guides/configuration.md:385`, and the natural free-tier choice for a user with
  no Anthropic key) crashed config loading with a pydantic `literal_error`. `hachi
  doctor` separately reported `unknown provider kind: 'gemini'`. Same for
  `chatgpt-web`.
- **Root cause:** `core/llm.py create_llm_client` implements `kind == "gemini"` and
  `kind == "chatgpt-web"`, but `ProviderKind` in `core/settings.py` is a `Literal` that
  listed neither, so `ResolvedConfig.model_validate` rejected the value at
  `config_loader.load_effective_config`. `ConfigDict(extra="ignore")` does not help —
  this is an invalid *value* for a declared field, not an unknown key. The rejection was
  doubled because `core/config_validate._VALID_KINDS` derives from the same literal.
- **Fix:** added both kinds to `ProviderKind` (the `HACHI_UNOFFICIAL=1` ToS gate for
  `chatgpt-web` stays at the client-construction boundary in `core/llm.py`, which is a
  better place to enforce it than a parse error), documented `gemini` in
  `settings.example.toml`, and added a ToS note to the configuration guide. Locked with
  an AST-derived test that fails whenever `create_llm_client` grows a `kind == "..."`
  branch with no matching `ProviderKind` member.
- **Avoid:** a provider is not supported until the schema accepts it. When you add a
  branch to a factory keyed on a config value, extend the `Literal` in the same commit —
  and prefer a test that derives the expected set from the implementation over one that
  hardcodes it, or the two lists drift again.
- **Locked by:** `tests/test_provider_kinds.py` —
  `test_provider_kind_literal_covers_every_implemented_kind`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **Do not instantiate a `chatgpt-web` client in a test.** It imports
  `hachi.core.unofficial_providers` (`llm.py:927`), which lives behind the `unofficial`
  extra and may not be installed. Test the **schema**, not the client. If you must touch
  the factory, assert that it *raises* without `HACHI_UNOFFICIAL`.
- `HACHI_UNOFFICIAL` is read from the process environment. `tests/conftest.py:93-114`
  snapshots and restores `os.environ` per test — use `monkeypatch.setenv`, never a bare
  assignment.
- `ProviderKind.__args__` is a `typing` implementation detail. It is already relied on by
  `config_validate.py:15`, so using it in a test matches existing practice — but note
  `mypy --strict` may need a `# type: ignore` or a `typing.get_args()` call instead
  (`get_args(ProviderKind)` is the portable form; prefer it in new code).
- [T-02](T-02-settings-example-toml.md) (the CF-3 example-config task) adds a test that
  `settings.example.toml` parses as valid TOML and that its keys are a subset of
  `ResolvedConfig.model_fields`. Your commented `gemini` block must not break it —
  commented lines are inert to `tomllib`, so keep the block commented as sketched.
