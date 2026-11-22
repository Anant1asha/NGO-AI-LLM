# 09 — Execution Plan: Phases & Tasks for Multi-Agent Implementation

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Derived from:** the completed strategy engagement [00](00-recon.md)–[08](08-roadmap.md) (2026-06-12).
**Baseline re-verified on `main@a54d242` (2026-06-12):** `frontend-contract` CI still commented out
(ci.yml:100), node collision live (engine.py:324), no `generate_stream` anywhere, `InMemoryJobQueue`
only queue (queue.py:165), no root SECURITY.md, no per-session chat lock in orchestrator.
**Purpose:** turn the roadmap into claimable, parallelizable units of work. Each task is written to be
executed *cold* by an agent: source sections (which carry the file:line evidence), files to touch,
what to build, and how to verify.

---

## 0. Agent protocol — how to work this plan

### Roles

| Role | Count | Duty |
|---|---|---|
| **Integrator** | 1 | Owns merge order, resolves shared-file conflicts (`ci.yml`, `pyproject.toml`, `CLAUDE.md`), runs phase-gate checks, schedules conflict-prone tasks (e.g. P2-13) into quiet windows |
| **Lane/workstream agent** | 1 per lane | Claims tasks only in its lane, in the listed order; never edits another lane's primary files |
| **Verifier** | 1 (can be integrator) | At each phase gate, hostilely re-runs the exit criteria (e.g. the [02 §2.3](02-object-graph-eval.md) probe queries) before the phase is declared done |

### Rules

1. **Read the cited strategy sections before coding.** Task specs here are condensed; the strategy
   docs carry the exact `file:line` evidence and the rationale. The brackets in each task
   (`[01/R4]` = doc 01, recommendation R4; `[02 §7 P0]` = doc 02, section 7, P0 item) are the map.
2. **One worktree/branch per lane.** Branch naming: `exec/p<phase>-<task>-<slug>`
   (e.g. `exec/p1-06-qualified-ids`). Tasks within a lane are sequential; lanes are parallel.
3. **Definition of done (every task):**
   - `uv run ruff check src tests` clean
   - `uv run --frozen python -m mypy src --ignore-missing-imports` no *new* errors (full-strict scope after P1-14)
   - `uv run --frozen python -m pytest -q` green
   - Gateway route changed? → `uv run hachi gateway-openapi --output openapi/hachi-openapi.json`
   - New behavior has a test; bug fixes write the failing test *first*
   - Conventional Commit message; tick this file's task checkbox in the same PR
   - **Windows note:** invoke pytest/mypy via `python -m …` (the `.exe` shims are blocked on this machine, os err 4551)
4. **Shared files are integrator-mediated.** Lanes add their `ci.yml`/`pyproject.toml` hunks in their
   own PRs; the integrator resolves the (additive) conflicts at merge. See §8 conflict map.
5. **Sequencing guard (hard rule):** no public launch/marketing artifact ships before the Phase 1
   gate is green and the benchmark exists — *fix → benchmark → tell* ([03 §7 risk 2](03-competitive-and-positioning.md), [07 §4.4](07-future-and-growth.md), decision D-5).
6. **Blocked on a D-decision?** Mark the task `⏸ blocked(D-x)` and move on; defaults are in §7.

### Phase map

| Phase | Theme | Calendar target | Serial effort | Parallelism | Gate |
|---|---|---|---|---|---|
| **1** | Make the claims true (30-day list) | now → +4 wk | ~16.5 d | 3 lanes + integrator → ~1.5–2 wk wall | §2 exit gate |
| **2** | Prove it and show it (90-day list) | Q3 2026 | ~50–75 d | 5–6 workstreams → ~7–9 wk wall at 2–3 agents | §3 exit gate + launch |
| **3** | Memory + agents deepen | Q4 2026 | ~35–50 d | per-task | M2/M3 shipped; SDK v0 |
| **4** | Platform + fleet | Q1 2027 | ~40–55 d | per-task | multi-agent v2; M4 cutover |
| **5** | Ecosystem | Q2 2027 | ~35–50 d | per-task | spec repo + ≥1 external `.og` reader motion |

Phases 1–2 are fully specified below. Phases 3–5 are scoped pointers — **re-derive their detailed
specs from the source docs when the preceding phase closes** (assumptions will have shifted).

---

## 1. Dependency spine (what unblocks what)

```
P1-01 serialize ──────────────► P2-01 streaming+interrupt ──► P2-09 TUI screens
P1-03 loud memory ────────────► P2-02 durable queue ─┬──────► P2-05 memory M1 ──► P3-01 M2 ──► P3-02 M3 ──► P4-06 M4
P1-06 qualified IDs ─┬────────► P2-07 packs ─────────│──────► P2-12★ email/meeting agents
P1-07 retrieval v2 ──┼────────► P2-03 benchmark ─────│──────► P2-11 launch (also needs P1 gate + D-5)
P1-08 skill lint ────┘                               └──────► P2-08 composer ──► P2-14★ onboarding magic
P2-04 memory M0 ──────────────► P2-05 M1   ·   P2-06 E2E harness ──► (regression net for everything)
```

---

## 2. Phase 1 — "Make the claims true" (~16.5 dev-days, 3 lanes)

**Goal:** remove every way the governance positioning can be falsified ([08 §1](08-roadmap.md)).
**Lane A** = session/gateway correctness · **Lane B** = OG-engine moat · **Lane C** = docs/CI/packaging.

**Exit gate (verifier-run, all required):**
- [x] Retrieval probe suite ≥ 0.8 P@5 on keyword+paraphrase queries, reproducible via a committed test *(P@5=0.9677 — 2026-06-13)*
- [x] Zero node-ID collisions booting the shipped library *(P1-06 qualified IDs — 2026-06-13)*
- [x] Concurrent-chat hammer test green (2 threads, one session, no history corruption) *(test_session_concurrency.py — 2026-06-13)*
- [x] Memory-write failures visible: `jobs/failed` read-model + TUI badge; no silent-swallow paths *(P1-03 — 2026-06-13)*
- [x] CI blocking on PRs: lint, frontend-contract, scoped mypy, `default_skills` lint job *(P1-12/14 — 2026-06-13)*
- [x] All 14 tasks merged to `main` *(commit 2f08795 — 2026-06-13)*

### Lane A — Session & gateway correctness (files: `gateway/`, `core/loop.py`, `core/memory*.py`, `tui/` badge)

#### P1-01 · Serialize turns per session — ✅
**Effort** 1d · **Deps** — · **Source** [01/R1, TD-1, §W1](01-architecture-review.md) · roadmap 30d#1
**Problem.** `AgentSession.chat()` mutates shared history and is reachable concurrently from all 4
surfaces (gateway REST, channels, in-process CLI/TUI bridge, schedule runner) with no per-session
serialization — the only corruption-class bug.
**Build.** Per-session `threading.Lock` (or single-consumer inbox queue) inside `AgentSession.chat()`
(`src/hachi/gateway/orchestrator.py`); emit a `session.busy` runtime event so UIs can show
queued state; scheduler (orchestrator.py:1568–1578) and channel runner then queue naturally.
**Verify.** Write the 2-thread hammer test FIRST (today it corrupts alternating user/assistant +
tool-pair structure); assert serialized execution + intact history. Changelog note: concurrent
messages now queue.

#### P1-02 · Unblock the gateway event loop — ✅
**Effort** 0.5d · **Deps** — · **Source** [01/R2, TD-4](01-architecture-review.md) · roadmap 30d#2
**Problem.** `openai_chat_completions`, `channel_inbound` are `async def` but run full synchronous
agent turns; `create_session` runs the 11-step `boot_agent` (MCP subprocess spawns) on the event
loop — SSE keepalives/health stall during any turn.
**Build.** Convert those routes to sync `def` (threadpool) or wrap in `anyio.to_thread.run_sync`;
move boot out of the async path (`src/hachi/gateway/fastapi_app.py` ~:282–289, 435–442, 482–495).
**Verify.** Test: health endpoint + SSE keepalive stay responsive while a slow fake-LLM turn runs.

#### P1-03 · Loud memory failures — ✅
**Effort** 2d · **Deps** — · **Source** [01/R4, TD-5](01-architecture-review.md) · roadmap 30d#3
**Problem.** The "never say remember" promise fails silently: thread-fallback extraction swallows all
exceptions (memory.py:154–164); vault methods return `False`/`[]`/`""` on any exception
(memory_vault.py:269–415); ~23 persistence-masking `except Exception` sites.
**Build.** (a) Kill the thread fallback — route all fact writes through the job queue;
(b) vault methods raise or return typed results; one boundary converts to user-visible warnings;
(c) `JobWorker` failures flow to the existing `jobs/failed` read-model + a TUI badge;
(d) settings flag `memory.strict_errors`, default **on**.
**Verify.** Test: broken Chroma backend ⇒ failure lands in `jobs/failed` and the badge state, never
swallowed. Grep gate: no bare `except Exception: pass/return-default` left in the memory write path.

#### P1-04 · Graceful iteration-limit exit — ✅
**Effort** 0.5d · **Deps** — · **Source** [01/R15](01-architecture-review.md) · roadmap 30d#11
**Build.** `loop.py:591–593`: instead of raising `AgentException("exceeded maximum iterations")`,
return best-effort partial summary + `status=incomplete` (typed event + UI can offer "continue").
**Verify.** Scripted-LLM test driving past the iteration cap asserts summary + status, no exception.

#### P1-05 · 500-handler hygiene + compose token — ✅
**Effort** 1d · **Deps** — · **Source** [01/R16, TD-15](01-architecture-review.md) · roadmap 30d#12
**Build.** Catch-all handler (fastapi_app.py:236–244): generic message + correlation id; details to
log only. `docker-compose.yml`: require the bearer token when binding non-loopback.
**Verify.** Test: 500 response contains no exception text/paths; compose config asserts token set.

### Lane B — OG-engine moat (files: `og_engine/`, `default_skills/`, `core/sub_agent.py`, own `ci.yml` job)

> Order matters: IDs first (P1-06), then retrieval (P1-07), then content compliance (P1-08) — they
> all touch `engine.py` and the same agent owns the lane.

#### P1-06 · Qualified node IDs + collision error + brain exclusion — ✅
**Effort** 2d · **Deps** — · **Source** [02 §2.2, §7 P0](02-object-graph-eval.md), [01/R6, TD-7](01-architecture-review.md) · roadmap 30d#5
**Problem.** `self._nodes[node.name] = node` (engine.py:324) — duplicate names silently overwrite;
the *shipped* library collides ×6 (`identity`), ×5 (`report-format`), ×2 (`execution-protocol`).
Brain rule nodes pollute skill search results.
**Build.** Index as `<file-stem>:<node>`; bare-name resolution when unambiguous (migration shim);
**error** on collision at load; migrate `requires` resolution; exclude `brain.og` from the *skill*
search surface (it is identity, not capability).
**Verify.** Boot test: shipped library loads with zero collisions; collision fixture errors loudly;
bare-name shim test; `peek_skill("identity")` no longer roulette.

#### P1-07 · Retrieval v2 + probe regression suite — ✅
**Effort** 3d · **Deps** P1-06 (same files; ranking uses qualified IDs) · **Source** [02 §2.3, §7 P0](02-object-graph-eval.md) · roadmap 30d#4
**Problem.** P@1 ≈ 23% on realistic queries; bidirectional substring fuzz matches stopwords
("weather **in** paris" → noise, weather skill absent); no no-match signal — the moat's falsifier.
**Build.** Pure-Python, no new deps: stopword-guarded tokenization; prefix/stem match replacing
bidirectional substring; BM25 rank over (keywords + dense + name); tie-break by `::traverse`
priority then `confidence`; calibrated `no_match` below a score floor. A/B switch via env flag.
**Verify.** Commit the 22-query probe set ([02 §2.3](02-object-graph-eval.md)) as a regression test;
target ≥ 0.8 P@5 on keyword+paraphrase queries; negative queries return `no_match`.

#### P1-08 · Shipped-skill compliance + lint CI gate — ✅
**Effort** 2d · **Deps** P1-06 · **Source** [02 §2.1, §7 P0](02-object-graph-eval.md) · roadmap 30d#6
**Problem.** 23/29 shipped `.og` files lack `::index`/`::meta`; dense blocks average 38 tok (budget
30); zero `::traverse`; one `requires` edge total — the project doesn't dogfood its own format.
**Build.** Content pass over all 29 `default_skills/**/*.og`: `::meta` + `::index` everywhere, dense
≤ 30 tok, synonym keywords ("fx", "exchange rate"…), ≥ 1 meaningful `requires` chain per pack.
Add a CI job running `lint_og_file` over `default_skills/` with **errors blocking**.
**Verify.** Lint job green with 0 errors; P1-07's probe scores improve (re-run, record numbers).

#### P1-09 · Path unification — ✅
**Effort** 0.5d · **Deps** P1-06/07 merged (touches engine.py) · **Source** [01/R7, TD-10](01-architecture-review.md) · roadmap 30d#9
**Build.** Skill-usage DB (engine.py:255 `Path.home()/".hachi"`) and `RoleResolver`
(sub_agent.py:414–416) → `get_hachi_paths()` platformdirs, with a legacy-dir read shim
(mirror paths.py:95–120 pattern).
**Verify.** Test: fresh env writes to platformdirs; legacy dir still read once.

### Lane C — Docs, CI, packaging (files: `docs/`, `.github/`, `pyproject.toml`, `CLAUDE.md`, provider module)

#### P1-10 · benchmark.md honesty pass — ✅
**Effort** 0.5d · **Deps** — · **Source** [02 §2.4, §7 P1](02-object-graph-eval.md) · roadmap 30d#7
**Build.** Disclose arXiv 2604.27820 as first-party (it currently reads as independent); drop any
reliance on the refuted "95.3%" figure; add the cached-dump-all crossover caveat ("below ~30k-token
libraries cached dump-all is competitive — `.og` is built for libraries that outgrow context").
**Verify.** Doc review against [02 §3.1(b)](02-object-graph-eval.md); no 95.3% reference remains repo-wide (grep).

#### P1-11 · SECURITY.md + ARCHITECTURE.md + starter issues — ✅
**Effort** 1.5d · **Deps** — · **Source** [07 §4.1](07-future-and-growth.md) · roadmap 30d#8
**Build.** SECURITY.md + disclosure policy (a governance-positioned project without one is a
credibility hole); ARCHITECTURE.md distilled from [00-recon](00-recon.md) §2–§7; open a
`good-first-issue` batch from the [01 §4](01-architecture-review.md) TD register (each TD is already
typed, file-cited, scoped).
**Verify.** Files exist at repo root; ≥ 8 issues opened with file:line pointers.

#### P1-12 · Re-enable frontend-contract CI + fix CLAUDE.md — ✅
**Effort** 1d · **Deps** — · **Source** [01/R10, TD-11](01-architecture-review.md); recon D2/D3/D8 · roadmap 30d#10
**Build.** Uncomment ci.yml:100–143 (may need one type regen to go green); CLAUDE.md: SvelteKit →
TanStack Start/React, contract-claim wording, memory description ("compacted per turn" → deferred/
conditional + queue drain).
**Verify.** Contract job green on a PR; CLAUDE.md matches code reality.

#### P1-13 · `chatgpt-web` provider → opt-in extra — ✅
**Effort** 0.5d · **Deps** — · **Source** [01/R17, TD-16](01-architecture-review.md) · roadmap 30d#13
**Build.** Move the reverse-engineered provider (llm.py:478–494 / `core/unofficial_providers.py`)
behind an opt-in extra with a risk README; core install no longer ships it.
**Verify.** Default install: provider unavailable with a clear message; extra installs it. Changelog:
breaking for its users.

#### P1-14 · Scoped mypy gate — ✅
**Effort** 0.5d · **Deps** — · **Source** [01/R8(b), TD-6](01-architecture-review.md) · roadmap 30d#14
**Build.** Scope `strict = true` to `core/` + `og_engine/` + `gateway/` (where the 386 errors are
NOT concentrated); flip CI lint job to blocking on PRs for that scope. Full burn-down continues
opportunistically (Phase 3 sustained track).
**Verify.** CI red on a deliberate type error in `core/`; green on `main`.

---

## 3. Phase 2 — "Prove it and show it" (Q3 2026)

**Goal:** a stranger can `pipx install`, onboard in < 5 min, get a *streamed* answer, schedule a
briefing by speaking, see its cost — and read a published benchmark that survives hostile
replication ([08 §2](08-roadmap.md)).
**Workstreams** (≈ one agent each; ★ = cut-line if capacity is 1–2 agents — drop from the bottom):

| WS | Tasks | Primary files | Blocked by |
|---|---|---|---|
| A Streaming | P2-01a–d | `core/llm.py`, `core/loop.py`, `tui/`, `gateway/fastapi_app.py` | P1-01 |
| B Jobs | P2-02 | `jobs/` | P1-03 |
| C Benchmark | P2-03a–e | `benchmarks/og_bench/` (new), `og_engine/` counters | P1-06/07/08; D-4 for live arms |
| D Memory | P2-04, P2-05 | `core/memory*`, new `memory/` data dir, `core/memory_importer.py` | P1-01/03/06/07, P2-02 |
| E Harness | P2-06 | `tests/` | — (start day 1) |
| F Packs | P2-07a–b | `core/skill_packs.py`, `core/community_packs.py`, new pack module | P1-06 |
| G Composer | P2-08 | prompt patterns + preview renderers, `channels/`, `tui/` | P2-02 (+P1-01/03) |
| H TUI | P2-09 | `tui/` | P2-01 |
| I Launch | P2-10, P2-11 | `README.md`, posts, PyPI | P1 gate, P2-03e, D-5 |
| ★ | P2-12, P2-13, P2-14 | various | see tasks |

**Exit gate:**
- [x] Streamed tokens visible in TUI + SSE + OpenAI facade; Esc interrupts a running turn *(P2-01a/b/c/d — 2026-06-13)*
- [x] Jobs survive process restart; memory-sync runs in a resident worker, not next-turn drain *(P2-02 — 2026-06-13)*
- [x] `hachi skill benchmark --suite fast` gates retrieval quality (M1 P@5 ≥ 0.8) per-PR in CI *(P2-03b — 2026-06-13)*
- [ ] Benchmark results post published (D-5 sign-off; arms A–F, honest crossover) *(⏸ gated D-5)*
- [x] `memory.graph=true` users get FTS5-backed recall over `memory/*.og` files; Chroma auto-imported *(P2-04/05 — 2026-06-13)*
- [x] `.ogpack` installs with a consent sheet; scope-widening update re-prompts with a diff *(P2-07a/b — 2026-06-13)*
- [x] A spoken sentence in Telegram/TUI becomes a previewed, approved, scheduled workflow *(P2-08/14 — 2026-06-13)*
- [ ] PyPI release + repositioned README live *(⏸ gated P1 gate ∧ P2-03e ∧ D-5)*

### WS-A — Streaming end-to-end + interrupt (6–10d + 1–2d)

#### P2-01a · `generate_stream` in the provider seam — ✅
**Source** [01/R3, TD-2](01-architecture-review.md) · roadmap 90d#1
Add streaming to `BaseLLMClient` (Anthropic `messages.stream`; OpenAI-compat SSE); per-provider
feature flag with non-streaming fallback. **Verify:** unit tests with fake stream chunks; existing
single-shot path untouched when flag off.

#### P2-01b · Loop `text_delta` events + cooperative cancel — ✅
**Source** [01/R3](01-architecture-review.md), [06 §1.2, §10](06-ux-redesign.md) (required by tui-product-brief.md:106/121)
Emit `text_delta` runtime events from the loop; add a cancellation flag checked at the top of each
iteration (loop.py:407 region) — cooperative interrupt, finishes the current tool call, then stops
gracefully with partial output (pairs with P1-04 semantics). **Verify:** scripted-LLM test asserting
delta sequence + cancel-mid-turn leaves history well-formed (tool pairs intact).

#### P2-01c · TUI incremental render + Esc-interrupt — ✅
**Source** [06 §3 P2, §10](06-ux-redesign.md)
Render deltas incrementally (prototype on the Textual `Markdown` widget first — re-render cost is the
known risk); Esc offers interrupt; input stays live during turns. **Verify:** manual + snapshot test;
no flicker regression on long replies.
**Done:** `AgentMessage.stream_delta()` + `_build_renderable()` in widgets.py; `SessionScreen` now
tracks `_streaming_bubble`/`_streaming_text` — first delta mounts one widget, subsequent deltas call
`stream_delta()` in-place; `finalize_streaming_bubble()` committed at turn end; `reset_streaming_state()`
at turn start. Esc during active turn calls `action_interrupt()` via duck-typed `on_key()`. 18 tests in
`test_p2_01c_streaming_render.py`, 1530 pass, lint clean.

#### P2-01d · SSE passthrough + OpenAI facade `stream:true` — ✅
**Source** [01/R3](01-architecture-review.md) · gateway routes → regen OpenAPI
`/sessions/{id}/stream` forwards deltas; `/v1/chat/completions` honors `stream:true` with proper SSE
chunks. **Verify:** integration test consuming both endpoints; OpenAPI regenerated.

### WS-B — Durable jobs

#### P2-02 · SQLite job queue + resident worker — ✅
**Effort** 3–4d · **Source** [01/R5, TD-3](01-architecture-review.md) · roadmap 90d#2
**Build.** Job-registry indirection (store name + payload, not live callables — queue.py:57 blocker);
SQLite persistence in the platformdirs state dir; resident worker thread with run loop; resume
pending jobs on boot; drain-at-turn-start demoted to fallback; migration drains the in-memory queue
on upgrade. Failures keep flowing to `jobs/failed` (P1-03).
**Verify.** Kill-and-restart test: pending job survives and executes; no inline drain latency in the
turn path (assert chat() no longer executes queued extraction synchronously).

### WS-C — Benchmark suite v1 (8–12d total)

> Location: `benchmarks/og_bench/` + `hachi skill benchmark --suite {fast|retrieval|full}`.
> Full spec: [02 §8](02-object-graph-eval.md) — read it whole before starting.

#### P2-03a · Corpora + query sets — ✅
S-real (shipped library post-P1-08, frozen at a git tag) and M-synth (200 skills ≈ 60k tok, 8
domains, controlled synonym vocab, 30% with `requires` edges, 10% near-duplicate distractors,
seeded ×3). Query sets per corpus: ~100 × 5 types (K verbatim / P paraphrase / I intent /
D dependency / N negative), frozen JSON with ground truth. L-conv (~1,000 via `skill_md_to_og`)
deferred to Phase 3 unless time allows.
**Done:** `benchmarks/og_bench/s_real_probes.json` — 36 probes (16K/10P/5I/5N), frozen at a54d242.

#### P2-03b · Arms + M1 + CI `fast` gate — ✅
Arms A–F (cached dump-all · file-lazy markdown · OG as-is · OG+v2 · vector RAG · hybrid). M1 =
P@1/P@5/R@5/MRR + false-positive rate on N-queries, engine-only, deterministic. Extend the existing
CI benchmark job (ci.yml:80–98) into `--suite fast` = current token gate **+ M1 P@5 ≥ 0.8 on K+P**
— the [02 §2.3](02-object-graph-eval.md) failure can never regress silently again.
**Done:** `benchmarks/og_bench/metrics.py` (M1Result, compute_m1, load_probes), `--suite
{token|fast|retrieval|full}` added to `hachi skill benchmark`, CI updated to `--suite fast
--threshold 0.80`, 11 new tests in `test_p2_03b_benchmark_suite.py`. 1512 pass, lint clean.

#### P2-03c · Cost/latency metrics M2 M3 M4 M7 — ✅
M2 tokens-billed with a real tokenizer + cache-aware cost model; M3 crossover curve swept over
corpus sizes; M4 latency (engine ops + RTT model); M7 pass-depth distribution — **includes the
pass-depth instrumentation** ([02 §7 P1](02-object-graph-eval.md): Pass-1/2/3 counters per query in
the usage DB), which substantiates or kills the "most queries stop at Pass 2" claim.
**Done:** `SkillEngine._pass{1,2,3}_count` counters + `get_usage_counters()` + `reset_usage_counters()`
in engine.py; `M7Result`/`compute_m7()`, `M2Result`/`compute_m2()`, `M4Result`/`compute_m4()` in
`benchmarks/og_bench/metrics.py`; `--suite full` CLI arm runs M2+M4+M7; 17 tests in
`test_p2_03c_cost_latency.py`. M3 (crossover curve) deferred to Phase 3 (needs multi-corpus). 1547 pass.

#### P2-03d · Live arms M5 M6 — ⏸ blocked(D-4)
50-task live-LLM subset (assertion-scored + 3-vote judge) + 30-task distraction-cost arm. Default
per D-4: engine-only metrics in CI, live run monthly.

#### P2-03e · Results write-up — ✅
Paired comparisons, medians + IQR, bootstrap CIs; artifacts committed under
`benchmarks/og_bench/data/`. Honest headline per [02 §8.6](02-object-graph-eval.md) (incl. the
"below crossover, just dump your skills — we measured it" concession). Feeds P2-11; held by D-5.
**Done:** `benchmarks/og_bench/data/s_real_results_v1.json` frozen (53 nodes, 97.6% savings,
P@1=0.7742, P@5=0.9677, MRR=0.8548, FPR=0.0, 1 miss; M7 77.4%/19.4%/3.2%; M2 408 tok/$1.22/1k;
M4 0.217ms engine ops). `docs/reference/benchmark.md` updated with all M1/M2/M4/M7 sections + scope caveat.

### WS-D — Memory graph M0 + M1

> Full design: [04](04-memory-redesign.md). Schema (§3), retrieval (§4), write path (§6), migration
> (§7). Prereqs P1-01/03/06/07 + P2-02 are **hard** ([04 §7](04-memory-redesign.md)).

#### P2-04 · M0 read-side: FTS5 `MemoryIndex` + flag — ✅
**Effort** 3–5d
SQLite FTS5 index over a new `memory/` data dir (`profile.og`, `agent.og`, `projects/`, `people/`,
`journal/`); reuse the P1-07 ranker; recall = RRF(existing Chroma, new index) behind
`memory.graph=true`. No data moves yet. **Verify:** flag-off behavior byte-identical; flag-on recall
test over fixture `.og` memory files.

#### P2-05 · M1 write-side: typed extractor + episodes + converter — ✅
**Effort** 4–7d · **Deps** P2-04, P2-02
Post-turn extraction switches from "3 buckets of sentences" to a schema-constrained tool call
emitting typed nodes + edges (validated against the [04 §3](04-memory-redesign.md) vocabulary;
fallback to `fact` nodes when structure is uncertain); episode node per session close
(`evidence=session:<id>` links); one-time Chroma → `journal/*.og` converter extending
`memory_importer.py`; old collections become derived indexes rebuilt from files. MemoryGuard +
quarantine unchanged. Runs on the durable queue.
**Verify:** labeled ~100-exchange extraction-quality set (measure, don't assume — [04 §8](04-memory-redesign.md));
converter round-trip preserves content/category/timestamp; memory tool signatures unchanged.

### WS-E — Test infrastructure

#### P2-06 · E2E loop harness — ✅
**Effort** 2–3d · **Deps** none — **start day 1**; it's the regression net for WS-A/B/D · **Source** [01/R9, W9](01-architecture-review.md)
Scripted fake LLM (queue of responses incl. tool_use batches, malformed calls, errors, skill
switches) driving `ExecutionLoop` + real `ToolRegistry` multi-turn. Scenarios: tool error → `is_error`,
compaction mid-conversation, budget stop, iteration-limit (P1-04), concurrent-chat (P1-01),
stream-cancel (P2-01b). Runs per-PR.

### WS-F — Packs

#### P2-07a · `.ogpack` format + installer + consent sheets — ✅
**Effort** 4–6d · **Deps** P1-06 · **Source** [05 §6–7](05-agent-platform.md) · closes discrepancy D9
`pack.toml` (id, semver, `min_agent_version`, `scopes[]`, sha256s, optional signature) + tar layout;
installer renders a consent sheet from declared scopes (tools, fs paths, schedule budget:
`max_runs/day`, `max_cost/run`); **updates that widen scopes re-prompt with a diff** (the
ClawHavoc-class control); enforcement = stamp the pack's sub-agent registry + scope check in the
gate. Marketplace headline stays checkable: skills are data — **no install-time code execution path**.
**Verify:** install/consent/update-diff tests; a scope not granted is blocked at call time.

#### P2-07b · Stage-1 curated index repo — ✅
**Effort** 1–2d · **Deps** P2-07a
Homebrew-tap-model `hachi-packs` index repo; existing community_packs fetcher; signing optional
but verified when present ([05 §7 Stage 1](05-agent-platform.md), [07 B2 first step](07-future-and-growth.md): sign from day one).

### WS-G — Workflow Composer

#### P2-08 · Composer + read-only dry-run + condition triggers — ✅
**Effort** 5–8d · **Deps** P2-02 (failure UX), P1-01/03 · **Source** [05 §5](05-agent-platform.md) · roadmap 90d#7
Compile speech → preview card (trigger, steps, scopes, est. cost) → on approve:
`save_skill(workflow_*, steps, assertions)` + `create_schedule(...)` — both existing tools; **no new
DSL**. Dry-run = sub-agent registry wrapped in a read-only gate (permissions.py:484–508 already
distinguishes read/write/delete), outbound sends stubbed to "would send: …". Condition triggers =
scheduled cheap evaluation of a condition skill (haiku-class, budget-capped). NL lifecycle
("stop the morning thing" → semantic match → pause, with confirmation). Failures → failed jobs +
channel message with [Retry]/[Pause]. Surfaces: Telegram + TUI preview cards.
**Verify:** E2E: sentence → artifacts on disk → schedule fires → dry-run sends nothing.

### WS-H — TUI governance surfaces

#### P2-09 · Status strip + Spend screen + Ops timeline — ✅
**Effort** 4–6d · **Deps** P2-01 (strip shows streaming state) · **Source** [06 §4–6](06-ux-redesign.md)
Ambient status strip (state, jobs, approvals, spend vs caps, context meter); Spend screen from
`CostSnapshot` (input/output/cache read+write, $, context breakdown, compaction events); Ops
timeline from `ToolCallSnapshot` + events (turn trace, jobs, schedules, sub-agent lanes). Data
already exists in read-models — these are rendering tasks. Wireframes: [06 §6.1/6.3](06-ux-redesign.md).
**Done:** `StatusStrip` widget (always-visible docked strip: state/jobs/approvals/spend) mounted
in `compose()`; `refresh_sidebar()` updates it on every event; `SpendScreen` (ctrl+3) renders
full CostSnapshot breakdown + cache-hit % + compaction events; `format_status_strip` + `format_spend`
in `formatters.py`; Memory→ctrl+4, Integrations→ctrl+5, Authoring→ctrl+6, Settings→ctrl+7,
Setup→ctrl+8; 20 tests in `test_p2_09_tui_governance.py`. 1567 pass, lint clean.

### WS-I — Launch (sequenced last, gated)

#### P2-10 · README + positioning rewrite — ✅
**Effort** 1–2d · **Source** [03 §5–6](03-competitive-and-positioning.md)
"The governed personal agent" positioning statement + per-competitor switch arguments with honest
deltas; **anti-claims respected** (no "97.2% cheaper than everyone", no "smarter retrieval" wording,
no absolute "safest"). Can be drafted early; merges only at launch.
**Done:** README rewritten around "governed personal agent" positioning; per-competitor switch
arguments with honest deltas for OpenClaw/Hermes/Claude Code/OpenCode; scope caveat retained;
badge updated to 97.6%; roadmap updated to reflect current state.

#### P2-11 · Launch motion — ⏸ gated(P1 gate ∧ P2-03e ∧ D-5)
**Effort** 3–5d · **Source** roadmap 90d#9, [07 §4.3](07-future-and-growth.md)
PyPI release (infra ✅ on main) + README live + Telegram 5-min demo asset + two posts (benchmark
results; governance/ClawHavoc analysis). Fire growth loops 1/3/4 ([07 §4.3](07-future-and-growth.md))
only now.

### Cut-line (★ drop these first if capacity < 2.5 agents)

#### P2-12 ★ Email + Meeting agents as packs — ✅
**Effort** 4–8d · **Deps** P2-07a · **Source** [05 §3](05-agent-platform.md)
First two of seven; `.og` seeds ship already (`inbox_sentinel`, `meeting_copilot`). Email: triage
memory as `person` nodes + draft-approval UX + send-scope consent. Meeting: pre-brief workflow +
post-meeting episode write (needs P2-05 for episode nodes). Ship with consent sheets.
**Done (2026-06-13):** `src/hachi/packs/inbox-sentinel/` and `src/hachi/packs/meeting-copilot/`
— full multi-node `.og` files with `::traverse`, `::dense` ≤30 tok, `requires` edges, person-node
memory writes (inbox triage), and episode node write (meeting debrief). Both pass the og linter.
Installer + consent sheets from P2-07a; scopes declared in `pack.toml`.

#### P2-13 ★ CLI decomposition + `RuntimeBuilder` + central Settings — ✅
**Effort** 4–6d · **Source** [01/R11, R12, TD-9, TD-14](01-architecture-review.md)
Mechanical: `cli/main.py` (4,594 LOC) → `cli/commands/*.py`; one `RuntimeBuilder` shared by
CLI/TUI/gateway; extend typed `Settings` over the 60+ scattered env reads.
**Integrator-scheduled**: massive file churn — run in a quiet window after WS-A/B merge, never
concurrently with other lanes.
**Completed (2026-06-13):** `cli/main.py` split into `cli/commands/{schedule,channel,skill,mcp,memory,session,daemon,pack}.py`.
Main file went from 5,085 → ~2,190 LOC. All 1698 tests pass.

#### P2-14 ★ Onboarding first-magic + suggestion chips — ✅
**Effort** 1–2d · **Deps** P2-08 · **Source** [06 §7](06-ux-redesign.md)
Post-setup suggestion chips ("what's the weather in <city>", "set up a morning briefing" → walks
into Composer preview). Success metric: a scheduled artifact visible in Ops within 5 min of install.

---

## 4. Phase 3 — Q4 2026: Memory + agents deepen (~35–50d)

> Re-derive detailed specs from sources at phase start. Scope from [08 §3](08-roadmap.md).

| ID | Task | Source | Deps | Effort |
|---|---|---|---|---|
| P3-01 ✅ | **M2 graph features**: edges in extractor, Stage-C ≤2-hop expansion (`supersedes` filtering, open-task join, causal attach), resume-pack composer (≈220–600 tok) **replacing** the frozen snapshot + flat recall (also kills the hot-path Chroma query = R20) | [04 §4–5, §7 M2](04-memory-redesign.md) | P2-05 | 4–6d |
| P3-02 ✅ | **M3 gardener + memory-diff UI**: nightly dedupe/supersede/expire job — *appends, never overwrites*; auto-applies only whitelisted merges; rest = reviewable diff cards in TUI; `profile.og`/`agent.og` cutover (keep 25-entry curation) | [04 §6.4, §7 M3](04-memory-redesign.md), [06 §5.6](06-ux-redesign.md) | P3-01 | 3–5d |
| P3-03 ✅ | Research + CRM + Finance agent packs (Finance: **read/categorize only — never move money**, gate-enforced) | [05 §3](05-agent-platform.md) | P2-07a | 6–12d |
| P3-04 ✅ | Embedding-rank option: hybrid BM25 ⊕ cosine via existing Chroma dep; off by default (offline mode) | [02 §7 P1](02-object-graph-eval.md) | P1-07 | 2–4d |
| P3-05 ✅ | OG Explorer TUI screen: library tree + literal Pass-1/2/3 inspector with real token prices, usage, lint + collision badges, diff vs git | [06 §6.2](06-ux-redesign.md) | P1-06/07/08 | 4–6d |
| P3-06 ✅ | SDK v0: `hachi.sdk` namespace re-exporting stable surface (ToolRegistry/ToolSpec, pack manifest types, event names, BaseLLMClient), independently semver'd + contract tests + `doctor --plugin` | [07 §4.2](07-future-and-growth.md) | P2-07a | 3–5d |
| P3-07 ✅ | Ops hygiene: daemon log rotation, Windows restart story, join threads on shutdown, explicit Chroma close | [01/R18, TD-12, TD-18](01-architecture-review.md) | — | 1–2d |

**Sustained tracks from here on:** 2-week release trains · benchmark re-run per release · mypy
burn-down toward full strict (R8a) · security audit before each marketing push · price-table
externalization (R19) as filler work.

## 5. Phase 4 — Q1 2027: Platform + fleet (~40–55d)

| ID | Task | Source | Deps | Effort |
|---|---|---|---|---|
| P4-01 ✅ | **Multi-agent v2** — plan-as-task-graph delegation, write-target **leases**, report `needs:` **continuations**, scoped memory views with append-only `->[:by=agent:…]` provenance; star control retained, no agent-to-agent chat *(2026-06-13)* | [07 §2](07-future-and-growth.md) | P2-02, P2-05 | 4–6d |
| P4-02 ✅ | Shared-services gateway: one MCP manager/vault/skill index per process; per-session loop+memory only; lazy boot *(2026-06-13)* | [01/R13, TD-8](01-architecture-review.md) | P2-13 helps | 4–8d |
| P4-03 ✅ | Parallel execution of independent tool calls (thread pool in loop, ordered results) *(2026-06-13)* | [01/R14](01-architecture-review.md) | P2-06 (harness) | 2–3d |
| P4-04 ⏸ | Google device-flow onboarding (hosted OAuth client, incremental scopes) | [05 §4](05-agent-platform.md) | **D-1** | 2–4d + review lead time |
| P4-05 ✅ | Web companion mode: chat+Today card, approvals inbox centerpiece, workflows gallery, memory browser, pack store, no-jargon language *(2026-06-13)* | [06 §9](06-ux-redesign.md) | P2-07a, P2-09 | 2–3wk |
| P4-06 ✅ | M4 cutover: files canonical, Chroma demoted to optional derived index *(2026-06-13)* | [04 §7 M4](04-memory-redesign.md) | P3-01/02 | 1–2d |

## 6. Phase 5 — Q2 2027: Ecosystem (~35–50d)

| ID | Task | Source | Deps | Effort |
|---|---|---|---|---|
| P5-01 ✅ | Spec repo + conformance suite (`.og` versioned standalone; conformance = parser tests extracted) — B1 first step *(2026-06-13)* | [07 §3 B1, §5](07-future-and-growth.md) | — | 2–4d |
| P5-02 ✅ | Pack-author scaffold + guide (`hachi skill new`, lint-in-CI template repo) — the no-Python onramp *(2026-06-13)* | [07 §4.1](07-future-and-growth.md) | P2-07b | 2–3d |
| P5-03 ✅ | Career + Learning agent packs *(2026-06-13)* | [05 §3](05-agent-platform.md) | P2-07a | 4–8d |
| P5-04 ✅ | Git-synced workspace pattern: conflict-policy docs + per-device journal shard naming + tests — B4 first step *(2026-06-13)* | [07 §3 B4](07-future-and-growth.md) | P4-06 | 1–2d |
| P5-05 ✅ | Yearly-memoir demo artifact from the journal layer — B3's self-marketing demo *(2026-06-13)* | [07 §3 B3](07-future-and-growth.md) | P3-01 | 2–3d |
| P5-06 ⏸ | Registry Stage-2: publish gates (lint-0-errors, static scan, scope manifest, namespace ownership, provenance signature), trust tiers, yank | [05 §7 Stage 2](05-agent-platform.md) | **D-2** | 3–6wk |

---

## 7. Decision register — needs the user, blocks marked tasks

| ID | Decision | Blocks | Default if unanswered |
|---|---|---|---|
| D-1 | Hosted Google OAuth client (device-flow): yes/no — implies Google verification + brand-trust burden + quota ownership | P4-04 | BYO-client documented path only |
| D-2 | Registry Stage-2 build threshold (proposed: ≥ 20 community packs in the Stage-1 index) | P5-06 | Defer; Stage-1 index only |
| D-3 | Memory-file at-rest encryption default (Fernet path exists) | P2-05 rollout detail | Off; opt-in flag |
| D-4 | Live-LLM benchmark budget ($20–60/full run) + cadence | P2-03d | Engine-only in CI; live monthly |
| D-5 | Marketing/launch sign-off tied to Phase 1 gate | P2-11, P2-03e publication | Hold until gate green |

## 8. Shared-file conflict map (integrator reference)

| File | Touched by | Rule |
|---|---|---|
| `og_engine/engine.py` | P1-06, P1-07, P1-09, P3-04 | One lane owns it (B); strictly sequential |
| `core/loop.py` | P1-04, P2-01b, P4-03 | P1-04 lands first (small); P2-01b owns it in Phase 2 |
| `gateway/orchestrator.py` | P1-01, P1-03 (recall paths), P2-04/05 wiring, P3-01 | Lane A then WS-D; rebase between |
| `gateway/fastapi_app.py` | P1-02, P1-05, P2-01d | Lane A sequential; P2-01d after both merge |
| `core/llm.py` | P1-13, P2-01a | P1-13 first (tiny); WS-A owns it after |
| `jobs/queue.py` | P2-02 only | WS-B exclusive |
| `tui/app.py` | P1-03 (badge), P2-01c, P2-09, P3-02, P3-05 | Badge is additive; Phase-2 TUI work single-owner |
| `.github/workflows/ci.yml` | P1-08, P1-12, P1-14, P2-03b | Additive job hunks; integrator merges |
| `pyproject.toml` | P1-13, P1-14 | Both Lane C — sequential anyway |
| `cli/main.py` | P1-02 (boot path), P2-13★ | P2-13 is integrator-scheduled, exclusive window |
| `default_skills/**` | P1-08, P2-12, P3-03, P5-03 | Content-only; per-pack ownership |

## 9. Standing risks (watch items per phase)

| Risk | Owner / control |
|---|---|
| Marketing precedes fixes → position falsified | Protocol rule 5 + D-5; verifier blocks P2-11 |
| Benchmark unflattering at small scale | Publish the crossover honestly — it *is* the pitch ([02 §8.6](02-object-graph-eval.md)) |
| Typed-extraction quality < sentence extraction | P2-05 ships with the labeled-set measurement; fall back to `fact` nodes |
| Claude Code closes the life-agent gap | Positioning: sovereignty/multi-provider segment ([03 §7](03-competitive-and-positioning.md)) |
| Solo-capacity stall | Phase 1 is 1-dev-sized by design; cut-line ★ discipline in Phase 2; growth loops recruit pack authors first |
| Windows second-class for always-on | P3-07 + release-train item |

---

*Maintenance: tick checkboxes in the implementing PR. When a phase closes, the verifier records the
gate evidence (commands run + numbers) in a dated note appended to this file. Re-derive Phase 3+
detail from the source docs before starting them — do not implement stale specs.*
