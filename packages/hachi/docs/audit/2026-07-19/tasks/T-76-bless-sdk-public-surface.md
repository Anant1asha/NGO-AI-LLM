# T-76 · Bless `hachi.sdk` as a supported public surface

|  |  |
|---|---|
| **Source finding** | Missed Opportunity #4 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P3 |
| **Wave** | 2 (fast-follow, pre-v1.1) — **optional leverage, not gate-blocking. See §2.** |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~3 days |
| **Difficulty** | Medium — almost no new code; the work is writing a stability policy you are willing to honour, and a two-directional contract test. The risk is scope creep into the OpenAPI question (§9) |
| **Files you will touch** | `src/hachi/sdk/__init__.py`, `src/hachi/sdk/py.typed` *(new)*, `pyproject.toml`, `tests/test_p3_06_sdk_v0.py`, `docs/guides/sdk.md` *(new)*, `docs/architecture/adr/00NN-sdk-public-surface.md` *(new)*, `docs/architecture/adr/README.md`, `README.md` |

---

## 1. Brief

`src/hachi/sdk/` is a 113-line re-export facade that *claims* to be a semver'd public API for
third-party pack authors. Verification found the claim is currently unbacked: there is no `py.typed`
marker anywhere in the repo, the extra its own docstring tells authors to install does not exist, the
version constant has no mechanical link to anything, no document outside two planning files mentions
it, and its contract test only checks one direction. When you are done, the facade's promises are all
true and mechanically enforced — or the promises have been narrowed to what you are actually willing
to support.

**This is not a bug fix.** The SDK works: every symbol imports, and 11 tests pass. The gap is between
what it *promises* and what is *enforced*. §4 shows you that gap; there is no failure to reproduce.

## 2. Why this matters

**Read this first: this task is optional leverage and it is not gate-blocking.** It comes from the
review's *Missed Opportunities*, not the release gate, and it is the lowest-priority of the three
(P3). **Do not start it while Wave 1 is open.** Nothing in Wave 1 depends on it, no user is blocked by
it, and a public API is worth roughly nothing until the product behind it is trustworthy — which is
exactly what Wave 1's 41 tasks are for.

The reason it is worth three days *later* is that the expensive part is already built. The review:
*"`sdk/` is a ready-made public API surface … a semver'd facade already exists and is honest about
internals; blessing it gives a supported programmatic story almost for free."* The facade, its 12
symbols, its version function, and its contract test all exist. What is missing is the cheap,
unglamorous half — the typing marker, the packaging extra, the docs, and a test that fails when
someone widens the surface by accident.

There is a second, sharper reason, and it is the one that should decide priority *within* Wave 2. The
docstring at `src/hachi/sdk/__init__.py:1-18` makes four concrete promises to third-party authors.
**Three of them are currently false** (§3.2). A public surface that documents a `pip install`
incantation that does not work is worse than no public surface, because it converts "we have not
shipped an SDK yet" into "their SDK is broken." Given a product whose central problem in this audit is
features that report success while inert (CF-1), shipping a *façade of a façade* is the same failure
mode wearing a different hat.

**"Blessing" must mean something checkable.** If this task ends with a nicer docstring, it has failed.
§8 defines blessing as five mechanically-verifiable properties. If you cannot tick all five, narrow
the promise instead of widening the prose.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 What the facade actually is

`src/hachi/sdk/` contains **exactly one source file**: `__init__.py`, **113 lines**. There are no other
modules. It contains no original implementation — every symbol is a re-export.

`src/hachi/sdk/__init__.py:1-18` — the full docstring, the source of every promise in this task:

```python
"""hachi.sdk — stable public surface for third-party pack authors.

This namespace re-exports the interfaces that external code may safely import
and depend on.  Everything else inside ``hachi`` is internal and subject
to change without notice.

Independently semver'd: the SDK minor version increments independently of the
app release so pack authors can pin ``hachi-og[sdk]`` without pulling in new
app features.

Stable surface (v0):
    * Tool authoring  — ToolRegistry, ToolSpec
    * Provider seam   — BaseLLMClient
    * Pack authoring  — OgPackManifest, PackScope, ScheduleBudget, parse_pack_toml,
                        render_consent_sheet
    * Runtime events  — all SESSION_*/TOOL_*/MEMORY_*/MCP_*/CHANNEL_* constants
    * Introspection   — sdk_version(), is_compatible()
"""
```

**`__all__` — `src/hachi/sdk/__init__.py:22-40`, 12 symbols:**

```python
__all__ = [
    # Tool authoring
    "ToolRegistry",
    "ToolSpec",
    # Provider seam
    "BaseLLMClient",
    # Pack authoring
    "OgPackManifest",
    "PackScope",
    "ScheduleBudget",
    "parse_pack_toml",
    "render_consent_sheet",
    # Runtime events
    "events",
    # Introspection
    "sdk_version",
    "is_compatible",
    "SDK_VERSION",
]
```

**Version — `src/hachi/sdk/__init__.py:81-85`:**

```python
SDK_VERSION: str = "0.1.0"
"""Current SDK semver string.  Updated on each breaking-or-additive change
to the stable surface, independently of the app release."""

_MIN_APP_VERSION: str = "0.1.0"
```

Every re-export is at `:49-75`. Eight come from `hachi.core`; **one comes from `hachi.gateway`** —
`src/hachi/sdk/__init__.py:75`:

```python
from hachi.gateway.tool_registration import ToolSpec as ToolSpec
```

So `import hachi.sdk` transitively imports the FastAPI gateway package. Worth knowing before you
promise a lightweight author-facing dependency.

### 3.2 Three of the docstring's promises are false

Each verified independently:

| Promise | Location | Verdict |
|---|---|---|
| "stable public surface" | `:1` | **Unenforced** — the contract test is one-directional (§3.4); no import-linter contract constrains `sdk/` (§3.5) |
| "pack authors can pin `hachi-og[sdk]`" | `:8` | **FALSE — there is no `sdk` extra.** `pyproject.toml`'s `[project.optional-dependencies]` (`:55`) defines exactly: `dev`, `memory`, `local-models`, `search`, `browser`, `files`, `tracing`, `observability`, `presentations`, `unofficial`, `security`. `pip install hachi-og[sdk]` warns about an unknown extra and installs nothing |
| "Independently semver'd" | `:7` | **Unenforced.** `SDK_VERSION` is a bare literal with no reference to package metadata — no `importlib.metadata.version()`, no import. It and `pyproject.toml:8` (`version = "0.1.0"`) are two independent strings that currently coincide by accident. No test asserts a bump when the surface changes |

Two more defects in the same file:

- **`_MIN_APP_VERSION` (`:85`) is dead.** Assigned once; grep across `src/` and `tests/` finds no read.
- **`is_compatible`'s docstring contradicts its implementation.** `:96` promises *"a simple major-match
  + minor-GTE rule (no patch sensitivity)"*. The implementation at `:106-113` is a plain 3-tuple `>=`:

  ```python
      def _parse(v: str) -> tuple[int, int, int]:
          parts = v.split(".")
          return (int(parts[0]), int(parts[1]), int(parts[2] if len(parts) > 2 else 0))

      return _parse(SDK_VERSION) >= _parse(required_sdk_version)
  ```

  It *does* compare patch, and it does **not** require a major match — so a hypothetical
  `SDK_VERSION = "5.0.0"` would report compatibility with a pack requiring `"0.1.0"`, which is exactly
  the case a major-match rule exists to reject. `_parse` also raises `ValueError`/`IndexError` on
  malformed input rather than returning `False`. **This is the function third-party packs will call to
  decide whether they can run.**

### 3.3 There is no `py.typed` anywhere in the repository

Verified: `find src -name "py.typed"` returns nothing. Not under `src/hachi/`, not under
`src/hachi/sdk/`.

`pyproject.toml:155-156` is the only packaging directive, and it is a whole-tree include:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/hachi"]
```

Consequence: `hachi.sdk` is fully annotated (`from __future__ import annotations`, typed signatures
throughout) but **PEP 561-invisible**. A pack author running mypy or pyright against it gets
`Skipping analyzing "hachi.sdk": module is installed, but missing library stubs or py.typed marker`.
The repo's own `[tool.mypy]` config (`pyproject.toml:143`) applies in-tree only and does nothing for
consumers. **This is the single highest-value line in the whole task** — one empty file converts an
untyped dependency into a typed one for every downstream user.

### 3.4 The contract test is one-directional — and its own docstring says otherwise

`tests/test_p3_06_sdk_v0.py` — 143 lines, **11 tests**. Docstring at `:1-9`:

```python
"""P3-06: SDK v0 contract tests.

Validates that:
1. All documented symbols are importable from ``hachi.sdk``.
2. The SDK version is a valid semver string.
3. ``is_compatible()`` correctly compares versions.
4. ``events`` module exposes the expected event-name constants.
5. The stable surface does NOT export any private/internal-only symbols.
"""
```

**Claim 5 is not implemented by any test in the file.** Both surface tests iterate `_STABLE_SYMBOLS`
and check membership *in* `sdk` — never the reverse. `tests/test_p3_06_sdk_v0.py:34-46`:

```python
def test_sdk_exports_all_stable_symbols() -> None:
    import hachi.sdk as sdk

    missing = [sym for sym in _STABLE_SYMBOLS if not hasattr(sdk, sym)]
    assert not missing, f"Missing from hachi.sdk: {missing}"


def test_sdk_all_list_matches_stable_symbols() -> None:
    import hachi.sdk as sdk

    for sym in _STABLE_SYMBOLS:
        assert sym in sdk.__all__, f"{sym!r} not in hachi.sdk.__all__"
```

There is no `assert set(sdk.__all__) == set(_STABLE_SYMBOLS)`. **Adding a symbol to `__all__` —
including accidentally re-exporting an internal — passes the suite today.** For a surface whose entire
value proposition is "this and only this is stable", that is the one assertion that had to exist.

The version test (`:56-60`) asserts *shape only*:

```python
def test_sdk_version_is_valid_semver() -> None:
    from hachi.sdk import SDK_VERSION, sdk_version

    assert _SEMVER_RE.match(SDK_VERSION), f"SDK_VERSION {SDK_VERSION!r} is not semver"
    assert sdk_version() == SDK_VERSION
```

Nothing ties `SDK_VERSION` to `pyproject.toml`, and nothing detects a surface change without a bump.

### 3.5 No import-linter contract constrains `sdk/` or `client/`

`pyproject.toml:158-177` declares a three-layer model **in a comment**:

```toml
#   edges    : cli, tui, channels        (entry adapters / transports)
#   service  : gateway, client, sdk      (the REST surface + its consumers)
#   engine   : core, og_engine, tools, jobs, integrations   (the foundation)
```

`pyproject.toml:166` is the only place in the repo that assigns `sdk` and `client` to a layer, and it
is not enforced. There are exactly **three** contracts (at `:179`, `:195`, `:213`), all
`type = "forbidden"`, and **all three guard the engine layer**. `hachi.sdk` and `hachi.client` appear
only as `forbidden_modules` in the first (`:185-186`) — never as `source_modules`.

Concretely: **`hachi.sdk` importing `hachi.cli` or `hachi.tui` would pass `lint-imports` today**, even
though the stated layering forbids it. Nothing mechanically stops the "stable surface" from growing a
dependency on the CLI.

### 3.6 Documentation: two planning files, and nothing else

Repo-wide, `hachi.sdk` appears outside its own source and test in exactly four places:

| `path:line` | What it is |
|---|---|
| `pyproject.toml:186` | a `forbidden_modules` entry (§3.5) |
| `docs/strategy/07-future-and-growth.md:134` | *"Proposal: a `hachi.sdk` namespace re-exporting the stable surface…"* — a **proposal**, in a strategy doc |
| `docs/strategy/07-future-and-growth.md:167` | a roadmap effort estimate |
| `docs/strategy/09-execution-plan.md:466` | roadmap row `P3-06 ✅`, marked complete |

Verified absent:

- **`README.md`** (32,899 bytes) — zero matches for `hachi.sdk`, `SDK`, `public API`, or `programmatic`.
- **`ARCHITECTURE.md`** — zero matches.
- **`docs/DECISIONS.md`** — zero matches for `hachi.sdk`, `SDK v0`, or `P3-06`. **No ADR or decision
  record exists for the SDK at all.**
- **`docs/architecture/adr/`** — no ADR mentions it.

So: a "public surface for third-party pack authors" that no author-facing document mentions.

> **Related unshipped deliverable, NOT in scope:** `docs/strategy/09-execution-plan.md:466` marks
> P3-06 complete *including* `doctor --plugin`. Grep for `--plugin` / `plugin_pkg` / `def plugin`
> across `src/hachi/` finds **nothing** — it was never built. That is a CF-1-shaped roadmap-honesty
> defect, not part of this task. Note it in §11 and leave it.

### 3.7 `client/` is a different thing, deliberately — do not merge them

The review verified this distinction and it is worth restating because the two packages look like
duplication and are not.

| | `sdk/` | `client/` |
|---|---|---|
| Size | 113 lines, 1 file | 2,488 lines, 5 files (`__init__` 140, `gaps` 521, `gateway` 591, `models` 988, `sse` 248) |
| What it is | in-process re-export facade for **pack authors** | synchronous **REST + SSE consumer** for the Textual TUI |
| Talks to | `hachi.core` / `hachi.gateway` by import | the gateway over HTTP (`httpx` at `client/gateway.py:27`, `client/sse.py:35`) |
| Imports from `hachi.*` | 9 (§3.1) | **zero** — only relative imports, stdlib, and `httpx` |
| Versioned | `SDK_VERSION` | **no version constant at all** |
| Stability claim | yes (`:1`) | none — `client/__init__.py:4` says "Public surface … used by the Textual TUI" |
| Tests | 11 | 164 across 7 files |

**This separation is intentional, not duplication. Do not propose merging them, and do not
"consolidate" `client/` into `sdk/`.** One is an import-time facade; the other is a network client.
They share no code and answer different questions.

Two incidental findings about `client/`, recorded so you do not rediscover them: `client/models.py:353`
defines `BlockedItem`, which is **not** in `client/__init__.py`'s `__all__`; and **no consumer in
`src/` imports the `hachi.client` package surface at all** — all 14 call sites in `tui/cockpit/`
import submodules directly (`hachi.client.models`, `hachi.client.gateway`), so the carefully-declared
61-entry `__all__` at `client/__init__.py:75-140` has zero users. Neither is in scope here.

### 3.8 The `client/` → OpenAPI question is a separate, larger decision — flagged, not scoped

The review's second half — *"routing the Python `client/` types through generated OpenAPI models"* —
is **out of scope for this task**, and this section exists so you can see why rather than wonder.

`src/hachi/client/models.py:1-8`:

```python
"""
Hachi Cockpit — display models.

Frozen dataclasses mirroring ``frontend/src/lib/data/types.ts``.
Every class exposes a ``from_api(d: dict[str, Any]) -> Self`` classmethod that
adapts raw gateway JSON to the model, replicating the TypeScript
domain-adapter logic (defaults / fallbacks / normalisation included).
"""
```

Line `:4` is the problem: 988 lines and 30 dataclasses mirror **`types.ts`**, not the gateway. That
makes a four-layer hand-maintained chain — gateway route → OpenAPI spec (generated, unconsumed) →
`types.ts` → `client/models.py` — with nothing enforcing any link. Nothing regenerates it, and no
schema test compares them.

Fixing that means deciding whether generated OpenAPI models become the source of truth for the Python
client, which is [T-38](T-38-openapi-pilot-og-domain.md)'s territory (CF-5) and is a multi-day
decision with its own migration. **Cross-link it, do not do it here.** A three-day task that quietly
becomes a contract-generation project is how Wave 2 stops being schedulable.

## 4. See the opportunity

**There is no failure to reproduce. This is an opportunity, not a defect** — the SDK imports fine and
its 11 tests pass. Do not manufacture a repro. What follows is the evidence that the promises are
unbacked. Run it; the output is your ADR's Context section.

### 4.1 The promises, checked one at a time

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
cd D:/OpenGigantic/hachi

# Promise: "pack authors can pin hachi-og[sdk]"  (sdk/__init__.py:8)
grep -n "^\[project.optional-dependencies\]" -A 60 pyproject.toml | grep -E "^\s*[0-9]+[-:][a-z-]+ = \["

# Promise: a typed, PEP 561 surface
find src -name "py.typed" ; echo "exit=$?  (no output = no marker = untyped for consumers)"

# Promise: "Independently semver'd"
grep -rn "SDK_VERSION" --include=*.py src/ tests/

# Promise: "stable public surface"  — who documents it?
grep -rn "hachi\.sdk" README.md ARCHITECTURE.md docs/DECISIONS.md docs/architecture/adr/ 2>/dev/null
echo "exit=$?  (1 = documented nowhere a consumer would look)"

# Dead constant
grep -rn "_MIN_APP_VERSION" --include=*.py src/ tests/
```

**You will see now:** the extras list contains `dev`, `memory`, `local-models`, `search`, `browser`,
`files`, `tracing`, `observability`, `presentations`, `unofficial`, `security` — and **no `sdk`**; no
`py.typed` file; `SDK_VERSION` referenced only inside `sdk/__init__.py` and its own test, never
compared to package metadata; **zero** hits in README / ARCHITECTURE / DECISIONS / ADRs; and
`_MIN_APP_VERSION` appearing exactly once, at its own assignment.

**You should see after the change:** an `sdk` extra that resolves, a `py.typed` marker, a version
mechanically checked against the surface, and at least one author-facing document.

### 4.2 Prove the contract test does not catch a widened surface

This is the strongest single demonstration, and it takes 30 seconds. **Make a temporary edit you will
revert:** add one internal symbol to `__all__` in `src/hachi/sdk/__init__.py:22-40` — e.g. append
`"_MIN_APP_VERSION"` — then:

```bash
uv run pytest -q tests/test_p3_06_sdk_v0.py
```

**You will see now:** 11 passed. The suite does not notice that a private, dead, internal constant is
now part of the advertised stable surface — despite the file's own docstring claiming at `:8` that it
checks exactly this. **Revert the edit immediately**; it exists only to show the hole, and §7 turns it
into a permanent test.

## 5. What "fixed" looks like

Every promise in the `sdk/__init__.py` docstring is either **mechanically enforced** or **removed**.
Nothing is left as prose.

### 5.1 The five things "blessing" concretely means

Decided here so you do not have to decide:

1. **PEP 561 typed.** An empty `src/hachi/sdk/py.typed` exists and ships in the wheel.
2. **Installable as advertised.** `pyproject.toml` gains an `sdk` extra so `pip install hachi-og[sdk]`
   resolves — or, if there is nothing extra to install, the docstring's `hachi-og[sdk]` claim is
   **deleted** and replaced with the honest `pip install hachi-og`. **Either is acceptable. What is
   not acceptable is leaving the false instruction in place.** Prefer the extra only if it actually
   carries something; an empty extra that exists to make a docstring true is theatre.
3. **The surface is pinned in both directions.** A test asserts `set(sdk.__all__) == set(_STABLE_SYMBOLS)`,
   so adding *or* removing a symbol fails the gate. This is the load-bearing change.
4. **The version means something.** `SDK_VERSION` is asserted against a recorded fingerprint of the
   surface, so widening `__all__` without bumping the version fails the gate.
5. **It is documented where a consumer would look.** `docs/guides/sdk.md` exists, with a working
   install line, the 12 symbols, the stability policy, and a runnable example. `README.md` links it.

### 5.2 The stability policy — write it down, then honour it

Put this in `docs/guides/sdk.md` and reference it from the ADR:

> **`hachi.sdk` stability policy (v0)**
>
> - Symbols in `hachi.sdk.__all__` are the supported surface. Everything else in `hachi` is internal
>   and may change in any release without notice.
> - **v0 caveat, stated plainly:** while `SDK_VERSION` is `0.x`, the surface may still change in a
>   minor release. Removals will be announced one minor version ahead. This is a real caveat, not
>   boilerplate — do not promise 1.0 guarantees at 0.1.0.
> - Adding a symbol bumps the **minor** version. Removing or changing one bumps the **major**.
> - `is_compatible(required)` is the supported runtime check for pack authors.
> - The surface is typed; `py.typed` ships.

### 5.3 Fix `is_compatible` — decide, do not leave it ambiguous

§3.2 shows the docstring and implementation disagree. **Make the implementation match the docstring**
(major-match + minor-GTE), because that is the semantically correct rule for a compatibility check and
it is what a pack author reading the docs will assume:

```python
def is_compatible(required_sdk_version: str) -> bool:
    """Return True if the running SDK satisfies *required_sdk_version*.

    Major versions must match exactly; the running minor must be >= the required
    minor. Patch is not considered. Returns False for a malformed argument.
    """
    def _parse(v: str) -> tuple[int, int] | None:
        parts = v.split(".")
        try:
            return (int(parts[0]), int(parts[1]))
        except (IndexError, ValueError):
            return None

    want = _parse(required_sdk_version)
    have = _parse(SDK_VERSION)
    if want is None or have is None:
        return False
    return have[0] == want[0] and have[1] >= want[1]
```

Note this **changes behaviour**: under a future `SDK_VERSION = "1.0.0"`, `is_compatible("0.1.0")` goes
from `True` to `False`. That is the correction, not a regression — but three existing tests
(`test_is_compatible_with_same_version` `:68`, `_older_version` `:74`, `_future_version` `:80`) assert
the current rule. Check whether they still pass at `SDK_VERSION == "0.1.0"` (they should — all three
share major `0`), and if any needs amending, say so explicitly in the commit message per
[CLAUDE.md](../../../../CLAUDE.md) Rule 2. **Do not delete a test to make this land.**

Delete `_MIN_APP_VERSION` (`:85`) in the same change — it is dead (§3.2), and leaving a dead version
constant in a file about version discipline is its own small joke.

### 5.4 What NOT to change

**The 12 symbols stay as they are.** Do not add to the surface, do not remove from it, do not
"improve" the selection. Blessing an existing surface and redesigning it are different tasks with
different risk; this is the first. If you believe a symbol is missing, file it — the whole point of
item 3 in §5.1 is that changing the surface should be deliberate and visible from now on.

The `hachi.gateway` import at `:75` also stays (§3.1). Moving `ToolSpec` into `core` to decouple the
SDK from the gateway is a real improvement and a real refactor with its own blast radius. Note it;
leave it.

## 6. Steps

1. Write the two failing tests from §7 first. Watch them fail — §4.2 shows you exactly how the current
   suite lets a widened surface through.
2. Create `src/hachi/sdk/py.typed` (empty file). Confirm `[tool.hatch.build.targets.wheel]`
   (`pyproject.toml:155-156`) already includes it — it is a whole-tree include, so it should, but
   verify with a built wheel (§10) rather than assuming.
3. Decide the extra (§5.1 item 2). Either add `sdk = [...]` to `[project.optional-dependencies]`
   (`pyproject.toml:55`) or correct the docstring at `src/hachi/sdk/__init__.py:8`. **Do one.**
4. Add the bidirectional `__all__` assertion to `tests/test_p3_06_sdk_v0.py` (§7a).
5. Add the surface-fingerprint / version test (§7b).
6. Fix `is_compatible` per §5.3 and delete `_MIN_APP_VERSION`.
7. Write `docs/guides/sdk.md`: install line, the 12 symbols with one-line descriptions, the §5.2
   stability policy, and a runnable example that you have actually run.
8. Link it from `README.md` and from `docs/README.md`'s index.
9. Write the ADR (§11) recording the surface, the policy, and the `sdk`-vs-`client` distinction from
   §3.7 — so the next reader does not propose merging them.
10. Run the gate (§10).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

**The right instrument here is a public-API contract test** — not a behavioural regression test, since
no behaviour is wrong. Its job is to fail when the *shape* of the public surface changes without a
deliberate decision. Concretely: it compares the live `__all__` against a checked-in expected set, in
both directions, and ties that set to `SDK_VERSION`. Both tests below assert real module state, not a
mock.

### 7a. The surface lock (the primary test)

- **File:** `tests/test_p3_06_sdk_v0.py` (existing)
- **Test name:** `test_sdk_all_contains_nothing_beyond_stable_symbols`
- **It must assert:** `set(sdk.__all__) == set(_STABLE_SYMBOLS)` — equality, not one-way membership.
  This is the file's own docstring claim 5 (`:8`), which is currently unimplemented (§3.4).
- **It must FAIL before your fix** — but only if you first reproduce §4.2's temporary edit, because
  today's `__all__` happens to match. **This is important and easy to get wrong:** the test as written
  passes against unmodified `main`, which under Rule 2 means it proves nothing yet. Do this instead:
  1. Add `"_MIN_APP_VERSION"` to `__all__` (the §4.2 edit).
  2. Confirm the **existing** 11 tests still pass — this is the hole.
  3. Add your new test; confirm it **fails** with
     `AssertionError: hachi.sdk.__all__ has extra symbols: {'_MIN_APP_VERSION'}`.
  4. Revert the temporary edit; confirm the new test passes.
  5. **Say all four steps happened in the commit message.** A reviewer cannot otherwise distinguish
     this from a test that never failed.

```python
# sketch — adapt to the file's existing style
def test_sdk_all_contains_nothing_beyond_stable_symbols() -> None:
    """T-76: the stable surface is pinned in BOTH directions.

    The pre-existing tests only checked that every stable symbol is present.
    Nothing stopped an internal symbol being added to __all__ — which is the
    one thing a 'stable public surface' must not allow.
    """
    import hachi.sdk as sdk

    extra = set(sdk.__all__) - set(_STABLE_SYMBOLS)
    assert not extra, f"hachi.sdk.__all__ has extra symbols: {extra}"

    missing = set(_STABLE_SYMBOLS) - set(sdk.__all__)
    assert not missing, f"hachi.sdk.__all__ is missing: {missing}"
```

### 7b. The version-discipline lock

- **File:** `tests/test_p3_06_sdk_v0.py`
- **Test name:** `test_sdk_version_matches_recorded_surface`
- **It must assert:** a checked-in `(SDK_VERSION, sorted(__all__))` pair matches the live module — so
  changing the surface without bumping the version fails, which is the "independently semver'd"
  promise made mechanical.
- **It must FAIL before your fix** with `AssertionError` once you alter either half.

```python
# The surface as of SDK_VERSION 0.1.0. Changing __all__ REQUIRES bumping
# SDK_VERSION and updating this record in the same commit. See docs/guides/sdk.md.
_SURFACE_BY_VERSION: dict[str, tuple[str, ...]] = {
    "0.1.0": tuple(sorted(_STABLE_SYMBOLS)),
}


def test_sdk_version_matches_recorded_surface() -> None:
    import hachi.sdk as sdk

    recorded = _SURFACE_BY_VERSION.get(sdk.SDK_VERSION)
    assert recorded is not None, (
        f"SDK_VERSION {sdk.SDK_VERSION!r} has no recorded surface — "
        "add one to _SURFACE_BY_VERSION when you bump the version."
    )
    assert tuple(sorted(sdk.__all__)) == recorded
```

### 7c. The typing-marker check

- **Test name:** `test_sdk_ships_py_typed_marker`
- **It must assert:** `importlib.resources` / `Path(hachi.sdk.__file__).parent / "py.typed"` exists —
  asserting the **installed** package, not the source tree.
- **It must FAIL before your fix** with `AssertionError` (§3.3: the file does not exist anywhere).

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> For 7a specifically, re-read the five-step procedure — the naive version of this test passes on
> unmodified `main` and gives you false confidence.

## 8. Acceptance criteria

**"Blessed" means all five of these are true and checkable. A nicer docstring is not blessing.**

- [ ] The regression test from §7a exists and demonstrably failed against a widened `__all__` (the
      five-step procedure, recounted in the commit message).
- [ ] **Typed:** `src/hachi/sdk/py.typed` exists and is present in a built wheel — verified by
      inspecting the wheel (§10), not by assuming the whole-tree include covers it.
- [ ] **Installable as documented:** either `pip install hachi-og[sdk]` resolves, or the
      `hachi-og[sdk]` string no longer appears in `src/hachi/sdk/__init__.py`. No false install
      instruction survives.
- [ ] **Surface pinned bidirectionally:** adding *or* removing a symbol from `__all__` fails the
      suite.
- [ ] **Version tied to surface:** changing `__all__` without bumping `SDK_VERSION` fails the suite.
- [ ] **Documented:** `docs/guides/sdk.md` exists with a working install line, all 12 symbols, the
      §5.2 stability policy, and an example you ran. `README.md` links it.
- [ ] `is_compatible` implements the rule its docstring describes; `_MIN_APP_VERSION` is gone.
- [ ] The 12 symbols are unchanged. This task blessed a surface; it did not redesign one.
- [ ] An ADR exists under `docs/architecture/adr/`, is linked from that directory's `README.md`, and
      has a `Status:` line plus `## Context` / `## Decision` / `## Consequences`
      (`scripts/check_adrs.py:26-28`).
- [ ] The ADR records the `sdk/` vs `client/` distinction (§3.7) so nobody proposes merging them.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).

## 9. Out of scope — do NOT

- **Do not start this while Wave 1 is open.** This is optional leverage from the review's *Missed
  Opportunities*, and at P3 it is the lowest-priority of the three. If Wave 1 is unfinished, close
  this file. This is the primary boundary on the task.
- **Do not route `client/models.py` through generated OpenAPI models** (§3.8). It is the review's
  second sentence and it is a separate, larger decision — cross-linked to
  [T-38](T-38-openapi-pilot-og-domain.md). It would turn a 3-day task into a contract-generation
  project.
- **Do not merge `sdk/` and `client/`, or "consolidate" one into the other** (§3.7). They look like
  duplication and are not: one is an import-time facade for pack authors, the other is an HTTP client
  for the TUI. The separation is deliberate.
- **Do not change the 12 symbols** (§5.4) — no additions, no removals, no renames. Blessing and
  redesigning are separate tasks.
- **Do not move `ToolSpec` out of `hachi.gateway`** to decouple the SDK (§3.1, `:75`). It is a real
  improvement with a real blast radius. Note it; leave it.
- **Do not add import-linter contracts for `sdk`/`client`** (§3.5). Making the commented layer model
  enforceable is [T-68](T-68-import-linter-exemption-burndown.md)'s territory, and a new blocking
  contract can fail the gate for reasons unrelated to this change.
- **Do not build `doctor --plugin`** (§3.6). It is marked ✅ in the roadmap and does not exist. That is
  a roadmap-honesty defect worth recording, not worth building here.
- **Do not fix `client/`'s unexported `BlockedItem` or its unused `__all__`** (§3.7). Noted; not this
  task.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). The three `is_compatible` tests may need **amending**
  per §5.3; amending with an explicit commit-message note is allowed, deleting is not.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_p3_06_sdk_v0.py

# The py.typed marker must be IN THE WHEEL, not just in the source tree.
uv build
python -c "
import zipfile, glob
whl = sorted(glob.glob('dist/*.whl'))[-1]
names = zipfile.ZipFile(whl).namelist()
print('wheel:', whl)
print('py.typed present:', any(n.endswith('hachi/sdk/py.typed') for n in names))
"

# If you added the extra, prove it resolves.
uv run python -c "import hachi.sdk as s; print(s.SDK_VERSION, len(s.__all__))"

uv run python scripts/check_adrs.py          # this task adds an ADR
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

**No `docs/bug-bank.md` entry is warranted for this task, and you should not invent one.** The bug
bank is for autopsies of real defects; nothing here misbehaves at runtime. Forcing an entry devalues
the file.

**Record the decision as an ADR instead**, per [CLAUDE.md](../../../../CLAUDE.md) ("`docs/DECISIONS.md`
— settled decisions / ADRs … record new ones here"). Create
`docs/architecture/adr/00NN-sdk-public-surface.md` — take the next free number (the highest existing is
`0005-observability-correlation-and-injected-exporter.md`; coordinate with
[T-75](T-75-durable-event-log.md), which also adds one) — and **link it from
`docs/architecture/adr/README.md` or `scripts/check_adrs.py` fails.**

```markdown
# NNNN. hachi.sdk is the supported public surface

- Status: Accepted
- Date: <YYYY-MM-DD>

## Context

`src/hachi/sdk/__init__.py` (113 lines, one file) re-exported 12 symbols and claimed to be a
"stable public surface for third-party pack authors", "independently semver'd", pinnable as
`hachi-og[sdk]`. Verification found: no `sdk` extra existed in `pyproject.toml`; no `py.typed`
marker existed anywhere in the repo, so the surface was PEP 561-invisible to consumers;
`SDK_VERSION` had no mechanical link to package metadata or to the surface; the contract test
(`tests/test_p3_06_sdk_v0.py`) checked only that stable symbols were PRESENT, never that
nothing extra had been added — despite its own docstring claiming otherwise; and no
consumer-facing document (README, ARCHITECTURE, DECISIONS, any ADR) mentioned it.

## Decision

Bless the existing 12-symbol surface rather than redesign it. Make each promise mechanical:
ship `py.typed`; resolve the install story; pin `__all__` bidirectionally in the test suite;
tie `SDK_VERSION` to a recorded surface fingerprint; document the surface and its stability
policy in `docs/guides/sdk.md`. Correct `is_compatible` to implement the major-match +
minor-GTE rule its docstring describes.

`hachi.sdk` and `hachi.client` remain SEPARATE and are not to be merged: `sdk/` is an
in-process re-export facade for pack authors; `client/` (2,488 lines) is a synchronous REST +
SSE consumer for the Textual TUI that imports nothing from `hachi` and talks to the gateway
over HTTP.

## Consequences

- The surface can no longer widen silently; adding a symbol requires a version bump and a
  test update in the same commit.
- Downstream pack authors get type checking against `hachi.sdk`.
- Deliberately NOT decided here: whether `client/models.py` (which mirrors
  `frontend/src/lib/data/types.ts`, not the gateway) should be generated from the OpenAPI
  schema. That is a four-layer contract problem tracked with the OpenAPI work (CF-5).
- Also noted, NOT fixed: `docs/strategy/09-execution-plan.md:466` marks `doctor --plugin`
  complete; it does not exist in `src/hachi/`.
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **The §7a test passes on unmodified `main`.** `__all__` currently matches `_STABLE_SYMBOLS`
  exactly, so a naive "write test, watch it fail" gives you a **green** result and a false sense of
  having satisfied Rule 2. Follow the five-step procedure in §7a and recount it in the commit message.
- **`py.typed` must be an *empty file*, not a directory and not a file with content.** A stray
  newline is harmless; a `.gitignore`d or zero-byte-rejected file is not. Verify it in the built
  wheel (§10), not in the source tree — a source-tree file that does not ship helps nobody.
- **Adding an extra to `pyproject.toml` can perturb `deptry`.** `pyproject.toml:66` runs `deptry` as
  an advisory rail; a new extra with no packages, or with packages nothing imports, may produce new
  advisory output. Read it before assuming you broke something.
- **`import hachi.sdk` pulls in the gateway.** `sdk/__init__.py:75` imports
  `hachi.gateway.tool_registration`, so any test or doc example that imports the SDK imports FastAPI
  transitively. If an example feels inexplicably slow to start, that is why.
- **`scripts/check_adrs.py` requires the ADR to be *linked from* `adr/README.md`.** An orphan ADR
  fails the lint even when the file itself is perfect — see `scripts/check_adrs.py:6-8`.
- **Do not confuse `SDK_VERSION` with the package version.** They are two unrelated `"0.1.0"` literals
  (§3.2). If you make them equal *mechanically*, you have deleted the "independently semver'd"
  property the docstring promises — which may be the right call, but it is a decision to record in the
  ADR, not a cleanup to perform silently.
- **BB-4 does not apply.** This task touches no gateway route, so no OpenAPI or frontend-type
  regeneration is needed.
