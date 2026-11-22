# Hachi Cost & Token Governance — Remaining Work Plan (execution-ready)

> **For the executing session:** this is a cold-start handoff. You will NOT have the
> conversation that produced it. Everything you need is in this file. Read it top to bottom
> once, then execute phase by phase. The "Verified current-state facts" table is your map —
> but line numbers drift: **re-confirm any file:line with a quick Read/Grep before you edit
> it.** All facts here were verified against `main`-line code on **2026-06-28** (branch
> `fix/web-gui-testing-batch`).
>
> This plan was produced by auditing an earlier draft with the `plan-critic` agent and then
> **verifying the critic's claims against the source** — which caught a critic error (see
> "Corrections baked in" below). Trust this file over memory and over the earlier draft.

---

## 0. What this is and why

A prior session today (commit `fde4aaa` + the four docs in this directory) completed a
cost/token audit and shipped 8 fixes. Per-turn cost dropped sharply (see "Honest numbers"
below — **do not repeat the inflated single-figure framing**). This plan covers **only the
remaining roadmap**, scoped by the user to the **full** set:

- **#13 Hot-reload model routing** — change routing from the Web UI and have it take effect
  immediately, **no restart, no killed in-flight turns**, with validate-before-apply,
  rollback, and an audit log. *This is the flagship and the user's own lived pain.*
- **#14 Config-driven model registry** — collapse the two Python tables that hold models +
  pricing into one editable `model-registry.json`.
- **#15 Pricing validation** — verify every price against official sources; add the missing
  providers (Gemini, xAI/Grok, OpenRouter); use real dated model ids.
- **Roadmap R2–R10** — surface metrics in the Web UI, a CI cost-regression guard, per-feature
  cost attribution, and a set of heavier token optimizers (each shipped with measured
  before/after evidence).

**Locked decisions (from the user):** full roadmap scope · registry format =
`model-registry.json` · measurement = **re-measure live** (fresh API calls, before/after for
every token-changing optimization).

**Outcome target:** routing is hot-swappable with zero restart, the model/pricing data is a
single validated JSON, cost is observable per-feature and guarded in CI, and the heavy
optimizers each land with measured evidence.

**Scale:** this is multi-session work. Phases are ordered so each lands independently.
**Recommended PR grouping:** Phase 0→1→2→3 as the first set (foundation + correctness + the
user's pain), then Phase 4 (governance), then Phase 5 (optimizers). Land each phase as its own
commit/PR.

---

## Corrections baked in (why this differs from the earlier draft)

The earlier draft's Phase 3 had a **good diagnosis but a flawed mechanism**, and a critic pass
mis-verified two facts. Both are fixed here:

1. **The draft's premise was RIGHT (critic was wrong):** a Web-UI routing change *does* trigger
   a heavy reboot today. The flow is `PUT /config/routing` → `control_plane.set_routing`
   ([control_plane.py:1166](../../../src/hachi/gateway/control_plane.py)) → injected handler
   `support.set_routing` (wired at [cli/main.py:2814](../../../src/hachi/cli/main.py)) → the
   method at [cli/main.py:2336](../../../src/hachi/cli/main.py) which calls
   `provider_admin.set_routing()` (writes config) **and then `self._reload_agents()`**
   ([cli/main.py:2353](../../../src/hachi/cli/main.py)). `_reload_agents()`
   ([cli/main.py:372](../../../src/hachi/cli/main.py)) reboots live sessions → can disrupt
   in-flight turns. *(The critic only checked the module-level `provider_admin.set_routing`
   ([provider_admin.py:275](../../../src/hachi/gateway/provider_admin.py)), which is config-only,
   and wrongly concluded no reload happens. There are two `set_routing`s; the wrapper reboots.)*

2. **The draft's mechanism was UNSAFE (critic was right):** the draft proposed making one
   `ModelRouter` **process-global and shared across all sessions**, swapped via an "atomic
   pointer swap" of an immutable snapshot. But the router carries **mutable per-instance caches
   with no locks** — `self._sticky` and `self._recorders`
   ([router.py:115-159](../../../src/hachi/core/routing/router.py)) — and `select()` reads then
   writes `_sticky` while `new_turn()` does `_sticky.clear()`. Turns serialize only *within* a
   session (per-session `_chat_lock`), and parallel sub-agents exist, so a single shared router
   would be raced across threads. A snapshot of immutable *config* does nothing for those mutable
   *caches*. **This plan keeps the router per-session and swaps the snapshot in at each
   session's own turn boundary (a pull model) — no shared mutable state, no race, no reboot.**
   See Phase 3.

3. **Honest numbers (fix the framing in the deliverables):** the headline reduction is
   dominated by flipping one user's mis-set `gpt-4o` default to a cheaper model — a config fix
   (~16× on that call), **not** an engine improvement. The *engine* token trim (lazy tool
   groups) is ~1.18× (≈5,958 → 5,037 input tokens). **Report both numbers separately**; do not
   present a single blended multiple as the achievement of the optimization work.

---

## Verified current-state facts (your map — re-confirm before editing)

Verified 2026-06-28. `[seen]` = read directly this session; `[critic]` = reported by the
plan-critic's source check (trust but spot-verify).

**Cost / pricing**
- `MODEL_PRICING` dict at [cost.py:33](../../../src/hachi/core/cost.py) `[critic]`;
  `pricing_for()` at [cost.py:239](../../../src/hachi/core/cost.py) `[critic]`.
- `CostTracker._resolve_pricing` prefers the registry, falls back to `pricing_for()` —
  [cost.py:364-377](../../../src/hachi/core/cost.py) `[critic]`.
- `record_background_usage(model, usage, *, store=None)` at
  [cost.py:181](../../../src/hachi/core/cost.py) `[seen]` — used for fact extraction, durable
  titling, recall summarisation (spend that bypasses the per-session `CostTracker`).
- Opus repriced to $5/$25 (BB-27): [cost.py:37,44](../../../src/hachi/core/cost.py),
  [descriptor.py:90,108](../../../src/hachi/core/routing/descriptor.py) `[critic]`.

**Routing**
- `BUNDLED_MODEL_DEFAULTS` at
  [descriptor.py:73](../../../src/hachi/core/routing/descriptor.py) `[critic]`;
  `ModelRegistry.build()` seeds from it at
  [registry.py:114](../../../src/hachi/core/routing/registry.py) `[critic]`.
- `ModelRouter` is **per-session**, built inside `boot_agent` (~
  [orchestrator.py:2754](../../../src/hachi/gateway/orchestrator.py), `boot_agent` starts ~2404)
  `[critic]`. It is **not** on `ProcessSharedServices` (`model_router` absent from
  [shared_services.py](../../../src/hachi/gateway/shared_services.py)) `[seen]`.
- Router internals `[seen]`: `__init__` sets `self._sticky` and `self._recorders` dicts
  ([router.py:115,117](../../../src/hachi/core/routing/router.py)); `new_turn()` clears `_sticky`
  ([router.py:123-125](../../../src/hachi/core/routing/router.py)); `select()` reads-then-writes
  `_sticky` with **no lock** ([router.py:154-159](../../../src/hachi/core/routing/router.py));
  docstring says "Pure" but it mutates instance state.
- `RoutingPolicy.costly_capability_warnings()` (BB-30 boot guard, read-only) at
  [policy.py:56](../../../src/hachi/core/routing/policy.py) `[critic]`.
- `set_routing` exists in **three** places `[seen]`: module fn
  [provider_admin.py:275-304](../../../src/hachi/gateway/provider_admin.py) (config write only,
  guarded by `_CONFIG_LOCK` at line 285); the control-plane delegator
  [control_plane.py:1166](../../../src/hachi/gateway/control_plane.py); and the **handler**
  [cli/main.py:2336-2354](../../../src/hachi/cli/main.py) which writes config **and** calls
  `_reload_agents()`. The gateway wires the handler at
  [cli/main.py:2814](../../../src/hachi/cli/main.py) (`set_routing=support.set_routing`).

**Loop / turn lifecycle**
- Per-turn client captured in `_resolve_turn_client` (~
  [loop.py:480-517](../../../src/hachi/core/loop.py)), set as `self._turn_client`; `new_turn()`
  called at the top of `run()` (~loop.py:740-741); model read in `_stream_generate` (~loop.py:558,
  885, 948) `[critic]`. **In-flight turns keep their captured client for the whole ReAct loop**
  — this is what makes a turn-boundary swap safe.

**Off-turn LLM work (must be handled in Phase 3 — does NOT pass through `new_turn()`):**
- Durable session titling: [session_titler.py:112-121](../../../src/hachi/core/session_titler.py)
  `[seen]` calls `llm_client.generate(...)` on a passed-in client and records via
  `cost_tracker.record(model_id, usage)`. Invoked from the worker path (~
  [orchestrator.py:1288](../../../src/hachi/gateway/orchestrator.py)) `[critic]`.
- Fact extraction: `MemoryManager.extract_facts` (~
  [memory.py:180](../../../src/hachi/core/memory.py)) uses `self._llm_client` (set ~memory.py:548)
  and records via `record_background_usage` (called ~memory.py:175) `[critic]`.

**Infra / rails**
- `EventBus` at [event_bus.py:61](../../../src/hachi/core/event_bus.py) (has its own lock)
  `[critic]`.
- `cache_observability.py` exists (the CACHE_OBSERVABILITY deliverable — already shipped)
  `[critic]`.
- `cache_control` placement (≤4 breakpoints) [llm.py:285-308](../../../src/hachi/core/llm.py);
  OpenAI `cached_tokens` parsing [llm.py:571-577](../../../src/hachi/core/llm.py) `[critic]`.
- `HachiPaths` accessors at [paths.py:13](../../../src/hachi/core/paths.py) (`state_dir` :17,
  `config_dir`, `data_dir`, …) — use `get_hachi_paths()` (BB-5) `[critic]`.
- `write_global_config(config)` at [config_loader.py:302](../../../src/hachi/core/config_loader.py)
  `[critic]`.
- `tests/test_routing_registry.py::TestPricingParity` at lines 20-64 asserts the two pricing
  views agree — but covers only ~5 model families of ~14 `[critic]`.
- `scripts/preflight.py` runs ruff, mypy-gate, skill-lint, import-linter, `hachi eval run`,
  FULL pytest, frontend build, `check:api`; `--quick` skips full pytest + FE `[critic]`.
- import-linter contracts in [pyproject.toml:189-233](../../../pyproject.toml) forbid
  `hachi.core`/`og_engine`/`tools`/`jobs`/`integrations` → `hachi.gateway`/`cli`/`tui`. **There
  is already a `cost.py → gateway.orchestrator` exemption in `ignore_imports`
  ([pyproject.toml:243](../../../pyproject.toml)) from BB-31 — do NOT add more such holes.**

---

## Cross-cutting rules & rails (apply to EVERY phase)

- **TDD / regression law:** failing test first → fix → green. Pricing corrections in Phase 2
  are bug-shaped → add `docs/bug-bank.md` entries (next ids **BB-32+**).
- **The gate:** `uv run python scripts/preflight.py` must be GREEN before any commit/push.
  Report real counts. Windows: on the `.exe` OS-error-4551 failure, fall back to
  `python -m pytest` / `python -m mypy` (BB-1).
- **No new runtime dependencies** (CLAUDE.md Rule 3). Consequences: R4/R5 compression are
  **deterministic/heuristic, NOT LLMLingua** (torch/transformers is heavy); R8 response cache is
  **stdlib LRU+TTL, no Redis**. If ML-grade compression is later wanted, that is a separate
  dependency decision — flag it, don't build it.
- **Layering (import-linter):** `hachi.core` must not import `hachi.gateway`/`hachi.cli`/`hachi.tui`.
  The routing swap primitive + snapshot + validate live in `core/routing/` (pure). The
  load→validate→build→apply→audit *orchestration* and any enumeration of live sessions live in
  the **gateway** layer. `og_engine` stays pure. **Treat any new `core→gateway` import as a
  design failure, not an `ignore_imports` entry.**
- **OpenAPI ↔ frontend contract (BB-4):** any new/changed gateway route →
  `uv run hachi gateway-openapi --output openapi/hachi-openapi.json` then
  `npm run --prefix frontend generate:api`. Import generated TS types; don't hand-type.
- **Stay in scope:** no drive-by refactors, no repo-wide `ruff format` (the auto-format hook
  handles touched files). Don't weaken tests — when a phase changes a test's premise, *repoint*
  it to the new source of truth, don't delete it.
- **Lazy credentials / no `.env` in the core import path** (BB-2/BB-8). New config/routing code
  resolves credentials at call time. The Phase 3 swap must **not** eagerly build clients in a way
  that reads creds at import/boot.

---

## Phase 0 — Live measurement harness & re-baseline

**Goal:** a reusable tool that (a) runs a fixed query live and captures real tokens/cost, and
(b) counts assembled-prompt tokens **offline** (no API call) for the CI guard. Re-confirm the
prior baseline and produce before-numbers for the optimizers.

**Build** a committed script `scripts/measure_turn.py` (reuse existing infra, no new deps):
- Boot a minimal `ExecutionLoop` with a real client from config (`create_llm_client`), real
  `CostTracker`, real `ToolRegistry`/`MemoryManager`, and the real `brain.og` system prompt.
  Mirror `tests/test_e2e_loop.py::_make_loop()` but with a live client.
- Run the canonical query `"What is my name? My name is Aditya"`, `loop.run(max_iterations=1)`,
  then read `cost_tracker.snapshot()` + `cost_tracker.cache_metrics(...)`.
- `--live` (default OFF): hits the real provider — **spends real money, needs keys**.
  `--offline`: assembles the prompt and counts tokens with `tiktoken` (`o200k_base`) **without**
  an API call. The offline function is what the Phase 4 R3 CI guard imports.
- Write/update a machine-readable record so before/after is diffable (append rows to
  `COST_BASELINE.json`).

**Tests:** `tests/test_measure_turn.py` — offline mode is deterministic; assert the fixed-context
token count is within tolerance of the recorded baseline. **No live call in CI.**

**Measurement:** run `--live` once to reconfirm the baseline against current `main`; capture the
multi-turn `cache_hit_rate` to close roadmap **R1** (verify OpenAI auto-cache engages on turn 2+).

**Done when:** offline harness committed + green in CI; live run reproduces the baseline within
noise; R1 cache-hit confirmed and recorded in `COST_BASELINE.json`.

---

## Phase 1 — #14 Model Registry: `model-registry.json` single source of truth

**Goal:** one human-editable, version-controlled JSON is the only place model ids, capabilities,
pricing, and feature flags live. `descriptor.py:BUNDLED_MODEL_DEFAULTS` and `cost.py:MODEL_PRICING`
both derive from it. Adding a model becomes a config edit, not a code change.

**File + override:** ship `src/hachi/data/model-registry.json` as package data (**verify it is in
the `pyproject.toml` package-data / wheel includes — add a `data` include if missing, or it won't
ship**). User override merged from `config_dir/model-registry.json` via `get_hachi_paths()`
(BB-5). Bundled < user override (last-write-wins by `id`).

**Schema** (each entry — superset of today's `ModelDescriptor` + brief-requested fields):
`id, provider, display_name, capabilities[], context_window, max_output, input_per_mtok,
cached_input_per_mtok, cache_write_per_mtok, output_per_mtok, supports_prompt_caching,
supports_reasoning, supports_streaming, supports_vision, supports_tools,
supports_structured_output, status (active|deprecated|disabled), tier_rank, metadata{}`.
Today's pricing is `input/output` + `cache_read_mult`/`cache_write_mult`; **keep multipliers
derivable but also allow explicit `cached_input_per_mtok`/`cache_write_per_mtok`; the loader
computes whichever is missing.**

**Files:**
- New `src/hachi/core/routing/registry_data.py` — `load_model_registry_json()` parsing bundled +
  override JSON → `list[ModelDescriptor]`. Pure (reads only the two JSON files). Filters
  `status="disabled"` out of routing candidates; keeps `deprecated` resolvable-but-deprioritized.
- `descriptor.py`: `BUNDLED_MODEL_DEFAULTS` becomes `load_model_registry_json()` output (the
  curated Python table is replaced by JSON; the OpenAI-cache-mult loop folds into the loader).
  `Pricing`/`ModelDescriptor` gain the new optional fields.
- `cost.py`: `MODEL_PRICING` + `pricing_for()` become thin shims over the registry (keep
  signatures — `CostTracker` already prefers the registry, falls back to `pricing_for`). The
  fallback table shrinks to a tiny last-resort default.
- `registry.py`: `ModelRegistry.build()` now seeds from the JSON-sourced defaults; provider
  discovery + config overrides still layer on top.

**Tests (repoint, don't weaken — Rule 2):**
- `TestPricingParity` (test_routing_registry.py:20-64): after the collapse, **repoint** it to
  assert *both* views resolve from the JSON identically (still a real cross-check, new source).
  **Extend coverage to all ~14 entries incl. `claude-opus-4-8` and the o-series** (currently ~5).
- New `tests/test_model_registry_json.py`: JSON parses; every entry has required fields; user
  override wins; `status` filtering works; round-trip `id` lookup + longest-prefix pricing match.
- Keep `test_cost_tracking.py` pricing assertions green (they now read JSON values).

**Done when:** one JSON drives both tables; adding a model in JSON (no code) is covered by a test;
full suite green.

---

## Phase 2 — #15 Pricing validation (report + corrections)

**Goal:** every configured price verified against official sources; missing/deprecated/new models
reconciled; a documented refresh process.

**Steps:**
- **Research** official pricing for every supported provider: Anthropic, OpenAI, Google Gemini,
  xAI/Grok, OpenRouter (+ note Groq/Together/DeepSeek/Ollama as pass-through). Use
  `WebSearch`/`WebFetch`. **For Anthropic model ids + pricing use the `claude-api` skill**
  (authoritative; avoids stale memory).
- **Cross-check** each JSON entry vs official; flag deltas. Known gaps from the code: registry has
  **no Gemini, no Grok, no OpenRouter** entries and uses generic ids (`claude-opus-4`,
  `claude-sonnet-4`) rather than real dated ids (the live session model is `claude-opus-4-8`).
- **Correct** `model-registry.json` (Phase 1) with verified prices; add missing current models;
  mark deprecated ones `status="deprecated"`. **Each price correction gets a failing-test-first
  guard + a `docs/bug-bank.md` entry (BB-32+).**
- **Process:** document a lightweight "pricing refresh" procedure (re-run research, diff JSON) in
  the registry README; optionally a non-blocking CI reminder. **Do NOT auto-scrape provider
  sites** (brittle, out of scope) — flag as a future decision.

**Deliverable:** new `docs/audit/2026-06-28/PRICING_VALIDATION.md` — table of
{model, configured, official, delta, action} + missing/deprecated/new lists.

**Done when:** PRICING_VALIDATION.md committed; JSON matches official prices; corrections locked
by tests + bug-bank.

---

## Phase 3 — #13 Hot-reload model routing (FLAGSHIP — corrected mechanism)

**Goal:** change routing from the Web UI → effective **immediately, no restart, no killed
turns**, with validate-before-apply, rollback, and an audit log. **Stop using `_reload_agents()`
for routing.** (Keep `_reload_agents()` for provider/credential changes — those bake API
key/base_url into clients at boot, which a snapshot swap won't rebuild. Folding provider changes
into the snapshot too is documented follow-up, not this phase.)

### Mechanism: per-session snapshot + pull-at-turn-boundary (NOT a shared global router)

This is the key correction. The router stays **per-session**; each session adopts a new routing
config at its **own next turn boundary, on its own thread** — so no shared mutable state and no
cross-session/sub-agent race.

**Core (pure, in `core/routing/`):**
- New `core/routing/snapshot.py` — `RoutingSnapshot(registry, policy, providers, resilience,
  version, source)`, **frozen**. Bundles the immutable config the router reads (essential now
  that the registry is JSON-driven and reloadable). It does **not** include `_sticky`/`_recorders`
  (those stay per-router mutable state).
- `core/routing/router.py`: refactor so the config it reads (`registry`/`policy`/`providers`)
  comes from a single `self._snapshot` field. Add `apply_snapshot(snap)` that swaps `self._snapshot`
  and clears `self._sticky`. **`apply_snapshot` is only ever called from the session's own turn
  thread at a turn boundary** (see loop change). `_sticky`/`_recorders` remain unguarded — which is
  safe because each router is single-threaded-per-session, exactly as today.
- New `core/routing/validate.py` — pure `validate_routing(registry, policy, providers) ->
  RoutingValidationResult{ok, issues[]}`: `default_model` resolvable; every capability candidate
  resolvable/synthesizable; ≥1 usable provider; capability keys parse to `Capability`; reuse
  `policy.costly_capability_warnings()` as **warnings**. Used by BOTH the validate endpoint and the
  apply path (parity).
- New `core/routing/audit.py` — pure record builder (timestamp via an **injected clock**, not
  inline `datetime.now()`); diff old→new.

**Loop (turn-boundary adoption — pull model):**
- `ExecutionLoop` gains `_applied_routing_version: int`. In `new_turn()`/`_resolve_turn_client`
  (~[loop.py:480-517,740](../../../src/hachi/core/loop.py)), **before** capturing `self._turn_client`,
  read the process-global current routing version; if it is newer than `_applied_routing_version`,
  call `self._router.apply_snapshot(store.current_snapshot)` and update the version. An in-flight
  turn already captured its client → it finishes on the old snapshot; the **next** turn uses the
  new one. No reboot, no dropped turn.

**Gateway (orchestration + storage):**
- New `gateway/routing_store.py` — `RoutingConfigStore` holds `current_snapshot`,
  `version` (monotonic int), last-known-good snapshot, injected clock, audit path; `_CONFIG_LOCK`-
  guarded `apply` / `rollback` / `reload_from_disk`. Reads are a cheap int + reference read (lock-
  free); only writes take the lock.
- Store the `RoutingConfigStore` where every session can reach it (e.g. a new optional field on
  `ProcessSharedServices` — [shared_services.py](../../../src/hachi/gateway/shared_services.py);
  guard for `None`, BB-6). Each `ExecutionLoop` gets a reference at boot.
- `provider_admin.set_routing()` and the `cli/main.py:2336` handler: **replace the
  `_reload_agents()` call on the routing path** with `routing_store.apply(new_snapshot)` after the
  config write. Sequence: validate → backup → `write_global_config` → build snapshot →
  `store.apply` (bumps version) → audit. **Leave `_reload_agents()` in place for provider/credential
  changes.**

**Off-turn work (must be handled — do NOT leave silently stale):** durable titling
([session_titler.py:112](../../../src/hachi/core/session_titler.py)) and fact extraction
([memory.py:180](../../../src/hachi/core/memory.py)) use a boot-captured client, not the router, so
they'd keep billing the pre-swap model after a routing change. **Preferred:** have them resolve
their client from the session's router (which now adopts snapshots at turn boundaries) at call
time. **Acceptable fallback (only if scoped out explicitly):** document that background work picks
up new routing on the next session boot — but make that a *stated* decision, never a silent lag
(this is the BB-30 invisible-cost class the audit just fixed).

**Turn-boundary & lock safety:**
- Lock order: `_CONFIG_LOCK` (whole load→write→apply→audit) is the only lock on the write path;
  readers (the loop's version check, `select()`) take **no** lock → hot path stays lock-free.
  Nothing under the store's write path may call back into `provider_admin` (would re-grab
  `_CONFIG_LOCK`).
- A snapshot that fails to build a usable client must be rejected by `validate_routing` **before**
  `apply`, so no half-built snapshot is ever published. If `apply` itself fails, roll back to
  last-known-good before returning.

**Rollback (dual):** in-memory previous snapshot (instant, exact — `apply` returns it); disk
`settings.toml.bak` via a new `backup: bool = False` flag on `write_global_config`
([config_loader.py:302](../../../src/hachi/core/config_loader.py)) (default off preserves all
callers).

**Audit:** new `runtime_events.py` constants `config.routing.{changed,rejected,rolled_back}`,
emitted on the existing `EventBus` ([event_bus.py:61](../../../src/hachi/core/event_bus.py)) +
appended to a durable `state_dir/routing_audit.jsonl` (new `HachiPaths.routing_audit_log`). Flush/
fsync the append so a crash mid-swap doesn't lose the record. Reuse the existing event facility —
don't invent one.

**API + UI:**
- Endpoints in `gateway/fastapi_app.py`: `POST /config/routing/validate` (no write, always 200),
  `PUT /config/routing` (now validate→backup→write→apply→audit; **422 + issues** on invalid),
  `POST /config/routing/rollback`, `GET /config/routing/audit?limit=N`. Add `control_plane` /
  `provider_admin` methods beside the existing `set_routing`. **Regen OpenAPI + TS (BB-4).**
- Frontend: new adapters in `frontend/src/lib/data/domains/providers.ts`
  (`validateRouting`/`rollbackRouting`/`getRoutingAudit`) + a **routing-table editor** (capability
  × model matrix seeded from `getRouting()` + `listAllModels()`, Validate button rendering issues
  by `field`, Save handling 422, Rollback). **Remove any "restart to apply" hint for routing.**

**Tests:**
- `tests/test_routing_hot_reload.py`: snapshot swap visible at next turn, not mid-turn; in-flight
  turn keeps its client; `apply` returns previous + rollback restores; **N concurrent sessions +
  sub-agents calling `select`/`new_turn` while a swap happens never tears `_sticky`/`_recorders`**
  (this is the regression test for the unsafe-shared-router design — prove the per-session model
  holds); registry+policy co-swap atomically.
- `tests/test_routing_validate.py`: each validation rule.
- Extend `tests/gateway/test_routing_admin.py`: invalid → 422 + no change + no `.bak` churn; valid
  → applied + persisted + `.bak` + one audit line + one bus event; validate↔apply parity; rollback;
  audit GET; **`_reload_agents` NOT called for a routing change but STILL called for a provider
  change**; in-flight turn not killed.
- Rails: `lint-imports` green (no new `core→gateway`); OpenAPI/TS regenerated and asserted present.

**Done when:** a UI routing change applies live with no restart and no dropped turn; invalid
configs are rejected with field-level errors; rollback works; every change is audited; background
work's model behavior is defined (not silently stale); full suite + gate green.

---

## Phase 4 — Governance & observability (R10, R3, R2)

- **R10 — per-feature cost attribution.** Add a `feature: str` param to
  `CostTracker.record()` (+ a `_by_feature` accumulator + `per_feature_snapshot()`). Thread the
  label through call sites: `feature="chat"` in `loop.py`; `"titling"` in
  [session_titler.py:121](../../../src/hachi/core/session_titler.py); `"extraction"`/`"compaction"`
  in `memory.py` (and `record_background_usage` gains the same param). Surface in the `usage` event
  + `/spend`. Tests in `tests/test_cost_tracking.py`.
- **R3 — CI cost-regression guard.** New `tests/test_core_tool_cost_guard.py` importing Phase 0's
  offline token-counter: a fixed set of ~10 standard queries' assembled-prompt tokens must not grow
  >10% vs recorded baselines; plus a core-tool-schema byte budget. **Pin model + brain.og version**
  so unrelated routing config doesn't flap it. Add as a `scripts/preflight.py` step. (Note: this
  guards *token counts*, not dollar cost or cache-hit-rate — see the replay-fixture note in Risks.)
- **R2 — surface metrics in Web UI.** The `cache_metrics` + `cost.routing_warning` events already
  flow; render per-request cache hit-rate + the routing-cost warning banner + per-feature breakdown
  in the spend widget. Frontend-mostly: `frontend/src/lib/data/domains/spend.ts` + the spend
  component. **Verify the SSE event schema** before claiming "no backend work"; if a response model
  gains a field, regen OpenAPI+TS (BB-4).

**Done when:** spend is attributable by feature and visible in the UI; CI fails on >10% token
growth.

---

## Phase 5 — Heavy optimizers (each with live before/after)

Ordered by ROI ÷ risk. Each: measure before (Phase 0 harness) → implement TDD → measure after →
record in OPTIMIZATIONS_IMPLEMENTED.md. Land low-risk first.

- **R8 — response cache (stdlib, but a real correctness hazard — scope tightly or cut).**
  In-process LRU+TTL wrapping `generate()`/`generate_stream()` in `BaseLLMClient`. **Restrict to
  non-tool, non-streaming, no-recall turns only**; key on the full serialized request
  (model + system + messages + tools), **excluding** the volatile dynamic/time block; short TTL.
  Tests must prove: a tool-bearing turn is **never** served from cache; streaming isn't broken;
  cache hit records zero new spend; TTL expiry works; the dynamic block is excluded from the key.
  If this can't be made clearly safe, ship nothing and flag it.
- **R5 — tool-output compression (medium).** Wrap large tool results before they re-enter history
  (~[loop.py:1014-1090](../../../src/hachi/core/loop.py) / `memory.add_message`). Deterministic
  structured-extract / truncate-with-pointer (**NOT LLMLingua**). Complements the existing lossless
  `clear_stale_tool_results()`. Measure multi-iteration turns.
- **R9 — mid-turn budget trim (behavior change).** Before `_stream_generate()`
  (~[loop.py:887](../../../src/hachi/core/loop.py)), if projected context exceeds the per-turn
  budget, call `clear_stale_tool_results()` / trigger compaction to trim-to-fit rather than
  hard-stopping the turn. Reuses the existing caps at `_turn_budget_exceeded`.
- **R6 — LLM-summary condenser (medium; mind the circularity).** Upgrade dropped-turn handling in
  `memory.py::_sliding_window_compact()` from plain-drop to a cheap-model summary before flush;
  route via the cheapest capable model + `record_background_usage(feature="compaction")`. **Pin the
  condenser model at the turn boundary, not per-summary** — otherwise a routing hot-swap (Phase 3)
  can change condenser behavior mid-turn. Keep it async/off the hot path (it already is). **Sequence
  this AFTER Phase 3 lands.**
- **R4 — prompt compression (highest risk → A/B first).** Tighten `brain.og` (dense blocks on
  routine turns) + terser tool descriptions. **Gate on `hachi eval run`: measure token delta AND
  task-success delta on a fixed eval set before shipping.** No ML compressor / no new dep. If
  results are marginal, ship only the safe trims and flag deeper compression for a dependency
  decision.
- **R7 (tidy):** bring `core/cache_observability.py` under the mypy-strict gate. **Do not** collapse
  the pricing-parity guard to a single self-comparison while doing tidy work — keep a real
  cross-check (Rule 2).

**Done when:** each shipped optimizer has recorded before/after live numbers; no tool-use quality
regression on the eval set.

---

## Deliverables (extend the existing four; add two)

In `docs/audit/2026-06-28/`:
- **TOKEN_AUDIT_REPORT.md** — append §13/14/15 findings + Phase 0 re-baseline (incl. R1 multi-turn
  cache-hit). **Fix the headline to report both numbers** (≈16× config fix vs ≈1.18× engine trim).
- **COST_BASELINE.json** — add post-optimizer before/after rows.
- **OPTIMIZATIONS_IMPLEMENTED.md** — one entry per shipped item (R-id, files, measured impact,
  locking tests/bug-bank).
- **COST_ROADMAP.md** — move shipped R-items to "done"; keep deferred ones (ML compression,
  provider-change hot-reload) with rationale.
- **NEW PRICING_VALIDATION.md** (Phase 2).
- **NEW registry README** documenting `model-registry.json` schema + refresh process.
- CACHE_OBSERVABILITY is already shipped as `core/cache_observability.py` — reference it.

---

## Verification (end-to-end)

1. **Gate:** `uv run python scripts/preflight.py` GREEN (ruff, mypy-gate, skill-lint, import-linter,
   eval, **FULL pytest** with real counts, frontend build, check:api). Quick loop: `--quick`.
2. **Hot-reload (manual):** start the gateway/app; with a session mid-turn (a long generate),
   `PUT /config/routing` from the UI → the in-flight turn finishes on the old model, the **next**
   turn uses the new model, **no restart, no dropped turn**; submit an invalid routing → 422 with
   field errors, live routing unchanged; Rollback → restored; `GET /config/routing/audit` shows the
   entries; `routing_audit.jsonl` has matching lines. Confirm a **provider** change still reboots
   (i.e. `_reload_agents` only retired for routing).
3. **Registry:** add a fake model to `config_dir/model-registry.json` (no code change) → it appears
   in `GET /config/models/all` and is routable.
4. **Live cost (Phase 0):** `uv run python scripts/measure_turn.py --live` reproduces the baseline;
   per-feature breakdown present; `cache_hit_rate` > 0 on turn 2+.
5. **Optimizers:** offline harness shows the recorded token reductions; the CI cost guard fails on
   an intentional brain.og bloat (then revert).
6. **Rails:** `lint-imports` clean (no new `core→gateway`); OpenAPI + generated TS regenerated and
   committed (BB-4).

---

## Risks & open decisions (flagged, not silently resolved)

- **Live measurement spends real API money** and needs keys + the routing fix applied — runs are
  manual/opt-in, never in the default gate.
- **Evidence reproducibility hole:** "manual live re-measure" can't be CI-checked. R3 guards token
  counts only. **Recommended addition:** a replay-fixture cost test (canned provider responses) so
  optimization PRs are CI-verifiable for cost/cache behavior, not just token count. Decide whether
  to build it in Phase 4 or accept manual-only evidence.
- **No new runtime deps:** R4/R5 are heuristic, not LLMLingua; R8 is stdlib. A decision is needed
  only if ML-grade compression is later wanted (adds torch/transformers) — not in this plan.
- **`model-registry.json` packaging:** must be in package-data includes or it won't ship in the
  wheel — verify in `pyproject.toml`.
- **Pricing parity test** is *repointed and extended* to the JSON source, not deleted (Rule 2).
- **Provider/credential changes still reboot sessions** (`_reload_agents`) — only *routing* goes hot
  this phase; folding provider changes into the snapshot is documented follow-up.
- **Off-turn billing:** the titling/extraction model behavior on a routing swap must be an explicit
  decision (route-through vs documented lag), never a silent stale-model bill.
- **Scope is large:** land Phase 0→1→2→3 first (foundation + correctness + the user's pain), then
  Phase 4 (governance), then Phase 5 (optimizers).

---

## How to start the next session

Point the session at this file, then:
1. Report pre-existing uncommitted WIP (CLAUDE.md Rule 1) before touching anything.
2. Run `uv run python scripts/preflight.py --quick` to confirm a green starting point.
3. Begin **Phase 0**. Re-confirm the file:line references in "Verified current-state facts" as you
   reach each one (they were accurate 2026-06-28 but drift).
4. One phase = one commit/PR. Run the FULL gate before each commit and report real pass/fail counts.
