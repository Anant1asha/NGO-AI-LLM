# Hachi Competitive Strategy Review — 2026-07-05

> **Scope.** A product/strategy exercise: ground-truth on what Hachi does *today*, current-state
> research on five competitor products, a feature-by-feature gap analysis, and a positioning
> recommendation. **No code changes** — analysis only.
>
> **Method.** Hachi claims come from a full read-only codebase audit cross-checked against
> [`docs/audit/2026-07-03/`](../../audit/2026-07-03/PRODUCTION_READINESS.md). Competitor claims are
> cited to primary sources (link + fetch date) in [SOURCES.md](SOURCES.md). OpenClaw and Hermes
> findings were **adversarially verified 3-0** against live docs (2026-07-05); Claude Code / Cursor /
> GitHub Copilot permission details are from official docs but their adversarial re-check was cut
> short by a rate limit and are marked `[primary, unverified]`.
>
> **Guardrail.** All competitor control/governance discussion is in **product-feature terms**
> (what settings exist, what needs approval, what is logged/auditable) — never incident or exploit
> mechanics.

## Documents in this review

| File | Contents |
|---|---|
| [01-hachi-ground-truth.md](01-hachi-ground-truth.md) | What Hachi actually does today, area by area, with a maturity verdict and the ship-blockers |
| [02-competitive-landscape.md](02-competitive-landscape.md) | OpenClaw, Hermes, Claude Code, GitHub Copilot, Cursor — architecture, governance, memory, licensing, momentum, pain points |
| [03-gap-analysis.md](03-gap-analysis.md) | Feature gap matrix + must-have / good-to-have / god-tier classification |
| [04-first-principles-and-bets.md](04-first-principles-and-bets.md) | First-principles pass, founder-thesis stress test, positioning statement, and the strategic bets |
| [SOURCES.md](SOURCES.md) | Every cited source with date and verification status |

## Relationship to prior strategy work

This review **updates and partly supersedes** [`../03-competitive-and-positioning.md`](../03-competitive-and-positioning.md)
(2026-06-12). Two of that document's load-bearing assumptions no longer match the competitors' shipped
products (see below), and its framing of competitor security incidents is replaced here with the
product-design lesson only.

---

## Executive summary (unvarnished)

Hachi is a genuinely well-engineered agent **engine** — a real ReAct loop, a novel typed `.og` skill
format with working three-pass retrieval, call-time permission gating, multi-provider routing across
seven backends, a durable job queue, a hardened loopback gateway, and 4,151 passing tests — wrapped in
a **claim-vs-code gap large enough to block launch**. The features the brand rests on are broken or
honor-system at exactly the load-bearing points: automatic memory is a silent no-op for every real user
(audit C1), the web approval buttons never call the backend, skill governance (lint/assertions) is
advisory rather than enforced, the headline "97.6% token savings" benchmark measures a query that
silently fails (C3/C4), and roughly 85% of documented slash commands do not exist (H4).

Worse for strategy: **the two grounding assumptions the founder's wedge depends on are false as of
today's competitor docs.** OpenClaw now ships native memory (`MEMORY.md` + hybrid semantic search);
Hermes now ships governance (approval-gated memory/skill writes + an append-only Kanban audit log). So
"owner control + visibility" is no longer an empty quadrant to occupy — it is becoming **table stakes** —
and Hachi is currently *behind* on both axes it claims to win. The thesis is not dead, but it must be
re-cut deeper (verifiable/portable/owned governance + reliable memory) and, above all, the present-tense
claims must be made true before they are pitched.

## Landscape at a glance

| Product | Core bet | Strength | Weakness | Momentum |
|---|---|---|---|---|
| **OpenClaw** (MIT) | Local-first gateway; channel breadth | 23 channels; fine-grained manual access control; now native memory | Memory inconsistent across installs; trust/config friction | ~375–380k★ but velocity collapsed +40k/wk→+1.7k/wk; founder → OpenAI |
| **Hermes** (Nous) | Self-improvement loop as the product | Auto-skill learning + user modeling; Kanban board w/ append-only audit log; approval gating | Trusted-local; autonomy bounded by config knobs | ~160k★ growing 2× faster; **#1 on OpenRouter daily tokens (2026-05-10)** |
| **Claude Code** | Permission modes as first-class | 6 modes + auto-classifier + denied-actions review | Dev/IDE-bound; Anthropic-locked | Usage-based / Max sub |
| **GitHub Copilot** | Agent inside GitHub's governance plane | Default-on network allowlist; org policy controls | Repo-bound; enterprise-shaped | $10–39/seat tiers |
| **Cursor** | Agentic IDE; default-restrictive approvals | Terminal + MCP gated by default; honest limits disclosure | IDE-bound | Free / Pro ~$20 |

**Two cross-cutting findings:** (1) *harness > model* has real evidence — identical GPT-5.5 scored 61.5%
in one harness vs 87.2% in another (25.7 pts from the harness alone); (2) *governance is becoming table
stakes* — all five ship approval controls and some audit surface today.

## Positioning recommendation

> **"Hachi is the personal AI agent you can actually trust to run itself — it remembers reliably, it acts
> only inside limits you set once, and it hands you a receipt for everything it did."**

### Top strategic bets

1. **Make the claims true first** (weeks): fix auto-memory (C1), wire web approvals to the backend,
   fix file tools (C2) and the benchmark (C3/C4), publish to PyPI (H9), correct the docs (H4).
2. **Ship the trust receipt** — a signed, append-only, exportable audit record the user owns.
3. **Move governance from honor-system to enforced** — make `.og` assertions + policy block at the gate.
4. **Win on memory *reliability***, not memory existence — deterministic, inspectable, diff-able `.og`.
5. **Add a legibility surface for long-running work** (the Hermes-Kanban lesson) + a one-command import
   bridge to strip switching cost from OpenClaw / SKILL.md users.

Full reasoning in [04-first-principles-and-bets.md](04-first-principles-and-bets.md).
