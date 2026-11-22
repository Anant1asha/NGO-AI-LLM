# T-49 · Decide the `MemoryProvider` seam: adopt it at the call sites, or delete the ABC

|  |  |
|---|---|
| **Source finding** | CF-12 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) ("seams that don't seam") |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | [T-48](T-48-memory-package-boundary.md) — it must know whether `memory_provider.py` still exists before it moves it |
| **Effort** | ~1 day (option A: delete) · ~4 days (option B: adopt) |
| **Difficulty** | **High — DECISION REQUIRED. Read §5 before you write a line.** |
| **Files you will touch** | `src/hachi/core/memory_provider.py`, `src/hachi/gateway/orchestrator.py`, `src/hachi/gateway/shared_services.py`, `src/hachi/core/user_profile.py` (option B only), `tests/test_memory_provider.py`, `docs/DECISIONS.md`, `docs/bug-bank.md` |

---

## 1. Brief

`MemoryProvider` is an ABC advertised as the swap seam for alternative memory backends
("Enables swapping ChromaDB for alternative backends (Qdrant, Pinecone, Honcho)
without touching core agent code" — `core/memory_provider.py:5-6`). Its three contract
methods — `upsert`, `search`, `delete` — are **called from nowhere in `src/`**. Boot
constructs a provider, calls `initialize()`, then immediately unwraps it back to the
raw `MemoryVault` and uses that for everything. The two alternative backends have no
`.vault`, so unwrapping yields `None` — which the rest of the system reads as *memory
off*, not *different memory*.

When you are done, exactly one of these is true: the seam is real (call sites go
through the provider and a non-Chroma backend actually stores and retrieves facts), or
the ABC is gone and boot builds a `MemoryVault` directly. **The middle state — which is
today's state — is not an acceptable outcome.**

## 2. Why this matters

An abstraction that nothing calls is worse than no abstraction. It costs 304 lines and
four classes; it appears in the module docstring as a capability; it has a config knob
(`memory.backend`) that users can set; and setting that knob to either non-default
value **silently disables semantic memory** rather than swapping the backend. A user
who reads `MemoryBackend = Literal["chroma", "in_memory", "fts5_only"]`
(`core/settings.py:77`) and picks `in_memory` for a lightweight deploy gets an agent
whose memory tools answer *"Long-term memory is not available"*
(`tools/memory_tools.py:190`, `:215`) — while the codebase says a provider was
resolved and initialized successfully.

That is the same class of defect the audit called existential: a feature reporting
success while doing nothing. The fix is not "make it prettier" — it is to make the
configuration surface tell the truth. Either option below does that. Neither
half-measure does.

If the change you are about to write leaves `memory.backend` claiming three working
backends when only one works, stop and re-read.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The contract methods have zero production callers

`rg -n "_provider\b" src/` returns every use of a resolved provider in the codebase.
Filtered to the memory provider (the other hits are LLM/search providers), the
complete list is:

```
src/hachi/gateway/orchestrator.py:3024      _provider = ChromaMemoryProvider(vault=vault)
src/hachi/gateway/orchestrator.py:3026      _provider = resolve_provider(_memory_settings)
src/hachi/gateway/orchestrator.py:3030      if isinstance(_provider, ChromaMemoryProvider):
src/hachi/gateway/orchestrator.py:3031          _provider.initialize(...)
src/hachi/gateway/orchestrator.py:3038          _provider.initialize(brain_dir=...)
src/hachi/gateway/orchestrator.py:3039      vault = _provider.vault if isinstance(...) else None
src/hachi/gateway/orchestrator.py:3045      _is_fts5_only = isinstance(_provider, FTS5MemoryProvider)
src/hachi/gateway/orchestrator.py:3058          _provider.attach_graph_index(_graph_index)
src/hachi/gateway/orchestrator.py:3072          _provider.attach_graph_index(_graph_index)
src/hachi/gateway/orchestrator.py:3087          _provider.attach_memory_writer(_shared.memory_writer)
src/hachi/gateway/orchestrator.py:3099          _provider.attach_memory_writer(_memory_writer)
src/hachi/gateway/shared_services.py:300    _provider = resolve_provider(_memory_settings)
src/hachi/gateway/shared_services.py:301    _provider.initialize(brain_dir=brain_dir)
src/hachi/gateway/shared_services.py:302    if isinstance(_provider, ChromaMemoryProvider):
src/hachi/gateway/shared_services.py:303        vault = _provider.vault
```

**`upsert`, `search` and `delete` do not appear.** Only `initialize()`,
`attach_graph_index()`, `attach_memory_writer()` and the `.vault` unwrap are used —
and of those four, **two are not on the ABC at all** (`attach_graph_index` /
`attach_memory_writer` exist only on `FTS5MemoryProvider`, `core/memory_provider.py:248`
and `:252`, plus `attach_graph_index` on `MemoryVault` at `memory_vault.py:696`).

So the interface that *is* used is not the interface that is *declared*.

### 3.2 Boot unwraps the provider — two sites

`src/hachi/gateway/orchestrator.py:3039-3040`, inside `boot_agent`:

```python
        vault = _provider.vault if isinstance(_provider, ChromaMemoryProvider) else None
    memory.set_vault(vault)
```

`src/hachi/gateway/shared_services.py:300-307`, inside `ProcessSharedServices`:

```python
        _provider = resolve_provider(_memory_settings)
        _provider.initialize(brain_dir=brain_dir)
        if isinstance(_provider, ChromaMemoryProvider):
            vault = _provider.vault
            # Mark as the process-shared vault so an individual AgentSession never
            # closes it on shutdown — only shutdown_all() (atexit) closes it once.
            if vault is not None:
                vault.is_shared = True
```

Both discard the provider immediately after construction. Nothing holds a reference to
it past boot.

### 3.3 The alternative backends are "memory off", not a swap

`resolve_provider` — `src/hachi/core/memory_provider.py:285-304`:

```python
    backend = (memory_settings.backend or "chroma").strip().lower()
    if backend == "in_memory":
        return InMemoryProvider()
    if backend == "fts5_only":
        return FTS5MemoryProvider()
    # Default: ChromaDB-backed vault.
    return ChromaMemoryProvider()
```

`InMemoryProvider` (`:170`) and `FTS5MemoryProvider` (`:229`) have **no `.vault`
attribute**, so the `isinstance` unwrap at both sites in §3.2 yields `None`, and
`memory.set_vault(None)` disables the whole vault-facing surface. `MemoryManager.sync_turn`
returns immediately on `if not self.vault:` (`core/memory.py:591-592`), and every
memory tool short-circuits — e.g. `tools/memory_tools.py:190`:

```python
        if not vault:
            return "Long-term memory is not available (backend=in_memory has no semantic store)."
```

`FTS5MemoryProvider.delete` — `src/hachi/core/memory_provider.py:277-279` — is the
clearest single statement of the problem:

```python
    def delete(self, fact_id: str) -> bool:
        """Not supported for file-based facts; always returns False."""
        return False
```

A backend that satisfies the ABC by returning `False` from a required method is not
implementing the contract; it is documenting that the contract does not fit.

`FTS5MemoryProvider` is the *least* dead of the three — its `upsert`/`search` bodies
(`:256-275`) are real, delegating to the attached `MemoryWriter`/`MemoryIndex`. But
because nothing ever calls `provider.upsert()` or `provider.search()`, those bodies
never execute either. Its `.og` write path only runs because
`orchestrator.py:3087`/`:3099` hand the writer to it and *other* code writes `.og`
files directly.

### 3.4 `user_profile.py` bypasses the seam entirely — twelve private reaches

`UserProfileStore` (`src/hachi/core/user_profile.py:226`) talks to `MemoryVault`
internals directly. The audit's "422-480" undershoots; the real range is **422-498**.
Verified with `rg -n "_vault\._|MemoryVault\._" src/hachi/core/user_profile.py` — the
complete list:

```
422:            with self._vault._vault_lock:
423:                self._vault._assert_open()
424:                ucoll = self._vault._get_collection("user_collection")
461:        existing_id = MemoryVault._generate_id(content)
463:            with self._vault._vault_lock:
464:                self._vault._assert_open()
465:                ucoll = self._vault._get_collection("user_collection")
480:        result: str = self._vault._guarded_write("user_collection", content, category)
494:            candidate_id = MemoryVault._generate_id(value_or_id)
496:            with self._vault._vault_lock:
497:                self._vault._assert_open()
498:                ucoll = self._vault._get_collection("user_collection")
```

Five distinct privates: `_vault_lock`, `_assert_open()`, `_get_collection()`,
`_guarded_write()`, `MemoryVault._generate_id()`. `_vault_set` even documents *why*
it reaches through (`:449-458`): it needs to bypass `upsert_user_fact`'s category
normalisation. That is a real requirement the public API does not serve — which is a
data point for option B's cost, not an argument against it.

### 3.5 Where the "seam" is actually load-bearing today: `isinstance`

The only behaviour the provider abstraction currently produces is three `isinstance`
checks that select boot paths:

- `orchestrator.py:3030` — Chroma gets the three-settings `initialize()`; everything
  else gets the bare one.
- `orchestrator.py:3039` / `shared_services.py:302` — Chroma yields a vault; everything
  else yields `None`.
- `orchestrator.py:3045` — `_is_fts5_only` forces `graph=True`
  (`:3046`: `_use_graph = _memory_settings.graph or _is_fts5_only`).

A polymorphic seam whose entire observable effect is `isinstance` dispatch at the
composition root is a `Literal` string wearing a costume.

### 3.6 Why it survived — `tests/test_memory_provider.py`

The test file exercises `resolve_provider`'s three branches (`:103`, `:109`, `:115`)
and the providers' methods directly. **No test asserts that any production code path
calls `provider.upsert()` / `.search()` / `.delete()`**, and no test asserts that
`backend="in_memory"` produces a working memory. That gap is what your regression test
must close, whichever option you pick.

## 4. Reproduce the failure

This one **is** decisively provable from a shell, because the claim is about the
absence of call sites and that is exactly what grep measures.

```bash
# 1. The ABC's three contract methods, called on a provider instance, anywhere in src/.
#    Expect: NO output.
rg -n "provider\.(upsert|search|delete)\(" src/

# 2. Every use of a resolved memory provider. Expect: only initialize / attach_* /
#    .vault / isinstance — never upsert, search or delete.
rg -n "_provider\." src/hachi/gateway/orchestrator.py src/hachi/gateway/shared_services.py

# 3. The unwrap that discards the seam. Expect: two hits.
rg -n "isinstance\(_provider, ChromaMemoryProvider\)" src/

# 4. The FTS5 backend's delete. Expect: `return False` with a docstring saying so.
rg -n -A 3 "def delete" src/hachi/core/memory_provider.py
```

**You will see now:** (1) silence — the contract has no callers; (2) only
`initialize`, `attach_graph_index`, `attach_memory_writer` and `.vault`; (3) two
unwrap sites; (4) `FTS5MemoryProvider.delete` returning `False` unconditionally.

**You should see after the fix:**
- *Option A (delete):* greps (1)–(4) all return nothing, because `memory_provider.py`
  is gone.
- *Option B (adopt):* grep (1) returns the real call sites in `tools/memory_tools.py`
  and `core/memory.py`; grep (3) returns nothing.

**Optional live confirmation of the user-facing symptom** — this one is real and worth
seeing once, because it is what a user experiences:

```bash
# In a scratch config only. Set memory.backend = "in_memory" in settings.toml, then:
hachi run --once "Remember that my deploy target is fly.io, then search your memory for 'deploy'."
```

Today the agent's memory tools answer *"Long-term memory is not available
(backend=in_memory has no semantic store)"* — even though `InMemoryProvider` has a
perfectly functional `upsert`/`search` pair sitting unused at
`core/memory_provider.py:188-216`. **Do not run this against your real
`settings.toml`** — it is a durable config write.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> This task cannot be implemented until someone picks. Both options are legitimate;
> the current state is not. Record the choice in `docs/DECISIONS.md` **before** you
> write code — that record is half the deliverable.
>
> ---
>
> **(A) Delete the ABC. Boot builds a `MemoryVault` directly. — RECOMMENDED.**
>
> `resolve_provider`, `MemoryProvider`, `ChromaMemoryProvider`, `InMemoryProvider` and
> `FTS5MemoryProvider` all go. `boot_agent` and `ProcessSharedServices` construct
> `MemoryVault(...)` directly. The two non-Chroma paths are re-expressed as what they
> actually are: `memory.backend` narrows to a `Literal["chroma", "fts5_only"]`, where
> `fts5_only` means "no Chroma client; `.og` + FTS5 are canonical" and is selected by a
> plain `if`, not by polymorphism. `in_memory` is **removed from the Literal** — it
> currently means "memory silently off", which no user asks for; if a genuine
> ephemeral mode is wanted later it can be added honestly.
>
> *For:*
> - Deletes ~304 lines and four classes that produce no behaviour.
> - Removes a config value that lies to users today.
> - `boot_agent` gets shorter and its memory block becomes readable in one pass.
> - Honest: the project has exactly one semantic backend and has never had two.
> - Smallest risk. The only real code paths (`ChromaMemoryProvider.initialize`'s
>   kwargs forwarding, `FTS5MemoryProvider`'s writer/index attachment) move to boot
>   verbatim.
>
> *Against:*
> - Loses the *stated* extensibility story. If a Qdrant/Honcho backend is on the
>   roadmap in the next two quarters, you will rebuild something like this — though
>   you will rebuild it against real requirements instead of guessed ones.
> - `MemoryVault` becomes explicitly the only backend, so its 1,801 lines become
>   load-bearing with no declared alternative. (They already are; this just admits it.)
>
> ---
>
> **(B) Adopt the seam at the call sites.**
>
> Every read/write of long-term memory goes through the provider: `MemoryManager` holds
> a `MemoryProvider`, not a `vault`; `tools/memory_tools.py` calls
> `provider.upsert/search/delete`; `set_vault()` becomes `set_provider()`.
> `InMemoryProvider` and `FTS5MemoryProvider` become *actually usable*, which means the
> `memory.backend` config finally means what it says.
>
> *For:*
> - The extensibility claim becomes true; a fourth backend is a new class, not a fork.
> - `backend="in_memory"` becomes a genuinely useful CI/test mode with no ChromaDB.
>
> *Against — and these are large:*
> - **The ABC is nowhere near sufficient.** The real vault surface used in production
>   includes `upsert_user_fact`, `upsert_agent_fact`, `search_user_profile`,
>   `get_user_snapshot`, `get_agent_snapshot`, `get_recent_facts`,
>   `get_profile_stats`, `prune_core_memory`, `delete_user_fact`, `delete_agent_fact`,
>   `attach_graph_index`, `is_shared`, plus the twelve private reaches in §3.4. Every
>   one of those must be designed into the interface *or* explicitly declared
>   Chroma-only — and the second answer just reintroduces `isinstance`.
> - `user_profile.py` must be rewritten against a public API that does not exist yet
>   (§3.4 shows it deliberately bypasses `upsert_user_fact` to preserve categories).
> - `InMemoryProvider` would need a user_profile collection, an agent_profile
>   collection, snapshots, decay and redaction to reach parity — otherwise
>   `backend="in_memory"` still lies, just at a different level.
> - Every one of those methods needs backend-parity tests, or you have moved the lie
>   rather than removed it.
>
> ---
>
> **Recommendation: (A).** The seam was built for zero-behaviour-change and was never
> adopted; three years of hindsight say the requirement it anticipated did not arrive.
> Deleting it is honest, cheap, and reversible — the git history keeps the design if
> a real second backend ever lands. **The rest of this spec assumes (A).** If you pick
> (B), say so in the commit message, write the ADR, and rewrite §6/§7 accordingly —
> and budget four days, not one.

### Target state under option (A)

1. `src/hachi/core/memory_provider.py` is **deleted**.
2. `core/settings.py:77` narrows: `MemoryBackend = Literal["chroma", "fts5_only"]`.
   The `MemorySettings.backend` default stays `"chroma"`.
3. `gateway/shared_services.py:296-307` becomes a direct build:
   ```python
   # --- MemoryVault (shared Chroma client) ---
   vault: Any = None
   _raw_memory = config.get("memory", {})
   _memory_settings = MemorySettings.model_validate(_raw_memory)
   if _memory_settings.backend != "fts5_only":
       from hachi.core.memory_vault import MemoryVault

       vault = MemoryVault(brain_dir=brain_dir)
       # Mark as the process-shared vault so an individual AgentSession never
       # closes it on shutdown — only shutdown_all() (atexit) closes it once.
       vault.is_shared = True
   ```
4. `gateway/orchestrator.py:3020-3046` becomes the same shape, keeping the
   three-settings forwarding that `ChromaMemoryProvider.initialize` performed today
   (`memory_provider.py:134-144`) — i.e. `recall_distance_max`,
   `core_memory_max_entries`, `decay_half_life_days` are passed straight to
   `MemoryVault(...)` when not `None`. **This forwarding is the one piece of real
   behaviour inside the deleted file; losing it is a regression.** See
   [T-06](T-06-memory-settings-reach-vault.md), which owns the wider version of that
   problem — coordinate, do not duplicate.
5. `_is_fts5_only` becomes `_memory_settings.backend == "fts5_only"`; the
   `_use_graph` line (`:3046`) is otherwise unchanged.
6. `_provider.attach_graph_index(...)` / `attach_memory_writer(...)` calls
   (`:3058`, `:3072`, `:3087`, `:3099`) disappear — under `fts5_only` there is no
   provider object to attach to. The index and writer are already built and held by
   `ProcessSharedServices` (`shared_services.py:317-325`) and the local branch
   (`orchestrator.py:3064-3067`); the reads go through those directly.
7. `tests/test_memory_provider.py` is **deleted** (it tests only deleted code) and
   replaced by the §7 test.
8. `docs/DECISIONS.md` gains an ADR recording the choice and its reasoning.

## 6. Steps

*(Option A. If you chose B, this section does not apply — write your own and get it
reviewed before starting.)*

1. **Write the ADR in `docs/DECISIONS.md` first.** One paragraph: what the seam was,
   why it was never adopted, what was deleted, and what a real second backend would
   need to reintroduce. This is the durable artefact; the code change is the easy part.
2. Write the regression test from §7 and watch it **fail**.
3. Narrow `MemoryBackend` in `core/settings.py:77` to `Literal["chroma", "fts5_only"]`.
   Grep for `"in_memory"` across `src/`, `tests/`, `settings.example.toml` and
   `docs/` — every reference must be updated or removed, including the message in
   `tools/memory_tools.py:190` and `:215` which names the backend.
4. Rewrite `gateway/shared_services.py:296-307` per §5 item 3.
5. Rewrite `gateway/orchestrator.py:3011-3046` per §5 items 4-5, **preserving the
   three-settings forwarding verbatim** and preserving every existing comment
   ([CLAUDE.md](../../../../CLAUDE.md) Rule 3 — move comments, don't delete them).
6. Remove the four `attach_*` calls at `orchestrator.py:3058`, `:3072`, `:3087`,
   `:3099`. Confirm the FTS5 read/write path still has its `MemoryIndex` and
   `MemoryWriter` — they come from `_shared.graph_index` / `_shared.memory_writer` or
   the locally-built pair, not from the provider.
7. Delete `src/hachi/core/memory_provider.py`.
8. Delete `tests/test_memory_provider.py`.
9. `rg -n "MemoryProvider|ChromaMemoryProvider|InMemoryProvider|FTS5MemoryProvider|resolve_provider" src/ tests/`
   must return **nothing** (mind `resolve_provider_model` in `core/onboarding.py:145` —
   that is a *different* symbol; do not touch it).
10. Run `uv run python scripts/preflight.py` (**full**) and report real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

The invariant worth locking is not "the ABC is gone" (that is a `find_spec` check and
worth one line); it is **"every value `memory.backend` accepts produces a memory that
actually works"**. That is the property whose violation created this task, and it must
hold under either option.

- **File:** `tests/test_memory_backend_honesty.py` (**new**)
- **Test names:** `test_every_declared_backend_produces_a_working_memory_or_is_not_declared`
  and `test_memory_provider_abc_is_gone`
- **It must assert:** the real, observed behaviour — that for **every** literal in
  `MemoryBackend`, booting the memory layer yields something that can store and
  retrieve a fact. Not a mock's return value: write a fact, read it back.
- **It must FAIL before your fix** with:
  `AssertionError: backend 'in_memory' resolved but stores nothing: vault is None` —
  because `resolve_provider("in_memory")` returns an `InMemoryProvider` whose `.vault`
  does not exist, so the unwrap in §3.2 yields `None`.

```python
# sketch — adapt to the repo's existing fixtures
import importlib.util
import typing

import pytest

from hachi.core.settings import MemoryBackend, MemorySettings


def _declared_backends() -> list[str]:
    """Every literal value memory.backend accepts."""
    return list(typing.get_args(MemoryBackend))


@pytest.mark.parametrize("backend", _declared_backends())
def test_every_declared_backend_produces_a_working_memory_or_is_not_declared(
    backend: str, tmp_path
) -> None:
    """A backend the config accepts must actually store and retrieve a fact.

    Regression (T-49): `in_memory` and `fts5_only` resolved to providers whose
    `.vault` did not exist, so boot set vault=None and every memory tool answered
    "Long-term memory is not available" — while config reported the backend as
    selected. A backend that cannot store a fact must not be offered.
    """
    settings = MemorySettings(backend=backend)  # type: ignore[arg-type]
    store = _build_memory_for(settings, brain_dir=tmp_path)   # helper you write in step 4/5

    assert store is not None, f"backend {backend!r} resolved but stores nothing: vault is None"

    fact_id = store.upsert_fact("the deploy target is fly.io", category="workspace_state")
    assert not fact_id.startswith("BLOCKED:")

    hits = store.semantic_search("deploy target", top_k=5)
    assert any("fly.io" in (h.get("raw_content") or h.get("content", "")) for h in hits)


def test_memory_provider_abc_is_gone() -> None:
    """The unadopted seam was deleted, not left half-wired (T-49 option A)."""
    assert importlib.util.find_spec("hachi.core.memory_provider") is None
```

Notes for whoever writes this for real:

- `_build_memory_for(...)` should be the **same** function boot calls after step 4/5,
  not a test-local reimplementation — otherwise the test proves nothing about boot.
  Extract it as a small module-level helper in `gateway/shared_services.py` and import
  it here.
- Under option A the parametrize collapses to `["chroma", "fts5_only"]` and the
  `fts5_only` case exercises `MemoryWriter` + `MemoryIndex` against `tmp_path` — no
  Chroma. That case is the valuable one; keep it.
- The `chroma` case touches real ChromaDB. Follow the existing suite's pattern of
  constructing against `tmp_path` (see `tests/test_memory_vault_close.py`) and read
  §12 (BB-3) first.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] An ADR recording the decision exists in `docs/DECISIONS.md`, written **before** the code change.
- [ ] The regression test from §7 exists, and failed before the fix with `vault is None` for at least one declared backend.
- [ ] **Option A:** `rg -n "MemoryProvider|resolve_provider\(" src/` returns nothing (excluding `resolve_provider_model`, an unrelated symbol in `core/onboarding.py`).
- [ ] **Option A:** `rg -n "in_memory" src/ tests/ settings.example.toml docs/guides/` shows no surviving claim that the backend exists.
- [ ] **Option B:** `rg -n "\.vault\b" src/hachi/gateway/` returns nothing — no call site unwraps the provider.
- [ ] The three memory settings (`recall_distance_max`, `core_memory_max_entries`, `decay_half_life_days`) still reach `MemoryVault` — verify against [T-06](T-06-memory-settings-reach-vault.md) rather than assuming.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not start the package move.** [T-48](T-48-memory-package-boundary.md) moves
  these files into `core/memory/`. Doing both at once produces a diff in which a
  deletion and a rename are indistinguishable. This is the single most likely drift for
  this task, because you will be staring at `core/memory_provider.py` and the neighbours
  will look untidy. Leave them.
- **Do not "improve" `MemoryVault` while you are in there.** It is 1,801 lines and every
  one of them will tempt you. Decomposing it is a separate task.
- **Do not fix `user_profile.py`'s twelve private reaches under option A.** Deleting the
  ABC does not make them worse and fixing them is a distinct change with its own
  regression surface. Note them; move on. (Under option B they are unavoidable — that
  is part of B's cost, not a bonus.)
- **Do not delete `MemoryVault.attach_graph_index`** (`memory_vault.py:696`) because the
  provider's version is going away. The vault's is live and called from
  `orchestrator.py:3056` and `:3070`.
- **Do not touch `resolve_provider_model`** in `core/onboarding.py:145` — similar name,
  entirely unrelated (it resolves an LLM model id).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
  Deleting `tests/test_memory_provider.py` under option A is **not** weakening a test:
  it exclusively tests deleted code, and §7 replaces its coverage with a stronger
  assertion. Say exactly that in the commit message.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** This changes boot-time construction of the
memory layer, which every gateway-booting test in the suite exercises transitively —
including the cockpit/live-gateway tests that `conftest.py` warns about. A scoped run
over `tests/test_memory_*.py` will pass and tell you nothing.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `memory.backend` offered three backends; two silently meant "memory off"

- **Symptom:** Setting `memory.backend = "in_memory"` (or `"fts5_only"`) in
  settings.toml produced an agent whose memory tools all answered "Long-term memory is
  not available", with no error and no warning — while boot logged a successfully
  resolved and initialized provider.
- **Root cause:** `MemoryProvider`'s contract methods (`upsert`/`search`/`delete`) had
  **zero call sites in `src/`**. Boot called `initialize()` then immediately unwrapped
  the provider with `vault = _provider.vault if isinstance(_provider,
  ChromaMemoryProvider) else None` (`gateway/orchestrator.py`, duplicated in
  `gateway/shared_services.py`) and used the raw `MemoryVault` for everything. The two
  non-Chroma providers have no `.vault`, so the unwrap yielded `None` and
  `memory.set_vault(None)` disabled the entire vault-facing surface. The seam existed
  as a type, never as a call path.
- **Fix:** Deleted the ABC and its three implementations; boot constructs `MemoryVault`
  directly and `fts5_only` is selected by an explicit `if`. `MemoryBackend` narrowed to
  the values that actually work.
- **Avoid:** an interface with no call sites is not a seam — it is a comment with a
  type annotation. Before adding an abstraction "for future backends", write the call
  site that would use it. If you cannot, do not add it.
- **Locked by:** `tests/test_memory_backend_honesty.py` — `test_every_declared_backend_produces_a_working_memory_or_is_not_declared`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3 — read this before writing any test here:** never `patch.dict(sys.modules)`
  over `chromadb`. `conftest.py` warms the chromadb PyO3 native module at import so it
  loads exactly once per process; `patch.dict` drops it and every later chromadb test in
  the process dies with *"cannot load module more than once"*. If you want to test the
  non-Chroma path, use `backend="fts5_only"` against `tmp_path` — do **not** simulate a
  missing chromadb.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. `shared_services.py`
  is one of the two files you are editing; do not add a `ProcessSharedServices.instance()`
  call into the construction path you are simplifying.
- **`_config_fingerprint` will hide your change on a hot reload.**
  `gateway/shared_services.py:52-63` keys the shared-services cache on
  `brain_dir|backend|graph` only. Changing `recall_distance_max` /
  `core_memory_max_entries` / `decay_half_life_days` does **not** produce a new
  instance, so a settings change is invisible until process restart. This is
  [T-06](T-06-memory-settings-reach-vault.md)'s territory — do not fix it here, but do
  not be fooled by it when you test.
- **Two construction sites must stay in sync.** `gateway/orchestrator.py:3011-3046` and
  `gateway/shared_services.py:296-307` build the same thing two different ways today
  (the orchestrator additionally reuses `_shared.vault` when present, `:3022-3024`).
  Whatever you do to one, do to the other — or better, have the orchestrator call the
  helper you extract for §7's `_build_memory_for`.
- **`vault.is_shared = True`** (`shared_services.py:307`) is load-bearing: it stops an
  individual `AgentSession` from closing the process-shared Chroma client on shutdown.
  Preserve it exactly, including the comment above it.
- **The three-settings forwarding is real behaviour inside a file you are deleting.**
  `ChromaMemoryProvider.initialize` (`memory_provider.py:113-144`) conditionally builds
  a kwargs dict so `None` means "keep the MemoryVault default". Reproduce that
  conditional exactly — passing `None` straight through changes the vault's defaults.
