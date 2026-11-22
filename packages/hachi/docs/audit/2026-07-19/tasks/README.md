# Hachi — 2026-07-19 Architecture Review · Task Pack

**77 execution-ready tasks** derived from [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md),
with every P0/P1 claim re-verified against source at `main` @ `bd24afe`.

> **Read [CORRECTIONS.md](CORRECTIONS.md) before starting anything.** Verification found
> **3 P0-class findings the review missed**, **8 refuted claims** (including one refuted
> root-cause diagnosis), and **16 corrections that change the implementation**. Working from
> the review alone will send you to fix code that never executes.

---

## For the agent picking up a task

1. Open your task file. It is self-contained — you do not need this README or the review.
2. **Re-confirm every `path:line` with Read/Grep before editing.** Anchors were verified on
   2026-07-19 and drift. Every anchor is paired with a symbol name; if the line moved, grep
   the symbol.
3. **Write the failing test first** ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). If your test
   passes before the fix, the test is wrong. Consider delegating to the `regression-guard`
   subagent, which enforces this.
4. Fix. Then run the gate and report the **real** numbers:
   ```bash
   uv run python scripts/preflight.py --quick   # inner loop
   uv run python scripts/preflight.py           # before claiming done
   ```
   Windows: if a `.exe` shim fails with OS error 4551, use `python -m pytest` / `python -m mypy` (BB-1).
5. Add the `docs/bug-bank.md` entry. Run `scope-sentinel` before committing.
6. One task = one commit. Conventional Commits (`fix:` / `feat:` / `refactor:` / `docs:` / `test:`).

> ⚠️ **If you delegate a task to subagents, read this first.** The push-lock was observed
> **not binding subagent Bash calls** during this pack's own production — two of them committed
> and pushed to `main` unasked (docs-only that time; see [CORRECTIONS.md](CORRECTIONS.md) §N8).
> Until that gap is closed: tell every subagent explicitly that it must not `git commit` or
> `git push`, and run `git log --oneline` when it returns. Do not rely on the hook to stop it.

**Every task file follows [_TEMPLATE.md](_TEMPLATE.md)** — 12 fixed sections, so §9
("Out of scope") and §12 ("Known traps") are always in the same place.

---

## Gate baseline — measured 2026-07-19 @ `bd24afe`

`uv run python scripts/preflight.py --quick` → **10 passed, 0 failed, 2 skipped**
(full `pytest` and the frontend build are skipped by `--quick`).

**All blocking checks were green before any of this work started.** So if a blocking check
fails while you are on a task, you broke it — do not assume it was already red.

**Three advisory checks were already failing.** They are informational, non-blocking, and
**pre-existing — not yours**:

| Advisory | Pre-existing state |
|---|---|
| security scan | 2 high-severity findings, incl. `capability.google.secret_ref_missing` — *"Capability 'google' is enabled without a secret_ref"* |
| `vulture` (dead code) | 7 findings, incl. `core/graph_recall.py:48` `mtime_sig`, `core/runtime/job_handlers.py:273` `event_timestamp`, `og_engine/engine.py:650` unsatisfiable ternary |
| complexity (PLR) | 90 outliers — 32 too-many-branches, 27 too-many-statements, 17 too-many-arguments, 14 too-many-returns |

Two of the `vulture` hits sit inside tasks in this pack (`job_handlers.py` →
[T-09](T-09-file-extracted-shared-bus.md); `graph_recall.py` →
[T-51](T-51-memory-delete-tri-store.md)) — worth a look while you are in the file, but do not
let them expand your diff.

**Before claiming any task done, run the FULL gate** (no `--quick`) and report the real pytest
counts. `--quick` skips the suite that catches Hachi's cross-module regressions.

---

## Start here

If you want a single ordered path rather than the full graph:

| # | Task | Why first |
|---|---|---|
| 1 | **[T-02](T-02-settings-example-toml.md)** | Trivial, zero deps, and it fixes first-run onboarding for every new user. |
| 2 | **[T-34](T-34-subagent-schedule-tool-blocklist.md)** | The **only** finding that fails **open**. ~1 hour. |
| 3 | **[T-01](T-01-approver-selection-dead-branch.md)** | Unblocks the entire governance chain. Nothing in CF-4 is observable until this lands. |
| 4 | **[T-05](T-05-routing-cost-warnings-arity.md)** + [T-26](T-26-routing-boot-failure-visible.md) + [T-27](T-27-forward-max-tokens-resilient-client.md) | Three ~1-hour fixes, batchable in one session. |
| 5 | **[T-29](T-29-sse-disconnect-scope.md)** | Best effort-to-value ratio in the pack: a live user-facing bug, ~2 hours, zero conflicting tests. |
| 6 | **[T-23](T-23-thread-llm-timeout.md)** → **[T-28](T-28-wall-clock-deadline-hung-socket.md)** | Together these are the "agent hangs forever unattended" story — see the note below. |
| 7 | The rest of Wave 1, by the dependency graph below. |

> **On T-23 + T-28.** Verification found something neither the review nor the first draft of
> CORRECTIONS.md had right: Anthropic calls carry **no timeout at all** (not the SDK's 600 s
> default — `timeout=None` is passed explicitly and `is_given(None)` is True, so the default is
> never substituted). And the loop's wall-clock deadline **cannot fire** while blocked in
> `next(gen)`. So a hung connection hangs **forever**, with no backstop. For a product whose
> pitch is unattended autonomy, treat this pair as higher priority than its P1 label suggests.

---

## Wave 1 — gate-blocking (before any public v1)

41 tasks. The review's verdict is *"approve with changes"*; these are the changes.

### The dead-feature epidemic (CF-1)

The theme: **shipped features that are inert in production while reporting success.** Every
task here has two halves — make the feature work, *and* make its failure loud next time.

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-04 · Kennel / pack store](T-04-kennel-pack-store.md) | P0 | 1d | Import points at the wrong package; `add_skill` returns hardcoded success |
| [T-05 · Routing cost-warning arity](T-05-routing-cost-warnings-arity.md) | P1 | 30m | Guaranteed `TypeError`, swallowed since inception. Smallest task in the pack |
| [T-06 · `[memory]` settings reach the vault](T-06-memory-settings-reach-vault.md) | P0 | 1d | ⚠ Neither branch delivers the settings — fix `shared_services`, not the `if` |
| [T-07 · `[eval_reports]` config section](T-07-eval-reports-config-section.md) | P1 | 2h | Loader warns the user their own documented key is unknown |
| [T-08 · MemoryGardener](T-08-memory-gardener.md) | P2 | — | 🔷 **DECISION** — wire it up or delete the surface |
| [T-09 · `file.extracted` → shared bus](T-09-file-extracted-shared-bus.md) | P1 | 3h | Imports a module global that doesn't exist; publishes to nobody |
| [T-10 · Shared `session_store`](T-10-shared-session-store.md) | P1 | 1d | Attribute never existed; leaks a SQLite connection per call on the hot path |
| [T-11 · Auto-memory key resolution](T-11-auto-memory-key-resolution.md) | P0 | 1d | Gated on a raw env var; skips marked COMPLETED. Recurrence of BB-40 |
| [T-12 · Provider kinds in schema](T-12-provider-kinds-schema.md) | P2 | 3h | 🔷 **DECISION** on `chatgpt-web` (ToS-gated) |
| [T-13 · Feature-liveness boot smoke](T-13-feature-liveness-smoke.md) | P0 | 3d | 🔑 **Keystone** — depends on T-04…T-12. Makes this class structurally unrepeatable |
| [T-14 · Ban `getattr` against own types](T-14-ban-getattr-own-types.md) | P2 | 1d | The idiom that masked at least three of the above |

### Governance — the product's stated moat (CF-4)

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-01 · Approver-selection dead branch](T-01-approver-selection-dead-branch.md) | **P0** | 2d | 🆕 **Not in the review.** Blocks T-15…T-20 |
| [T-15 · Approvals through the control plane](T-15-approvals-through-control-plane.md) | P2 | 1d | Honesty/layering cleanup — behaviourally a no-op (see CORRECTIONS R1) |
| [T-16 · Real approval deadline](T-16-approval-real-deadline.md) | P2 | 1d | Registry stores no deadline at all; needs a timestamp on `_PendingEntry` |
| [T-17 · Resolve approvals by `request_id`](T-17-fe-resolve-approvals-by-request-id.md) | P1 | 1d | Frontend-only. `approvals[0]` currently wins **unconditionally** |
| [T-18 · Surface failed decisions](T-18-fe-surface-decision-failures.md) | P1 | 1d | Two silent paths: swallowed POST error **and** skipped POST |
| [T-19 · Stop fabricating audit rows](T-19-fe-stop-fabricating-audit-rows.md) | P1 | 3h | Mostly a deletion. Recurrence of BB-87 |
| [T-20 · Govern channel/schedule sessions](T-20-govern-channel-schedule-sessions.md) | P1 | 2d | Two entry paths boot outside the registry |
| [T-21 · TUI DEGRADED state](T-21-tui-degraded-state.md) | P2 | 2d | A crashed gateway currently renders as a healthy cockpit |
| [T-22 · Fixtures out of the prod bundle](T-22-web-fixtures-out-of-prod-bundle.md) | P2 | 2d | Demo fiction ships in production; not tree-shakeable |
| [T-40 · `emit_runtime_event` closure capture](T-40-emit-runtime-event-closure-capture.md) | P1 | 4h | 🆕 **Not in the review.** **Latent** — a trap armed for T-01: the six capture sites are all permission/approval, and they go live the moment T-01 lands. Pair it with T-01 |

### Config correctness (CF-3, CF-10)

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-02 · `settings.example.toml`](T-02-settings-example-toml.md) | P0 | <1d | Canonical config reference doesn't parse. 11 live `= null` lines |
| [T-03 · Config writers persist the file layer](T-03-config-writers-file-layer-only.md) | P1 | 3d | 15 writers bake transient env state — incl. `HACHI_PERMISSION_TIER` — into the file |

### Reliability (CF-7)

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-23 · Thread the LLM timeout](T-23-thread-llm-timeout.md) | P1 | 4h | ⚠ Anthropic has **no timeout at all** — a hung connection hangs forever, not 600 s. Fix is small; defect is worse than the review states (CORRECTIONS C1) |
| [T-24 · Collapse the retry layers](T-24-collapse-retry-layers.md) | P1 | 2d | **Four** stacked layers, two divergent transient taxonomies |
| [T-25 · `served_model` cost attribution](T-25-served-model-cost-attribution.md) | P1 | 1d | Spend misattributed exactly during failover |
| [T-26 · Routing boot failure visible](T-26-routing-boot-failure-visible.md) | P2 | 1h | A working boot is currently louder than a broken one |
| [T-27 · Forward `max_tokens`](T-27-forward-max-tokens-resilient-client.md) | P2 | 1h | Enabling `[routing]` silently weakens a safety guardrail |
| [T-28 · Wall-clock deadline vs hung socket](T-28-wall-clock-deadline-hung-socket.md) | P1 | 1d | Deadline can't fire while blocked in `next(gen)` |

### Events / SSE (CF-8)

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-29 · Scope disconnect → interrupt](T-29-sse-disconnect-scope.md) | P1 | 2h | ⭐ Closing one tab kills generation for everyone |
| [T-30 · SSE gap signal](T-30-sse-gap-signal.md) | P2 | 3d | Silent clamp, no gap signal. Amends two existing tests |

### API surface (CF-5, CF-9)

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-31 · OpenAI facade](T-31-openai-facade-decision.md) | — | — | 🔷 **DECISION — product call.** Blocks T-32/T-33 |
| [T-32 · Facade session isolation](T-32-facade-session-isolation.md) | P1 | 4h | Cross-principal session sharing via `"__default__"` |
| [T-33 · Facade session lifecycle](T-33-facade-session-lifecycle.md) | P1 | 4h | Leaks toward the 100-session cap; 101st request fails permanently |
| [T-37 · Error envelope in OpenAPI](T-37-error-envelope-in-openapi.md) | P2 | 4h | Purely additive. Root cause: **zero** routes declare `responses=` |
| [T-38 · OpenAPI pilot (`og.ts`)](T-38-openapi-pilot-og-domain.md) | P2 | 1d | 6,001 generated lines with zero imports; pilot on the smallest domain |

### Tool platform (CF-11)

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-34 · Sub-agent schedule blocklist](T-34-subagent-schedule-tool-blocklist.md) | **P0** | 1h | 🆕 **Not in the review. Fails OPEN — ship first** |
| [T-35 · Google double-mount](T-35-google-double-mount.md) | P1 | 4h | ⚠ Review inverts this: it fails **closed** (availability bug) |
| [T-36 · Registry duplicate guard](T-36-tool-registry-duplicate-guard.md) | P2 | 2h | **Must land after T-35** or it hard-crashes boot for Google users |
| [T-39 · Tool groups at registration](T-39-tool-groups-at-registration.md) | P2 | 1d | Three drifting tables; `use_tools("delegation")` misses a sibling |

### Tenancy (CF-15)

| Task | P | Effort | Notes |
|---|---|---|---|
| [T-62 · `/messages` ownership check](T-62-session-messages-ownership-check.md) | P2 | 2h | Cheap; do it regardless of T-61. Not exploitable today (single token) |

---

## Wave 2 — fast-follow (pre-v1.1)

36 tasks. These are refactors and consolidations, specced with more design latitude than
Wave 1's precise bug fixes.

**Decomposition (CF-2, CF-6)** — sequence matters, see the graph below
[T-41 Extract in-process runtime](T-41-extract-in-process-runtime.md) 🔑 ·
[T-42 Retire the core→cli seam](T-42-retire-core-cli-seam.md) ·
[T-43 Collapse control-plane interfaces](T-43-collapse-control-plane-interfaces.md) ·
[T-44 `boot_agent` staged builders](T-44-boot-agent-staged-builders.md) ·
[T-45 Constructor stashes](T-45-boot-agent-constructor-stashes.md) ·
[T-46 `SessionReadModels` facade](T-46-session-read-models-facade.md) ·
[T-47 Lift routers out of the closure](T-47-lift-routers-out-of-closure.md)

**Memory & storage (CF-12, CF-13)**
[T-48 Memory package boundary](T-48-memory-package-boundary.md) ·
[T-49 Provider seam](T-49-memory-provider-seam-decision.md) 🔷 ·
[T-50 Session provenance](T-50-memory-session-provenance.md) ·
[T-51 Tri-store delete](T-51-memory-delete-tri-store.md) ·
[T-52 Compaction persistence](T-52-memory-compaction-persistence.md) ·
[T-53 `jobs.db` path unification](T-53-jobs-db-path-unification.md) ·
[T-54 `schema_version` tables](T-54-schema-version-tables.md) ·
[T-55 Backup completeness](T-55-backup-completeness.md) 🆕 **data loss**

**Canonical-per-concept (CF-14)**
[T-56 Consent on every install path](T-56-pack-consent-every-install-path.md) ·
[T-57 OAuth consolidation](T-57-oauth-consolidation.md) ·
[T-58 Declarative integrations](T-58-declarative-integrations-consolidation.md) ·
[T-59 Exception taxonomy](T-59-exception-taxonomy-unification.md) ·
[T-60 Twin contract types](T-60-twin-contract-types.md)

**Tenancy & frontend (CF-15, CF-16)**
[T-61 Single-tenant ADR](T-61-single-tenant-adr.md) 🔷 ·
[T-63 Store slices](T-63-frontend-store-slices.md) ·
[T-64 False cycle comment](T-64-frontend-fix-false-cycle-comment.md) ·
[T-65 `chat.ts` kernel extraction](T-65-chat-ts-kernel-extraction.md) ·
[T-66 Approval string ids](T-66-approval-string-ids.md)

**Guardrails, tests, spec, hygiene (CF-17…CF-20)**
[T-67 Governance-drift cleanup](T-67-governance-drift-cleanup.md) ·
[T-68 Import-linter burn-down](T-68-import-linter-exemption-burndown.md) ·
[T-69 mypy ratchet](T-69-mypy-burndown-ratchet.md) ·
[T-70 Test-tree mirroring](T-70-test-tree-mirroring.md) ·
[T-71 Injected clocks](T-71-injected-clocks-restore-parallelism.md) ·
[T-72 `.og` executable surface](T-72-og-spec-executable-surface.md) 🔷 ·
[T-73 `SkillEngine` collaborators](T-73-skill-engine-collaborators.md) ·
[T-74 Repo hygiene](T-74-repo-hygiene-sweep.md)

**Opportunities (from the review's "Missed Opportunities")** — leverage, not defects. Do not
schedule these ahead of Wave 1.
[T-75 Durable event log](T-75-durable-event-log.md) — *the review's own "highest-leverage
storage change available"; fixes SSE loss, replay fidelity, restart amnesia and the audit
trail at once* ·
[T-76 Bless `sdk/` as public surface](T-76-bless-sdk-public-surface.md) ·
[T-77 Consolidate prompts into `prompt_composer`](T-77-consolidate-prompts-into-composer.md)

---

## Dependency graph

```
T-01 ─┬─► T-15 ─► T-16
      ├─► T-17          (frontend; unobservable until T-01)
      └─► T-20

T-04 …T-12 ────────────► T-13     (liveness smoke needs the features alive)

T-31 (DECISION) ───────┬► T-32
                       └► T-33

T-35 ──► T-36                     (reversed order hard-crashes boot)

T-23 ──► T-28                     (transport timeout is the primary defence)

T-41 ─┬─► T-42                    (T-42 becomes trivial afterwards)
      └─► T-43

T-40 ──► T-45 ──► T-44            (closure fix, then stashes, then the big split)
T-35, T-39 ──────► T-44           (they edit the block T-44 restructures)

T-53 ──► T-54 ──► T-55            (settle paths, then versions, then backup)
```

**Independent — safe to run in parallel with anything:** T-02, T-05, T-14, T-18, T-19, T-21,
T-26, T-27, T-29, T-34, T-37, T-38, T-47, T-60, T-62, T-64, T-69, T-74.

---

## Collision map

Six files absorb most of this work. **Do not run two tasks against the same file
concurrently** — serialize them or accept the merge cost.

| File | Lines | Tasks touching it |
|---|---:|---|
| `gateway/orchestrator.py` | 3,694 | T-01, T-06, T-07, T-08, T-26, T-35, T-39, T-40, T-44, T-45, T-46 |
| `gateway/fastapi_app.py` | 3,059 | T-10, T-15, T-29, T-30, T-32, T-33, T-37, T-47, T-62 |
| `cli/main.py` | 5,524 | T-03, T-04, T-41, T-55, T-67 |
| `frontend/src/lib/store/store.ts` | 1,807 | T-19, T-22, T-63 |
| `core/loop.py` | 1,283 | T-24, T-27, T-28, T-36, T-59 |
| `core/llm.py` | 968 | T-12, T-23, T-25, T-67 |

Two tasks need a **dedicated feature-freeze window** because they move code the whole repo
references: **[T-41](T-41-extract-in-process-runtime.md)** (2,356 lines out of `cli/main.py`)
and **[T-70](T-70-test-tree-mirroring.md)** (~300 test files).

---

## 🔷 Decisions required

**"DECISION REQUIRED" appears in 20 specs, but only 6 need you.** Two different things wear
the same label:

- **Blocking — needs the product owner (6, listed below).** Strategy or scope calls with no
  correct default. The task does not start until answered.
- **In-spec — the implementer decides (14).** A design fork inside an otherwise well-defined
  task, always accompanied by a recommendation. **Take the recommendation and proceed** — do
  not escalate. These are: T-01, T-16, T-18, T-20, T-21, T-22, T-51, T-52, T-53, T-56, T-57,
  T-58, T-59, T-64.

The six that need you:

| Task | The question | Blocks |
|---|---|---|
| [T-31](T-31-openai-facade-decision.md) | Keep, flag, demote, or delete the OpenAI-compat facade? It is a **README-advertised** integration path with 19 tests and 4 bug-bank entries — deleting it is not the cheap option the review suggests. | T-32, T-33 |
| [T-08](T-08-memory-gardener.md) | Wire up MemoryGardener (needs a job, a route, and a screen) or delete the dead surface? | — |
| [T-12](T-12-provider-kinds-schema.md) | Legitimise `chatgpt-web` in the config schema, given it is ToS-gated behind `HACHI_UNOFFICIAL=1`? | — |
| [T-49](T-49-memory-provider-seam-decision.md) | Adopt the `MemoryProvider` seam at call sites, or delete the ABC? | — |
| [T-61](T-61-single-tenant-adr.md) | Delete the ownership machinery (honest single-principal) or finish it? The middle state is the worst option. | — |
| [T-72](T-72-og-spec-executable-surface.md) | Document `.og`'s executable tags as public surface, or mark them internal and lint against them? | — |

---

## Honest scope

The review estimates **3–4 focused weeks** for its ten gate-blocking items. That looks
optimistic against this decomposition — Wave 1 is 41 tasks, several of which
(T-03, T-13, T-20, T-24, T-30) are multi-day on their own, and two carry decision latency.
**Treat 6–8 weeks as the realistic Wave 1 range** for one focused contributor, less if the
independent tasks are parallelised.

Wave 2 is genuinely multi-month and should be scheduled against product priorities rather than
run as a block.

Effort figures in the tables are per-task estimates from the specs, not a schedule.
