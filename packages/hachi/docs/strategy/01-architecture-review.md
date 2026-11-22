# Phase 1 — Architecture Review

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy
**Date:** 2026-06-12 · Builds on [00-recon.md](00-recon.md) (file map, test baseline, `.og` pipeline).
**Evidence markers:** ✅ direct read · Ⓐ subagent-verified (path:line cited) · ▶ executed/observed.
Two subagent claims were checked and found wrong; they are corrected here, not repeated
(`loop.py:195` re-raises tool errors so the model sees `is_error` ✅ loop.py:193–196, 539–542;
sync-`def` FastAPI routes threadpool correctly — the blocking problem is the *async* routes, §W2.2).

This document keeps the two voices separate: **§1–§5 = What I found** (observation), **§6 = What I
propose** (recommendation).

---

## 1. Executive verdict (observation)

The codebase is a *well-layered single-process agent engine with genuinely strong security seams and
observability read-models, undermined by a thread-concurrency story that is unsafe at every entry
point, an aspirational-but-absent background-work layer, no streaming, and three monolith files that
concentrate maintenance risk*. The architecture documents (CLAUDE.md, module docstrings, spec) describe
the system as ~1 release ahead of where the code actually is — "durable queue", "SvelteKit", "strict
mypy", "O(1) routing", "frontend-contract CI" are all claims the code does not currently honor.

Quality gates observed this session ▶: tests **1,357 passed / 13 skipped / 60.8 s**; `ruff check src
tests` **clean**; `mypy src --ignore-missing-imports` **386 errors in 55 files** (with
`[tool.mypy] strict = true` configured ✅ pyproject.toml:102–105 and the CI lint job
`continue-on-error` Ⓐ ci.yml:74–78).

---

## 2. Strengths (What I found)

| # | Strength | Evidence |
|---|---|---|
| S1 | **Clean core seams.** Loop ↔ memory via a narrow `ConversationMemory` Protocol + frozen `IterationState`; loop ↔ prompt via immutable `TurnContext`; prompt assembly centralized in `PromptComposer` | ✅ conversation_memory.py:9–39, turn_context.py:24–62, prompt_composer.py:1–5 |
| S2 | **Declarative, ordered tool registration.** `TOOL_SPECS` table with explicit `after=`/`last=` constraints via `ToolRegistrar` — boot order is data, not prose | ✅ orchestrator.py:1307–1432 |
| S3 | **Prompt-cache-aware design.** Cacheable/dynamic system-prompt split flows from composer → TurnContext → loop → Anthropic `cache_control` blocks (incl. tools-array breakpoint) | ✅ prompt_composer.py:98–134, loop.py:289–300, llm.py:195–214 |
| S4 | **Lazy tool loading.** Core-only tool schemas per turn; model unlocks groups via `use_tools`; `load_skill` auto-unlocks the skill's own REST tools — directly serves the token-efficiency thesis | ✅ loop.py:160–174, 513–525, orchestrator.py:175–235 |
| S5 | **Security guard stack is real, layered, and tested.** PermissionGate (blocked-paths-always-win, interpreter & wrapper-bypass blocking in lower tiers Ⓐ permissions.py:461–467, 584–603); SSRF guards with all-resolved-IP checks and no-redirects Ⓐ net_guard.py:34–74, rest_adapter.py:101–161, 305; outbound secret redaction Ⓐ secret_scanner.py:23–85; prompt-injection scoring + memory quarantine ✅ memory_vault.py:111–150, Ⓐ memory_guard.py:78–99; structural-injection escaping in the serializer ✅ serializer.py:29–40; MCP subprocess env isolation Ⓐ mcp_client.py |
| S6 | **Observability read-models.** Typed event taxonomy with legacy-alias envelopes; ring-buffered `RuntimeReadModelStore` with monotonic sequencing that feeds TUI, REST and SSE from one source | Ⓐ runtime_events.py:14–98, runtime_read_models.py:208–411, ✅ orchestrator.py:480–635 |
| S7 | **Cost discipline.** Shared `CostTracker` across orchestrator + sub-agents, per-session *and* per-turn budget caps enforced mid-loop, cache-priced | ✅ loop.py:327–360, 411–415, 469–473; Ⓐ cost.py:19–30 |
| S8 | **Reliability details in the loop.** Bounded LLM retry w/ backoff; tool_use/tool_result pair repair; safe compaction boundaries that never split pairs | ✅ loop.py:302–325, memory.py:509–556, 690–751 |
| S9 | **Provider seam + memory-backend seam.** One `BaseLLMClient` ABC with 7 provider kinds; `resolve_provider` allows ChromaDB-free operation | ✅ llm.py:105–512, orchestrator.py:1266–1279 |
| S10 | **Session persistence done sanely.** SQLite WAL + busy_timeout + idempotent ALTER migrations; resume; auto-titling on the job queue | Ⓐ session_store.py:50–107, ✅ orchestrator.py:444–474, 895–897 |
| S11 | **Test culture.** ~1,207 test functions, security-specific suites (injection guards, redaction, RBAC), an in-repo benchmark wired as a CI gate | ▶, Ⓐ Phase-0 test inventory; ci.yml:80–98 |

---

## 3. Weaknesses & debt (What I found)

### W1 — Concurrency: no entry point serializes chats to a session **(highest-severity correctness finding)**

`AgentSession.chat()` mutates shared state (`MemoryManager._history` is a plain list ✅ memory.py:87,
264) and is reachable concurrently from every surface, none of which serialize per session:

- Gateway REST: `send_message` validates and calls the chat handler directly — no per-session lock or
  queue ✅ control_plane.py:231–258. `post_message` is a sync `def` route, so FastAPI's threadpool
  will happily run two of them at once ✅ fastapi_app.py:299–301.
- Channels: the runner's lock protects only agent *boot*, then concurrent messages "both call
  `.chat()` on the same AgentSession" Ⓐ channels/runner.py:23–31, router.py:40–61.
- In-process bridge: `chat()` calls `agent.chat(prompt)` with no queueing Ⓐ cli/main.py:198–200.
- The schedule runner fires `session.chat(s.task)` on its own thread — i.e., a schedule can fire *mid
  user turn* on the same session ✅ orchestrator.py:1568–1578.

Interleaved `add_message` calls corrupt the alternating user/assistant structure and tool-pair
invariants the Anthropic API requires; the repair logic (memory.py:509–556) was built to paper over
exactly this class of damage. QA's concurrency phase (QA_TESTING_PLAN.md Ⓐ) exercised the gateway but
this hazard is structural.

### W2 — The asynchrony story is inverted in two places

1. **"Background" work runs in the foreground of the next turn.** The only queue is
   `InMemoryJobQueue` ("Jobs are lost on process restart" ✅ queue.py:165–171); `JobWorker` has no run
   loop — only `execute_one()` ✅ queue.py:293–309 — and is drained **synchronously at the start of
   each `chat()`** ✅ orchestrator.py:686–691, 819. Consequence: post-turn LLM fact-extraction
   (memory.py:105–148) and structured-summary jobs execute inline before the *next* user turn begins,
   adding hidden latency, and are silently lost if the process exits first.
2. **Async routes run full agent turns on the event loop.** `openai_chat_completions` and
   `channel_inbound` are `async def` but call the synchronous `control_plane.complete_chat(...)`
   (a whole LLM+tools turn) directly ✅ fastapi_app.py:435–442, 482–495; `create_session` likewise
   triggers the full 11-step `boot_agent` (MCP subprocess spawn included) inside the event loop ✅
   fastapi_app.py:282–289 + Ⓐ cli/main.py:176–187. While one webhook turn runs, SSE keepalives,
   health checks, and every other async route stall.

### W3 — No streaming, anywhere

`BaseLLMClient.generate()` is single-shot ✅ llm.py:111–133; both clients buffer the full response;
the loop emits one `text_chunk` event containing the entire reply ✅ loop.py:478–480. The TUI, SSE
stream, OpenAI-compatible endpoint (`stream: bool` is accepted but a non-streaming JSON is returned ✅
fastapi_app.py:127–131, 435–457), and channels all therefore render answers only after completion.
Every competitor surface in this category streams; this is the single largest perceived-latency gap.
(Recommendation §6 / R3.)

### W4 — Silent data loss in the memory write path

The auto-memory pipeline can fail invisibly end-to-end: thread-fallback fact extraction swallows all
exceptions "to never interrupt the agent" ✅ memory.py:154–164; vault writes/searches/deletes return
`False`/`[]`/`""` on any exception so callers cannot distinguish "nothing found" from "store broken"
▶ memory_vault.py:269, 327, 388, 398, 415; the fire-and-forget upsert thread in the memory tools
swallows errors Ⓐ memory_tools.py:116–120; orchestrator recall paths collapse exceptions to `[]` ✅
orchestrator.py:697–706, 825–829. Repo-wide, the smells audit counted **123 `except Exception`
sites, ~23 of them masking persistence failures** Ⓐ. The product promise "the user never needs to say
remember this" (memory.py:14–15) currently has no failure signal when it breaks.

### W5 — Monoliths and duplication concentrate change risk

- `cli/main.py` **4,594 LOC** mixing ≥8 concerns (arg parsing, REPL, gateway bridge+bootstrap, config
  mutation, provider setup, secrets, doctor, permissions) Ⓐ; `tui/app.py` **3,063 LOC** (UI + state
  machine + 7 daemon threads Ⓐ tui/app.py:2015–2980); `gateway/orchestrator.py` **1,593 LOC** (boot +
  session + prefetch + snapshots) ✅.
- Duplicated logic clusters Ⓐ: fresh `SkillEngine()` built per CLI subcommand (13+ sites in
  cli/main.py — each re-parses the library from disk); config load→validate→write repeated across
  setup/quickstart/config-set; provider setup repeated in CLI and TUI flows.
- 60+ scattered `os.environ.get()` call sites, plus import-time env capture (oauth.py:25–26,
  tui/app.py:105 Ⓐ) that ignores later changes; a typed `Settings` model exists but covers only
  memory settings ✅ orchestrator.py:1270–1274.

### W6 — Declared quality gates are not the enforced ones

- `mypy strict = true` ✅ pyproject.toml:102–105 vs **386 errors in 55 files** ▶, with CI lint
  `continue-on-error: true` even on PRs Ⓐ ci.yml:74–78. The gap is concentrated in
  `integrations/*` and `tools/*` (subclassing dynamically-imported `Any` bases) ▶.
- `frontend-contract` job is commented out Ⓐ ci.yml:100–143 while the frontend consumes a generated
  client (1,394 lines Ⓐ) — contract drift is currently detectable only by hand (`npm run check:api`).
- CLAUDE.md states SvelteKit and an enforced contract job — both stale (Phase 0 D2/D3).

### W7 — Engine-level correctness debt in the moat itself

- **Global node namespace**: `self._nodes[node.name] = node` — any two `.og` files with a same-named
  node silently overwrite each other (user-authored `learned/` skills can shadow shipped ones) ✅
  engine.py:323–324.
- Hardcoded legacy paths bypass `platformdirs`: usage DB at `Path.home()/".hachi"/brain/` ✅
  engine.py:255; `RoleResolver` searches `~/.hachi/skills/roles` ✅ sub_agent.py:414–416 — user
  role overrides land in a directory the rest of the system no longer treats as canonical
  (paths.py:73–81 ✅).
- Retrieval is exact-keyword + linear fuzzy substring, unranked by `confidence` (Phase 0 §6.4) —
  deferred to Phase 2 for full treatment.

### W8 — Operational gaps

- Daemon = service installer; **no auto-restart on Windows** (Task Scheduler `ONLOGON` only) and an
  **unbounded log file** Ⓐ daemon.py:48–60, 365–398.
- Each gateway session boots a *complete* runtime — MCP subprocess servers, Chroma client, full tool
  table — per `register_connection` Ⓐ cli/main.py:176–187 + ✅ orchestrator.py:1027–1175; with the
  100-session cap (control_plane.py:91 ✅) that is up to 100 MCP server sets per process.
- Scheduler/notifier/TUI daemon threads are never joined on shutdown Ⓐ scheduler.py:395–396,
  notifier.py:180, tui/app.py — contradicting the repo's own "prefer queued background work"
  guardrail (CLAUDE.md); ChromaDB client has no explicit close Ⓐ memory_vault.py:67–72.
- Catch-all 500 handler returns `str(exc)` to the client — internal details (paths, key names in
  exception text) can leak ✅ fastapi_app.py:236–244. Gateway auth is *absent by default* unless a
  token is configured (`_require_auth` no-ops) ✅ fastapi_app.py:207–213 — acceptable for loopback,
  but docker-compose publishes 0.0.0.0:8787 with the token optional Ⓐ docker-compose.yml.
- `chatgpt-web` reverse-engineered provider ships in core with an in-code ToS warning ✅
  llm.py:478–494 — reputational/legal surface for an OSS project.
- LLM key fallback reads `.env` from **`Path.cwd()`** ✅ llm.py:50–52 — secret resolution varies with
  the directory the user happens to launch from.

### W9 — Test blind spots (carried from Phase 0, confirmed relevant here)

No E2E test drives a multi-turn, multi-tool `ExecutionLoop` with a scripted fake LLM; orchestrator,
MemoryManager internals, os_tools, delegation_tools, and non-Telegram channels lack direct tests Ⓐ
(Phase-0 test inventory). The concurrency hazards in W1 are precisely the kind that only such a
harness would catch.

### W10 — Misc. debt worth recording

- `AgentException("exceeded maximum iterations")` surfaces as an error instead of a graceful partial
  summary ✅ loop.py:591–593 (also flagged by the project's own QA: docs/qa/core-engine.md Ⓐ).
- Tools execute strictly sequentially even when the model batches independent calls ✅ loop.py:507–567.
- Hardcoded price table (incl. speculative model ids) with prefix matching Ⓐ cost.py:19–30 — silent
  mispricing as providers move.
- Per-turn frozen snapshot runs a fixed `semantic_search("important context", top_k=8)` every turn ✅
  orchestrator.py:666–671 — a constant-query Chroma hit in the latency path with cache-unfriendly output.
- Busy-wait `time.sleep(0.01)` polling in the control plane Ⓐ control_plane.py:529; CLI gateway
  polling loop Ⓐ cli/main.py:2509.

---

## 4. Technical debt register (consolidated)

| ID | Sev | Debt | Evidence |
|----|-----|------|----------|
| TD-1 | **Critical** | Concurrent `chat()` corrupts session history (all 4 surfaces) | control_plane.py:231–258 ✅; runner.py:23–31 Ⓐ; cli/main.py:198–200 Ⓐ; orchestrator.py:1568–1578 ✅ |
| TD-2 | **High** | No streaming end-to-end | llm.py:111–133 ✅; loop.py:478–480 ✅; fastapi_app.py:435–457 ✅ |
| TD-3 | **High** | In-memory-only "durable" queue; no worker loop; drain-at-next-turn | queue.py:165–171, 293–309 ✅; orchestrator.py:686–691, 819 ✅ |
| TD-4 | **High** | Async gateway routes block the event loop with full turns / boots | fastapi_app.py:282–289, 435–442, 482–495 ✅ |
| TD-5 | **High** | Silent memory-write failures (23 persistence-masking sites) | memory.py:154–164 ✅; memory_vault.py:269–415 ▶; memory_tools.py:116–120 Ⓐ |
| TD-6 | **High** | mypy strict configured, 386 errors, gate non-blocking | pyproject.toml:102–105 ✅; ▶; ci.yml:74–78 Ⓐ |
| TD-7 | Med-High | Global skill-node namespace collision | engine.py:323–324 ✅ |
| TD-8 | Med-High | Per-session full runtime boot in gateway (MCP × N sessions) | cli/main.py:176–187 Ⓐ; orchestrator.py:1027–1175 ✅ |
| TD-9 | Medium | cli/main.py / tui/app.py / orchestrator.py monoliths + duplication clusters | Ⓐ smells audit §5–6 |
| TD-10 | Medium | Legacy-path drift (`~/.hachi`) in engine + RoleResolver | engine.py:255 ✅; sub_agent.py:414 ✅ |
| TD-11 | Medium | frontend-contract CI disabled; CLAUDE.md stale | ci.yml:100–143 Ⓐ; Phase-0 D2/D3 |
| TD-12 | Medium | Unjoined daemon threads (scheduler, notifier, TUI, meet polling) | scheduler.py:395 Ⓐ; notifier.py:180 Ⓐ; meet.py:73–140 Ⓐ |
| TD-13 | Medium | Iteration-limit failure mode; sequential tool execution | loop.py:591–593, 507–567 ✅ |
| TD-14 | Medium | Env-read sprawl (60+ sites; import-time captures) | Ⓐ smells audit §4 |
| TD-15 | Low-Med | 500-handler detail leak; default-off auth + 0.0.0.0 compose | fastapi_app.py:236–244, 207–213 ✅; docker-compose Ⓐ |
| TD-16 | Low-Med | `chatgpt-web` unofficial provider in core | llm.py:478–494 ✅ |
| TD-17 | Low | cwd-relative `.env` secret fallback | llm.py:50–52 ✅ |
| TD-18 | Low | Hardcoded LLM price table; unbounded daemon log; no Windows autorestart | cost.py:19–30 Ⓐ; daemon.py:48–60, 365–398 Ⓐ |

## 5. Architectural risks & future limitations (observation)

1. **Single-process ceiling.** Threads + SQLite + embedded Chroma + in-proc MCP make one box the unit
   of scale; there is no story for >1 worker or >1 device sharing memory/sessions (relevant to the
   roadmap's always-on ambitions).
2. **Latency stack-up in the turn path**: per-turn vault snapshot search (orchestrator.py:666–671) +
   queue drain (819) + sequential tools + no streaming compounds into a perceived-slow agent even
   when the LLM is fast.
3. **The moat's correctness depends on author discipline** (keywords, dense budgets, unique node
   names) with lint as advisory only — at ecosystem scale (community packs, agent-authored skills)
   collisions and unroutable skills become data-quality failures (ties into Phase 2).
4. **Contract drift**: web frontend, OpenAPI export, and gateway evolve on trust while the CI job is
   off.
5. **Windows is a first-class user base but a second-class runtime** (no service autorestart, console
   Unicode issues per docs/qa/core-engine.md Ⓐ, path-casing subtleties in permissions Ⓐ).

---

## 6. Recommendations (What I propose)

Effort = ideal engineering-days for one senior engineer already familiar with the repo; confidence =
my confidence the estimate and approach are right. Each item names the assumption it rests on.

### P0 — correctness and competitiveness (do before any new feature work)

| R | Proposal | Addresses | Effort (conf.) | Key assumption / test |
|---|---|---|---|---|
| R1 | **Serialize turns per session.** Add a per-session `threading.Lock` (or single-consumer inbox queue) inside `AgentSession.chat()`; schedule-runner and channels then naturally queue. Emit a `session.busy` event for UIs. | TD-1 | 0.5–1 d (high) | Assumes callers tolerate blocking/queueing rather than erroring; verify with a 2-thread hammer test on one session (today it corrupts history — write that test first). |
| R2 | **Unblock the event loop.** Convert `openai_chat_completions`, `channel_inbound` to sync `def` (threadpool) or wrap calls in `anyio.to_thread.run_sync`; move `boot_agent` out of `create_session`'s async path. | TD-4 | 0.5 d (high) | No handler relies on async context beyond FastAPI plumbing — true today ✅. |
| R3 | **Streaming end-to-end.** Add `generate_stream()` to `BaseLLMClient` (Anthropic SDK `messages.stream`, OpenAI-compat SSE), emit `text_delta` runtime events, render incrementally in TUI, pass through `/sessions/{id}/stream` and honor `stream:true` on the OpenAI facade. | TD-2, W3 | 4–8 d (medium) | The loop's event channel is already the right transport (S6); risk is TUI re-render cost — prototype on the Textual `Markdown` widget first. |
| R4 | **Make memory failures loud.** Route *all* fact writes through the JobQueue (kill the thread fallback), let `JobWorker` failures flow to the existing `jobs/failed` read-model + a TUI badge; change vault methods to return typed results or raise, with one boundary that converts to user-visible warnings. | TD-5 | 1–2 d (high) | The read-model plumbing already exists (S6); assumes no caller depends on `[]`-on-error semantics (grep shows callers already treat empty as empty ✅). |

### P1 — durability, moat hygiene, and the gates you claim

| R | Proposal | Addresses | Effort (conf.) | Key assumption |
|---|---|---|---|---|
| R5 | **SQLite-backed JobQueue + resident worker thread** (the ABC anticipates it — queue.py:11). Drain-at-turn-start becomes a fallback, not the mechanism. Persist jobs in the existing state dir; resume pending jobs on boot. | TD-3 | 2–4 d (high) | Job funcs must become re-creatable (store name+payload, not callables) — today `func` is a live callable (queue.py:57), so this needs a small job-registry indirection. |
| R6 | **Qualified skill-node IDs.** Index nodes as `<file-stem>:<node>` with bare-name resolution when unambiguous; warn on collision at load; migrate `requires` resolution. Protects user/community packs from silent shadowing. | TD-7 | 1–2 d (med-high) | Shipped skills have no intra-collisions today (▶ 42 nodes load cleanly), so back-compat shims are cheap now and expensive later. |
| R7 | **One path truth.** Move skill-usage DB and RoleResolver onto `get_hachi_paths()` with a legacy-dir read shim. | TD-10 | 0.5 d (high) | Mirrors the existing legacy-import pattern (paths.py:95–120). |
| R8 | **Honest type gate.** Pick one: (a) burn down the 386 (most are mechanical: implicit-Optional, `Any` bases in integrations) then flip lint to blocking on PRs, or (b) scope strict mypy to `core/` + `og_engine/` + `gateway/` and gate that. Current strict-but-ignored config is the worst of both. | TD-6 | (a) 3–6 d / (b) 0.5 d (high) | (b) first, (a) opportunistically. |
| R9 | **E2E loop harness.** A scripted fake LLM (queue of responses incl. tool_use batches, errors, skill switches) driving `ExecutionLoop` + real `ToolRegistry` through multi-turn scenarios: tool error→`is_error`, compaction mid-conversation, budget stop, concurrent-chat regression (pairs with R1). | W9 | 2–3 d (high) | Inline mock-LLM patterns in tests already prove the shape (test_loop_resilience.py:18–32 Ⓐ). |
| R10 | **Re-enable `frontend-contract` CI** (job exists, commented) and fix CLAUDE.md's stale claims (SvelteKit→TanStack, contract job, memory description). | TD-11 | 0.5–1 d (high) | The generate+diff script already works locally (frontend/package.json Ⓐ). |
| R11 | **Decompose `cli/main.py`** into `cli/commands/*.py` per group with a shared `RuntimeBuilder` (one boot/config/provider service used by CLI, TUI, gateway). Kills duplication clusters 1–3. | TD-9 | 2–4 d (medium) | Typer sub-apps already exist as seams (Ⓐ CLI map); pure mechanical move. |
| R12 | **Central typed Settings.** Extend the existing `core/settings.py` pattern to cover gateway/voice/notifier/channel env vars; read env once at boot, inject. | TD-14 | 1–2 d (medium) | `MemorySettings` proves the pattern ✅ orchestrator.py:1270–1274. |

### P2 — scale, polish, posture

| R | Proposal | Addresses | Effort (conf.) |
|---|---|---|---|
| R13 | Shared-services gateway: one MCP manager/vault/skill index per process, per-session loop+memory only; lazy boot on first message | TD-8 | 4–8 d (medium) |
| R14 | Parallel execution of independent tool calls in a batch (thread pool inside the loop, preserving result order) | TD-13 | 2–3 d (medium) |
| R15 | Graceful iteration-limit exit: return best-effort summary + `status=incomplete` instead of raising | TD-13 | 0.5 d (high) |
| R16 | 500-handler: generic message + correlation id (details to log only); ship compose with token required when host ≠ loopback | TD-15 | 0.5–1 d (high) |
| R17 | Move `chatgpt-web` provider out of core (opt-in extra or community plugin) with an explicit risk README | TD-16 | 0.5 d (high) |
| R18 | Ops hygiene: log rotation for daemon log; document/automate Windows restart (`schtasks` limitations); join threads on shutdown; explicit Chroma close | TD-12, TD-18 | 1–2 d (medium) |
| R19 | Externalize the price table (data file + `hachi models --prices` refresh) | TD-18 | 1 d (medium) |
| R20 | Cache the per-turn "important context" snapshot (invalidate on vault writes) to take a Chroma query out of the hot path | W10 | 0.5–1 d (medium) |

### Sequencing note (proposal)

R1+R2 are a half-week that removes the only *corruption-class* bug surface; R3 (streaming) is the
single highest user-perceived improvement and should land before any UX work in Phase 6; R5+R4
together make the memory promise trustworthy and are prerequisites for the Phase 4 memory redesign;
R6 is cheap now and breaking later — do it before any marketplace/community-pack push (Phase 5).
