# T-60 · Delete the twin contract types (`SearchResult`, `ExtractResult`, `SearchProvider`, `ProviderHealth`)

|  |  |
|---|---|
| **Source finding** | CF-14 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P3 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | Low (mechanical) — but read §3.5 before you assume it is cosmetic |
| **Files you will touch** | `src/hachi/core/providers/base.py`, `src/hachi/core/providers/search.py`, `src/hachi/core/providers/__init__.py`, `src/hachi/core/resilience.py`, `tests/test_twin_contract_types.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

Four contract types are each defined twice in `core/`: `SearchResult`,
`ExtractResult`, `SearchProvider` and `ProviderHealth`. The twins are not identical —
they differ in base class (dataclass vs pydantic `BaseModel`), in field types, and in
which fields exist at all. They coexist without a type error because nothing type-checks
the boundary where they meet.

When you are done there is one definition per concept and the twins are gone. This is
mostly mechanical, but §3.5 shows one place where an instance of one class is
**already flowing into a slot annotated as the other** — so the acceptance bar is
"pick canonical and delete", not "add an alias".

## 2. Why this matters

Duplicate types split the fix. When someone adds a field to `SearchResult` — a
`published_date`, a `source_domain` — they will add it to one of the two, and the other
half of the search stack silently won't have it. That is not hypothetical: the two
`SearchResult` definitions have **already** drifted (different `score` semantics,
one has an `extra` dict and one doesn't), which means they were edited independently
at least once.

`ProviderHealth` is the sharper case: `core/providers/base.py:22-26` says it is
"Produced by `HealthRecorder` and consumed by `ModelRouter`" — but `HealthRecorder`
lives in `resilience.py` and produces the **other** `ProviderHealth`. The docstring
describes a relationship between two classes that are not the same class. §3.5 traces
the call chain where they meet.

This is P3 because nothing is broken today. It is worth doing *now* because it is a
one-day mechanical change that gets more expensive with every field added to either
twin.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 `SearchResult` — dataclass vs pydantic

`core/providers/base.py:40-48`:

```python
@dataclass
class SearchResult:
    """One search hit from a :class:`SearchProvider`."""

    title: str
    url: str
    snippet: str
    score: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)
```

`core/providers/search.py:23-38`:

```python
class SearchResult(BaseModel):
    """One search hit returned by a :class:`SearchProvider`.
    ...
    """

    model_config = ConfigDict(extra="ignore")

    title: str
    url: str
    snippet: str
    score: float | None = None
```

**They have already drifted:** `score` is `float = 0.0` in one and `float | None = None`
in the other, and only the dataclass has `extra`.

### 3.2 `ExtractResult` — the review missed this one; it is a twin too

`core/providers/base.py:51-58` (dataclass, `title: str = ""`, has `extra`) vs
`core/providers/search.py:41-54` (pydantic, `title: str | None = None`, no `extra`).
Same split, same drift. Include it — a fix that leaves `ExtractResult` doubled has done
three quarters of a mechanical job.

### 3.3 `SearchProvider` — two Protocols

Both are `@runtime_checkable` Protocols: `core/providers/base.py:118-119` and
`core/providers/search.py:62-63`. Each references *its own module's* result types in
its method signatures, so the two protocols are structurally distinct even where the
method names match.

### 3.4 `ProviderHealth` — dataclass twins with a `Literal` difference

`core/providers/base.py:20-37`:

```python
@dataclass
class ProviderHealth:
    """Health snapshot for one provider.

    Produced by :class:`~hachi.core.resilience.HealthRecorder` and consumed by
    :class:`~hachi.core.routing.router.ModelRouter` to skip open-breaker providers.
    """

    provider: str
    available: bool = True
    recent_error_rate: float = 0.0
    p50_latency_ms: float = 0.0
    consecutive_failures: int = 0
    breaker: str = "closed"  # "closed" | "open" | "half_open"
```

`core/resilience.py:115-132` — same six fields and the same `is_usable()`, but:

```python
    breaker: Literal["closed", "open", "half_open"] = "closed"
```

One is a `str` with the constraint in a comment; the other encodes it in the type.

### 3.5 ⚠️ They already meet — the live crossing

This is the part that makes it more than tidiness. `ModelRouter._get_recorder`
(`core/routing/router.py:303-320`) wires the recorder's update sink straight to the
adapter:

```python
        if provider_name not in self._recorders:
            on_update = None
            if self._providers is not None:
                provider = self._providers.get_by_name(provider_name)
                if provider is not None and hasattr(provider, "update_health"):
                    on_update = provider.update_health
            self._recorders[provider_name] = HealthRecorder(
                provider_name, self._resilience, on_update=on_update
            )
```

Follow the types:

1. `HealthRecorder.snapshot()` (`core/resilience.py:222`) returns
   **`resilience.ProviderHealth`** (constructed at `:241`).
2. It is handed to `on_update`, i.e. `AnthropicProvider.update_health`
   (`core/providers/anthropic_provider.py:94`), whose parameter is annotated
   **`base.ProviderHealth`** (imported at `anthropic_provider.py:17`). Same for
   `openai_compat_provider.py:102`/`:18`.
3. It is stored on `self._health` and returned by `health()`
   (`anthropic_provider.py:90-92`), still annotated `base.ProviderHealth`.
4. `ProviderRegistry.health()` (`core/providers/registry.py:111-120`) collects it into
   `dict[str, ProviderHealth]` — the `base` one, imported at `registry.py:18`:

   ```python
       def health(self) -> dict[str, ProviderHealth]:
           """Return health snapshots for all registered providers."""
           result: dict[str, ProviderHealth] = {}
           for p in self._providers:
               try:
                   h: ProviderHealth = p.health()
   ```

5. `ModelRouter` consumes that map at `core/routing/router.py:234`.

So a `resilience.ProviderHealth` travels through four slots annotated
`base.ProviderHealth` and is used for breaker filtering. **It works purely because the
field names line up** — exactly the "isinstance by structural luck" the review names.

### 3.6 Why no type checker catches it

The scoped strict gate (`mypy-strict-gate.ini`, run at `scripts/preflight.py:78-80`)
lists ~42 files. **None** of `core/providers/base.py`, `core/providers/search.py`,
`core/providers/registry.py`, `core/resilience.py` or `core/routing/router.py` is among
them. The full-tree mypy run is advisory only. So the mismatch at §3.5 step 2 is
invisible to the blocking gate.

### 3.7 Which twin is actually used

| Type | `base.py` used by | `search.py` used by |
|---|---|---|
| `SearchResult` / `ExtractResult` | re-exported via `providers/__init__.py:8-16`; no concrete consumer | `tavily_provider.py:17` (the only concrete adapter), `tests/test_search_platform.py:24` |
| `SearchProvider` | `registry.py:100` (isinstance dispatch) | docstring refs at `gateway/orchestrator.py:402`, `tools/search_tools.py:217`; `tests/test_search_platform.py:24` |
| `ProviderHealth` | `anthropic_provider.py:17`, `openai_compat_provider.py:18`, `registry.py:18`, plus `tests/test_multi_provider.py:27`, `test_provider_registry.py:11`, `test_routing_router.py:16` | (`resilience.py`'s own copy) `resilience.py:158`, `:222`, `:241`, `:484` |

The split is clean: **`search.py` owns the search types in practice**, and
**`base.ProviderHealth` is what everything except `resilience.py` imports**.

## 4. Reproduce the failure

Nothing malfunctions today. This is provable by reading, and the proof is the
definition count — say that plainly rather than inventing a failing command.

```bash
# 1. Four concepts, eight definitions.
grep -n "class SearchResult\|class ExtractResult\|class SearchProvider" \
  src/hachi/core/providers/base.py src/hachi/core/providers/search.py
grep -n "class ProviderHealth" src/hachi/core/providers/base.py src/hachi/core/resilience.py

# 2. They have drifted, so they are not interchangeable.
grep -n "score" src/hachi/core/providers/base.py src/hachi/core/providers/search.py
grep -n "breaker" src/hachi/core/providers/base.py src/hachi/core/resilience.py

# 3. The live crossing (§3.5).
grep -n "update_health" src/hachi/core/routing/router.py src/hachi/core/providers/anthropic_provider.py

# 4. Why nothing catches it: none of these files is in the blocking gate.
grep -c "providers/base.py\|providers/search.py\|resilience.py\|routing/router.py" mypy-strict-gate.ini
```

**You will see now:** (1) two `SearchResult`, two `ExtractResult`, two `SearchProvider`,
two `ProviderHealth`; (2) `score: float = 0.0` vs `score: float | None = None`, and
`breaker: str` vs `breaker: Literal[...]`; (3) `on_update = provider.update_health` in
the router and `def update_health(self, health: ProviderHealth)` in the adapter — two
different `ProviderHealth`s; (4) **`0`**.

**You should see after the fix:** grep (1) returns one definition per concept, and
grep (4) is still 0 but no longer matters, because the §7 test pins it instead.

## 5. What "fixed" looks like

The canonical choice follows the usage in §3.7. **The author has made it; it is not a
judgement call left to the implementer:**

1. **`SearchResult`, `ExtractResult`, `SearchProvider` → `core/providers/search.py`
   is canonical** (pydantic). It is what the only concrete adapter
   (`tavily_provider.py`) and the search test suite use, and pydantic gives validation
   at the vendor boundary — which is precisely where untrusted data enters.

   Delete the three from `core/providers/base.py:40-58` and `:118-119`.
   `core/providers/__init__.py:8-16` re-imports them from `search.py` instead, so the
   public export surface (`__all__`, `:19-28`) is **unchanged**.

2. **`ProviderHealth` → `core/providers/base.py` is canonical.** It is imported by both
   adapters, the registry and three test files; `resilience.py` has the only other
   copy. Adopt the `Literal["closed", "open", "half_open"]` annotation from
   `resilience.py:132` — it is strictly better than `str` + a comment — and delete
   `resilience.py:115-132`, importing from `providers.base` instead.

   Check the import direction first: `core/resilience.py` importing
   `core/providers/base.py` is a `core → core` edge and fine, **but** `providers/base.py`
   imports `hachi.core.llm` (`base.py:15`) and `hachi.core.routing.*` (`:16-17`). If
   `resilience.py` is imported *by* any of those, you have a cycle — verify before you
   commit to this direction, and if there is one, move `ProviderHealth` to a third,
   dependency-free module rather than forcing it.

3. `base.py`'s docstring at `:24-25` ("Produced by `HealthRecorder`…") becomes **true**
   for the first time. Keep it.

4. Observable outcome: no behaviour change whatsoever. `hachi eval run` unchanged,
   every provider test unchanged.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. **`ProviderHealth` first** (it is the one with the live crossing). Delete
   `core/resilience.py:115-132`; add `from hachi.core.providers.base import ProviderHealth`.
   Copy the `Literal[...]` annotation onto `base.py:33`. Run
   `uv run pytest tests/test_multi_provider.py tests/test_provider_registry.py tests/test_routing_router.py -q`.
3. Verify no import cycle: `uv run lint-imports` must stay green (it is a **blocking**
   preflight step, `scripts/preflight.py:85`).
4. `SearchResult` + `ExtractResult`: delete `core/providers/base.py:40-58`; re-point
   `core/providers/__init__.py:8` at `search.py`. Confirm `__all__` (`:19-28`) still
   exports the same names.
5. `SearchProvider`: delete `core/providers/base.py:118-119` and re-point. Check
   `registry.py:100` — it does an isinstance dispatch against the Protocol, so it must
   now import from `search.py`.
6. Grep the docstring cross-references and fix the ones that now point at a deleted
   symbol: `gateway/orchestrator.py:402`, `tools/search_tools.py:217`,
   `routing/capability.py:16`, `routing/descriptor.py:44`,
   `anthropic_provider.py:4`, `tavily_provider.py:153`, `:183`. These are Sphinx-style
   `:class:` refs — a dangling one is silent, so do it by grep, not by eye.
7. Run the regression test — it must now pass.
8. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_twin_contract_types.py` (**new**)
- **Test names:** `test_contract_types_have_exactly_one_definition` and
  `test_health_recorder_produces_the_canonical_provider_health`
- **It must assert:** the real, observed object identity — that the class the recorder
  produces **is** the class the registry annotates. Not that the fields match:
  matching fields is the bug (§3.5), so a field-equality test would pass today and pin
  nothing.
- **It must FAIL before your fix** with something like
  `AssertionError: HealthRecorder produces <class 'hachi.core.resilience.ProviderHealth'> but ProviderRegistry.health() is annotated with <class 'hachi.core.providers.base.ProviderHealth'>`.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations


def test_health_recorder_produces_the_canonical_provider_health() -> None:
    """The health object flowing through the router must be ONE class.

    Regression: HealthRecorder.snapshot() returned resilience.ProviderHealth,
    which was passed to Provider.update_health(health: base.ProviderHealth) via
    ModelRouter._get_recorder's on_update wiring and then collected into
    ProviderRegistry.health() -> dict[str, base.ProviderHealth]. It only worked
    because the field names happened to line up; the classes were unrelated and
    had already drifted (breaker: str vs Literal[...]).
    """
    from hachi.core.providers.base import ProviderHealth as CanonicalHealth
    from hachi.core.resilience import HealthRecorder, ProviderHealth as ResilienceHealth

    assert ResilienceHealth is CanonicalHealth, (
        f"two ProviderHealth classes still exist: {ResilienceHealth!r} vs {CanonicalHealth!r}"
    )

    recorder = HealthRecorder("test-provider", _default_resilience_policy())
    snapshot = recorder.snapshot()
    assert type(snapshot) is CanonicalHealth, (
        f"HealthRecorder produces {type(snapshot)} but the registry is annotated "
        f"with {CanonicalHealth}"
    )


def test_contract_types_have_exactly_one_definition() -> None:
    """SearchResult / ExtractResult / SearchProvider must resolve to one class each."""
    from hachi.core.providers import ExtractResult, SearchProvider, SearchResult
    from hachi.core.providers import search as search_mod

    assert SearchResult is search_mod.SearchResult
    assert ExtractResult is search_mod.ExtractResult
    assert SearchProvider is search_mod.SearchProvider
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Specifically: an `assert A.__name__ == B.__name__` or a field-by-field comparison
> **will** pass today. Use `is` on the classes.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_health_recorder_produces_the_canonical_provider_health` failed before the fix.
- [ ] `grep -rn "class SearchResult\|class ExtractResult\|class SearchProvider\|class ProviderHealth" src/` returns **exactly four** lines.
- [ ] `core/providers/__init__.py`'s `__all__` is unchanged — no public export was renamed or dropped.
- [ ] `ProviderHealth.breaker` is the `Literal["closed", "open", "half_open"]` annotation, not `str`.
- [ ] `uv run lint-imports` is green (no new cycle).
- [ ] No `:class:` docstring reference points at a deleted symbol.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not add these files to `mypy-strict-gate.ini`.** This is the adjacent thing you
  will reach for — §3.6 says the gate is why nobody caught it, so adding them looks
  like the real fix. It isn't, for this task: those files carry pre-existing strict
  debt unrelated to the twins, so you would be signing up for an unbounded burn-down
  mid-refactor. Adding them is CF-17's mypy ratchet; note it and move on.
- **Do not reconcile the drifted field semantics.** `score: float = 0.0` vs
  `float | None = None`, and the presence of `extra` — picking `search.py` as canonical
  *decides* those by adoption. Do not "restore" the `extra` dict onto the pydantic model
  to avoid losing a field: nothing reads it (`base.SearchResult` has no concrete
  producer, §3.7), and adding an unused field to the canonical type is how twins are
  born.
- **Do not touch `SpeechProvider`, `StorageProvider`, `Embedder` or `AIProvider`**
  (`base.py:100`, `:134`, `:145`, `:62`). They are single-definition and not part of
  this finding.
- **Do not "improve" `HealthRecorder`.** Its percentile logic at `resilience.py:238-240`
  has a deliberate nearest-rank correction with a comment explaining an off-by-one. You
  are moving a dataclass out of that file, not editing the recorder.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Run the **full** suite. `ProviderHealth` is on the router's breaker path, which every
routed LLM call consults, and the search types are on the provider registry's
isinstance dispatch (`registry.py:85-100`) — a Protocol that stops matching makes a
provider silently unregisterable rather than raising. Report the **actual** pass/fail
counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Four contract types defined twice; health objects crossed the seam by structural luck

- **Symptom:** No visible failure — which is the point. `SearchResult`, `ExtractResult`, `SearchProvider` and `ProviderHealth` each existed as two unrelated classes, and a `resilience.ProviderHealth` instance was already flowing through four slots annotated `providers.base.ProviderHealth` (HealthRecorder.snapshot → Provider.update_health → Provider.health → ProviderRegistry.health → ModelRouter). It worked only because the field names matched.
- **Root cause:** `core/providers/base.py` (dataclasses) and `core/providers/search.py` (pydantic) were written for the same contracts in different initiatives; `core/resilience.py` grew its own `ProviderHealth` beside the one in `base.py` whose docstring already claimed the recorder produced it. The twins had drifted (`score: float = 0.0` vs `float | None = None`; `breaker: str` vs `Literal[...]`). None of the five files involved is in the blocking mypy gate, so the mismatch was invisible.
- **Fix:** `search.py` canonical for the three search contracts; `providers/base.py` canonical for `ProviderHealth` (adopting the `Literal` annotation). Twins deleted, `providers/__init__` re-points, public `__all__` unchanged.
- **Avoid:** two classes with the same name and the same fields are not "compatible" — they are a fix that will land on one of them. When a docstring says "produced by X and consumed by Y", check that X and Y are talking about the same class.
- **Locked by:** `tests/test_twin_contract_types.py` — `test_health_recorder_produces_the_canonical_provider_health`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. The provider registry pulls
  in adapters that transitively touch embedding code; if you reach for module patching
  to isolate a provider test, use the existing fixtures instead.
- **`@runtime_checkable` Protocols check methods, not signatures.** `isinstance(x, SearchProvider)`
  passes if the method *names* exist, regardless of parameter or return types. So
  deleting one Protocol will **not** produce an isinstance failure that points at your
  mistake — the failure will be a wrong-shaped result much later. This is why §7 asserts
  class identity with `is`.
- **Import cycle risk is real.** `core/providers/base.py` imports `hachi.core.llm`
  (`:15`) and `hachi.core.routing.capability` / `.descriptor` (`:16-17`). Making
  `core/resilience.py` import from `providers/base.py` pulls all of that into
  `resilience`'s import graph. `uv run lint-imports` is blocking — run it *before* you
  finish, not after.
- **`providers/__init__.py` is a public-ish surface.** `__all__` at `:19-28` lists eight
  names. Changing where they come from is fine; changing the list is not — `sdk/` and
  `client/` may re-export.
- **Three test files import `base.ProviderHealth` directly**
  (`tests/test_multi_provider.py:27`, `test_provider_registry.py:11`,
  `test_routing_router.py:16`), and `tests/test_routing_router.py:52` defines its own
  `update_health(self, health: ProviderHealth)` stub. If you move the canonical class,
  those imports must still resolve — keeping `providers/base.py` as the home for
  `ProviderHealth` (as §5 recommends) means they need no change at all.
