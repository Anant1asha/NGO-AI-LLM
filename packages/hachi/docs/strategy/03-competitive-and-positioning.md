# Phase 3 — Competitive Position & the Switch Argument

> **⚠️ Partly superseded (2026-07-05).** See
> [`2026-07-05-competitive-review/`](2026-07-05-competitive-review/README.md) for the current landscape.
> Two assumptions below no longer hold against live competitor docs: OpenClaw **now ships native memory**
> (`MEMORY.md` + hybrid search) and Hermes **now ships governance/audit** (approval gating + append-only
> Kanban log). "Governance + visibility" is therefore table stakes, not an open quadrant. The competitor
> **security-incident** framing in this doc (CVE / exposed instances / marketplace incident) is out of
> scope for the 2026-07-05 review, which discusses control only in product-feature terms.

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy · **Date:** 2026-06-12
**Inputs:** web verification this session (two research passes, sources inline); Hachi-side claims
cite the codebase per Phases 0–2. **Markers:** 🌐 web-verified · Ⓢ single/low-authority source (treat
as directional) · ⚠️ UNVERIFIED · ✅/▶ repo evidence per earlier phases.
Voices: §1–§4 **What I found** · §5–§8 **What I propose**.

> Source-quality note: security facts below come from vendor/researcher write-ups and GitHub issues
> (medium-high authority); user-sentiment quotes often come from blogs/Medium (Ⓢ). Star counts are
> order-of-magnitude signals, not audited numbers.

---

## 1. Market map (June 2026)

**Direct (always-on personal agents):** OpenClaw (~378k★ 🌐), Hermes Agent by Nous Research (~180k★ 🌐).
**Adjacent (coding/terminal agents):** Claude Code, OpenCode (~150k★ Ⓢ), Copilot CLI, Aider, Cursor
(+cloud agents), Goose, OpenHands, Devin, Warp, and two that just changed state: **Roo Code shut down
2026-05-15** 🌐 and **Gemini CLI deprecates 2026-06-18** (→ Antigravity) 🌐.
**Converging from adjacent:** only **Claude Code** (Gmail/Calendar/Slack/Notion integrations, scheduled
Routines, "personal AI Chief of Staff" framing 🌐) and **Cursor** (Slack-triggered Automations 🌐) are
materially entering the personal-assistant space. Non-dev standalone assistants (Lindy, Reclaim) grow
in parallel 🌐.
**Hachi today:** effectively **zero public footprint** — the researcher found no index entries,
comparisons, or security write-ups mentioning it 🌐. (PyPI release infrastructure landed on this very
branch ✅ release.yml — distribution is in flight, not in market.) This matches prior internal research:
the gap is distribution, not capability (project memory, 2026-06).

## 2. OpenClaw — verified profile

| Dimension | Verified finding |
|---|---|
| Identity | Open-source personal agent by Peter Steinberger (Warelay→Clawdbot/Moltbot→OpenClaw lineage 🌐 [TechCrunch/CNBC]); Steinberger joined OpenAI Feb 2026 🌐 CNBC. ~378k★, fastest-to-100k in GitHub history 🌐. |
| Architecture | Node/TypeScript local-first **gateway** = control plane for sessions/channels/tools; Docker/SSH sandboxes for non-main sessions 🌐 repo README. |
| Channels | 20+ (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Teams, Matrix…) 🌐 repo. |
| Memory | **Plain markdown, loaded at session start**: SOUL.md, AGENTS.md, TOOLS.md, MEMORY.md + daily notes Ⓢ; human-readable/diffable, no selective loading mechanism — i.e., the "dump" model Hachi's benchmark targets. |
| Extensibility | Markdown skills; **ClawHub** registry peaked ~13.7k skills, purged to ~3.3k after audits Ⓢ. |
| Praise | "Stays running for weeks" Ⓢ; unmatched channel breadth Ⓢ; huge community/tutorial base Ⓢ. |
| Complaints | **(1) Token-bill surprises** — e.g. $47 burned in 20 min via a WhatsApp echo loop Ⓢ; mitigations are user-side env caps. **(2) Security crisis** 🌐 [Conscia/Censys/Bitsight]: CVE-2026-25253 RCE (CVSS 8.8); 21k–42k exposed instances, **93.4% without auth**; **ClawHavoc**: 800+ malicious ClawHub skills shipping AMOS stealer/RATs; 1.5M agent tokens leaked via Moltbook. **(3)** ~15 h first-week setup/tinkering Ⓢ. |

## 3. Hermes Agent — verified profile

| Dimension | Verified finding |
|---|---|
| Identity | Open-source personal agent by **Nous Research**, launched Feb 2026; ~180k★ in 4 months 🌐; Python-dominant repo 🌐. |
| Architecture | CLI-first, optional gateway; backends: local/Docker/SSH/Modal/Daytona ($5-VPS pitch) 🌐 docs; sub-agent delegation via RPC-callable Python 🌐. |
| Channels | Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, iMessage-bridge, Home Assistant… 🌐 docs (fewer than OpenClaw Ⓢ). |
| Memory | 3 layers: **autonomously generated skill documents**, FTS5 conversational search w/ LLM summaries (~10 ms Ⓢ), Honcho user modeling 🌐 docs. Skills load on demand. |
| Extensibility | **The defining feature: closed self-improvement loop** — after complex tasks (5+ tool calls) the agent writes a reusable skill; a **Curator** autonomously maintains/refactors the library Ⓢ/🌐 release notes; agentskills.io-compatible 🌐. |
| Praise | Durable memory reduces re-steering Ⓢ; "operations, not conversation" Ⓢ; 40%-faster repeat tasks (internal Nous benchmark Ⓢ — vendor-claimed). |
| Complaints | **(1) Ungoverned learning**: self-evaluation "almost always thinks it did well"; **Curator overwrites manual edits** — "dealbreaker for power users" Ⓢ. **(2) Security**: audit found 4 Critical + 9 High issues 🌐 GitHub #7826; terminal tool = raw `bash -c`, no sandbox/allowlist 🌐 repello.ai. **(3)** Pre-1.0 instability; learning loop off by default so many users never see the differentiator Ⓢ; small community Ⓢ. |

## 4. Adjacent set — one line each (full bullets in research appendix; sources inline above)

Claude Code (proprietary; CLAUDE.md+Skills+MCP; **moving into personal-assistant via integrations +
Routines** 🌐; chronic complaint: usage limits/caps Ⓢ) · OpenCode (MIT, model-agnostic TUI/desktop,
75+ providers 🌐; no assistant motion) · Copilot CLI (GitHub-context agents, custom agents/MCP 🌐;
Linux-runner limits Ⓢ) · Aider (git-native pair-programmer; RepoMap; BYOK Ⓢ) · Cursor (IDE+cloud
agents; **Slack Automations** 🌐; cost-unpredictability complaints Ⓢ) · Goose (Block, Apache-2, MCP-
first; phishing/prompt-injection red-team incident Jan 2026 Ⓢ) · OpenHands (MIT CodeAct; automations
only an RFC 🌐) · Devin (cloud ACU pricing; "last 30%" complaints Ⓢ) · Warp (Rust terminal, now
MIT/AGPL 🌐; privacy/auth gripes Ⓢ) · Roo Code (dead 🌐) · Gemini CLI (deprecating 🌐).

**Implication (observation):** the four names in the core question split into two different jobs.
OpenClaw/Hermes own the *life-agent* job; Claude Code/OpenCode own the *repo* job and only Claude Code
is crossing over. Hachi's codebase (channels, Google tools, scheduler, voice, permission tiers,
memory vault ✅ Phase 0) is built for the first job.

---

## 5. The Core Question, answered (What I propose)

> *"If someone already uses OpenClaw, Hermes Agent, Claude Code, or OpenCode, why switch to Hachi?"*

**Positioning statement:**

> **Hachi is the governed personal agent: OpenClaw-class autonomy where the safety, the spend, and
> the self-improvement are enforced by code, not by vibes.** Every capability the agent has — or
> teaches itself — is a typed, versioned, lintable, permission-scoped `.og` file you can diff and
> audit. Every token has a budget the loop enforces mid-turn. Every shell command, path, URL, and
> memory write passes a guard that exists in source, not in a system prompt. The category's two
> defining failures of 2026 — OpenClaw's exposure/marketplace crisis and Hermes' agent that rewrites
> its own brain unsupervised — are the two things this architecture was built to prevent.

This is not "cheaper/open-source/similar": it is a *different construction* of the same product, and
every clause is backed by code that exists today (with two engineering caveats flagged below).

### Per-competitor switch argument

**→ From OpenClaw** (their verified pains: bills, breaches, poisoned skills):
1. *Spend is governed in the loop*, not by a user-remembered env var: per-session **and per-turn**
   cost/token caps enforced between LLM calls ✅ loop.py:327–360, 469–473, live cost read-models in
   TUI/gateway ✅ orchestrator.py:495–502, lazy tool groups + cache-aware prompt split ✅ Phase 1 S3/S4.
   The $47-echo-loop story Ⓢ is structurally impossible under a turn cap.
2. *Exposure is opt-in, not default*: gateway binds loopback with bearer-token support and a
   security-audit CLI that CI runs with `--fail-on-medium` on PRs ✅ fastapi_app.py:207–213,
   ci.yml:30–53; permission tiers gate filesystem/shell/MCP at call time ✅ Phase 1 S5 — vs 93.4% of
   OpenClaw instances exposed without auth 🌐.
3. *Skills are auditable artifacts*: typed blocks, lint with errors/warnings, semver+changelog,
   structural-injection escaping, RBAC scopes ✅ engine.py:104–208, 621–771; serializer.py:29–40 — the
   shape of an answer to ClawHavoc (provenance/signing still to build, §6-C3).
   **Honest deltas:** 4 channels vs 20+; no community; no streaming yet (Phase 1 R3); OpenClaw's
   markdown memory is *simpler to hand-edit* than `.og` — concede simplicity, sell governance.

**→ From Hermes** (their verified pains: ungoverned self-learning, no sandbox, churn):
Hermes proved the demand for the *learning agent* — and shipped it ungoverned. Hachi has the same
loop (`save_skill` after novel tasks, hot-load, refine ✅ og_tools.py:368–431) **with the governance
Hermes users ask for**: refinements bump semver and append changelog instead of overwriting ✅
engine.py:705–747; dense-budget rejection + lint advisories bound what the agent may write ✅; manual
edits live in plain files the Curator-equivalent never silently rewrites (no auto-refactor exists —
a feature here); `::assertions` make learned procedures machine-checkable before execution ✅; and the
shell the learned skill ultimately calls is permission-gated, not raw `bash -c` ✅ Phase 1 S5 vs 🌐
repello.ai. **Honest deltas:** Hermes' FTS5 conversational recall + Honcho user modeling are ahead of
Hachi's Chroma recall in maturity; Hermes ships a Curator (autonomous maintenance) that Hachi
deliberately lacks — position the absence as a choice.

**→ From Claude Code** (now crossing into life-agent territory):
Don't fight the repo job — concede it. The switch (or *addition*) argument is sovereignty: Hachi
is self-hosted, **provider-free** (Anthropic/OpenAI-compat/OpenRouter/Groq/DeepSeek/Gemini/Ollama ✅
llm.py:424–512 — incl. fully local), channel-native (Telegram guided setup ✅ telegram_setup.py),
permission-tiered for non-developer trust, with hard cost caps instead of subscription throttles
(the top verified Claude Code complaint Ⓢ). For an OpenAI-compatible client ecosystem it *is* an
endpoint ✅ fastapi_app.py:435–457. **Honest deltas:** Claude Code's model quality/integration polish
and Anthropic's distribution are unmatched; a claude.ai subscriber happy inside that ecosystem has
little reason to move — target the self-host/multi-provider/cost-sensitive segment.

**→ From OpenCode:** same terminal sensibility, different job. Pitch Hachi as the *second* agent
on the box: OpenCode writes the code, Hachi runs the life — and exposes an OpenAI-compatible API
OpenCode users can point tools at. No head-on switch claim (their job isn't ours).

### What we must NOT claim (anti-positioning, from Phase 2)

- Not "97.2% cheaper than everyone" — the number is vs an uncached strawman; below ~30k-token
  libraries cached dump-all competes ✅ Phase 2 §3.1. Lead with *budget enforcement + selective
  loading built for libraries that outgrow context*, publish the Phase-2 benchmark when it exists.
- Not "smarter retrieval" until Retrieval v2 lands — today's P@1 ≈ 23% ▶ would be falsified by any
  blogger in an afternoon (Phase 2 R-a).
- Not "the safest agent" as an absolute — claim *governed by construction*, evidenced by the
  security-audit CLI, tiers, and CI gates; invite audits.

## 6. The 3 capabilities Hachi must nail to win (What I propose)

**C1 — Trustworthy always-on (the OpenClaw counter).** Streaming + per-session serialization +
durable job queue + daemon restart/log hygiene (Phase 1 R1–R5, R18) so "leave it running for weeks"
is true *and* safe; secure-by-default gateway posture marketed loudly. *This makes the governance
story experientially real: an agent that never double-runs your turn, never loses a memory write,
never surprises the bill.*

**C2 — The governed learning loop (the Hermes counter, and the moat).** Retrieval v2 + qualified
node IDs + exemplary shipped skills (Phase 2 P0s), then make `save_skill` the hero feature: every
learned skill = diffable, versioned, linted, assertion-checked, scope-tagged `.og`. Add provenance +
signing + lint-gated publishing for packs (pre-marketplace), so the ClawHavoc failure mode is
structurally answered before a registry exists.

**C3 — Five-minute sovereign onboarding (the distribution wedge).** `pipx install hachi-og` →
`quickstart` → Telegram guided setup ✅ (this branch) → first scheduled briefing, on any provider
including local — under 5 minutes, zero config files. Prior internal research (project memory):
capability bar is already met; *distribution* is the binding constraint — PyPI release (this branch),
README repositioning per §5, and the published benchmark are the three artifacts that convert.

## 7. Risks to this position

1. **Claude Code closes the gap from above** (integrations+Routines already shipping 🌐) before
   Hachi has distribution — mitigation: provider-freedom + self-host segments Anthropic won't serve.
2. **The governance pitch gets falsified** by the Phase-1/2 defects (unserialized sessions, silent
   memory loss, retrieval misses) if marketing precedes the P0 fixes — sequencing is the strategy.
3. **OpenClaw hardens** (post-crisis security investment is likely) — mitigation: governance must be
   *architectural* (typed skills, tiers, budgets), not a checklist OpenClaw can copy in a sprint.
4. **Hermes ships governance** (versioned skills would be a small PR for them) — mitigation: the
   `.og` format depth (assertions, RBAC, block-granular cost) is the part that isn't a sprint.

## 8. Carried forward

Phase 4 (memory redesign) should steal what's verified-good: Hermes' FTS5 session recall + user
modeling 🌐, OpenClaw's human-readable daily-notes ergonomics Ⓢ — expressed as `.og` so the §5
governance claim extends to memory. Phase 5's marketplace design must start from ClawHavoc as the
threat model. Phase 6 UX benchmarks against Claude Code/OpenCode TUIs per the brief.
