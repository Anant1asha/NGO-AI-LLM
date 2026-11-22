# 03 — Gap Analysis & Classification

## Feature gap matrix

Legend: **H**ave (works end-to-end) · **P**artial (exists, not wired/reliable) · **M**issing.
Hachi column reflects the verified state in [01-hachi-ground-truth.md](01-hachi-ground-truth.md).

| Capability | Hachi (today) | OpenClaw | Hermes | Claude Code | Cursor / Copilot |
|---|---|---|---|---|---|
| Cross-session persistent memory | **P** — vault exists; **auto-extract no-op (C1)**; explicit `remember` works | **H** (inconsistent across installs) | **H** (`MEMORY.md`/`USER.md` + episodic SQLite) | P (project files) | P (rules/memories) |
| Self-improvement (agent writes/refines skills) | **P** — `save_skill` writes versioned `.og`; not auto-triggered; governance advisory | M (static markdown) | **H** (auto-create + refine loop) | M | M |
| User modeling | M | P (facts in `MEMORY.md`) | **H** (`USER.md` + Honcho) | M | M |
| Messaging-channel breadth | **P** — Telegram real; Slack/Discord outbound; generic webhook; WhatsApp/email unverified | **H** (23 channels) | P (15+) | M | M |
| Fine-grained permission model | **H** — call-time gate, 3 tiers, blocked-command patterns | **H** (pairing/allowlist/sandbox) | **H** (write-approval gating) | **H** (6 modes) | **H** |
| Approval UX that actually enforces | **P** — **web approve/decline never calls backend**; TUI real | H | H (staged review) | **H** | **H** |
| Audit trail / activity log | **P** — interaction_log + runtime_events; not signed/exportable | P (plain files) | **H** (append-only `task_events` + live dashboard) | P ("Recently denied") | P (logs/policies) |
| In-loop spend caps | **H** — per-session/turn caps enforced mid-turn | M (runaway-cost complaints) | M | P (usage limits) | P |
| Multi-provider / no lock-in | **H** — 7 providers + routing | H | H | **M** (Anthropic only) | P |
| Token-efficient typed skill substrate | **H** — `.og` typed/versioned + 3-pass (benchmark headline broken) | M (markdown) | M (markdown) | M | M |
| Task board / long-running-goals surface | M | P | **H** (Kanban) | M | P |
| Eval / regression replay gate | **H** — `hachi eval run` in CI | M | M | P | P |
| One-command install / instant first-run | **P** — `quickstart` works; **PyPI publish broken (H9)** | **H** (`npm i -g`) | H | **H** | **H** |
| Sandboxed execution | **P** — Docker + gates + SSRF guards, some bypasses | P (non-main sandbox) | P | P | P |

**The uncomfortable read.** The columns where Hachi is *uniquely* **H** are `.og`, in-loop spend caps,
multi-provider, and the eval gate. The columns the *pitch* leans on — memory, self-improvement, enforced
governance/audit — are **P** for Hachi and **H** for the competitors.

---

## Classification

### Must-have (table stakes — ranked)

Each is something without which a specific user bounces or a technical evaluator falsifies the pitch on
contact. Items 1–6 are the audit's Critical/High list — ~1–2 weeks of concentrated work.

1. **Automatic memory that persists (fix C1).** The category's whole premise is "it remembers." Today
   Hachi silently writes nothing; both competitors do this. *Without it, Hachi is a chat wrapper, not a
   personal agent.*
2. **Approvals that enforce (wire web approve/decline to backend).** The "leash" is the headline. A
   button that renders success while doing nothing is trust-destroying the moment it's noticed. *Without
   it, the governance story is theater.*
3. **A working, honest benchmark (fix C3/C4).** The one number proving the `.og` moat measures a failed
   query; a technical reviewer reproduces the problem in an afternoon. *Without it, the moat claim is
   discrediting, not just absent.*
4. **Working install path (publish to PyPI, fix H9).** `pipx install hachi-og` 404s; OpenClaw's
   `npm i -g` is the bar. *Without it, you lose the user at step zero.*
5. **File-attachment tools that don't crash (fix C2).** Basic competence; a crash on "look at this
   screenshot" ends the session.
6. **Truthful docs (fix H4 — ~85% of slash commands don't exist).** Every missing command compounds the
   trust deficit.
7. **Reliable, inspectable memory storage.** OpenClaw's documented weakness is memory inconsistency
   across installs. Being *deterministic and inspectable* where they're flaky is the cheapest credible
   differentiator available.

### Good-to-have (real differentiators, not urgent)

- **Channel-breadth trajectory** — verified WhatsApp/Signal/Slack-inbound closes the visible OpenClaw gap
  without needing all 23.
- **A task-board / long-running-goals surface** — Hermes's Kanban makes autonomy *legible* and is a
  momentum driver; Hachi already has the durable job queue underneath.
- **Budget-aware model downgrade** — auto-route to a cheaper model as a session nears its cap; a natural
  extension of the in-loop caps that no competitor pairs with spend governance.
- **Skill marketplace / import bridge** — a one-command "import my OpenClaw/SKILL.md skills" kills
  switching cost; the SKILL.md→`.og` bridge already exists in code.
- **Explainability surface** ("why did the agent do X") built on the existing runtime_events taxonomy —
  the visible half of god-tier bet #1.

### God-tier (category-defining — each tied to a falsifiable gap)

1. **The portable, signed "trust receipt."** *Gap:* Hermes has an append-only `task_events` log,
   OpenClaw has plain files, but none produces a **tamper-evident, user-owned, exportable audit record**
   a third party could be shown to verify what the agent did, when, under what approval, at what cost.
   Hachi already emits typed runtime_events + cost records + permission decisions; turning that into a
   signed, exportable ledger is bounded — and it's the governance feature that **compounds and is painful
   to retrofit** onto a markdown-file competitor.
2. **Policy-as-code enforcement (not honor-system).** *Gap:* every competitor's model is either
   per-prompt (fatiguing) or config-knob (coarse). A declarative policy — "never spend >$5/day, never
   email outside my domains without approval, never touch `~/taxes` in guided mode" — **enforced at the
   gate and provable in the receipt** — is unshipped. Hachi's `device-permissions.og` + call-time gate is
   80% there; the missing 20% is making `.og` assertions/lint *block* in the execution path (today
   advisory, audit M2).
3. **Deterministic, diff-able agent brain.** *Gap:* OpenClaw's own users report memory that behaves
   differently on three machines. Because Hachi's skills (and potentially memory) are typed, versioned
   `.og` files, the agent's entire "brain" can be **inspected, diffed, rolled back, and moved between
   machines byte-for-byte** — a reproducibility story markdown-blob competitors structurally can't tell.
   This is the honest cut of the `.og` moat (not the token-savings number, which only matters at library
   sizes no user has yet).
4. **Governed autonomy at long-running scale.** *Gap:* Hermes made "long-running goals on a board" the
   momentum story but pairs it with a trusted-local model. A board of autonomous, multi-day goals where
   **every step is spend-capped, policy-enforced, and receipted** combines Hermes's legibility with
   Hachi's control — which neither side has.

Bets 1–3 are one insight: **make the agent's behavior, brain, and budget into owned, verifiable,
portable artifacts.** That is the only "governance" story that isn't copied in a sprint, because it's a
substrate property, not a UI feature.
