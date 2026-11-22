# Hachi — Consolidated Forward Backlog

**Compiled 2026-07-05.** One board that fuses the 2026-07-03 production audit
([`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md), [`DETAILED_FINDINGS.md`](DETAILED_FINDINGS.md),
[`GAP_ANALYSIS.md`](GAP_ANALYSIS.md), [`TASKS.md`](TASKS.md)) with the 2026-07-05 competitive review
([`../../strategy/2026-07-05-competitive-review/`](../../strategy/2026-07-05-competitive-review/README.md))
into a single, cold-start-able task list.

**Why this file exists.** [`TASKS.md`](TASKS.md) tracked the *reactive* audit remediation and is now
essentially closed. What was never turned into executable tasks is the *proactive* strategy — the
god-tier bets and the 5 strategic bets. This board captures both the audit's residual open items and
that forward work, sized and scoped so an agent (or a fresh session) can pick up the top-of-stack task
without re-reading the whole engagement.

> **No code has been changed to produce this board — it is planning only.** Each task below still owes
> its own failing-test-first / gate-green execution per [`CLAUDE.md`](../../../CLAUDE.md).

---

## 1. Where we are (state snapshot)

| Fact | Value |
|---|---|
| Branch / HEAD | `frontend-review` / see T0 + A3 commits below |
| Audit remediation ([`TASKS.md`](TASKS.md)) | **Done & committed** — all P0/P1/P2/P3 + S1–S3 + A3 (BB-72) |
| Gate (last independent run, 2026-07-05) | **preflight 12/12 green**; `pytest` **4251 passed / 21 skipped / 0 failed** |
| Uncommitted | Nothing — T0 and A3 both committed. |

**The one-paragraph thesis** (compiled from the audit + review): the *engine* is real and rare
(governed ReAct loop, in-loop cost caps, hardened gateway, durable job queue, `.og`, 4245 passing
tests). The audit found the *headline features* were hollow at the exact points the brand rests on —
and remediation has now **made those claims true** (auto-memory, file tools, benchmark honesty, slash
commands, governance-lint-that-blocks, web approvals). The competitive review then found the *framing*
is out of date: "governance + visibility" is now **table stakes** (all five competitors ship it;
OpenClaw shipped memory, Hermes shipped governance/audit), not an open quadrant. The durable move is to
convert governance from a copyable feature into a **verifiable, owned, enforced trust substrate** — plus
*reliable* memory and the `.og` skill-as-artifact story. Workstreams B–F below are that move.

---

## 2. Open items carried over from the audit

Everything else in [`TASKS.md`](TASKS.md) is Done. These three are the only remainder.

| ID | Item | Type | Status | Blocking question for the owner |
|---|---|---|---|---|
| **H9** | `pipx install hachi-og` 404s — package not on PyPI | Release/ops | **Blocked (decision)** | Cut `0.1.0` to PyPI now, or keep the README leading with `install.sh`/`git clone` and mark pipx "coming soon"? Needs PyPI creds + a go/no-go. |
| **M10** | `tokoboros` compat shim reintroduced (`cli/main.py:151-184`, `gateway/workspace.py:49-90`) — violates CLAUDE.md's anti-shim rule | Decision | **Blocked (decision)** | Was it added to cover a real self-heal/migration need? Either remove it or formally reverse the CLAUDE.md rule. Check `git blame` on those lines first. |
| **A3** | Session/data retention sweep never wired (`cleanup_completed()` defined 3×, called by zero production code); `jobs.db`/`interaction_log`/`idempotency_keys`/`daily_spend`/checkpoints grow monotonically | Code | **Done** (2026-07-05, BB-72) | — |

---

## 3. How to use this board (read before picking a task)

1. **T0 first** (commit the audit + strategy docs), then **decisions in §2** unblock A1/A2.
2. Otherwise pick the highest task whose **Deps** are all done and whose **Owner-decision** column is clear.
3. Work it per [`CLAUDE.md`](../../../CLAUDE.md): failing regression test first (bugs) → minimal change →
   `docs/bug-bank.md` entry (bugs) → run the relevant gate. Use `regression-guard` for bug-shaped work,
   `Plan` for the spec-first tasks (B1, F1), `scope-sentinel` before commit.
4. **Sequencing guard (hard rule, from [09 §0](../../strategy/09-execution-plan.md) and the founder's own
   "fix → benchmark → tell"):** no new public/marketing claim ships before the capability behind it is
   real and gate-green. Every task here is present-tense-honest or explicitly labelled roadmap.
5. Sizes are **estimates** (S ≈ ≤1 day, M ≈ 2–4 days, L ≈ 1–2 wk, XL ≈ 2 wk+), single-dev, not commitments.
6. Discover new work → append a task row; never silently fold it into another.

**Cold-start reading order:** this §1–§2 → [`GAP_ANALYSIS.md`](GAP_ANALYSIS.md) §5/§6 (the good-to-have
+ god-tier source) → [`../../strategy/2026-07-05-competitive-review/04-first-principles-and-bets.md`](../../strategy/2026-07-05-competitive-review/04-first-principles-and-bets.md)
(the 5 bets these tasks execute) → the specific task block below.

---

## 4. Task index

Priority key: **P0** = finish making the claims true / unblock; **P1** = the durable-moat bets;
**P2** = differentiators; **P3** = breadth/polish. "Bet" maps to the review's §04 strategic bets.

| ID | Title | WS | Bet | Priority | Size | Deps |
|---|---|---|---|---|---|---|
| **T0** ✅ | Commit the audit + competitive-review docs | — | — | P0 | S | none |
| **A1** | Cut `hachi-og 0.1.0` to PyPI (= H9) | A | 1 | P0 | S | decision |
| **A2** | Resolve the tokoboros shim (= M10) | A | 1 | P0 | S | decision |
| **A3** ✅ | Wire the retention/prune sweep (= H8 deferred) | A | 1 | P1 | M | none |
| **A4** | Real OAuth token consumption for Notion/Slack (= H5 bridge) | A | 3 | P2 | M | none |
| **A5** | Claim-vs-code truth-pass re-verification | A | 1 | P1 | S | A1–A4 |
| **B1** | Trust-receipt design + threat model (spec) | B | 2 | P1 | M | none |
| **B2** | Append-only hash-chained signed event ledger | B | 2 | P1 | L | B1 |
| **B3** | `hachi audit export` / `verify` CLI | B | 2 | P1 | M | B2 |
| **B4** | "What it did today" receipt view (web + TUI) | B | 2 | P2 | M | B2 |
| **C1** | Assertion enforcement at skill-load / opt-in gate | C | 3 | P1 | M | none |
| **C2** | `device-permissions.og` policy-as-code at the PermissionGate | C | 3 | P1 | L | C1 |
| **C3** | Unify spend-cap + policy into one enforcement point | C | 3 | P2 | M | C2 |
| **D1** | Memory-reliability harness (cross-run determinism) | D | 4 | P1 | M | none |
| **D2** | Diff-able `.og` memory + inspection surface | D | 4 | P2 | L | D1 |
| **D3** | Editable, verifiable user-model (G3) | D | 4 | P2 | L | D1 |
| **E1** | Goals / work-inbox (Kanban) over the job queue | E | 5 | P2 | L | none |
| **E2** | Consequence-boundary approvals (plan + blast-radius) (G4) | E | 5 | P1 | L | F1 |
| **E3** | One-command import bridge (OpenClaw / Hermes → Hachi) | E | 5 | P2 | M | D1 |
| **F1** | Static blast-radius analyzer for a skill/pack (G2) | F | 5 | P1 | L | none |
| **F2** | `.ogpack` install with consent-sheet / scope-diff (G2) | F | 5 | P2 | L | F1 |
| **F3** | Portable sovereignty export (memory+skills+audit) (G5) | F | 2 | P2 | M | B2 |
| **G1** | De-facade the channels people actually route life through | G | — | P3 | L | none |

**Dependency spine (what unblocks what):**

```
T0 ─► (commit) 
decisions ─► A1, A2
A3, A4 ───────────────────────────────► A5 (truth-pass)
B1 ─► B2 ─┬─► B3
          ├─► B4
          └─► F3
C1 ─► C2 ─► C3
D1 ─┬─► D2
    ├─► D3
    └─► E3
F1 ─┬─► F2
    └─► E2   (needs a plan/blast-radius primitive to gate on)
E1 (independent)      G1 (independent)
```

---

## 5. Workstream A — finish "make the claims true"

The audit's must-have #1/#5/#6 are mostly closed; these are the residuals.

### A1 — Cut `hachi-og 0.1.0` to PyPI  *(= audit H9 · P0 · S · needs decision)*
- **Goal:** the README's most prominent install path (`pipx install hachi-og`) works.
- **Why:** first-contact install failure is the highest-signal credibility loss for an OSS launch.
- **Do:** confirm `release.yml` is publish-ready; tag `v0.1.0`; publish; smoke-test `pipx install hachi-og`
  in a clean venv; flip the README from "coming soon" to the real command.
- **Owner decision (gate):** publish now vs. defer. If defer → the *code* task is the README hedge
  (lead with `install.sh`/`git clone`, mark pipx "coming soon"). **Do not publish unilaterally.**
- **DoD:** `pipx install hachi-og` resolves and `hachi --version` runs in a fresh environment; README matches.

### A2 — Resolve the tokoboros compat shim  *(= audit M10 · P0 · S · needs decision)*
- **Goal:** stop violating CLAUDE.md's "no tokoboros shims" rule, or reverse the rule deliberately.
- **Why:** three reviewers flagged it independently; it's the textbook "a rule makes the task impossible → STOP and ask" case.
- **Do:** `git blame`/`git log -p` `cli/main.py:151-184` + `gateway/workspace.py:49-90` to learn *why* it
  returned (self-heal for existing installs?). Then either remove it (+ regression test that old paths
  still resolve) or record an ADR/DECISIONS.md entry reversing the rule.
- **Owner decision (gate):** remove vs. formally sanction. **Do not remove unilaterally** until the "why" is known.
- **DoD:** shim gone with tests green, *or* a DECISIONS.md entry + CLAUDE.md edit that legitimizes it.

### A3 — Wire the retention / prune sweep  *(= audit H8 deferred · P1 · M)*
- **Goal:** installs stop growing monotonically; `cleanup_completed()` actually runs.
- **Why:** a "governed" product that never prunes `interaction_log`/`idempotency_keys`/`jobs.db`/
  `daily_spend`/checkpoint snapshots leaks data and disk forever — contradicts the promise.
- **Do:** add a retention sweep to the worker's idle loop (config-driven TTLs, default conservative);
  call the existing `cleanup_completed()`; cover `session_store` + `jobs` + edit-undo checkpoints.
- **DoD:** failing test proving unbounded growth first; sweep prunes rows older than TTL; gate green; BB entry.
- **Refs:** `PRODUCTION_READINESS.md` §4 H8; `session_store.py`, `jobs/`, worker idle loop.

### A4 — Real OAuth token consumption for Notion/Slack  *(= audit H5 deferred bridge · P2 · M)*
- **Goal:** connecting Notion/Slack via the OAuth UI yields *working* tools (not tools that still ask for a pasted key).
- **Why:** H5 was honesty-patched in docs ("Notion/Slack via API tokens"); the real fix — bridge the OAuth
  callback to the service vault keys — was deferred. Closing it makes "native integrations" true, not reworded.
- **Do:** bridge `connector_registry.py` (`auth_type="oauth2"`) → the `CredentialVault` keys the services
  actually read (`notion_api_key`/`slack_bot_token`); have `notion/service.py`/`slack/service.py` call
  `OAuthTokenStore.load()` at request time; add an apikey fallback where OAuth isn't configured.
- **DoD:** integration test: OAuth-connect → tool call authorizes without a pasted key; gate green; BB entry.
- **Refs:** `PRODUCTION_READINESS.md` §4 H5; `integrations/notion/service.py`, `slack/service.py`, `connector_registry.py`, `oauth_flow.py`.

### A5 — Claim-vs-code truth-pass re-verification  *(= must-have #5 · P1 · S)*
- **Goal:** a final sweep confirming every present-tense README/ARCHITECTURE/docs claim is true post-remediation.
- **Why:** the audit's core lesson was claim-vs-code drift; after ~30 fixes, re-confirm nothing new drifted.
- **Do:** walk the README promise table + ARCHITECTURE.md route/module claims against current code; fix or
  label any residual. Light re-run of the audit's "Promise vs reality" table (§3).
- **DoD:** a short checklist appended here (or to `AUDIT.md`) with each headline claim marked verified-today.
- **Deps:** run after A1–A4 so install/integration claims are settled.

---

## 6. Workstream B — the trust receipt  *(Bet 2 · G1 · the durable moat)*

The review's #2 bet and its single most-defensible, hardest-to-copy differentiator: turn the existing
typed `runtime_events` + `interaction_log` + cost/permission decisions into a **signed, append-only,
exportable, independently-attestable** record of everything the agent did and why. *Falsifiable test no
competitor passes today (G1):* can a user hand a third party a complete, replayable, tamper-evident log
their agent produced, and have it verified without trusting the vendor?

### B1 — Trust-receipt design + threat model  *(P1 · M · spec-first)*
- **Goal:** a written design: event schema, hash-chain/signature scheme, key management, export format, what "attestable" means, and the threat model it defends (tamper, omission, replay).
- **Do:** use the `Plan` agent; inventory today's `runtime_events`/`interaction_log`/cost/permission
  records; decide append-only storage + per-record hash chain + signing key location (sovereign/local).
  Explicitly scope out anything requiring a third-party trust anchor for v1.
- **DoD:** design doc under `docs/architecture/` + an ADR; reviewed against the honesty guardrails.
- **Note:** keep all framing in product/verifiability terms, not security-incident terms (review guardrail).

### B2 — Append-only, hash-chained, signed event ledger  *(P1 · L · deps B1)*
- **Goal:** every action, memory write, skill mutation, and dollar lands in an append-only ledger where
  each record chains to the prior (tamper-evident) and the chain is signed.
- **Do:** implement per B1 over the existing event stream; make writes fail-closed; add a chain-verify routine.
- **DoD:** tests prove (a) records are append-only, (b) any edit/deletion is detectable, (c) a full run replays from the ledger; gate green; BB entry.

### B3 — `hachi audit export` / `hachi audit verify` CLI  *(P1 · M · deps B2)*
- **Goal:** a user can export a portable receipt and anyone can verify it offline.
- **DoD:** `export` produces a self-contained artifact; `verify` validates the chain + signature on a machine
  that never ran the agent; round-trip test in CI.

### B4 — "What it did today" receipt view  *(P2 · M · deps B2)*
- **Goal:** a sub-60-second demo surface (web + TUI) that renders the ledger as a human-readable activity feed with reasons + blast-radius per action.
- **DoD:** view reads the real ledger (no demo data — cf. the audit's optimistic-only frontend findings); e2e test.

---

## 7. Workstream C — governance: honor-system → enforced  *(Bet 3 · the tagline made literal)*

The audit's M2 fix made **lint block a skill write**; the deeper bet is policy-as-code that *physically*
blocks at the gate, so "enforced by code, not by vibes" is true for actions and assertions, not just writes.

### C1 — Assertion enforcement at skill-load (opt-in gate)  *(P1 · M)*
- **Goal:** `::assertions` are checked at load and can *block* (not just be checkable via an optional tool).
- **Do:** the bounded evaluator already exists (`core/assertion_eval.py`); add an opt-in enforcement point
  in the load path that fails closed when an assertion fails; default conservative; config-gated.
- **DoD:** failing test (assertion violation currently loads) → then blocks; gate green; BB entry.
- **Refs:** `PRODUCTION_READINESS.md` §4 M2; `og_engine/engine.py` resolve/load path; `core/assertion_eval.py`.

### C2 — `device-permissions.og` policy-as-code at the PermissionGate  *(P1 · L · deps C1)*
- **Goal:** a declarative policy file the `PermissionGate` evaluates so allow/deny is data, not per-action prompts.
- **Do:** define the policy schema; wire evaluation into `permissions.py` at call time; deny wins; ship a sane default policy.
- **DoD:** policy denies/permits deterministically at the gate; tests cover precedence + fail-closed; gate green.

### C3 — Unify spend-cap + policy into one enforcement point  *(P2 · M · deps C2)*
- **Goal:** one place where cost caps and policy are both enforced, so "the agent physically cannot exceed X" is one auditable seam.
- **DoD:** spend-cap + policy share an enforcement path; the trust-receipt (B2) records each decision; tests.

---

## 8. Workstream D — memory reliability + user model  *(Bet 4 · G3)*

C1 (audit) fixed the *no-op*. The bet is **reliability**: beat OpenClaw's documented cross-install
inconsistency ([GAP_ANALYSIS.md](GAP_ANALYSIS.md) §6 G3) with deterministic, inspectable, diff-able memory.

### D1 — Memory-reliability harness  *(P1 · M)*
- **Goal:** tests that assert memory is deterministic and consistent across runs/restarts/installs.
- **Do:** a harness that seeds facts, restarts the process, and asserts identical recall; run in CI.
- **DoD:** harness catches a seeded inconsistency; green on current code or files the gap as a task.

### D2 — Diff-able `.og` memory + inspection surface  *(P2 · L · deps D1)*
- **Goal:** memory as diffable `.og` a user can read and `git diff`, with a UI to inspect it.
- **DoD:** memory serializes to stable `.og`; a view renders it; diff of two snapshots is meaningful; tests.

### D3 — Editable, verifiable user-model  *(P2 · L · deps D1)*
- **Goal (G3 falsifiable test):** open what the agent believes about you, edit a wrong belief, and *verify the correction changes future behavior*.
- **Do:** build on the existing hard-capped `user_profile`; add edit + a test proving the edit propagates into the next turn's system prompt.
- **DoD:** correction round-trip test; gate green.

---

## 9. Workstream E — legibility for long-running work  *(Bet 5 · G4)*

The Hermes-Kanban lesson: autonomy must be *visible*. Hachi has the job queue + `/runs` to back this.

### E1 — Goals / work-inbox (Kanban) surface  *(P2 · L)*
- **Goal:** a board that shows queued/running/done delegated work, backed by the real job queue + `/runs` (not demo data).
- **DoD:** board reflects live `/runs` state; actions call the gateway; e2e test.

### E2 — Consequence-boundary approvals  *(P1 · L · deps F1)*
- **Goal (G4):** batch intent into a reviewable plan with a **blast-radius estimate**, and interrupt the user *only* for irreversible/expensive/external actions — fewer, higher-signal prompts, not a firehose.
- **Do:** needs F1's blast-radius primitive; produce a plan artifact; gate approval on consequence, not every file write.
- **DoD:** a multi-step task surfaces one plan + one approval at the consequential step; tests; ties into B2's receipt.

### E3 — One-command import bridge  *(P2 · M · deps D1)*
- **Goal:** strip switching cost — import OpenClaw/Hermes `MEMORY.md`/`SKILL.md` + memory into Hachi's stores in one command.
- **DoD:** `hachi import <openclaw|hermes> <path>` maps their memory/skills into `.og` + the vault; round-trip test; docs.

---

## 10. Workstream F — `.og` as flagship: provable blast-radius + portability  *(G2 · G5 · Bet 5)*

Hachi's one genuinely novel, hard-to-copy bet: typed, scoped, permission-declarative skills make a static
"what could this touch" proof *possible* — the structurally-correct answer to marketplace-poisoning that
plain-markdown competitors structurally cannot match.

### F1 — Static blast-radius analyzer  *(P1 · L)*
- **Goal (G2 falsifiable test):** given a skill/pack, compute a *provable upper bound* on what it can read, write, spend, and reach — **before** it runs.
- **Do:** analyze `.og` typed blocks + declared scopes/permissions; emit a structured blast-radius report; no execution required.
- **DoD:** analyzer produces a sound over-approximation for the shipped skills; tests on crafted skills; feeds E2 + F2.

### F2 — `.ogpack` install with consent-sheet / scope-diff  *(P2 · L · deps F1)*
- **Goal:** installing a third-party pack shows a consent sheet + scope-diff (what new reach it gains) sourced from F1 — "skills are data, no install-time execution."
- **DoD:** install flow renders the scope-diff and requires consent; tests; docs.

### F3 — Portable sovereignty export  *(P2 · M · deps B2)*
- **Goal (G5 falsifiable test):** export governed memory + skills + audit history as a provably-yours artifact and move it to another host.
- **DoD:** `hachi export --sovereign` bundles `.og` skills + memory + the B2 ledger; a second install verifies + adopts it; round-trip test.

---

## 11. Workstream G — channel breadth reality  *(must-have #7 · P3)*

### G1 — De-facade the channels people actually route life through  *(P3 · L)*
- **Goal:** WhatsApp/Telegram/Slack/email are real end-to-end, not shallow/facade transports (OpenClaw ~23, Hermes ~10; Hachi ~4–5 and thin).
- **Do:** pick the 3–4 users actually route through; make send+receive real; drop or clearly-label the rest.
- **DoD:** each supported channel has a live send/receive integration test; docs list only what works.
- **Refs:** [GAP_ANALYSIS.md](GAP_ANALYSIS.md) §4 must-have #7; audit H5.

---

## 12. Decisions required from the owner (consolidated)

Nothing in Workstreams B–G is blocked on you — they're engineering. These four gate only their own tasks:

1. **H9 / A1 — PyPI release:** cut `0.1.0` now, or defer and hedge the README? *(gates A1)*
2. **M10 / A2 — tokoboros shim:** remove, or formally reverse the CLAUDE.md rule? *(gates A2)*
3. **Push / commit cadence:** the audit + review docs are uncommitted and nothing is pushed. T0 commits the
   docs locally; a push to any shared branch still needs your explicit OK (push-lock). *(gates sharing)*
4. **Sequencing after A-block:** which durable bet leads once the claims are fully true — the **trust
   receipt (B)**, **enforced governance (C)**, or **memory reliability (D)**? The review recommends **B**
   (most-defensible, sub-60s demo, compounds); C and D are close seconds. *(orders P1 work)*

---

## 13. Provenance — where each task came from

| Source doc | Contributes |
|---|---|
| [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md) §4 | H9→A1, M10→A2, H8→A3, H5→A4, M2→C1; the state snapshot + gate numbers |
| [`TASKS.md`](TASKS.md) | Confirmation that C1–C4/H1–H8/M1–M14/L1–L4/S1–S3 are Done; the two blocked items |
| [`GAP_ANALYSIS.md`](GAP_ANALYSIS.md) §5/§6/§8 | Good-to-have + god-tier G1–G5 → Workstreams B/C/D/E/F/G; must-have #7 → G1 |
| [`../../strategy/2026-07-05-competitive-review/04-first-principles-and-bets.md`](../../strategy/2026-07-05-competitive-review/04-first-principles-and-bets.md) | The 5 strategic bets → the Bet column + the WS grouping + the §12.4 recommendation |
| [`../../strategy/09-execution-plan.md`](../../strategy/09-execution-plan.md) | The agent-protocol / sequencing-guard conventions this board reuses (its Phase-1 "make claims true" is now the audit's closed work) |

_This board supersedes the forward-looking (Phase 2+) portions of `09-execution-plan.md` for planning
purposes: 09's Phase 1 was "make the claims true," which the 2026-07-03 audit remediation has now
delivered. Re-derive 09's later phases from these workstreams when the A-block closes._
