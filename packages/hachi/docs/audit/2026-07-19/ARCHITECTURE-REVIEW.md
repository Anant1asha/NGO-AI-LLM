# Hachi — Principal Architecture Review

**Date:** 2026-07-19 · **Scope:** full repository at `main` (bd24afe) · **Method:** seven parallel deep-read audits (core engine/AI, gateway/API, memory/data-flow, config/secrets, extension model, CLI/TUI edges, frontend/repo hygiene) plus cross-cutting analysis (churn, CI, tests, decision hygiene). Every P0/P1 claim below was re-verified against source by the lead reviewer; where docs and code disagree, the code is reported.

**Measured baseline:** ~85K lines of Python across 236 files; ~42K lines of TS in `frontend/`; 309 test files (~77K lines); 87 REST paths / 100 operations; ~60 first-party tools; 82 `HACHI_*` env vars; 344 commits by effectively 2 contributors since April.

---

## Executive Summary

| Dimension | Score |
|---|---|
| **Overall Architecture** | **5.5 / 10** |
| **Production Readiness** | **~55%** (for the stated single-tenant, local-first v1) |
| **Maintainability** | **4 / 10** |
| **Scalability** | **5 / 10** (adequate for stated single-tenant scope; documented cliffs beyond it) |
| **Developer Experience** | **6 / 10** (carried by a top-decile engineering system; dragged by god modules) |
| **Complexity** (10 = essential only) | **4 / 10** (high accidental complexity: parallel generations of the same concept) |
| **Recommendation** | **Approve with changes** |

**The one-paragraph verdict.** Hachi has an unusually good architectural *skeleton* — mechanically enforced layering with honestly-frozen debt seams, a genuine LLM-provider seam (five providers added with zero loop changes), a frozen per-turn context that is actually frozen, real security engineering at the edges, and an engineering system (3-OS CI, deterministic eval-replay gate, bug bank, two-tier ADRs) that most seed-stage teams never build. But the *body* contradicts the skeleton in three load-bearing ways: (1) the product's actual backend is a 2,358-line class inside the CLI module, making the gateway a hollow shell of ~75 injected callables and forcing the engine to import CLI privates; (2) a systemic `except Exception: pass` idiom has produced a verified epidemic of **shipped features that are dead in production while reporting success** — at least eight, including the pack store, memory tuning, the memory gardener, and background fact extraction for any non-env-key user; and (3) the governance surface — the product's stated moat — is the *least* trustworthy subsystem: approvals bypass the app's own layering, the API fabricates expiries the backend doesn't honor, the UIs drop failed denials silently and substitute fabricated data on error, and two whole entry paths (channels, schedules) boot outside governance entirely. None of this requires a rewrite; nearly all of it is mechanical extraction, deletion of parallel implementations, and replacing silent failure with loud failure. That is exactly what "approve with changes" means.

---

## Strengths

These are genuinely well designed, verified in code:

1. **Enforced layering with honest debt.** `import-linter` runs blocking in CI with three contracts; the five known engine→gateway inversions are *frozen, commented allowlist entries* that error when fixed (self-cleaning). This is how you rail architecture: mechanically, with visible debt instead of hidden drift (`pyproject.toml:174–237`).
2. **The LLM provider seam is real.** The loop touches only `generate_stream`/`model`; OpenAI-compat, Ollama, Groq, Gemini, DeepSeek were all added with zero `loop.py` changes. The generator-with-return streaming contract is unusual but consistently honored, including the subtle `yield from` return-value handling in the resilience wrapper (`resilience.py:429–441`).
3. **`TurnContext` is what it claims.** `@dataclass(frozen=True, slots=True)`, composed once, restored in `finally`. The cacheable/dynamic prompt split is cache-literate for both Anthropic breakpoints and OpenAI prefix caching (`llm.py:277–346, 564–570`).
4. **Routing config vs logic separation.** Data (`ModelDescriptor` JSON registry, immutable `RoutingSnapshot`) is cleanly separate from the pure `ModelRouter.select()`; hot-reload is a per-session pull-at-turn-boundary version check — no cross-session mutation (`loop.py:576–599`).
5. **Security engineering at the boundaries.** Fail-closed gateway auth (NO_AUTH only on loopback, token required off-loopback, constant-time compare); `rest_adapter.py` is defense-in-depth done right (DNS-pinned SSRF guard with Host/SNI preservation, fail-closed allowlist, outbound secret redaction, no redirects, documented); `guard_untrusted` wraps every MCP result; sub-agent registries are genuinely scope-filtered security boundaries (`delegation_tools.py:211`); the `.ogpack` format has a real consent model (scope vocabulary, widening-diff re-consent, sha256, hardened extraction).
6. **The engineering system is top-decile for a project this age.** 3-OS CI matrix; a deterministic eval-replay gate that drives the *real* `ExecutionLoop` with a scripted LLM and blocks merges; `scripts/preflight.py` mirroring CI with blocking/advisory split; `docs/bug-bank.md` regression law; 2,854-line decision log + 5 numbered ADRs + an ADR linter.
7. **Well-built infrastructure internals.** Jobs queue (compare-and-set claims, dead-letter vs structural-failure distinction, crash recovery); scheduler (cross-process file lock, atomic replace, collapse-to-one missed-run semantics); session store (deferred batched commits, ingress idempotency, online hot backup); compaction (tool-pair-safe boundaries, lock-scoped mutation, bounded passes).
8. **Frontend foundation layer and discipline.** `client.ts`/`sse.ts` are small and correct (typed errors, incremental SSE parsing, idle-timeout zombie protection); *zero* whole-store subscriptions (measured); *zero* direct API calls from route files (measured); a deliberate right-sized SWR cache instead of a heavy dependency.
9. **The TUI honors the REST-only decision** — verified by import scan; the legacy TUI was actually deleted; the cockpit connects over HTTP/SSE with a real token. `client/` vs `sdk/` is deliberate separation (REST consumer vs semver'd pack-author facade), not duplication.
10. **Declarative boot registration where it exists.** `ToolRegistrar` with topological `after`/`last` constraints and cycle detection replaced ordering-by-comment; the connector registry is genuinely open/closed for OAuth credential UIs ("add an entry — nothing else changes" is true).

---

## Critical Findings

> Severity: P0 = must fix before any public v1; P1 = serious, fix in the v1 window; P2 = moderate; P3 = minor. Confidence reflects direct code verification.

### CF-1 · Silent-degradation idiom → a dead-feature epidemic
**Severity:** P0 · **Confidence:** High (each instance verified in code; three re-verified independently by the lead reviewer)
**Evidence:** At least **eight shipped features are inert in production while reporting success**, all hidden by `except Exception: pass`/`getattr(..., None)`/unreachable-branch patterns:
1. **Pack store (kennel):** `cli/main.py:2232` imports `hachi.og_engine.bundled_packs.list_bundled_packs` — module doesn't exist anywhere; `ImportError` swallowed; `add_skill_from_kennel` returns hardcoded `{"ok": True, "installed": True}` while installing nothing (`cli/main.py:2279–2291`).
2. **Routing cost warnings:** `routing/validate.py:80` calls `costly_capability_warnings()` missing its required `registry` arg — a guaranteed `TypeError` swallowed on every call since inception.
3. **`[memory]` settings, incl. M2 decay:** the settings-passing vault branch is unreachable once the shared vault exists (`orchestrator.py:3022–3038`), which is always on the standard path — `recall_distance_max`, `core_memory_max_entries`, `decay_half_life_days` are silently ignored; the code comment claims the opposite.
4. **`[eval_reports]`:** the settings model exists but was never registered as a `ResolvedConfig` field; the section is stripped before boot and the loader *warns the user their key is unknown* (`settings.py:246–268` vs `:428–462`).
5. **MemoryGardener:** zero production call sites; the UI's Memory-Diff surface reads a file (`pending_diffs.json`) that is never written (`orchestrator.py:745–756`).
6. **`file.extracted` events:** `job_handlers.py:435` imports `_shared` from the orchestrator — which has no such module global — always fails, is swallowed, and publishes into a freshly-constructed subscriber-less `EventBus()`.
7. **`ProcessSharedServices.session_store`:** read via `getattr` in three places (`fastapi_app.py:431,1019`, `core/cost.py:106`), assigned **nowhere** in `src/` (verified by grep) — every "prefer shared store" branch is dead; fresh SQLite connections open on the hot message path instead.
8. **Auto-memory for non-env-key users:** `memory.py:222` / `memory_vault.py:297` gate background fact extraction on the literal `ANTHROPIC_API_KEY` env var, bypassing the secret-store/config resolution the chat path uses; when skipped, the job is marked **COMPLETED**, so the promised "failures visible in jobs/failed" is false for this entire class.

Two more *documented behaviors that don't exist*: the per-call LLM timeout (CF-7) and the pre-flight token ceiling under routing (`ResilientClient` doesn't forward `max_tokens`, `loop.py:754`). Plus two provider kinds (`gemini`, `chatgpt-web`) implemented in the client factory but rejected by the config schema, so the documented config for them crashes validation (`llm.py:896–938` vs `settings.py:8–10`).
**Why this matters:** This is the single most important finding, and it is architectural, not incidental: ~4,100 tests pass while the product ships broken promises, which means **tests verify units, not wiring**, and the failure-handling idiom guarantees you find out from users, never from the system. For a product whose pitch is *honest, verifiable agent governance*, an engineering culture of "report success, degrade silently" is a direct thesis contradiction.
**Root cause:** Blanket `except Exception` at feature boundaries + `getattr` defaults masking absent wiring + no boot-time liveness assertions; high-velocity AI-agent-driven development that lands features without an end-to-end activation check.
**Recommended solution:** (a) Replace the ~10 identified swallow sites with `logger.warning` + runtime events; (b) add a **feature-liveness boot smoke** (a preflight/CI check that boots a real session and asserts: kennel manifests load, routing validation returns warnings for a costly override, vault carries the configured settings, gardener schedule exists or the surface is removed, `file.extracted` reaches the shared bus, shared `session_store` is populated, extraction runs without the env var when a vaulted key exists); (c) adopt a rule: *a `getattr(x, "field", None)` against your own types is a lint error*.
**Tradeoffs:** Louder failure means some currently-hidden breakage becomes visible to users; that is the point.
**Engineering impact:** ~1–2 weeks for the sites + smoke harness. **User impact:** Pack store, memory tuning, memory hygiene, and memory-for-non-Anthropic-setups start actually working; several "why does nothing happen" bug classes disappear.

### CF-2 · The product backend lives inside the CLI; the service layer is a hollow shell
**Severity:** P1 · **Confidence:** High (verified by two independent audits + lead review)
**Evidence:** `_InProcessGatewayRuntime` spans `cli/main.py:244–2601` — **2,358 lines, 85 methods, 43% of the file** — implementing sessions/locking, transcript rehydration, MCP admin, spend aggregation, authoring, routing admin, memory CRUD, secrets. `GatewayControlPlane` (`control_plane.py:88–169`) takes **~75 optional callables** and contains almost no behavior; `cli/main.py:2950–3045` wires ~80 callbacks into it. Consequently `core/runtime/resume.py:124` imports `hachi.cli.main`, reads the module global `_ACTIVE_RUNTIME`, and touches private `_agents`/`_agents_lock` — the frozen import-linter seam.
**Why this matters:** Layering is inverted in spirit while green in letter: a standalone gateway is impossible; the web UI, TUI, and `hachi serve` all transit the CLI module; every backend change edits a 5.5K-line file (also the highest-churn file in the repo — ~93 touches since April); each new endpoint touches four places (runtime method, control-plane param, delegate, CLI wiring). This is the primary contributor-scalability bottleneck.
**Root cause:** The gateway grew endpoint-by-endpoint around an in-process bridge that was never moved out of the file it started in; the "handler bag" is dependency inversion taken past the point of meaning.
**Recommended solution:** Extract `_InProcessGatewayRuntime` + control-plane builder into `gateway/runtime.py` (verbatim first — mechanical, ~zero behavior change), define a small `SessionRuntime` protocol in `core` (get_live_session/rehydrate), collapse the 75 callables into 3–4 grouped interfaces (sessions, events, config, admin), delete the `core→cli` seam and its linter exemption.
**Tradeoffs:** A large diff with merge-conflict risk against in-flight work; do it as a dedicated, feature-frozen change.
**Engineering impact:** ~1 week extraction + 1 week interface grouping. **User impact:** None directly; unlocks embedding, faster iteration, and honest layering.

### CF-3 · `settings.example.toml` is invalid TOML — the canonical config reference cannot be used
**Severity:** P0 · **Confidence:** High (re-verified: `tomllib` fails at line 122 col 22)
**Evidence:** Ten `= null` lines (TOML has no null). A user who copies the file as its own header instructs hits the loader's malformed-file path (`config_loader.py:131`): the app **keeps running on built-in defaults** with only a log-line warning — their entire config silently discarded.
**Why this matters:** First-run onboarding is the one flow a v1 cannot fumble; combined with the silent fallback it produces "I configured X and nothing changed" across every setting at once.
**Root cause:** Pydantic `None` semantics transliterated into TOML; nothing in CI parses the example.
**Recommended solution:** Comment out null-valued lines; add a trivial test: `tomllib.loads(example)` succeeds **and** parsed keys ⊆ `ResolvedConfig.model_fields` (this also catches CF-1 #4-class drift permanently).
**Tradeoffs:** None. **Engineering impact:** <1 day. **User impact:** Config actually applies for new users.

### CF-4 · The governance chain — the product's moat — is untrustworthy end-to-end
**Severity:** P1 · **Confidence:** High (each link verified; several links independently found by 2+ audits)
**Evidence:** (a) The approvals REST surface is the *only* router that bypasses the control plane, calling the process-global registry directly, and it **fabricates `expiresAt = now+60s`** regardless of the real deadline (`fastapi_app.py:35,1890–1933`) — the likely root cause of the reported "approvals auto-decline ~1s after mount" defect. (b) The `permission.requested` SSE payload carries no `request_id`, so the web UI resolves in-context approvals by **fuzzy text match** — "if multiple approvals are pending the first one wins" (`approvals.ts:286–300`). (c) The UI decision path is optimistic with swallowed failure: a failed deny POST leaves the UI showing "resolved" while the gateway still blocks (`approvals.ts:201–225`), and the client **fabricates AuditEntry rows** into the same slice server truth hydrates (`store.ts:526–563`). (d) Channels and schedules boot sessions via `boot_agent()` directly (`channels/runner.py:14`, `cli/commands/schedule.py:169`), outside the gateway registry — a Telegram user's gated action parks an approval in an in-process registry **no surface can reach**, and those sessions are invisible to session/audit/spend views. (e) Both UIs substitute fiction on failure: the TUI cockpit "NEVER raises … always returns real or placeholder data" (`tui/cockpit/data.py:5-6`) so a crashed gateway renders as a healthy cockpit with plausible fake approvals/spend/audit; the web store ships scripted demo content inside production actions one boolean away (`store.ts:1155–1586`).
**Why this matters:** Every competitive document in this repo says the moat is *verifiable, owned governance/audit*. As built, an approval can expire on a fabricated timer, resolve against the wrong request, silently fail to deny, appear in an audit log the client invented, or never be reachable at all — and when the backend is down, both UIs *display fabricated governance data*. This is the gap between the pitch and the product.
**Root cause:** The approval subsystem was built UI-first against a demo, then wired to a backend that never carried the identifiers/deadlines the UI needed; entry paths multiplied without a rule that all sessions boot governed.
**Recommended solution:** One integrity pass, backend-out: add `request_id` and the real deadline to the approval SSE envelope and REST responses; route approvals through the control plane like every other surface; make UI decisions non-optimistic (or optimistic-with-rollback) and never client-fabricate audit rows; register channel/schedule sessions through the (extracted, CF-2) runtime so approvals and audit are reachable; replace placeholder-on-error with explicit DEGRADED states in both UIs.
**Tradeoffs:** Slightly worse perceived latency on approval clicks (a POST round-trip); an honest offline TUI is less demo-pretty.
**Engineering impact:** ~1–2 weeks across backend+both UIs. **User impact:** The core product promise becomes true.

### CF-5 · Contract theater: OpenAPI is generated, gated in CI — and consumed by nothing
**Severity:** P1 · **Confidence:** High (measured: zero importers)
**Evidence:** `frontend/src/lib/data/schema.d.ts` (6,001 generated lines) has **zero imports**; the real contract is 55+ hand-written `interface Gateway*` blocks across 14 domain files ("mirror Python dicts exactly" — `approvals.ts:13`). The Python `client/` hand-mirrors the *TypeScript* types (`client/models.py:1–8`) with ~40 hardcoded path strings and no schema check. The error envelope isn't in the spec at all: custom handlers return `{code,message,details}` while ~30 `HTTPException` sites return Starlette's `{"detail": …}`, and `ErrorResponse` is absent from `components.schemas`. Route grammar is inconsistent (`POST /runtime/mcp/{name}/enable` vs `PUT /schedules/{id}/enabled`; `/config/provider` vs `/config/providers`), and nothing besides the OpenAI-mimicry `/v1/*` is versioned.
**Why this matters:** The repo has already suffered the "FE wired to nonexistent routes" regression class; the CI job that supposedly prevents it diff-checks a file nothing uses. Three hand-synced contract copies multiply breakage probability with every route, and generated clients get the error shape wrong.
**Root cause:** Codegen bolted on after adapter-first development; never threaded into the type graph.
**Recommended solution:** Derive domain types from `schema.d.ts` (`components["schemas"]`, `paths[...]`) one domain at a time (start approvals/chat); add a preflight check walking `GatewayClient` paths against the exported spec; add an `HTTPException` handler mapping onto the envelope and register `ErrorResponse` as a default response; write a one-page route-grammar convention and decide versioning **before** external clients exist.
**Tradeoffs:** Generated types are uglier to consume; a thin mapping layer remains legitimate.
**Engineering impact:** ~1 week incremental. **User impact:** Fewer runtime breakages on upgrade.

### CF-6 · `boot_agent` is a 1,137-line composition function; `AgentSession` is a god class
**Severity:** P1 · **Confidence:** High
**Evidence:** `orchestrator.py:2557–3693` — 11 numbered boot steps in one closure-heavy scope; behavior differences created by **redefining `emit_runtime_event` mid-function** (`:2601`, `:2747` with `# noqa: F811`); constructor contract fiction — boot stashes `session._max_daily_cost_usd`, `_sub_agent_client`, `_browser_controller`, `_provider_registry` onto the built object (`:3467–3496`). `AgentSession` (`:507–1961`) couples the turn engine to ~25 `snapshot_*`/`query_*` UI read-model methods, live MCP admin, schedule control, and job pipelines. `orchestrator.py` is 3,694 lines with ~85 touches since April; `fastapi_app.py` is the entire 87-path REST surface in one module.
**Why this matters:** The composition root is where every feature meets; at this size each addition is O(understand-everything). Function-shadowing means the *same name does different things at different line numbers* — hostile to both humans and tooling.
**Root cause:** Incremental audit-fix accretion (each fix annotated BB-x/P4-x) with no decomposition pass; the declarative `TOOL_SPECS` table shows the intended pattern but covers only tools.
**Recommended solution:** Split boot into staged builders (permissions → providers → memory → tools → jobs → schedules) each returning typed results; move read models into a `SessionReadModels` facade over `RuntimeReadModelStore`; make stashed privates constructor args; split `fastapi_app.py` into APIRouter modules per domain.
**Tradeoffs:** Churn-heavy refactor; sequence after CF-2 to avoid double-moves.
**Engineering impact:** ~2 weeks. **User impact:** None directly; velocity and reviewability.

### CF-7 · Documented reliability that doesn't exist: no LLM timeout, three stacked retry layers
**Severity:** P1 · **Confidence:** High (re-verified)
**Evidence:** `resilience.py` documents "per-call timeout (default 60s, down from 600s)" and defines `timeout_s: float = 60.0` — **applied nowhere**; `AnthropicClient` is constructed without a timeout (`llm.py:882`), so the SDK's 600s default rules, and the loop's wall-clock deadline only checks between chunks — a hung connection defeats it. Retries stack: loop-level (`loop.py:59–62`, statuses incl. 408/409/529) × resilience-level (`resilience.py:34`, different status set, different backoff) × fallback chain — worst case ~21 provider calls and ~16s of thread-blocking sleep before an error surfaces, with two divergent "is transient" taxonomies. Cost is then attributed to the *primary* model even when a fallback served the turn (`resilience.py:347` + `loop.py:1089`), and a routing-layer boot failure silently disables routing at DEBUG level (`orchestrator.py:2955–2960`).
**Why this matters:** For an autonomous agent that runs unattended, hang behavior and honest failure surfacing are the product. Spend attribution being wrong exactly during failover corrupts the cost-governance story.
**Root cause:** The resilience layer was added around an older loop-level retry that nobody removed; `timeout_s` designed but never plumbed.
**Recommended solution:** Thread `timeout_s` into client construction (test asserts the SDK client's timeout); make resilience the *sole* retry owner with one shared `is_transient()`; add `served_model` to `LLMResponse` and prefer it in cost recording; promote routing-boot failure to WARNING + runtime event.
**Tradeoffs:** Tighter timeouts surface slow-provider errors that were previously silent waits.
**Engineering impact:** 2–3 days. **User impact:** No more 10-minute hangs; correct spend books.

### CF-8 · Event/SSE architecture: a 50ms poll over a lossy ring, with a per-connection kill switch on shared turns
**Severity:** P1 · **Confidence:** High (re-verified)
**Evidence:** Live events are an in-memory list trimmed to 2,000 (`runtime_read_models.py:250`); reconnecting clients whose cursor predates the trim are silently clamped — **no gap signal** (`:426–440`); history replay is synthesized from SQLite at message granularity, so replay fidelity ≠ live fidelity (`control_plane.py:588–649`). The SSE loop wakes on an unconditional 50ms trigger (`fastapi_app.py:1140–1146`). And **any** stream disconnect calls `control_plane.interrupt(session_id)` (`fastapi_app.py:1155–1158`) — a connection-local trigger canceling a session-global turn: closing a tab, a proxy blip, or a second viewer leaving kills generation for everyone. The bus and read model also keep **two unrelated sequence spaces**, and legacy alias events bypass the bus entirely (`orchestrator.py:2762–2765`).
**Why this matters:** The UI's realtime truthfulness (and the audit trail's completeness) sits on an at-most-once, restart-lossy, gap-blind channel; the disconnect-cancel is a user-facing correctness bug today.
**Root cause:** A read-model list reused as a transport buffer; "stop button must really stop" implemented at the wrong scope.
**Recommended solution:** Refcount streams per session and cancel only on sole-stream disconnect (or require explicit `POST /interrupt`); return `base_sequence` so clients detect gaps and refetch; feed per-connection `asyncio.Queue`s from the emitter instead of polling; longer-term, persist events to the existing SQLite substrate (see Missed Opportunities).
**Tradeoffs:** Durable events add write volume; gate by category if needed.
**Engineering impact:** Disconnect scoping + gap signal: 2–3 days. Durable log: ~1 week. **User impact:** Mid-turn tab closes stop killing runs; no more silent event holes.

### CF-9 · The OpenAI-compat facade is semantically wrong in both modes
**Severity:** P1 (if kept) · **Confidence:** High (re-verified)
**Evidence:** All client-supplied history except the last user message is discarded (`fastapi_app.py:320–335`). Non-streaming requests share **one server-side `"__default__"` session across all clients** (`control_plane.py:449,491`) — cross-client conversation bleed. Streaming mints a fresh session per request → **full `boot_agent()` per call** (LLM clients, worker threads, SQLite), leaking facade sessions toward the 100-session cap. `usage` is hardcoded zeros; the response echoes the requested model while running the configured one.
**Why this matters:** Anyone pointing an OpenAI-client tool at Hachi gets memory bleed between "stateless" calls, heavyweight boots, and false billing/usage data — a support-load magnet for a fringe surface.
**Root cause:** A stateless protocol bolted onto a session-centric runtime without deciding which semantics win.
**Recommended solution:** Decide: either demote to a non-agentic passthrough (messages[] straight to the LLM client — cheap, honest) or derive `session_key` from a stable client field, close facade sessions, report real usage from `CostTracker`, and return the real model. If neither is worth it, delete the facade.
**Tradeoffs:** Passthrough loses "agent behind an OpenAI URL" demos. **Engineering impact:** 2–4 days. **User impact:** No cross-client bleed; honest metering.

### CF-10 · The config write path persists the merged view; 13 writers, 1 lock
**Severity:** P1 · **Confidence:** High
**Evidence:** Writers call `load_effective_config()` (defaults+file+env+overrides) then `write_global_config(config)` — serializing the **merged** state back to `settings.toml` — at 13+ sites (`provider_admin.py:140→186`; `cli/main.py:724,790,840,1623,1710,4349`; `onboarding.py:526`; `fastapi_app.py:2314`; `workspace.py:137`; `config_tools.py:721–732`; …). Only `provider_admin` holds `_CONFIG_LOCK`; the other writers race (lost updates). Effect: transient env state — including `HACHI_PERMISSION_TIER` — gets **baked durably into the file** by any innocuous settings write. This is the generic mechanism behind the historical "tier reverted" bug.
**Why this matters:** Config precedence is a promise ("env overrides the file, temporarily"); this silently converts overrides into permanent state, including *security posture*.
**Root cause:** `write_global_config(ResolvedConfig)` has no notion of layer provenance; ownership per section is convention only.
**Recommended solution:** Writers read the *file layer only*, apply the mutation, write back; move the lock inside `write_global_config`. Add a regression test: set an env override, perform an unrelated settings write, assert the file doesn't contain the override.
**Tradeoffs:** None meaningful. **Engineering impact:** 2–3 days. **User impact:** Settings and safety tier stop mutating themselves.

### CF-11 · The tool platform is open/closed in name only, and the registry accepts silent clobbering
**Severity:** P2 · **Confidence:** High (double-registration re-verified)
**Evidence:** `ToolRegistry.register` overwrites `_tools[name]` and appends duplicate schemas with no guard (`loop.py:188–189`). Google tools have **two live mount paths** — `TOOL_SPECS` (with approver) and the capability loop (`orchestrator.py:3325–3352`, **no approver**) — so when both trigger, schemas duplicate (Anthropic rejects duplicate names) and gated handlers are replaced by ungated ones. Grouping metadata lives in three hand-maintained orchestrator tables that already drift: `_GROUP_BY_TOOL_NAME:258` maps a nonexistent `schedule_task`; `delegate_parallel_tasks` is misclassified into `integrations`, so unlocking the delegation group omits its parallel sibling. Tool schemas are raw dicts with no validation and no `ToolDef` model; `google_tools.py:126–127` pokes registry privates. Adding one tool touches 2–3 files including orchestrator tables.
**Why this matters:** ~60 tools and growing; every addition edits core-adjacent gateway code and nothing validates tables against reality — drift is already present.
**Root cause:** Grouping centralized instead of declared at registration; two generations of integration mounting both left live.
**Recommended solution:** `register(...)` raises on duplicate names; pass `group=` at registration and delete the tables (boot-assert any residual table references registered names); a small `ToolDef` model with jsonschema sanity-check; one mount path per integration.
**Tradeoffs:** Duplicate-raise may surface latent double-mounts immediately (good). **Engineering impact:** ~1 week. **User impact:** No approval-gate bypass; correct tool groups.

### CF-12 · Memory subsystem: 12 flat modules, a fictional swap seam, and provenance that is always empty
**Severity:** P2 · **Confidence:** High
**Evidence:** Twelve `memory*`/recall modules sit flat in `core/` with no package boundary. The `MemoryProvider` ABC has **zero production call sites** — boot unwraps `provider.vault` and everything uses raw `MemoryVault`; alternative backends set `vault=None`, i.e. "memory off", not a swap; `user_profile.py:422–480` reaches into vault privates. Facts dual-write .og + Chroma but deletes are two-store only — deleted facts **resurface** via file-based `graph_recall`, and the gardener that would reconcile is dead (CF-1). `MemoryManager._session_id` is **never assigned** — every extraction payload carries an empty session id, so the .og memory graph's provenance edges are empty (`memory.py:609`; masked by `getattr`). Two different extraction prompts write the same store with different quality gates (`memory.py:370` vs `:1461`). A conversation exists in five server-side representations with no declared owner; compaction summaries are never persisted, so resumed sessions silently have weaker context than live ones.
**Why this matters:** Memory is a headline capability; its architecture is the least coherent subsystem — write paths without read paths, seams that don't seam, and provenance (the "verifiable" story) broken at the first hop.
**Root cause:** Successive memory initiatives (vault → index → graph → gardener → provider) each added a module without consolidating; adapters built for zero-behavior-change were never adopted.
**Recommended solution:** Create `core/memory/` package; **decide** the provider seam (adopt it at call sites or delete the ABC); set `_session_id` at boot + regression test on payload; make deletes tri-store (tombstone in .og); route the flush path through `extract_facts`; persist compaction checkpoints as system rows; document SessionStore as the single durable transcript.
**Tradeoffs:** The package move is churny but mechanical. **Engineering impact:** ~1–2 weeks. **User impact:** Forget actually forgets; provenance real; resume fidelity matches live.

### CF-13 · Storage sprawl: ~10 persistent stores, 3 Chroma roots, two platformdirs identities, no schema versioning
**Severity:** P2 · **Confidence:** High
**Evidence:** sessions.db, jobs.db, memory_index.db, files.db, runs.db (in *data_dir* unlike siblings), tui_state.db, chroma_vault (6 collections), an attachments PersistentClient rooted *inside* the first client's directory, opt-in embedding store, plus schedules.json/checkpoints/skill_usage.json/.og files. `jobs.db` resolves under `PlatformDirs("hachi","opengigantic")` while everything else uses `PlatformDirs("hachi", appauthor=False)` — **two separate on-disk roots on Windows**, invisible to backup/doctor/export tooling built on `get_hachi_paths()`. No `schema_version` table anywhere; `core/migrations.py` (additive-only) is used by 2 of 6 SQLite stores; a single turn commits to four stores with no cross-store transaction.
**Why this matters:** The product sells *portable, owned* data; today "your data" is ten locations across two roots with no versioned migration story — future upgrades and the export/backup promise both get harder every month this persists.
**Root cause:** Every initiative added its own store; `_default_db_path()` predates paths consolidation.
**Recommended solution:** Point jobs.db at `state_dir` with a move-if-exists migration (1 day, do now); add `schema_version` serviced by `migrations.py` everywhere; plan consolidation to one state SQLite + Chroma + blobs.
**Tradeoffs:** Consolidation is a real migration; the two quick fixes aren't. **Engineering impact:** Quick fixes 2 days; consolidation ~2 weeks later. **User impact:** Backup/export that actually captures everything.

### CF-14 · Parallel implementations of the same concept, everywhere
**Severity:** P2 · **Confidence:** High
**Evidence:** **Three pack ecosystems** (og_pack/`pack.toml` with consent+sha256; community_packs/`pack.json` with neither; skill_packs/`manifest.json`) — `hachi skill install user/repo` bypasses the entire consent/scope machinery the product built. **Two OAuth stacks** (`core/oauth.py` loopback flow vs `integrations/oauth_flow.py` connector flow) with token exchange/refresh implemented twice and a fallback key-read bridging them. **Three declarative-integration mechanisms** (legacy `IntegrationRuntime` with plaintext creds in .og env nodes and `print()` errors; native integrations; `UniversalRestAdapter`). **Two exception systems** (`errors.py` taxonomy vs loop-local `AgentException` + string-prefix outcomes — `run()` encodes eight outcomes in string prefixes). **Twin contract types** (`SearchResult`/`SearchProvider`/`ProviderHealth` each defined twice, passing isinstance by structural luck).
**Why this matters:** Every duplicated concept doubles the learning surface, splits fixes, and creates behavior asymmetries (consent enforced on one install path and not the other is a *security* asymmetry, not just hygiene).
**Root cause:** Generational layering under velocity — new implementations added beside old ones, old ones never retired.
**Recommended solution:** Declare canonical per concept and reduce the others to adapters or delete: og_pack canonical (community_packs becomes a fetcher producing an ogpack dir); oauth_flow primitives canonical; RestAdapter canonical (fold/deprecate IntegrationRuntime); migrate loop sentinels under `HachiError` or a `TurnOutcome` object; delete twin types.
**Tradeoffs:** Some breakage risk in rarely-used paths; staged deprecation. **Engineering impact:** ~2 weeks across items. **User impact:** Consent applies to every install path.

### CF-15 · Single-tenant by decision, half multi-principal by implementation
**Severity:** P2 · **Confidence:** High
**Evidence:** Exactly one bearer token exists per process (`fastapi_app.py:592`), so the C1 ownership machinery (per-owner hashes, 403 paths, per-principal rate keys) can never discriminate — dead ceremony. Enforcement is also inconsistent: `GET /sessions/{id}/messages` skips the ownership check its sibling routes perform (`fastapi_app.py:1036–1067`); the owner map is in-memory and lost on restart; token rotation would orphan owned sessions.
**Why this matters:** It's the worst middle state: complexity without capability, plus a trap — the day a second token appears, the unchecked route and volatile owner map become real holes.
**Root cause:** Audit findings implemented locally without an authz decision.
**Recommended solution:** Write the ADR and pick: delete C1 (honest single-principal) or finish it (persisted owners, token identities, uniform enforcement incl. `/messages`). Either is fine; the middle isn't.
**Tradeoffs:** Deleting feels like losing work; keeping half is worse. **Engineering impact:** 2–4 days either way. **User impact:** None today; removes a future breach class.

### CF-16 · Frontend state architecture: one 1,807-line store, an untyped hydrate hatch, and a module-state kernel
**Severity:** P2 · **Confidence:** High
**Evidence:** One flat zustand store: ~95 fields, ~85 actions, ~16 unrelated concerns; `hydrate: (patch) => set(patch)` lets any caller overwrite any field; ~20 actions fork on `dataMode === "live"` with scripted demo fiction in the mock branches; `fixtures.ts` statically imported into the prod bundle. `chat.ts` (1,593 lines) is a runtime kernel on ~18 module-level mutable variables with reset logic duplicated in four places — invisible to devtools and the store. Comments claim "no cycle because store.ts never statically imports chat.ts" while `store.ts:10–17` does exactly that. UI types are prototype-derived (`Approval.id: number` vs gateway string ids) forcing a translation map whose miss path **silently skips the decision POST**. Route files: 2,187/1,472/1,283/1,214 lines with exactly one route-level test; 25 test files vs 101 sources.
**Why this matters:** The store is the top-churn frontend file; no ownership boundaries means the SSE handler, 20 loaders, and UI actions race one namespace — the breeding ground of the "stale slice" bug class already seen.
**Root cause:** Direct port of the prototype's single logic object; mock mode was the original app.
**Recommended solution:** Split into typed slices with per-domain hydrate; move mock/live behind the data layer (mock adapters, lazy fixtures); extract `sessionRef`/`streamBuffers`/`costMeter` from chat.ts with a single `reset()`; migrate ids to strings; fix or delete the false cycle comments and add `import/no-cycle`; render smoke tests for the four big screens before splitting them.
**Tradeoffs:** Mechanical but wide; do slice-by-slice. **Engineering impact:** ~1–2 weeks. **User impact:** Fewer cross-session bleed/stale-pane bugs.

### CF-17 · Codebase governance drift: the rules the repo enforces on others, it breaks itself
**Severity:** P2 · **Confidence:** High
**Evidence:** A `TOKOBOROS_*` env shim runs at CLI import (`cli/main.py:151–184`) despite the repo-level ban ("explicitly removed; do not reintroduce") — reintroduced post-purge by a later commit. `core/llm.py:67–69` reads `.env` from CWD, bypassing the `HACHI_DISABLE_DOTENV_AUTOLOAD` gate that BB-2 says confines dotenv to the CLI edge. `job_handlers.py:435` attempts an engine→gateway import inside try/except — escaping import-linter because it's runtime, not import-time. `[tool.mypy] strict = true` is aspirational: ~483 errors across 64 files, with the blocking gate covering only 48 clean files — and the *engine's most load-bearing seam* (`resume.py`'s CLI reach) carries `type: ignore`. CI comments address fictional "owning teams" ("owned by other agents this session") — agent-authored comments drifting from a 2-person reality.
**Why this matters:** Guardrails only work if they bind the guardian. Each tolerated exception teaches the next contributor (human or agent) that the walls are decorative.
**Root cause:** High-velocity multi-agent development without a "rules apply to me" checkpoint; bans not mechanized.
**Recommended solution:** Delete the shim; honor the dotenv gate in `_resolve_api_key` (or delete the CWD fallback); fix the job-handler import to use `ProcessSharedServices.instance()`; add a `tokoboros` grep to preflight; schedule the mypy burn-down (64 files is finite); sweep comments addressed to nonexistent teams.
**Tradeoffs:** None. **Engineering impact:** 2–3 days + ongoing mypy ratchet. **User impact:** Indirect but real: guardrail integrity is regression prevention.

### CF-18 · Test suite organization mismatches its own importance
**Severity:** P2 · **Confidence:** High
**Evidence:** 309 test files **flat** in `tests/`, many named for remediation batches (`test_backend_fixes_issues.py`, `test_memory_fixes.py`, `test_b10_episodic_recall_offload.py`) rather than subjects — finding "the tests for module X" is archaeology. The suite must run **sequentially** because wall-clock timing tests starve under parallel workers (`preflight.py` docstring) — a hard ceiling on gate latency that worsens with every test added. And CF-1 demonstrates the deeper gap: thousands of unit tests, near-zero wiring/liveness assertions.
**Why this matters:** The suite is the project's contract (its words); at 4,100+ tests growing under agent-velocity, sequential-only + unfindable-by-subject + wiring-blind is a scaling wall for both CI time and confidence.
**Root cause:** Tests accreted per fix-batch; timing-based tests instead of injected clocks.
**Recommended solution:** Mirror `src/` structure under `tests/` (mechanical moves); rename batch-files by subject as touched; convert wall-clock tests to injected-clock so `-n auto` works; add the CF-1 feature-liveness smoke as a first-class suite.
**Tradeoffs:** Churny renames pollute blame briefly. **Engineering impact:** ~1 week spread out. **User impact:** Indirect: faster, more trustworthy gate.

### CF-19 · The `.og` spec omits the format's executable surface; the engine class is a god object with environment coupling
**Severity:** P2 · **Confidence:** High
**Evidence:** The parser and runtime execute `::api`, `::tool`, `::config`, and node roles `env`/`integration`/`mcp` (`parser.py:616–620`; `integrations.py:49/81`; `mcp_client.py:1531`) — `docs/reference/objectgraph-spec.md` contains **zero occurrences** of any of them. So the most security-sensitive .og capability (skills that declare credentials, REST APIs, and MCP servers) is invisible to pack authors and *unauditable against the spec*. `SkillEngine` is one ~1,550-line class mixing search, lint, usage persistence, authoring, analytics, and an embedded chromadb client, with `get_hachi_paths()` called in `__init__` — the "pure library" passes import-linter but can't be embedded without a Hachi home directory.
**Why this matters:** The .og format is the stated moat; a moat whose executable semantics are undocumented can't build an ecosystem, and third-party review of malicious packs is impossible against an incomplete spec.
**Root cause:** Spec tracks the knowledge format; runtime tags accreted in code only. Engine features bolted onto the one class the moat lives in.
**Recommended solution:** Add a "runtime/integration tags" spec section (or mark the tags internal and lint against them in community packs); extract `UsageTracker`/`SkillAuthor`/`EmbeddingRanker` collaborators and inject the usage path.
**Tradeoffs:** Documenting the surface commits you to it — decide deliberately. **Engineering impact:** Spec ~2 days; engine split ~1 week. **User impact:** Pack authors can target (and reviewers can audit) the real format.

### CF-20 · Repository hygiene: design-tool sediment camouflaged by blanket ignores
**Severity:** P3 · **Confidence:** High
**Evidence:** ~52MB of untracked design trees at root (`.ds-sync/` alone 45MB **including a node_modules with esbuild/playwright binaries**) kept out of `git status` only because `.gitignore` globally ignores `*.html`/`*.png` — which also traps any future tracked HTML (single exception: `frontend/index.html`). `design-system/` (65 files incl. tool prompts) is tracked and duplicates frontend primitives that are *ahead* of it. `dist/` holds a stale 31MB sdist. `frontend/.tanstack/` pollutes status. The root `hachi` bash shim hardcodes the Windows `.venv/Scripts/` layout (broken on POSIX). Dated audit snapshots regrow in `docs/audit/` (the 2026-06-27 cleanup already deleted 57 once). The base wheel ships every edge (Typer+Textual+FastAPI+ChromaDB) while `memory`/`local-models` extras duplicate base deps — cosmetic extras.
**Why this matters:** Root noise is an onboarding tax and an accidental-commit risk; the `*.html` global is a standing trap; cosmetic extras misrepresent the install surface.
**Recommended solution:** Ignore each design dir by name and narrow the globals; move design exports out of the product repo; delete `dist/`; fix or drop the shims; adopt a docs/audit retention rule; either make extras real (move fastapi/uvicorn/textual/chromadb behind extras) or delete the duplicated extras.
**Tradeoffs:** Splitting deps into real extras changes install UX — decide once. **Engineering impact:** 1–2 days. **User impact:** Cleaner clones, honest install.

---

## Architectural Risks (if nothing changes)

1. **Trust decay from the silent-failure culture (CF-1/CF-4).** The pattern that shipped eight dead features will ship the next eight. Users of a *governance* product forgive missing features; they don't forgive fabricated success. This is existential for the thesis, not cosmetic.
2. **The CLI monolith becomes the permanent center of gravity (CF-2/CF-6).** Churn data already shows every feature landing in the same three files. At 2× the feature count, merge conflicts, review latency, and onboarding cost compound; at the first additional full-time contributor, this is where they collide.
3. **Contract drift accelerates with surface area (CF-5).** 87 paths × 3 hand-synced copies × agent-velocity route additions = breakage probability approaching 1 per release without a consumed schema.
4. **Data-migration debt compounds (CF-13).** Every month of ten unversioned stores across two roots makes the eventual consolidation (or even a clean export feature) more expensive; "portable, owned data" quietly becomes false advertising.
5. **The eval/test gate becomes a bottleneck instead of an asset (CF-18).** Sequential-only 4,100+ tests grow toward multi-hour gates; the team will be tempted to skip the full suite — the exact behavior the project's rules exist to prevent.
6. **Bus factor + agent-drift.** Two effective contributors, heavy AI-agent authorship, and comments/state addressed to fictional teams: without periodic human-owned consolidation passes (like this one), the codebase's *self-description* diverges from reality, and agents trained on its comments amplify the divergence.

## Missed Opportunities

1. **A durable event log is one table away.** The project already has excellent SQLite discipline (WAL, atomic writes, CAS job claims). Persisting runtime events to a `events` table would simultaneously fix SSE loss windows, replay fidelity, restart amnesia, *and* provide the tamper-evident audit trail the pitch promises — the single highest-leverage storage change available.
2. **The `ToolSpec`/`ToolRegistrar` pattern is the answer to its own neighborhood.** Declarative, dependency-ordered registration already exists and works; extending it to capabilities, read models, and boot stages would dissolve most of `boot_agent` without inventing anything new.
3. **The eval harness is wired for exactly the missing test class.** `hachi eval run` already drives the real loop deterministically; adding *feature-liveness* cases (CF-1's list) would make the wiring-blindness structurally impossible to regress.
4. **`sdk/` is a ready-made public API surface.** A semver'd facade already exists and is honest about internals; blessing it (and routing the Python `client/` types through generated OpenAPI models) gives a supported programmatic story almost for free.
5. **og_pack's consent model deserves to be *the* install path.** The best trust engineering in the repo (scopes, widening re-consent, sha256) currently guards the least-used of three install paths.
6. **`prompt_composer` is 80% of a prompt registry.** Consolidating the ~8 stray prompt sites into it makes prompts testable/versionable — cheap now, expensive after prompt-injection hardening starts depending on exact wording.

## Comparative Analysis

**Where Hachi exceeds the bar for its stage** (benchmarks: what strong platform teams — Stripe-, Linear-, Anthropic-like — actually do):
- *Architecture-as-mechanism:* blocking import-linter with self-cleaning frozen seams is rarer than it should be even at mature companies; most enforce layering by review folklore.
- *Deterministic agent-loop evals in CI* put it ahead of most AI products at this stage, which test prompts manually or not at all.
- *3-OS CI for a local-first product*, a written bug bank with regression law, and a two-tier ADR system with a linter are practices many Series-B teams still lack.
- *Edge security engineering* (SSRF pinning, fail-closed auth, consent-scoped packs, untrusted-content guards) is genuinely above typical for pre-v1.

**Where it falls clearly below the bar:**
- *Contract discipline:* mature platforms make the generated schema the only source of truth (Stripe's OpenAPI → every SDK). Here the schema is generated, gated, and unused — worse than not having it, because it manufactures false confidence.
- *Service decomposition:* no serious platform ships its backend inside its CLI module or a 75-callable constructor; FastAPI's own idioms (routers, dependencies) are unused in a 3,059-line route file.
- *Failure honesty:* "show fabricated data on error" and "mark skipped work COMPLETED" would fail review at any of the named companies; their idiom is loud degradation with explicit degraded-state UX.
- *Operational data model:* one versioned store with migrations is table stakes for "own your data" products; ten stores, two roots, no schema versions is prototype-grade.
- *Test taxonomy:* subject-mirroring test trees and parallel-safe suites are baseline at scale; fix-batch-named flat files are an archaeology tax.

**Net:** the *engineering system* is ahead of the product's maturity; the *implementation integrity* is behind it. That combination is actually favorable — the machinery to enforce the fixes already exists; it just hasn't been aimed at wiring and decomposition.

## Release Gate

**Would I approve this architecture for a public v1 release? — Not as it stands. Approve with changes.**

The strengths are real and the debt is tractable, but a public v1 of a *governance-and-honesty-themed* agent product cannot ship with fabricated approval expiries, silently-dropped denials, ungoverned channel sessions, a broken canonical config file, and eight dead features reporting success. Required changes, in priority order:

**Gate-blocking (do before any public v1):**
1. Fix `settings.example.toml` + CI parse/keys test (CF-3).
2. Kill the silent-degradation sites and add the feature-liveness boot smoke; fix the eight dead features or visibly remove their surfaces (CF-1).
3. Approval-integrity pass end-to-end: real `request_id` + real deadline in SSE/REST, approvals through the control plane, non-optimistic (or rollback) UI decisions, no client-fabricated audit rows, DEGRADED states instead of placeholder data in both UIs (CF-4).
4. Register channel/schedule sessions through the governed runtime — or block gated actions on those paths with an explicit error (CF-4d).
5. Plumb the LLM per-call timeout; collapse retries to the resilience layer with one transient taxonomy (CF-7).
6. Scope SSE disconnect→interrupt to sole-stream (or explicit interrupt only); add gap signaling (CF-8).
7. Fix the OpenAI facade's `"__default__"` cross-client bleed and per-request boot — or delete the facade (CF-9).
8. Config writers persist the file layer only, under the moved lock (CF-10).
9. `ToolRegistry` duplicate-name guard + single Google mount path (approver preserved) (CF-11).
10. Auto-memory: resolve the background LLM client via config/secret-store; surface `skipped:*` visibly; set session provenance (CF-1#8, CF-12).

**Required, but can land in fast-follow (pre-v1.1):**
11. Extract `_InProcessGatewayRuntime` → `gateway/runtime.py`; retire the core→cli seam behind a protocol; collapse the 75 callables into grouped interfaces (CF-2).
12. Decompose `boot_agent` into staged builders; split `fastapi_app.py` into routers; move read models off `AgentSession` (CF-6).
13. Make the generated OpenAPI schema the consumed contract (FE domains first; Python client path check; error envelope in spec) (CF-5).
14. jobs.db path unification + `schema_version` tables; storage-consolidation ADR (CF-13).
15. Canonical-per-concept consolidation: packs (consent everywhere), OAuth, declarative integrations, exceptions (CF-14).
16. Single-tenant ADR: delete or finish the ownership machinery; enforce uniformly (CF-15).
17. Frontend: store slices + mock/live behind the data layer + chat.ts extraction + string ids (CF-16).
18. Governance-drift cleanup (tokoboros shim, dotenv CWD read, engine try/except import) + mypy burn-down ratchet (CF-17).
19. Test tree mirroring `src/`, injected clocks to restore parallelism, liveness suite institutionalized (CF-18).
20. Spec the .og executable surface; split `SkillEngine` collaborators (CF-19). Repo hygiene sweep (CF-20).

Executed in that order, items 1–10 are roughly three to four focused weeks and transform the release story from "impressive demo with a credibility time bomb" to "small, honest v1" — which is the only kind of v1 this product's positioning can afford.
