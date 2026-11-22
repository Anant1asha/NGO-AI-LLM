# AUDIT.md — Hachi Architecture Review Board

> **The roadmap is the contract; this audit is the proof.** Living document — update at the
> end of every session. North star: **trust first** (reliable + personal beats powerful + surprising).

**Date:** 2026-06-23 · **Branch:** `reassess` · **Reviewer:** Principal-Architect engagement (Opus 4.8)

**Method.** 9 parallel read-only, evidence-based subagent audits (one per pillar / cross-cutting
dimension), each citing real `file:line`; 3 inter-auditor conflicts adjudicated by direct grep
(results below); full `pytest` baseline run. Rubric is the **world-class bar** in the operating
protocol (ChatGPT / Claude / Gemini / Cursor / Claude Code / Perplexity), **not** a bug-count
health score — so this score is *not* directly comparable to the prior 44 → 59 → 80 "health"
numbers from earlier audits.

**Test baseline (this tree, incl. 12 uncommitted in-flight files):** `2 failed, 3355 passed,
19 skipped` in 7m38s. Both failures are `test_cockpit_*` live/ChromaDB-isolation tests (known
Windows-env flakiness), not subsystems under audit.

---

## Reassessment delta — 2026-06-24 (HEAD `4063e41`, branch `reassess`)

**Re-verification.** All 4 P0s + key P1s were independently re-checked against current code by direct
grep/read. HEAD's "live bug-fix round" (MCP HTTP transport, model-name reporting, frontend retry/leak)
was **orthogonal** to this backlog and closed none of it — the findings below stand as written,
**except P0-3, now resolved** (§3).

**Shipped this session — trust-first, one tested change at a time:**
- ✅ **P0-3 RESOLVED — the idempotency layer (Theme A, the audit's "single most corrosive gap").**
  Three layers: outbound messaging dedup (per-session `IdempotencyGuard`, success-only,
  `core/idempotency.py`), scheduler `add()` windowed fingerprint dedup (no duplicate recurring jobs),
  and **durable ingress idempotency** on `POST /sessions/{id}/messages` (header/body key →
  `SessionStore.idempotency_keys` → replay the prior turn; the web client sends a stable
  `turn-${id}` key that `retryLastMessage` reuses). **155 workstream tests green**; `ruff`+`mypy`
  clean; OpenAPI + `schema.d.ts` regenerated.
- ✅ **P0-2 RESOLVED — `interaction_log`, the keystone of the eval loop.** A durable per-turn row
  `{user_input, agent_output, tool_calls, memory_hits, model_used, token_cost, tokens, rating, notes}`
  written once per turn (`SessionStore.log_interaction` ← `AgentSession._write_interaction_log`), plus
  `get_interactions` + `set_interaction_rating` and a new `ExecutionLoop.last_tool_calls` per-turn
  capture. Unblocks rating, `/review`, per-turn audit, and output-regression eval. **14 tests**; zero
  new mypy errors (strict-gated `session_store.py` clean).
- ✅ **P0-1 RESOLVED — the suspend producer (a dead marquee feature, now alive).** `loop.py` exposes
  the structured suspend (`last_suspend`) instead of discarding it into a string; `AgentSession`
  persists `RunState(WAITING)` + arms the wait registry after the turn
  (`_persist_suspended_run_if_any`). The whole wake/recover/sweep subsystem and `GET /runs` now have
  inputs. **5 tests assert the durable side effect** the prior tests never did. Cold-start replay /
  precise `resume_cursor` remain the separately-tracked deferred resume work.
- ✅ **P0-4 RESOLVED — the Docker self-host path runs.** Added the missing `frontend/Dockerfile`
  (node build → nginx serve, proxying `/api`→gateway with prefix-strip + server-side bearer token +
  SSE-safe buffering, mirroring the dev Vite proxy); switched the backend's four `/root` bind mounts
  to **named volumes** at `/home/hachi/...` that inherit the non-root user's ownership (Dockerfile
  pre-creates+chowns the XDG dirs). Replaced the string-only test with **10 structural guards** + a
  `docker-smoke` CI job (`compose config` + build **both** images). `docker compose config` validates
  locally; the live build is verified in CI (Docker Desktop's Linux engine went down mid-session).
- ✅ **Google Workspace config resolution (user-reported).** `core/oauth.py` captured the OAuth client
  id/secret as **module-level globals at import time**, so a value configured in `.env` (loaded later,
  or in `config_dir/.env`, or under a different import order) was never seen → "Missing
  GOOGLE_CLIENT_ID" despite being configured (proven by reproduction). Fixed in three layers: lazy
  `_resolve_env()` (env → `cwd/.env` → `config_dir/.env`) in oauth; `register_google_tools` gate uses
  the same resolver; and the CLI startup loader now also merges `config_dir/.env` (where `hachi setup`
  writes) — fixing Google **and** all wizard-configured credentials. 9 tests.
- ✅ **Connector hardening (completeness sweep).** Closed the two residual items a "what's left" check
  surfaced: (a) **in-turn idempotency for Google writes** — an opt-in guard in `GoogleHTTPClient.post`
  applied to `send_email`/`reply_thread`/`create_event`/`create_recurring_event` (Theme A now covers
  the connector send/create path, not just messaging + ingress); (b) **headless first-auth fail-fast**
  — the gateway/serve server marks itself non-interactive so a first Google call raises "run `hachi
  auth google`" instead of hanging ~120 s on a browser. 8 tests.
- Detail for all: `DECISIONS.md` → "Reassessment P0 sweep (2026-06-24)" + "Google Workspace config
  resolution" + "Connector hardening".

**Score impact:** P0-3 (idempotency, the shared deduction across three pillars) → **P2 Tools 68→74**,
**Gateway 78→80**; P0-1+P0-3 (suspend was the other big P5 deduction) → **P5 Loop 52→62**; P0-2 (the
eval substrate now exists; `/review` UI + eval suite still to come) → **P4 Eval & Observability 42→50**;
P0-1 also lifts **Long-Running Tasks 80→84**; P0-4 → **Deployment 48→60**; the Google config-resolution
fix → **Connectors 68→72**. **All four P0s resolved.**

**P1 tier — ALL 9 resolved (2026-06-24, agent-orchestrated sweep; Sonnet 4.6 subagents writing code under Opus orchestration, each verified + committed separately):** P1-2 hot-path model tiering
(complexity classifier → `router.select` + user-turn failover); P1-3 daily-cap enforcement; P1-4
web-Stop/disconnect → `loop.cancel`; P1-5 durable fact-extraction (func→handler_name); P1-6 async
compaction summary applied back to history; P1-7 personalization substrate (UserProfileStore +
append-only CorrectionLog + save tool); P1-8 MCP retry/breaker/reconnect; P1-9 `hachi backup`/`restore`
+ Windows CI + removed the phantom GitHub connector; P1-1 single-tenant constraint documented (account_id
plumbing deferred to the 12-month multi-tenant track). Score impact: **P3 Routing 62→76**, **P7
Personalization 48→64**, **P1 Memory 68→74**, **P5 Loop 56→66**, **P2 Tools 74→80**, **Reliability
82→86**, **Deployment 60→66**, **CI 70→78**. **Overall 64→73→~82.**

**P2 hardening tier — the clear-cut hardening debt is now closed (2026-06-24, same agent-orchestrated pattern;
Sonnet 4.6 subagents under Opus orchestration + independent verification + full-suite gate):** P2-1 token-based
context-window management (removes the count→token *cliff*; `_MAX_ACTIVE_TOKENS` + bounded compaction passes);
P2-5 behavioral tests guarding the `brain.og` hard-constraint blocks (persona-drift CI gate); P2-7 job-queue
dead-letter + `redrive` (durable background work survives a longer outage instead of silent post-FAILED
deletion); P2-10 **cold-start resume** (a WAITING run woken after a gateway restart now rehydrates its session
from the SQLite transcript via the existing `boot_agent(resume_session_id=…)` → `resume_from_session` machinery
instead of `HonestResumeError`; the previously-untested replay is now proven against a **real** store+memory —
no mocks); P2-11 deep readiness probe + compose healthcheck; P2-13 structural perf-regression guards for recall
(bounded top-k, lazy ChromaDB) and compaction (bounded passes, no unbounded history growth). Also confirmed
already-shipped: P2-4's **recall-side** PII/secret redaction (`memory_vault` MED-009 `_redact_results`). Score
impact (incremental): **Context Engineering 78→84**, **Reliability 86→88**, **Gateway 78→82**, **Prompt-as-Code
82→86**, **Long-Running Tasks 84→88**, **CI/Tests 78→82**. **Overall ~82→~84.** Full `pytest` after the batch:
**3643 passed / 17 skipped / 0 failed**.

What remains is **features, not hardening** — episodic store (P2-3), memory decay/recency + LRU eviction (P2-2),
EventBus reactivity (P2-6), container/gVisor sandbox (P2-8), unified knowledge graph (P2-9), FE client query
cache (P2-12) — plus design-decision items (encryption-at-rest, multi-tenant `account_id` plumbing). Per the
operating protocol these are **flagged, not auto-built**. The leash approve/deny `request_id` correlation
(P2-12b, currently text-matched) is a real but **near-zero-blast-radius** nicety — per-session `_chat_lock`
serialization precludes the concurrent-identical-request race it guards against — flagged for a future
cross-stack pass rather than auto-built.

**Eval loop — the trust flywheel now closes (2026-06-24, user-greenlit feature build on the P0-2 substrate).**
With `interaction_log` already capturing one row/turn, the consume side is now shipped end-to-end:
(E1) gateway read/rating API — `GET /interactions` (ownership-filtered like `list_sessions`) + `PUT
/interactions/{id}/rating` (typed up/down + notes), backed by the REAL store; `fastapi_app.py` still
strict-mypy-0; 23 tests. (E2) `core/eval/` — a PURE `build_failure_report()` (totals, failure-rate,
errored-turn detection, top failing tools, per-model cost/down breakdown) + a regression-runner scaffold
(`EvalCase` + structural assertions checked against a REAL `ExecutionLoop` trajectory — `run_case` never
hardcodes pass) + `hachi eval report`/`run` CLI; 38 tests incl an anti-fake proof (an unsatisfiable
assertion must yield `passed=False`). (E3) a `/review` web screen listing each turn's trajectory with
thumbs-up/down + notes (real gateway round-trip; honesty guard so a failed fetch shows empty, never
fixtures-as-real); typecheck + 82 vitest + production build + `check:api` green. Honest gaps (E1–E3, now CLOSED by E4–E5 below): `hachi eval run` reported "not wired"; the
weekly-failure-report automation + a curated regression corpus were the natural next increments. Score
impact (E1–E3): **P4 Eval & Observability 50→62** (the eval half went from ~12 to a real, usable loop).
**Overall ~84→~85.**

**Eval flywheel completed (E4–E5, 2026-06-24):** (E4) `hachi eval run` is now REAL and CI-able — a
deterministic record/replay harness (`core/eval/replay.py`) drives the PRODUCTION `ExecutionLoop` via a
`ScriptedLLMClient` (only the LLM transport is stubbed), runs a curated `DEFAULT_REPLAY_SUITE`, and exits
non-zero on any failure; the anti-fake guarantee is preserved (`run_replay_suite`→`run_case`, proven by a
test where an unsatisfiable assertion forces exit 1). (E5) weekly failure-report automation — a decoupled
`core/eval/scheduled_report.py` writes timestamped `.md`+`.json` artifacts, surfaced by an opt-in resident
daemon (`[eval_reports] enabled`, default OFF, mirrors the proven `_start_timeout_sweep` pattern; the
load-bearing agent-turn scheduler is untouched) + a `hachi eval snapshot` manual/cron command + an
`eval.report.generated` event. 54 new tests; full `pytest` **3758 pass / 0 fail**. Verified live on the
REAL store: `eval run` 5/5, `eval report` over 29 real turns, `eval snapshot` artifact written. The
flywheel immediately surfaced one real finding — every logged turn showed **$0.00 cost / 0 tokens** (a
pre-existing P0-2 instrumentation gap, NOT introduced by E4/E5), which was then root-caused and **FIXED
(COST-1, below)**. Remaining eval gaps are CONTENT/OPS not machinery, and **E6/E7 (below) closed two of the three**: a
live-record mode is still absent (fixtures are hand-authored). Score impact: **P4 Eval & Observability
62→70.** **Overall ~85→~86.**

**E6/E7 — eval corpus hardened into a real CI gate (2026-06-24):** the replay corpus grew from a 5-case
smoke seed to **14 loop-mechanics regression cases** that pin the ReAct loop's control-flow contracts
(tool-error recovery, unregistered-tool handling, max-iteration cap → `[INCOMPLETE]` at exactly 10 calls,
empty/degraded response, argument passing, parallel tool calls, ordered multi-step, no-sentinel-leak in
clean output), backed by 3 new precise assertion kinds (`tool_call_count`, `output_not_contains`,
`tool_called_in_order`). Exercising every edge case **found no loop bugs** — the loop is robust. `eval run`
is now a **blocking CI job** (exits non-zero on any regression) so these contracts are enforced on every
push/PR. Full `pytest` **3793 pass / 0 fail**. The only remaining eval increment is a live-record mode
(record real LLM responses into replay fixtures); the corpus is otherwise a genuine regression net, not a
seed.

**COST-1 — OpenAI-compat streaming usage fix (2026-06-24, surfaced by the eval flywheel above):**
`OpenAICompatibleClient.generate_stream` set `stream=True` but never sent
`stream_options:{include_usage:true}`, so OpenAI-compatible providers omit the final usage chunk in
streaming mode → the `CostTracker` recorded **zero tokens/cost for every streaming turn**. Two real
consequences, not just cosmetics: (1) interaction_log / eval-report cost+token metrics were meaningless for
all non-Anthropic providers; (2) the **daily spend cap (P1-3) was silently inert** for OpenAI-compat
streaming (cost never accrued → the cap could never trip). Fix: request usage by default (threaded through
all client build sites via a `stream_usage` provider-config flag; opt-out for strict local servers that 400
on unknown fields). 4 new streaming tests; full `pytest` **3762 pass / 0 fail**. This closes a silent
correctness gap behind both the P1-3 cap and the P4 cost metrics for OpenAI-compatible providers; overall
holds at **~86** (a restored guarantee, not a new capability). Honest limits: historical rows do not
backfill; the `chatgpt-web` unofficial provider is inherently usage-less.

The 2026-06-23 scorecard/findings below are preserved as the baseline snapshot; this dated block is the current truth.

---

## 1. Overall maturity: **64 / 100** *(→ ~82 as of 2026-06-24; all P0s + the full P1 tier resolved — see delta above)*

A genuinely well-engineered, **honest**, secure foundation that is ~2/3 of the way to world-class.
The *infrastructure* pillars (security, reliability, gateway, frontend streaming, scheduler,
prompt-as-code) are strong (78–86). The *agent-intelligence* pillars (eval loop, personalization,
loop integrity, hot-path routing) and *deployment* carry the real gaps (42–62) and pull the score
down. Crucially, very few gaps are "missing from scratch" — most are **last-mile-unwired** (the hard
machinery exists; the final connection was never made), which makes the 30-day ROI unusually high.

| # | Pillar / Dimension | Score | One-line verdict |
|---|--------------------|:-----:|------------------|
| P1 | Memory Architecture | 68 | Advanced + well-tested; cross-user isolation is dead code, episodic = raw LIKE-scan, no real decay |
| P2 | Tools & MCP | 68 | Strong plumbing & traceability; **no idempotency on writes**, dead `ToolError`, MCP lacks retry/breaker |
| P3 | Token Budget & Routing | 62 | Excellent router/resilience **built but not on the hot path**; daily cap cosmetic |
| P4 | Eval & Observability | 42 | Observability strong (~70); **eval half near-absent (~12)** — no interaction_log, rating, /review |
| P5 | Agentic Loop Integrity | 52 | Best-in-class backstops; **suspend/resume is a dead feature**; web-interrupt unwired; no idempotency |
| P6 | Prompt as Code | 82 | Versioned `.og` brain, single composer, cache-aware split; only behavioral tests missing |
| P7 | Personalization | 48 | Solid memory *substrate*, no personalization *product* — no onboarding/UserProfileStore/CorrectionLog |
| — | Security & Privacy | 86 | Reference-quality SSRF, fail-closed auth, Fernet/keychain secrets, injection framing; sandbox process-only |
| — | Reliability | 82 | Real circuit-breaker + fallback chain + durable queue; no dead-letter / re-drive |
| — | Gateway / Daemon | 78 | Real OS daemon, fail-closed auth, end-to-end-ish interrupt; shallow readiness, no chat idempotency |
| — | Deployment | 48 | Installers + PyPI OIDC excellent; **Docker Compose is broken**, backup/restore orphaned |
| — | CI / Tests | 70 | 6 jobs, 243 test files, broad backend coverage; no Windows runner, advisory mypy/bandit |
| — | Frontend / UX | 82 | Professional streaming, strong trust signals (leash/approvals/retry); no client query cache |
| — | Connectors / Knowledge | 68 | Google suite excellent; GitHub is a phantom; no unified knowledge graph |
| — | Long-Running Tasks | 80 | Standout: durable DST-correct scheduler actually fires turns; cold-start resume unimplemented |
| — | Event-Driven Arch | 62 | Good EventBus; behaviorally shallow (one reactive workflow; mostly telemetry fan-out) |
| — | Context Engineering | 78 | Cache-aware split, hybrid RRF, tool-pair-safe compaction; message-count (not token) window = cliff risk |
| — | **Claims honesty** | **93** | 6/6 DECISIONS claims + 4/4 frontend routes verified true; the historical "claimed-done-but-absent" pattern is **not** reproduced |

---

## 2. Two meta-themes (read these first)

### Theme A — The **idempotency deficit** (highest trust risk)
Three independent auditors (P2, P5, Gateway) surfaced the same structural hole: **no idempotency
anywhere a side effect happens.** Side-effecting tools (`send_slack/discord/whatsapp/telegram`,
`create_schedule`, email/calendar) carry no idempotency key and don't dedup; the chat ingress
`POST /v1/.../messages` has no `Idempotency-Key`. On any retry/reconnect/turn-resume the result is
**duplicate messages, duplicate recurring schedules, or a duplicate whole turn with double spend.**
For an assistant whose entire promise is *acting on the user's behalf*, this is the single most
corrosive gap. Evidence: `messaging_tools.py:56-206`, `scheduler.py:551-571`,
`fastapi_app.py:1239,1301-1304` (zero `Idempotency-Key`/`client_message_id` in `src/`).

### Theme B — The **"last-mile-unwired" pattern** (highest ROI)
Hachi repeatedly builds the hard machinery and the seams, then never connects the final wire. This
is good news: many P0/P1 fixes are *connect two existing things*, not *build from scratch*.
- `ModelRouter` + cross-provider failover — **built**, but the loop always calls `default_client()` (router bypassed for user turns). `router.py` ✅ / `orchestrator.py:2724-2730`.
- Suspend/resume wake/recover/sweep subsystem — **built**, but no producer ever creates a `RunState(WAITING)`. `orchestrator.py:1682-1840` ✅ / no producer ⚫.
- Daily spend cap — **recorded + displayed**, never read to enforce. `get_daily_spend` → 1 caller (display).
- `SessionStore.backup()` — **correct primitive**, zero callers, no CLI.
- Eval events + `RuntimeReadModels` — **rich**, but no durable `interaction_log` to write them to.
- `account_id` vault namespacing — **built (ADV-023)**, never plumbed from auth.
- Structured conversation summary — **generated** in background, then discarded (placeholder used instead).

---

## 3. Critical findings — **P0** (block any "production"/multi-user/"it works" claim)

```
FINDING P0-1: Suspend/resume is non-functional end-to-end (a dead marquee feature)
PILLAR: P5 Agentic Loop / Long-Running
STATUS: ✅ RESOLVED 2026-06-24 (was ⚫ producer / ✅ consumer) — producer wired: loop surfaces
  last_suspend → AgentSession persists RunState(WAITING) + arms registry (5 tests on the durable side
  effect). Cold-start replay / precise resume_cursor remain deferred. See DECISIONS.md.
EVIDENCE: loop.py:1002 catches SuspendWorkflow → `return f"[WORKFLOW SUSPENDED] {reason}"` (a string).
  RunState( is constructed ONLY at store.py:188 (deserialize existing rows). Grep of all src/hachi:
  no RunState(status=WAITING) producer, no SuspendWorkflow catch in gateway/orchestrator/control_plane.
  workflow_tools.py:23-24 DOCSTRING asserts "the gateway layer persists RunState(WAITING) + arms the
  WaitConditionRegistry" — that wiring does not exist. The wake/recover/sweep subsystem
  (orchestrator.py:1682-1840, fastapi_app.py:2053-2164) therefore has zero inputs; GET /runs is always
  empty. Tests (test_suspend_workflow.py) assert only the exception contract, never the durable side
  effect — so CI stays green over a dead feature. [VERIFIED by direct grep, 2026-06-23]
ROOT CAUSE: unfinished seam — consumer half shipped (slices), producer half never wired.
RISK: a documented capability silently does nothing; "Hachi keeps working after the chat ends" is
  half-true (scheduler works; suspend/wait does not).
ACTION: implement — in AgentSession, detect suspend → store.upsert(RunState(status=WAITING, wait=...))
  → get_wait_registry().arm(run_id, wait). Add a test asserting the run row + arm, not just the exception.
PRIORITY: P0
```
```
FINDING P0-2: No durable per-interaction record → entire eval loop is unbuildable
PILLAR: P4 Eval & Observability
STATUS: ✅ RESOLVED 2026-06-24 (was ⚫) — interaction_log table + per-turn write + rating write-side
  shipped (14 tests). The eval substrate now exists; the /review UI + trajectory-eval suite that
  consume it remain follow-ups. See DECISIONS.md "Reassessment P0 sweep".
EVIDENCE: session_store.py:91-114 persists two flat `messages` rows (session_id, role, content,
  tool_name, ts). The target interaction_log {id, ts, user_input, agent_output, tool_calls,
  memory_hits, model_used, token_cost, rating, notes} does not exist. memory_hits (recalled facts,
  orchestrator.py:1286-1297) are injected then discarded. Per-turn cost is reconstructed by scanning
  the last 500 in-memory events (cli/main.py:1274) — ephemeral, capped, lost on restart. No rating
  column, no /review route (frontend has no review.tsx; no PATCH rating endpoint), no output-quality
  regression eval (the "benchmark" measures .og retrieval precision; assertion_eval validates skill
  preconditions).
ROOT CAUSE: storage designed for transcript replay + spend caps, not eval.
RISK: no row-level ground truth → no good/bad tagging, no failure mining, no per-turn audit, no
  regression safety net. A change that degrades answers ships green.
ACTION: add interaction_log table written once per turn from _chat_impl_inner (all fields already
  in-scope: user_input, response, recalled, cost delta, model_name, turn_id). Then layer rating +
  /review + a small trajectory-eval suite on top.
PRIORITY: P0
```
```
FINDING P0-3: Duplicate side effects on any retry (the idempotency deficit — Theme A)
PILLAR: P2 Tools / P5 Loop / Gateway
STATUS: ✅ RESOLVED 2026-06-24 (was 🔴) — idempotency layer shipped across all three layers
  (outbound tools + scheduler + durable ingress); 155 tests. See DECISIONS.md "Reassessment P0 sweep".
EVIDENCE: messaging_tools.py:56-206 (no idempotency/dedup on Slack/Discord/WhatsApp/Telegram send);
  scheduler.py:551-571 (add() mints fresh uuid4 per call, no name dedup); fastapi_app.py:1239,1301
  (POST /messages has no Idempotency-Key; grep src → zero). Turn-granular resume re-injects + re-runs
  (resume.py:31-50). LLM-retry + 4-worker tool pool + client reconnect all create retry paths.
ROOT CAUSE: design gap — idempotency solved for wake/resume orchestration, never for outbound effects
  or chat ingress.
RISK: duplicate user-visible messages, duplicate recurring schedules, duplicate whole turns + double
  spend. Directly erodes "acts safely on your behalf."
ACTION: thread a per-call idempotency key (provider-native where supported, else short-TTL dedup cache
  on (tool, recipient, content-hash)); add Idempotency-Key header on POST /messages persisted in
  SessionStore (replay returns the prior turn); dedup scheduler by (name, task) within a window.
PRIORITY: P0
```
```
FINDING P0-4: Docker Compose does not run (the headline self-host path is broken)
PILLAR: Deployment
STATUS: ✅ RESOLVED 2026-06-24 (was 🔴) — added frontend/Dockerfile (nginx + /api proxy), switched
  to writable named volumes at /home/hachi, 10 structural tests + a docker-smoke CI build job. Live
  build verified in CI (local daemon was down). See DECISIONS.md.
EVIDENCE: docker-compose.yml:21-24 builds ./frontend with dockerfile: Dockerfile, but
  `find frontend -iname Dockerfile*` → ZERO. Backend runs USER hachi (uid 10001, Dockerfile:9,20)
  while compose mounts volumes to /root/.config/hachi etc. (docker-compose.yml:15-18) — paths the
  non-root user cannot write. test_docker_assets.py:25-28 only asserts the string "8787" is present,
  so CI is falsely green. [VERIFIED by find, 2026-06-23]
ROOT CAUSE: untested asset + string-only test.
RISK: `docker compose up` fails on first invocation; the advertised "runs locally via Docker Compose"
  is false.
ACTION: add frontend/Dockerfile (nginx-serve dist), fix volume targets to /home/hachi/..., add a real
  compose-build smoke job to CI.
PRIORITY: P0
```

---

## 4. High-priority findings — **P1**

```
FINDING P1-1: Cross-user memory isolation is dead code (latent Critical)
PILLAR: P1 Memory / Security
STATUS: ⚪ acceptable TODAY under documented single-operator model / 🔴 if multi-user
EVIDENCE: account_id namespacing exists (memory_vault.py:259-353, ADV-023) but is never plumbed:
  boot constructs the vault with no account_id (orchestrator.py:2369-2381); the vault is a process
  singleton keyed on (brain_dir, backend, graph) only (shared_services.py:52-63); principal="session"
  is a placeholder (orchestrator.py:1255). Gateway HAS per-session ownership by token-hash
  (fastapi_app.py:684, control_plane.py:328) and there is one bearer token = one principal, so under
  the stated single-operator trust model (god-tier-plan.md: "one trusted operator per machine/VPS; do not claim
  multi-tenant") there is no breach today.
ROOT CAUSE: single-tenant assumption never re-examined; primitive built, never wired per-request.
RISK: the moment a 2nd user/token or hosted tenancy is added, two users share one core_memory /
  user_profile collection → cross-user PII recall + profile contamination.
ACTION: (a) document the hard single-tenant constraint prominently NOW; (b) plumb authenticated
  principal → account_id into vault construction AND the ProcessSharedServices fingerprint BEFORE any
  multi-user step. The auditor disagreement (P1 called it P0-catastrophic; Security called it ⚪-by-design)
  is reconciled here: latent-Critical, safe-today, must-guard-before-multi-user.
PRIORITY: P1
```
```
FINDING P1-2: No model tiering on the hot path (router built, bypassed for user turns)
PILLAR: P3 Routing
EVIDENCE: orchestrator.py:2724-2730 feeds the loop default_client(); router.select() is only called
  for side tasks (vision/title/compaction). No complexity scorer exists (grep "complexity"/"triage" →
  none on hot path). If default_model = a heavyweight, 100% of turns are heavyweight. Also: the
  cross-provider fallback chain is assembled inside select(), so user turns get NO failover on a
  provider outage.
ACTION: heuristic complexity classifier (length + tool-depth + keyword cues, no extra LLM call) →
  route the main turn through router.select(); this also grants user turns the failover chain.
PRIORITY: P1
```
```
FINDING P1-3: Daily budget cap is cosmetic (recorded + displayed, never enforced)
PILLAR: P3 Routing
EVIDENCE: orchestrator.py:1365 records per-turn into a durable daily ledger; get_daily_spend has
  exactly ONE caller — cli/main.py:1433 (the /spend/daily display). The loop's _budget_exceeded checks
  only the in-memory session tracker (resets per session), never today's ledger. [VERIFIED by grep]
ACTION: at run() start, if max_daily_cost_usd set, read get_daily_spend(today) and abort/downgrade when
  exceeded. (Per-session + per-turn caps ARE genuinely enforced — loop.py:713-718,847-852.)
PRIORITY: P1
```
```
FINDING P1-4: Web "Stop"/disconnect does NOT stop the server-side turn
PILLAR: P5 Loop / Gateway
EVIDENCE: loop.cancel() (threading.Event) is excellent and tested, but grep finds NO loop.cancel()
  reachable from gateway; control_plane's only _cancel is _cancel_schedule. The turn runs via
  anyio.to_thread.run_sync (fastapi_app.py:1303) without cancellable=True; turn_task.cancel() on
  disconnect cancels the awaiting coroutine but abandons the worker thread, which runs to completion.
  [VERIFIED — adjudicated against the Gateway auditor's contrary claim]
RISK: clicking Stop halts the stream display but cost keeps accruing server-side until a backstop fires.
ACTION: POST /sessions/{id}/interrupt → session.loop.cancel(); also call loop.cancel() in the
  disconnect handler. Consider per-tool-call timeouts in the pool wait.
PRIORITY: P1
```
```
FINDING P1-5: Memory writes are not durable across crash (user told "queued")
PILLAR: P1 Memory / Long-Running
EVIDENCE: fact-extraction/flush ride func= jobs (memory.py:228-260, 909-925) which the durable queue
  explicitly cannot recover and DELETES after a crash (queue.py:624-659); handle_extract_fact is a
  no-op seam (job_handlers.py:60-94). memory_tools.py:169 tells the user "queued for long-term
  consolidation" — true only of the enqueue, not the persist.
ACTION: inject an LLM client into JobContext and move fact-extraction to the handler_name durable path;
  or persist the raw exchange durably and re-extract on recovery.
PRIORITY: P1
```
```
FINDING P1-6: Production compaction discards the real summary (context loss on failover/resume)
PILLAR: P3 / Context Engineering
EVIDENCE: in the job-queue path the dropped middle is replaced by a static placeholder
  "[Context compacted asynchronously…]" (memory.py:960-963) and the generated structured summary is
  "not applied back to the live history" (memory.py:1090-1097). Correct only while one provider session
  holds the full context; breaks on failover/resume.
ACTION: apply the generated summary back into _history when the background job completes.
PRIORITY: P1
```
```
FINDING P1-7: Personalization is a substrate, not a product
PILLAR: P7
EVIDENCE: onboarding.py captures only provider/model/key + permission tier + memory toggle
  (the "API-key-only onboarding" anti-pattern). No UserProfileStore (grep → none); profile is a flat
  category-tagged string bag across 4 modules; no {identity, preferences, routines, knowledge,
  corrections[]} schema (no "routines"/"knowledge"/"corrections" categories); no export; corrections
  are destructive deletes with no CorrectionLog.
ACTION: UserProfileStore {get,set,correct,export} + CorrectionLog + a real personalization onboarding
  step/route capturing identity/prefs/routines → core_save_user_profile.
PRIORITY: P1
```
```
FINDING P1-8: MCP path has no retry / circuit-breaker; ToolError contract is dead
PILLAR: P2
EVIDENCE: mcp_client.py:1142-1178 call_tool is single-shot; resilience.py breaker is wired only to
  LLM/Speech/Search, never MCP → a flapping/mid-session-dead server is re-hit every turn. errors.py:104
  ToolError/MCPError {code, retryable} are defined but NEVER raised/caught (grep → 0 sites); tools return
  English error strings so is_error is under-reported and failures look like successful results.
ACTION: wrap MCPServerConnection.call_tool in resilient_call + per-server breaker + tool allow/deny
  filter + reconnect-on-dead; adopt a structured {ok, code, message, retryable} tool envelope.
PRIORITY: P1
```
```
FINDING P1-9: Phantom GitHub connector + orphaned backup/restore + no Windows CI
PILLAR: Connectors / Deployment / CI
EVIDENCE: GitHub registered OAuth (connector_registry.py:327-340) with NO integrations/github/ and no
  github tool (dead UI affordance). SessionStore.backup() (session_store.py:680) has zero callers/CLI;
  vault has no backup at all. CI test job runs ubuntu+macos only (ci.yml:17) — Windows (the dev platform)
  uncovered; 2 of today's failures are Windows cockpit tests.
ACTION: implement or remove the GitHub connector; add `hachi backup`/`restore` (session + vault export);
  add windows-latest to the CI matrix.
PRIORITY: P1
```

---

## 5. Technical debt — **P2** (ranked by blast radius)

1. **Window management is message-count, not token-based** (memory.py:864) → large tool outputs can blow the provider context window before the count trips: failure is a *cliff* (Anthropic 400 / truncation), not graceful. Add `count_tokens`-based triggering. — ✅ **DONE 2026-06-24** (P2-1): token trigger + `_MAX_ACTIVE_TOKENS` + bounded compaction passes.
2. **No memory decay / recency weighting; naive oldest-first eviction** (vault:1003-1084; LRU is an open TODO at :1024). Stale facts resurface; hot facts get evicted. `valid_until` exists but is never auto-populated.
3. **Episodic store is a raw transcript searched by leading-wildcard LIKE** (session_store.py:458) — no `{summary, entities, sentiment, outcome}`, no semantic episodic recall, full-scan at 1000s of sessions.
4. **Implicit learning stores raw PII** (memory.py:270-338) — redaction covers secrets, not names/emails/addresses; no PII-minimization/abstraction step; ChromaDB + sessions.db are plaintext on disk (no encryption-at-rest option). — *recall-side* secret/PII redaction ✅ already shipped (MED-009 `_redact_results` on `semantic_search`/`search_user_profile`); raw-PII-min on the *write* path + encryption-at-rest remain (design decision, flagged).
5. **No behavioral tests for brain.og constraints** (test_prompt_composer.py is structural-only) — a careless edit to the hard-constraint `::warning` block passes CI; classic persona drift ships silently. — ✅ **DONE 2026-06-24** (P2-5).
6. **EventBus is behaviorally shallow** — one reactive workflow (file.uploaded→extract); tool/memory/job lifecycle events are emitted but nothing reacts beyond read-model/telemetry fan-out. No trigger/rules engine.
7. **No dead-letter / re-drive in the job queue** (queue.py:439-460,857) — exhausted-retry jobs go FAILED then are deleted by cleanup; durable background work (memory) can be permanently lost across a longer outage. — ✅ **DONE 2026-06-24** (P2-7): `JobStatus.DEAD_LETTER` + `redrive_dead_letter()` + `hachi jobs dead-letter/redrive` CLI; cleanup preserves dead-letters.
8. **Sandbox is process-only** (sandbox.py, honestly labeled) — model-generated code runs at operator privilege; env-gated off by default. Needs a container/gVisor backend before default-on or untrusted code.
9. **No unified knowledge graph** — memory_graph is over `.og` files only; connectors are isolated tools with no cross-source entity linking. (Seam exists: connector reads could emit facts into the vault `attachments` collection.)
10. **Cold-start resume unimplemented** (resume.py:148-152) — a WAITING run survives restart at the state level but the wake fails if the in-memory session is gone (`HonestResumeError`). — ✅ **DONE 2026-06-24** (P2-10): rehydrates from the SQLite transcript via the existing `boot_agent(resume_session_id=…)` → `resume_from_session` path; `HonestResumeError` kept only when no runtime is attached (standalone CLI). Replay now has direct real-store coverage.
11. **Shallow readiness probe** (cli/main.py:1994) — only checks two files exist; a gateway with a dead provider key or crashed worker reports "ready". No compose healthcheck. — ✅ **DONE 2026-06-24** (P2-11): deep probe + compose healthcheck (stdlib `urllib`, not `curl`) gating the frontend's `depends_on`.
12. **Frontend has no client-side query cache** (no TanStack Query) — refetch-on-nav; and the leash allow/deny is matched by request *text* not request_id (chat.ts:976) — rare mis-association under concurrent identical requests.
13. **No latency/perf regression test** anywhere despite perf-sensitive streaming + vector retrieval; recall <100ms is architecturally right (prefetch, lazy Chroma) but never benchmarked. — ✅ **DONE 2026-06-24** (P2-13): structural (not wall-clock) regression guards — bounded recall top-k, lazy ChromaDB at `__init__`, bounded compaction passes, no unbounded history growth.

---

## 6. What's already excellent (do NOT break)

- **Claims honesty (93/100).** 6/6 sampled DECISIONS claims and 4/4 frontend→route mappings verified true against cited lines; the historical "claimed-done-but-absent" regression class is **not** reproduced. DECISIONS.md is self-critical (flags its own `TODO(issue9)`, Whisper-batch-only, deferred wiring). Keep this discipline.
- **Security (86).** Reference-quality SSRF defense (validate → pin resolved IP → `follow_redirects=False` → Host header, closing scheme/private-IP/redirect/DNS-rebind in one design); fail-closed everywhere (missing OAuth id raises, missing passphrase never writes plaintext, loopback-without-token is a startup error); Fernet+PBKDF2(390k)/OS-keychain secrets; unconditional untrusted-content framing; a `security-audit` command that flags its *own* weak points.
- **Loop backstops (P5).** Five independent runaway caps (iteration 15 / sub-agent 10; wall-clock 600s checked per-chunk *and* per-iteration; per-session + per-turn token/cost; an always-on 2M-token hard ceiling), each with a distinct event + result prefix, all regression-tested. Per-session serialization (`_chat_lock`) genuinely resolves the god-tier-plan.md shared-state race. Every `tool_use` is guaranteed a `tool_result` (no Anthropic 400s).
- **Memory engineering.** Tool-pair-safe compaction (`_find_safe_sliding_boundary`), cache-aware prompt split (frozen profile in cacheable prefix, volatile recall after the breakpoint), MemoryGuard prompt-injection scanning on every write, lazy ChromaDB + async prefetch.
- **Durable scheduler (80) + job queue.** DST-correct dependency-free cron, atomic cross-process-locked persistence, collapse-to-one missed runs, **actually wired to fire `session.chat()`** on a background thread. SQLite queue handles crash recovery + per-instance func-job ownership + WAL.
- **Multi-provider abstraction.** Exactly two authorized vendor-SDK import sites; 8 OpenAI-compat kinds + Anthropic + Gemini + Ollama, swap by config; real `ResilientClient` (retry + 3-state breaker + ordered fallback chain). This is a genuine competitive edge.
- **Frontend streaming (82).** Auth-capable SSE-over-fetch, idle-timeout zombie protection, React.memo-isolated streaming row, rAF-batched autoscroll, FOUC-free Markdown; strong trust signals (inline "leash" + approvals screen + retry-in-place).
- **Prompt-as-code (82).** `brain.og` versioned identity-as-data rendered in attention-ordered layers; single `prompt_composer` with an enforced no-ad-hoc-concatenation contract.

---

## 7. World-class gap analysis (honest, grounded)

| Capability | Hachi today | vs reference | Gap |
|------------|-------------|--------------|-----|
| Streaming UX | Token-coalesced, cursor-resume, FOUC-free | ChatGPT/Claude | **~1 generation** — mechanics near-parity; polish/scale |
| Memory / personalization | ChromaDB + threshold + recency; substrate only | ChatGPT memory | **~2 generations** — no episodic graph, no profile product |
| Tool reliability | Strong governance; idempotency + MCP-resilience gaps | Claude Code | **Behind** — improving reactively, not yet battle-hardened |
| Multi-provider | Anthropic/OpenAI/OpenRouter/Groq/DeepSeek/Gemini/Ollama | all reference | **At/ahead** — none are provider-agnostic by design |
| Observability | Opt-in OTel + cost ledger; **no eval loop** | hosted products | **Behind** hosted, **ahead** of most OSS agents |
| Onboarding / distribution | Good CLI + installers; 4 channels | OpenClaw ecosystem | **Materially behind** on ecosystem, fine on mechanics |
| Latency | Competitive; honestly bounded (voice diagnosed) | all | **Acceptable** |

**Bottom line:** the remaining distance to world-class is **eval maturity, memory/personalization
depth, tool-reliability hardening, and ecosystem/distribution** — *not* dishonesty and *not* missing
foundations.

---

## 8. Rolling roadmap (highest-leverage first)

### 30 days — close the trust-critical P0s + the cheapest last-mile wins
1. ~~**Idempotency layer** (P0-3): keys on side-effecting tools + `Idempotency-Key` on `POST /messages`. *Kills Theme A.*~~ ✅ **DONE 2026-06-24.**
2. ~~**Wire the suspend producer** (P0-1): catch `SuspendWorkflow` in `AgentSession` → persist `RunState(WAITING)` + `arm()`. *Brings the whole runs subsystem alive; ~1 connection.*~~ ✅ **DONE 2026-06-24** (loop surfaces `last_suspend`; producer persists + arms; 5 tests).
3. ~~**`interaction_log` table** (P0-2): one row/turn from `_chat_impl_inner`. *Unlocks rating, /review, regression eval, per-turn audit.*~~ ✅ **DONE 2026-06-24** (table + per-turn write + rating write-side; `/review` UI still to come).
4. ~~**Fix Docker Compose** (P0-4): real `frontend/Dockerfile` + writable volumes + compose-build smoke test.~~ ✅ **DONE 2026-06-24.**
5. ~~**Bridge web Stop → `loop.cancel()`** (P1-4) and **enforce the daily cap** (P1-3).~~ ✅ **DONE 2026-06-24.**
6. ~~**Add `windows-latest` to CI** (P1-9).~~ ✅ **DONE 2026-06-24.**

### 90 days — agent intelligence + durability + personalization  *(all ✅ DONE 2026-06-24)*
7. ~~**Hot-path model tiering** (P1-2): complexity classifier → `router.select()` (also gives user turns failover).~~ ✅ **DONE.**
8. ~~**Durable memory writes** (P1-5) + **apply the structured summary back into history** (P1-6).~~ ✅ **DONE.**
9. ~~**`UserProfileStore {get,set,correct,export}` + `CorrectionLog`** (P1-7).~~ ✅ **DONE** (backend substrate + save tool; personalization *onboarding wizard* + frontend deferred as feature work).
10. ~~**MCP retry/breaker + reconnect** (P1-8).~~ ✅ **DONE** (full `{ok,code,message,retryable}` envelope across all tool types + tool allow-list deferred to P2).
11. ~~**Cold-start resume** (rehydrate session from transcript)~~ ✅ **DONE 2026-06-24** (P2-10); ~~**`hachi backup`/`restore`** (P1-9)~~ ✅ **DONE.**

### 6 months — the eval loop + memory maturity + reactivity
12. ~~**Trajectory/regression eval suite + thumbs UI + `/review` page**~~ ✅ **DONE 2026-06-24** (E1 read/rating API + E2 eval report/runner + E3 /review screen); the **weekly failure report** automation + a record/replay `eval run` corpus remain as the next increments.
13. ~~**Token-budget window management** (P2-1) — remove the context-limit cliff.~~ ✅ **DONE 2026-06-24.**
14. **Memory decay/recency + LRU eviction + episodic `{summary,entities,sentiment,outcome}` store** (P2-2/3).
15. **Reactive EventBus automations** (inbound email/message triggers) (P2-6).
16. **Knowledge-graph seam** — connector reads emit facts into the vault; implement/remove GitHub (P2-9).
17. **PII minimization on implicit learning + encryption-at-rest option** (P2-4).

### 12 months — scale, trust, ecosystem
18. **Multi-tenant readiness** — plumb `account_id` through the vault + session principal (only if product calls for it) (P1-1).
19. **Container/gVisor sandbox backend** before default-on generated-code execution (P2-8).
20. ~~**Job-queue dead-letter + re-drive** (P2-7).~~ ✅ **DONE 2026-06-24.**
21. **Confidence/uncertainty gate + explicit plan/reflect loop phases** (P5).
22. **Hosted observability/eval dashboard + connector ecosystem expansion** (close the distribution gap).
23. **Self-improvement loop** — candidate-skill synthesis from trajectories → human review → publish (god-tier-plan.md Phase 5).

---

## 9. Top improvements by ROI (do these first)

| Rank | Change | Effort | Impact | Why |
|------|--------|:------:|:------:|-----|
| 1 | ~~Idempotency on tools + `POST /messages`~~ ✅ done | M | P0 | Removed the #1 trust risk (duplicate sends/turns) |
| 2 | ~~Wire suspend producer~~ ✅ done | S | P0 | Resurrected an entire built-but-dead subsystem |
| 3 | ~~`interaction_log` table~~ ✅ done | S–M | P0 | Keystone for rating/review/eval/per-turn audit |
| 4 | Enforce daily cap | S | P1 | One-line-ish; makes the settings-UI promise real |
| 5 | Bridge web Stop → loop.cancel | S | P1 | Stops cost accruing after the user hits Stop |
| 6 | ~~Fix Docker Compose + smoke test~~ ✅ done | S–M | P0 | Makes the headline self-host path actually work |
| 7 | Hot-path model tiering | M | P1 | Cost/latency on personal devices + user-turn failover |

> Items 2–6 are **last-mile wiring** (Theme B): small effort, large effect, because the hard parts
> already exist and are tested. Start there.

---

## Session delta — 2026-06-25 (HEAD `67a5196`, branch `reassess`)

Memory-depth + sandbox hardening (orchestrated Sonnet 4.6 subagents, Opus verifies + commits + gates).

- ✅ **M1 — Episodic memory store** (`26f3042`, pushed). New `episodic_memory` Chroma collection;
  `MemoryVault.upsert_episode` (deterministic per-session id, MemoryGuard scan→quarantine, `_vault_lock`
  + `_assert_open`, `_redact_results`) + `search_episodic` (top_k≤0 guard). Orchestrator captures a
  per-session digest (`build_episode_summary`) at shutdown and merges past-session recall into each
  turn (guarded by `episodic_top_k`, off-able). Replaces the old LIKE-scan with real semantic recall.
- ✅ **M2 — Memory decay** (`cc2fde8`, pushed). Optional recency re-ranking inside `_query_collection`:
  multiplicative `score = distance / 0.5**(age_days/half_life)` (parameter-free beyond the half-life),
  off by default (`memory.decay_half_life_days=None`). Over-fetch → distance-gate (unchanged, on RAW
  distance — never resurrects a filtered fact) → decay-rank → top_k, re-rank wrapped to fall back to
  relevance order on any error. `apply_decay=False` on `search_user_profile` (identity is timeless);
  `get_recent_facts`/`search_delegations` untouched. `_decay_score` is total/exception-free.
- ✅ **S1 — Pluggable sandbox backend + hardened Docker container** (`67a5196`, pushed). `SandboxBackend`
  ABC; `SandboxExecutor` is the `process` backend (preserved exactly, dev-grade); new
  `ContainerSandboxExecutor` runs scripts in an ephemeral container with `--network none --read-only
  --cap-drop ALL --security-opt no-new-privileges` non-root `--user`, memory/pids/cpus/tmpfs limits,
  script mounted read-only at `/work` (command built as a list, never `shell=True`). `create_sandbox_backend`
  selects via `HACHI_SANDBOX_BACKEND` and **fails fast** (never silent-downgrades) when `container` is
  selected without Docker. `sandbox_audit_finding` makes the audit honest: container+Docker → finding
  cleared; container without Docker → **HIGH** `sandbox.container_unavailable`; process/default → the
  existing **medium** `sandbox.process_backend`. 37 new tests (mock subprocess; no live daemon — a
  docker-smoke live job is the follow-up). `core/sandbox.py` stays strict-mypy 0.

**Verification.** Each shipped behind: targeted tests + strict-mypy-gate (36 files, 0) + ruff + a full
`pytest` gate. M1 gate 3809/0; M2 gate green (memory path). S1 full gate: **1 failed / 3867 passed** —
the single failure is `test_cockpit_gaps::TestMemoryCRUD` (a live in-process-gateway memory-CRUD test
that boots real gateways + creates live sessions; a *different* test in the class fails on isolated re-run
→ pre-existing live/timing flakiness, S1 touches no gateway/session/memory code).

**RESOLVED — test-suite hermeticity/isolation (FLAKE, commit `afe8138`).** The deferred pass landed,
re-diagnosed from scratch on `reassess` (the `flake-wip` branch's fixes were superseded — see below).
Full suite now **3867 passed / 21 skipped / 0 failed**, deterministic, ~8× faster (4:40 vs the
leaked-key baseline crawl). Four independently root-caused layers:
1. **Secret leak / nondeterminism** — import-time `.env` autoload pulled real keys into `os.environ`,
   flipping import-time skipif guards *and* making `test_cockpit_chat_live` issue billed LLM calls every
   run. Gated behind `HACHI_DISABLE_DOTENV_AUTOLOAD` (prod default unchanged); conftest sets it.
2. **`os.environ` leak** — tokoboros shim writes `HACHI_*` past monkeypatch's undo → diff-based
   `os.environ` restore fixture in conftest.
3. **chromadb "poison"** — the real root cause `flake-wip` never cracked: `patch.dict(sys.modules, …)`
   drops modules *first-imported inside the block*; `_build_extractor_chain` lazily first-imports
   chromadb there, wiping its **PyO3 native submodules** — and a native ext cannot re-init (`cannot load
   module more than once per process`), so later vault/embedding tests silently degrade. `flake-wip`'s
   `_restore_chromadb_modules` fixture was *causing* this, not fixing it. Fix: warm chromadb at conftest
   import (so it survives every snapshot) + fix the offending test to never restore a `MagicMock`.
4. **"Cockpit flakiness"** — NOT a key issue (12/13 pass keyless); `POST /sessions` cold-boot exceeds
   GatewayClient's 15s timeout. Made the client timeout env-configurable
   (`HACHI_GATEWAY_CLIENT_TIMEOUT`; prod stays 15s); conftest grants 90s. This fixes the S1 gate's
   single `test_cockpit_gaps` failure noted above. `flake-wip`'s blanket `skipif` was wrong — it would
   have skipped 12 passing tests. Per-layer detail in `DECISIONS.md`.
