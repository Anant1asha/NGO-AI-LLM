# 02 — Competitive Landscape (current state, cited)

*All dates are fetch dates. OpenClaw and Hermes claims were adversarially verified 3-0 against live
primary sources on 2026-07-05. Claude Code / Cursor / Copilot permission details are from official docs
but their adversarial re-check was interrupted by a rate limit — marked `[primary, unverified]`. Full
source list in [SOURCES.md](SOURCES.md).*

---

## OpenClaw — MIT, self-hosted personal agent

- **Architecture bet.** A **local-first Gateway** acting as a "single control plane for sessions,
  channels, tools, and events," with multi-agent routing to isolated per-agent workspaces. Breadth of
  channels is the headline. *(README, 2026-07-05, verified 3-0.)*
- **Governance model (product terms).** Manual, fine-grained access control: unknown senders get a
  short **pairing code** and are ignored until approved (`openclaw pairing approve …`); configurable
  sender **allowlists** (`allowFrom`); a **`dmPolicy`** setting (`pairing` default vs `open`); and an
  opt-in **sandbox mode** for non-main sessions. This is access control (who/what can reach the agent),
  not per-action oversight or a rich audit trail. *(README, verified 3-0.)*
- **Memory & self-improvement.** **Has native memory** — file-based, plain Markdown in the agent
  workspace: `MEMORY.md` (durable facts/preferences) "loaded at the start of every DM session," plus
  daily notes and a bundled memory-core plugin. A **`memory_search`** tool does **hybrid search**
  (vector similarity + keyword) with configurable embedding providers (OpenAI default; Gemini, Voyage,
  Mistral, local, Ollama, Bedrock, …). No agent-driven skill self-improvement loop. *(memory docs,
  2026-07-05, verified 3-0.)* → **This refutes the grounding claim that OpenClaw has "no native memory."**
- **Licensing / pricing.** MIT, free, self-hosted, no paid tier. *(README, verified 3-0.)*
- **Momentum.** ~375–380k GitHub stars / ~78k forks by mid-2026 (hit 250k by early March — surpassing
  React's 10-year star total in ~60 days), **but star velocity collapsed from +40k/week (Feb peak) to
  +1.7k/week by May**. Founder Peter Steinberger joined OpenAI in February 2026; the project moved to an
  independent foundation with OpenAI as sponsor. Consumer virality "cooled" amid rising compute cost and
  trust/config concerns. *(glukhov popularity; smartproductivitytools; "OpenClaw is dead" blog.)*
- **Pain points (product framing).** **Memory inconsistency across installs** — a documented user report
  (v2026.3.8): three colleagues' machines stored memory three different ways (SQLite / daily markdown /
  nothing). Rising compute cost; setup/trust friction; early promoters publicly stepping back.

---

## Hermes Agent — Nous Research

- **Architecture bet.** The **self-improvement loop is the product**: skills auto-generated from
  completed tasks and refined during use (a `skill_manage`-style pass roughly every 15 turns), a
  persistent user model, and an episodic archive. Launched **February 25, 2026**. *(Nous docs +
  secondary coverage.)*
- **Governance model (product terms).** More than the grounding claim credited it: memory can be
  disabled (`memory_enabled: false`); writes can be **approval-gated** (`write_approval`) with staged
  review (`/memory pending`, `/memory approve/reject`); **skill writes** are gated
  (`skills.write_approval`, `/skills pending`, `/skills diff`); notifications tune via
  `memory_notifications: off|on|verbose`. The **Kanban board** maintains an **append-only `task_events`
  audit log**, persisted worker logs (`~/.hermes/kanban/logs/`), a live WebSocket dashboard, and
  live-tail CLI (`hermes kanban tail/watch`). *(memory docs + kanban docs, 2026-07-05, verified 3-0.)*
  → **This refutes the grounding claim that Hermes has "less fine-grained control/visibility."**
- **Memory & self-improvement.** Bounded, curated `MEMORY.md` + `USER.md` under `~/.hermes/memories/`,
  loaded into the system prompt at session start; `USER.md` holds identity, preferences, communication
  style, timezone, and workflow habits (user modeling); an SQLite episodic archive with FTS5
  cross-session search; a **background self-improvement review after each turn** that "may quietly save a
  memory or update a skill." *(memory docs, verified 3-0; user-modeling-via-Honcho detail is
  `[primary, unverified]`.)*
- **Licensing / pricing.** Open project from Nous Research (GitHub repo public). No per-seat pricing
  found in the researched sources.
- **Momentum.** ~160k stars growing **+3.8k/week (≈2× OpenClaw's rate on a smaller base)**;
  **overtook OpenClaw for #1 on OpenRouter's global daily token rankings on 2026-05-10 (224B vs 186B
  daily tokens)**, though OpenClaw still leads all-time cumulative (9.17T vs 6.35T). *(marktechpost
  2026-05-10; glukhov.)*
- **Pain points (product framing).** Trusted-local, single-host design; autonomy bounded more by config
  knobs (dispatch interval, concurrency, failure caps) than by rich per-action approval
  `[primary, unverified]`; fewer channels than OpenClaw.

---

## Claude Code — Anthropic `[primary, unverified re-check]`

- **Architecture bet.** Terminal + SDK coding agent; **permission modes are a first-class product
  surface**.
- **Governance model.** Six permission modes (`default`/manual, `acceptEdits`, `plan`, `auto`,
  `dontAsk`, `bypassPermissions`), each trading convenience for oversight; per-action approval is the
  default. A research-preview **"auto mode"** routes actions through a separate classifier and produces a
  **"Recently denied" review tab** with retry-under-approval, plus automatic fallback to prompting after
  repeated blocks. Permission evaluation follows a documented deterministic order (hooks → deny → ask →
  mode → allow → approval callback), and deny rules hard-override even `bypassPermissions`.
  *(permission-modes.md; agent-sdk/permissions.)*
- **Memory & self-improvement.** Project memory files (e.g. `CLAUDE.md`); no agent-curated
  self-improvement loop. Vendor-locked to Anthropic models.
- **Licensing / pricing.** Usage-based API or an Anthropic Max subscription.
- **Relevance.** A *harness-pattern* reference (approval UX, deterministic permission order, denied-
  action review), **not a direct personal-agent competitor** (developer/IDE-bound, single-vendor).

---

## GitHub Copilot (agent mode) `[primary, unverified re-check]`

- **Architecture bet.** Coding agent inside GitHub's existing governance plane.
- **Governance model.** The cloud agent ships a **built-in network firewall with a recommended
  allowlist enabled by default**, restricting outbound access to a curated set (OS repos, registries,
  package managers, CAs) unless an admin expands it. **Org/enterprise policies** are a first-class
  surface controlling which features, agents, and models users can access. *(allowlist ref; policies.)*
- **Memory & self-improvement.** None notable at the personal-agent level; repo/PR-scoped.
- **Licensing / pricing.** Free (limited) / Pro $10 / Pro+ $39 / Business $19-seat / Enterprise $39-seat;
  metered "premium requests" (Free 50, Pro 300, Pro+ 1,500 per month) with $0.04/request overage.
- **Relevance.** Reference for *default-safe posture* (allowlist-on-by-default) and enterprise policy —
  not a personal-agent competitor.

---

## Cursor `[primary, unverified re-check]`

- **Architecture bet.** Agentic IDE with a default-restrictive approval model.
- **Governance model.** **Terminal commands need approval by default**; file reads/searches proceed
  without. **All MCP tool calls require approval** even after the connection is approved, unless
  pre-approved via an allowlist. **"Run Modes"** let users allow trusted terminal calls without prompting
  (from a simple allowlist up to an auto-review classifier) — and the docs **explicitly frame these as
  best-effort guardrails, not a hard security boundary** (an honest-limits disclosure worth emulating).
  *(agent security; CLI permissions.)*
- **Memory & self-improvement.** Rules/memories files; no self-improvement loop.
- **Licensing / pricing.** Free tier; Pro ~$20/mo.
- **Relevance.** Reference for default-deny approvals + honest limits disclosure — not a personal-agent
  competitor.

---

## Two cross-cutting findings

### Harness quality vs model quality — evidence *for* the founder's thesis
- **Endor Labs benchmark:** identical **GPT-5.5 scored 61.5% functionality in one harness (Codex) vs
  87.2% in another (Cursor)** — a 25.7-point gap attributable solely to the harness. *(mindstudio,
  2026-05-01.)*
- Google's cited figure: the LLM is ~**10%** of an agentic system.
- Nuance: the model sets the *ceiling*; the harness determines how much of that ceiling is realized and
  at what token cost. It is not a pure either/or. *(adambaitch, 2026-03-04.)*

### Governance + visibility is becoming table stakes, not a moat
- All five products ship approval controls and some audit/visibility surface **today**.
- Gartner projects **40% of enterprise applications will embed task-specific AI agents by end-2026**
  (up from <5% in 2025), pulling governance from optional toward mandatory. *(zylos, 2026-05-01.)*
- Implication: "we have approvals and a log" is no longer differentiating. Durable advantage requires a
  deeper cut — verifiable, portable, owned audit + enforced policy (see
  [04-first-principles-and-bets.md](04-first-principles-and-bets.md)).
