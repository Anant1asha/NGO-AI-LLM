# Phase 8 — Roadmap Synthesis

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy · **Date:** 2026-06-12
**Consolidates:** [01](01-architecture-review.md) (R1–R20) · [02](02-object-graph-eval.md) (P0s +
benchmark spec) · [03](03-competitive-and-positioning.md) (positioning, C1–C3) ·
[04](04-memory-redesign.md) (M0–M4) · [05](05-agent-platform.md) · [06](06-ux-redesign.md) ·
[07](07-future-and-growth.md).
**Effort unit:** ideal engineering-days, one senior dev familiar with the repo. **Conf.** = estimate
confidence. **Leverage** = positioning-impact per dependency-adjusted day.

**The strategic spine** (one sentence): *make the governance claims true (30 d) → prove them and make
them visible (90 d) → compound them into platform + memory moats (1 yr) → own the format layer (3 yr)*
— with marketing strictly sequenced **after** the fixes it depends on (Phase 3 risk #2, Phase 7 §4.4).

---

## 1. 30-Day Quick Wins — "Make the claims true"

Budget ≈ 17 of ~20 working days (1 engineer). Every item is small, cited, and removes a way the
positioning can be falsified.

| # | Item | Rationale → source | Impact | Cmplx | Effort (conf.) | Deps | Risk / rollout |
|---|---|---|---|---|---|---|---|
| 1 | Serialize turns per session (lock/inbox in `AgentSession.chat`) + 2-thread regression test | Only corruption-class bug; all 4 surfaces exposed → 01/TD-1 | **H** correctness | Low | 1 d (high) | — | Behavior: concurrent msgs queue; note in changelog |
| 2 | Unblock gateway event loop (sync-def or `to_thread` for chat/boot routes) | SSE/health stall during turns → 01/TD-4 | H reliability | Low | 0.5 d (high) | — | None — semantics unchanged |
| 3 | Loud memory failures: kill thread-fallback, route via queue, surface `jobs/failed` + TUI badge; vault methods raise/typed-return | "Never say remember" promise currently fails silently → 01/TD-5, R4 | **H** trust | Med | 2 d (high) | — | Flag `memory.strict_errors` default on |
| 4 | **Retrieval v2**: stopword guard, stem/prefix match, BM25 rank, confidence tie-break, calibrated no-match | P@1≈23% probe is the moat's falsifier → 02 §2.3, P0 | **H** moat | Med | 3 d (high) | — | A/B via env flag; probe set becomes regression test |
| 5 | Qualified node IDs + collision error; exclude `brain.og` from skill search | Shipped library self-collides (identity ×6) → 02 §2.2 | **H** moat | Med | 2 d (med-high) | — | Migration shim resolves bare names when unique |
| 6 | Shipped-skill compliance: ::meta/::index everywhere, dense ≤30, synonym keywords, ≥1 requires chain per pack; `lint default_skills` CI job (errors block) | 23/29 non-compliant; dogfood the format → 02 §2.1, P0 | H moat | Low | 2 d (high) | #5 | Pure content + 1 CI job |
| 7 | benchmark.md honesty pass: disclose first-party paper, add cached-dump crossover caveat, drop 95.3% reliance | Credibility pre-launch → 02 §2.4/§7 | M trust | Low | 0.5 d (high) | — | Docs only |
| 8 | SECURITY.md + disclosure policy; ARCHITECTURE.md (from 00-recon); `good-first-issue` batch from TD register | Governance project without a security policy → 07 §4.1 | M credibility | Low | 1.5 d (high) | — | Docs only |
| 9 | Path unification (usage DB, RoleResolver → platformdirs w/ legacy shim) | 01/TD-10 | M correctness | Low | 0.5 d (high) | — | Shim reads legacy dir |
| 10 | Re-enable `frontend-contract` CI; fix CLAUDE.md (SvelteKit→TanStack, contract claim, memory description) | Doc-vs-code drift D2/D3/D8 → 00 §9 | M DX | Low | 1 d (high) | — | CI may need one type regen |
| 11 | Graceful iteration-limit exit (partial summary + `status=incomplete`) | 01/R15; QA-flagged | M UX | Low | 0.5 d (high) | — | — |
| 12 | 500-handler correlation-id (no `str(exc)` leak); compose requires token off-loopback | 01/TD-15 | M security | Low | 1 d (high) | — | — |
| 13 | Move `chatgpt-web` provider to opt-in extra w/ risk README | OSS/ToS surface → 01/TD-16 | L risk | Low | 0.5 d (high) | — | Breaking for its users — changelog |
| 14 | Scoped mypy gate (strict on core/og_engine/gateway, blocking on PRs) | Honest gates → 01/TD-6 (b-variant) | M DX | Low | 0.5 d (high) | — | Burn-down continues opportunistically |

**Exit criteria for the month:** probe suite ≥0.8 P@5 on K+P queries ▶-reproducible; zero collisions
on boot; concurrent-chat test green; `jobs/failed` visible in TUI; CI: lint+contract+mypy(core) blocking.

## 2. 90-Day Roadmap — "Prove it and show it" (Q3 2026)

Assumes 1.5–2 engineers (or ruthless use of the cut-line). Ordered by leverage; ★ = cut-line if
capacity is 1 dev.

| # | Item | Rationale | Impact | Effort (conf.) | Deps | Rollout |
|---|---|---|---|---|---|---|
| 1 | **Streaming end-to-end** + Esc-interrupt (cooperative cancel) | Largest perceived gap; required by tui-product-brief.md:106/121 → 01/R3, 06 §10 | **H** UX/competitive | 6–10 d (med) | 30d#1 | Flag per provider; TUI first, SSE next, OpenAI-facade `stream:true` last |
| 2 | **Durable SQLite job queue + resident worker** (job registry indirection) | Memory promise + always-on → 01/R5 | **H** reliability | 3–4 d (high) | 30d#3 | Migration: drain in-memory on upgrade |
| 3 | **Benchmark suite v1** (arms A–F, M1/M2/M3/M7; corpora S+M; CI retrieval gate) + **publish results post** | The proof apparatus → 02 §8; growth loop 1 → 07 §4.3 | **H** moat/growth | 8–12 d (med) | 30d#4–6 | Live-LLM subset behind budget flag (decision D-4) |
| 4 | **Memory graph M0+M1** (FTS5 index over memory/*.og; typed extractor; Chroma import) | Hermes-parity recall + files-as-memory story → 04 §7 | **H** product | 7–12 d (med-high) | #2, 30d#3/#5 | `memory.graph=true` flag; converter on first boot |
| 5 | E2E loop harness (scripted fake LLM, multi-tool/multi-turn + concurrency regressions) | Test blind spot under all of the above → 01/R9 | H quality | 2–3 d (high) | — | CI per-PR |
| 6 | Pack format + installer + consent sheets (closes D9) | Platform substrate; scope model → 05 §6–7 | H platform | 4–6 d (med-high) | 30d#5 | `.ogpack` v0; index repo (Stage 1) |
| 7 | Workflow Composer + read-only-gate dry-run + condition triggers | NL automation visible → 05 §5 | H product | 5–8 d (med) | #2 | Telegram + TUI preview cards |
| 8 | TUI: status strip + Spend + Ops timeline screens | Governance has pixels; data exists → 06 | M-H UX | 4–6 d (med-high) | #1 | Incremental screens |
| 9 | **Launch motion**: PyPI release (infra ✅ this branch) + README repositioning (03 §5) + Telegram 5-min demo + benchmark/governance posts | Distribution is the binding constraint → 03/07 | **H** growth | 3–5 d (high) | #3 + 30-day exit criteria | Fix→benchmark→tell order enforced |
| 10★ | Email + Meeting agents as packs | First two of seven; seeds exist → 05 §3 | M-H product | 4–8 d (med) | #6 | Ship with consent sheets |
| 11★ | CLI decomposition + `RuntimeBuilder`; central Settings | Debt before ecosystem → 01/R11/R12 | M maintainability | 4–6 d (med) | — | Mechanical, behind tests |
| 12★ | Onboarding first-magic + suggestion chips | <5-min wedge → 06 §7 | M growth | 1–2 d (high) | #7 | — |

**Exit criteria for the quarter:** a stranger can `pipx install`, onboard in <5 min, get a streamed
answer, schedule a briefing by speaking, see its cost — and read a published benchmark that survives
hostile replication.

## 3. 1-Year Roadmap (to mid-2027) — themes by quarter

| Quarter | Theme | Contents (sources) | Effort scale |
|---|---|---|---|
| **Q4 2026** | Memory + agents | M2 graph features + resume packs replacing snapshot recall; M3 gardener + memory-diff UI; Research/CRM/Finance packs; embedding-rank option (02 P1); OG Explorer screen (06 §6.2); SDK v0 semver surface (07 §4.2) | ~35–50 d |
| **Q1 2027** | Platform + fleet | Multi-agent v2 (leases, continuations, scoped memory views — 07 §2); shared-services gateway (01/R13); parallel tool exec (R14); Google device-flow (pending decision D-1); web companion mode (06 §9); M4 files-canonical cutover | ~40–55 d |
| **Q2 2027** | Ecosystem | Registry Stage-2 (if decision-gate D-2 met); spec repo + conformance suite (B1 first step); pack-author scaffold + guide; Career/Learning agents; git-synced workspace pattern (B4 first step); yearly-memoir demo (B3) | ~35–50 d |

Sustained tracks all year: 2-week release trains; benchmark re-runs per release; mypy burn-down;
security audits before each marketing push.
**Capacity note:** this assumes 2–3 contributors by Q4 (the growth loops exist to recruit them — pack
authors first, core second). At 1 dev, the year is Q4-theme only; cut from the bottom of each quarter.

## 4. 3-Year Vision (2029) — where the bets point

- **B1:** `.og` spec is versioned, conformance-tested, and read by ≥1 non-Hachi tool; Hachi
  is its reference engine — the "Markdown of agents" position.
- **B2:** signed, reputation-weighted skill exchange; agents author and consume verified procedures;
  ClawHavoc-class attacks structurally answered (skills = data; consent diffs; provenance).
- **B3:** users with years of typed memory ask "what did I decide and why" and get evidence-linked
  answers; the memoir artifact is the category's most-shared demo.
- **B4:** one agent identity across laptop/server/phone via synced plain-text brains; local-model
  mode is first-class; the sovereignty segment's default choice.
- Honest framing: these are *directions earned by the format decision*, not forecasts. Annual
  re-derivation from then-current evidence is part of the operating rhythm.

## 5. Top-10 leverage ranking (across horizons)

1. Retrieval v2 (30d#4) — 3 days that decide whether the moat survives scrutiny.
2. Per-session serialization (30d#1) — 1 day, removes the only corruption class.
3. Streaming+interrupt (90d#1) — the felt-quality delta vs every competitor.
4. Benchmark suite + publication (90d#3) — converts claims into artillery.
5. Loud memory failures + durable queue (30d#3+90d#2) — the trust substrate.
6. Shipped-skill compliance + collision fix (30d#5–6) — credibility of our own dogfood.
7. Launch motion (90d#9) — zero→nonzero distribution; everything above feeds it.
8. Memory graph M0–M1 (90d#4) — Hermes-parity recall + the files-as-memory story.
9. Pack format + consent (90d#6) — unlocks agents, marketplace, and D9 closure.
10. Workflow Composer (90d#7) — the "no YAML" demo that sells the OS framing.

## 6. Decisions required from the user (register)

| ID | Decision | Blocks | Default if unanswered |
|---|---|---|---|
| D-1 | Hosted Google OAuth client (device-flow) — yes/no | 05 §4, Q1-2027 item | BYO-client documented path only |
| D-2 | Registry Stage-2 build threshold (proposed: ≥20 community packs in index) | Q2-2027 | Defer; Stage-1 index only |
| D-3 | Memory-file at-rest encryption default (04 §8) | M1 rollout | Off, opt-in flag |
| D-4 | Live-LLM benchmark budget ($20–60/full run, weekly) | 90d#3 M5/M6 | Engine-only metrics in CI; live monthly |
| D-5 | Marketing timing sign-off tied to 30-day exit criteria | 90d#9 | Hold until criteria green |

## 7. Consolidated risk register (top 6)

| Risk | Mitigation (owner phase) |
|---|---|
| Marketing precedes fixes → position falsified | Sequencing guard + D-5 (03 §7, 07 §4.4) |
| Claude Code closes the life-agent gap from above | Sovereignty/multi-provider segment focus (03 §7) |
| Solo-maintainer bus factor / capacity | 30-day list is 1-dev-sized; growth loops recruit; SDK + starter issues lower onboarding cost (07) |
| Benchmark results unflattering at small scale | Publish the crossover honestly — it's the credible version of the pitch (02 §8.6) |
| Typed memory extraction quality | M1 ships with labeled-set measurement; fallback to fact nodes (04 §8) |
| Windows remains second-class for always-on | Daemon restart docs + log rotation in Q4; track as release-train item (01/R18) |

---

*Engagement complete. All eight deliverables live in docs/strategy/. No code, config, or behavior was
modified anywhere in this engagement — analysis and specs only; the working tree contains only new
documentation files. Every recommendation traces to file-cited evidence; every external claim is
sourced or marked ⚠️ UNVERIFIED in its phase document.*
