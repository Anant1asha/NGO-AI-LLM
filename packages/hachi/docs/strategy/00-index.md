# Hachi Strategy Engagement — Index

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Role:** Principal Engineer · Product Architect · AI Systems Researcher · UX Designer · OSS Strategist
**Method:** Evidence-first. Current-system claims cite real paths/lines; external claims cite sources or are
marked ⚠️ UNVERIFIED. Observation ("What I found") is kept separate from recommendation ("What I propose").
No code/config changes are made by this engagement — analysis and specs only, in this directory.

## Phase ledger

| Phase | Deliverable | Status | Checkpoint summary |
|---|---|---|---|
| 0 — Repo reconnaissance | [00-recon.md](00-recon.md) | ✅ Done (2026-06-12) | Inventory complete; .og = skills/brain/permissions/config (no OG memory layer exists); 1,357 tests green; benchmark gate real but narrow; 8 doc-vs-code discrepancies logged |
| 1 — Architecture review | [01-architecture-review.md](01-architecture-review.md) | ✅ Done (2026-06-12) | 11 strengths / 18-item debt register; critical: unserialized concurrent chat (TD-1), no streaming (TD-2), in-memory-only job layer (TD-3), event-loop blocking routes (TD-4), silent memory-write loss (TD-5); gates: ruff clean, mypy 386 errors non-blocking; 20 recommendations P0–P2 |
| 2 — Object Graph deep evaluation + benchmark spec | [02-object-graph-eval.md](02-object-graph-eval.md) | ✅ Done (2026-06-12) | Live probe: ~23% P@1 retrieval, stopword noise, shipped library collides (identity ×6) & 23/29 files lack ::index; graph machinery data-free (1 requires edge); cost model: cached dump-all cheaper below ~30k-token libraries; citations verified (2 external real; 2604.27820 is first-party, presented as independent); 6-arm benchmark spec w/ retrieval-quality CI gate |
| 3 — Competitive position & switch argument | [03-competitive-and-positioning.md](03-competitive-and-positioning.md) | ✅ Done (2026-06-12) | Verified: OpenClaw (378k★; CVE-2026-25253, 42k exposed instances, ClawHavoc, bill pain) & Hermes (180k★; ungoverned self-learning, no sandbox) — Hachi positioning: "the governed personal agent" (budgets/guards/typed versioned skills in code); 3 capabilities: trustworthy always-on, governed learning loop, 5-min sovereign onboarding; Roo dead, Gemini CLI deprecating, Claude Code crossing over |
| 4 — Next-gen memory system proposal | [04-memory-redesign.md](04-memory-redesign.md) | ✅ Done (2026-06-12) | OG Memory Graph: typed nodes (episode/fact/decision/task/project/person/insight) + edges (t/about/supersedes/caused_by/blocked_by/evidence) in diffable memory/*.og; 3-stage recall (FTS5+BM25 ⊕ embeddings ⊕ graph expansion) → ~220-tok resume packs; worked "continue the migration" example; M0–M4 migration (15–25 d) behind Phase 1 P0s |
| 5 — Agent platform (Workspace, NL automation, marketplace) | [05-agent-platform.md](05-agent-platform.md) | ✅ Done (2026-06-12) | Agents-as-packs over one kernel; 7 agents composed from existing primitives; Google device-flow onboarding (org decision flagged); NL Workflow Composer compiling speech → save_skill+create_schedule with read-only-gate dry-run; 5-layer permission model (pack scopes close new gap D9); .ogpack marketplace w/ ClawHavoc→control mapping ("skills are data, no install-time execution") |
| 6 — UX redesign (TUI first, then Web) | [06-ux-redesign.md](06-ux-redesign.md) | ✅ Done (2026-06-12) | 7 principles ("governance has pixels", stream everything, every action is a card); 5-area IA + status strip + palette; 3 ASCII wireframes (Chat w/ inline approvals, OG Explorer w/ literal Pass-1/2/3 inspector, Ops timeline); onboarding <5 min w/ first-magic moment; error-recovery matrix; web companion mode for non-tech users; hard prereqs: engine streaming (R3) + cooperative interrupt — both required by the project's own tui-product-brief.md |
| 7 — Multi-agent, bold bets & growth | [07-future-and-growth.md](07-future-and-growth.md) | ✅ Done (2026-06-12) | Multi-agent v2: shared task graph + leases + continuations, star control retained (~1 wk); 4 OG-derived bets (format standard, verified skill economy, life graph, device-fleet sovereignty) + kill list; growth: two onramps (pack authors need no Python), 5 loops incl. "bring your memory" importer aimed at Hermes users; SECURITY.md missing — P0 credibility gap; fix→benchmark→tell sequencing guard |
| 8 — Roadmap synthesis | [08-roadmap.md](08-roadmap.md) | ✅ Done (2026-06-12) | 30-day "make the claims true" (14 items, ~17 d, 1 dev); 90-day "prove and show" (streaming, durable queue, benchmark v1 + publish, memory M0–M1, packs, Composer, launch); 1-yr quarter themes; 3-yr = the four bets; top-10 leverage ranking; 5 user decisions (D-1..D-5); risk register. **ENGAGEMENT COMPLETE — all 8 phases delivered.** |

## Follow-on

| Artifact | Purpose |
|---|---|
| [09-execution-plan.md](09-execution-plan.md) | The engagement's roadmap (Phase 8) broken into implementation phases, parallel lanes, and agent-executable task specs with dependencies, acceptance criteria, and phase gates. **Start here to implement.** |
| [2026-07-05-competitive-review/](2026-07-05-competitive-review/README.md) | Fresh (2026-07-05) competitive/gap analysis + positioning. **Updates and partly supersedes [03-competitive-and-positioning.md](03-competitive-and-positioning.md):** two of that doc's assumptions no longer hold — OpenClaw now ships native memory and Hermes now ships governance/audit, so "governance + visibility" is table stakes rather than an open quadrant. Competitor incident framing is replaced with the product-design lesson only. |
| [../audit/2026-07-03/BACKLOG.md](../audit/2026-07-03/BACKLOG.md) | **Consolidated forward backlog (2026-07-05).** Fuses the 2026-07-03 production audit (now remediated) with the competitive review's strategic bets into cold-start-able unit tasks. **Start here for the next session's work** — it carries the state snapshot, the two blocked owner decisions (H9/M10), and Workstreams A–G. |

## Standing evidence notes

- Test baseline (2026-06-12, Windows): `uv run --frozen python -m pytest -q` → **1,357 passed / 13 skipped / 60.8 s**.
- Built-in OG benchmark observed: `nodes=42 | baseline=8991 | 3-pass=253 | savings=97.2%` (methodology caveats in 00-recon §8).
- arXiv link `arxiv.org/abs/2604.27820` from the brief: ⚠️ UNVERIFIED (ID format implies an April-2026 submission; to be checked during Phase 2/3 web verification, alongside docs/reference/benchmark.md citations).
- Evidence markers used throughout: ✅ direct read · Ⓐ subagent-verified · ▶ executed/observed · ⚠️ UNVERIFIED.
