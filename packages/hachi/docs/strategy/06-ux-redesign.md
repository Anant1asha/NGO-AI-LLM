# Phase 6 — UX Redesign: TUI first, then Web

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy · **Date:** 2026-06-12
**Inputs:** current TUI structure Ⓐ (Phase 0/1 recon: tui/app.py 3,063 LOC, tabs for
Permissions/MCP/Jobs/Settings/Memory/Integrations, SlashMenu, ToolCard, modal approvals), the
read-model layer that already feeds dashboards ✅ orchestrator.py:480–635, the project's own design
brief ✅ [tui-product-brief.md](../history/tui-product-brief.md), and Phase 3 competitor verification 🌐.
**Voices:** §1 = What I found · §2–§10 = What I propose.
**Note on tui-product-brief.md:** it forbids wireframes *for its own consumer* (a Stitch prompt, tui-product-brief.md:152); the
engagement brief requires them here — included in §6. Everything in tui-product-brief.md's requirement list is
honored; §2 lists where this design goes beyond it.

---

## 1. What I found (baseline)

1. The data layer for a great operator UX **already exists and is typed**: session state, full cost
   snapshot (incl. cache reads), task ledger, skill inventory w/ usage, recall, permission audit,
   MCP inventory, jobs, sub-agent reports, tool-call timeline with durations ✅
   orchestrator.py:480–635 + runtime_read_models Ⓐ. The TUI surfaces several as flat tabs Ⓐ.
2. Two engine gaps cap the experience and are *required* by the project's own brief:
   **streamed deltas** (tui-product-brief.md:121 vs TD-2: no streaming exists) and **operator interrupt**
   (tui-product-brief.md:106 vs a synchronous `loop.run()` with no cancellation path ✅ loop.py:362–593 — feasible
   as a cooperative flag checked at the top of each iteration, loop.py:407).
3. Permission approvals already flow through modal screens via `InteractivePermissionGate` Ⓐ — the
   hard part (a real approval pipeline) exists; the UX around it is minimal.
4. No streaming + whole-reply rendering makes the agent *feel* slower than competitors even at equal
   latency (Phase 1 W3).
5. tui-product-brief.md covers operator needs thoroughly but does not mention the three surfaces that express the
   *positioning*: an `.og` library explorer, a spend/cache economics view, and memory-diff review
   (Phase 4 gardener) — the governance story currently has no face.

## 2. Competitive interaction benchmark (patterns to steal / avoid)

| Product | Steal | Avoid |
|---|---|---|
| Claude Code 🌐 | Streaming + Esc-interrupt as table stakes; inline permission prompt with allow-once/always; plan-then-execute mode; `/status`-style cost intro­spection | Usage-limit anxiety (top complaint Ⓢ) — Hachi shows *caps you set*, not limits imposed |
| OpenCode 🌐 | First-class agent/model switcher; session list + resume as a primary surface; theming | — |
| Copilot CLI 🌐 | Explicit modes (ask/plan/autopilot) mapping cleanly to permission posture | GitHub-only context assumptions |
| Warp 🌐 | Block model (every action = a discrete, addressable card) and a universal command palette | Hiding raw output by default from operators |
| Gemini CLI 🌐 | (deprecating 2026-06-18 — benchmark only as a cautionary tale: terminal UX without a durable platform dies) | — |

Interaction details above are product-docs/community-level knowledge 🌐/Ⓢ; none affect engine design.

## 3. UX principles (proposal)

P1. **Governance has pixels.** Spend, caps, permission tier, pending approvals, and memory writes are
    *ambient* — always one glance away, never buried in a tab. This is the positioning, rendered.
P2. **Stream everything; never block the prompt.** Deltas render as they arrive; input stays live;
    Esc always offers interrupt (cooperative cancel).
P3. **Every action is a card** (Warp's block insight, already half-built as ToolCard Ⓐ): collapsed =
    one line; expanded = full payload, duration, tokens, related job/permission/event links
    (tui-product-brief.md:116 "errors actionable by linking").
P4. **Drill, don't dump** (tui-product-brief.md:137–144): summaries first, payloads on demand — the UI mirrors the
    3-pass philosophy of the engine.
P5. **The library is a place.** Skills and memory are browsable, diffable artifacts — the `.og` moat
    must be *seen* to be believed.
P6. **Errors propose their own recovery** (§8): every failure state names its next action.
P7. **80 columns is a citizen.** Sidebar collapses (exists Ⓐ); wireframes verified ≤94 cols, degrade
    to stacked panes.

## 4. Information architecture (proposal)

Consolidate today's seven flat tabs Ⓐ into five areas (tui-product-brief.md's seven product areas map cleanly):

```
Chat (home)      Library            Ops                 Spend            Setup
transcript       skills explorer    turn timeline       session cost     provider+model
turn timeline ▸  memory explorer    jobs (active/fail)  cache hit-rate   permissions tier
approvals inbox  packs (installed)  schedules           per-turn caps    integrations
                 lint status        sub-agents          context meter    channels · doctor
                                    runtime events      budget history   diagnostics/audit
```

Global: a **status strip** (always visible — tui-product-brief.md:45–55) and a **command palette** (`ctrl-k`:
actions, sessions, skills, schedules, settings — fuzzy, the Warp pattern). Slash commands remain the
power path (SlashMenu exists Ⓐ).

## 5. Key screens (full list; three wireframed in §6)

1. **Chat home** — streaming transcript + ambient governance strip + inline approvals (§6.1).
2. **OG Explorer** — library tree, node inspector with literal Pass-1/2/3 progressive disclosure,
   usage + lint + collision warnings, edit/diff/graph (§6.2).
3. **Ops timeline** — per-turn execution trace from `ToolCallSnapshot`+events; jobs, schedules,
   sub-agent lanes (§6.3).
4. **Spend** — cost/token/cache panel from `CostSnapshot` ✅ (input/output/cache-read/write,
   call_count, $) + context meter (estimate_token_count ✅ memory.py:400–413) with a breakdown of
   *what's in context* (system/skills-loaded/history) and compaction events surfaced (events exist ✅
   loop.py:418–431).
5. **Approvals inbox** — pending + audit trail (read-model exists ✅), approve/once/deny + rationale
   (tui-product-brief.md:107–111).
6. **Memory review** — Phase 4 gardener diffs as reviewable cards (approve merge/supersede); recall
   tester ("what would the agent remember about X?").
7. **Workflow composer view** — the Phase 5 §5 preview card (trigger, steps, scopes, est. cost,
   dry-run) rendered in TUI and Telegram.
8. **Onboarding** — §7.
9. **Doctor/diagnostics** — existing `doctor`/security-audit output as a screen with fix-actions
   (tui-product-brief.md:93–95).

## 6. Wireframes — top 3 TUI screens (proposal)

### 6.1 Chat home (streaming, governance strip, inline approval)

```
┌ hachi ▸ s:8f3a92 “billing migration”   claude-haiku-4-5 ▸ anthropic   tier:guided ──────┐
│ ● ready   jobs:2   approvals:1!   spend $0.41 ▸ cap $2.00/turn   ctx ▓▓▓▓▓░░░░░ 47%        │
├────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ you ▸ continue the database migration from last month          │ TURN 41        ▸ expand     │
│                                                                │ 0.1s  recall   220t pack    │
│ ▦ memory · billing-db-migration — in-progress                  │ 1.2s  llm #1   3.1k in      │
│   blocked: payments (FK cycle) · decision: pgloader            │       (2.9k cached) 86 out  │
│   runbook §4 · freeze til Jul 1                    220t  [▸]   │ 0.2s  load_skill            │
│                                                                │       pg_migration  128t    │
│ ⚙ run_terminal_command · psql -f pre_drop_fk.sql       ✓ 0.8s  │ 0.8s  ⚙ terminal  ✓         │
│   └ 14 lines · [enter] expand · [j] related job                │ …     llm #2  streaming     │
│                                                                ├─────────────────────────────┤
│ hachi ▸ Dropping the payments↔refunds FK per runbook §4,       │ MEMORY WRITES               │
│ then re-running pgloader for the payments table…▌              │ +1 episode (queued #129)    │
├────────────────────────────────────────────────────────────────┴─────────────────────────────┤
│ ⚠ approval · write_file → ~/work/billing/migrate/post_fk.sql (outside allowed paths)         │
│   [a]pprove session · [o]nce · [d]eny · [v]iew diff                              esc=stop ■  │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ ❯ _                                                  ctrl-k palette · /skills /ops /spend     │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 OG Explorer (Library)

```
┌ library ▸ skills   42 nodes · 6 packs · lint: 3⚠ 2 collisions!        filter ❯ migra▌ ──────┐
├──────────────────────────────────┬────────────────────────────────────────────────────────────┤
│ ▾ projects/billing-db-migration  │ node ▸ use-pgloader                 decision · conf 1.0    │
│   ● billing-db-migration  proj   │                                                            │
│   ● use-pgloader          dec    │ PASS 1 · index    migration, pgloader, tooling             │
│   ○ migrate-payments      task ! │ PASS 2 · dense    Decision: pgloader, not DMS. Accepted.   │
│   ○ fk-cycle-issue        ins    │ PASS 3 · full     (412t) [enter to load] ─────────────     │
│ ▸ google/            5 skills    │   DMS spike failed on enum casts (3 days lost)…            │
│ ▸ roles/             5 ⚠2 collid │                                                            │
│ ▸ learned/           3 (agent)   │ edges   supersedes→use-dms · about→billing-db-migration    │
│ ▸ journal/2026-06    12 nodes    │ usage   7 loads · last 06-10 · stops at pass-2: 71%        │
│                                  │ lint    ⚠ dense 38>30t   version 1.4.0 · changelog [c]     │
├──────────────────────────────────┴────────────────────────────────────────────────────────────┤
│ [enter] load · [e]dit · [d]iff vs git · [g]raph · [b]enchmark · [n]ew    tab: skills⇄memory   │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

*(The “PASS 1/2/3” inspector is the moat made visible: users watch progressive disclosure work, with
real token prices from `peek` ✅ engine.py:463–497. Collision and lint badges surface Phase 2's
findings instead of hiding them.)*

### 6.3 Ops timeline

```
┌ ops ▸ timeline │ jobs │ schedules │ sub-agents │ events                  sse ● live ─────────┐
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│ turn 41  10:02:01 → 10:02:19 · 18.2s · $0.038 · 3 llm calls · cache 92%                        │
│  ├ recall            ▏0.1s   220t resume pack                                                  │
│  ├ llm #1            ▎1.2s   in 3.1k (2.9k cached) · out 86                                    │
│  ├ load_skill        ▏0.2s   pg_migration · group auto-unlocked                                │
│  ├ ⚙ run_terminal…   ▎0.8s   ✓ exit 0                                                          │
│  ├ llm #2            ▍1.9s   streaming…                                                        │
│  └ memory.sync       → job #129 (queued)                                                       │
│ turn 40  09:58 · 6.1s · $0.011 · ✓                                              [enter] drill │
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│ jobs  #129 fact_extraction · pending   #127 session_title · ✓ 0.4s   failed: 0                │
│ sched morning_briefing ▸ next Mon 08:00 ·  standup_digest ▸ paused                             │
│ subs  researcher #12 ✓ 41s · 9.2k tok est · report [r]                                         │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 7. Onboarding (TUI) — time-to-first-magic < 5 min (Phase 3 C3)

`pipx install hachi-og` → `hachi` →
1. Splash (exists Ⓐ) → provider picker incl. **local Ollama** and free-tier options ✅ llm.py presets;
   key paste or Google device-flow (Phase 5 §4) — validated live before proceeding ✅ provider
   validation exists Ⓐ.
2. Permission tier wizard (exists ✅ workspace.py:208–317) — re-rendered as one screen with plain-
   language consequences.
3. **First-magic moment** (new): pre-seeded suggestion chips — “▸ what's the weather in <detected
   city>” · “▸ set up a morning briefing” — the second one walks straight into the Workflow Composer
   preview. Success = a scheduled artifact the user can see in Ops.
4. Channel hookup offer (Telegram guided setup exists ✅ telegram_setup.py) — deferred-able.
Resumable via onboarding state file ✅ paths.py:33 (tui-product-brief.md:90–92).

## 8. Error recovery matrix (proposal)

| Failure | Surface today | Proposed UX |
|---|---|---|
| Budget cap hit (✅ loop.py:411–415) | `[BUDGET LIMIT REACHED]` text | Card: spend so far, what was mid-flight; [raise cap once] [resume] [end] |
| Iteration limit (✅ loop.py:591) | `AgentException` error | Needs Phase 1 R15: partial summary + [continue 15 more] |
| Tool error (✅ is_error path) | red ToolCard Ⓐ | + [retry tool] [open related skill] |
| LLM transient | auto-retry ✅ loop.py:302–325 | surface retry count inline (event exists) |
| Job failed | Jobs tab Ⓐ | toast + inbox badge; [retry] enqueues again (R5) |
| Memory write blocked/quarantined ✅ | invisible today (TD-5) | Memory review badge: “1 quarantined write” + view/release flow |
| Gateway/SSE drop | reconnect Ⓐ | status-strip ◌ + cursor-replay on reconnect (read_events_since ✅) |

## 9. Web UI for non-technical users (proposal — second priority per brief)

Audience shift: the operator console (current 4-route TanStack app Ⓐ) stays for operators; add a
**companion mode** for the household user the agents serve. Same gateway, same read-models, same SSE.

- **Home = chat + Today card** (next schedules, pending approvals, yesterday's agent activity in
  plain language).
- **Approvals inbox** as the centerpiece (mobile-friendly): plain-language permission sheets — “Hachi
  wants to *send an email* to Priya. [Allow once] [Always for drafts I approve] [Deny]”.
- **Workflows gallery**: Composer previews as cards; toggle/pause; run history with cost in ₹/$.
- **Memory browser**: Phase 4 nodes rendered as editable cards grouped by project/person — *“what
  does it know about me?”* answered in one screen (deletion = `core_delete_memory` ✅ exists).
- **Pack store**: Phase 5 consent sheets; scope diffs on update.
- **Setup**: provider + Google device-flow + Telegram QR — no terminal mention anywhere.
Principles: no jargon (“context window” → “working memory”), approval-centric, every agent action
reviewable after the fact (audit read-models ✅).

## 10. Dependencies & effort (feeds Phase 8)

| Item | Depends on | Effort (conf.) |
|---|---|---|
| Streaming render path (transcript + timeline) | **R3 (engine streaming)** — hard prerequisite | TUI side 2–3 d after R3 (med-high) |
| Esc-interrupt | new: cooperative cancel flag checked per iteration (loop.py:407) + TUI wiring | 1–2 d (high) |
| IA consolidation to 5 areas + status strip + palette | — | 3–5 d (medium) |
| OG Explorer (6.2) | Phase 2 P0s (collision/lint data honest) | 4–6 d (medium) |
| Ops timeline (6.3) | read-models ✅ (data exists) | 2–4 d (med-high) |
| Spend screen + context meter | CostSnapshot ✅ | 1–2 d (high) |
| Approvals inbox + error matrix | R4/R5, R15 | 2–3 d (medium) |
| Onboarding first-magic | Composer (Phase 5) | 1–2 d (high) |
| Web companion mode | gateway ✅; design system exists Ⓐ (46 shadcn components) | 2–3 wk (low-med conf.) |

**Sequencing:** streaming + interrupt first (they change how everything else feels), then Chat home
strip, then Ops/Spend (cheap — data exists), then Explorer, then onboarding polish, web last.
