# 04 — First Principles, Thesis Stress-Test & Bets

## First-principles pass

Set the competitors aside. The underlying job a personal agent exists to do is:
**"act on my behalf across my life, and let me trust it without babysitting it."**

Trust decomposes into four things that no current agent delivers *together*:

- **(a) It remembers reliably** — deterministic and inspectable, not OpenClaw's per-install lottery.
- **(b) It does only what I've allowed** — policy enforced at the gate, not prompted per-action (which
  fatigues) nor configured by coarse knobs (which is too blunt).
- **(c) It can prove what it did** — a receipt I own and can show someone (an accountant, a reviewer, a
  spouse).
- **(d) I can pick it up and move it** — brain-as-portable-files, not a hidden vendor store.

**The divergence from how everyone builds "an agent" today:** every existing product optimizes (b) as a
*prompt-approval experience*, which is exactly why they all suffer either approval fatigue or
over-permissiveness. The first-principles move is to **stop treating governance as an interruption and
treat it as an artifact.** The agent should run with *less* friction *because* its boundaries are
declared once as policy and everything it does is receipted. Approval-fatigue and opacity are the same
problem attacked from the wrong end. That reframing is what diverges from the assumed shape of an agent
(a chat loop that occasionally asks permission).

Hachi is unusually well-positioned for this because its skills, permissions, and config are already
typed `.og` files and its gateway already emits typed events + cost + permission decisions. The
substrate for (a)–(d) mostly exists; it is under-exploited and, in places, not wired up.

## Stress-testing the founder's thesis

### "Harness quality matters more than model quality"
**Largely true, with a boundary.** The Endor Labs result (same GPT-5.5: 61.5% vs 87.2% across harnesses)
and Google's "LLM ≈ 10% of the system" are strong support. The boundary: the **model sets the ceiling**
of what's achievable; the harness decides how much of that ceiling is realized and at what cost. For a
frontier task the model still gates you; for *reliability, cost, safety, and trust* — which is where
personal agents live — the harness dominates. So the thesis holds for Hachi's chosen battleground, but
"more than" should be "decides how much of the model you actually get, and owns everything the user
feels" rather than a claim that the model doesn't matter.

### "Governance + visibility is a durable moat"
**False as stated; true only in a deeper form.** As of today's docs, all five competitors ship approval
controls and some audit surface, and two of them (OpenClaw memory, Hermes governance) closed the exact
gaps the founder's wedge assumed were open. Generic "approvals + a log" is now **table stakes** — a
feature the next competitor copies in weeks, not a moat.

What would make it durable is **product depth that compounds and is expensive to retrofit**, not the
feature category:

- **Verifiability** — a signed, tamper-evident, append-only ledger the user can *export and attest*, not
  just view. (Hermes has an append-only table; nobody has the portable, provable receipt.)
- **Enforcement** — policy-as-code that *blocks at the gate*, so "safety enforced by code" is literally
  true instead of honor-system.
- **Explainability** — "why did the agent take this action" reconstructable from the trace.
- **Portability/ownership** — the brain (skills + memory + policy) as diffable, movable files, which the
  incumbents (Anthropic, GitHub) structurally *cannot* match because their business is the opposite.

That combination is a substrate property. It is the durable version of the thesis.

### Where the founder is simply right
The **ownership axis** is genuinely defensible against the incumbents (self-hosted, provider-free,
brain-as-files), and governance *demand* is real and rising (Gartner's 40%-by-end-2026). The instinct to
compete on trust is correct; the framing just has to move from "the competitors lack X" (false) to "we
make X verifiable, enforced, and owned" (open).

## What to build instead

Not a new thesis — a truer, deeper cut of the existing one:

- **Reliable memory** (beat OpenClaw's documented inconsistency), not "we also have memory."
- **Verifiable/owned governance** (the trust receipt + enforced policy), not "we also have approvals."
- **The `.og` substrate** as the reproducible, portable brain — defended on format/traversal/ownership,
  **not** on the token-savings percentage (which only becomes economically load-bearing above library
  sizes no current user has, and whose headline number is currently mis-measured — see C3/C4).

---

## Positioning statement

> **"Hachi is the personal AI agent you can actually trust to run itself — it remembers reliably, it
> acts only inside limits you set once, and it hands you a receipt for everything it did."**

Internal framing: *governed autonomy you can audit and own.* Drop the older
"OpenClaw-with-memory / Hermes-with-control" dichotomy — it is false against current competitor docs and
a technical evaluator will falsify it in one doc fetch.

## The strategic bets

1. **Make the claims true first (weeks, not quarters).** Fix C1 (memory), the web approval wiring, C2
   (file tools), C3/C4 (benchmark), H9 (PyPI), H4 (docs). Nothing else matters until a new user's first
   hour matches the pitch. *This is the whole ballgame — you cannot win a trust argument from a product
   that doesn't do what it says.*
2. **Ship the trust receipt.** Turn the existing runtime_events + cost + permission logs into a signed,
   append-only, exportable audit record with a "show me what it did today" view. The durable,
   compounding differentiator — and a sub-60-second demo.
3. **Move governance from honor-system to enforced (policy-as-code).** Make `.og` assertions + lint +
   `device-permissions.og` *block at the gate*, so "safety enforced by code, not vibes" is literally
   true. Pair spend-caps and policy in one enforcement point.
4. **Win on memory *reliability*, not memory *existence*.** Position against OpenClaw's documented
   cross-install inconsistency: deterministic, inspectable, diff-able memory as `.og`.
5. **Add a legibility surface for long-running work** (the Hermes-Kanban lesson) so autonomy is
   *visible*, and pair it with a one-command import bridge to strip switching cost from OpenClaw /
   SKILL.md users.

**Bottom line.** The engine is real and the ownership axis is genuinely defensible against the
incumbents. But the competitive framing is out of date and the product does not yet do what it says. Fix
the six ship-blockers, re-anchor on *reliable memory + verifiable/owned governance*, and build the
trust-receipt substrate. That is a moat made of product depth — not a feature a competitor copies in a
sprint.

---

### Honesty/pitch guardrails carried forward
- Do **not** claim OpenClaw lacks memory or Hermes lacks control — both are false against 2026-07-05
  primary docs and trivially checkable.
- Present-tense claims must be true *today*; everything else is labelled roadmap.
- Defend `.og` on format/traversal/ownership, not on the token-savings number (and never the retracted
  "95.3%" figure). Fix C3/C4 before citing any benchmark headline.
